"""Benchmark the marketplace read and write paths.

No payment provider and no model is involved. What is measured is what the
backend actually does: search a population of experts, assemble a public
profile, generate slots over a month and a quarter, and put an order and a
booking through one transaction.

Slot generation is the interesting one. It walks local days, resolves each
window to UTC against that day's offset, subtracts exceptions and existing
appointments, and steps through at the configured granularity - so its cost
grows with the range, not with the number of experts.

Run against real Postgres:  python -m scripts.benchmark_marketplace
"""

from __future__ import annotations

import asyncio
import statistics
import sys
import time as clock
import uuid
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import delete, select

from app.core.config import settings
from app.db.models.marketplace import (
    Appointment,
    Expert,
    ExpertAvailability,
    ExpertService,
    ServiceOrder,
    SlotHold,
)
from app.db.models.service import ServiceDefinition
from app.db.models.user import User
from app.db.session import get_session_factory
from app.domain.marketplace import DeliveryType, ExpertStatus
from app.services.marketplace.discovery import (
    ExpertSearchFilters,
    ExpertSearchService,
    ReviewService,
)
from app.services.marketplace.experts import ExpertServiceManager
from app.services.marketplace.orders import OrderService
from app.services.marketplace.slots import SlotGenerator

MARKER = "benchmark-expert"
POPULATION = 40
SPECIALTIES = ("astrology", "synastry", "tarot", "horary", "rune")


async def timed(label: str, coro_factory, repeat: int = 20) -> tuple[str, float, float]:
    samples = []
    for _ in range(repeat):
        started = clock.perf_counter()
        await coro_factory()
        samples.append((clock.perf_counter() - started) * 1000)
    return (
        label,
        round(statistics.median(samples), 2),
        round(sorted(samples)[int(len(samples) * 0.95) - 1], 2),
    )


async def seed() -> dict:
    factory = get_session_factory()
    async with factory() as session:
        user = await session.scalar(select(User).limit(1))
        if user is None:
            raise SystemExit("No users in the database; register one first.")

        definition = await session.scalar(
            select(ServiceDefinition)
            .where(
                ServiceDefinition.supports_appointment.is_(True),
                ServiceDefinition.active.is_(True),
            )
            .limit(1)
        )
        if definition is None:
            raise SystemExit("No appointment service in the catalogue.")

        first_service: uuid.UUID | None = None
        first_expert: uuid.UUID | None = None

        # One profile per account is a real constraint, so a population of
        # experts needs a population of accounts.
        for index in range(POPULATION):
            # The account carries credentials only; the display name lives
            # on the expert profile.
            owner = User(
                email=f"{MARKER}-{index}@benchmark.invalid",
                password_hash="not-a-real-hash",
                is_active=True,
            )
            session.add(owner)
            await session.flush()

            expert = Expert(
                user_id=owner.id,
                display_name=f"{MARKER}-{index}",
                headline="Benchmark profile",
                languages=["tr", "en"] if index % 2 else ["tr"],
                specialties=[SPECIALTIES[index % len(SPECIALTIES)]],
                experience_years=index % 25,
                timezone="Europe/Istanbul",
                status=ExpertStatus.ACTIVE.value,
                verified=index % 3 == 0,
                rating_average=round(3 + (index % 20) / 10, 2),
                rating_count=index,
            )
            session.add(expert)
            await session.flush()

            offering = ExpertService(
                expert_id=expert.id,
                service_definition_id=definition.id,
                title=f"{MARKER} consultation",
                delivery_type=DeliveryType.CHAT.value,
                duration_minutes=60,
                price_minor=5000 + index * 500,
                currency="TRY",
                active=True,
            )
            session.add(offering)
            await session.flush()

            if first_service is None:
                first_service, first_expert = offering.id, expert.id
                for weekday in range(7):
                    session.add(
                        ExpertAvailability(
                            expert_id=expert.id,
                            weekday=weekday,
                            start_local_time=time(9, 0),
                            end_local_time=time(18, 0),
                            timezone="Europe/Istanbul",
                            active=True,
                        )
                    )

        await session.commit()
        return {
            "expert_id": first_expert,
            "service_id": first_service,
            "user_id": user.id,
            "definition_id": definition.id,
        }


async def cleanup() -> None:
    factory = get_session_factory()
    async with factory() as session:
        experts = list(
            await session.scalars(
                select(Expert.id).where(Expert.display_name.like(f"{MARKER}%"))
            )
        )
        if experts:
            await session.execute(
                delete(Appointment).where(Appointment.expert_id.in_(experts))
            )
            await session.execute(
                delete(SlotHold).where(SlotHold.expert_id.in_(experts))
            )
            await session.execute(
                delete(ServiceOrder).where(ServiceOrder.expert_id.in_(experts))
            )
            await session.execute(
                delete(ExpertAvailability).where(
                    ExpertAvailability.expert_id.in_(experts)
                )
            )
            await session.execute(
                delete(ExpertService).where(ExpertService.expert_id.in_(experts))
            )
            await session.execute(delete(Expert).where(Expert.id.in_(experts)))
        await session.execute(
            delete(User).where(User.email.like(f"{MARKER}%@benchmark.invalid"))
        )
        await session.commit()


async def main() -> int:
    if settings.is_production:
        print("REFUSED: this writes test rows. Not in production.")
        return 1

    await cleanup()
    context = await seed()
    factory = get_session_factory()
    rows = []

    try:
        async def search_all():
            async with factory() as session:
                await ExpertSearchService(session).search(
                    ExpertSearchFilters(limit=20)
                )

        async def search_filtered():
            async with factory() as session:
                await ExpertSearchService(session).search(
                    ExpertSearchFilters(
                        specialty=None,
                        language="tr",
                        min_price_minor=5000,
                        max_price_minor=20000,
                        verified_only=True,
                        limit=20,
                    )
                )

        async def expert_detail():
            async with factory() as session:
                offerings = await ExpertServiceManager(session).list_for_expert(
                    context["expert_id"]
                )
                await ReviewService(session).summary(context["expert_id"])
                return offerings

        async def slots(days: int):
            async with factory() as session:
                service = await session.scalar(
                    select(ExpertService).where(
                        ExpertService.id == context["service_id"]
                    )
                )
                now = datetime.now(UTC)
                await SlotGenerator(session).generate(
                    expert_id=context["expert_id"],
                    service=service,
                    start=now,
                    end=now + timedelta(days=days),
                )

        rows.append(await timed("expert search (unfiltered)", search_all))
        rows.append(await timed("expert search (filtered)", search_filtered))
        rows.append(await timed("expert detail + rating summary", expert_detail))
        rows.append(await timed("slots, 30 days", lambda: slots(30), repeat=10))
        rows.append(await timed("slots, 90 days", lambda: slots(90), repeat=10))

        # Order + booking in one transaction, each on a fresh slot.
        offset = [0]

        async def order_and_book():
            async with factory() as session:
                user = await session.get(User, context["user_id"])
                service = await session.scalar(
                    select(ExpertService).where(
                        ExpertService.id == context["service_id"]
                    )
                )
                generator = SlotGenerator(session)
                now = datetime.now(UTC)
                available = await generator.generate(
                    expert_id=context["expert_id"],
                    service=service,
                    start=now,
                    end=now + timedelta(days=60),
                )
                if offset[0] >= len(available):
                    return
                starts = available[offset[0]].starts_at_utc
                offset[0] += 4

                await OrderService(session).create(
                    user,
                    expert_service_id=service.id,
                    starts_at_utc=starts,
                    display_timezone="Europe/Istanbul",
                )
                await session.commit()

        rows.append(
            await timed("order + booking transaction", order_and_book, repeat=10)
        )

        print(f"\n{'operation':36} {'median ms':>10} {'p95 ms':>9}")
        print("-" * 60)
        for label, median, p95 in rows:
            print(f"{label:36} {median:>10} {p95:>9}")

        print()
        print(f"expert population       : {POPULATION}")
        print(
            f"slot granularity        : "
            f"{settings.appointment_slot_granularity_minutes} min"
        )
        print(
            f"buffers                 : "
            f"{settings.appointment_buffer_before_minutes}/"
            f"{settings.appointment_buffer_after_minutes} min"
        )
        print(f"commission              : {settings.marketplace_commission_bps} bp")
    finally:
        await cleanup()
        print("\ncleaned up")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
