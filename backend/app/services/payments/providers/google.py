"""Google Play: server-side purchase verification, acknowledgement and RTDN.

Checked against Google's current reference on 2026-09-24:

* Subscriptions: `purchases.subscriptionsv2.get`
  (`GET /applications/{package}/purchases/subscriptionsv2/tokens/{token}`).
  The v1 subscriptions `get` is not used.
* One-time products: `purchases.productsv2.getproductpurchasev2`
  (`GET /applications/{package}/purchases/productsv2/tokens/{token}`).
* Acknowledge: `purchases.subscriptions.acknowledge` and
  `purchases.products.acknowledge`; consumables: `purchases.products.consume`.
  Google refunds a purchase not acknowledged within three days, and says to
  acknowledge only a PURCHASED purchase, never a PENDING one.
* RTDN is a Pub/Sub push. Google's reference says outright that a
  notification only says *that* a purchase changed - the Developer API must be
  called for its state. So RTDN here never changes state by itself: it names a
  token, and the token is fetched.
* A Pub/Sub push subscription with authentication signs an OIDC JWT sent as
  `Authorization: Bearer`. It is verified with `google.oauth2.id_token`
  (signature, `aud`, `exp`), then `iss`, `email` and `email_verified` are
  checked against the configured push service account.

Nothing here decides entitlement; it returns a `VerifiedPurchase`.
"""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import UTC, datetime
from urllib.parse import quote
from typing import Any, Protocol

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.payments import PurchaseStatus, StoreEnvironment, StoreProvider
from app.services.payments.providers.base import (
    GoogleNotification,
    InvalidProviderNotification,
    StoreNotConfigured,
    StoreUnavailable,
    StoreVerificationFailed,
    VerifiedPurchase,
    hash_token,
)

logger = get_logger(__name__)

API_BASE = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
SCOPE = "https://www.googleapis.com/auth/androidpublisher"
GOOGLE_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})


class GooglePlayProvider(Protocol):
    name: str

    @property
    def configured(self) -> bool: ...

    async def get_subscription(self, token: str) -> VerifiedPurchase: ...

    async def get_product(self, token: str) -> VerifiedPurchase: ...

    async def acknowledge_subscription(self, product_id: str, token: str) -> None: ...

    async def acknowledge_product(self, product_id: str, token: str) -> None: ...

    async def consume_product(self, product_id: str, token: str) -> None: ...

    async def verify_push(self, authorization: str | None) -> None: ...


# ========================================================== normalisation


def _rfc3339(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


_SUBSCRIPTION_STATES = {
    "SUBSCRIPTION_STATE_ACTIVE": PurchaseStatus.ACTIVE,
    "SUBSCRIPTION_STATE_IN_GRACE_PERIOD": PurchaseStatus.GRACE_PERIOD,
    "SUBSCRIPTION_STATE_ON_HOLD": PurchaseStatus.ON_HOLD,
    "SUBSCRIPTION_STATE_PAUSED": PurchaseStatus.PAUSED,
    "SUBSCRIPTION_STATE_EXPIRED": PurchaseStatus.EXPIRED,
    "SUBSCRIPTION_STATE_PENDING": PurchaseStatus.PENDING,
    "SUBSCRIPTION_STATE_PENDING_PURCHASE_CANCELED": PurchaseStatus.CANCELLED,
    # Unknown means "do not entitle": fail closed.
    "SUBSCRIPTION_STATE_UNSPECIFIED": PurchaseStatus.PENDING,
}


def normalise_subscription(token: str, data: dict[str, Any]) -> VerifiedPurchase:
    """A SubscriptionPurchaseV2 -> VerifiedPurchase.

    CANCELED is split on `expiryTime`: a cancelled subscription is paid up to
    its expiry, so it is CANCELLED_PENDING_EXPIRY until then and EXPIRED after.
    """
    now = datetime.now(UTC)
    items = data.get("lineItems") or [{}]
    item = items[0]
    expires = _rfc3339(item.get("expiryTime"))
    state = data.get("subscriptionState", "SUBSCRIPTION_STATE_UNSPECIFIED")
    if state == "SUBSCRIPTION_STATE_CANCELED":
        status = (
            PurchaseStatus.CANCELLED_PENDING_EXPIRY
            if expires is not None and expires > now
            else PurchaseStatus.EXPIRED
        )
    else:
        status = _SUBSCRIPTION_STATES.get(state, PurchaseStatus.PENDING)

    plan = item.get("autoRenewingPlan") or {}
    linked = data.get("linkedPurchaseToken")
    account = (data.get("externalAccountIdentifiers") or {}).get(
        "obfuscatedExternalAccountId"
    )
    return VerifiedPurchase(
        provider=StoreProvider.GOOGLE,
        purchase_key=hash_token(token),
        purchase_token_hash=hash_token(token),
        store_product_ref=item.get("productId", ""),
        product_kind="subscription",
        status=status,
        environment=(
            StoreEnvironment.SANDBOX if data.get("testPurchase") is not None else StoreEnvironment.PRODUCTION
        ),
        external_transaction_id=data.get("latestOrderId"),
        purchased_at=_rfc3339(data.get("startTime")),
        expires_at=expires,
        auto_renewing=plan.get("autoRenewEnabled") if plan else None,
        account_hint=account,
        acknowledged=data.get("acknowledgementState") == "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED",
        replaces_purchase_token_hash=hash_token(linked) if linked else None,
    )


_PRODUCT_STATES = {
    "PURCHASED": PurchaseStatus.ACTIVE,
    "PENDING": PurchaseStatus.PENDING,
    "CANCELLED": PurchaseStatus.CANCELLED,
}


def normalise_product(token: str, data: dict[str, Any]) -> VerifiedPurchase:
    """A ProductPurchaseV2 -> VerifiedPurchase. PENDING never entitles."""
    line = data.get("productLineItem") or {}
    if isinstance(line, list):
        line = line[0] if line else {}
    offer = line.get("productOfferDetails") or {}
    state = (data.get("purchaseStateContext") or {}).get("purchaseState", "PENDING")
    return VerifiedPurchase(
        provider=StoreProvider.GOOGLE,
        purchase_key=hash_token(token),
        purchase_token_hash=hash_token(token),
        store_product_ref=line.get("productId", ""),
        product_kind="one_time",
        status=_PRODUCT_STATES.get(state, PurchaseStatus.PENDING),
        environment=(
            StoreEnvironment.SANDBOX
            if data.get("testPurchaseContext") is not None
            else StoreEnvironment.PRODUCTION
        ),
        external_transaction_id=data.get("orderId"),
        quantity=int(offer.get("quantity") or 1),
        purchased_at=_rfc3339(data.get("purchaseCompletionTime")),
        account_hint=data.get("obfuscatedExternalAccountId"),
        acknowledged=data.get("acknowledgementState") == "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED",
        store_consumed=offer.get("consumptionState") == "CONSUMPTION_STATE_CONSUMED",
    )


def validate_push_claims(claims: dict[str, Any], *, audience: str, service_account: str) -> None:
    """Pub/Sub push OIDC claims. The signature and `aud` are checked by the caller."""
    if claims.get("aud") != audience:
        raise InvalidProviderNotification()
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise InvalidProviderNotification()
    if claims.get("email") != service_account or claims.get("email_verified") is not True:
        raise InvalidProviderNotification()


def parse_push_body(body: bytes, *, expected_package: str | None) -> GoogleNotification:
    """A Pub/Sub push envelope -> the DeveloperNotification it carries.

    Parsed only after the push was authenticated. Even then it is a pointer to
    a purchase, not a purchase.
    """
    try:
        envelope = json.loads(body)
        message = envelope["message"]
        message_id = str(message.get("messageId") or message.get("message_id"))
        notification = json.loads(base64.b64decode(message["data"]))
    except Exception as exc:  # noqa: BLE001 - malformed is the same answer
        raise InvalidProviderNotification("Malformed notification.") from exc

    package = notification.get("packageName", "")
    if expected_package and package != expected_package:
        raise InvalidProviderNotification("Notification for another package.")

    event_time = None
    if notification.get("eventTimeMillis"):
        event_time = datetime.fromtimestamp(int(notification["eventTimeMillis"]) / 1000, tz=UTC)

    if "subscriptionNotification" in notification:
        inner = notification["subscriptionNotification"]
        return GoogleNotification(
            message_id=message_id,
            package_name=package,
            kind="subscription",
            notification_type=inner.get("notificationType"),
            purchase_token=inner.get("purchaseToken"),
            product_id=inner.get("subscriptionId"),
            event_time=event_time,
        )
    if "oneTimeProductNotification" in notification:
        inner = notification["oneTimeProductNotification"]
        return GoogleNotification(
            message_id=message_id,
            package_name=package,
            kind="one_time",
            notification_type=inner.get("notificationType"),
            purchase_token=inner.get("purchaseToken"),
            product_id=inner.get("sku"),
            event_time=event_time,
        )
    if "voidedPurchaseNotification" in notification:
        inner = notification["voidedPurchaseNotification"]
        return GoogleNotification(
            message_id=message_id,
            package_name=package,
            kind="voided",
            notification_type=inner.get("productType"),
            purchase_token=inner.get("purchaseToken"),
            voided_refund=inner.get("refundType") in (1, 2),
            event_time=event_time,
        )
    return GoogleNotification(
        message_id=message_id,
        package_name=package,
        kind="test" if "testNotification" in notification else "other",
        notification_type=None,
        event_time=event_time,
    )


# ============================================================== real provider


class PlayDeveloperApiProvider:
    """The real Google Play Developer API. Unverified live: no credentials yet."""

    name = "google"

    def __init__(self) -> None:
        self._credentials = None
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return settings.google_configured

    async def _token(self) -> str:
        if not self.configured:
            raise StoreNotConfigured()
        async with self._lock:
            if self._credentials is None:
                from google.oauth2 import service_account

                if settings.google_play_service_account_json:
                    info = json.loads(settings.google_play_service_account_json)
                    self._credentials = service_account.Credentials.from_service_account_info(
                        info, scopes=[SCOPE]
                    )
                else:
                    self._credentials = service_account.Credentials.from_service_account_file(
                        str(settings.google_play_service_account_path), scopes=[SCOPE]
                    )
            if not self._credentials.valid:
                from google.auth.transport.requests import Request

                try:
                    await asyncio.to_thread(self._credentials.refresh, Request())
                except Exception as exc:  # noqa: BLE001
                    logger.warning("google_play_auth_failed", error_type=type(exc).__name__)
                    raise StoreUnavailable() from exc
            return self._credentials.token

    async def _request(self, method: str, path: str) -> dict[str, Any]:
        url = f"{API_BASE}/{settings.google_play_package_name}/{path}"
        headers = {"Authorization": f"Bearer {await self._token()}"}
        try:
            async with httpx.AsyncClient(
                timeout=settings.google_play_request_timeout_seconds
            ) as client:
                response = await client.request(method, url, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("google_play_request_failed", error_type=type(exc).__name__)
            raise StoreUnavailable() from exc
        if response.status_code in (400, 404, 410):
            # An unknown or invalid token, or another package's.
            raise StoreVerificationFailed()
        if response.status_code >= 300:
            logger.warning("google_play_http_error", http_status=response.status_code)
            raise StoreUnavailable()
        return response.json() if response.content else {}

    async def get_subscription(self, token: str) -> VerifiedPurchase:
        data = await self._request("GET", f"purchases/subscriptionsv2/tokens/{quote(token, safe='')}")
        return normalise_subscription(token, data)

    async def get_product(self, token: str) -> VerifiedPurchase:
        data = await self._request("GET", f"purchases/productsv2/tokens/{quote(token, safe='')}")
        return normalise_product(token, data)

    async def acknowledge_subscription(self, product_id: str, token: str) -> None:
        await self._request(
            "POST", f"purchases/subscriptions/{quote(product_id, safe='')}/tokens/{quote(token, safe='')}:acknowledge"
        )

    async def acknowledge_product(self, product_id: str, token: str) -> None:
        await self._request("POST", f"purchases/products/{quote(product_id, safe='')}/tokens/{quote(token, safe='')}:acknowledge")

    async def consume_product(self, product_id: str, token: str) -> None:
        await self._request("POST", f"purchases/products/{quote(product_id, safe='')}/tokens/{quote(token, safe='')}:consume")

    async def verify_push(self, authorization: str | None) -> None:
        if not settings.google_rtdn_configured:
            raise StoreNotConfigured("Real-time developer notifications are not configured.")
        if not authorization or not authorization.lower().startswith("bearer "):
            raise InvalidProviderNotification()
        token = authorization[7:].strip()

        from google.auth.transport.requests import Request
        from google.oauth2 import id_token

        try:
            claims = await asyncio.to_thread(
                id_token.verify_oauth2_token,
                token,
                Request(),
                settings.google_pubsub_push_audience,
            )
        except Exception as exc:  # noqa: BLE001 - every failure is the same answer
            raise InvalidProviderNotification() from exc
        validate_push_claims(
            claims,
            audience=settings.google_pubsub_push_audience or "",
            service_account=settings.google_pubsub_push_service_account or "",
        )
