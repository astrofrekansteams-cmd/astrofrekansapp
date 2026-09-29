"""What an order means to the people looking at it.

`status` and `payment_status` are the truth, deliberately kept apart
(docs/orders.md). But a person reading their order needs one answer - "is it
scheduled, done, cancelled, is my money coming back?" - and every client
deriving that answer on its own is how two screens end up disagreeing.

So the server derives it once, from the stored facts, and never stores it:

| lifecycle            | when                                                  |
| -------------------- | ----------------------------------------------------- |
| `pending`            | waiting for payment, or not yet under way             |
| `paid`               | paid (or free) and waiting for the expert, no session |
| `scheduled`          | a live session in the future                          |
| `awaiting_completion`| the session has begun; completion not yet recorded    |
| `completed`          | delivered                                             |
| `cancelled`          | cancelled with nothing owed back                      |
| `refund_review`      | money is owed back and a person is reviewing it       |
| `refunded`           | a provider said the money went back                   |

Alongside it: what the caller may do now (`actions`), the latest refund
request, what cancelling would mean for money (`cancellation`), a written
delivery if there is one, and a timeline assembled from the timestamps the
order, its appointment, its payment and its refund requests already carry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.marketplace import Appointment, ServiceOrder
from app.db.models.payments import PaymentIntent, RefundRequest
from app.domain.marketplace import DeliveryType, OrderStatus, PaymentStatus
from app.domain.payments import PaymentIntentStatus, RefundStatus
from app.services.marketplace.completion import completion_block

LIVE_APPOINTMENT = ("pending", "confirmed")
CANCELLED_LIKE = (
    OrderStatus.CANCELLED.value,
    OrderStatus.REFUNDED.value,
    OrderStatus.FAILED.value,
)
REFUND_OPEN = (
    RefundStatus.REQUESTED.value,
    RefundStatus.MANUAL_REVIEW.value,
    RefundStatus.APPROVED.value,
    RefundStatus.PROCESSING.value,
)


def _aware(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def lifecycle_of(
    order: ServiceOrder,
    appointment: Appointment | None,
    latest_refund: RefundRequest | None,
    *,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(UTC)
    payment = order.payment_status
    refund_open = latest_refund is not None and latest_refund.status in REFUND_OPEN

    if payment == PaymentStatus.REFUNDED.value or order.status == OrderStatus.REFUNDED.value:
        return "refunded"
    if payment == PaymentStatus.REFUND_PENDING.value or refund_open:
        return "refund_review"
    if order.status in CANCELLED_LIKE:
        return "cancelled"
    if order.status == OrderStatus.COMPLETED.value:
        return "completed"
    if order.status in (OrderStatus.PENDING_PAYMENT.value, OrderStatus.DRAFT.value):
        return "pending"
    if payment not in (PaymentStatus.PAID.value, PaymentStatus.NOT_REQUIRED.value):
        return "pending"
    if appointment is not None and appointment.status in LIVE_APPOINTMENT:
        starts = _aware(appointment.starts_at_utc)
        return "scheduled" if starts and starts > now else "awaiting_completion"
    return "paid"


@dataclass(slots=True)
class OrderView:
    lifecycle: str
    actions: dict[str, bool]
    completion_block: str | None
    refund: dict[str, Any] | None
    cancellation: dict[str, Any]
    delivery: dict[str, Any] | None
    timeline: list[dict[str, Any]] = field(default_factory=list)


async def _latest_refund(session: AsyncSession, order: ServiceOrder) -> RefundRequest | None:
    return await session.scalar(
        select(RefundRequest)
        .where(RefundRequest.order_id == order.id)
        .order_by(RefundRequest.created_at.desc())
        .limit(1)
    )


async def _paid_intent(session: AsyncSession, order: ServiceOrder) -> PaymentIntent | None:
    return await session.scalar(
        select(PaymentIntent)
        .where(
            PaymentIntent.order_id == order.id,
            PaymentIntent.paid_at.is_not(None),
        )
        .order_by(PaymentIntent.paid_at)
        .limit(1)
    )


def _cancellation(order: ServiceOrder, intent: PaymentIntent | None, cancellable: bool) -> dict[str, Any]:
    """What cancelling now would mean for money. Advice for a confirmation."""
    if not cancellable:
        return {"allowed": False, "refund_outcome": "none", "refundable_minor": 0,
                "currency": order.currency}
    if order.payment_status in (
        PaymentStatus.PAID.value,
        PaymentStatus.PARTIALLY_REFUNDED.value,
    ) and intent is not None and intent.status in (
        PaymentIntentStatus.PAID.value,
        PaymentIntentStatus.PARTIALLY_REFUNDED.value,
    ):
        return {
            "allowed": True,
            # No percentage is promised: a person reviews every refund.
            "refund_outcome": "refund_review",
            "refundable_minor": max(intent.amount_minor - intent.refunded_minor, 0),
            "currency": intent.currency,
        }
    if order.payment_status == PaymentStatus.NOT_REQUIRED.value or order.total_minor == 0:
        return {"allowed": True, "refund_outcome": "free", "refundable_minor": 0,
                "currency": order.currency}
    return {"allowed": True, "refund_outcome": "not_paid", "refundable_minor": 0,
            "currency": order.currency}


def _iso(moment: datetime | None) -> str | None:
    moment = _aware(moment)
    return moment.isoformat() if moment else None


async def order_view(
    session: AsyncSession,
    order: ServiceOrder,
    *,
    as_expert: bool,
    now: datetime | None = None,
) -> OrderView:
    now = now or datetime.now(UTC)
    appointment = await session.scalar(
        select(Appointment).where(Appointment.service_order_id == order.id)
    )
    refund = await _latest_refund(session, order)
    intent = await _paid_intent(session, order)
    lifecycle = lifecycle_of(order, appointment, refund, now=now)
    blocked = completion_block(order, appointment, now=now)

    terminal = OrderStatus(order.status).is_terminal
    written = order.delivery_type == DeliveryType.WRITTEN_REPORT.value
    # The user may cancel their own order; an expert cancels a session
    # through its appointment, which reaches the same path.
    can_cancel = not terminal and (
        not as_expert
        or (appointment is not None and appointment.status in LIVE_APPOINTMENT)
    )
    actions = {
        "can_cancel": can_cancel,
        "can_complete": blocked is None and not written,
        "can_deliver": as_expert and blocked is None and written,
        "review_eligible": (
            not as_expert
            and order.status == OrderStatus.COMPLETED.value
            and order.expert_id is not None
        ),
    }

    meta = order.meta or {}
    delivery = meta.get("delivery") if isinstance(meta.get("delivery"), dict) else None

    timeline: list[dict[str, Any]] = [{"event": "created", "at": _iso(order.created_at)}]
    if intent is not None and intent.paid_at is not None:
        timeline.append({"event": "paid", "at": _iso(intent.paid_at)})
    if appointment is not None:
        timeline.append({"event": "session_scheduled", "at": _iso(appointment.starts_at_utc)})
    if delivery is not None:
        timeline.append({"event": "delivered", "at": delivery.get("delivered_at")})
    if order.completed_at is not None:
        timeline.append({"event": "completed", "at": _iso(order.completed_at)})
    if order.cancelled_at is not None:
        timeline.append({"event": "cancelled", "at": _iso(order.cancelled_at),
                         "actor": order.cancellation_actor})
    refunds = list(
        await session.scalars(
            select(RefundRequest)
            .where(RefundRequest.order_id == order.id)
            .order_by(RefundRequest.created_at)
        )
    )
    for row in refunds:
        timeline.append({"event": "refund_requested", "at": _iso(row.created_at)})
        if row.status == RefundStatus.REFUNDED.value and row.processed_at:
            timeline.append({"event": "refunded", "at": _iso(row.processed_at)})
        elif row.status == RefundStatus.DENIED.value and row.processed_at:
            timeline.append({"event": "refund_denied", "at": _iso(row.processed_at)})
    timeline = [item for item in timeline if item.get("at")]
    timeline.sort(key=lambda item: item["at"])

    return OrderView(
        lifecycle=lifecycle,
        actions=actions,
        completion_block=blocked,
        refund=(
            {
                "id": str(refund.id),
                "status": refund.status,
                "amount_minor": refund.amount_minor,
                "currency": refund.currency,
                "reason": refund.reason,
                "created_at": _iso(refund.created_at),
                "processed_at": _iso(refund.processed_at),
            }
            if refund is not None
            else None
        ),
        cancellation=_cancellation(order, intent, can_cancel),
        delivery=delivery,
        timeline=timeline,
    )
