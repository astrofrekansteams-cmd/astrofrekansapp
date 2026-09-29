"""Call pushes are claimed for seconds, not minutes.

A ring lasts CALL_RING_TIMEOUT_SECONDS (60). B9's generic outbox lease is 120
seconds: a worker that died holding an incoming call would be taken over only
after the call was MISSED. Call events therefore take CALL_PUSH_LEASE_SECONDS
(15), with every provider operation bounded by CALL_PUSH_SEND_TIMEOUT_SECONDS
(8) so a live worker never loses its claim mid-send:

    send timeout + margin  <=  call push lease  <  ring timeout

Time is moved by shifting every stored timestamp back, which is exactly what
"t seconds later" means to the claim and expiry queries.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings, settings
from app.db.models.chat import NotificationDelivery, NotificationOutbox
from app.domain.chat import PushEvent
from app.services.notifications.apns import FakeApnsProvider
from app.services.notifications.call_delivery import CallPushSender
from app.services.notifications.outbox import OutboxService
from tests.test_call_delivery import (  # noqa: F401 - fixtures
    VOIP_TOKEN,
    add_devices,
    enqueue_call,
    firebase,
    load,
    user,
    voip,
)
from tests.test_call_delivery_reliability import WorkerDied, worker_pass


async def advance(session_factory, seconds: float) -> None:
    """`seconds` pass: every lease and expiry moves that much closer."""
    delta = timedelta(seconds=seconds)
    async with session_factory() as session:
        for row in await session.scalars(select(NotificationOutbox)):
            if row.lease_expires_at is not None:
                row.lease_expires_at -= delta
            if row.expires_at is not None:
                row.expires_at -= delta
        for delivery in await session.scalars(select(NotificationDelivery)):
            if delivery.lease_until is not None:
                delivery.lease_until -= delta
        await session.commit()


async def worker_a_claims_and_dies(session_factory, firebase, voip, monkeypatch) -> datetime:
    original = CallPushSender._send
    state = {"died": False}

    async def dies_once(self, *args, **kwargs):
        if not state["died"]:
            state["died"] = True
            raise WorkerDied()
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(CallPushSender, "_send", dies_once)
    claimed_at = datetime.now(UTC)
    with pytest.raises(WorkerDied):
        await worker_pass(session_factory, firebase, voip)
    return claimed_at


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


async def test_a_crashed_ring_is_recovered_while_the_phone_can_still_ring(
    session_factory, firebase, voip, user, monkeypatch
):
    assert (settings.call_ring_timeout_seconds, settings.call_push_lease_seconds) == (60, 15)
    await add_devices(session_factory, user, voip=[VOIP_TOKEN])
    await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)

    claimed_at = await worker_a_claims_and_dies(session_factory, firebase, voip, monkeypatch)
    [row] = await load(session_factory, NotificationOutbox)
    lease = (_aware(row.lease_expires_at) - claimed_at).total_seconds()
    assert 14 <= lease <= 16  # the call lease, not B9's 120 s
    [delivery] = await load(session_factory, NotificationDelivery)
    assert _aware(delivery.lease_until) == _aware(row.lease_expires_at)

    await advance(session_factory, 10)  # t = 10: A's lease is still live
    assert await worker_pass(session_factory, firebase, voip) is None
    assert voip.requests == []

    await advance(session_factory, 6)  # t = 16: lapsed; the ring is not
    await worker_pass(session_factory, firebase, voip)

    [delivery] = await load(session_factory, NotificationDelivery)
    assert (delivery.status, delivery.attempts) == ("delivered", 2)
    assert len(voip.requests) == 1
    [row] = await load(session_factory, NotificationOutbox)
    assert row.status == "sent"
    assert _aware(row.expires_at) > datetime.now(UTC)  # still ringing when delivered


async def test_a_lease_that_lapses_after_the_ring_is_skipped(
    session_factory, firebase, voip, user, monkeypatch
):
    await add_devices(session_factory, user, voip=[VOIP_TOKEN])
    await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)
    await worker_a_claims_and_dies(session_factory, firebase, voip, monkeypatch)

    await advance(session_factory, 61)  # past the ring
    await worker_pass(session_factory, firebase, voip)

    assert voip.requests == []
    [row] = await load(session_factory, NotificationOutbox)
    assert (row.status, row.notes) == ("skipped", "skipped_expired")
    [delivery] = await load(session_factory, NotificationDelivery)
    assert (delivery.status, delivery.error_code, delivery.attempts) == ("skipped", "skipped_expired", 1)


class SlowApns(FakeApnsProvider):
    def __init__(self, delay: float) -> None:
        super().__init__()
        self.delay = delay
        self.entered = asyncio.Event()

    async def send_voip(self, *args, **kwargs):
        self.entered.set()
        await asyncio.sleep(self.delay)
        return await super().send_voip(*args, **kwargs)


async def test_a_worker_still_talking_to_the_provider_keeps_its_claim(
    session_factory, firebase, voip, user
):
    await add_devices(session_factory, user, voip=[VOIP_TOKEN])
    outbox_id, _ = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)
    slow = SlowApns(delay=0.3)

    first = asyncio.create_task(worker_pass(session_factory, firebase, slow))
    await slow.entered.wait()  # A is inside the provider call

    assert await worker_pass(session_factory, firebase, slow) is None
    async with session_factory() as session:
        now = datetime.now(UTC)
        assert await CallPushSender(session, firebase, slow)._claim(outbox_id, now, now) == []

    await first
    [delivery] = await load(session_factory, NotificationDelivery)
    assert (delivery.status, delivery.attempts) == ("delivered", 1)
    assert len(slow.requests) == 1


async def test_a_hung_provider_is_cut_off_inside_the_lease(
    session_factory, firebase, voip, user, monkeypatch
):
    monkeypatch.setattr(settings, "call_push_send_timeout_seconds", 0.05)
    await add_devices(session_factory, user, voip=[VOIP_TOKEN])
    outbox_id, _ = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)

    started = datetime.now(UTC)
    await worker_pass(session_factory, firebase, SlowApns(delay=2.0))
    assert (datetime.now(UTC) - started).total_seconds() < 1.5

    [delivery] = await load(session_factory, NotificationDelivery)
    assert (delivery.status, delivery.error_code) == ("pending", "provider_timeout")
    [row] = await load(session_factory, NotificationOutbox)
    assert row.status == "pending"  # retried at once, not after a lease

    await worker_pass(session_factory, firebase, voip)
    [delivery] = await load(session_factory, NotificationDelivery)
    assert (delivery.status, delivery.attempts) == ("delivered", 2)


async def test_generic_notifications_keep_the_b9_lease(session_factory, user):
    async with session_factory() as session:
        await OutboxService(session).enqueue_chat_message(
            recipient_user_id=user.id, conversation_id=uuid.uuid4(), message_id="m-1"
        )
        await session.commit()
    async with session_factory() as session:
        claimed_at = datetime.now(UTC)
        row = await OutboxService(session).claim_next(worker_id="w")
        lease = (_aware(row.lease_expires_at) - claimed_at).total_seconds()
    assert settings.push_outbox_lease_seconds - 1 <= lease <= settings.push_outbox_lease_seconds + 1


# ================================================================ config


def test_the_defaults_satisfy_the_invariant():
    assert settings.apns_timeout_seconds <= settings.call_push_send_timeout_seconds
    assert settings.call_push_send_timeout_seconds + 2 <= settings.call_push_lease_seconds
    assert settings.call_push_lease_seconds < settings.call_ring_timeout_seconds


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"call_push_lease_seconds": 60}, "shorter than CALL_RING_TIMEOUT_SECONDS"),
        ({"call_push_lease_seconds": 120}, "shorter than CALL_RING_TIMEOUT_SECONDS"),
        ({"call_push_lease_seconds": 9}, "must exceed CALL_PUSH_SEND_TIMEOUT_SECONDS"),
        ({"call_push_send_timeout_seconds": 14}, "must exceed CALL_PUSH_SEND_TIMEOUT_SECONDS"),
        ({"apns_timeout_seconds": 9}, "APNS_TIMEOUT_SECONDS must not exceed"),
        ({"call_ring_timeout_seconds": 15}, "shorter than CALL_RING_TIMEOUT_SECONDS"),
    ],
)
def test_an_unsafe_timing_is_refused_at_startup(overrides, message):
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **overrides)


def test_a_consistent_custom_timing_boots():
    custom = Settings(
        _env_file=None,
        call_ring_timeout_seconds=45,
        call_push_lease_seconds=12,
        call_push_send_timeout_seconds=6,
        apns_timeout_seconds=5,
    )
    assert custom.call_push_lease_seconds == 12
