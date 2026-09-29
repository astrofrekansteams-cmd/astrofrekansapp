"""Completing a service: the step a review and a settlement are anchored to.

`OrderService.complete` has long been the transition; this is the surface that
decides *when* it may run, by service type:

* **Written analysis** (`written_report`): the expert delivers - a written
  note the user reads on the order - and delivering completes the order. The
  delivery is the service.
* **Live session** (`chat`, `voice`, `video`): completion is a separate
  business action after the session's start time, taken by either party.
  Ending a call never completes anything (docs/call_authorization.md): a
  dropped call is not a finished consultation, so a call ending only makes the
  "mark completed" action available once the appointment has begun.

Both require the order to be settled on the money side - paid, or free - and
alive: a cancelled, refund-pending or already completed order cannot be
completed. Completion then releases the expert's share only if the settlement
hold has been decided and has passed (`SettlementService.release_order`).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.db.models.marketplace import Appointment, ServiceOrder
from app.domain.chat import PushEvent
from app.domain.marketplace import DeliveryType, OrderStatus, PaymentStatus

logger = get_logger(__name__)

LIVE_DELIVERY = frozenset(
    {DeliveryType.CHAT.value, DeliveryType.VOICE.value, DeliveryType.VIDEO.value}
)
SETTLED_PAYMENT = frozenset(
    {PaymentStatus.PAID.value, PaymentStatus.NOT_REQUIRED.value}
)
DELIVERY_NOTE_MAX = 20_000


class OrderNotCompletable(AppError):
    status_code = 409
    code = "order_not_completable"
    message = "This order cannot be completed yet."


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def completion_block(
    order: ServiceOrder,
    appointment: Appointment | None,
    *,
    now: datetime | None = None,
) -> str | None:
    """Why this order cannot be completed now, or None if it can.

    One function for both the action and the button that offers it, so the
    client is never shown an action the server would refuse.
    """
    now = now or datetime.now(UTC)
    if order.expert_id is None:
        return "not_an_expert_order"
    if OrderStatus(order.status).is_terminal:
        return f"order_{order.status}"
    if order.status == OrderStatus.PENDING_PAYMENT.value:
        return "payment_pending"
    if order.payment_status not in SETTLED_PAYMENT:
        return f"payment_{order.payment_status}"
    if order.delivery_type == DeliveryType.WRITTEN_REPORT.value:
        return None
    if appointment is None:
        return "no_appointment"
    if appointment.status not in ("pending", "confirmed"):
        return f"appointment_{appointment.status}"
    if _aware(appointment.starts_at_utc) > now:
        return "session_not_started"
    return None


class CompletionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _appointment(self, order: ServiceOrder) -> Appointment | None:
        return await self.session.scalar(
            select(Appointment).where(Appointment.service_order_id == order.id)
        )

    async def complete_live(self, order: ServiceOrder, *, actor: str) -> ServiceOrder:
        """Mark a live session delivered. User or expert, after it began."""
        if order.status == OrderStatus.COMPLETED.value:
            return order  # a retry: already done, nothing moves twice
        if order.delivery_type == DeliveryType.WRITTEN_REPORT.value:
            raise OrderNotCompletable(
                "A written analysis is completed by its delivery.",
                details={"reason": "written_needs_delivery"},
            )
        blocked = completion_block(order, await self._appointment(order))
        if blocked is not None:
            raise OrderNotCompletable(details={"reason": blocked})
        return await self._complete(order, actor=actor)

    async def deliver_written(
        self, order: ServiceOrder, *, note: str
    ) -> ServiceOrder:
        """The expert hands over a written analysis; that completes it."""
        if order.status == OrderStatus.COMPLETED.value and (order.meta or {}).get("delivery"):
            return order
        if order.delivery_type != DeliveryType.WRITTEN_REPORT.value:
            raise OrderNotCompletable(
                "Only a written analysis is delivered this way.",
                details={"reason": "not_written"},
            )
        text = (note or "").strip()
        if not text:
            raise OrderNotCompletable(
                "The delivery needs its written analysis.",
                details={"reason": "empty_delivery"},
            )
        blocked = completion_block(order, await self._appointment(order))
        if blocked is not None:
            raise OrderNotCompletable(details={"reason": blocked})

        meta = dict(order.meta or {})
        meta["delivery"] = {
            "note": text[:DELIVERY_NOTE_MAX],
            "delivered_at": datetime.now(UTC).isoformat(),
        }
        # Reassigned, not mutated: a JSON column only notices a new value.
        order.meta = meta
        return await self._complete(order, actor="expert")

    async def _complete(self, order: ServiceOrder, *, actor: str) -> ServiceOrder:
        from app.services.marketplace.orders import OrderService

        meta = dict(order.meta or {})
        meta["completion"] = {"by": actor, "at": datetime.now(UTC).isoformat()}
        order.meta = meta
        await OrderService(self.session).complete(order)

        from app.services.notifications.outbox import OutboxService

        await OutboxService(self.session).enqueue(
            event=PushEvent.ORDER_STATUS_CHANGED,
            user_id=order.user_id,
            dedupe_key=f"order_completed:{order.id}:user",
            data={"order_id": str(order.id)},
            order_id=order.id,
        )
        logger.info("order_completion_recorded", order_id=str(order.id), actor=actor)
        return order
