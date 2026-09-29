"""Prove the call invariants that only a real database can settle.

    python -m scripts.call_concurrency_check

The unit suite runs on SQLite, which serialises writers and ignores
`FOR UPDATE`. That proves the state machine and nothing about races, so the
races are run here, on Postgres, from many connections at once:

1. **Ten simultaneous "start call" taps -> one session.** The partial unique
   index `uq_call_sessions_live_order` is the guarantee; a SELECT-then-INSERT
   in the application would let two through.
2. **The same webhook delivered eight times at once -> one transition.** The
   `(provider, event_id)` unique constraint decides.
3. **Ten simultaneous join-token requests -> one session, ten tokens.** The row
   lock serialises them; none creates a second room or a second participant.

Uses the fake provider - the properties are the database's, not LiveKit's -
with LiveKit's real token and webhook-signing code. Writes its own throwaway
users, expert, order and appointment, and deletes exactly those.

Refuses to run against SQLite, and refuses to run in production.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from datetime import time as clock_time

from sqlalchemy import delete, func, select

from app.core.config import settings
from app.db.models.calls import CallParticipant, CallProviderEvent, CallSession
from app.db.models.chat import NotificationOutbox
from app.db.models.marketplace import (
    Appointment,
    Expert,
    ExpertAvailability,
    ExpertService,
    ServiceOrder,
)
from app.db.models.service import ServiceDefinition
from app.db.models.user import User, UserProfile
from app.db.session import get_session_factory
from app.domain.calls import CallType
from app.domain.marketplace import (
    AppointmentStatus,
    DeliveryType,
    ExpertStatus,
    FulfillmentMode,
    OrderStatus,
    PaymentStatus,
)
from app.services.calls.fake_provider import FakeRealtimeCommunicationProvider
from app.services.calls.service import CallService

MARKER = "call-concurrency-check"
OPENERS = 10
DUPLICATES = 8
JOINERS = 10


async def build_scenario(marker: str = MARKER) -> dict:
    """A user, an expert, a paid video order with an appointment happening now."""
    factory = get_session_factory()
    stamp = uuid.uuid4().hex[:8]
    async with factory() as session:
        definition = await session.scalar(
            select(ServiceDefinition)
            .where(
                ServiceDefinition.supports_video.is_(True),
                ServiceDefinition.supports_appointment.is_(True),
                ServiceDefinition.active.is_(True),
            )
            .limit(1)
        )
        if definition is None:
            raise SystemExit("No video-capable service. Run scripts/seed_services.py.")

        user = User(
            email=f"{marker}-user-{stamp}@example.com",
            password_hash=None,
            is_active=True,
            is_email_verified=True,
        )
        expert_user = User(
            email=f"{marker}-expert-{stamp}@example.com",
            password_hash=None,
            is_active=True,
            is_email_verified=True,
        )
        session.add_all([user, expert_user])
        await session.flush()
        session.add_all(
            [
                UserProfile(user_id=user.id, name="Check User"),
                UserProfile(user_id=expert_user.id, name="Check Expert"),
            ]
        )
        expert = Expert(
            user_id=expert_user.id,
            display_name=f"Check Expert {stamp}",
            languages=["tr"],
            specialties=["astrology"],
            experience_years=1,
            timezone="Europe/Istanbul",
            status=ExpertStatus.ACTIVE.value,
            verified=True,
            rating_average=0,
            rating_count=0,
        )
        session.add(expert)
        await session.flush()
        offering = ExpertService(
            expert_id=expert.id,
            service_definition_id=definition.id,
            title="Check consultation",
            delivery_type=DeliveryType.VIDEO.value,
            duration_minutes=60,
            price_minor=10000,
            currency="TRY",
            active=True,
        )
        session.add(offering)
        session.add(
            ExpertAvailability(
                expert_id=expert.id,
                weekday=0,
                start_local_time=clock_time(0, 0),
                end_local_time=clock_time(23, 0),
                timezone="Europe/Istanbul",
                active=True,
            )
        )
        await session.flush()

        now = datetime.now(UTC)
        order = ServiceOrder(
            user_id=user.id,
            service_definition_id=definition.id,
            expert_id=expert.id,
            expert_service_id=offering.id,
            fulfillment_mode=FulfillmentMode.EXPERT.value,
            delivery_type=DeliveryType.VIDEO.value,
            status=OrderStatus.CONFIRMED.value,
            # A fixture, not a payment. No production path sets PAID yet.
            payment_status=PaymentStatus.PAID.value,
            subtotal_minor=10000,
            discount_minor=0,
            total_minor=10000,
            currency="TRY",
            commission_basis_points=2000,
            platform_fee_minor=2000,
            expert_net_minor=8000,
            service_title="Check consultation",
            service_duration_minutes=60,
            notes=marker,
        )
        session.add(order)
        await session.flush()
        session.add(
            Appointment(
                user_id=user.id,
                expert_id=expert.id,
                expert_service_id=offering.id,
                service_order_id=order.id,
                # Far enough in the past that the booking-overlap constraint
                # cannot clash with anything real; the window is still open.
                starts_at_utc=now - timedelta(minutes=5),
                ends_at_utc=now + timedelta(minutes=55),
                timezone="Europe/Istanbul",
                status=AppointmentStatus.CONFIRMED.value,
            )
        )
        await session.commit()
        return {
            "stamp": stamp,
            "user_id": user.id,
            "expert_user_id": expert_user.id,
            "order_id": order.id,
        }


async def cleanup(marker: str = MARKER) -> None:
    factory = get_session_factory()
    async with factory() as session:
        orders = list(
            await session.scalars(select(ServiceOrder.id).where(ServiceOrder.notes == marker))
        )
        if orders:
            calls = list(
                await session.scalars(
                    select(CallSession.id).where(CallSession.order_id.in_(orders))
                )
            )
            if calls:
                await session.execute(
                    delete(CallProviderEvent).where(
                        CallProviderEvent.call_session_id.in_(calls)
                    )
                )
                await session.execute(
                    delete(NotificationOutbox).where(
                        NotificationOutbox.dedupe_key.like("%call%")
                        & NotificationOutbox.user_id.in_(
                            select(User.id).where(User.email.like(f"{marker}-%"))
                        )
                    )
                )
                await session.execute(
                    delete(CallParticipant).where(
                        CallParticipant.call_session_id.in_(calls)
                    )
                )
                await session.execute(delete(CallSession).where(CallSession.id.in_(calls)))
            await session.execute(
                delete(Appointment).where(Appointment.service_order_id.in_(orders))
            )
            await session.execute(delete(ServiceOrder).where(ServiceOrder.id.in_(orders)))

        users = list(
            await session.scalars(select(User).where(User.email.like(f"{marker}-%")))
        )
        for user in users:
            await session.execute(
                delete(NotificationOutbox).where(NotificationOutbox.user_id == user.id)
            )
            expert = await session.scalar(select(Expert).where(Expert.user_id == user.id))
            if expert is not None:
                await session.execute(
                    delete(ExpertService).where(ExpertService.expert_id == expert.id)
                )
                await session.execute(
                    delete(ExpertAvailability).where(
                        ExpertAvailability.expert_id == expert.id
                    )
                )
                await session.delete(expert)
            await session.execute(delete(UserProfile).where(UserProfile.user_id == user.id))
            await session.delete(user)
        # Stray events for rooms that were never ours (from check 2 retries).
        await session.execute(
            delete(CallProviderEvent).where(CallProviderEvent.event_id.like(f"{marker}%"))
        )
        await session.commit()


# ------------------------------------------------------------------ checks


async def check_create(scenario: dict, provider) -> tuple[bool, uuid.UUID | None]:
    print("--- concurrent create ------------------------------------------")
    factory = get_session_factory()

    async def open_once(index: int):
        async with factory() as session:
            caller_id = scenario["user_id"] if index % 2 else scenario["expert_user_id"]
            caller = await session.get(User, caller_id)
            call, created = await CallService(session, provider).create(
                caller, order_id=scenario["order_id"], call_type=CallType.VIDEO
            )
            await session.commit()
            return call.id, created

    results = await asyncio.gather(*(open_once(i) for i in range(OPENERS)))
    ids = {call_id for call_id, _ in results}
    created = sum(1 for _, was_created in results if was_created)

    async with factory() as session:
        stored = await session.scalar(
            select(func.count())
            .select_from(CallSession)
            .where(CallSession.order_id == scenario["order_id"])
        )
    print(f"  concurrent creates : {OPENERS}")
    print(f"  created            : {created}")
    print(f"  distinct ids       : {len(ids)}")
    print(f"  rows stored        : {stored}")
    ok = stored == 1 and len(ids) == 1 and created == 1
    print("PASS: one session, and every caller got it" if ok else "FAIL")
    return ok, next(iter(ids)) if len(ids) == 1 else None


async def check_duplicate_webhook(call_id: uuid.UUID, provider) -> bool:
    print("\n--- the same webhook, eight times at once ---------------------")
    factory = get_session_factory()
    async with factory() as session:
        call = await session.get(CallSession, call_id)
        participant = await session.scalar(
            select(CallParticipant).where(
                CallParticipant.call_session_id == call_id,
                CallParticipant.role == "user",
            )
        )
        room, identity = call.provider_room_name, participant.provider_identity
    provider.join(room, identity)

    body = json.dumps(
        {
            "event": "participant_joined",
            "id": f"{MARKER}-EV-{uuid.uuid4().hex}",
            "createdAt": str(int(datetime.now(UTC).timestamp())),
            "room": {"name": room},
            "participant": {"identity": identity},
        }
    ).encode()
    authorization = provider.signed_webhook(body)

    async def deliver():
        async with factory() as session:
            event = provider.parse_webhook(body, authorization)
            outcome = await CallService(session, provider).apply_provider_event(event)
            await session.commit()
            return outcome

    outcomes = Counter(await asyncio.gather(*(deliver() for _ in range(DUPLICATES))))
    async with factory() as session:
        participant = await session.scalar(
            select(CallParticipant).where(CallParticipant.provider_identity == identity)
        )
        call = await session.get(CallSession, call_id)
    print(f"  deliveries        : {DUPLICATES}")
    print(f"  outcomes          : {dict(outcomes)}")
    print(f"  connection_count  : {participant.connection_count}")
    print(f"  call status       : {call.status}")
    ok = outcomes.get("applied") == 1 and participant.connection_count == 1
    print("PASS: applied once" if ok else "FAIL: applied more than once")
    return ok


async def check_concurrent_join(scenario: dict, call_id: uuid.UUID, provider) -> bool:
    print("\n--- ten join-token requests at once ---------------------------")
    factory = get_session_factory()

    async def join_once():
        async with factory() as session:
            caller = await session.get(User, scenario["expert_user_id"])
            grant = await CallService(session, provider).issue_join_token(caller, call_id)
            await session.commit()
            return grant.participant.provider_identity

    identities = set(await asyncio.gather(*(join_once() for _ in range(JOINERS))))
    async with factory() as session:
        sessions = await session.scalar(
            select(func.count())
            .select_from(CallSession)
            .where(CallSession.order_id == scenario["order_id"])
        )
        participants = await session.scalar(
            select(func.count())
            .select_from(CallParticipant)
            .where(CallParticipant.call_session_id == call_id)
        )
        expert = await session.scalar(
            select(CallParticipant).where(
                CallParticipant.call_session_id == call_id,
                CallParticipant.role == "expert",
            )
        )
    print(f"  requests            : {JOINERS}")
    print(f"  distinct identities : {len(identities)}")
    print(f"  sessions            : {sessions}")
    print(f"  participants        : {participants}")
    print(f"  tokens counted      : {expert.token_issued_count}")
    ok = (
        len(identities) == 1
        and sessions == 1
        and participants == 2
        and expert.token_issued_count == JOINERS
    )
    print("PASS: one session, one identity, every token counted" if ok else "FAIL")
    return ok


async def main() -> int:
    if settings.database_url.startswith("sqlite"):
        print("SKIPPED: this check is meaningless on SQLite.")
        return 2
    if settings.is_production:
        print("REFUSED: this writes test rows. Not in production.")
        return 1

    print(f"dialect : {settings.database_url.split('://', 1)[0]}\n")
    provider = FakeRealtimeCommunicationProvider()
    await cleanup()
    ok = False
    try:
        scenario = await build_scenario()
        ok, call_id = await check_create(scenario, provider)
        if call_id is not None:
            ok = await check_duplicate_webhook(call_id, provider) and ok
            ok = await check_concurrent_join(scenario, call_id, provider) and ok
    finally:
        await cleanup()
        print("\ncleaned up")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
