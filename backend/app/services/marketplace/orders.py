"""Service orders: what was bought, on what terms.

Three things this file is careful about.

**The price is frozen.** An order stores its own amounts, its own commission
split and its own copy of the service title and duration. Reading the price
back through `expert_services` would be a live number wearing a historical
label: an expert raising their rate tomorrow would appear to have charged more
yesterday. Money is integer minor units throughout; no float touches it.

**Booking and ordering are one transaction.** An order whose appointment
failed, or an appointment whose order failed, are both worse than a clean
error. The caller commits once, at the end.

**No payment provider is integrated.** `payment_status` is a real typed state
and priced orders sit at `pending_payment`. Nothing here marks a priced order
paid - mocking that would produce a flow that works in development and fails
the first time money is involved.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, NotFound
from app.core.logging import get_logger
from app.db.models.marketplace import (
    Appointment,
    Expert,
    ExpertService,
    ServiceOrder,
    ServiceOrderSource,
)
from app.db.models.service import ServiceDefinition
from app.db.models.user import User
from app.domain.marketplace import (
    CancellationActor,
    DeliveryType,
    FulfillmentMode,
    Money,
    OrderSourceKind,
    OrderStatus,
    PaymentStatus,
)
from app.services.marketplace.booking import BookingService
from app.services.marketplace.experts import ExpertServiceManager

logger = get_logger(__name__)


class OrderNotCancellable(AppError):
    status_code = 409
    code = "order_not_cancellable"
    message = "This order can no longer be cancelled."


class IdempotencyConflict(AppError):
    status_code = 409
    code = "idempotency_conflict"
    message = "That idempotency key was already used with a different request."


class InvalidOrderRequest(AppError):
    status_code = 422
    code = "invalid_order_request"
    message = "That order cannot be created."


class SourceNotOwned(AppError):
    status_code = 404
    code = "source_not_found"
    message = "That source does not exist."


# Which table each source kind lives in, and the column that proves ownership.
# Linking a source to an order is not an access grant, but it must still be
# *the user's own* material - otherwise an order could reference a stranger's
# chart and leak its existence.
SOURCE_OWNERSHIP = {
    OrderSourceKind.BIRTH_PROFILE: ("birth_profiles", "user_id"),
    OrderSourceKind.SAVED_PERSON: ("saved_people", "user_id"),
    OrderSourceKind.CHART: ("charts", "user_id"),
    OrderSourceKind.COMPATIBILITY_REPORT: ("compatibility_reports", "user_id"),
    OrderSourceKind.HORARY_QUESTION: ("horary_questions", "user_id"),
    OrderSourceKind.DIVINATION_READING: ("divination_readings", "user_id"),
    OrderSourceKind.AI_REPORT: ("ai_reports", "user_id"),
}


class OrderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.booking = BookingService(session)
        self.offerings = ExpertServiceManager(session)

    # ------------------------------------------------------------ create

    async def create(
        self,
        user: User,
        *,
        expert_service_id: uuid.UUID | None = None,
        service_definition_id: uuid.UUID | None = None,
        starts_at_utc: datetime | None = None,
        display_timezone: str | None = None,
        sources: list[tuple[OrderSourceKind, uuid.UUID]] | None = None,
        notes: str | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[ServiceOrder, Appointment | None]:
        """Create an order, and its appointment when one is needed.

        Returns `(order, appointment)`. The caller commits; nothing here is
        durable until it does, which is what makes the pair atomic.
        """
        if idempotency_key:
            replay = await self._replay(user, idempotency_key, expert_service_id)
            if replay is not None:
                return replay

        if expert_service_id is not None:
            order, appointment = await self._create_expert_order(
                user,
                expert_service_id=expert_service_id,
                starts_at_utc=starts_at_utc,
                display_timezone=display_timezone,
                notes=notes,
                idempotency_key=idempotency_key,
            )
        elif service_definition_id is not None:
            order = await self._create_automated_order(
                user,
                service_definition_id=service_definition_id,
                notes=notes,
                idempotency_key=idempotency_key,
            )
            appointment = None
        else:
            raise InvalidOrderRequest(
                "An order needs either an expert service or a catalogue "
                "service."
            )

        for kind, source_id in sources or []:
            await self.attach_source(user, order, kind=kind, source_id=source_id)

        logger.info(
            "order_created",
            order_id=str(order.id),
            user_id=str(user.id),
            expert_id=str(order.expert_id) if order.expert_id else None,
            fulfillment_mode=order.fulfillment_mode,
            total_minor=order.total_minor,
            currency=order.currency,
            status=order.status,
            appointment_id=str(appointment.id) if appointment else None,
        )
        return order, appointment

    async def _replay(
        self,
        user: User,
        key: str,
        expert_service_id: uuid.UUID | None,
    ) -> tuple[ServiceOrder, Appointment | None] | None:
        """Return the original result for a repeated request.

        A mobile client on a flaky connection retries. Without this, a retry
        books a second appointment and charges twice for one intention.
        """
        existing = await self.session.scalar(
            select(ServiceOrder).where(
                ServiceOrder.user_id == user.id,
                ServiceOrder.idempotency_key == key,
            )
        )
        if existing is None:
            return None

        # Same key, different request: that is a client bug, and silently
        # returning the wrong order would hide it.
        if (
            expert_service_id is not None
            and existing.expert_service_id != expert_service_id
        ):
            raise IdempotencyConflict(
                "That idempotency key was used for a different service.",
                details={"order_id": str(existing.id)},
            )

        appointment = await self.session.scalar(
            select(Appointment).where(Appointment.service_order_id == existing.id)
        )
        logger.info("order_idempotent_replay", order_id=str(existing.id))
        return existing, appointment

    async def _create_expert_order(
        self,
        user: User,
        *,
        expert_service_id: uuid.UUID,
        starts_at_utc: datetime | None,
        display_timezone: str | None,
        notes: str | None,
        idempotency_key: str | None,
    ) -> tuple[ServiceOrder, Appointment | None]:
        offering = await self.offerings.get_public(expert_service_id)
        definition = await self.session.scalar(
            select(ServiceDefinition).where(
                ServiceDefinition.id == offering.service_definition_id
            )
        )
        if definition is None:  # pragma: no cover - FK guarantees it
            raise NotFound("That service is not in the catalogue.")

        expert = await self.session.scalar(
            select(Expert).where(Expert.id == offering.expert_id)
        )

        modes = {str(mode) for mode in (definition.fulfillment_modes or [])}
        mode = (
            FulfillmentMode.HYBRID
            if FulfillmentMode.HYBRID.value in modes
            else FulfillmentMode.EXPERT
        )

        price = Money(offering.price_minor, offering.currency)
        fee, net = price.split_commission(settings.marketplace_commission_bps)

        # A free service needs no payment step, so it does not pretend to wait
        # for one. A priced service waits for a provider that does not exist
        # yet, and says so honestly.
        free = price.amount_minor == 0
        order = ServiceOrder(
            user_id=user.id,
            service_definition_id=definition.id,
            expert_id=offering.expert_id,
            expert_service_id=offering.id,
            fulfillment_mode=mode.value,
            delivery_type=offering.delivery_type,
            status=(
                OrderStatus.CONFIRMED.value
                if free
                else OrderStatus.PENDING_PAYMENT.value
            ),
            payment_status=(
                PaymentStatus.NOT_REQUIRED.value
                if free
                else PaymentStatus.PENDING.value
            ),
            subtotal_minor=price.amount_minor,
            discount_minor=0,
            total_minor=price.amount_minor,
            currency=price.currency,
            commission_basis_points=settings.marketplace_commission_bps,
            platform_fee_minor=fee.amount_minor,
            expert_net_minor=net.amount_minor,
            # Snapshots: an edited offering cannot rewrite this order.
            service_title=offering.title,
            service_duration_minutes=offering.duration_minutes,
            notes=(notes or "").strip() or None,
            idempotency_key=idempotency_key,
            meta={
                "service_code": definition.code,
                "expert_display_name": expert.display_name if expert else None,
            },
        )
        self.session.add(order)
        await self.session.flush()

        appointment: Appointment | None = None
        if definition.supports_appointment and starts_at_utc is not None:
            timezone = display_timezone or (
                user.profile.timezone if user.profile else None
            ) or offering.expert.timezone if offering.expert else "UTC"

            hold = await self.booking.active_hold_for(
                user,
                expert_id=offering.expert_id,
                starts_at_utc=starts_at_utc,
            )
            appointment = await self.booking.book(
                user,
                service=offering,
                starts_at_utc=starts_at_utc,
                display_timezone=timezone,
                order=order,
                hold=hold,
            )
        elif definition.supports_appointment and starts_at_utc is None:
            raise InvalidOrderRequest(
                f"'{definition.code}' is delivered by appointment and needs a "
                "start time.",
                details={"service_code": definition.code},
            )

        # B11: what this order sells, classified for store policy, and which
        # rail may collect each part. Local import: payments depend on the
        # marketplace, not the other way round.
        from app.services.payments.order_payments import OrderPaymentService

        await OrderPaymentService(self.session).build(order, definition)
        return order, appointment

    async def _create_automated_order(
        self,
        user: User,
        *,
        service_definition_id: uuid.UUID,
        notes: str | None,
        idempotency_key: str | None,
    ) -> ServiceOrder:
        definition = await self.session.scalar(
            select(ServiceDefinition).where(
                ServiceDefinition.id == service_definition_id,
                ServiceDefinition.active.is_(True),
            )
        )
        if definition is None:
            raise NotFound("That service is not in the catalogue.")

        modes = {str(mode) for mode in (definition.fulfillment_modes or [])}
        if FulfillmentMode.AUTOMATED.value not in modes:
            raise InvalidOrderRequest(
                f"'{definition.code}' needs an expert and cannot be ordered "
                "directly.",
                details={"service_code": definition.code},
            )

        # Automated pricing arrives with subscriptions and entitlements; for
        # now an automated order carries no amount rather than a made-up one.
        order = ServiceOrder(
            user_id=user.id,
            service_definition_id=definition.id,
            fulfillment_mode=FulfillmentMode.AUTOMATED.value,
            delivery_type=DeliveryType.WRITTEN_REPORT.value,
            status=OrderStatus.PENDING.value,
            payment_status=PaymentStatus.NOT_REQUIRED.value,
            subtotal_minor=0,
            total_minor=0,
            currency=settings.marketplace_default_currency,
            commission_basis_points=0,
            platform_fee_minor=0,
            expert_net_minor=0,
            service_title=definition.name,
            service_duration_minutes=definition.estimated_duration_minutes,
            notes=(notes or "").strip() or None,
            idempotency_key=idempotency_key,
            meta={"service_code": definition.code},
        )
        self.session.add(order)
        await self.session.flush()

        # B11: an automated report is digital - paid only through a store,
        # and only if a store product is configured for it. Otherwise it stays
        # free, as it was.
        from app.services.payments.order_payments import OrderPaymentService

        await OrderPaymentService(self.session).build(order, definition)
        return order

    # ----------------------------------------------------------- sources

    async def attach_source(
        self,
        user: User,
        order: ServiceOrder,
        *,
        kind: OrderSourceKind,
        source_id: uuid.UUID,
        label: str | None = None,
    ) -> ServiceOrderSource:
        """Reference existing work from this order.

        Ownership is verified: an order may only point at the ordering user's
        own material. Attaching is *not* an access grant - an expert still
        needs consent to read any of it.
        """
        await self._require_owned_source(user, kind, source_id)

        existing = await self.session.scalar(
            select(ServiceOrderSource).where(
                ServiceOrderSource.order_id == order.id,
                ServiceOrderSource.source_kind == kind.value,
                ServiceOrderSource.source_id == source_id,
            )
        )
        if existing is not None:
            return existing

        link = ServiceOrderSource(
            order_id=order.id,
            source_kind=kind.value,
            source_id=source_id,
            label=label,
        )
        self.session.add(link)
        await self.session.flush()
        return link

    async def _require_owned_source(
        self, user: User, kind: OrderSourceKind, source_id: uuid.UUID
    ) -> None:
        from sqlalchemy import text

        table, column = SOURCE_OWNERSHIP[kind]
        found = await self.session.scalar(
            text(
                f"SELECT 1 FROM {table} WHERE id = :id AND {column} = :user_id"
            ).bindparams(id=source_id, user_id=user.id)
        )
        if not found:
            # 404 rather than 403: a wrong guess must not confirm the row
            # exists on somebody else's account.
            raise SourceNotOwned(details={"source_kind": kind.value})

    async def sources_for(self, order: ServiceOrder) -> list[ServiceOrderSource]:
        return list(
            await self.session.scalars(
                select(ServiceOrderSource).where(
                    ServiceOrderSource.order_id == order.id
                )
            )
        )

    # -------------------------------------------------------------- read

    async def get_for_user(self, user: User, order_id: uuid.UUID) -> ServiceOrder:
        order = await self.session.scalar(
            select(ServiceOrder).where(
                ServiceOrder.id == order_id,
                ServiceOrder.user_id == user.id,
                ServiceOrder.deleted_at.is_(None),
            )
        )
        if order is None:
            raise NotFound("Order not found.")
        return order

    async def get_for_expert(
        self, expert: Expert, order_id: uuid.UUID
    ) -> ServiceOrder:
        """An order as its expert sees it. Another expert's is a 404."""
        order = await self.session.scalar(
            select(ServiceOrder).where(
                ServiceOrder.id == order_id,
                ServiceOrder.expert_id == expert.id,
                ServiceOrder.deleted_at.is_(None),
            )
        )
        if order is None:
            raise NotFound("Order not found.")
        return order

    async def list_for_user(
        self, user: User, *, status: OrderStatus | None = None, limit: int = 50
    ) -> list[ServiceOrder]:
        statement = select(ServiceOrder).where(
            ServiceOrder.user_id == user.id,
            ServiceOrder.deleted_at.is_(None),
        )
        if status is not None:
            statement = statement.where(ServiceOrder.status == status.value)
        return list(
            await self.session.scalars(
                statement.order_by(ServiceOrder.created_at.desc()).limit(limit)
            )
        )

    async def list_for_expert(
        self, expert: Expert, *, status: OrderStatus | None = None, limit: int = 100
    ) -> list[ServiceOrder]:
        statement = select(ServiceOrder).where(
            ServiceOrder.expert_id == expert.id,
            ServiceOrder.deleted_at.is_(None),
        )
        if status is not None:
            statement = statement.where(ServiceOrder.status == status.value)
        return list(
            await self.session.scalars(
                statement.order_by(ServiceOrder.created_at.desc()).limit(limit)
            )
        )

    # ------------------------------------------------------ transitions

    async def cancel(
        self,
        order: ServiceOrder,
        *,
        actor: CancellationActor,
        reason: str | None = None,
    ) -> ServiceOrder:
        """Cancel an order and any live appointment with it.

        Delegates to the one cancellation path (`cancellation.py`), which the
        appointment routes use too - so cancelling by either door has the same
        financial outcome. A paid order becomes `refund_pending` with a single
        refund request awaiting review; `payment_status` never claims
        `refunded` before a provider says the money moved.
        """
        from app.services.marketplace.cancellation import CancellationService

        outcome = await CancellationService(self.session).cancel_order(
            order, actor=actor, reason=reason
        )
        return outcome.order or order

    async def mark_in_progress(self, order: ServiceOrder) -> ServiceOrder:
        order.status = OrderStatus.IN_PROGRESS.value
        await self.session.flush()
        return order

    async def complete(self, order: ServiceOrder) -> ServiceOrder:
        """Mark the order delivered.

        No route yet: completion belongs to the consultation surface. It
        exists here so a review can be anchored to a genuinely completed
        order rather than to an assumption.
        """
        if OrderStatus(order.status).is_terminal:
            raise OrderNotCancellable(
                f"An order that is {order.status} cannot be completed.",
                details={"status": order.status},
            )
        order.status = OrderStatus.COMPLETED.value
        order.completed_at = datetime.now(UTC)
        await self.session.flush()

        appointment = await self.session.scalar(
            select(Appointment).where(Appointment.service_order_id == order.id)
        )
        if appointment is not None and appointment.status in (
            "pending",
            "confirmed",
        ):
            await self.booking.complete(appointment)

        # B11: the expert's share may become available - only if a settlement
        # hold has been decided and has passed. Without one, nothing moves.
        from app.services.payments.settlement import SettlementService

        await SettlementService(self.session).release_order(order)

        logger.info("order_completed", order_id=str(order.id))
        return order

    def commission_preview(self, price_minor: int, currency: str) -> dict:
        """What the split would be, for display before purchase.

        Integer arithmetic, and rounding favours the expert: the platform fee
        is truncated and the remainder is theirs.
        """
        money = Money(price_minor, currency)
        fee, net = money.split_commission(settings.marketplace_commission_bps)
        return {
            "gross_amount_minor": money.amount_minor,
            "platform_fee_minor": fee.amount_minor,
            "expert_net_minor": net.amount_minor,
            "commission_basis_points": settings.marketplace_commission_bps,
            "currency": money.currency,
        }
