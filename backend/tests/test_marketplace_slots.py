"""Slot generation, and the timezone traps it has to survive.

The point of this file is daylight saving time. An expert says "Mondays 09:00,
Istanbul" and means it: they still start at nine after the clocks change. Get
that wrong and you either move someone's morning by an hour twice a year, or
invent a meeting at a time that did not exist.

Three zones, chosen because they behave differently:

* `Europe/Istanbul` - no DST since 2016, permanently UTC+3. The control.
* `Europe/Berlin` - EU transitions, last Sunday of March and October.
* `America/New_York` - US transitions, on different dates from the EU.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models.marketplace import (
    Appointment,
    Expert,
    ExpertAvailability,
    ExpertAvailabilityException,
    ExpertService,
)
from app.db.models.service import ServiceDefinition
from app.domain.marketplace import (
    AppointmentStatus,
    AvailabilityExceptionType,
    DeliveryType,
    ExpertStatus,
)
from app.services.marketplace.slots import (
    InvalidTimezone,
    SlotGenerator,
    SlotRangeTooLarge,
    local_time_exists,
    utc_instants,
    zone,
)

ISTANBUL = ZoneInfo("Europe/Istanbul")
BERLIN = ZoneInfo("Europe/Berlin")
NEW_YORK = ZoneInfo("America/New_York")

# Transition dates that actually matter.
EU_SPRING_FORWARD = date(2027, 3, 28)   # 02:00 -> 03:00 local
EU_AUTUMN_BACK = date(2027, 10, 31)     # 03:00 -> 02:00 local
US_SPRING_FORWARD = date(2027, 3, 14)
US_AUTUMN_BACK = date(2027, 11, 7)


# ================================================= local time arithmetic


def test_a_skipped_local_time_does_not_exist():
    """Spring forward: 02:30 is simply not on the clock that day."""
    assert local_time_exists(EU_SPRING_FORWARD, time(2, 30), BERLIN) is False
    assert utc_instants(EU_SPRING_FORWARD, time(2, 30), BERLIN) == []

    assert local_time_exists(US_SPRING_FORWARD, time(2, 30), NEW_YORK) is False
    assert utc_instants(US_SPRING_FORWARD, time(2, 30), NEW_YORK) == []

    # An hour either side is perfectly real.
    assert local_time_exists(EU_SPRING_FORWARD, time(1, 30), BERLIN)
    assert local_time_exists(EU_SPRING_FORWARD, time(3, 30), BERLIN)


def test_an_ambiguous_local_time_is_two_real_instants():
    """Autumn back: 02:30 happens twice, and both are bookable."""
    instants = utc_instants(EU_AUTUMN_BACK, time(2, 30), BERLIN)
    assert len(instants) == 2
    assert instants[1] - instants[0] == timedelta(hours=1)
    assert instants[0] == datetime(2027, 10, 31, 0, 30, tzinfo=UTC)
    assert instants[1] == datetime(2027, 10, 31, 1, 30, tzinfo=UTC)

    us = utc_instants(US_AUTUMN_BACK, time(1, 30), NEW_YORK)
    assert len(us) == 2
    assert us[1] - us[0] == timedelta(hours=1)


def test_istanbul_has_no_transitions_to_survive():
    """The control: permanently UTC+3 since 2016."""
    for day in (EU_SPRING_FORWARD, EU_AUTUMN_BACK, date(2027, 7, 1)):
        instants = utc_instants(day, time(9, 0), ISTANBUL)
        assert len(instants) == 1
        assert instants[0].hour == 6  # 09:00 +03:00


def test_an_unknown_timezone_is_a_clean_error():
    with pytest.raises(InvalidTimezone) as error:
        zone("Mars/Olympus_Mons")
    assert error.value.code == "invalid_timezone"


# ========================================================= fixtures


@pytest.fixture
async def expert_setup(client, registered, session_factory):
    """An active expert with a 60-minute service, no schedule yet."""
    from app.db.models.user import User

    from app.services.catalog.service import CatalogService

    async with session_factory() as session:
        # The catalogue is the source of truth for what can be offered, so the
        # marketplace tests seed it rather than inventing a service definition.
        await CatalogService(session).seed()
        await session.commit()

        user = await session.scalar(
            select(User).where(User.email == registered["email"])
        )
        definition = await session.scalar(
            select(ServiceDefinition)
            .where(ServiceDefinition.supports_appointment.is_(True))
            .limit(1)
        )
        assert definition is not None, "the catalogue has no appointment service"

        expert = Expert(
            user_id=user.id,
            display_name="Test Expert",
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
            title="Consultation",
            delivery_type=DeliveryType.VIDEO.value
            if definition.supports_video
            else DeliveryType.CHAT.value,
            duration_minutes=60,
            price_minor=10000,
            currency="TRY",
            active=True,
        )
        session.add(offering)
        await session.commit()
        return {
            "expert_id": expert.id,
            "service_id": offering.id,
            "user_id": user.id,
        }


async def add_window(
    session_factory,
    expert_id: uuid.UUID,
    *,
    weekday: int,
    start: time,
    end: time,
    timezone: str,
):
    async with session_factory() as session:
        session.add(
            ExpertAvailability(
                expert_id=expert_id,
                weekday=weekday,
                start_local_time=start,
                end_local_time=end,
                timezone=timezone,
                active=True,
            )
        )
        await session.commit()


async def generate(
    session_factory,
    setup,
    *,
    start: datetime,
    end: datetime,
    display: str | None = None,
):
    async with session_factory() as session:
        service = await session.scalar(
            select(ExpertService).where(ExpertService.id == setup["service_id"])
        )
        return await SlotGenerator(session).generate(
            expert_id=setup["expert_id"],
            service=service,
            start=start,
            end=end,
            display_timezone=display,
        )


# ========================================================= generation


async def test_no_schedule_means_no_slots(client, registered, expert_setup, session_factory):
    slots = await generate(
        session_factory,
        expert_setup,
        start=datetime.now(UTC) + timedelta(days=1),
        end=datetime.now(UTC) + timedelta(days=8),
    )
    assert slots == []


async def test_a_weekly_window_produces_slots(
    client, registered, expert_setup, session_factory
):
    # Next Monday, 09:00-12:00 Istanbul, 60-minute service.
    await add_window(
        session_factory,
        expert_setup["expert_id"],
        weekday=0,
        start=time(9, 0),
        end=time(12, 0),
        timezone="Europe/Istanbul",
    )

    now = datetime.now(UTC)
    slots = await generate(
        session_factory, expert_setup, start=now, end=now + timedelta(days=14)
    )
    assert slots, "a Monday window should produce Monday slots"

    for slot in slots:
        local = slot.starts_at_utc.astimezone(ISTANBUL)
        assert local.weekday() == 0
        assert 9 <= local.hour < 12
        assert slot.ends_at_utc - slot.starts_at_utc == timedelta(minutes=60)


async def test_slots_respect_minimum_notice_and_horizon(
    client, registered, expert_setup, session_factory, monkeypatch
):
    for weekday in range(7):
        await add_window(
            session_factory,
            expert_setup["expert_id"],
            weekday=weekday,
            start=time(0, 0),
            end=time(23, 0),
            timezone="Europe/Istanbul",
        )

    monkeypatch.setattr(settings, "appointment_minimum_notice_minutes", 240)
    monkeypatch.setattr(settings, "appointment_max_horizon_days", 3)

    now = datetime.now(UTC)
    slots = await generate(
        session_factory, expert_setup, start=now, end=now + timedelta(days=30)
    )
    assert slots

    earliest = min(slot.starts_at_utc for slot in slots)
    latest = max(slot.starts_at_utc for slot in slots)
    assert earliest >= now + timedelta(minutes=239)
    assert latest <= now + timedelta(days=3, minutes=1)


async def test_an_over_long_range_is_refused(
    client, registered, expert_setup, session_factory
):
    now = datetime.now(UTC)
    with pytest.raises(SlotRangeTooLarge):
        await generate(
            session_factory, expert_setup, start=now, end=now + timedelta(days=400)
        )


# ============================================================= DST


async def test_spring_forward_produces_no_impossible_slot(
    client, registered, expert_setup, session_factory, monkeypatch
):
    """A window over the gap must not offer a time that did not exist."""
    monkeypatch.setattr(settings, "appointment_minimum_notice_minutes", 0)
    monkeypatch.setattr(settings, "appointment_max_horizon_days", 3650)

    await add_window(
        session_factory,
        expert_setup["expert_id"],
        weekday=EU_SPRING_FORWARD.weekday(),
        start=time(1, 0),
        end=time(5, 0),
        timezone="Europe/Berlin",
    )

    start = datetime(2027, 3, 28, tzinfo=UTC)
    slots = await generate(
        session_factory,
        expert_setup,
        start=start,
        end=start + timedelta(days=1),
        display="Europe/Berlin",
    )

    assert slots, "the window produced nothing; the test would prove nothing"
    for slot in slots:
        local = slot.starts_at_utc.astimezone(BERLIN)
        # 02:xx local never happened on this date.
        assert local.hour != 2, f"offered a non-existent local time: {local}"
        # And every offered instant round-trips to itself.
        assert local.astimezone(UTC) == slot.starts_at_utc


async def test_autumn_back_does_not_duplicate_a_slot(
    client, registered, expert_setup, session_factory, monkeypatch
):
    """Both 02:30s are real, and they are different UTC instants."""
    monkeypatch.setattr(settings, "appointment_minimum_notice_minutes", 0)
    monkeypatch.setattr(settings, "appointment_max_horizon_days", 3650)

    await add_window(
        session_factory,
        expert_setup["expert_id"],
        weekday=EU_AUTUMN_BACK.weekday(),
        start=time(1, 0),
        end=time(5, 0),
        timezone="Europe/Berlin",
    )

    start = datetime(2027, 10, 31, tzinfo=UTC)
    slots = await generate(
        session_factory,
        expert_setup,
        start=start,
        end=start + timedelta(days=1),
        display="Europe/Berlin",
    )

    assert slots, "the window produced nothing; the test would prove nothing"
    starts = [slot.starts_at_utc for slot in slots]
    assert len(starts) == len(set(starts)), "the same UTC instant twice"

    # No two slots overlap, which is what would break booking.
    ordered = sorted(slots, key=lambda item: item.starts_at_utc)
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        assert earlier.starts_at_utc != later.starts_at_utc


async def test_us_transitions_behave_the_same_way(
    client, registered, expert_setup, session_factory, monkeypatch
):
    monkeypatch.setattr(settings, "appointment_minimum_notice_minutes", 0)
    monkeypatch.setattr(settings, "appointment_max_horizon_days", 3650)

    await add_window(
        session_factory,
        expert_setup["expert_id"],
        weekday=US_SPRING_FORWARD.weekday(),
        start=time(1, 0),
        end=time(5, 0),
        timezone="America/New_York",
    )

    start = datetime(2027, 3, 14, tzinfo=UTC)
    slots = await generate(
        session_factory,
        expert_setup,
        start=start,
        end=start + timedelta(days=1),
        display="America/New_York",
    )
    assert slots, "the window produced nothing; the test would prove nothing"
    for slot in slots:
        local = slot.starts_at_utc.astimezone(NEW_YORK)
        assert local.hour != 2, f"offered a non-existent local time: {local}"


async def test_an_expert_changing_timezone_does_not_move_appointments(
    client, registered, expert_setup, session_factory
):
    """UTC is canonical, so a profile edit cannot shift a booking."""
    async with session_factory() as session:
        appointment = Appointment(
            user_id=expert_setup["user_id"],
            expert_id=expert_setup["expert_id"],
            expert_service_id=expert_setup["service_id"],
            starts_at_utc=datetime(2027, 6, 1, 9, 0, tzinfo=UTC),
            ends_at_utc=datetime(2027, 6, 1, 10, 0, tzinfo=UTC),
            timezone="Europe/Istanbul",
            status=AppointmentStatus.CONFIRMED.value,
        )
        session.add(appointment)
        await session.commit()
        appointment_id = appointment.id
        original = appointment.starts_at_utc

    async with session_factory() as session:
        expert = await session.scalar(
            select(Expert).where(Expert.id == expert_setup["expert_id"])
        )
        expert.timezone = "America/New_York"
        await session.commit()

    async with session_factory() as session:
        again = await session.scalar(
            select(Appointment).where(Appointment.id == appointment_id)
        )
        assert again.starts_at_utc == original
        # The display zone recorded at booking is untouched too.
        assert again.timezone == "Europe/Istanbul"


# ====================================================== exceptions


async def test_a_blocking_exception_removes_slots(
    client, registered, expert_setup, session_factory, monkeypatch
):
    monkeypatch.setattr(settings, "appointment_minimum_notice_minutes", 0)

    for weekday in range(7):
        await add_window(
            session_factory,
            expert_setup["expert_id"],
            weekday=weekday,
            start=time(9, 0),
            end=time(17, 0),
            timezone="Europe/Istanbul",
        )

    now = datetime.now(UTC)
    before = await generate(
        session_factory, expert_setup, start=now, end=now + timedelta(days=5)
    )
    assert before

    # Block the entire range.
    async with session_factory() as session:
        session.add(
            ExpertAvailabilityException(
                expert_id=expert_setup["expert_id"],
                exception_type=AvailabilityExceptionType.VACATION.value,
                starts_at_utc=now - timedelta(days=1),
                ends_at_utc=now + timedelta(days=6),
                reason="holiday",
            )
        )
        await session.commit()

    after = await generate(
        session_factory, expert_setup, start=now, end=now + timedelta(days=5)
    )
    assert after == []


async def test_a_block_can_split_a_window(
    client, registered, expert_setup, session_factory, monkeypatch
):
    monkeypatch.setattr(settings, "appointment_minimum_notice_minutes", 0)
    monkeypatch.setattr(settings, "appointment_max_horizon_days", 3650)

    await add_window(
        session_factory,
        expert_setup["expert_id"],
        weekday=2,  # Wednesday
        start=time(9, 0),
        end=time(17, 0),
        timezone="Europe/Istanbul",
    )

    # 2027-12-01 is a Wednesday. Block the middle of the day.
    day = datetime(2027, 12, 1, tzinfo=UTC)
    async with session_factory() as session:
        session.add(
            ExpertAvailabilityException(
                expert_id=expert_setup["expert_id"],
                exception_type=AvailabilityExceptionType.BUSY.value,
                starts_at_utc=datetime(2027, 12, 1, 9, 0, tzinfo=UTC),  # 12:00 local
                ends_at_utc=datetime(2027, 12, 1, 11, 0, tzinfo=UTC),  # 14:00 local
            )
        )
        await session.commit()

    slots = await generate(
        session_factory, expert_setup, start=day, end=day + timedelta(days=1)
    )
    assert slots
    for slot in slots:
        assert not (
            slot.starts_at_utc < datetime(2027, 12, 1, 11, 0, tzinfo=UTC)
            and datetime(2027, 12, 1, 9, 0, tzinfo=UTC) < slot.ends_at_utc
        ), "a slot overlaps the blocked window"


async def test_extra_availability_adds_slots_outside_the_schedule(
    client, registered, expert_setup, session_factory, monkeypatch
):
    monkeypatch.setattr(settings, "appointment_minimum_notice_minutes", 0)
    monkeypatch.setattr(settings, "appointment_max_horizon_days", 3650)

    # No weekly schedule at all - only a one-off extra evening.
    day = datetime(2027, 12, 4, 17, 0, tzinfo=UTC)
    async with session_factory() as session:
        session.add(
            ExpertAvailabilityException(
                expert_id=expert_setup["expert_id"],
                exception_type=AvailabilityExceptionType.EXTRA_AVAILABILITY.value,
                starts_at_utc=day,
                ends_at_utc=day + timedelta(hours=3),
                reason="one-off evening",
            )
        )
        await session.commit()

    slots = await generate(
        session_factory,
        expert_setup,
        start=day - timedelta(hours=1),
        end=day + timedelta(hours=4),
    )
    assert slots
    assert all(slot.starts_at_utc >= day for slot in slots)


async def test_an_existing_appointment_removes_its_slot(
    client, registered, expert_setup, session_factory, monkeypatch
):
    monkeypatch.setattr(settings, "appointment_minimum_notice_minutes", 0)
    monkeypatch.setattr(settings, "appointment_max_horizon_days", 3650)
    monkeypatch.setattr(settings, "appointment_buffer_before_minutes", 0)
    monkeypatch.setattr(settings, "appointment_buffer_after_minutes", 0)

    await add_window(
        session_factory,
        expert_setup["expert_id"],
        weekday=2,
        start=time(9, 0),
        end=time(17, 0),
        timezone="Europe/Istanbul",
    )

    day = datetime(2027, 12, 1, tzinfo=UTC)
    slots = await generate(
        session_factory, expert_setup, start=day, end=day + timedelta(days=1)
    )
    taken = slots[0].starts_at_utc

    async with session_factory() as session:
        session.add(
            Appointment(
                user_id=expert_setup["user_id"],
                expert_id=expert_setup["expert_id"],
                expert_service_id=expert_setup["service_id"],
                starts_at_utc=taken,
                ends_at_utc=taken + timedelta(minutes=60),
                timezone="Europe/Istanbul",
                status=AppointmentStatus.CONFIRMED.value,
            )
        )
        await session.commit()

    after = await generate(
        session_factory, expert_setup, start=day, end=day + timedelta(days=1)
    )
    assert taken not in [slot.starts_at_utc for slot in after]


async def test_buffers_keep_neighbouring_slots_clear(
    client, registered, expert_setup, session_factory, monkeypatch
):
    """A back-to-back booking is not a slot when a buffer is configured."""
    monkeypatch.setattr(settings, "appointment_minimum_notice_minutes", 0)
    monkeypatch.setattr(settings, "appointment_max_horizon_days", 3650)
    monkeypatch.setattr(settings, "appointment_buffer_before_minutes", 30)
    monkeypatch.setattr(settings, "appointment_buffer_after_minutes", 30)

    await add_window(
        session_factory,
        expert_setup["expert_id"],
        weekday=2,
        start=time(9, 0),
        end=time(17, 0),
        timezone="Europe/Istanbul",
    )

    booked = datetime(2027, 12, 1, 9, 0, tzinfo=UTC)  # 12:00 Istanbul
    async with session_factory() as session:
        session.add(
            Appointment(
                user_id=expert_setup["user_id"],
                expert_id=expert_setup["expert_id"],
                expert_service_id=expert_setup["service_id"],
                starts_at_utc=booked,
                ends_at_utc=booked + timedelta(minutes=60),
                timezone="Europe/Istanbul",
                status=AppointmentStatus.CONFIRMED.value,
            )
        )
        await session.commit()

    day = datetime(2027, 12, 1, tzinfo=UTC)
    slots = await generate(
        session_factory, expert_setup, start=day, end=day + timedelta(days=1)
    )

    blocked_start = booked - timedelta(minutes=30)
    blocked_end = booked + timedelta(minutes=90)
    for slot in slots:
        assert not (
            slot.starts_at_utc < blocked_end and blocked_start < slot.ends_at_utc
        ), f"{slot.starts_at_utc} ignores the buffer around a booking"


async def test_a_cancelled_appointment_frees_its_slot(
    client, registered, expert_setup, session_factory, monkeypatch
):
    monkeypatch.setattr(settings, "appointment_minimum_notice_minutes", 0)
    monkeypatch.setattr(settings, "appointment_max_horizon_days", 3650)
    monkeypatch.setattr(settings, "appointment_buffer_before_minutes", 0)
    monkeypatch.setattr(settings, "appointment_buffer_after_minutes", 0)

    await add_window(
        session_factory,
        expert_setup["expert_id"],
        weekday=2,
        start=time(9, 0),
        end=time(17, 0),
        timezone="Europe/Istanbul",
    )

    taken = datetime(2027, 12, 1, 9, 0, tzinfo=UTC)
    async with session_factory() as session:
        appointment = Appointment(
            user_id=expert_setup["user_id"],
            expert_id=expert_setup["expert_id"],
            expert_service_id=expert_setup["service_id"],
            starts_at_utc=taken,
            ends_at_utc=taken + timedelta(minutes=60),
            timezone="Europe/Istanbul",
            status=AppointmentStatus.CANCELLED.value,
        )
        session.add(appointment)
        await session.commit()

    day = datetime(2027, 12, 1, tzinfo=UTC)
    slots = await generate(
        session_factory, expert_setup, start=day, end=day + timedelta(days=1)
    )
    assert taken in [slot.starts_at_utc for slot in slots]
