"""Who may start or join a call, and when.

All of it here, as functions of loaded rows, so the create path, the join path
and every token reissue ask exactly the same question. The order it is asked
in is the order in the phase spec, and it matters: nothing reaches the provider
until every business check has passed. LiveKit enforces the grants it is given;
it never decides who deserves them.

    caller -> membership -> order -> expert -> offering -> payment
           -> delivery channel -> appointment -> window -> call state

Every refusal carries a machine-readable `reason`, so a client can explain it
without the server leaking anything else.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.core.exceptions import AppError
from app.db.models.marketplace import (
    Appointment,
    Expert,
    ExpertService,
    ServiceOrder,
)
from app.db.models.service import ServiceDefinition
from app.db.models.user import User
from app.domain.calls import CallType
from app.domain.marketplace import (
    AppointmentStatus,
    DeliveryType,
    ExpertStatus,
    FulfillmentMode,
    OrderStatus,
    PaymentStatus,
)

# ------------------------------------------------------------------ errors


class CallNotFound(AppError):
    status_code = 404
    code = "call_not_found"
    message = "Call not found."


class CallNotAllowed(AppError):
    status_code = 403
    code = "call_not_allowed"
    message = "This call is not available for this order."


class CallTooEarly(AppError):
    status_code = 409
    code = "call_too_early"
    message = "It is too early to join this call."


class CallWindowClosed(AppError):
    status_code = 409
    code = "call_window_closed"
    message = "The window for this call has closed."


class CallAlreadyEnded(AppError):
    status_code = 409
    code = "call_already_ended"
    message = "This call has already ended. Start a new call if the consultation allows it."


class CallTypeNotSupported(AppError):
    status_code = 422
    code = "call_type_not_supported"
    message = "This service does not include that kind of call."


class CallParticipantLimit(AppError):
    status_code = 409
    code = "call_participant_limit"
    message = "This call is already between its two participants."


# ----------------------------------------------------------------- policy

# Order states in which a consultation may happen live. `pending_payment` is
# absent: a call before payment is a free consultation.
CALLABLE_ORDER_STATES = frozenset(
    {
        OrderStatus.PAID.value,
        OrderStatus.CONFIRMED.value,
        OrderStatus.AWAITING_EXPERT.value,
        OrderStatus.IN_PROGRESS.value,
    }
)

LIVE_APPOINTMENT_STATES = frozenset(
    {AppointmentStatus.PENDING.value, AppointmentStatus.CONFIRMED.value}
)


@dataclass(slots=True, frozen=True)
class CallWindow:
    """When a call may be joined. `None` bounds mean unbounded on that side."""

    opens_at: datetime | None
    closes_at: datetime | None

    def contains(self, moment: datetime) -> bool:
        if self.opens_at is not None and moment < self.opens_at:
            return False
        if self.closes_at is not None and moment > self.closes_at:
            return False
        return True


def window_for(
    scheduled_start: datetime | None,
    scheduled_end: datetime | None,
    *,
    created_at: datetime | None = None,
) -> CallWindow:
    """The join window.

    Scheduled: from `CALL_JOIN_EARLY_SECONDS` before the start to
    `CALL_JOIN_LATE_SECONDS` after the **end**. After the end rather than the
    start, because a participant who drops at minute thirty must be able to get
    a fresh token and rejoin; the join token is not the call.

    Unscheduled (no service in today's catalogue works this way, but the rule
    should not assume that forever): open from creation, closed after the hard
    duration ceiling.
    """
    if scheduled_start is not None and scheduled_end is not None:
        return CallWindow(
            opens_at=scheduled_start
            - timedelta(seconds=settings.call_join_early_seconds),
            closes_at=scheduled_end
            + timedelta(seconds=settings.call_join_late_seconds),
        )
    if created_at is not None:
        return CallWindow(
            opens_at=None,
            closes_at=created_at
            + timedelta(seconds=settings.call_max_duration_seconds),
        )
    return CallWindow(opens_at=None, closes_at=None)


def _deny(reason: str, message: str | None = None) -> CallNotAllowed:
    return CallNotAllowed(message, details={"reason": reason})


def check_accounts(*accounts: User | None) -> None:
    """Both people must still have accounts that can sign in.

    The caller is already checked by authentication. The other party is
    checked here: a call with a deleted account is a call with nobody.
    """
    for account in accounts:
        if account is None or account.deleted_at is not None or not account.is_active:
            raise _deny("participant_unavailable")


def check_order(order: ServiceOrder) -> None:
    if order.deleted_at is not None:
        raise _deny("order_unavailable")
    if order.expert_id is None or order.expert_service_id is None:
        raise _deny("order_has_no_expert")
    if order.fulfillment_mode not in (
        FulfillmentMode.EXPERT.value,
        FulfillmentMode.HYBRID.value,
    ):
        raise _deny("order_is_automated")
    if order.status not in CALLABLE_ORDER_STATES:
        raise _deny(f"order_state_{order.status}")


def check_payment(order: ServiceOrder) -> None:
    """The payment invariant.

    A priced order must be PAID. `not_required` counts only when the order is
    actually free - a priced order carrying `not_required` is a data error, and
    treating it as permission would be a free consultation by accident.

    Nothing in this codebase marks a priced order PAID yet; that arrives with a
    payment provider. Until then, priced consultations cannot be joined in
    production - which is the correct failure.
    """
    if order.total_minor > 0:
        if order.payment_status != PaymentStatus.PAID.value:
            raise _deny("payment_required")
        return
    if order.payment_status not in (
        PaymentStatus.NOT_REQUIRED.value,
        PaymentStatus.PAID.value,
    ):
        raise _deny("payment_required")


def check_expert(order: ServiceOrder, expert: Expert | None) -> None:
    if expert is None or expert.id != order.expert_id:
        raise _deny("expert_mismatch")
    if expert.status == ExpertStatus.SUSPENDED.value:
        raise _deny("expert_suspended")
    if expert.status == ExpertStatus.INACTIVE.value or expert.deleted_at is not None:
        raise _deny("expert_unavailable")


def check_offering(order: ServiceOrder, offering: ExpertService | None) -> None:
    """The offering the order was bought from must belong to the order's expert.

    The order's snapshot of the channel is what counts, not the offering's
    current settings: an expert editing an offering tomorrow must not change
    what somebody already bought.
    """
    if offering is None or offering.expert_id != order.expert_id:
        raise _deny("offering_mismatch")


def check_call_type(
    order: ServiceOrder, definition: ServiceDefinition, call_type: CallType
) -> None:
    """The channel sold decides the call allowed.

    * AUDIO - the catalogue supports voice, and the order was for voice or
      video. Audio on a video order is a downgrade the customer may choose.
    * VIDEO - the catalogue supports video, and the order was for video. Video
      on a voice order would be an upgrade nobody paid for.

    A chat or written-report order gets no call at all.
    """
    delivery = order.delivery_type
    if call_type is CallType.AUDIO:
        if definition.supports_voice and delivery in (
            DeliveryType.VOICE.value,
            DeliveryType.VIDEO.value,
        ):
            return
    elif call_type is CallType.VIDEO:
        if definition.supports_video and delivery == DeliveryType.VIDEO.value:
            return
    raise CallTypeNotSupported(
        details={"call_type": call_type.value, "delivery_type": delivery}
    )


def check_appointment(
    order: ServiceOrder,
    definition: ServiceDefinition,
    appointment: Appointment | None,
    *,
    requested_appointment_id=None,  # noqa: ANN001 - uuid or None
) -> None:
    """An appointment-delivered service has no call without its appointment.

    No rule is invented for services that do not use appointments; today none
    of the voice or video services is one of them.
    """
    if requested_appointment_id is not None and (
        appointment is None or appointment.id != requested_appointment_id
    ):
        raise _deny("appointment_mismatch")

    if not definition.supports_appointment:
        return

    if appointment is None:
        raise _deny("appointment_required")
    if appointment.service_order_id != order.id:
        raise _deny("appointment_mismatch")
    if appointment.status not in LIVE_APPOINTMENT_STATES:
        raise _deny(f"appointment_{appointment.status}")


def check_window(window: CallWindow, now: datetime) -> None:
    if window.opens_at is not None and now < window.opens_at:
        raise CallTooEarly(details={"opens_at": window.opens_at.isoformat()})
    if window.closes_at is not None and now > window.closes_at:
        raise CallWindowClosed(details={"closed_at": window.closes_at.isoformat()})


def check_entitlement(
    *,
    order: ServiceOrder,
    definition: ServiceDefinition,
    expert: Expert | None,
    offering: ExpertService | None,
    appointment: Appointment | None,
    call_type: CallType,
    user_account: User | None,
    expert_account: User | None,
    requested_appointment_id=None,  # noqa: ANN001
) -> None:
    """Everything except the clock. Raises on the first failure."""
    check_accounts(user_account, expert_account)
    check_order(order)
    check_expert(order, expert)
    check_offering(order, offering)
    check_payment(order)
    check_call_type(order, definition, call_type)
    check_appointment(
        order,
        definition,
        appointment,
        requested_appointment_id=requested_appointment_id,
    )


def utcnow() -> datetime:
    return datetime.now(UTC)


def describe_policy() -> dict:
    """The policy as data, for `/calls/status` and the docs to agree on."""
    return {
        "callable_order_states": sorted(CALLABLE_ORDER_STATES),
        "join_early_seconds": settings.call_join_early_seconds,
        "join_late_seconds": settings.call_join_late_seconds,
        "ring_timeout_seconds": settings.call_ring_timeout_seconds,
        "reconnect_grace_seconds": settings.call_reconnect_grace_seconds,
        "max_duration_seconds": settings.call_max_duration_seconds,
        "token_ttl_seconds": settings.call_token_ttl_seconds,
        "recording": False,
    }
