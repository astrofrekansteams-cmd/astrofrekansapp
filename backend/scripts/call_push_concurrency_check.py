"""Prove call push delivery happens once per device, against a real Postgres.

    python -m scripts.call_push_concurrency_check

SQLite serialises writers and has no ``SKIP LOCKED``; here, from many
connections at once:

1. **The same call event enqueued 10 times concurrently** -> one outbox row.
2. **8 workers draining 6 call events** for a user with two Android phones and
   an iPhone (PushKit VoIP) -> every device rung exactly once per event, one
   delivery row per (event, device).
3. **Two workers delivering the same row at once** (a lost lease) -> still
   once per device: the per-device ledger's unique pair holds.
4. **A worker dies after claiming a delivery** -> once the lease lapses a
   second worker claims the *same* delivery row: `attempts=2`, delivered, no
   second row.
5. **Two workers recover the same stale delivery at once** -> exactly one
   claims it (`FOR UPDATE SKIP LOCKED` + the lease).
6. **Short call lease, real time** -> a worker dies holding a ring; the next
   worker takes it over as soon as the call push lease lapses - measured on
   the wall clock, well inside the ring - and delivers it.

Fake FCM and fake APNs (nothing leaves the machine). Refuses to run when the
queue holds anybody else's pending rows, refuses SQLite and production, and
deletes exactly its own rows.
"""

from __future__ import annotations

import asyncio
import sys
import time
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update

from app.core.config import settings
from app.db.models.chat import NotificationDelivery, NotificationOutbox
from app.db.models.user import User
from app.db.session import get_session_factory
from app.domain.chat import DevicePlatform, OutboxStatus, PushEvent
from app.services.firebase.factory import fake_providers
from app.services.notifications.apns import FakeApnsProvider
from app.services.notifications.call_delivery import CallPushSender, call_event_fields, route
from app.services.notifications.devices import DeviceService
from app.services.notifications.outbox import OutboxService
from app.services.notifications.sender import NotificationSender

MARKER = "call-push-check"
ANDROID = [f"{MARKER}-android-{i}-" + "x" * 32 for i in range(2)]
VOIP = "ef" * 32
WORKERS = 8
EVENTS = 6


async def make_user(factory) -> uuid.UUID:
    async with factory() as session:
        user = User(email=f"{MARKER}-{uuid.uuid4().hex[:8]}@example.com", password_hash=None,
                    is_active=True, is_email_verified=True)
        session.add(user)
        await session.flush()
        devices = DeviceService(session)
        for token in ANDROID:
            await devices.register(user, token=token, platform=DevicePlatform.ANDROID)
        await devices.register_voip(user, token=VOIP, environment=settings.apns_environment)
        await session.commit()
        return user.id


async def enqueue(factory, user_id, call_id, *, key_suffix="") -> bool:
    data, expires_at = call_event_fields(
        PushEvent.INCOMING_CALL, call_id=call_id, call_type="audio", ringing_at=datetime.now(UTC)
    )
    async with factory() as session:
        row = await OutboxService(session).enqueue(
            event=PushEvent.INCOMING_CALL,
            user_id=user_id,
            dedupe_key=f"incoming_call:{call_id}:{user_id}{key_suffix}",
            data=data,
            variant="audio",
            expires_at=expires_at,
        )
        await session.commit()
        return row is not None


async def check_enqueue_dedupe(factory, user_id) -> bool:
    print("--- the same call event enqueued 10 times at once --------------")
    call_id = str(uuid.uuid4())
    accepted = await asyncio.gather(*(enqueue(factory, user_id, call_id) for _ in range(10)))
    async with factory() as session:
        rows = await session.scalar(
            select(func.count()).select_from(NotificationOutbox).where(
                NotificationOutbox.dedupe_key.like(f"incoming_call:{call_id}:%")
            )
        )
    print(f"  accepted: {sum(accepted)}, rows: {rows}")
    ok = rows == 1 and sum(accepted) == 1
    print("PASS: one event, one outbox row" if ok else "FAIL")
    return ok


async def drain(factory, firebase, voip) -> None:
    async def worker(index: int) -> None:
        while True:
            async with factory() as session:
                outbox = OutboxService(session)
                row = await outbox.claim_next(worker_id=f"{MARKER}-{index}")
                if row is None:
                    return
                await NotificationSender(session, firebase, voip).deliver(row)

    await asyncio.gather(*(worker(i) for i in range(WORKERS)))


async def check_workers(factory, user_id, firebase, voip) -> bool:
    print("\n--- 8 workers, 6 call events, three devices ---------------------")
    for _ in range(EVENTS - 1):
        await enqueue(factory, user_id, str(uuid.uuid4()))
    await drain(factory, firebase, voip)

    async with factory() as session:
        rows = list(await session.scalars(
            select(NotificationOutbox).where(NotificationOutbox.user_id == user_id)
        ))
        deliveries = list(await session.scalars(
            select(NotificationDelivery).where(
                NotificationDelivery.outbox_id.in_([row.id for row in rows])
            )
        ))
    per_target = Counter((d.outbox_id, d.device_id) for d in deliveries)
    fcm = Counter(
        (message.data["call_id"], token) for tokens, message in firebase.push.data_sent for token in tokens
    )
    apns = Counter(request["payload"]["call_id"] for request in voip.requests)
    print(f"  outbox rows: {Counter(row.status for row in rows)}")
    print(f"  delivery rows: {len(deliveries)}, max per target: {max(per_target.values(), default=0)}")
    print(f"  FCM sends per (call, device): max {max(fcm.values(), default=0)}, total {sum(fcm.values())}")
    print(f"  APNs sends per call: max {max(apns.values(), default=0)}, total {sum(apns.values())}")
    ok = (
        len(rows) == EVENTS
        and all(row.status == "sent" for row in rows)
        and len(deliveries) == EVENTS * 3
        and max(per_target.values()) == 1
        and sum(fcm.values()) == EVENTS * 2 and max(fcm.values()) == 1
        and sum(apns.values()) == EVENTS and max(apns.values()) == 1
    )
    print("PASS: every device rung exactly once per event" if ok else "FAIL")
    return ok


async def check_lost_lease(factory, user_id, firebase, voip) -> bool:
    print("\n--- two workers deliver the same row at once --------------------")
    call_id = str(uuid.uuid4())
    await enqueue(factory, user_id, call_id)
    async with factory() as session:
        row_id = await session.scalar(
            select(NotificationOutbox.id).where(NotificationOutbox.dedupe_key.like(f"incoming_call:{call_id}:%"))
        )
        row = await session.get(NotificationOutbox, row_id)
        row.status = OutboxStatus.SENDING.value
        await session.commit()
    before_fcm, before_apns = len(firebase.push.data_sent), len(voip.requests)

    async def deliver() -> None:
        async with factory() as session:
            mine = await session.get(NotificationOutbox, row_id)
            await NotificationSender(session, firebase, voip).deliver(mine)

    await asyncio.gather(deliver(), deliver())
    fcm_tokens = [t for tokens, m in firebase.push.data_sent[before_fcm:] for t in tokens if m.data["call_id"] == call_id]
    apns = [r for r in voip.requests[before_apns:] if r["payload"]["call_id"] == call_id]
    async with factory() as session:
        deliveries = await session.scalar(
            select(func.count()).select_from(NotificationDelivery).where(NotificationDelivery.outbox_id == row_id)
        )
    print(f"  FCM sends: {Counter(fcm_tokens)}, APNs sends: {len(apns)}, delivery rows: {deliveries}")
    ok = sorted(fcm_tokens) == sorted(ANDROID) and len(apns) == 1 and deliveries == 3
    print("PASS: once per device despite two workers" if ok else "FAIL")
    return ok


async def voip_only_user(factory) -> uuid.UUID:
    async with factory() as session:
        user = User(email=f"{MARKER}-{uuid.uuid4().hex[:8]}@example.com", password_hash=None,
                    is_active=True, is_email_verified=True)
        session.add(user)
        await session.flush()
        await DeviceService(session).register_voip(
            user, token=uuid.uuid4().hex + uuid.uuid4().hex, environment=settings.apns_environment
        )
        await session.commit()
        return user.id


async def lapse(factory, row_id) -> None:
    past = datetime.now(UTC) - timedelta(seconds=1)
    async with factory() as session:
        await session.execute(
            update(NotificationOutbox).where(NotificationOutbox.id == row_id).values(lease_expires_at=past)
        )
        await session.execute(
            update(NotificationDelivery).where(NotificationDelivery.outbox_id == row_id).values(lease_until=past)
        )
        await session.commit()


async def claim_and_die(factory, firebase, voip, row_id) -> int:
    """A worker's claim step, then nothing: it died before sending."""
    async with factory() as session:
        row = await session.get(NotificationOutbox, row_id)
        sender = CallPushSender(session, firebase, voip)
        devices = await sender.devices.enabled_devices(row.user_id)
        targets = [(d, t) for d in devices if (t := route(PushEvent(row.event_type), d, user_has_voip=True))]
        await sender._ensure(row_id, targets)
        now = datetime.now(UTC)
        # As the real pipeline does: the delivery lease is the row's lease.
        lease_until = row.lease_expires_at or now + timedelta(seconds=settings.call_push_lease_seconds)
        claims = await sender._claim(row_id, now, lease_until)
        return len(claims)


async def check_stale_lease(factory, firebase, voip) -> bool:
    print("\n--- worker A claims and dies; worker B takes over the lease -------")
    user_id = await voip_only_user(factory)
    call_id = str(uuid.uuid4())
    await enqueue(factory, user_id, call_id)
    async with factory() as session:
        row = await OutboxService(session).claim_next(worker_id=f"{MARKER}-A")
        row_id = row.id
    claimed_by_a = await claim_and_die(factory, firebase, voip, row_id)
    before = len(voip.requests)

    await lapse(factory, row_id)
    async with factory() as session:
        outbox = OutboxService(session)
        await outbox.recover_stale()
        row = await outbox.claim_next(worker_id=f"{MARKER}-B")
        await NotificationSender(session, firebase, voip).deliver(row)

    async with factory() as session:
        deliveries = list(await session.scalars(
            select(NotificationDelivery).where(NotificationDelivery.outbox_id == row_id)
        ))
        final = await session.get(NotificationOutbox, row_id)
    sends = [r for r in voip.requests[before:] if r["payload"]["call_id"] == call_id]
    print(f"  A claimed: {claimed_by_a}; delivery rows: {len(deliveries)}; "
          f"{[(d.status, d.attempts) for d in deliveries]}; APNs sends by B: {len(sends)}; row: {final.status}")
    ok = (
        claimed_by_a == 1
        and len(deliveries) == 1
        and (deliveries[0].status, deliveries[0].attempts) == ("delivered", 2)
        and len(sends) == 1
        and final.status == "sent"
    )
    print("PASS: same logical delivery, attempts=2, delivered" if ok else "FAIL")
    return ok


async def check_concurrent_recovery(factory, firebase, voip) -> bool:
    print("\n--- two workers recover the same stale delivery at once ---------")
    user_id = await voip_only_user(factory)
    call_id = str(uuid.uuid4())
    await enqueue(factory, user_id, call_id)
    async with factory() as session:
        row_id = await session.scalar(
            select(NotificationOutbox.id).where(NotificationOutbox.dedupe_key.like(f"incoming_call:{call_id}:%"))
        )
    await claim_and_die(factory, firebase, voip, row_id)
    await lapse(factory, row_id)

    async def reclaim() -> int:
        async with factory() as session:
            now = datetime.now(UTC)
            sender = CallPushSender(session, firebase, voip)
            return len(await sender._claim(row_id, now, now + timedelta(seconds=60)))

    results = []
    for _ in range(5):  # several rounds: the race is not guaranteed to overlap once
        await lapse(factory, row_id)
        results.append(await asyncio.gather(*(reclaim() for _ in range(6))))
    async with factory() as session:
        attempts = await session.scalar(
            select(NotificationDelivery.attempts).where(NotificationDelivery.outbox_id == row_id)
        )
    print(f"  claims per round (6 workers): {[sum(r) for r in results]}; attempts: {attempts}")
    ok = all(sum(r) == 1 for r in results) and attempts == 1 + len(results)
    print("PASS: one claim per stale lease" if ok else "FAIL")
    return ok


async def check_fast_lease(factory, firebase, voip) -> bool:
    print("\n--- short call lease: a crashed ring recovered while ringing ------")
    # In-process only, and consistent with the startup invariant
    # (send timeout + 2 <= lease < ring): real waiting, short numbers.
    saved = (settings.call_ring_timeout_seconds, settings.call_push_lease_seconds,
             settings.call_push_send_timeout_seconds)
    settings.call_ring_timeout_seconds, settings.call_push_lease_seconds = 10, 3
    settings.call_push_send_timeout_seconds = 1.0
    try:
        # A clean queue: earlier scenarios leave rows the claim would take first.
        await cleanup(factory)
        user_id = await voip_only_user(factory)
        call_id = str(uuid.uuid4())
        await enqueue(factory, user_id, call_id)
        async with factory() as session:
            row = await OutboxService(session).claim_next(worker_id=f"{MARKER}-A")
            row_id, expires_at = row.id, row.expires_at
            lease = (row.lease_expires_at - datetime.now(UTC)).total_seconds()
        await claim_and_die(factory, firebase, voip, row_id)
        died = time.monotonic()
        before = len(voip.requests)

        recovered_after = None
        while time.monotonic() - died < settings.call_ring_timeout_seconds:
            async with factory() as session:
                outbox = OutboxService(session)
                await outbox.recover_stale()
                taken = await outbox.claim_next(worker_id=f"{MARKER}-B")
                if taken is not None:
                    recovered_after = time.monotonic() - died
                    await NotificationSender(session, firebase, voip).deliver(taken)
                    break
            await asyncio.sleep(0.25)

        async with factory() as session:
            delivery = await session.scalar(
                select(NotificationDelivery).where(NotificationDelivery.outbox_id == row_id)
            )
            final = await session.get(NotificationOutbox, row_id)
        sends = [r for r in voip.requests[before:] if r["payload"]["call_id"] == call_id]
        print(f"  lease: {lease:.1f}s; recovered after {recovered_after and round(recovered_after, 2)}s "
              f"(ring {settings.call_ring_timeout_seconds}s); delivery: {(delivery.status, delivery.attempts)}; "
              f"sends: {len(sends)}; row: {final.status}")
        ok = (
            recovered_after is not None
            and settings.call_push_lease_seconds - 1 <= recovered_after < settings.call_ring_timeout_seconds
            and (delivery.status, delivery.attempts) == ("delivered", 2)
            and len(sends) == 1
            and final.status == "sent"
            and expires_at > datetime.now(UTC)
        )
        print("PASS: recovered inside the ring and delivered" if ok else "FAIL")
        return ok
    finally:
        (settings.call_ring_timeout_seconds, settings.call_push_lease_seconds,
         settings.call_push_send_timeout_seconds) = saved


async def cleanup(factory) -> None:
    async with factory() as session:
        users = select(User.id).where(User.email.like(f"{MARKER}-%"))
        await session.execute(delete(NotificationOutbox).where(NotificationOutbox.user_id.in_(users)))
        await session.execute(delete(User).where(User.email.like(f"{MARKER}-%")))
        await session.commit()


async def main() -> int:
    if settings.database_url.startswith("sqlite"):
        print("SKIPPED: meaningless on SQLite.")
        return 2
    if settings.is_production:
        print("REFUSED: writes test rows.")
        return 1
    factory = get_session_factory()
    await cleanup(factory)
    async with factory() as session:
        foreign = await session.scalar(
            select(func.count()).select_from(NotificationOutbox).where(
                NotificationOutbox.status == OutboxStatus.PENDING.value
            )
        )
    if foreign:
        print(f"REFUSED: {foreign} pending outbox rows belong to somebody else.")
        return 1

    firebase = fake_providers()
    voip = FakeApnsProvider()
    print(f"dialect : {settings.database_url.split('://', 1)[0]}\n")
    ok = True
    try:
        user_id = await make_user(factory)
        ok &= await check_enqueue_dedupe(factory, user_id)
        ok &= await check_workers(factory, user_id, firebase, voip)
        ok &= await check_lost_lease(factory, user_id, firebase, voip)
        ok &= await check_stale_lease(factory, firebase, voip)
        ok &= await check_concurrent_recovery(factory, firebase, voip)
        ok &= await check_fast_lease(factory, firebase, voip)
    finally:
        await cleanup(factory)
        print("\ncleaned up")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
