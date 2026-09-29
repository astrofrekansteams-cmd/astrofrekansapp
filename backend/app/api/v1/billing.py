"""Billing: store verification, entitlements, order payment, refunds, earnings.

The flows, stated once:

* **Digital (StoreKit / Play Billing).** The device buys with the store, then
  sends the transaction to `POST /billing/{apple,google}/verify`. The backend
  asks the store, records the purchase against this account, derives the
  entitlement, and - for Google - acknowledges or consumes only after that is
  committed. Nothing is granted on the client's say-so.
* **Live 1:1 expert sessions.** `POST /orders/{id}/payment` with
  `method=external` opens a checkout with the external provider (none is
  configured yet: 503). The order becomes paid only when the provider's signed
  webhook says so.
* **Webhooks.** Apple V2 JWS, Google Pub/Sub OIDC, the external provider's
  signature - verified before anything changes, applied once by event id.

No endpoint accepts "paid" from a client, returns a token or JWS, or takes a
card detail.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession, SensitiveUser, UserRateLimit
from app.core.config import settings
from app.core.exceptions import AppError, NotFound
from app.core.logging import get_logger
from app.core.rate_limit import RateLimit
from app.db.models.marketplace import ServiceOrder
from app.db.models.payments import PaymentProviderEvent, RefundRequest
from app.domain.enums import SubscriptionTier
from app.domain.payments import (
    ClientPlatform,
    EntitlementKind,
    EntitlementStatus,
    PaymentGroupStatus,
    RefundActor,
)
from app.schemas.billing import (
    AccountTokensResponse,
    AppleVerifyRequest,
    BillingStatusResponse,
    ConsumeCreditRequest,
    ConsumeCreditResponse,
    EntitlementResponse,
    EntitlementSummaryResponse,
    ExpertBalanceResponse,
    ExpertEarningsResponse,
    GoogleVerifyRequest,
    LineItemResponse,
    OrderPaymentRequest,
    OrderPaymentResponse,
    OrderPaymentStartResponse,
    PaymentGroupResponse,
    PayoutResponse,
    ProductListResponse,
    PurchaseResultResponse,
    ReconcileRequest,
    ReconcileResponse,
    RefundRequestCreate,
    RefundRequestResponse,
    StoreProductResponse,
)
from app.services.ai.report_access import RESERVATION_PREFIX, report_entitlement_codes
from app.services.payments.catalog import (
    COSMIC_PLUS,
    PLAN_ENTITLEMENTS,
    PREMIUM,
    StoreCatalogService,
)
from app.services.payments.entitlements import EntitlementService
from app.services.payments.factory import (
    billing_status,
    get_apple_provider,
    get_external_provider,
    get_google_provider,
)
from app.services.features import catalogue as feature_catalogue
from app.services.payments.order_payments import OrderPaymentService
from app.services.payments.providers.base import (
    InvalidProviderNotification,
    StoreEnvironmentRejected,
    StoreNotConfigured,
    StoreVerificationFailed,
)
from app.services.payments.purchases import (
    StorePurchaseService,
    apple_account_token,
    google_account_id,
)
from app.services.payments.refunds import RefundService
from app.services.payments.settlement import SettlementService
from app.services.payments.store_notifications import StoreNotificationService

logger = get_logger(__name__)


router = APIRouter(prefix="/billing", tags=["billing"])
order_router = APIRouter(tags=["billing"])
expert_router = APIRouter(prefix="/expert", tags=["expert-workspace"])
webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_verify_limit = Depends(UserRateLimit(settings.billing_verify_rate_limit, scope="billing_verify"))
_reconcile_limit = Depends(UserRateLimit(settings.billing_reconcile_rate_limit, scope="billing_reconcile"))
_external_limit = Depends(
    UserRateLimit(settings.external_payment_create_rate_limit, scope="external_payment_create")
)
_refund_limit = Depends(UserRateLimit(settings.refund_request_rate_limit, scope="refund_request"))
# Stores and providers are not users; signatures are the protection.
_webhook_limit = Depends(RateLimit(settings.store_webhook_rate_limit, scope="payment_webhook"))


# ================================================================ helpers


async def _summary(session, user_id: uuid.UUID) -> EntitlementSummaryResponse:  # noqa: ANN001
    service = EntitlementService(session)
    rows = await service.for_user(user_id)
    items = [
        EntitlementResponse(
            id=row.id,
            entitlement_code=row.entitlement_code,
            kind=row.kind,
            source=row.source,
            status=row.status,
            active=service.policy.grants_access(row),
            environment=row.environment,
            starts_at=row.starts_at,
            expires_at=row.expires_at,
            grace_until=row.grace_until,
            auto_renewing=row.auto_renewing,
            consumed_at=row.consumed_at,
        )
        for row in rows
    ]
    plan_rows = [
        item for item in items
        if item.entitlement_code in PLAN_ENTITLEMENTS
        and item.kind == EntitlementKind.SUBSCRIPTION.value
        and item.active
    ]
    premium_rows = plan_rows
    credits = Counter(
        item.entitlement_code
        for item in items
        if item.kind == EntitlementKind.CREDIT.value and item.status == EntitlementStatus.ACTIVE.value
    )
    tier = (
        SubscriptionTier.COSMIC_PLUS
        if any(item.entitlement_code == COSMIC_PLUS for item in plan_rows)
        else SubscriptionTier.PREMIUM
        if plan_rows
        else SubscriptionTier.FREE
    )
    return EntitlementSummaryResponse(
        tier=tier.value,
        premium=bool(premium_rows),
        premium_expires_at=max((item.expires_at for item in premium_rows if item.expires_at), default=None),
        credits=dict(credits),
        capabilities=service.policy.capabilities(tier),
        items=items,
    )


async def _order_for(session, user_id: uuid.UUID, order_id: uuid.UUID) -> ServiceOrder:  # noqa: ANN001
    order = await session.scalar(
        select(ServiceOrder).where(
            ServiceOrder.id == order_id,
            ServiceOrder.user_id == user_id,
            ServiceOrder.deleted_at.is_(None),
        )
    )
    if order is None:
        raise NotFound("Order not found.")
    return order


async def _order_payment(session, order: ServiceOrder) -> OrderPaymentResponse:  # noqa: ANN001
    service = OrderPaymentService(session)
    lines = await service.lines(order.id)
    groups = await service.groups(order.id)
    blocked = any(group.status == PaymentGroupStatus.BLOCKED_REVIEW.value for group in groups)
    external = any(
        group.rail == "external_marketplace" and group.status == PaymentGroupStatus.REQUIRED.value
        for group in groups
    )
    return OrderPaymentResponse(
        order_id=order.id,
        order_status=order.status,
        payment_status=order.payment_status,
        lines=[LineItemResponse.model_validate(line, from_attributes=True) for line in lines],
        groups=[PaymentGroupResponse.model_validate(group, from_attributes=True) for group in groups],
        payable_externally=external and not blocked,
        blocked_by_policy_review=blocked,
    )


def _result(result, summary) -> PurchaseResultResponse:  # noqa: ANN001
    return PurchaseResultResponse(
        purchase_id=result.purchase.id,
        product_code=result.product.code,
        status=result.purchase.status,
        environment=result.purchase.environment,
        expires_at=result.purchase.expires_at,
        entitlements=summary,
    )


# ================================================================ billing


@router.get("/status", response_model=BillingStatusResponse, summary="Which payment rails work here")
async def status_(user: CurrentUser) -> BillingStatusResponse:
    return BillingStatusResponse(**billing_status())


@router.get(
    "/products",
    response_model=ProductListResponse,
    summary="Products sold on this platform's store",
    description="No prices: StoreKit and Play Billing return the real, localised price.",
)
async def products(
    user: CurrentUser,
    session: DbSession,
    platform: ClientPlatform = Query(),
) -> ProductListResponse:
    if platform is ClientPlatform.WEB:
        return ProductListResponse(platform=platform, items=[])
    rows = await StoreCatalogService(session).for_platform(platform)
    await session.commit()
    return ProductListResponse(
        platform=platform,
        items=[
            StoreProductResponse(
                code=row.code,
                product_type=row.product_type,
                entitlement_code=row.entitlement_code,
                store_product_id=(
                    row.apple_product_id if platform is ClientPlatform.IOS else row.google_product_id
                ),
            )
            for row in rows
        ],
    )


@router.get("/account-tokens", response_model=AccountTokensResponse)
async def account_tokens(user: CurrentUser) -> AccountTokensResponse:
    return AccountTokensResponse(
        apple_app_account_token=apple_account_token(user.id),
        google_obfuscated_account_id=google_account_id(user.id),
    )


@router.get("/features", summary="Premium feature catalogue the client mirrors")
async def features(_user: CurrentUser) -> dict:
    return feature_catalogue()


@router.get("/entitlements", response_model=EntitlementSummaryResponse)
async def entitlements(user: CurrentUser, session: DbSession) -> EntitlementSummaryResponse:
    # Read straight from the database: entitlement changes arrive from
    # webhooks at any moment, and a cached "premium" would outlive a refund.
    return await _summary(session, user.id)


@router.post("/apple/verify", response_model=PurchaseResultResponse, dependencies=[_verify_limit])
async def verify_apple(payload: AppleVerifyRequest, user: SensitiveUser, session: DbSession) -> PurchaseResultResponse:
    result = await StorePurchaseService(session).verify_apple(
        user.id,
        product_code=payload.product_code,
        signed_transaction=payload.signed_transaction,
        transaction_id=payload.transaction_id,
        provider=get_apple_provider(),
    )
    await session.commit()
    return _result(result, await _summary(session, user.id))


@router.post("/google/verify", response_model=PurchaseResultResponse, dependencies=[_verify_limit])
async def verify_google(payload: GoogleVerifyRequest, user: SensitiveUser, session: DbSession) -> PurchaseResultResponse:
    provider = get_google_provider()
    service = StorePurchaseService(session)
    result = await service.verify_google(
        user.id, product_code=payload.product_code, purchase_token=payload.purchase_token, provider=provider
    )
    # Our record first; the store's irreversible completion after.
    await session.commit()
    try:
        await service.complete_google(result, payload.purchase_token, provider)
        await session.commit()
    except AppError:
        logger.warning("store_completion_deferred", purchase_id=str(result.purchase.id))
        await session.rollback()
    return _result(result, await _summary(session, user.id))


@router.post(
    "/reconcile",
    response_model=ReconcileResponse,
    dependencies=[_reconcile_limit],
    summary="Restore: re-verify what the device owns",
)
async def reconcile(payload: ReconcileRequest, user: SensitiveUser, session: DbSession) -> ReconcileResponse:
    service = StorePurchaseService(session)
    verified, failed = 0, []
    for item in payload.apple:
        try:
            await service.verify_apple(
                user.id, product_code=item.product_code, signed_transaction=item.signed_transaction,
                transaction_id=item.transaction_id, provider=get_apple_provider(),
            )
            await session.commit()
            verified += 1
        except AppError as exc:
            await session.rollback()
            failed.append({"store": "apple", "product_code": item.product_code, "code": exc.code})
    google = get_google_provider()
    for item in payload.google:
        try:
            result = await service.verify_google(
                user.id, product_code=item.product_code, purchase_token=item.purchase_token, provider=google
            )
            await session.commit()
            verified += 1
            try:
                await service.complete_google(result, item.purchase_token, google)
                await session.commit()
            except AppError:
                await session.rollback()
        except AppError as exc:
            await session.rollback()
            failed.append({"store": "google", "product_code": item.product_code, "code": exc.code})
    return ReconcileResponse(verified=verified, failed=failed, entitlements=await _summary(session, user.id))


@router.post("/credits/consume", response_model=ConsumeCreditResponse)
async def consume_credit(payload: ConsumeCreditRequest, user: CurrentUser, session: DbSession) -> ConsumeCreditResponse:
    if payload.entitlement_code in report_entitlement_codes():
        # Report credits are spent by `POST /ai/reports` itself, atomically
        # with the job that delivers the report. Spending one here would pay
        # for nothing - and an older client that creates a report and then
        # calls this would pay twice.
        raise AppError(
            "Report credits are used by POST /ai/reports with a consumer_ref.",
            code="credit_reserved_for_reports",
            status_code=409,
        )
    if payload.consumer_ref.startswith(RESERVATION_PREFIX):
        raise AppError(
            "That consumer_ref prefix is reserved.",
            code="consumer_ref_reserved",
            status_code=422,
        )
    row = await EntitlementService(session).consume(user.id, payload.entitlement_code, payload.consumer_ref)
    await session.commit()
    return ConsumeCreditResponse(
        entitlement_id=row.id,
        entitlement_code=row.entitlement_code,
        consumer_ref=row.consumed_ref or payload.consumer_ref,
        consumed_at=row.consumed_at,
    )


# ================================================================== orders


@order_router.get("/orders/{order_id}/payment", response_model=OrderPaymentResponse)
async def order_payment(order_id: uuid.UUID, user: CurrentUser, session: DbSession) -> OrderPaymentResponse:
    return await _order_payment(session, await _order_for(session, user.id, order_id))


@order_router.post(
    "/orders/{order_id}/payment",
    response_model=OrderPaymentStartResponse,
    dependencies=[_external_limit],
    summary="Pay for an order",
    description=(
        "`external`: live 1:1 sessions only, through the external provider. "
        "`store_credit`: a digital line, with a verified store credit. There "
        "is no way to tell this API an order is paid."
    ),
)
async def pay_order(
    order_id: uuid.UUID, payload: OrderPaymentRequest, user: CurrentUser, session: DbSession
) -> OrderPaymentStartResponse:
    order = await _order_for(session, user.id, order_id)
    service = OrderPaymentService(session)
    if payload.method == "store_credit":
        await service.pay_with_credit(user.id, order)
        await session.commit()
        return OrderPaymentStartResponse(status="satisfied", order=await _order_payment(session, order))

    intent, checkout = await service.start_external_checkout(
        user.id, order, idempotency_key=payload.idempotency_key, provider=get_external_provider()
    )
    await session.commit()
    return OrderPaymentStartResponse(
        payment_intent_id=intent.id,
        status=intent.status,
        client_handoff=checkout.client_handoff,
        expires_at=checkout.expires_at,
        order=await _order_payment(session, order),
    )


@order_router.post(
    "/orders/{order_id}/refund-requests",
    response_model=RefundRequestResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_refund_limit],
)
async def request_refund(
    order_id: uuid.UUID, payload: RefundRequestCreate, user: CurrentUser, session: DbSession
) -> RefundRequestResponse:
    order = await _order_for(session, user.id, order_id)
    request = await RefundService(session).request(
        user_id=user.id,
        order=order,
        amount_minor=payload.amount_minor,
        reason=payload.reason,
        actor=RefundActor.USER,
        idempotency_key=payload.idempotency_key,
    )
    await session.commit()
    return RefundRequestResponse.model_validate(request, from_attributes=True)


@order_router.get("/orders/{order_id}/refund-requests", response_model=list[RefundRequestResponse])
async def list_refunds(order_id: uuid.UUID, user: CurrentUser, session: DbSession) -> list[RefundRequestResponse]:
    order = await _order_for(session, user.id, order_id)
    rows = await session.scalars(
        select(RefundRequest).where(RefundRequest.order_id == order.id).order_by(RefundRequest.created_at)
    )
    return [RefundRequestResponse.model_validate(row, from_attributes=True) for row in rows]


# ================================================================== expert


@expert_router.get("/earnings", response_model=ExpertEarningsResponse)
async def earnings(user: CurrentUser, session: DbSession) -> ExpertEarningsResponse:
    from app.services.marketplace.experts import ExpertProfileService

    expert = await ExpertProfileService(session).get_own(user)
    balances = await SettlementService(session).balances(expert.id)
    await session.commit()
    return ExpertEarningsResponse(
        settlement_hold_days=settings.expert_settlement_hold_days,
        balances=[
            ExpertBalanceResponse(
                currency=currency,
                pending_minor=values["pending"],
                available_minor=values["available"],
                paid_minor=values["paid"],
            )
            for currency, values in sorted(balances.items())
        ],
    )


@expert_router.get("/payouts", response_model=list[PayoutResponse])
async def payouts(user: CurrentUser, session: DbSession) -> list[PayoutResponse]:
    from app.services.marketplace.experts import ExpertProfileService

    expert = await ExpertProfileService(session).get_own(user)
    rows = await SettlementService(session).payouts(expert.id)
    return [PayoutResponse.model_validate(row, from_attributes=True) for row in rows]


# ================================================================ webhooks


@webhook_router.post("/apple/app-store", dependencies=[_webhook_limit], summary="App Store Server Notifications V2")
async def apple_notifications(request: Request, session: DbSession) -> dict[str, str]:
    provider = get_apple_provider()
    if not provider.configured:
        raise StoreNotConfigured()
    body = await request.body()
    try:
        signed_payload = json.loads(body)["signedPayload"]
        notification = provider.verify_notification(signed_payload)
    except (StoreVerificationFailed, StoreEnvironmentRejected, KeyError, ValueError, TypeError) as exc:
        # The signed payload is never logged.
        logger.warning("apple_notification_rejected", error_type=type(exc).__name__, body_bytes=len(body))
        raise InvalidProviderNotification() from exc
    outcome = await StoreNotificationService(session).apply_apple(notification, body)
    await session.commit()
    return {"status": "ok", "outcome": outcome}


@webhook_router.post("/google/play", dependencies=[_webhook_limit], summary="Google Play RTDN (Pub/Sub push)")
async def google_notifications(request: Request, session: DbSession) -> dict[str, str]:
    provider = get_google_provider()
    if not provider.configured:
        raise StoreNotConfigured()
    try:
        await provider.verify_push(request.headers.get("authorization"))
    except InvalidProviderNotification:
        logger.warning("google_rtdn_rejected")
        raise
    body = await request.body()
    service = StoreNotificationService(session)
    outcome, result, token = await service.apply_google(body, provider)
    await session.commit()
    if result is not None and token:
        try:
            await service.purchases.complete_google(result, token, provider)
            await session.commit()
        except AppError:
            await session.rollback()
    return {"status": "ok", "outcome": outcome}


@webhook_router.post("/payments/external", dependencies=[_webhook_limit], summary="External payment provider events")
async def external_payment_events(request: Request, session: DbSession) -> dict[str, str]:
    provider = get_external_provider()
    body = await request.body()
    event = provider.parse_webhook(body, {k.lower(): v for k, v in request.headers.items()})

    record = PaymentProviderEvent(
        provider=provider.name,
        external_event_id=event.event_id[:128],
        event_type=event.event_type[:60],
        transaction_ref=event.external_reference[:128],
        payload_sha256=hashlib.sha256(body).hexdigest(),
        received_at=datetime.now(UTC),
        status="received",
    )
    try:
        async with session.begin_nested():
            session.add(record)
            await session.flush()
    except IntegrityError:
        return {"status": "ok", "outcome": "duplicate"}
    outcome = await OrderPaymentService(session).apply_external_event(event, provider.name)
    record.outcome = outcome
    record.status = "processed"
    record.processed_at = datetime.now(UTC)
    await session.commit()
    return {"status": "ok", "outcome": outcome}

