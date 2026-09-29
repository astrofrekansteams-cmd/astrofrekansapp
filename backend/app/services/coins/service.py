"""The coin ledger service: the only code that moves coins.

Every movement is one ledger row plus the wallet update, in the caller's
transaction, under a row lock on the wallet (Postgres) - so two spends cannot
both see the same balance. Each movement has an idempotency key; repeating a
key returns the original row and moves nothing.
"""

from __future__ import annotations

import asyncio
import uuid
import weakref
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, NotFound
from app.core.logging import get_logger
from app.db.models.coins import CoinTransaction, CoinWallet
from app.db.models.user import User
from app.services.coins.ads import get_ad_verifier
from app.services.coins.catalog import monthly_bonus, spend_item

logger = get_logger(__name__)

KIND_PURCHASE = "purchase"
KIND_PURCHASE_REVERSAL = "purchase_reversal"
KIND_AD_REWARD = "ad_reward"
KIND_MONTHLY_BONUS = "monthly_bonus"
KIND_SPEND = "spend"
KIND_REFUND = "refund"


class InsufficientCoins(AppError):
    status_code = 402
    code = "insufficient_coins"
    message = "Not enough AstroCoins."


class AdRewardLimitReached(AppError):
    status_code = 429
    code = "ad_reward_limit_reached"
    message = "Today's rewarded ads are used up."


class UnknownSpendItem(AppError):
    status_code = 422
    code = "unknown_spend_item"
    message = "This item cannot be bought with AstroCoins."


_wallet_locks: "weakref.WeakValueDictionary[uuid.UUID, asyncio.Lock]" = (
    weakref.WeakValueDictionary()
)


def _lock_for(user_id: uuid.UUID) -> asyncio.Lock:
    """In-process serialisation of one user's coin movements.

    Only an optimisation for this process (and what makes SQLite tests
    deterministic): across processes the wallet row lock and the ledger's
    unique key decide.
    """
    lock = _wallet_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _wallet_locks[user_id] = lock
    return lock


class CoinService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -------------------------------------------------------------- reading

    async def wallet(self, user_id: uuid.UUID, *, lock: bool = False) -> CoinWallet:
        query = select(CoinWallet).where(CoinWallet.user_id == user_id)
        if lock:
            query = query.with_for_update()
        wallet = await self.session.scalar(query.execution_options(populate_existing=True))
        if wallet is not None:
            return wallet
        try:
            async with self.session.begin_nested():
                wallet = CoinWallet(user_id=user_id, balance=0)
                self.session.add(wallet)
                await self.session.flush()
        except IntegrityError:
            wallet = await self.session.scalar(query)
        return wallet

    async def history(
        self, user_id: uuid.UUID, *, limit: int = 50, before: datetime | None = None
    ) -> list[CoinTransaction]:
        query = select(CoinTransaction).where(CoinTransaction.user_id == user_id)
        if before is not None:
            query = query.where(CoinTransaction.created_at < before)
        return list(
            await self.session.scalars(
                query.order_by(CoinTransaction.created_at.desc()).limit(limit)
            )
        )

    async def _by_key(self, user_id: uuid.UUID, key: str) -> CoinTransaction | None:
        return await self.session.scalar(
            select(CoinTransaction).where(
                CoinTransaction.user_id == user_id,
                CoinTransaction.idempotency_key == key,
            )
        )

    # ------------------------------------------------------------- moving

    async def _apply(
        self,
        user_id: uuid.UUID,
        amount: int,
        *,
        kind: str,
        reason: str,
        key: str,
        reference_id: str | None = None,
        meta: dict | None = None,
        allow_partial: bool = False,
    ) -> CoinTransaction | None:
        """One ledger row + the wallet. Idempotent per `key`."""
        lock = _lock_for(user_id)
        async with lock:
            return await self._apply_locked(
                user_id,
                amount,
                kind=kind,
                reason=reason,
                key=key,
                reference_id=reference_id,
                meta=meta,
                allow_partial=allow_partial,
            )

    async def _apply_locked(
        self,
        user_id: uuid.UUID,
        amount: int,
        *,
        kind: str,
        reason: str,
        key: str,
        reference_id: str | None,
        meta: dict | None,
        allow_partial: bool,
    ) -> CoinTransaction | None:
        existing = await self._by_key(user_id, key)
        if existing is not None:
            return existing
        wallet = await self.wallet(user_id, lock=True)
        # Re-check under the lock: a concurrent twin may have just written it.
        existing = await self._by_key(user_id, key)
        if existing is not None:
            return existing

        if amount < 0 and wallet.balance + amount < 0:
            if not allow_partial:
                raise InsufficientCoins(
                    details={"balance": wallet.balance, "required": -amount}
                )
            amount = -wallet.balance
            if amount == 0:
                return None

        try:
            async with self.session.begin_nested():
                row = CoinTransaction(
                    user_id=user_id,
                    amount=amount,
                    balance_after=wallet.balance + amount,
                    kind=kind,
                    reason=reason,
                    idempotency_key=key,
                    reference_id=reference_id,
                    meta=meta,
                )
                self.session.add(row)
                wallet.balance += amount
                if amount > 0 and kind != KIND_REFUND:
                    wallet.lifetime_earned += amount
                if amount < 0 and kind == KIND_SPEND:
                    wallet.lifetime_spent += -amount
                if amount > 0 and kind == KIND_REFUND:
                    wallet.lifetime_spent -= amount
                await self.session.flush()
        except IntegrityError:
            # Lost a race on the idempotency key (SQLite has no row lock).
            await self.session.refresh(wallet)
            row = await self._by_key(user_id, key)
        logger.info(
            "coin_transaction",
            user_id=str(user_id),
            kind=kind,
            reason=reason,
            amount=amount,
        )
        return row

    # --------------------------------------------------------------- earn

    async def grant_purchase(
        self, *, user_id: uuid.UUID, purchase_id: uuid.UUID, product_code: str, coins: int
    ) -> CoinTransaction | None:
        return await self._apply(
            user_id,
            coins,
            kind=KIND_PURCHASE,
            reason=product_code,
            key=f"purchase:{purchase_id}",
            reference_id=str(purchase_id),
        )

    async def reverse_purchase(
        self, *, user_id: uuid.UUID, purchase_id: uuid.UUID, product_code: str, coins: int
    ) -> CoinTransaction | None:
        """A refunded pack takes back what is left of it (never below zero)."""
        granted = await self._by_key(user_id, f"purchase:{purchase_id}")
        if granted is None:
            return None
        return await self._apply(
            user_id,
            -coins,
            kind=KIND_PURCHASE_REVERSAL,
            reason=product_code,
            key=f"purchase_reversal:{purchase_id}",
            reference_id=str(purchase_id),
            allow_partial=True,
        )

    async def ads_today(self, user_id: uuid.UUID) -> int:
        start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        return int(
            await self.session.scalar(
                select(func.count()).select_from(CoinTransaction).where(
                    CoinTransaction.user_id == user_id,
                    CoinTransaction.kind == KIND_AD_REWARD,
                    CoinTransaction.created_at >= start,
                )
            )
            or 0
        )

    async def reward_ad(self, user: User, *, token: str) -> CoinTransaction:
        verifier = get_ad_verifier()
        reward = await verifier.verify(user_id=str(user.id), token=token)
        key = f"ad:{reward.network}:{reward.reward_id}"
        existing = await self._by_key(user.id, key)
        if existing is not None:
            return existing
        if await self.ads_today(user.id) >= settings.ad_rewards_per_day:
            raise AdRewardLimitReached(
                details={"limit": settings.ad_rewards_per_day}
            )
        row = await self._apply(
            user.id,
            settings.ad_reward_coins,
            kind=KIND_AD_REWARD,
            reason=reward.network,
            key=key,
            reference_id=reward.reward_id[:80],
        )
        assert row is not None
        return row

    async def ensure_monthly_bonus(self, user: User) -> CoinTransaction | None:
        """This month's plan bonus, granted lazily and at most once per plan.

        An upgrade mid-month tops up to the higher plan's bonus.
        """
        bonus = monthly_bonus(user.tier)
        if bonus <= 0:
            return None
        month = datetime.now(UTC).strftime("%Y-%m")
        granted = int(
            await self.session.scalar(
                select(func.coalesce(func.sum(CoinTransaction.amount), 0)).where(
                    CoinTransaction.user_id == user.id,
                    CoinTransaction.kind == KIND_MONTHLY_BONUS,
                    CoinTransaction.reason == month,
                )
            )
            or 0
        )
        if granted >= bonus:
            return None
        return await self._apply(
            user.id,
            bonus - granted,
            kind=KIND_MONTHLY_BONUS,
            reason=month,
            key=f"bonus:{month}:{user.tier.value}",
            meta={"tier": user.tier.value},
        )

    # -------------------------------------------------------------- spend

    async def spend(
        self,
        user_id: uuid.UUID,
        *,
        items: list[str],
        consumer_ref: str,
        reference_id: str | None = None,
    ) -> CoinTransaction:
        """Pay for one action. `consumer_ref` makes a retry free."""
        known = [spend_item(code) for code in items]
        if not items or any(item is None or not item.available for item in known):
            raise UnknownSpendItem(details={"items": items})
        price = sum(item.price for item in known if item is not None)
        row = await self._apply(
            user_id,
            -price,
            kind=KIND_SPEND,
            reason="+".join(items)[:80],
            key=f"spend:{consumer_ref}",
            reference_id=reference_id,
            meta={"items": items, "price": price},
        )
        assert row is not None
        return row

    async def already_spent(self, user_id: uuid.UUID, consumer_ref: str) -> bool:
        """Whether `consumer_ref` was charged (a retry is then free)."""
        return await self._by_key(user_id, f"spend:{consumer_ref}") is not None

    async def spend_active(self, user_id: uuid.UUID, consumer_ref: str) -> bool:
        """Charged and not refunded: the work it paid for may still run."""
        if not await self.already_spent(user_id, consumer_ref):
            return False
        return await self._by_key(user_id, f"refund:{consumer_ref}") is None

    async def refund(self, user_id: uuid.UUID, *, consumer_ref: str) -> CoinTransaction | None:
        """Give back a spend whose work did not happen. Idempotent."""
        spent = await self._by_key(user_id, f"spend:{consumer_ref}")
        if spent is None:
            raise NotFound("No such spend.", code="coin_spend_not_found")
        return await self._apply(
            user_id,
            -spent.amount,
            kind=KIND_REFUND,
            reason=spent.reason,
            key=f"refund:{consumer_ref}",
            reference_id=spent.reference_id,
        )

    async def price_of(self, items: list[str]) -> int:
        return sum(spend_item(code).price for code in items if spend_item(code))
