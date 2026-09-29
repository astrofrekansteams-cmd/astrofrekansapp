"""Prove "one draw session = at most one reading" against a real Postgres.

    python -m scripts.divination_reveal_concurrency_check

SQLite in the unit suite shares one connection, so it cannot race. Here:

1. **10 concurrent reveals, same picks, 10 separate DB sessions** - the
   in-process route lock is bypassed on purpose, so only the row lock and the
   unique constraints stand between the racers -> exactly one reading, every
   racer returns it.
2. **10 concurrent creates with one consumer_ref** -> one session row.
3. **Different picks after completion** -> `session_already_completed`.

Rows belong to a marker account and are deleted at the end. Refuses SQLite
and production.
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from sqlalchemy import delete, func, select

from app.core.config import settings
from app.db.models.divination import (
    DivinationDrawItem,
    DivinationDrawSession,
    DivinationReading,
)
from app.db.models.user import User, UserProfile
from app.db.session import get_session_factory
from app.domain.divination import DeckType
from app.services.divination.sessions import (
    DrawSessionService,
    RevealRaceLost,
    SessionAlreadyCompleted,
)

MARKER = "divination-reveal-check"
CONCURRENCY = 10


async def make_user(factory) -> User:
    async with factory() as db:
        user = User(email=f"{MARKER}-{uuid.uuid4().hex[:8]}@example.com")
        db.add(user)
        await db.flush()
        db.add(UserProfile(user_id=user.id, name="Check"))
        await db.commit()
        return user


async def reveal_once(factory, user: User, session_id: uuid.UUID, picks: list[int]) -> str:
    async with factory() as db:
        service = DrawSessionService(db)
        try:
            reading = await service.reveal(user, session_id, picks)
            await db.commit()
        except (RevealRaceLost, Exception) as exc:  # noqa: BLE001 - IntegrityError too
            if isinstance(exc, SessionAlreadyCompleted):
                raise
            await db.rollback()
            reading = await service.reveal(user, session_id, picks)
        return str(reading.id)


async def create_once(factory, user: User, ref: str) -> str:
    async with factory() as db:
        row = await DrawSessionService(db).create(
            user,
            consumer_ref=ref,
            deck_type=DeckType.TAROT,
            spread_code="past_present_future",
            locale="tr",
            question=None,
            include_optional_items=False,
        )
        await db.commit()
        return str(row.id)


async def main() -> int:
    if settings.database_url.startswith("sqlite") or settings.is_production:
        print("refused: needs a non-production Postgres")
        return 2
    factory = get_session_factory()
    user = await make_user(factory)
    failures: list[str] = []
    try:
        # 2. concurrent creates, one ref
        ref = f"{MARKER}-{uuid.uuid4().hex}"
        ids = await asyncio.gather(*(create_once(factory, user, ref) for _ in range(CONCURRENCY)))
        async with factory() as db:
            rows = await db.scalar(
                select(func.count()).select_from(DivinationDrawSession).where(
                    DivinationDrawSession.user_id == user.id,
                    DivinationDrawSession.consumer_ref == ref,
                )
            )
        print(f"creates: {CONCURRENCY} calls -> {len(set(ids))} session id(s), {rows} row(s)")
        if len(set(ids)) != 1 or rows != 1:
            failures.append("concurrent create produced more than one session")

        # 1. concurrent reveals
        session_id = uuid.UUID(ids[0])
        results = await asyncio.gather(
            *(reveal_once(factory, user, session_id, [7, 24, 51]) for _ in range(CONCURRENCY)),
            return_exceptions=True,
        )
        errors = [r for r in results if isinstance(r, BaseException)]
        reading_ids = {r for r in results if isinstance(r, str)}
        async with factory() as db:
            readings = await db.scalar(
                select(func.count()).select_from(DivinationReading).where(
                    DivinationReading.draw_session_id == session_id
                )
            )
        print(
            f"reveals: {CONCURRENCY} concurrent -> {len(reading_ids)} distinct reading id(s), "
            f"{readings} reading row(s), {len(errors)} error(s)"
        )
        if errors:
            failures.append(f"reveal errors: {[type(e).__name__ for e in errors]}")
        if len(reading_ids) != 1 or readings != 1:
            failures.append("concurrent reveal produced more than one reading")

        # 3. different picks after completion
        try:
            await reveal_once(factory, user, session_id, [1, 2, 3])
            failures.append("different picks on a completed session were accepted")
        except SessionAlreadyCompleted:
            print("different picks after completion -> session_already_completed")
    finally:
        async with factory() as db:
            reading_ids_q = select(DivinationReading.id).where(DivinationReading.user_id == user.id)
            await db.execute(
                delete(DivinationDrawSession).where(DivinationDrawSession.user_id == user.id)
            )
            await db.execute(
                delete(DivinationDrawItem).where(DivinationDrawItem.reading_id.in_(reading_ids_q))
            )
            await db.execute(delete(DivinationReading).where(DivinationReading.user_id == user.id))
            await db.execute(delete(UserProfile).where(UserProfile.user_id == user.id))
            await db.execute(delete(User).where(User.id == user.id))
            await db.commit()

    if failures:
        print("FAIL:", "; ".join(failures))
        return 1
    print("PASS: one session = one reading; create is idempotent under concurrency")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
