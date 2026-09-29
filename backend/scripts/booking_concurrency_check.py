"""Prove that one slot yields one appointment, against real Postgres.

    python -m scripts.booking_concurrency_check

The unit tests check the booking state machine, but they run on SQLite, which
serialises writers and has no exclusion constraints. That proves the logic and
nothing about the race.

This script runs the real thing: N connections attempt the same slot at the
same instant, on the real dialect, with the real
`EXCLUDE USING gist (expert_id WITH =, tstzrange(...) WITH &&)` constraint in
place. Exactly one must succeed.

It creates a throwaway expert, service and users, runs the race, and deletes
everything it made. Refuses to run against SQLite or in production.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections import Counter
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.exceptions import AppError
from app.db.models.marketplace import (
    Appointment,
    Expert,
    ExpertAvailability,
    ExpertService,
    SlotHold,
)
from app.db.models.service import ServiceDefinition
from app.db.models.user import User
from app.db.session import get_session_factory
from app.domain.marketplace import DeliveryType, ExpertStatus
from app.services.marketplace.booking import BookingService

ATTEMPTS = 10
MARKER = "concurrency-check-expert"


async def setup() -> dict:
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

        expert = Expert(
            user_id=user.id,
            display_name=MARKER,
            languages=["tr"],
            specialties=["astrology"],
            experience_years=1,
            timezone="Europe/Istanbul",
            status=ExpertStatus.ACTIVE.value,
            verified=False,
            rating_average=0,
            rating_count=0,
        )
        session.add(expert)
        await session.flush()

        offering = ExpertService(
            expert_id=expert.id,
            service_definition_id=definition.id,
            title=MARKER,
            delivery_type=DeliveryType.CHAT.value,
            duration_minutes=60,
            price_minor=0,
            currency="TRY",
            active=True,
        )
        session.add(offering)

        for weekday in range(7):
            session.add(
                ExpertAvailability(
                    expert_id=expert.id,
                    weekday=weekday,
                    start_local_time=time(0, 0),
                    end_local_time=time(23, 0),
                    timezone="Europe/Istanbul",
                    active=True,
                )
            )
        await session.commit()

        users = list(await session.scalars(select(User).limit(ATTEMPTS)))
        return {
            "expert_id": expert.id,
            "service_id": offering.id,
            "user_ids": [row.id for row in users] or [user.id],
        }


async def attempt(
    context: dict, user_id: uuid.UUID, starts_at: datetime, index: int
) -> str:
    """One booking attempt, on its own connection."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            user = await session.get(User, user_id)
            service = await session.scalar(
                select(ExpertService).where(
                    ExpertService.id == context["service_id"]
                )
            )
            booking = BookingService(session)
            await booking.book(
                user,
                service=service,
                starts_at_utc=starts_at,
                display_timezone="Europe/Istanbul",
            )
            await session.commit()
            return "booked"
        except AppError as exc:
            await session.rollback()
            return getattr(exc, "code", "app_error")
        except Exception as exc:  # noqa: BLE001 - the point is to see it
            await session.rollback()
            return f"unexpected:{type(exc).__name__}"


async def hold_attempt(
    context: dict, user_id: uuid.UUID, starts_at: datetime
) -> str:
    factory = get_session_factory()
    async with factory() as session:
        try:
            user = await session.get(User, user_id)
            service = await session.scalar(
                select(ExpertService).where(
                    ExpertService.id == context["service_id"]
                )
            )
            await BookingService(session).hold_slot(
                user, service=service, starts_at_utc=starts_at
            )
            await session.commit()
            return "held"
        except AppError as exc:
            await session.rollback()
            return getattr(exc, "code", "app_error")
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            return f"unexpected:{type(exc).__name__}"


async def cleanup(context: dict | None) -> None:
    factory = get_session_factory()
    async with factory() as session:
        experts = list(
            await session.scalars(
                select(Expert.id).where(Expert.display_name == MARKER)
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
                delete(ExpertAvailability).where(
                    ExpertAvailability.expert_id.in_(experts)
                )
            )
            await session.execute(
                delete(ExpertService).where(ExpertService.expert_id.in_(experts))
            )
            await session.execute(delete(Expert).where(Expert.id.in_(experts)))
        await session.commit()


async def main() -> int:
    if settings.database_url.startswith("sqlite"):
        print("SKIPPED: this check is meaningless on SQLite.")
        print("Point DATABASE_URL at Postgres and run it again.")
        return 2
    if settings.is_production:
        print("REFUSED: this writes test rows. Not in production.")
        return 1

    await cleanup(None)
    context = await setup()

    # A slot comfortably inside the booking horizon.
    starts_at = (
        datetime.now(UTC) + timedelta(days=3)
    ).replace(minute=0, second=0, microsecond=0)

    print(f"dialect  : {settings.database_url.split('://', 1)[0]}")
    print(f"slot     : {starts_at.isoformat()}")
    print(f"attempts : {ATTEMPTS}\n")

    ok = True
    try:
        # --- the race that matters --------------------------------------
        user_ids = context["user_ids"]
        results = await asyncio.gather(
            *(
                attempt(
                    context, user_ids[index % len(user_ids)], starts_at, index
                )
                for index in range(ATTEMPTS)
            )
        )
        counts = Counter(results)
        print("booking attempts:")
        for outcome, count in sorted(counts.items()):
            print(f"  {outcome:24} {count}")

        booked = counts.get("booked", 0)
        if booked == 1:
            print(f"\nPASS: exactly one of {ATTEMPTS} attempts booked the slot")
        else:
            print(f"\nFAIL: {booked} attempts booked the same slot")
            ok = False

        unexpected = [
            outcome for outcome in counts if outcome.startswith("unexpected")
        ]
        if unexpected:
            print(f"FAIL: unmapped errors leaked out: {unexpected}")
            ok = False

        # --- and the same for holds -------------------------------------
        free_slot = starts_at + timedelta(days=1)
        hold_results = await asyncio.gather(
            *(
                hold_attempt(context, user_ids[index % len(user_ids)], free_slot)
                for index in range(ATTEMPTS)
            )
        )
        hold_counts = Counter(hold_results)
        print("\nhold attempts:")
        for outcome, count in sorted(hold_counts.items()):
            print(f"  {outcome:24} {count}")

        if hold_counts.get("held", 0) == 1:
            print(f"\nPASS: exactly one of {ATTEMPTS} attempts held the slot")
        else:
            print(f"\nFAIL: {hold_counts.get('held', 0)} attempts held one slot")
            ok = False

        # --- the database really is enforcing it ------------------------
        factory = get_session_factory()
        async with factory() as session:
            rows = await session.scalar(
                select(Appointment.id).where(
                    Appointment.expert_id == context["expert_id"],
                    Appointment.starts_at_utc == starts_at,
                )
            )
            constraint = await session.scalar(
                select(1).select_from(
                    __import__("sqlalchemy").text(
                        "(SELECT 1 FROM pg_constraint "
                        "WHERE conname = 'ex_appointments_no_overlap') AS c"
                    )
                )
            )
        if constraint:
            print("PASS: the exclusion constraint is present in this database")
        else:
            print("FAIL: ex_appointments_no_overlap is missing")
            ok = False
    finally:
        await cleanup(context)
        print("\ncleaned up")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
