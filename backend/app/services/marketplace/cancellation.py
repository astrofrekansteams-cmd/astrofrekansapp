"""Cancelling a service: one path, whoever asks and whatever they point at.

Before this module a paid consultation could be cancelled two ways - through
its order or through its appointment - and the two disagreed about money. The
order path opened a refund review; the appointment path left the order
`confirmed` and the payment `paid`, so the user had nothing to follow and the
refund queue never heard of it.

Now every cancellation lands here:

* `cancel_order` - the user's order route (and `OrderService.cancel`).
* `cancel_appointment` - the user's and the expert's appointment routes. An
  appointment that belongs to an order cancels **the order**; the appointment
  goes with it. Only a bare appointment (booked directly, no order) is
  cancelled on its own.

One transaction, one outcome. The caller commits once:

1. the order row is locked (Postgres), so two cancels cannot both proceed;
2. live calls stop (`order_cancelled`);
3. the appointment is cancelled, reminders dropped, both parties notified;
4. open payment intents are closed, so a checkout started earlier cannot turn
   a cancelled order into a charge that nobody is tracking;
5. a paid order becomes `refund_pending` with **one** refund request awaiting
   review (idempotency key `cancel:{order_id}`). Nothing is refunded
   automatically - a person approves it and the provider moves the money.

Repeating a cancellation is a replay, not an error and not a second refund:
an order that is already cancelled comes back as it is.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.marketplace import Appointment, ServiceOrder
from app.db.models.payments import PaymentIntent, RefundRequest
from app.domain.marketplace import CancellationActor, OrderStatus
from app.domain.payments import PaymentIntentStatus

logger = get_logger(__name__)

# Intents that may still turn into a charge. Closing them is what stops a
# payment page left open in a browser from charging for a cancelled service.
OPEN_INTENTS = (
    PaymentIntentStatus.CREATED.value,
    PaymentIntentStatus.PENDING.value,
    PaymentIntentStatus.AUTHORIZED.value,
)


@dataclass(slots=True)
class CancellationOutcome:
    order: ServiceOrder | None
    appointment: Appointment | None
    refund_request: RefundRequest | None
    # True when nothing changed because this was already cancelled.
    replayed: bool = False


class CancellationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @property
    def _locks(self) -> bool:
        bind = self.session.bind
        return bind is not None and bind.dialect.name != "sqlite"

    async def _lock_order(self, order_id) -> ServiceOrder | None:  # noqa: ANN001
        statement = select(ServiceOrder).where(ServiceOrder.id == order_id)
        if self._locks:
            statement = statement.with_for_update()
        order = await self.session.scalar(statement)
        if order is not None:
            # Another request may have changed it while we waited for the lock.
            await self.session.refresh(order)
        return order

    async def _appointment_for(self, order: ServiceOrder) -> Appointment | None:
        return await self.session.scalar(
            select(Appointment).where(Appointment.service_order_id == order.id)
        )

    # ------------------------------------------------------------ entries

    async def cancel_order(
        self,
        order: ServiceOrder,
        *,
        actor: CancellationActor,
        reason: str | None = None,
    ) -> CancellationOutcome:
        from app.services.marketplace.orders import OrderNotCancellable

        locked = await self._lock_order(order.id) or order

        if locked.status == OrderStatus.CANCELLED.value:
            # A retried request. Same answer, no side effects.
            logger.info("order_cancel_replayed", order_id=str(locked.id))
            return CancellationOutcome(
                order=locked,
                appointment=await self._appointment_for(locked),
                refund_request=await self._cancel_refund(locked),
                replayed=True,
            )
        if OrderStatus(locked.status).is_terminal:
            raise OrderNotCancellable(
                f"An order that is {locked.status} cannot be cancelled.",
                details={"status": locked.status},
            )

        # Calls first (B10), so they record that the *order* was cancelled
        # rather than inheriting the appointment's reason below.
        from app.services.calls.factory import get_call_provider
        from app.services.calls.service import CallService

        await CallService(self.session, get_call_provider()).cancel_for_order(locked.id)

        appointment = await self._appointment_for(locked)
        if appointment is not None and appointment.status in ("pending", "confirmed"):
            from app.services.marketplace.booking import BookingService

            await BookingService(self.session).cancel(
                appointment, actor=actor, reason=reason
            )

        locked.status = OrderStatus.CANCELLED.value
        locked.cancelled_at = datetime.now(UTC)
        locked.cancellation_actor = actor.value
        locked.cancellation_reason = (reason or "").strip()[:300] or None
        await self.session.flush()

        await self._close_open_intents(locked)

        # B11: a paid order is not forgotten. It becomes `refund_pending` with
        # a refund request awaiting review; nothing is refunded automatically.
        from app.services.payments.refunds import RefundService

        refund = await RefundService(self.session).on_paid_order_cancelled(
            locked, actor=actor.value
        )

        logger.info(
            "order_cancelled",
            order_id=str(locked.id),
            actor=actor.value,
            payment_status=locked.payment_status,
            refund_request_id=str(refund.id) if refund else None,
        )
        return CancellationOutcome(
            order=locked, appointment=appointment, refund_request=refund
        )

    async def cancel_appointment(
        self,
        appointment: Appointment,
        *,
        actor: CancellationActor,
        reason: str | None = None,
    ) -> CancellationOutcome:
        """Cancel through the appointment - the same outcome as the order."""
        if appointment.service_order_id is not None:
            order = await self.session.get(ServiceOrder, appointment.service_order_id)
            if order is not None:
                if appointment.status in ("pending", "confirmed"):
                    # Its calls stop first, so they record the door the
                    # cancellation came through (docs/call_authorization.md).
                    # Nothing is committed if the order turns out not to be
                    # cancellable.
                    from app.services.calls.factory import get_call_provider
                    from app.services.calls.service import CallService

                    await CallService(
                        self.session, get_call_provider()
                    ).cancel_for_appointment(appointment.id)
                outcome = await self.cancel_order(order, actor=actor, reason=reason)
                await self.session.refresh(appointment)
                outcome.appointment = appointment
                return outcome

        # A bare appointment: no order, so no money and nothing to refund.
        from app.services.marketplace.booking import BookingService

        if appointment.status == "cancelled":
            return CancellationOutcome(
                order=None, appointment=appointment, refund_request=None, replayed=True
            )
        await BookingService(self.session).cancel(appointment, actor=actor, reason=reason)
        return CancellationOutcome(order=None, appointment=appointment, refund_request=None)

    # ---------------------------------------------------------- internals

    async def _close_open_intents(self, order: ServiceOrder) -> int:
        intents = list(
            await self.session.scalars(
                select(PaymentIntent).where(
                    PaymentIntent.order_id == order.id,
                    PaymentIntent.status.in_(OPEN_INTENTS),
                )
            )
        )
        for intent in intents:
            intent.status = PaymentIntentStatus.CANCELLED.value
        if intents:
            await self.session.flush()
            logger.info(
                "payment_intents_closed_on_cancel",
                order_id=str(order.id),
                count=len(intents),
            )
        return len(intents)

    async def _cancel_refund(self, order: ServiceOrder) -> RefundRequest | None:
        return await self.session.scalar(
            select(RefundRequest).where(
                RefundRequest.order_id == order.id,
                RefundRequest.idempotency_key == f"cancel:{order.id}",
            )
        )
