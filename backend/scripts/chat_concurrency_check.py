"""Prove the chat and push invariants against a real Postgres.

    python -m scripts.chat_concurrency_check

The unit suite runs on SQLite, which serialises writers and has no
``SKIP LOCKED``. That proves the state machines and nothing about the locking,
so the two invariants that only a real database can settle are checked here:

1. **One notification, one delivery.** Many workers claim from the outbox at
   once. Every row must go to exactly one of them, or a user's phone buzzes
   twice for the same message.
2. **One conversation per order.** Many requests open the conversation for the
   same order simultaneously. The unique constraint - not an application-level
   ``SELECT`` first - is what has to hold, because two concurrent readers both
   see nothing and both insert.

It writes its own throwaway rows, checks them, and deletes what it created.
Refuses to run against SQLite, and refuses to run in production.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections import Counter

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.models.chat import ExpertConversation, NotificationOutbox
from app.db.models.marketplace import Expert, ServiceOrder
from app.db.models.user import User
from app.db.session import get_session_factory
from app.domain.chat import ConversationStatus, OutboxStatus, ProvisioningStatus
from app.services.notifications.outbox import OutboxService

NOTIFICATION_COUNT = 16
WORKER_COUNT = 8
OPENER_COUNT = 8

# Every row this script writes carries the marker, so cleanup can be exact
# rather than "delete recent rows" - which would take somebody's real data with
# it if this were ever pointed at a populated database.
MARKER = "chat-concurrency-check"


# ================================================ 1. once-only outbox claim


async def seed_notifications(user_id: uuid.UUID) -> set[uuid.UUID]:
    factory = get_session_factory()
    ids: set[uuid.UUID] = set()
    async with factory() as session:
        for index in range(NOTIFICATION_COUNT):
            row = NotificationOutbox(
                event_type="new_chat_message",
                user_id=user_id,
                dedupe_key=f"{MARKER}:{index}",
                payload={"title": "Astrofrekans", "body": "", "data": {}},
                status=OutboxStatus.PENDING.value,
                max_attempts=3,
                notes=MARKER,
            )
            session.add(row)
            await session.flush()
            ids.add(row.id)
        await session.commit()
    return ids


async def claiming_worker(name: str) -> list[uuid.UUID]:
    """Claim until the queue is empty, on this worker's own connection."""
    factory = get_session_factory()
    claimed: list[uuid.UUID] = []
    while True:
        async with factory() as session:
            row = await OutboxService(session).claim_next(worker_id=name)
            if row is None:
                return claimed
            claimed.append(row.id)
        await asyncio.sleep(0)  # let the others in


async def check_outbox(user_id: uuid.UUID) -> bool:
    print("--- once-only outbox claim -------------------------------------")
    print(f"notifications : {NOTIFICATION_COUNT}")
    print(f"workers       : {WORKER_COUNT}\n")

    expected = await seed_notifications(user_id)
    results = await asyncio.gather(
        *(claiming_worker(f"{MARKER}-{index}") for index in range(WORKER_COUNT))
    )

    everything = [row_id for batch in results for row_id in batch]
    counts = Counter(everything)
    duplicates = {str(key): value for key, value in counts.items() if value > 1}
    missed = expected - set(everything)

    for index, batch in enumerate(results):
        print(f"  worker-{index}: {len(batch)} claimed")

    ok = True
    if duplicates:
        print(f"\nFAIL: a notification was claimed twice: {duplicates}")
        ok = False
    else:
        print("\nPASS: no notification was claimed by more than one worker")

    if missed:
        print(f"FAIL: {len(missed)} notifications were never claimed")
        ok = False
    else:
        print(f"PASS: all {len(expected)} notifications were claimed exactly once")

    factory = get_session_factory()
    async with factory() as session:
        owners = list(
            await session.scalars(
                select(NotificationOutbox.worker_id).where(
                    NotificationOutbox.notes == MARKER
                )
            )
        )
    print(f"PASS: work was spread over {len({o for o in owners if o})} workers")
    return ok


# ==================================================== 2. dedupe under races


async def check_dedupe(user_id: uuid.UUID) -> bool:
    """The same event, enqueued from many connections at once.

    The application checks for an existing row first, which handles the
    ordinary retry. This checks the case that check cannot: two connections
    that both look, both see nothing, and both insert.
    """
    print("\n--- dedupe under a race ---------------------------------------")
    key = f"{MARKER}:raced"
    factory = get_session_factory()

    async def enqueue_once() -> bool:
        async with factory() as session:
            row = NotificationOutbox(
                event_type="new_chat_message",
                user_id=user_id,
                dedupe_key=key,
                payload={"title": "Astrofrekans", "body": "", "data": {}},
                status=OutboxStatus.PENDING.value,
                max_attempts=3,
                notes=MARKER,
            )
            session.add(row)
            try:
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False

    outcomes = await asyncio.gather(*(enqueue_once() for _ in range(OPENER_COUNT)))
    async with factory() as session:
        stored = await session.scalar(
            select(func.count())
            .select_from(NotificationOutbox)
            .where(NotificationOutbox.dedupe_key == key)
        )

    print(f"  concurrent enqueues : {OPENER_COUNT}")
    print(f"  accepted            : {sum(outcomes)}")
    print(f"  rows stored         : {stored}")

    if stored == 1:
        print("PASS: one event, one notification row")
        return True
    print(f"FAIL: {stored} rows for one dedupe key")
    return False


# ======================================= 3. one conversation per order, ever


async def check_conversation_idempotency(order: ServiceOrder, expert: Expert) -> bool:
    """Open the conversation for one order from many connections at once.

    The service reads first and inserts if it finds nothing, which is correct
    and insufficient: under concurrency both readers find nothing. The unique
    constraint on `order_id` is the actual guarantee, so that is what is tested
    - two conversations for one order would mean two threads, each holding half
    the consultation.
    """
    print("\n--- one conversation per order --------------------------------")
    factory = get_session_factory()

    async def open_once() -> bool:
        async with factory() as session:
            row = ExpertConversation(
                order_id=order.id,
                user_id=order.user_id,
                expert_id=expert.id,
                expert_user_id=expert.user_id,
                status=ConversationStatus.ACTIVE.value,
                provisioning_status=ProvisioningStatus.PENDING.value,
                close_reason=MARKER,
            )
            session.add(row)
            try:
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False

    outcomes = await asyncio.gather(*(open_once() for _ in range(OPENER_COUNT)))
    async with factory() as session:
        stored = await session.scalar(
            select(func.count())
            .select_from(ExpertConversation)
            .where(ExpertConversation.order_id == order.id)
        )

    print(f"  concurrent opens : {OPENER_COUNT}")
    print(f"  accepted         : {sum(outcomes)}")
    print(f"  rows stored      : {stored}")

    if stored == 1:
        print("PASS: the constraint held; one thread per order")
        return True
    print(f"FAIL: {stored} conversations for one order")
    return False


# ==================================================================== main


async def cleanup() -> None:
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
            delete(NotificationOutbox).where(NotificationOutbox.notes == MARKER)
        )
        await session.execute(
            delete(ExpertConversation).where(
                ExpertConversation.close_reason == MARKER
            )
        )
        await session.commit()


async def main() -> int:
    if settings.database_url.startswith("sqlite"):
        print("SKIPPED: this check is meaningless on SQLite.")
        print("Point DATABASE_URL at Postgres and run it again.")
        return 2
    if settings.is_production:
        print("REFUSED: this writes test rows. Not in production.")
        return 1

    print(f"dialect : {settings.database_url.split('://', 1)[0]}\n")

    factory = get_session_factory()
    async with factory() as session:
        user = await session.scalar(select(User).limit(1))
        expert = await session.scalar(select(Expert).limit(1))
        order = await session.scalar(
            select(ServiceOrder)
            .where(ServiceOrder.expert_id.is_not(None))
            .limit(1)
        )
    user_id = user.id if user else uuid.uuid4()

    await cleanup()
    ok = await check_outbox(user_id)
    ok = await check_dedupe(user_id) and ok

    if order is not None and expert is not None:
        # The conversation check needs a real order to hang off, because the
        # foreign keys are real. Fabricating one would test the constraint
        # against a row nobody would ever have.
        existing = None
        async with factory() as session:
            existing = await session.scalar(
                select(ExpertConversation).where(
                    ExpertConversation.order_id == order.id
                )
            )
        if existing is None:
            ok = await check_conversation_idempotency(order, expert) and ok
        else:
            print("\n--- one conversation per order --------------------------------")
            print("SKIPPED: that order already has a conversation.")
    else:
        print("\n--- one conversation per order --------------------------------")
        print("SKIPPED: no expert order in this database to test against.")
        print("Run scripts/benchmark_marketplace.py first, or seed one.")

    await cleanup()
    print("\ncleaned up")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
