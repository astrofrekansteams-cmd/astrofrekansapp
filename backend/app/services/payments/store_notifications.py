"""App Store Server Notifications V2 and Google Play RTDN.

Both arrive signed or authenticated; both are verified before anything is
read; both are recorded by event id first, under a unique constraint, so a
replay changes nothing. Neither stores its payload - only a hash.

The difference that matters:

* **Apple V2** carries Apple-signed transaction and renewal info. After
  verifying the outer JWS and each inner one, the transaction *is* Apple's
  statement of state and is applied.
* **Google RTDN** only says a purchase changed. Its token is fetched from the
  Developer API, and the API's answer is applied. The notification's own
  fields are never used as state - except a voided-purchase notification's
  statement that a refund happened, which arrives through the authenticated
  channel and is Google's word; the purchase is still fetched.

A notification for a purchase no client has verified yet is attached if the
purchase names our account (Apple's `appAccountToken`); otherwise it is
recorded as `unassociated` and the client's next verification or restore
attaches it.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.payments import PaymentProviderEvent, StoreProduct, StorePurchase
from app.db.models.user import User
from app.domain.payments import ProviderEventStatus, PurchaseStatus, StoreProductType
from app.services.payments.providers.base import (
    AppleNotification,
    GoogleNotification,
    ProductMismatch,
    PurchaseOwnedByAnotherAccount,
    StoreVerificationFailed,
    UnknownStoreProduct,
    hash_token,
)
from app.services.payments.providers.google import parse_push_body
from app.services.payments.purchases import ApplyResult, StorePurchaseService

logger = get_logger(__name__)


class StoreNotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.purchases = StorePurchaseService(session)

    async def _record(
        self,
        *,
        provider: str,
        event_id: str,
        event_type: str,
        body: bytes,
        transaction_ref: str | None,
        environment: str | None,
    ) -> PaymentProviderEvent | None:
        """Claim the event id. None means we have seen it before."""
        event = PaymentProviderEvent(
            provider=provider,
            external_event_id=event_id[:128],
            event_type=event_type[:60],
            transaction_ref=(transaction_ref or "")[:128] or None,
            payload_sha256=hashlib.sha256(body).hexdigest(),
            environment=environment,
            received_at=datetime.now(UTC),
            status=ProviderEventStatus.RECEIVED.value,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(event)
                await self.session.flush()
        except IntegrityError:
            logger.info("store_notification_duplicate", provider=provider, event_type=event_type)
            return None
        return event

    @staticmethod
    def _finish(event: PaymentProviderEvent, outcome: str, status: ProviderEventStatus) -> None:
        event.outcome = outcome
        event.status = status.value
        event.processed_at = datetime.now(UTC)

    async def _owner_for(self, provider: str, purchase_key: str, account_hint: str | None) -> uuid.UUID | None:
        existing = await self.session.scalar(
            select(StorePurchase.user_id).where(
                StorePurchase.provider == provider, StorePurchase.purchase_key == purchase_key
            )
        )
        if existing is not None:
            return existing
        if provider == "apple" and account_hint:
            try:
                candidate = uuid.UUID(account_hint)
            except ValueError:
                return None
            user = await self.session.scalar(
                select(User.id).where(User.id == candidate, User.deleted_at.is_(None))
            )
            return user
        return None

    # ================================================================ Apple

    async def apply_apple(self, notification: AppleNotification, body: bytes) -> str:
        purchase = notification.purchase
        event = await self._record(
            provider="apple",
            event_id=notification.notification_uuid,
            event_type=f"{notification.notification_type}:{notification.subtype or ''}",
            body=body,
            transaction_ref=purchase.original_transaction_id if purchase else None,
            environment=notification.environment.value,
        )
        if event is None:
            return "duplicate"
        if purchase is None:
            self._finish(event, "no_transaction", ProviderEventStatus.IGNORED)
            return "no_transaction"

        try:
            self.purchases.check_environment(purchase)
        except Exception:  # noqa: BLE001 - StoreEnvironmentRejected
            self._finish(event, "environment_rejected", ProviderEventStatus.IGNORED)
            return "environment_rejected"

        owner = await self._owner_for("apple", purchase.purchase_key, purchase.account_hint)
        if owner is None:
            self._finish(event, "unassociated", ProviderEventStatus.IGNORED)
            return "unassociated"
        try:
            product = await self.purchases.product_for(purchase, None)
            await self.purchases.apply(
                owner,
                purchase,
                product,
                allow_unrevoke=notification.notification_type == "REFUND_REVERSED",
            )
        except (UnknownStoreProduct, ProductMismatch):
            self._finish(event, "unknown_product", ProviderEventStatus.IGNORED)
            return "unknown_product"
        except PurchaseOwnedByAnotherAccount:
            self._finish(event, "owner_conflict", ProviderEventStatus.FAILED)
            return "owner_conflict"
        self._finish(event, "applied", ProviderEventStatus.PROCESSED)
        return "applied"

    # =============================================================== Google

    async def apply_google(self, body: bytes, provider) -> tuple[str, ApplyResult | None, str | None]:  # noqa: ANN001
        """Returns (outcome, apply result, token) - the caller acknowledges after commit."""
        notification: GoogleNotification = parse_push_body(
            body, expected_package=settings.google_play_package_name
        )
        token = notification.purchase_token
        event = await self._record(
            provider="google",
            event_id=notification.message_id,
            event_type=f"{notification.kind}:{notification.notification_type}",
            body=body,
            transaction_ref=hash_token(token) if token else None,
            environment=None,
        )
        if event is None:
            return "duplicate", None, None
        if not token or notification.kind in ("test", "other"):
            self._finish(event, "noted", ProviderEventStatus.IGNORED)
            return "noted", None, None

        key = hash_token(token)
        existing = await self.session.scalar(
            select(StorePurchase).where(
                StorePurchase.provider == "google", StorePurchase.purchase_key == key
            )
        )
        if existing is None:
            # We cannot tell whose it is without the client: the obfuscated
            # account id is a one-way hash. The next verify or restore
            # attaches it.
            self._finish(event, "unassociated", ProviderEventStatus.IGNORED)
            return "unassociated", None, None

        product = await self.session.get(StoreProduct, existing.store_product_id)
        # The notification is a pointer. The state comes from the API.
        try:
            if StoreProductType(product.product_type) is StoreProductType.SUBSCRIPTION:
                verified = await provider.get_subscription(token)
            else:
                verified = await provider.get_product(token)
                verified.product_kind = product.product_type
        except StoreVerificationFailed:
            self._finish(event, "fetch_failed", ProviderEventStatus.FAILED)
            return "fetch_failed", None, None

        if notification.kind == "voided":
            verified.status = PurchaseStatus.REVOKED
            verified.refunded = notification.voided_refund
            verified.revoked_at = notification.event_time or datetime.now(UTC)
            verified.revocation_reason = "voided"

        result = await self.purchases.apply(existing.user_id, verified, product)
        self._finish(event, "applied", ProviderEventStatus.PROCESSED)
        return "applied", result, token
