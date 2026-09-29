"""Entitlements: what a user may do, derived only from verified purchases.

Three layers, each derived from the one before:

    store_purchases   facts the store verified
         ↓
    user_entitlements what those facts grant (a subscription, credits, a
                      permanent unlock)
         ↓
    subscriptions     the per-user tier projection `User.tier` reads - the B4
                      table, reused rather than duplicated

A client saying "purchase successful" writes none of them.

`EntitlementPolicyService` is the one place that answers "does this grant
access right now" and "what does premium include". Feature code asks it; it
does not re-implement grace periods or expiry.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.db.models.payments import StoreProduct, StorePurchase, UserEntitlement
from app.db.models.subscription import Subscription
from app.domain.enums import SubscriptionStatus, SubscriptionTier
from app.domain.payments import (
    EntitlementKind,
    EntitlementStatus,
    PurchaseStatus,
    StoreProductType,
)
from app.services.payments.catalog import COINS, COSMIC_PLUS, PLAN_ENTITLEMENTS, PREMIUM

logger = get_logger(__name__)


class NoCreditAvailable(AppError):
    status_code = 402
    code = "no_credit_available"
    message = "There is no unused purchase for this."


# A purchase state -> the entitlement state it implies.
_SUBSCRIPTION_STATE = {
    PurchaseStatus.ACTIVE: EntitlementStatus.ACTIVE,
    PurchaseStatus.CANCELLED_PENDING_EXPIRY: EntitlementStatus.CANCELLED_PENDING_EXPIRY,
    PurchaseStatus.GRACE_PERIOD: EntitlementStatus.GRACE_PERIOD,
    PurchaseStatus.ON_HOLD: EntitlementStatus.ON_HOLD,
    PurchaseStatus.PAUSED: EntitlementStatus.PAUSED,
    PurchaseStatus.EXPIRED: EntitlementStatus.EXPIRED,
    PurchaseStatus.REVOKED: EntitlementStatus.REVOKED,
    PurchaseStatus.CANCELLED: EntitlementStatus.EXPIRED,
}

# Purchase states that may create an entitlement at all. PENDING never does:
# Google and Apple both say not to grant anything before a purchase completes.
ENTITLING = frozenset(
    {
        PurchaseStatus.ACTIVE,
        PurchaseStatus.CANCELLED_PENDING_EXPIRY,
        PurchaseStatus.GRACE_PERIOD,
    }
)


def _aware(moment: datetime | None) -> datetime | None:
    if moment is not None and moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment


class EntitlementPolicyService:
    """Does an entitlement grant access now, and what does premium include."""

    def grants_access(self, entitlement: UserEntitlement, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        status = EntitlementStatus(entitlement.status)
        expires = _aware(entitlement.expires_at)
        if status is EntitlementStatus.ACTIVE:
            return expires is None or expires > now
        if status is EntitlementStatus.CANCELLED_PENDING_EXPIRY:
            # Cancelled is not ended: it was paid up to the expiry.
            return expires is not None and expires > now
        if status is EntitlementStatus.GRACE_PERIOD:
            # Both stores mean grace as "keep access while payment is retried".
            # A business may decide otherwise; it is one setting.
            if not settings.premium_during_grace_period:
                return False
            grace = _aware(entitlement.grace_until)
            return grace is None or grace > now
        # ON_HOLD, PAUSED, EXPIRED, REVOKED, CONSUMED.
        return False

    def capabilities(self, tier: SubscriptionTier) -> dict[str, object]:
        """What a tier includes.

        Limits come from configuration. Where the product has not decided a
        premium number, premium gets the free number: the seam exists, the
        value is not invented.
        """
        tier = SubscriptionTier(tier)
        premium = tier.includes(SubscriptionTier.PREMIUM)
        cosmic = tier.includes(SubscriptionTier.COSMIC_PLUS)
        return {
            "tier": tier.value,
            "ai_chat_rate_limit": (
                settings.ai_chat_rate_limit_premium if premium and settings.ai_chat_rate_limit_premium
                else settings.ai_chat_rate_limit
            ),
            "ai_report_rate_limit": (
                settings.ai_report_rate_limit_premium
                if premium and settings.ai_report_rate_limit_premium
                else settings.ai_report_rate_limit
            ),
            # Whether premium includes the reports otherwise sold as credits.
            "premium_reports": (
                (premium and settings.paid_reports_included_in_premium)
                or (cosmic and settings.paid_reports_included_in_cosmic_plus)
            ),
            "advanced_forecasts": premium,
            "ad_free": premium,
            "monthly_coins": (
                settings.monthly_coins_cosmic_plus if cosmic
                else settings.monthly_coins_premium if premium
                else 0
            ),
        }


class EntitlementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.policy = EntitlementPolicyService()

    # ---------------------------------------------------------- derivation

    async def sync_from_purchase(
        self, purchase: StorePurchase, product: StoreProduct
    ) -> list[UserEntitlement]:
        """Bring a purchase's entitlements in line with it. Idempotent.

        Units are unique per purchase, so however many times a purchase is
        verified - by the client, a notification, a restore - it yields each
        credit exactly once.
        """
        status = PurchaseStatus(purchase.status)
        product_type = StoreProductType(product.product_type)
        existing = list(
            await self.session.scalars(
                select(UserEntitlement).where(UserEntitlement.store_purchase_id == purchase.id)
            )
        )

        if product_type is StoreProductType.SUBSCRIPTION:
            target = _SUBSCRIPTION_STATE.get(status)
            if not existing:
                if status not in ENTITLING:
                    return []
                existing = await self._create_units(purchase, product, EntitlementKind.SUBSCRIPTION, 1)
            for row in existing:
                if target is not None:
                    row.status = target.value
                row.expires_at = purchase.expires_at
                row.grace_until = purchase.grace_until
                row.auto_renewing = purchase.auto_renewing
            await self.session.flush()
            return existing

        if product.entitlement_code == COINS:
            # A coin pack grants a ledger balance, not entitlement units. The
            # ledger's idempotency key is the purchase, so re-verifying it
            # (client, notification, restore) credits it exactly once.
            await self._sync_coin_pack(purchase, product, status)
            return []

        kind = (
            EntitlementKind.CREDIT
            if product_type is StoreProductType.CONSUMABLE
            else EntitlementKind.PERMANENT
        )
        if status is PurchaseStatus.REVOKED:
            # A refunded purchase takes back what has not been used. A credit
            # already consumed stays consumed: the report exists. That case is
            # visible in the purchase row for support.
            for row in existing:
                if row.status != EntitlementStatus.CONSUMED.value:
                    row.status = EntitlementStatus.REVOKED.value
            await self.session.flush()
            return existing
        if status not in ENTITLING:
            return existing

        units = product.units_per_purchase * max(purchase.quantity, 1)
        if kind is EntitlementKind.PERMANENT:
            units = 1
        if len(existing) < units:
            existing = await self._create_units(purchase, product, kind, units)
        return existing

    async def _sync_coin_pack(
        self, purchase: StorePurchase, product: StoreProduct, status: PurchaseStatus
    ) -> None:
        from app.services.coins.service import CoinService
        from app.services.payments.catalog import StoreCatalogService

        definition = StoreCatalogService.definition(product.code)
        coins = (definition.coins if definition else 0) * max(purchase.quantity, 1)
        if coins <= 0:
            return
        ledger = CoinService(self.session)
        if status is PurchaseStatus.REVOKED:
            await ledger.reverse_purchase(
                user_id=purchase.user_id,
                purchase_id=purchase.id,
                product_code=product.code,
                coins=coins,
            )
        elif status in ENTITLING:
            await ledger.grant_purchase(
                user_id=purchase.user_id,
                purchase_id=purchase.id,
                product_code=product.code,
                coins=coins,
            )

    async def _create_units(
        self,
        purchase: StorePurchase,
        product: StoreProduct,
        kind: EntitlementKind,
        units: int,
    ) -> list[UserEntitlement]:
        for index in range(units):
            try:
                async with self.session.begin_nested():
                    self.session.add(
                        UserEntitlement(
                            user_id=purchase.user_id,
                            entitlement_code=product.entitlement_code,
                            kind=kind.value,
                            source=purchase.provider,
                            store_purchase_id=purchase.id,
                            unit_index=index,
                            environment=purchase.environment,
                            status=EntitlementStatus.ACTIVE.value,
                            starts_at=purchase.purchased_at,
                            expires_at=purchase.expires_at if kind is EntitlementKind.SUBSCRIPTION else None,
                            grace_until=purchase.grace_until,
                            auto_renewing=purchase.auto_renewing,
                            original_transaction_ref=purchase.original_transaction_id
                            or purchase.external_transaction_id,
                        )
                    )
                    await self.session.flush()
            except IntegrityError:
                # Already derived - by a concurrent verification of the same
                # purchase. The unique index is the guarantee.
                pass
        return list(
            await self.session.scalars(
                select(UserEntitlement)
                .where(UserEntitlement.store_purchase_id == purchase.id)
                .order_by(UserEntitlement.unit_index)
            )
        )

    # ------------------------------------------------------------ projection

    async def refresh_projection(self, user_id: uuid.UUID) -> SubscriptionTier:
        """Write the tier `User.tier` reads, from entitlements alone."""
        now = datetime.now(UTC)
        rows = list(
            await self.session.scalars(
                select(UserEntitlement).where(
                    UserEntitlement.user_id == user_id,
                    UserEntitlement.entitlement_code.in_(PLAN_ENTITLEMENTS),
                    UserEntitlement.kind == EntitlementKind.SUBSCRIPTION.value,
                )
            )
        )
        granting = [row for row in rows if self.policy.grants_access(row, now)]
        # The highest plan wins; within a plan, the one that lasts longest.
        best = max(
            granting,
            key=lambda row: (
                PLAN_ENTITLEMENTS.index(row.entitlement_code),
                _aware(row.expires_at) or now,
            ),
            default=None,
        )

        projection = await self.session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        if projection is None:
            projection = Subscription(user_id=user_id, tier=SubscriptionTier.FREE)
            self.session.add(projection)

        if best is None:
            projection.tier = SubscriptionTier.FREE
            projection.status = (
                SubscriptionStatus.EXPIRED if rows else SubscriptionStatus.ACTIVE
            )
            projection.expires_at = None
            tier = SubscriptionTier.FREE
        else:
            purchase = await self.session.get(StorePurchase, best.store_purchase_id) if best.store_purchase_id else None
            best_tier = (
                SubscriptionTier.COSMIC_PLUS
                if best.entitlement_code == COSMIC_PLUS
                else SubscriptionTier.PREMIUM
            )
            projection.tier = best_tier
            # Cancelled-but-paid is still access until expiry. It is projected
            # as ACTIVE, because the B4 projection treats CANCELLED as no
            # access; the expiry below is what ends it. The entitlement row
            # keeps the precise state for the client.
            projection.status = (
                SubscriptionStatus.GRACE
                if best.status == EntitlementStatus.GRACE_PERIOD.value
                else SubscriptionStatus.ACTIVE
            )
            # Grace keeps access beyond the paid expiry; the projection's
            # expiry follows whichever is later so `User.tier` agrees with the
            # policy.
            grace = _aware(best.grace_until)
            expires = _aware(best.expires_at)
            if best.status == EntitlementStatus.GRACE_PERIOD.value:
                expires = grace
            projection.expires_at = expires
            projection.started_at = best.starts_at
            projection.platform = best.source
            projection.transaction_id = best.original_transaction_ref
            projection.product_id = purchase.store_product_ref if purchase else None
            tier = best_tier
        await self.session.flush()
        return tier

    # ------------------------------------------------------------- reading

    async def for_user(self, user_id: uuid.UUID) -> list[UserEntitlement]:
        return list(
            await self.session.scalars(
                select(UserEntitlement)
                .where(UserEntitlement.user_id == user_id)
                .order_by(UserEntitlement.entitlement_code, UserEntitlement.created_at)
            )
        )

    async def has_access(self, user_id: uuid.UUID, entitlement_code: str) -> bool:
        rows = await self.session.scalars(
            select(UserEntitlement).where(
                UserEntitlement.user_id == user_id,
                UserEntitlement.entitlement_code == entitlement_code,
            )
        )
        return any(self.policy.grants_access(row) for row in rows)

    # ---------------------------------------------------------- consumption

    async def consume(
        self, user_id: uuid.UUID, entitlement_code: str, consumer_ref: str
    ) -> UserEntitlement:
        """Use one credit, once per `consumer_ref`.

        A network retry repeats `consume` with the same reference and gets the
        same credit back, so it cannot use a second credit.

        Paid AI reports do not use this: they reserve a credit together with
        their job (`reserve`) and consume it on delivery (`settle`).
        """
        return await self._take(
            user_id, entitlement_code, consumer_ref, EntitlementStatus.CONSUMED
        )

    async def reserve(
        self, user_id: uuid.UUID, entitlement_code: str, consumer_ref: str
    ) -> UserEntitlement:
        """Hold one credit for `consumer_ref` until `settle`. Idempotent.

        A reserved credit is no longer available to anything else, and a
        refund of its purchase revokes it like any unused credit.
        """
        return await self._take(
            user_id, entitlement_code, consumer_ref, EntitlementStatus.RESERVED
        )

    async def settle(self, entitlement_id: uuid.UUID, consumer_ref: str) -> UserEntitlement | None:
        """Turn a reservation into a consumption. None if it is no longer held.

        Row-locked, so a concurrent refund either revokes it first (and the
        caller must not deliver) or finds it consumed.
        """
        statement = select(UserEntitlement).where(UserEntitlement.id == entitlement_id)
        if _is_postgres(self.session):
            statement = statement.with_for_update()
        credit = await self.session.scalar(statement)
        if credit is None or credit.consumed_ref != consumer_ref:
            return None
        if credit.status == EntitlementStatus.CONSUMED.value:
            return credit
        if credit.status != EntitlementStatus.RESERVED.value:
            return None
        credit.status = EntitlementStatus.CONSUMED.value
        credit.consumed_at = datetime.now(UTC)
        await self.session.flush()
        return credit

    async def release(self, entitlement_id: uuid.UUID, consumer_ref: str) -> bool:
        """Give a reservation back, unused. False if it is not held as one."""
        statement = select(UserEntitlement).where(UserEntitlement.id == entitlement_id)
        if _is_postgres(self.session):
            statement = statement.with_for_update()
        credit = await self.session.scalar(statement)
        if (
            credit is None
            or credit.consumed_ref != consumer_ref
            or credit.status != EntitlementStatus.RESERVED.value
        ):
            return False
        credit.status = EntitlementStatus.ACTIVE.value
        credit.consumed_ref = None
        credit.consumed_at = None
        await self.session.flush()
        return True

    async def is_held(self, entitlement_id: uuid.UUID, consumer_ref: str) -> bool:
        """Whether a reservation (or its consumption) still stands."""
        credit = await self.session.get(UserEntitlement, entitlement_id)
        if credit is not None:
            await self.session.refresh(credit)
        return (
            credit is not None
            and credit.consumed_ref == consumer_ref
            and credit.status
            in (EntitlementStatus.RESERVED.value, EntitlementStatus.CONSUMED.value)
        )

    async def _take(
        self,
        user_id: uuid.UUID,
        entitlement_code: str,
        consumer_ref: str,
        target: EntitlementStatus,
    ) -> UserEntitlement:
        if _is_postgres(self.session):
            # Serialise takers of the *same* reference. Without this, ten
            # concurrent retries all miss the idempotency check below, race for
            # a credit with SKIP LOCKED, and nine are told there is no credit
            # while the tenth is still committing. Transaction-scoped, keyed
            # by (user, reference); distinct references never wait on it.
            await advisory_xact_lock(self.session, f"{user_id}:{consumer_ref}")

        already = await self.session.scalar(
            select(UserEntitlement).where(
                UserEntitlement.user_id == user_id,
                UserEntitlement.consumed_ref == consumer_ref,
            )
        )
        if already is not None:
            if already.entitlement_code != entitlement_code:
                raise AppError(
                    "That reference already used a different credit.",
                    code="consumption_conflict",
                    status_code=409,
                )
            return already

        statement = (
            select(UserEntitlement)
            .where(
                UserEntitlement.user_id == user_id,
                UserEntitlement.entitlement_code == entitlement_code,
                UserEntitlement.kind == EntitlementKind.CREDIT.value,
                UserEntitlement.status == EntitlementStatus.ACTIVE.value,
            )
            .order_by(UserEntitlement.created_at, UserEntitlement.unit_index)
            .limit(1)
        )
        if _is_postgres(self.session):
            statement = statement.with_for_update(skip_locked=True)
        credit = await self.session.scalar(statement)
        if credit is None:
            raise NoCreditAvailable(details={"entitlement_code": entitlement_code})

        credit.status = target.value
        credit.consumed_at = (
            datetime.now(UTC) if target is EntitlementStatus.CONSUMED else None
        )
        credit.consumed_ref = consumer_ref[:120]
        try:
            async with self.session.begin_nested():
                await self.session.flush()
        except IntegrityError:
            # The same reference taken concurrently, on another credit.
            await self.session.refresh(credit)
            winner = await self.session.scalar(
                select(UserEntitlement).where(
                    UserEntitlement.user_id == user_id,
                    UserEntitlement.consumed_ref == consumer_ref,
                )
            )
            if winner is None:
                raise
            return winner
        logger.info(
            "entitlement_consumed" if target is EntitlementStatus.CONSUMED else "entitlement_reserved",
            user_id=str(user_id),
            entitlement_code=entitlement_code,
            entitlement_id=str(credit.id),
        )
        return credit


def _is_postgres(session: AsyncSession) -> bool:
    bind = session.bind
    return bind is not None and bind.dialect.name != "sqlite"


async def advisory_xact_lock(session: AsyncSession, key: str) -> None:
    """A transaction-scoped Postgres advisory lock on `key`. No-op on SQLite."""
    if not _is_postgres(session):
        return
    digest = hashlib.sha256(key.encode()).digest()
    await session.execute(
        select(func.pg_advisory_xact_lock(int.from_bytes(digest[:8], "big", signed=True)))
    )
