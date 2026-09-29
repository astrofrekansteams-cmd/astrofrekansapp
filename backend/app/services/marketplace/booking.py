"""Holding and booking slots.

The invariant this file exists for: **one appointment per slot, per expert.**

"SELECT to check, then INSERT" does not achieve that. Two requests can both
run the SELECT before either runs the INSERT, and both find the slot free.
The window is milliseconds wide and it is exactly the window a popular
expert's 10:00 slot lives in.

So the real guarantee is a Postgres exclusion constraint over
`tstzrange(starts_at_utc, ends_at_utc)` for live appointments (see migration
0008). The application check below is still worth having - it produces a
readable error instead of an integrity violation, and it catches the common
case before any work is done - but it is the *second* line of defence, not the
first. When both run, the database wins and the loser gets a clean 409.

SQLite has no exclusion constraints, so the unit tests exercise the state
machine and the pre-check; the constraint itself is proven against real
Postgres by `scripts/booking_concurrency_check.py`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, NotFound
from app.core.logging import get_logger
from app.db.models.marketplace import (
    Appointment,
    Expert,
    ExpertService,
    ServiceOrder,
    SlotHold,
)
from app.db.models.user import User
from app.domain.chat import PushEvent
from app.domain.marketplace import (
    AppointmentStatus,
    CancellationActor,
    SlotHoldStatus,
)
from app.services.marketplace.slots import SlotGenerator, zone

logger = get_logger(__name__)

LIVE_APPOINTMENTS = (
    AppointmentStatus.PENDING.value,
    AppointmentStatus.CONFIRMED.value,
)

# Constraint names from migration 0008. Matching on them lets an integrity
# error be translated into the right domain error instead of a 500.
APPOINTMENT_OVERLAP_CONSTRAINT = "ex_appointments_no_overlap"
HOLD_OVERLAP_CONSTRAINT = "ex_slot_holds_no_overlap"


class SlotUnavailable(AppError):
    status_code = 409
    code = "slot_unavailable"
    message = "That time is no longer available."


class SlotNotOffered(AppError):
    status_code = 422
    code = "slot_not_offered"
    message = "That time is not one of this expert's available slots."


class AppointmentNotCancellable(AppError):
    status_code = 409
    code = "appointment_not_cancellable"
    message = "This appointment can no longer be cancelled."


def _is_overlap_violation(error: IntegrityError, constraint: str) -> bool:
    return constraint in str(getattr(error, "orig", error))


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.slots = SlotGenerator(session)

    # ------------------------------------------------------------- holds

    async def expire_stale_holds(self, expert_id: uuid.UUID | None = None) -> int:
        """Retire holds whose time has run out.

        Called before any availability decision. Without it an abandoned
        checkout would block a slot until somebody noticed, and the exclusion
        constraint would keep enforcing a claim nobody is using.
        """
        statement = (
            update(SlotHold)
            .where(
                SlotHold.status == SlotHoldStatus.ACTIVE.value,
                SlotHold.expires_at <= datetime.now(UTC),
            )
            .values(status=SlotHoldStatus.EXPIRED.value)
        )
        if expert_id is not None:
            statement = statement.where(SlotHold.expert_id == expert_id)

        try:
            result = await self.session.execute(statement)
        except IntegrityError:  # pragma: no cover - housekeeping, never fatal
            # Tidying up expired holds must never be the reason a booking
            # fails. Under concurrency several requests race to expire the same
            # rows; whoever loses simply carries on.
            await self.session.rollback()
            return 0
        return result.rowcount or 0

    async def hold_slot(
        self,
        user: User,
        *,
        service: ExpertService,
        starts_at_utc: datetime,
        ttl_seconds: int | None = None,
    ) -> SlotHold:
        """Claim a slot briefly while an order is placed."""
        await self.expire_stale_holds(service.expert_id)

        ends_at_utc = starts_at_utc + timedelta(minutes=service.duration_minutes)
        await self._require_offered(service, starts_at_utc)
        await self._require_free(service.expert_id, starts_at_utc, ends_at_utc)

        hold = SlotHold(
            user_id=user.id,
            expert_id=service.expert_id,
            expert_service_id=service.id,
            starts_at_utc=starts_at_utc,
            ends_at_utc=ends_at_utc,
            expires_at=datetime.now(UTC)
            + timedelta(seconds=ttl_seconds or settings.slot_hold_ttl_seconds),
            status=SlotHoldStatus.ACTIVE.value,
        )
        self.session.add(hold)

        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            if _is_overlap_violation(exc, HOLD_OVERLAP_CONSTRAINT):
                # Somebody else claimed it in the microseconds since the check.
                raise SlotUnavailable(
                    "Someone else is booking that time right now."
                ) from exc
            raise

        logger.info(
            "slot_hold_created",
            hold_id=str(hold.id),
            expert_id=str(service.expert_id),
            user_id=str(user.id),
            expires_in_seconds=ttl_seconds or settings.slot_hold_ttl_seconds,
        )
        return hold

    async def release_hold(self, hold: SlotHold, *, consumed: bool) -> SlotHold:
        hold.status = (
            SlotHoldStatus.CONSUMED.value
            if consumed
            else SlotHoldStatus.CANCELLED.value
        )
        await self.session.flush()
        return hold

    async def active_hold_for(
        self, user: User, *, expert_id: uuid.UUID, starts_at_utc: datetime
    ) -> SlotHold | None:
        return await self.session.scalar(
            select(SlotHold).where(
                SlotHold.user_id == user.id,
                SlotHold.expert_id == expert_id,
                SlotHold.starts_at_utc == starts_at_utc,
                SlotHold.status == SlotHoldStatus.ACTIVE.value,
                SlotHold.expires_at > datetime.now(UTC),
            )
        )

    # -------------------------------------------------------- validation

    async def _require_offered(
        self, service: ExpertService, starts_at_utc: datetime
    ) -> None:
        """The instant must be a slot the generator would have shown.

        Booking goes through the same generator as the slot list, so nothing
        can be booked that was never offered - a hand-crafted request for
        03:00 on a Sunday is refused even though the row would fit.
        """
        if not await self.slots.is_bookable(
            expert_id=service.expert_id,
            service=service,
            starts_at_utc=starts_at_utc,
        ):
            raise SlotNotOffered(
                "That time is not available for this service.",
                details={"starts_at_utc": starts_at_utc.isoformat()},
            )

    async def _require_free(
        self, expert_id: uuid.UUID, start: datetime, end: datetime
    ) -> None:
        """The readable half of the guarantee. The constraint is the real one."""
        clash = await self.session.scalar(
            select(Appointment.id).where(
                Appointment.expert_id == expert_id,
                Appointment.status.in_(LIVE_APPOINTMENTS),
                Appointment.starts_at_utc < end,
                Appointment.ends_at_utc > start,
            )
        )
        if clash is not None:
            raise SlotUnavailable()

        held = await self.session.scalar(
            select(SlotHold.id).where(
                SlotHold.expert_id == expert_id,
                SlotHold.status == SlotHoldStatus.ACTIVE.value,
                SlotHold.expires_at > datetime.now(UTC),
                SlotHold.starts_at_utc < end,
                SlotHold.ends_at_utc > start,
            )
        )
        if held is not None:
            raise SlotUnavailable(
                "Someone else is booking that time right now."
            )

    # -------------------------------------------------------- booking

    async def book(
        self,
        user: User,
        *,
        service: ExpertService,
        starts_at_utc: datetime,
        display_timezone: str,
        order: ServiceOrder | None = None,
        hold: SlotHold | None = None,
    ) -> Appointment:
        """Reserve the slot.

        The caller owns the transaction: an order and its appointment are
        committed together or not at all, so a failure here cannot leave an
        order pointing at a booking that does not exist.
        """
        await self.expire_stale_holds(service.expert_id)
        zone(display_timezone)

        ends_at_utc = starts_at_utc + timedelta(minutes=service.duration_minutes)

        if hold is not None:
            # Consume the caller's own hold *first*. Both the availability
            # check and the overlap check treat a live hold as busy, so a user
            # who reserved a slot would otherwise be refused their own booking.
            # A later failure rolls the transaction back, hold included.
            await self.release_hold(hold, consumed=True)

        await self._require_offered(service, starts_at_utc)
        await self._require_free(service.expert_id, starts_at_utc, ends_at_utc)

        appointment = Appointment(
            user_id=user.id,
            expert_id=service.expert_id,
            expert_service_id=service.id,
            service_order_id=order.id if order else None,
            starts_at_utc=starts_at_utc,
            ends_at_utc=ends_at_utc,
            timezone=display_timezone,
            status=AppointmentStatus.PENDING.value,
        )
        self.session.add(appointment)

        try:
            await self.session.flush()
        except IntegrityError as exc:
            # A failed flush leaves the session unusable until it is rolled
            # back. Doing that here - rather than leaving it to the caller -
            # means a lost race surfaces as a clean 409 instead of a
            # PendingRollbackError from the next statement anybody runs.
            await self.session.rollback()
            if _is_overlap_violation(exc, APPOINTMENT_OVERLAP_CONSTRAINT):
                # The database caught what the check could not: another
                # request booked this slot in between.
                logger.info(
                    "appointment_overlap_rejected",
                    expert_id=str(service.expert_id),
                    starts_at_utc=starts_at_utc.isoformat(),
                )
                raise SlotUnavailable() from exc
            raise

        logger.info(
            "appointment_booked",
            appointment_id=str(appointment.id),
            expert_id=str(service.expert_id),
            user_id=str(user.id),
            starts_at_utc=starts_at_utc.isoformat(),
            duration_minutes=service.duration_minutes,
        )

        # Notifications are queued, never sent inline: FCM being down must not
        # roll back a booking that succeeded. Enqueued in this transaction, so
        # there is no state where the appointment exists and nothing will be
        # sent - nor one where a notification promises a booking that rolled
        # back.
        await self._notify_booked(appointment, service)
        return appointment

    async def _notify_booked(
        self, appointment: Appointment, service: ExpertService
    ) -> None:
        from app.services.notifications.outbox import OutboxService

        outbox = OutboxService(self.session)
        expert = await self.session.scalar(
            select(Expert).where(Expert.id == appointment.expert_id)
        )

        await outbox.enqueue(
            event=PushEvent.APPOINTMENT_BOOKED,
            user_id=appointment.user_id,
            dedupe_key=f"appointment_booked:{appointment.id}:user",
            data={"appointment_id": str(appointment.id)},
            appointment_id=appointment.id,
        )
        if expert is not None:
            await outbox.enqueue(
                event=PushEvent.APPOINTMENT_BOOKED,
                user_id=expert.user_id,
                dedupe_key=f"appointment_booked:{appointment.id}:expert",
                data={"appointment_id": str(appointment.id)},
                appointment_id=appointment.id,
            )

        # Reminders are scheduled outbox rows, which is why this phase needs no
        # separate scheduler: the worker's "what is due" query is the scheduler.
        await outbox.enqueue_appointment_reminders(
            user_id=appointment.user_id,
            appointment_id=appointment.id,
            starts_at_utc=appointment.starts_at_utc,
        )

    # ----------------------------------------------------------- reading

    async def get_for_user(
        self, user: User, appointment_id: uuid.UUID
    ) -> Appointment:
        appointment = await self.session.scalar(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.user_id == user.id,
            )
        )
        if appointment is None:
            raise NotFound("Appointment not found.")
        return appointment

    async def get_for_expert(
        self, expert: Expert, appointment_id: uuid.UUID
    ) -> Appointment:
        appointment = await self.session.scalar(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.expert_id == expert.id,
            )
        )
        if appointment is None:
            raise NotFound("Appointment not found.")
        return appointment

    async def list_for_user(
        self,
        user: User,
        *,
        upcoming_only: bool = False,
        limit: int = 50,
    ) -> list[Appointment]:
        statement = select(Appointment).where(Appointment.user_id == user.id)
        if upcoming_only:
            statement = statement.where(
                Appointment.ends_at_utc >= datetime.now(UTC),
                Appointment.status.in_(LIVE_APPOINTMENTS),
            )
        return list(
            await self.session.scalars(
                statement.order_by(Appointment.starts_at_utc.desc()).limit(limit)
            )
        )

    async def list_for_expert(
        self,
        expert: Expert,
        *,
        upcoming_only: bool = False,
        limit: int = 100,
    ) -> list[Appointment]:
        statement = select(Appointment).where(Appointment.expert_id == expert.id)
        if upcoming_only:
            statement = statement.where(
                Appointment.ends_at_utc >= datetime.now(UTC),
                Appointment.status.in_(LIVE_APPOINTMENTS),
            )
        return list(
            await self.session.scalars(
                statement.order_by(Appointment.starts_at_utc).limit(limit)
            )
        )

    # ------------------------------------------------------ transitions

    async def cancel(
        self,
        appointment: Appointment,
        *,
        actor: CancellationActor,
        reason: str | None = None,
    ) -> Appointment:
        """Cancel, recording who did it.

        The actor is stored because refund policy will depend on it: an expert
        cancelling an hour beforehand is a different situation from a user
        cancelling a week out. No refund is computed in this phase, but the
        fact needed to compute one later is captured now, when it is known.
        """
        if appointment.status not in LIVE_APPOINTMENTS:
            raise AppointmentNotCancellable(
                f"An appointment that is {appointment.status} cannot be "
                "cancelled.",
                details={"status": appointment.status},
            )

        appointment.status = AppointmentStatus.CANCELLED.value
        appointment.cancelled_at = datetime.now(UTC)
        appointment.cancellation_actor = actor.value
        appointment.cancellation_reason = (reason or "").strip()[:300] or None
        await self.session.flush()

        logger.info(
            "appointment_cancelled",
            appointment_id=str(appointment.id),
            actor=actor.value,
        )

        from app.services.notifications.outbox import OutboxService

        outbox = OutboxService(self.session)
        # A reminder for something that is no longer happening is worse than no
        # reminder, so pending ones are dropped.
        await outbox.cancel_for_appointment(appointment.id)

        # And its calls stop with it (B10). Local import: calls depend on the
        # marketplace, not the other way round.
        from app.services.calls.factory import get_call_provider
        from app.services.calls.service import CallService

        await CallService(self.session, get_call_provider()).cancel_for_appointment(
            appointment.id
        )

        expert = await self.session.scalar(
            select(Expert).where(Expert.id == appointment.expert_id)
        )
        for recipient in filter(
            None,
            [appointment.user_id, expert.user_id if expert else None],
        ):
            await outbox.enqueue(
                event=PushEvent.APPOINTMENT_CANCELLED,
                user_id=recipient,
                dedupe_key=f"appointment_cancelled:{appointment.id}:{recipient}",
                data={"appointment_id": str(appointment.id)},
                appointment_id=appointment.id,
            )
        return appointment

    async def confirm(self, appointment: Appointment) -> Appointment:
        if appointment.status != AppointmentStatus.PENDING.value:
            raise AppointmentNotCancellable(
                "Only a pending appointment can be confirmed.",
                details={"status": appointment.status},
            )
        appointment.status = AppointmentStatus.CONFIRMED.value
        await self.session.flush()
        return appointment

    async def complete(self, appointment: Appointment) -> Appointment:
        """Mark the session as delivered. Expert or admin action.

        No route yet - the surface that drives this belongs to the
        consultation phase - but the transition is here so an order can be
        completed and reviewed without inventing state later.
        """
        if appointment.status not in LIVE_APPOINTMENTS:
            raise AppointmentNotCancellable(
                "Only a live appointment can be completed.",
                details={"status": appointment.status},
            )
        appointment.status = AppointmentStatus.COMPLETED.value
        await self.session.flush()
        return appointment

    async def mark_no_show(self, appointment: Appointment) -> Appointment:
        if appointment.status not in LIVE_APPOINTMENTS:
            raise AppointmentNotCancellable(
                "Only a live appointment can be marked as a no-show.",
                details={"status": appointment.status},
            )
        appointment.status = AppointmentStatus.NO_SHOW.value
        await self.session.flush()
        return appointment
