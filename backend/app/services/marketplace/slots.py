"""Turning a weekly schedule into bookable slots.

The hard part is not the arithmetic, it is daylight saving time.

An expert says "Mondays, 09:00 to 12:00, Europe/Istanbul". That is a statement
about *local* time, and it stays true across a DST change - they still start
at nine. If we had converted it to UTC when it was saved, their morning would
silently move by an hour twice a year. So the schedule is stored local and
resolved to UTC per day, against that day's actual offset.

Two things then go wrong at a transition, and both are handled explicitly:

* **Spring forward**: 02:30 does not exist. `fold` cannot help; the time is
  simply not on the clock that day. Such a slot is skipped rather than
  silently shifted into 03:30, which would put an expert in a meeting they
  did not agree to.
* **Autumn back**: 02:30 happens twice, an hour apart, and both are real.
  Emitting one and discarding the other would lose an hour of genuine
  availability, so both are generated - they are different instants, and the
  UTC values prove it.

Everything leaves here in UTC. The presentation timezone travels alongside so
a client can render what the user will see, but nothing is ever scheduled
against a local string.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.db.models.marketplace import (
    Appointment,
    ExpertAvailability,
    ExpertAvailabilityException,
    ExpertService,
    SlotHold,
)
from app.domain.marketplace import (
    AppointmentStatus,
    AvailabilityExceptionType,
    SlotHoldStatus,
)

LIVE_APPOINTMENTS = (
    AppointmentStatus.PENDING.value,
    AppointmentStatus.CONFIRMED.value,
)


class InvalidTimezone(AppError):
    status_code = 422
    code = "invalid_timezone"
    message = "That is not a known IANA timezone."


class SlotRangeTooLarge(AppError):
    status_code = 422
    code = "slot_range_too_large"
    message = "That date range is longer than slots are generated for."


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
        raise InvalidTimezone(f"Unknown timezone: {name!r}") from exc


def local_time_exists(day: date, moment: time, tz: ZoneInfo) -> bool:
    """False for a local time that a DST spring-forward skipped.

    Python happily constructs 02:30 on a day when 02:30 never happened; the
    way to find out is to convert to UTC and back and see whether the clock
    agrees with itself.
    """
    naive = datetime.combine(day, moment)
    aware = naive.replace(tzinfo=tz)
    round_tripped = aware.astimezone(UTC).astimezone(tz)
    return (
        round_tripped.hour == moment.hour
        and round_tripped.minute == moment.minute
    )


def utc_instants(day: date, moment: time, tz: ZoneInfo) -> list[datetime]:
    """Every UTC instant this local time maps to on this day.

    Usually one. Zero when the clock skipped it (spring forward), and two
    when it happened twice (autumn back) - both of which are real bookable
    times, an hour apart.
    """
    naive = datetime.combine(day, moment)
    if not local_time_exists(day, moment, tz):
        return []

    first = naive.replace(tzinfo=tz, fold=0).astimezone(UTC)
    second = naive.replace(tzinfo=tz, fold=1).astimezone(UTC)
    return [first] if first == second else [first, second]


@dataclass(slots=True, frozen=True)
class Slot:
    """One bookable window. UTC is canonical; the rest is presentation."""

    starts_at_utc: datetime
    ends_at_utc: datetime
    display_timezone: str

    @property
    def local_start(self) -> datetime:
        return self.starts_at_utc.astimezone(zone(self.display_timezone))

    @property
    def local_end(self) -> datetime:
        return self.ends_at_utc.astimezone(zone(self.display_timezone))

    def overlaps(self, start: datetime, end: datetime) -> bool:
        return self.starts_at_utc < end and start < self.ends_at_utc


@dataclass(slots=True, frozen=True)
class BusyWindow:
    """Time that is already spoken for, with buffers already applied."""

    starts_at_utc: datetime
    ends_at_utc: datetime


class SlotGenerator:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -------------------------------------------------------- gathering

    async def _schedule(self, expert_id: uuid.UUID) -> list[ExpertAvailability]:
        rows = await self.session.scalars(
            select(ExpertAvailability).where(
                ExpertAvailability.expert_id == expert_id,
                ExpertAvailability.active.is_(True),
            )
        )
        return list(rows)

    async def _exceptions(
        self, expert_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[ExpertAvailabilityException]:
        rows = await self.session.scalars(
            select(ExpertAvailabilityException).where(
                ExpertAvailabilityException.expert_id == expert_id,
                ExpertAvailabilityException.ends_at_utc > start,
                ExpertAvailabilityException.starts_at_utc < end,
            )
        )
        return list(rows)

    async def _busy(
        self, expert_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[BusyWindow]:
        """Appointments and live holds, padded by the configured buffers.

        Buffers are applied here rather than at booking time so that a slot
        list and a booking attempt agree about what is free. If they
        disagreed, a user would be shown a slot that the booking then
        refused.
        """
        before = timedelta(minutes=settings.appointment_buffer_before_minutes)
        after = timedelta(minutes=settings.appointment_buffer_after_minutes)

        appointments = await self.session.scalars(
            select(Appointment).where(
                Appointment.expert_id == expert_id,
                Appointment.status.in_(LIVE_APPOINTMENTS),
                Appointment.ends_at_utc > start - after,
                Appointment.starts_at_utc < end + before,
            )
        )
        now = datetime.now(UTC)
        holds = await self.session.scalars(
            select(SlotHold).where(
                SlotHold.expert_id == expert_id,
                SlotHold.status == SlotHoldStatus.ACTIVE.value,
                SlotHold.expires_at > now,
                SlotHold.ends_at_utc > start - after,
                SlotHold.starts_at_utc < end + before,
            )
        )

        windows = [
            BusyWindow(row.starts_at_utc - before, row.ends_at_utc + after)
            for row in list(appointments) + list(holds)
        ]
        return windows

    # ------------------------------------------------------- generation

    def _windows_for_day(
        self,
        day: date,
        schedule: list[ExpertAvailability],
    ) -> list[tuple[datetime, datetime]]:
        """The expert's working windows on one local day, as UTC pairs."""
        windows: list[tuple[datetime, datetime]] = []

        for row in schedule:
            tz = zone(row.timezone)
            if day.weekday() != row.weekday:
                continue

            starts = utc_instants(day, row.start_local_time, tz)
            if not starts:
                # The whole window's start was skipped by a DST jump.
                continue

            for start_utc in starts:
                local_start = start_utc.astimezone(tz)
                # Measure the window in local wall-clock terms, then let the
                # zone decide how long that is in real time. An hour lost or
                # gained to DST inside the window is handled by the
                # conversion rather than by arithmetic on UTC.
                duration = datetime.combine(
                    day, row.end_local_time
                ) - datetime.combine(day, row.start_local_time)
                end_local_naive = (
                    local_start.replace(tzinfo=None) + duration
                )
                end_utc = end_local_naive.replace(
                    tzinfo=tz, fold=local_start.fold
                ).astimezone(UTC)
                if end_utc > start_utc:
                    windows.append((start_utc, end_utc))

        return windows

    def _apply_exceptions(
        self,
        windows: list[tuple[datetime, datetime]],
        exceptions: list[ExpertAvailabilityException],
    ) -> list[tuple[datetime, datetime]]:
        """Add extra availability, then subtract every blocking exception."""
        extra = [
            (row.starts_at_utc, row.ends_at_utc)
            for row in exceptions
            if AvailabilityExceptionType(row.exception_type).adds_time
        ]
        blocking = [
            (row.starts_at_utc, row.ends_at_utc)
            for row in exceptions
            if not AvailabilityExceptionType(row.exception_type).adds_time
        ]

        result = list(windows) + extra
        for block_start, block_end in blocking:
            trimmed: list[tuple[datetime, datetime]] = []
            for start, end in result:
                if block_end <= start or block_start >= end:
                    trimmed.append((start, end))
                    continue
                # The block may split a window in two.
                if start < block_start:
                    trimmed.append((start, block_start))
                if block_end < end:
                    trimmed.append((block_end, end))
            result = trimmed

        return sorted(result)

    async def generate(
        self,
        *,
        expert_id: uuid.UUID,
        service: ExpertService,
        start: datetime,
        end: datetime,
        display_timezone: str | None = None,
    ) -> list[Slot]:
        """Every bookable slot for this service in this window."""
        if (end - start).days > settings.appointment_max_slot_query_days:
            raise SlotRangeTooLarge(
                f"Slots are generated at most "
                f"{settings.appointment_max_slot_query_days} days at a time.",
                details={"requested_days": (end - start).days},
            )

        now = datetime.now(UTC)
        earliest = now + timedelta(
            minutes=settings.appointment_minimum_notice_minutes
        )
        latest = now + timedelta(days=settings.appointment_max_horizon_days)

        start = max(start, earliest)
        end = min(end, latest)
        if start >= end:
            return []

        schedule = await self._schedule(expert_id)
        exceptions = await self._exceptions(expert_id, start, end)
        busy = await self._busy(expert_id, start, end)

        if not schedule and not any(
            AvailabilityExceptionType(row.exception_type).adds_time
            for row in exceptions
        ):
            return []

        timezone_name = display_timezone or (
            schedule[0].timezone if schedule else "UTC"
        )
        zone(timezone_name)  # validate early, not per slot

        duration = timedelta(minutes=service.duration_minutes)
        step = timedelta(
            minutes=settings.appointment_slot_granularity_minutes
        )

        # Walk a day either side of the range: a window that starts late in
        # the expert's local evening can land inside the requested UTC range
        # while belonging to the previous or next local day.
        windows: list[tuple[datetime, datetime]] = []
        day = (start - timedelta(days=1)).date()
        final_day = (end + timedelta(days=1)).date()
        while day <= final_day:
            windows.extend(self._windows_for_day(day, schedule))
            day += timedelta(days=1)

        windows = self._apply_exceptions(windows, exceptions)

        slots: list[Slot] = []
        seen: set[datetime] = set()

        for window_start, window_end in windows:
            cursor = window_start
            while cursor + duration <= window_end:
                slot_start = cursor
                slot_end = cursor + duration
                cursor += step

                if slot_start < start or slot_end > end:
                    continue
                if slot_start in seen:
                    continue
                if any(
                    slot_start < window.ends_at_utc
                    and window.starts_at_utc < slot_end
                    for window in busy
                ):
                    continue

                seen.add(slot_start)
                slots.append(
                    Slot(
                        starts_at_utc=slot_start,
                        ends_at_utc=slot_end,
                        display_timezone=timezone_name,
                    )
                )

        return sorted(slots, key=lambda item: item.starts_at_utc)

    async def is_bookable(
        self,
        *,
        expert_id: uuid.UUID,
        service: ExpertService,
        starts_at_utc: datetime,
    ) -> bool:
        """Whether one specific instant is a slot the generator would offer.

        Booking re-checks through the same generator rather than through a
        cheaper shortcut, so a slot can never be booked that the list would
        not have shown.
        """
        duration = timedelta(minutes=service.duration_minutes)
        slots = await self.generate(
            expert_id=expert_id,
            service=service,
            start=starts_at_utc - timedelta(minutes=1),
            end=starts_at_utc + duration + timedelta(minutes=1),
        )
        return any(slot.starts_at_utc == starts_at_utc for slot in slots)
