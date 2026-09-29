"""Prove the coin ledger holds under real concurrency, against Postgres.

    python -m scripts.coin_concurrency_check

The in-process lock is bypassed on purpose (`_apply_locked`), so only the
wallet row lock and the ledger's unique key stand between the racers:

1. 20 concurrent spends of 10 from a balance of 55 -> exactly 5 succeed,
   balance 5, never negative.
2. 10 concurrent grants with one idempotency key -> one ledger row.

Rows belong to a marker account and are deleted at the end. Refuses SQLite
and production.
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from sqlalchemy import delete, func, select

from app.core.config import settings
from app.db.models.coins import CoinTransaction, CoinWallet
from app.db.models.user import User, UserProfile
from app.db.session import get_session_factory
from app.services.coins.service import CoinService, InsufficientCoins

MARKER = "coin-concurrency-check"


async def spend_once(factory, user_id: uuid.UUID, index: int) -> bool:
    async with factory() as db:
        try:
            await CoinService(db)._apply_locked(
                user_id, -10, kind="spend", reason="check", key=f"spend:{index}",
                reference_id=None, meta=None, allow_partial=False,
            )
            await db.commit()
            return True
        except InsufficientCoins:
            await db.rollback()
            return False


async def grant_once(factory, user_id: uuid.UUID) -> str:
    async with factory() as db:
        row = await CoinService(db)._apply_locked(
            user_id, 7, kind="ad_reward", reason="check", key="grant:same",
            reference_id=None, meta=None, allow_partial=False,
        )
        await db.commit()
        return str(row.id)


async def main() -> int:
    if settings.database_url.startswith("sqlite") or settings.is_production:
        print("refused: needs a non-production Postgres")
        return 2
    factory = get_session_factory()
    async with factory() as db:
        user = User(email=f"{MARKER}-{uuid.uuid4().hex[:8]}@example.com")
        db.add(user)
        await db.flush()
        db.add(UserProfile(user_id=user.id, name="Check"))
        await db.commit()
        user_id = user.id
    failures: list[str] = []
    try:
        async with factory() as db:
            await CoinService(db)._apply_locked(
                user_id, 55, kind="purchase", reason="seed", key="seed",
                reference_id=None, meta=None, allow_partial=False,
            )
            await db.commit()

        results = await asyncio.gather(*(spend_once(factory, user_id, i) for i in range(20)))
        async with factory() as db:
            balance = await db.scalar(select(CoinWallet.balance).where(CoinWallet.user_id == user_id))
        print(f"spends: 20 concurrent x10 from 55 -> {sum(results)} succeeded, balance {balance}")
        if sum(results) != 5 or balance != 5:
            failures.append("concurrent spends overspent or lost updates")

        ids = await asyncio.gather(*(grant_once(factory, user_id) for _ in range(10)))
        async with factory() as db:
            rows = await db.scalar(
                select(func.count()).select_from(CoinTransaction).where(
                    CoinTransaction.user_id == user_id,
                    CoinTransaction.idempotency_key == "grant:same",
                )
            )
            balance = await db.scalar(select(CoinWallet.balance).where(CoinWallet.user_id == user_id))
        print(f"grants: 10 concurrent same key -> {len(set(ids))} id(s), {rows} row(s), balance {balance}")
        if len(set(ids)) != 1 or rows != 1 or balance != 12:
            failures.append("idempotent grant applied more than once")
    finally:
        async with factory() as db:
            await db.execute(delete(CoinTransaction).where(CoinTransaction.user_id == user_id))
            await db.execute(delete(CoinWallet).where(CoinWallet.user_id == user_id))
            await db.execute(delete(UserProfile).where(UserProfile.user_id == user_id))
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()

    if failures:
        print("FAIL:", "; ".join(failures))
        return 1
    print("PASS: no overspend, no double grant")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
