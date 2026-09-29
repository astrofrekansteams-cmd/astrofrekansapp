"""Store purchases: verify, attach to one account, derive, account for.

Every route into this file - a client verifying a purchase, a restore, an App
Store Server Notification, a Google RTDN - ends in `apply()`. It is the one
place a verified purchase changes state, and it is safe to run twice, or twice
at the same time:

* the purchase row is unique per `(provider, purchase_key)` and locked
  (`FOR UPDATE`) while it is changed;
* entitlements are unique per `(purchase, unit)`;
* charges are unique per `(provider, store transaction id, type)`;
* ledger journals are unique per key.

So a client verification racing the store's own notification for the same
transaction produces one purchase, one entitlement change and one ledger
effect - proven on Postgres by scripts/payment_concurrency_check.py.

What is trusted: only what the store signed (Apple) or returned (Google). The
client's request names a product code and hands over a transaction reference;
both are checked against the store's answer and neither is believed.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.payments import PaymentTransaction, StoreProduct, StorePurchase
from app.domain.chat import PushEvent
from app.domain.payments import (
    LedgerAccount,
    PaymentRail,
    PurchaseStatus,
    StoreEnvironment,
    StoreProductType,
    StoreProvider,
    TransactionType,
)
from app.services.notifications.outbox import OutboxService
from app.services.payments.catalog import StoreCatalogService
from app.services.payments.entitlements import ENTITLING, EntitlementService
from app.services.payments.ledger import CREDIT, DEBIT, LedgerService, Posting
from app.services.payments.providers.base import (
    ProductMismatch,
    PurchaseAccountMismatch,
    PurchaseOwnedByAnotherAccount,
    StoreEnvironmentRejected,
    StoreNotConfigured,
    StoreVerificationFailed,
    UnknownStoreProduct,
    VerifiedPurchase,
)

logger = get_logger(__name__)

RAIL = {StoreProvider.APPLE: PaymentRail.APPLE_STORE, StoreProvider.GOOGLE: PaymentRail.GOOGLE_PLAY}


def apple_account_token(user_id: uuid.UUID) -> str:
    """What the app passes as StoreKit's `appAccountToken`.

    Apple requires a UUID and signs it into every transaction, so the account a
    purchase was made for is part of what Apple vouches for. The user id is a
    random UUID with no personal data in it.
    """
    return str(user_id)


def google_account_id(user_id: uuid.UUID) -> str:
    """What the app passes as `obfuscatedAccountId` to Play Billing.

    Google asks for a one-way hash of the account id, not the id. Keyed with a
    server secret so it cannot be computed from a user id by anybody else.
    """
    key = hashlib.sha256(f"play-account:{settings.jwt_secret}".encode()).digest()
    return hmac.new(key, str(user_id).encode(), hashlib.sha256).hexdigest()[:64]


@dataclass(slots=True)
class ApplyResult:
    purchase: StorePurchase
    product: StoreProduct
    created: bool
    became_active: bool = False
    # Google work that must happen after the commit: acknowledge / consume.
    completion: str | None = None
    notes: list[str] = field(default_factory=list)


class StorePurchaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.catalog = StoreCatalogService(session)
        self.entitlements = EntitlementService(session)
        self.ledger = LedgerService(session)
        self.outbox = OutboxService(session)

    @property
    def _locks(self) -> bool:
        bind = self.session.bind
        return bind is not None and bind.dialect.name != "sqlite"

    # ============================================================ checks

    def check_environment(self, purchase: VerifiedPurchase) -> None:
        """A sandbox or test purchase is never a production entitlement by accident."""
        if purchase.environment is StoreEnvironment.PRODUCTION:
            return
        if not settings.is_production:
            return
        allowed = (
            settings.apple_accept_sandbox_in_production
            if purchase.provider is StoreProvider.APPLE
            else settings.google_accept_test_purchases_in_production
        )
        if not allowed:
            raise StoreEnvironmentRejected()

    async def product_for(self, purchase: VerifiedPurchase, requested_code: str | None) -> StoreProduct:
        """Map the store's product id to ours, and compare with the request.

        The client says `premium_yearly`; the store says what was actually
        bought. A mismatch is refused - a cheap monthly purchase must not
        unlock whatever the request claims.
        """
        product = await self.catalog.by_store_ref(purchase.provider.value, purchase.store_product_ref)
        if product is None:
            raise UnknownStoreProduct(details={"reason": "store_product_not_in_catalogue"})
        if requested_code is not None and product.code != requested_code:
            raise ProductMismatch(details={"requested": requested_code})
        kind = purchase.product_kind
        declared = StoreProductType(product.product_type)
        if kind == "subscription" and declared is not StoreProductType.SUBSCRIPTION:
            raise ProductMismatch(details={"reason": "product_type"})
        if kind in ("consumable", "non_consumable") and declared.value != kind:
            raise ProductMismatch(details={"reason": "product_type"})
        return product

    def check_account(self, user_id: uuid.UUID, purchase: VerifiedPurchase) -> None:
        if not purchase.account_hint:
            return
        expected = (
            apple_account_token(user_id)
            if purchase.provider is StoreProvider.APPLE
            else google_account_id(user_id)
        )
        if purchase.account_hint.lower() != expected.lower():
            raise PurchaseAccountMismatch()

    # ============================================================= apply

    async def _lock_or_create(
        self, user_id: uuid.UUID, verified: VerifiedPurchase, product: StoreProduct
    ) -> tuple[StorePurchase, bool]:
        key = (verified.provider.value, verified.purchase_key)
        statement = select(StorePurchase).where(
            StorePurchase.provider == key[0], StorePurchase.purchase_key == key[1]
        )
        if self._locks:
            statement = statement.with_for_update()
        row = await self.session.scalar(statement)
        if row is not None:
            return row, False
        try:
            async with self.session.begin_nested():
                row = StorePurchase(
                    user_id=user_id,
                    provider=verified.provider.value,
                    store_product_id=product.id,
                    store_product_ref=verified.store_product_ref,
                    purchase_key=verified.purchase_key,
                    status=PurchaseStatus.PENDING.value,
                    environment=verified.environment.value,
                    quantity=verified.quantity,
                )
                self.session.add(row)
                await self.session.flush()
            return row, True
        except IntegrityError:
            # The other side of a race - a notification and a client
            # verification for the same purchase. Take the winner's row.
            row = await self.session.scalar(statement)
            if row is None:  # pragma: no cover - the constraint says otherwise
                raise
            return row, False

    async def apply(
        self,
        user_id: uuid.UUID,
        verified: VerifiedPurchase,
        product: StoreProduct,
        *,
        allow_unrevoke: bool = False,
    ) -> ApplyResult:
        """Make our records match a verified purchase. Idempotent, race-safe."""
        now = datetime.now(UTC)
        purchase, created = await self._lock_or_create(user_id, verified, product)

        if purchase.user_id != user_id:
            # Never moved between accounts. Whoever learns a transaction id or
            # a purchase token does not get the entitlement behind it.
            logger.warning(
                "store_purchase_owner_conflict",
                provider=verified.provider.value,
                purchase_id=str(purchase.id),
            )
            raise PurchaseOwnedByAnotherAccount()
        if purchase.store_product_id != product.id:
            raise ProductMismatch(details={"reason": "purchase_already_recorded_for_other_product"})

        previous = PurchaseStatus(purchase.status)
        target = verified.status
        if previous is PurchaseStatus.REVOKED and target is not PurchaseStatus.REVOKED and not allow_unrevoke:
            # A refund is not undone by a stale client verification; only the
            # store saying so (REFUND_REVERSED) may do that.
            target = PurchaseStatus.REVOKED

        purchase.status = target.value
        purchase.environment = verified.environment.value
        purchase.external_transaction_id = verified.external_transaction_id or purchase.external_transaction_id
        purchase.original_transaction_id = verified.original_transaction_id or purchase.original_transaction_id
        purchase.purchase_token_hash = verified.purchase_token_hash or purchase.purchase_token_hash
        purchase.quantity = max(verified.quantity, 1)
        purchase.purchased_at = purchase.purchased_at or verified.purchased_at
        purchase.expires_at = verified.expires_at
        purchase.grace_until = verified.grace_until
        purchase.auto_renewing = verified.auto_renewing
        purchase.last_verified_at = now
        if verified.acknowledged and purchase.acknowledged_at is None:
            purchase.acknowledged_at = now
        if verified.store_consumed and purchase.store_consumed_at is None:
            purchase.store_consumed_at = now
        if target is PurchaseStatus.REVOKED and purchase.revoked_at is None:
            purchase.revoked_at = verified.revoked_at or now
            purchase.revocation_reason = verified.revocation_reason
        await self.session.flush()

        result = ApplyResult(
            purchase=purchase,
            product=product,
            created=created,
            became_active=target in ENTITLING and previous not in ENTITLING,
        )

        await self.entitlements.sync_from_purchase(purchase, product)
        if verified.replaces_purchase_token_hash:
            await self._retire_replaced(user_id, verified.replaces_purchase_token_hash)

        if target in ENTITLING and verified.external_transaction_id:
            await self._record_charge(purchase, verified, renewal=not created and not result.became_active)
        if target is PurchaseStatus.REVOKED and previous is not PurchaseStatus.REVOKED:
            await self._record_store_refund(purchase, verified)
        if (
            target is PurchaseStatus.EXPIRED
            and previous is not PurchaseStatus.EXPIRED
            and StoreProductType(product.product_type) is StoreProductType.SUBSCRIPTION
        ):
            await self._push(PushEvent.SUBSCRIPTION_EXPIRED, purchase, f"expired:{purchase.id}:{purchase.expires_at}")

        await self.entitlements.refresh_projection(user_id)

        if (
            verified.provider is StoreProvider.GOOGLE
            and target in ENTITLING
            and (
                not verified.acknowledged
                or (
                    StoreProductType(product.product_type) is StoreProductType.CONSUMABLE
                    and not verified.store_consumed
                )
            )
        ):
            result.completion = (
                "consume"
                if StoreProductType(product.product_type) is StoreProductType.CONSUMABLE
                else "acknowledge"
            )

        logger.info(
            "store_purchase_applied",
            provider=verified.provider.value,
            purchase_id=str(purchase.id),
            user_id=str(user_id),
            product_code=product.code,
            status=target.value,
            previous_status=previous.value,
            environment=verified.environment.value,
            created=created,
        )
        return result

    async def _retire_replaced(self, user_id: uuid.UUID, token_hash: str) -> None:
        """A Google upgrade/downgrade replaces the old purchase; it stops entitling."""
        old = await self.session.scalar(
            select(StorePurchase).where(
                StorePurchase.provider == StoreProvider.GOOGLE.value,
                StorePurchase.purchase_key == token_hash,
                StorePurchase.user_id == user_id,
            )
        )
        if old is None or old.status == PurchaseStatus.EXPIRED.value:
            return
        old.status = PurchaseStatus.EXPIRED.value
        await self.session.flush()
        product = await self.session.get(StoreProduct, old.store_product_id)
        await self.entitlements.sync_from_purchase(old, product)

    # ======================================================== accounting

    async def _record_charge(
        self, purchase: StorePurchase, verified: VerifiedPurchase, *, renewal: bool
    ) -> None:
        """One CHARGE per store transaction, whatever path saw it first.

        Store revenue is posted gross when the store reports a price (Apple
        does). Google's purchase APIs do not, so a Google charge is recorded
        without an amount and posts nothing: its revenue is reconciled from
        Play's financial reports. Never an expert payable - store revenue is
        the platform's.
        """
        rail = RAIL[verified.provider]
        now = datetime.now(UTC)
        transaction = PaymentTransaction(
            provider=verified.provider.value,
            rail=rail.value,
            user_id=purchase.user_id,
            store_purchase_id=purchase.id,
            external_transaction_ref=verified.external_transaction_id or "",
            type=TransactionType.CHARGE.value,
            amount_minor=verified.amount_minor,
            currency=verified.currency.upper() if verified.currency else None,
            status="succeeded",
            occurred_at=verified.purchased_at or now,
            created_at=now,
            metadata_safe={"environment": verified.environment.value, "product": verified.store_product_ref},
        )
        try:
            async with self.session.begin_nested():
                self.session.add(transaction)
                await self.session.flush()
        except IntegrityError:
            return  # already recorded
        if transaction.amount_minor and transaction.currency:
            await self.ledger.post(
                journal_key=f"store_charge:{transaction.id}",
                entry_type=TransactionType.CHARGE,
                currency=transaction.currency,
                payment_transaction_id=transaction.id,
                occurred_at=transaction.occurred_at,
                postings=[
                    Posting(LedgerAccount.STORE_CLEARING, DEBIT, transaction.amount_minor),
                    Posting(LedgerAccount.PLATFORM_REVENUE, CREDIT, transaction.amount_minor),
                ],
            )
        if renewal:
            await self._push(
                PushEvent.SUBSCRIPTION_RENEWED, purchase, f"renewed:{transaction.id}"
            )

    async def _record_store_refund(self, purchase: StorePurchase, verified: VerifiedPurchase) -> None:
        """The store took the money back: reverse what we posted, once."""
        now = datetime.now(UTC)
        purchase.refunded_at = purchase.refunded_at or now
        charges = list(
            await self.session.scalars(
                select(PaymentTransaction).where(
                    PaymentTransaction.store_purchase_id == purchase.id,
                    PaymentTransaction.type == TransactionType.CHARGE.value,
                )
            )
        )
        for charge in charges:
            refund = PaymentTransaction(
                provider=charge.provider,
                rail=charge.rail,
                user_id=charge.user_id,
                store_purchase_id=purchase.id,
                related_transaction_id=charge.id,
                external_transaction_ref=charge.external_transaction_ref,
                type=TransactionType.REFUND.value,
                amount_minor=charge.amount_minor,
                currency=charge.currency,
                status="succeeded",
                occurred_at=verified.revoked_at or now,
                created_at=now,
                metadata_safe={"reason": verified.revocation_reason},
            )
            try:
                async with self.session.begin_nested():
                    self.session.add(refund)
                    await self.session.flush()
            except IntegrityError:
                continue
            if charge.amount_minor and charge.currency:
                await self.ledger.post(
                    journal_key=f"store_refund:{charge.id}",
                    entry_type=TransactionType.REFUND,
                    currency=charge.currency,
                    payment_transaction_id=refund.id,
                    postings=[
                        Posting(LedgerAccount.PLATFORM_REVENUE, DEBIT, charge.amount_minor),
                        Posting(LedgerAccount.STORE_CLEARING, CREDIT, charge.amount_minor),
                    ],
                )
        await self.session.flush()
        await self._push(PushEvent.REFUND_PROCESSED, purchase, f"store_refund:{purchase.id}")

    async def _push(self, event: PushEvent, purchase: StorePurchase, key: str) -> None:
        # Generic text only: no amount, no product, no transaction id.
        await self.outbox.enqueue(
            event=event,
            user_id=purchase.user_id,
            dedupe_key=f"{event.value}:{key}"[:160],
            data={},
        )

    # ============================================================ Apple

    async def verify_apple(
        self,
        user_id: uuid.UUID,
        *,
        product_code: str,
        signed_transaction: str | None,
        transaction_id: str | None,
        provider,  # noqa: ANN001 - AppleStoreProvider
    ) -> ApplyResult:
        if not provider.configured:
            raise StoreNotConfigured()
        if transaction_id and provider.api_configured:
            # The authoritative read: Apple's server, not the device.
            verified = await provider.fetch_transaction(transaction_id)
            if signed_transaction:
                claimed = provider.verify_signed_transaction(signed_transaction)
                if claimed.external_transaction_id != verified.external_transaction_id:
                    raise StoreVerificationFailed(details={"reason": "transaction_mismatch"})
        elif signed_transaction:
            # Apple-signed and verified to Apple's root: genuine, though it may
            # be older than Apple's current view. Subscriptions are refreshed
            # below when the API is available.
            verified = provider.verify_signed_transaction(signed_transaction)
        else:
            raise StoreVerificationFailed(details={"reason": "no_transaction_supplied"})

        if verified.product_kind == "subscription" and provider.api_configured and verified.original_transaction_id:
            verified = await provider.fetch_subscription(verified.original_transaction_id)

        self.check_environment(verified)
        product = await self.product_for(verified, product_code)
        self.check_account(user_id, verified)
        return await self.apply(user_id, verified, product)

    # =========================================================== Google

    async def verify_google(
        self,
        user_id: uuid.UUID,
        *,
        product_code: str,
        purchase_token: str,
        provider,  # noqa: ANN001 - GooglePlayProvider
    ) -> ApplyResult:
        if not provider.configured:
            raise StoreNotConfigured()
        requested = await self.catalog.by_code(product_code)
        if requested is None:
            raise UnknownStoreProduct()
        if StoreProductType(requested.product_type) is StoreProductType.SUBSCRIPTION:
            verified = await provider.get_subscription(purchase_token)
        else:
            verified = await provider.get_product(purchase_token)
            verified.product_kind = requested.product_type
        self.check_environment(verified)
        product = await self.product_for(verified, product_code)
        self.check_account(user_id, verified)
        return await self.apply(user_id, verified, product)

    async def complete_google(
        self, result: ApplyResult, purchase_token: str, provider  # noqa: ANN001
    ) -> None:
        """Acknowledge or consume at Google - after our commit, never before.

        The irreversible step goes last: if it fails, the entitlement is safely
        recorded and the next verification, restore or RTDN retries it. If it
        succeeded but our write failed, Google would still show the purchase
        and a retry would find it; if we acknowledged before recording, a crash
        in between would leave a paid purchase with nothing granted.
        """
        if result.completion is None:
            return
        product_ref = result.purchase.store_product_ref
        if result.completion == "consume":
            await provider.consume_product(product_ref, purchase_token)
            result.purchase.store_consumed_at = datetime.now(UTC)
        elif StoreProductType(result.product.product_type) is StoreProductType.SUBSCRIPTION:
            await provider.acknowledge_subscription(product_ref, purchase_token)
        else:
            await provider.acknowledge_product(product_ref, purchase_token)
        result.purchase.acknowledged_at = result.purchase.acknowledged_at or datetime.now(UTC)
        await self.session.flush()
        logger.info(
            "store_purchase_completed_at_store",
            purchase_id=str(result.purchase.id),
            action=result.completion,
        )
