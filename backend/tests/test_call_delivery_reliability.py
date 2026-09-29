"""Call delivery is at least once: a dead worker never silently loses a ring.

* A delivery left `sending` by a worker that died is claimed again when its
  lease lapses - same logical delivery row, `attempts` counts the sends, the
  same `apns-id`, the same `event_version` for the device to deduplicate on.
* Transient failures retry; permanent ones do not; an expired ring is skipped.
* A live lease is never claimed twice.
* The worker runs with Firebase **or** APNs, and idles only with neither.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.db.models.chat import NotificationDelivery, NotificationOutbox
from app.domain.chat import PushEvent
from app.services.notifications.call_delivery import CallPushSender
from app.services.notifications.outbox import OutboxService
from app.services.notifications.sender import NotificationSender
from app.workers.notification_worker import CALL_EVENT_TYPES, IDLE, claim_scope
from tests.test_call_delivery import (  # noqa: F401 - fixtures
    ANDROID_TOKEN,
    VOIP_TOKEN,
    add_devices,
    deliver,
    enqueue_call,
    firebase,
    load,
    user,
    voip,
)


class WorkerDied(Exception):
    pass


async def lapse_leases(session_factory) -> None:
    """Time passes: every claim - row and delivery - is now stale."""
    past = datetime.now(UTC) - timedelta(seconds=1)
    async with session_factory() as session:
        await session.execute(update(NotificationOutbox).values(lease_expires_at=past))
        await session.execute(update(NotificationDelivery).values(lease_until=past))
        await session.commit()


async def worker_pass(session_factory, firebase, voip, *, event_types=None):
    """One iteration of the notification worker: recover, claim, deliver."""
    async with session_factory() as session:
        outbox = OutboxService(session)
        await outbox.recover_stale()
        row = await outbox.claim_next(worker_id=f"w-{uuid.uuid4().hex[:6]}", event_types=event_types)
        if row is None:
            return None
        await NotificationSender(session, firebase, voip).deliver(row)
        return row.id


async def worker_that_dies_in(session_factory, firebase, voip, monkeypatch, step: str) -> None:
    original = getattr(CallPushSender, step)
    calls = {"n": 0}

    async def dies_once(self, *args, **kwargs):
        # `_send`: dies after the claim, before any provider call.
        # `_record`: the providers have accepted; dies before the DB knows.
        if calls["n"] == 0:
            calls["n"] += 1
            raise WorkerDied()
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(CallPushSender, step, dies_once)
    with pytest.raises(WorkerDied):
        await worker_pass(session_factory, firebase, voip)


async def test_a_worker_that_dies_before_sending_is_retried_after_its_lease(
    session_factory, firebase, voip, user, monkeypatch
):
    await add_devices(session_factory, user, voip=[VOIP_TOKEN])
    await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)

    await worker_that_dies_in(session_factory, firebase, voip, monkeypatch, "_send")
    [delivery] = await load(session_factory, NotificationDelivery)
    assert delivery.status == "sending" and delivery.attempts == 1 and delivery.lease_until
    assert voip.requests == []

    # Before the lease lapses nobody may take it.
    assert await worker_pass(session_factory, firebase, voip) is None

    await lapse_leases(session_factory)
    await worker_pass(session_factory, firebase, voip)

    [delivery] = await load(session_factory, NotificationDelivery)
    assert delivery.status == "delivered" and delivery.attempts == 2
    assert len(voip.requests) == 1
    [row] = await load(session_factory, NotificationOutbox)
    assert row.status == "sent"


async def test_a_worker_that_dies_after_the_provider_accepted_resends_the_same_delivery(
    session_factory, firebase, voip, user, monkeypatch
):
    await add_devices(session_factory, user, voip=[VOIP_TOKEN], android=[ANDROID_TOKEN])
    await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)

    await worker_that_dies_in(session_factory, firebase, voip, monkeypatch, "_record")
    assert len(voip.requests) == 1 and len(firebase.push.data_sent) == 1  # really sent
    assert {d.status for d in await load(session_factory, NotificationDelivery)} == {"sending"}

    await lapse_leases(session_factory)
    await worker_pass(session_factory, firebase, voip)

    deliveries = await load(session_factory, NotificationDelivery)
    assert len(deliveries) == 2  # one logical delivery per device, no more
    assert {(d.status, d.attempts) for d in deliveries} == {("delivered", 2)}
    # At least once: the duplicate is visible to the device as the same event.
    first, second = voip.requests
    assert first["headers"]["apns-id"] == second["headers"]["apns-id"]
    assert first["payload"] == second["payload"]
    (_, a), (_, b) = firebase.push.data_sent
    assert a.data["event_version"] == b.data["event_version"] and a.data["call_id"] == b.data["call_id"]


async def test_a_live_lease_is_not_claimed_twice(session_factory, firebase, voip, user, monkeypatch):
    await add_devices(session_factory, user, voip=[VOIP_TOKEN])
    outbox_id, _ = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)
    await worker_that_dies_in(session_factory, firebase, voip, monkeypatch, "_send")

    # A second worker holding the same row while the first's lease is live
    # (its own row lease lapsed early) claims nothing and leaves the row alone.
    async with session_factory() as session:
        row = await session.get(NotificationOutbox, outbox_id)
        await CallPushSender(session, firebase, voip).deliver(row)
    [delivery] = await load(session_factory, NotificationDelivery)
    assert delivery.status == "sending" and delivery.attempts == 1
    assert voip.requests == []
    [row] = await load(session_factory, NotificationOutbox)
    assert row.status == "sending"


async def test_a_transient_fcm_failure_is_retried(session_factory, firebase, voip, user):
    await add_devices(session_factory, user, android=[ANDROID_TOKEN])
    outbox_id, _ = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)
    firebase.push.transient_tokens.add(ANDROID_TOKEN)

    await deliver(session_factory, firebase, voip, outbox_id)
    [delivery] = await load(session_factory, NotificationDelivery)
    assert (delivery.status, delivery.error_code, delivery.attempts) == ("pending", "fcm_transient", 1)
    [row] = await load(session_factory, NotificationOutbox)
    assert row.status == "pending"

    firebase.push.transient_tokens.clear()
    await deliver(session_factory, firebase, voip, outbox_id)
    [delivery] = await load(session_factory, NotificationDelivery)
    assert (delivery.status, delivery.attempts) == ("delivered", 2)


async def test_a_ring_that_expires_before_its_retry_is_skipped(session_factory, firebase, voip, user):
    await add_devices(session_factory, user, voip=[VOIP_TOKEN])
    voip.reasons[VOIP_TOKEN] = "ServiceUnavailable"
    outbox_id, _ = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)
    await deliver(session_factory, firebase, voip, outbox_id)
    assert len(voip.requests) == 1

    async with session_factory() as session:
        await session.execute(
            update(NotificationOutbox).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
    del voip.reasons[VOIP_TOKEN]
    await deliver(session_factory, firebase, voip, outbox_id)

    assert len(voip.requests) == 1  # no late ring
    [row] = await load(session_factory, NotificationOutbox)
    assert row.status == "skipped" and row.notes == "skipped_expired"
    [delivery] = await load(session_factory, NotificationDelivery)
    assert (delivery.status, delivery.error_code) == ("skipped", "skipped_expired")


async def test_a_permanent_failure_is_not_retried(session_factory, firebase, voip, user):
    await add_devices(session_factory, user, voip=[VOIP_TOKEN])
    voip.reasons[VOIP_TOKEN] = "BadDeviceToken"
    outbox_id, _ = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)
    await deliver(session_factory, firebase, voip, outbox_id)
    await deliver(session_factory, firebase, voip, outbox_id)
    assert len(voip.requests) == 1
    [delivery] = await load(session_factory, NotificationDelivery)
    assert (delivery.status, delivery.attempts) == ("failed", 1)


# ============================================================ worker startup


def test_claim_scope_follows_the_configured_transports():
    assert claim_scope(fcm_ready=True, voip_ready=True) is None
    assert claim_scope(fcm_ready=True, voip_ready=False) is None
    assert claim_scope(fcm_ready=False, voip_ready=True) == CALL_EVENT_TYPES
    assert claim_scope(fcm_ready=False, voip_ready=False) == IDLE


async def test_apns_without_firebase_still_rings_ios(session_factory, firebase, voip, user):
    firebase.push.unavailable = True  # no Firebase credentials
    await add_devices(session_factory, user, android=[ANDROID_TOKEN], voip=[VOIP_TOKEN])
    async with session_factory() as session:
        chat = await OutboxService(session).enqueue_chat_message(
            recipient_user_id=user.id, conversation_id=uuid.uuid4(), message_id="m-1"
        )
        await session.commit()
        chat_id = chat.id
    call_id, _ = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)

    scope = claim_scope(fcm_ready=False, voip_ready=voip.available)
    assert await worker_pass(session_factory, firebase, voip, event_types=scope) == call_id
    assert await worker_pass(session_factory, firebase, voip, event_types=scope) is None

    assert len(voip.requests) == 1
    by_transport = {d.transport: (d.status, d.error_code) for d in await load(session_factory, NotificationDelivery)}
    assert by_transport == {
        "apns_voip": ("delivered", None),
        "fcm_call_data": ("skipped", "provider_not_configured"),
    }
    [chat_row] = await load(session_factory, NotificationOutbox, NotificationOutbox.id == chat_id)
    assert chat_row.status == "pending"  # ordinary notifications wait for Firebase


async def test_firebase_without_apns_keeps_android_and_ordinary_pushes(session_factory, firebase, voip, user):
    voip.unavailable = True  # no APNs credentials
    await add_devices(session_factory, user, android=[ANDROID_TOKEN], voip=[VOIP_TOKEN])
    async with session_factory() as session:
        await OutboxService(session).enqueue_chat_message(
            recipient_user_id=user.id, conversation_id=uuid.uuid4(), message_id="m-1"
        )
        await session.commit()
    await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)

    scope = claim_scope(fcm_ready=True, voip_ready=False)
    while await worker_pass(session_factory, firebase, voip, event_types=scope) is not None:
        pass

    assert len(firebase.push.sent) == 1 and len(firebase.push.data_sent) == 1
    by_transport = {d.transport: (d.status, d.error_code) for d in await load(session_factory, NotificationDelivery)}
    assert by_transport == {
        "apns_voip": ("skipped", "provider_not_configured"),
        "fcm_call_data": ("delivered", None),
    }
    statuses = sorted(r.status for r in await load(session_factory, NotificationOutbox))
    assert statuses == ["sent", "sent"]


async def test_with_neither_the_queue_is_untouched(session_factory, firebase, voip, user):
    await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)
    assert claim_scope(fcm_ready=False, voip_ready=False) == IDLE
    [row] = await load(session_factory, NotificationOutbox)
    assert row.status == "pending" and row.attempts == 0
    async with session_factory() as session:
        assert list(await session.scalars(select(NotificationDelivery))) == []
