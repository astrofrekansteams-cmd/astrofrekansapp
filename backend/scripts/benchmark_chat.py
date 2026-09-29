"""What backend-mediated chat actually costs.

    python -m scripts.benchmark_chat

B9 routes every message through FastAPI rather than letting the client write to
Firestore, which buys a coherent authorisation story and costs a round trip. The
size of that cost is the thing to know, so it is measured rather than asserted.

Run with the **fake** Firebase providers, which is the point: the transport's
latency belongs to Firebase and varies by region and network, while the work
measured here - authorise, reconcile, validate, check idempotency, count, queue a
notification - is ours and is the same everywhere. Add the region's Firestore
write latency to these numbers to get a real send.

Needs Postgres, because the authorisation queries are the bulk of it and SQLite
would flatter them.

Usage:
    python -m scripts.benchmark_chat [--messages 200]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import statistics
import sys
import time
import uuid
from datetime import UTC, datetime, time as clock_time, timedelta

import structlog
from sqlalchemy import delete, select

from app.core.cache import close_cache, init_cache
from app.core.config import settings
from app.db.models.chat import ExpertConversation, NotificationOutbox
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
from app.domain.marketplace import (
    AppointmentStatus,
    DeliveryType,
    ExpertStatus,
    FulfillmentMode,
    OrderStatus,
    PaymentStatus,
)
from app.services.chat.conversations import ConversationService
from app.services.firebase.factory import fake_providers
from app.services.notifications.outbox import OutboxService

MARKER = "benchmark-chat"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(int(len(ordered) * fraction), len(ordered) - 1)
    return ordered[index]


def report(label: str, samples: list[float]) -> None:
    print(
        f"  {label:<34} "
        f"mean {statistics.mean(samples) * 1000:7.1f} ms   "
        f"p50 {percentile(samples, 0.5) * 1000:7.1f}   "
        f"p95 {percentile(samples, 0.95) * 1000:7.1f}   "
        f"max {max(samples) * 1000:7.1f}"
    )


# ------------------------------------------------------------------ fixtures


async def build_scenario() -> dict:
    """A user, an expert, a paid order and a booked appointment.

    Written directly rather than through the API: the point is to time the chat
    path, not the setup.
    """
    factory = get_session_factory()
    stamp = uuid.uuid4().hex[:8]

    async with factory() as session:
        definition = await session.scalar(
            select(ServiceDefinition)
            .where(
                ServiceDefinition.supports_chat.is_(True),
                ServiceDefinition.supports_appointment.is_(True),
                ServiceDefinition.active.is_(True),
            )
            .limit(1)
        )
        if definition is None:
            raise SystemExit(
                "No chat-capable appointment service in the catalogue. "
                "Run scripts/seed_services.py first."
            )

        user = User(
            email=f"bench-chat-user-{stamp}@example.com",
            password_hash=None,
            is_active=True,
            is_email_verified=True,
            firebase_uid=f"bench-uid-user-{stamp}",
        )
        expert_user = User(
            email=f"bench-chat-expert-{stamp}@example.com",
            password_hash=None,
            is_active=True,
            is_email_verified=True,
            firebase_uid=f"bench-uid-expert-{stamp}",
        )
        session.add_all([user, expert_user])
        await session.flush()
        session.add_all(
            [
                UserProfile(user_id=user.id, name="Bench User"),
                UserProfile(user_id=expert_user.id, name="Bench Expert"),
            ]
        )

        expert = Expert(
            user_id=expert_user.id,
            display_name=f"Bench Expert {stamp}",
            languages=["tr"],
            specialties=["astrology"],
            experience_years=5,
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
            title="Bench consultation",
            delivery_type=DeliveryType.CHAT.value,
            duration_minutes=60,
            price_minor=10000,
            currency="TRY",
            active=True,
        )
        session.add(offering)
        session.add(
            ExpertAvailability(
                expert_id=expert.id,
                weekday=datetime.now(UTC).weekday(),
                start_local_time=clock_time(0, 0),
                end_local_time=clock_time(23, 0),
                timezone="Europe/Istanbul",
                active=True,
            )
        )
        await session.flush()

        starts = datetime.now(UTC) + timedelta(days=2)
        order = ServiceOrder(
            user_id=user.id,
            service_definition_id=definition.id,
            expert_id=expert.id,
            expert_service_id=offering.id,
            fulfillment_mode=FulfillmentMode.EXPERT.value,
            delivery_type=DeliveryType.CHAT.value,
            service_title="Bench consultation",
            service_duration_minutes=60,
            status=OrderStatus.CONFIRMED.value,
            payment_status=PaymentStatus.PAID.value,
            subtotal_minor=10000,
            discount_minor=0,
            total_minor=10000,
            currency="TRY",
            platform_fee_minor=2000,
            expert_net_minor=8000,
            commission_basis_points=2000,
            notes=MARKER,
        )
        session.add(order)
        await session.flush()

        session.add(
            Appointment(
                service_order_id=order.id,
                user_id=user.id,
                expert_id=expert.id,
                expert_service_id=offering.id,
                starts_at_utc=starts,
                ends_at_utc=starts + timedelta(minutes=60),
                timezone="Europe/Istanbul",
                status=AppointmentStatus.CONFIRMED.value,
            )
        )
        await session.commit()

        return {
            "user_id": user.id,
            "expert_user_id": expert_user.id,
            "order_id": order.id,
            "stamp": stamp,
        }


async def cleanup(scenario: dict | None) -> None:
    factory = get_session_factory()
    async with factory() as session:
        orders = list(
            await session.scalars(
                select(ServiceOrder.id).where(ServiceOrder.notes == MARKER)
            )
        )
        if orders:
            await session.execute(
                delete(NotificationOutbox).where(
                    NotificationOutbox.order_id.in_(orders)
                )
            )
            conversations = list(
                await session.scalars(
                    select(ExpertConversation.id).where(
                        ExpertConversation.order_id.in_(orders)
                    )
                )
            )
            if conversations:
                await session.execute(
                    delete(NotificationOutbox).where(
                        NotificationOutbox.conversation_id.in_(conversations)
                    )
                )
                await session.execute(
                    delete(ExpertConversation).where(
                        ExpertConversation.id.in_(conversations)
                    )
                )
            appointments = list(
                await session.scalars(
                    select(Appointment.id).where(
                        Appointment.service_order_id.in_(orders)
                    )
                )
            )
            if appointments:
                await session.execute(
                    delete(NotificationOutbox).where(
                        NotificationOutbox.appointment_id.in_(appointments)
                    )
                )
                await session.execute(
                    delete(Appointment).where(Appointment.id.in_(appointments))
                )
            await session.execute(
                delete(ServiceOrder).where(ServiceOrder.id.in_(orders))
            )
        await session.commit()

    if scenario is None:
        return
    async with factory() as session:
        stamp = scenario["stamp"]
        users = list(
            await session.scalars(
                select(User).where(User.email.like(f"bench-chat-%-{stamp}@%"))
            )
        )
        for row in users:
            expert = await session.scalar(
                select(Expert).where(Expert.user_id == row.id)
            )
            if expert is not None:
                await session.execute(
                    delete(ExpertService).where(
                        ExpertService.expert_id == expert.id
                    )
                )
                await session.execute(
                    delete(ExpertAvailability).where(
                        ExpertAvailability.expert_id == expert.id
                    )
                )
                await session.delete(expert)
            profile = await session.scalar(
                select(UserProfile).where(UserProfile.user_id == row.id)
            )
            if profile is not None:
                await session.delete(profile)
            await session.delete(row)
        await session.commit()


# --------------------------------------------------------------------- main


async def main(count: int) -> int:
    if settings.is_production:
        print("REFUSED: this writes test rows. Not in production.")
        return 1
    if settings.database_url.startswith("sqlite"):
        print("SKIPPED: SQLite would flatter the authorisation queries.")
        print("Point DATABASE_URL at Postgres and run it again.")
        return 2

    # The services under measurement log a line per message, which would bury
    # the numbers this script exists to print.
    logging.getLogger().setLevel(logging.WARNING)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING)
    )

    await init_cache()
    firebase = fake_providers()
    factory = get_session_factory()
    scenario = None

    try:
        await cleanup(None)
        scenario = await build_scenario()

        print(f"dialect  : {settings.database_url.split('://', 1)[0]}")
        print("provider : fake (Firestore latency excluded on purpose)")
        print(f"messages : {count}\n")

        # --- opening the conversation ---------------------------------------
        async with factory() as session:
            user = await session.get(User, scenario["user_id"])
            service = ConversationService(session, firebase)

            started = time.perf_counter()
            conversation = await service.ensure_for_order(
                user, scenario["order_id"]
            )
            await session.commit()
            first_open = time.perf_counter() - started
            conversation_id = conversation.id

        print("open")
        print(f"  first open (creates + projects)    {first_open * 1000:7.1f} ms")

        reopens: list[float] = []
        for _ in range(20):
            async with factory() as session:
                user = await session.get(User, scenario["user_id"])
                started = time.perf_counter()
                await ConversationService(session, firebase).ensure_for_order(
                    user, scenario["order_id"]
                )
                await session.commit()
                reopens.append(time.perf_counter() - started)
        report("idempotent re-open", reopens)

        # --- authorising a read ---------------------------------------------
        reads: list[float] = []
        for _ in range(count):
            async with factory() as session:
                user = await session.get(User, scenario["user_id"])
                started = time.perf_counter()
                await ConversationService(session, firebase).get_for_member(
                    user, conversation_id
                )
                await session.commit()
                reads.append(time.perf_counter() - started)

        print("\nauthorise")
        report("get_for_member (+ reconcile)", reads)

        # --- the full send path ---------------------------------------------
        sends: list[float] = []
        for index in range(count):
            async with factory() as session:
                user = await session.get(User, scenario["user_id"])
                service = ConversationService(session, firebase)

                started = time.perf_counter()
                message, conversation, _ = await service.send_message(
                    user,
                    conversation_id,
                    text=f"benchmark message {index}",
                    client_message_id=f"bench-{scenario['stamp']}-{index}",
                )
                recipient = await service.counterpart_user_id(conversation, user)
                await OutboxService(session).enqueue_chat_message(
                    recipient_user_id=recipient,
                    conversation_id=conversation.id,
                    message_id=message.message_id,
                )
                await session.commit()
                sends.append(time.perf_counter() - started)

        print("\nsend (authorise -> validate -> write -> queue push)")
        report("send_message + enqueue", sends)

        # --- the idempotent replay, which a retry pays -----------------------
        replays: list[float] = []
        for index in range(min(count, 50)):
            async with factory() as session:
                user = await session.get(User, scenario["user_id"])
                started = time.perf_counter()
                await ConversationService(session, firebase).send_message(
                    user,
                    conversation_id,
                    text=f"benchmark message {index}",
                    client_message_id=f"bench-{scenario['stamp']}-{index}",
                )
                await session.commit()
                replays.append(time.perf_counter() - started)
        report("idempotent replay of a retry", replays)

        # --- history ---------------------------------------------------------
        pages: list[float] = []
        for _ in range(50):
            async with factory() as session:
                user = await session.get(User, scenario["user_id"])
                started = time.perf_counter()
                await ConversationService(session, firebase).history(
                    user, conversation_id, limit=50
                )
                await session.commit()
                pages.append(time.perf_counter() - started)

        print("\nread")
        report("history page of 50", pages)

        # --- the outbox claim ------------------------------------------------
        claims: list[float] = []
        while True:
            async with factory() as session:
                started = time.perf_counter()
                row = await OutboxService(session).claim_next(
                    worker_id="benchmark"
                )
                elapsed = time.perf_counter() - started
            if row is None:
                break
            claims.append(elapsed)
            if len(claims) >= count:
                break

        print("\npush")
        if claims:
            report("claim_next (SKIP LOCKED)", claims)
        else:
            print("  nothing queued to claim")

        print(
            "\nEvery figure excludes the Firebase round trip, which is what a\n"
            "client would also pay writing to Firestore directly. The backend's\n"
            "own share of a send is the send figure above."
        )
        return 0
    finally:
        await cleanup(scenario)
        await close_cache()
        print("\ncleaned up")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--messages", type=int, default=200)
    arguments = parser.parse_args()
    sys.exit(asyncio.run(main(arguments.messages)))
