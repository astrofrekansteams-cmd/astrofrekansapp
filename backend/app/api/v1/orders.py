"""Orders, appointments, consent and reviews.

Every route here is owner-scoped. A user sees their own orders; an expert sees
orders placed with them. Someone else's is a `404`, never a `403` - a wrong
guess must not confirm that a row exists.

Consent lives under the user's own order on purpose: only the person whose data
it is may grant or revoke it, and the route shape makes that structural rather
than something a reviewer has to notice.

No payment provider is integrated. A priced order is created at
`pending_payment` and stays there; nothing in this file marks it paid.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, UserRateLimit
from app.core.config import settings
from app.core.exceptions import AppError
from app.db.models.marketplace import (
    Appointment,
    Expert,
    ExpertService,
    ServiceOrder,
)
from app.db.models.service import ServiceDefinition
from app.domain.marketplace import (
    AppointmentStatus,
    CancellationActor,
    ConsentScope,
    DeliveryType,
    FulfillmentMode,
    OrderSourceKind,
    OrderStatus,
    PaymentStatus,
)
from app.schemas.common import Message
from app.schemas.marketplace import (
    AppointmentCreateRequest,
    AppointmentResponse,
    CancellationPreviewResponse,
    CancelRequest,
    CommissionResponse,
    DeliverRequest,
    OrderActionsResponse,
    OrderDeliveryResponse,
    OrderRefundResponse,
    OrderTimelineEvent,
    ConsentResponse,
    ConsentUpdateRequest,
    MoneyResponse,
    OrderCreateRequest,
    OrderResponse,
    OrderSourceResponse,
    OrderSummary,
    ReviewCreateRequest,
    ReviewResponse,
    ReviewUpdateRequest,
)
from app.services.marketplace.booking import BookingService
from app.services.marketplace.cancellation import CancellationService
from app.services.marketplace.completion import CompletionService
from app.services.marketplace.consent import ConsentService
from app.services.marketplace.discovery import FavoriteService, ReviewService
from app.services.marketplace.experts import (
    ExpertProfileService,
    ExpertServiceManager,
)
from app.services.marketplace.lifecycle import lifecycle_of, order_view
from app.services.marketplace.orders import OrderService
from app.services.marketplace.slots import zone

router = APIRouter(tags=["orders"])

_order_limit = Depends(
    UserRateLimit(settings.order_create_rate_limit, scope="order_create")
)
_booking_limit = Depends(
    UserRateLimit(
        settings.appointment_booking_rate_limit, scope="appointment_booking"
    )
)
_review_limit = Depends(
    UserRateLimit(settings.review_create_rate_limit, scope="review_create")
)


# ----------------------------------------------------------- serialisation


def _money(amount_minor: int, currency: str) -> MoneyResponse:
    return MoneyResponse(amount_minor=amount_minor, currency=currency)


def _appointment(appointment: Appointment) -> AppointmentResponse:
    return AppointmentResponse(
        id=appointment.id,
        expert_id=appointment.expert_id,
        expert_service_id=appointment.expert_service_id,
        service_order_id=appointment.service_order_id,
        starts_at_utc=appointment.starts_at_utc,
        ends_at_utc=appointment.ends_at_utc,
        starts_at_local=appointment.starts_at_utc.astimezone(
            zone(appointment.timezone)
        ),
        timezone=appointment.timezone,
        status=AppointmentStatus(appointment.status),
        cancelled_at=appointment.cancelled_at,
        cancellation_actor=(
            CancellationActor(appointment.cancellation_actor)
            if appointment.cancellation_actor
            else None
        ),
        cancellation_reason=appointment.cancellation_reason,
        created_at=appointment.created_at,
    )


async def _order_to_schema(
    session,  # noqa: ANN001
    order: ServiceOrder,
    *,
    for_expert: Expert | None = None,
) -> OrderResponse:
    definition = await session.scalar(
        select(ServiceDefinition).where(
            ServiceDefinition.id == order.service_definition_id
        )
    )
    appointment = await session.scalar(
        select(Appointment).where(Appointment.service_order_id == order.id)
    )

    consents = ConsentService(session)
    sources = await OrderService(session).sources_for(order)

    if for_expert is not None:
        # For an expert, each reference says whether consent actually allows
        # reading it. A reference is not permission.
        readable = {
            (item.source_kind, item.source_id)
            for item in await consents.readable_sources(for_expert, order.id)
        }
        source_payload = [
            OrderSourceResponse(
                source_kind=OrderSourceKind(item.source_kind),
                source_id=item.source_id,
                label=item.label,
                readable=(item.source_kind, item.source_id) in readable,
            )
            for item in sources
        ]
        granted = [
            ConsentScope(scope)
            for scope in await consents.granted_scopes(for_expert, order.id)
        ]
    else:
        source_payload = [
            OrderSourceResponse(
                source_kind=OrderSourceKind(item.source_kind),
                source_id=item.source_id,
                label=item.label,
            )
            for item in sources
        ]
        granted = [
            ConsentScope(row.scope)
            for row in await consents.list_for_order_unchecked(order.id)
            if row.revoked_at is None
        ]

    view = await order_view(session, order, as_expert=for_expert is not None)
    return OrderResponse(
        id=order.id,
        service_code=(order.meta or {}).get("service_code")
        or (definition.code if definition else ""),
        fulfillment_mode=FulfillmentMode(order.fulfillment_mode),
        delivery_type=(
            DeliveryType(order.delivery_type) if order.delivery_type else None
        ),
        status=OrderStatus(order.status),
        payment_status=PaymentStatus(order.payment_status),
        expert_id=order.expert_id,
        expert_display_name=(order.meta or {}).get("expert_display_name"),
        expert_service_id=order.expert_service_id,
        service_title=order.service_title,
        service_duration_minutes=order.service_duration_minutes,
        subtotal=_money(order.subtotal_minor, order.currency),
        discount_minor=order.discount_minor,
        total=_money(order.total_minor, order.currency),
        commission=CommissionResponse(
            gross_amount_minor=order.total_minor,
            platform_fee_minor=order.platform_fee_minor,
            expert_net_minor=order.expert_net_minor,
            commission_basis_points=order.commission_basis_points,
        ),
        appointment=_appointment(appointment) if appointment else None,
        sources=source_payload,
        granted_consent_scopes=granted,
        notes=order.notes,
        completed_at=order.completed_at,
        cancelled_at=order.cancelled_at,
        cancellation_actor=(
            CancellationActor(order.cancellation_actor)
            if order.cancellation_actor
            else None
        ),
        cancellation_reason=order.cancellation_reason,
        created_at=order.created_at,
        lifecycle=view.lifecycle,
        actions=OrderActionsResponse(**view.actions),
        completion_block=view.completion_block,
        refund=OrderRefundResponse(**view.refund) if view.refund else None,
        cancellation=CancellationPreviewResponse(**view.cancellation),
        delivery=OrderDeliveryResponse(**view.delivery) if view.delivery else None,
        timeline=[OrderTimelineEvent(**item) for item in view.timeline],
    )


async def _summary(session, order: ServiceOrder) -> OrderSummary:  # noqa: ANN001
    from app.db.models.payments import RefundRequest

    booked = await session.scalar(
        select(Appointment).where(Appointment.service_order_id == order.id)
    )
    appointment = booked.starts_at_utc if booked else None
    latest_refund = await session.scalar(
        select(RefundRequest)
        .where(RefundRequest.order_id == order.id)
        .order_by(RefundRequest.created_at.desc())
        .limit(1)
    )
    return OrderSummary(
        id=order.id,
        service_code=(order.meta or {}).get("service_code", ""),
        service_title=order.service_title,
        status=OrderStatus(order.status),
        payment_status=PaymentStatus(order.payment_status),
        total=_money(order.total_minor, order.currency),
        expert_id=order.expert_id,
        expert_display_name=(order.meta or {}).get("expert_display_name"),
        appointment_starts_at_utc=appointment,
        created_at=order.created_at,
        lifecycle=lifecycle_of(order, booked, latest_refund),
    )


class SlotDateMismatch(AppError):
    status_code = 422
    code = "slot_date_mismatch"
    message = "The chosen time is not on the day that was selected."


def _require_selected_day(payload: OrderCreateRequest) -> None:
    """The slot must be on the day the person was looking at.

    Only checked when the client says which day that was: the instant plus the
    UTC offset it was displayed with gives the wall-clock day it was shown on.
    """
    if (
        payload.starts_at_utc is None
        or payload.selected_local_date is None
        or payload.selected_utc_offset_minutes is None
    ):
        return
    starts = payload.starts_at_utc
    if starts.tzinfo is None:
        starts = starts.replace(tzinfo=UTC)
    shown = (
        starts.astimezone(UTC)
        + timedelta(minutes=payload.selected_utc_offset_minutes)
    ).date()
    if shown != payload.selected_local_date:
        raise SlotDateMismatch(
            details={
                "selected_local_date": payload.selected_local_date.isoformat(),
                "slot_local_date": shown.isoformat(),
            }
        )


# ------------------------------------------------------------------ orders


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_order_limit],
    summary="Place an order",
    description=(
        "Creates the order and, for a service delivered by appointment, books "
        "the slot in the same transaction - so there is never an order "
        "pointing at a booking that does not exist, or the reverse.\n\n"
        "Send `Idempotency-Key` and a retried request returns the original "
        "order instead of placing a second one. No payment provider is "
        "integrated: a priced order is created at `pending_payment`."
    ),
)
async def create_order(
    payload: OrderCreateRequest,
    user: CurrentUser,
    session: DbSession,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> OrderResponse:
    _require_selected_day(payload)
    service = OrderService(session)
    order, _ = await service.create(
        user,
        expert_service_id=payload.expert_service_id,
        service_definition_id=payload.service_definition_id,
        starts_at_utc=payload.starts_at_utc,
        display_timezone=payload.display_timezone,
        sources=[
            (item.source_kind, item.source_id) for item in payload.sources
        ],
        notes=payload.notes,
        idempotency_key=idempotency_key,
    )
    await session.commit()
    return await _order_to_schema(session, order)


@router.get(
    "/orders",
    response_model=list[OrderSummary],
    summary="Your orders",
)
async def list_orders(
    user: CurrentUser,
    session: DbSession,
    order_status: OrderStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[OrderSummary]:
    rows = await OrderService(session).list_for_user(
        user, status=order_status, limit=limit
    )
    return [await _summary(session, row) for row in rows]


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="One of your orders",
)
async def get_order(
    order_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> OrderResponse:
    order = await OrderService(session).get_for_user(user, order_id)
    return await _order_to_schema(session, order)


@router.post(
    "/orders/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Cancel your order",
    description=(
        "Cancels the order and any live appointment with it, through the same "
        "path as an appointment cancellation. A paid order becomes "
        "`refund_pending` with one refund request awaiting review; nothing is "
        "refunded automatically. Repeating the request returns the cancelled "
        "order unchanged - it never opens a second refund."
    ),
)
async def cancel_order(
    order_id: uuid.UUID,
    payload: CancelRequest,
    user: CurrentUser,
    session: DbSession,
) -> OrderResponse:
    service = OrderService(session)
    order = await service.get_for_user(user, order_id)
    await service.cancel(
        order, actor=CancellationActor.USER, reason=payload.reason
    )
    await session.commit()
    return await _order_to_schema(session, order)


@router.post(
    "/orders/{order_id}/complete",
    response_model=OrderResponse,
    summary="Confirm a live session took place",
    description=(
        "For a live session (chat, voice, video) whose start time has passed. "
        "Ending a call never completes an order; this does. Completion opens "
        "the review and lets the expert's share settle once the hold passes. "
        "Repeating it is harmless."
    ),
)
async def complete_order(
    order_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> OrderResponse:
    order = await OrderService(session).get_for_user(user, order_id)
    await CompletionService(session).complete_live(order, actor="user")
    await session.commit()
    return await _order_to_schema(session, order)


# ----------------------------------------------------------- appointments


@router.post(
    "/appointments",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_booking_limit],
    summary="Book a slot directly",
    description=(
        "For a free or already-paid engagement. Most bookings go through "
        "`POST /orders`, which creates the order and the appointment together."
    ),
)
async def create_appointment(
    payload: AppointmentCreateRequest, user: CurrentUser, session: DbSession
) -> AppointmentResponse:
    offering = await ExpertServiceManager(session).get_public(
        payload.expert_service_id
    )
    expert = await session.scalar(
        select(Expert).where(Expert.id == offering.expert_id)
    )
    display = (
        payload.display_timezone
        or (user.profile.timezone if user.profile else None)
        or (expert.timezone if expert else "UTC")
    )

    booking = BookingService(session)
    hold = await booking.active_hold_for(
        user, expert_id=offering.expert_id, starts_at_utc=payload.starts_at_utc
    )
    appointment = await booking.book(
        user,
        service=offering,
        starts_at_utc=payload.starts_at_utc,
        display_timezone=display,
        hold=hold,
    )
    await session.commit()
    return _appointment(appointment)


@router.get(
    "/appointments",
    response_model=list[AppointmentResponse],
    summary="Your appointments",
)
async def list_appointments(
    user: CurrentUser,
    session: DbSession,
    upcoming: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AppointmentResponse]:
    rows = await BookingService(session).list_for_user(
        user, upcoming_only=upcoming, limit=limit
    )
    return [_appointment(row) for row in rows]


@router.get(
    "/appointments/{appointment_id}",
    response_model=AppointmentResponse,
    summary="One of your appointments",
)
async def get_appointment(
    appointment_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> AppointmentResponse:
    appointment = await BookingService(session).get_for_user(
        user, appointment_id
    )
    return _appointment(appointment)


@router.post(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    summary="Cancel your appointment",
)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    payload: CancelRequest,
    user: CurrentUser,
    session: DbSession,
) -> AppointmentResponse:
    booking = BookingService(session)
    appointment = await booking.get_for_user(user, appointment_id)
    # The same path as cancelling the order: its refund, its calls, its
    # payment - not just the appointment row.
    await CancellationService(session).cancel_appointment(
        appointment, actor=CancellationActor.USER, reason=payload.reason
    )
    await session.commit()
    return _appointment(appointment)


# ---------------------------------------------------------------- consent


@router.get(
    "/orders/{order_id}/consents",
    response_model=list[ConsentResponse],
    summary="What you have shared for this order",
)
async def list_consents(
    order_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> list[ConsentResponse]:
    rows = await ConsentService(session).list_for_order(user, order_id)
    return [
        ConsentResponse(
            scope=ConsentScope(row.scope),
            granted_at=row.granted_at,
            revoked_at=row.revoked_at,
            active=row.revoked_at is None,
        )
        for row in rows
    ]


@router.put(
    "/orders/{order_id}/consents",
    response_model=list[ConsentResponse],
    summary="Set exactly what you share for this order",
    description=(
        "The complete set: anything absent is revoked. Only the user whose "
        "data it is may call this - an expert cannot grant consent on "
        "somebody's behalf."
    ),
)
async def set_consents(
    order_id: uuid.UUID,
    payload: ConsentUpdateRequest,
    user: CurrentUser,
    session: DbSession,
) -> list[ConsentResponse]:
    rows = await ConsentService(session).set_scopes(
        user, order_id, payload.scopes
    )
    await session.commit()
    return [
        ConsentResponse(
            scope=ConsentScope(row.scope),
            granted_at=row.granted_at,
            revoked_at=row.revoked_at,
            active=row.revoked_at is None,
        )
        for row in rows
    ]


# ---------------------------------------------------------------- reviews


@router.post(
    "/orders/{order_id}/review",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_review_limit],
    summary="Review a completed order",
    description=(
        "Only a completed order with an expert can be reviewed, once. A rating "
        "anchored to nothing is free to manufacture, so it is anchored to a "
        "transaction."
    ),
)
async def create_review(
    order_id: uuid.UUID,
    payload: ReviewCreateRequest,
    user: CurrentUser,
    session: DbSession,
) -> ReviewResponse:
    review = await ReviewService(session).create(
        user, order_id, rating=payload.rating, comment=payload.comment
    )
    await session.commit()
    return ReviewResponse(
        id=review.id,
        expert_id=review.expert_id,
        order_id=review.order_id,
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


@router.patch(
    "/reviews/{review_id}",
    response_model=ReviewResponse,
    summary="Edit your review",
)
async def update_review(
    review_id: uuid.UUID,
    payload: ReviewUpdateRequest,
    user: CurrentUser,
    session: DbSession,
) -> ReviewResponse:
    review = await ReviewService(session).update(
        user, review_id, rating=payload.rating, comment=payload.comment
    )
    await session.commit()
    return ReviewResponse(
        id=review.id,
        expert_id=review.expert_id,
        order_id=review.order_id,
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


@router.delete(
    "/reviews/{review_id}",
    response_model=Message,
    summary="Delete your review",
)
async def delete_review(
    review_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> Message:
    await ReviewService(session).delete(user, review_id)
    await session.commit()
    return Message(message="Review deleted.")


# -------------------------------------------------------------- favorites


@router.get(
    "/favorites/experts",
    response_model=None,
    summary="Your favourite experts",
)
async def list_favorites(user: CurrentUser, session: DbSession):
    from app.api.v1.marketplace import _summary as expert_summary
    from app.services.marketplace.discovery import ExpertSearchService

    experts = await FavoriteService(session).list_experts(user)
    search = ExpertSearchService(session)
    result = []
    for expert in experts:
        cheapest = await search.cheapest_offering(expert.id)
        summary = expert_summary(
            expert,
            from_price=(
                _money(cheapest.price_minor, cheapest.currency)
                if cheapest
                else None
            ),
            is_favorite=True,
        )
        result.append(summary)
    return result


# ------------------------------------------------------------ expert view


expert_router = APIRouter(prefix="/expert", tags=["expert-workspace"])


@expert_router.get(
    "/orders",
    response_model=list[OrderSummary],
    summary="Orders placed with you",
)
async def list_expert_orders(
    user: CurrentUser,
    session: DbSession,
    order_status: OrderStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[OrderSummary]:
    expert = await ExpertProfileService(session).get_own(user)
    rows = await OrderService(session).list_for_expert(
        expert, status=order_status, limit=limit
    )
    return [await _summary(session, row) for row in rows]


@expert_router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="One order placed with you",
    description=(
        "Each referenced source says whether consent actually allows you to "
        "read it. A reference is not permission."
    ),
)
async def get_expert_order(
    order_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> OrderResponse:
    expert = await ExpertProfileService(session).get_own(user)
    order = await OrderService(session).get_for_expert(expert, order_id)
    return await _order_to_schema(session, order, for_expert=expert)


@expert_router.get(
    "/appointments",
    response_model=list[AppointmentResponse],
    summary="Your appointments as an expert",
)
async def list_expert_appointments(
    user: CurrentUser,
    session: DbSession,
    upcoming: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[AppointmentResponse]:
    expert = await ExpertProfileService(session).get_own(user)
    rows = await BookingService(session).list_for_expert(
        expert, upcoming_only=upcoming, limit=limit
    )
    return [_appointment(row) for row in rows]


@expert_router.post(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    summary="Cancel an appointment as the expert",
    description=(
        "The actor is recorded: refund policy will distinguish an expert "
        "cancelling an hour beforehand from a user cancelling a week out."
    ),
)
async def expert_cancel_appointment(
    appointment_id: uuid.UUID,
    payload: CancelRequest,
    user: CurrentUser,
    session: DbSession,
) -> AppointmentResponse:
    expert = await ExpertProfileService(session).get_own(user)
    booking = BookingService(session)
    appointment = await booking.get_for_expert(expert, appointment_id)
    await CancellationService(session).cancel_appointment(
        appointment, actor=CancellationActor.EXPERT, reason=payload.reason
    )
    await session.commit()
    return _appointment(appointment)


@expert_router.post(
    "/orders/{order_id}/complete",
    response_model=OrderResponse,
    summary="Mark a live session delivered",
    description=(
        "Live sessions only, after their start time. A written analysis is "
        "completed by `POST /expert/orders/{id}/deliver`."
    ),
)
async def expert_complete_order(
    order_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> OrderResponse:
    expert = await ExpertProfileService(session).get_own(user)
    order = await OrderService(session).get_for_expert(expert, order_id)
    await CompletionService(session).complete_live(order, actor="expert")
    await session.commit()
    return await _order_to_schema(session, order, for_expert=expert)


@expert_router.post(
    "/orders/{order_id}/deliver",
    response_model=OrderResponse,
    summary="Deliver a written analysis",
    description=(
        "The written analysis is stored on the order for the user to read, "
        "and delivering completes the order. The order must be paid or free."
    ),
)
async def expert_deliver_order(
    order_id: uuid.UUID,
    payload: DeliverRequest,
    user: CurrentUser,
    session: DbSession,
) -> OrderResponse:
    expert = await ExpertProfileService(session).get_own(user)
    order = await OrderService(session).get_for_expert(expert, order_id)
    await CompletionService(session).deliver_written(order, note=payload.note)
    await session.commit()
    return await _order_to_schema(session, order, for_expert=expert)
