"""Marketplace endpoints: experts, availability and slots.

The authorisation shape of this router:

* `/experts` and `/experts/{id}` are the public shop front. They return active
  profiles only and carry no account data.
* `/experts/me/**` acts on the caller's own profile. There is no route that
  lets one expert touch another's profile, offerings or schedule - the
  services take the caller's own `Expert` row, so an id from the URL can never
  redirect the write.
* Activation and verification have no routes at all. They exist as service
  methods for a future admin surface.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession, UserRateLimit
from app.core.config import settings
from app.core.exceptions import NotFound
from app.db.models.marketplace import Expert, ExpertService
from app.db.models.service import ServiceDefinition
from app.domain.marketplace import (
    AvailabilityExceptionType,
    DeliveryType,
    ExpertSpecialty,
    ExpertStatus,
)
from app.schemas.common import Message
from app.schemas.marketplace import (
    AvailabilityExceptionRequest,
    AvailabilityExceptionResponse,
    AvailabilityWindowRequest,
    AvailabilityWindowResponse,
    ExpertApplicationRequest,
    ExpertDetail,
    ExpertSearchResponse,
    ExpertServiceCreateRequest,
    ExpertServiceResponse,
    ExpertServiceUpdateRequest,
    ExpertSummary,
    ExpertUpdateRequest,
    MoneyResponse,
    SlotHoldRequest,
    SlotHoldResponse,
    SlotListResponse,
    SlotResponse,
)
from app.services.marketplace.booking import BookingService
from app.services.marketplace.discovery import (
    ExpertSearchFilters,
    ExpertSearchService,
    FavoriteService,
    ReviewService,
)
from app.services.marketplace.experts import (
    AvailabilityManager,
    ExpertProfileService,
    ExpertServiceManager,
)
from app.services.marketplace.slots import SlotGenerator, zone

router = APIRouter(prefix="/experts", tags=["marketplace"])

_search_limit = Depends(
    UserRateLimit(
        settings.marketplace_search_rate_limit, scope="marketplace_search"
    )
)
_mutation_limit = Depends(
    UserRateLimit(
        settings.expert_mutation_rate_limit, scope="expert_mutation"
    )
)
_booking_limit = Depends(
    UserRateLimit(
        settings.appointment_booking_rate_limit, scope="appointment_booking"
    )
)


# ----------------------------------------------------------- serialisation


def _money(amount_minor: int, currency: str) -> MoneyResponse:
    return MoneyResponse(amount_minor=amount_minor, currency=currency)


async def _offering_to_schema(
    session, offering: ExpertService
) -> ExpertServiceResponse:  # noqa: ANN001
    from sqlalchemy import select

    definition = await session.scalar(
        select(ServiceDefinition).where(
            ServiceDefinition.id == offering.service_definition_id
        )
    )
    delivery = DeliveryType(offering.delivery_type)

    # Capability is the intersection: the catalogue must support the channel
    # *and* this offering must be sold through it.
    return ExpertServiceResponse(
        id=offering.id,
        expert_id=offering.expert_id,
        service_code=definition.code if definition else "",
        service_name=definition.name if definition else "",
        title=offering.title,
        description=offering.description,
        delivery_type=delivery,
        duration_minutes=offering.duration_minutes,
        price=_money(offering.price_minor, offering.currency),
        active=offering.active,
        supports_chat=bool(definition and definition.supports_chat)
        and delivery is DeliveryType.CHAT,
        supports_voice=bool(definition and definition.supports_voice)
        and delivery is DeliveryType.VOICE,
        supports_video=bool(definition and definition.supports_video)
        and delivery is DeliveryType.VIDEO,
        requires_birth_data=bool(definition and definition.requires_birth_data),
        requires_partner_data=bool(
            definition and definition.requires_partner_data
        ),
        requires_question=bool(definition and definition.requires_question),
        supports_appointment=bool(definition and definition.supports_appointment),
    )


def _summary(expert: Expert, *, from_price=None, is_favorite=False) -> ExpertSummary:
    return ExpertSummary(
        id=expert.id,
        display_name=expert.display_name,
        headline=expert.headline,
        avatar_key=expert.avatar_key,
        languages=list(expert.languages or []),
        specialties=list(expert.specialties or []),
        experience_years=expert.experience_years,
        verified=expert.verified,
        rating_average=float(expert.rating_average or 0),
        rating_count=expert.rating_count,
        from_price=from_price,
        is_favorite=is_favorite,
    )


# ------------------------------------------------------------ application


@router.post(
    "/apply",
    response_model=ExpertDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_mutation_limit],
    summary="Apply to become an expert",
    description=(
        "Creates the caller's own profile in `pending_review`. A profile is "
        "never created active or verified - activation is a moderation "
        "decision with no route."
    ),
)
async def apply(
    payload: ExpertApplicationRequest, user: CurrentUser, session: DbSession
) -> ExpertDetail:
    expert = await ExpertProfileService(session).apply(
        user,
        display_name=payload.display_name,
        headline=payload.headline,
        bio=payload.bio,
        avatar_key=payload.avatar_key,
        languages=payload.languages,
        specialties=[item.value for item in payload.specialties],
        experience_years=payload.experience_years,
        timezone=payload.timezone,
    )
    await session.commit()
    return await _detail(session, expert, own=True)


# ------------------------------------------------------------------ search


@router.get(
    "",
    response_model=ExpertSearchResponse,
    dependencies=[_search_limit],
    summary="Search experts",
    description=(
        "Active profiles only. Results carry the public shop front and nothing "
        "from the underlying account. Pagination is mandatory."
    ),
)
async def search_experts(
    user: CurrentUser,
    session: DbSession,
    q: str | None = Query(
        default=None,
        max_length=80,
        description="Free text: name, headline, bio and specialty names (Turkish or English).",
    ),
    specialty: ExpertSpecialty | None = Query(default=None),
    language: str | None = Query(default=None, max_length=8),
    service_code: str | None = Query(default=None, max_length=60),
    delivery_type: DeliveryType | None = Query(default=None),
    min_price_minor: int | None = Query(default=None, ge=0),
    max_price_minor: int | None = Query(default=None, ge=0),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    verified: bool = Query(default=False),
    rating_min: float | None = Query(default=None, ge=0, le=5),
    available_today: bool = Query(
        default=False,
        description="Only experts with weekly availability today (their timezone).",
    ),
    sort: str = Query(default="rating"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ExpertSearchResponse:
    service = ExpertSearchService(session)
    favorites = FavoriteService(session)

    experts, total = await service.search(
        ExpertSearchFilters(
            q=q.strip() if q else None,
            specialty=specialty,
            language=language.lower() if language else None,
            service_code=service_code,
            delivery_type=delivery_type,
            min_price_minor=min_price_minor,
            max_price_minor=max_price_minor,
            currency=currency,
            verified_only=verified,
            min_rating=rating_min,
            available_today=available_today,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    )

    items = []
    for expert in experts:
        cheapest = await service.cheapest_offering(expert.id)
        items.append(
            _summary(
                expert,
                from_price=(
                    _money(cheapest.price_minor, cheapest.currency)
                    if cheapest
                    else None
                ),
                is_favorite=await favorites.is_favorite(user, expert.id),
            )
        )

    return ExpertSearchResponse(
        items=items, total=total, limit=limit, offset=offset
    )


# ------------------------------------------------------------ own profile


async def _detail(session, expert: Expert, *, own: bool) -> ExpertDetail:  # noqa: ANN001
    offerings = await ExpertServiceManager(session).list_for_expert(
        expert.id, active_only=not own
    )
    summary = await ReviewService(session).summary(expert.id)

    base = _summary(expert)
    return ExpertDetail(
        **base.model_dump(),
        bio=expert.bio,
        timezone=expert.timezone,
        status=ExpertStatus(expert.status),
        services=[
            await _offering_to_schema(session, offering) for offering in offerings
        ],
        rating_distribution=summary["distribution"],
        created_at=expert.created_at,
    )


@router.get(
    "/me",
    response_model=ExpertDetail,
    summary="Your own expert profile",
)
async def get_own_profile(user: CurrentUser, session: DbSession) -> ExpertDetail:
    expert = await ExpertProfileService(session).get_own(user)
    return await _detail(session, expert, own=True)


@router.patch(
    "/me",
    response_model=ExpertDetail,
    dependencies=[_mutation_limit],
    summary="Edit your own expert profile",
)
async def update_own_profile(
    payload: ExpertUpdateRequest, user: CurrentUser, session: DbSession
) -> ExpertDetail:
    fields = payload.model_dump(exclude_unset=True)
    if payload.specialties is not None:
        fields["specialties"] = [item.value for item in payload.specialties]
    if payload.status is not None:
        fields["status"] = payload.status.value

    expert = await ExpertProfileService(session).update_own(user, **fields)
    await session.commit()
    return await _detail(session, expert, own=True)


# --------------------------------------------------------- own offerings


@router.post(
    "/me/services",
    response_model=ExpertServiceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_mutation_limit],
    summary="Add an offering",
    description=(
        "Validated against the catalogue: an expert cannot offer a service the "
        "platform does not deliver by experts, nor through a channel the "
        "service definition does not support."
    ),
)
async def create_own_service(
    payload: ExpertServiceCreateRequest, user: CurrentUser, session: DbSession
) -> ExpertServiceResponse:
    expert = await ExpertProfileService(session).get_own(user)
    offering = await ExpertServiceManager(session).create(
        expert,
        service_definition_id=payload.service_definition_id,
        title=payload.title,
        description=payload.description,
        delivery_type=payload.delivery_type,
        duration_minutes=payload.duration_minutes,
        price_minor=payload.price_minor,
        currency=payload.currency,
    )
    await session.commit()
    return await _offering_to_schema(session, offering)


@router.patch(
    "/me/services/{service_id}",
    response_model=ExpertServiceResponse,
    dependencies=[_mutation_limit],
    summary="Edit an offering",
    description=(
        "Changing the price here does not change any existing order: every "
        "order carries its own price snapshot."
    ),
)
async def update_own_service(
    service_id: uuid.UUID,
    payload: ExpertServiceUpdateRequest,
    user: CurrentUser,
    session: DbSession,
) -> ExpertServiceResponse:
    expert = await ExpertProfileService(session).get_own(user)
    fields = payload.model_dump(exclude_unset=True)
    if payload.delivery_type is not None:
        fields["delivery_type"] = payload.delivery_type.value

    offering = await ExpertServiceManager(session).update(
        expert, service_id, **fields
    )
    await session.commit()
    return await _offering_to_schema(session, offering)


@router.delete(
    "/me/services/{service_id}",
    response_model=ExpertServiceResponse,
    dependencies=[_mutation_limit],
    summary="Stop offering a service",
    description=(
        "Deactivates rather than deletes: past orders point at this offering "
        "and must keep resolving."
    ),
)
async def deactivate_own_service(
    service_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> ExpertServiceResponse:
    expert = await ExpertProfileService(session).get_own(user)
    offering = await ExpertServiceManager(session).deactivate(expert, service_id)
    await session.commit()
    return await _offering_to_schema(session, offering)


# ------------------------------------------------------- own availability


@router.get(
    "/me/availability",
    response_model=list[AvailabilityWindowResponse],
    summary="Your weekly schedule",
)
async def list_own_availability(
    user: CurrentUser, session: DbSession
) -> list[AvailabilityWindowResponse]:
    expert = await ExpertProfileService(session).get_own(user)
    rows = await AvailabilityManager(session).list_schedule(expert.id)
    return [
        AvailabilityWindowResponse(
            id=row.id,
            weekday=row.weekday,
            start_local_time=row.start_local_time,
            end_local_time=row.end_local_time,
            timezone=row.timezone,
            active=row.active,
        )
        for row in rows
    ]


@router.post(
    "/me/availability",
    response_model=AvailabilityWindowResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_mutation_limit],
    summary="Add a weekly window",
    description=(
        "Local time plus a timezone, not UTC: 'Mondays 09:00 in Istanbul' has "
        "to stay 09:00 across a daylight-saving change. For a window that "
        "crosses midnight, add one window per local day."
    ),
)
async def add_own_availability(
    payload: AvailabilityWindowRequest, user: CurrentUser, session: DbSession
) -> AvailabilityWindowResponse:
    expert = await ExpertProfileService(session).get_own(user)
    window = await AvailabilityManager(session).add_window(
        expert,
        weekday=payload.weekday,
        start_local_time=payload.start_local_time,
        end_local_time=payload.end_local_time,
        timezone=payload.timezone,
    )
    await session.commit()
    return AvailabilityWindowResponse(
        id=window.id,
        weekday=window.weekday,
        start_local_time=window.start_local_time,
        end_local_time=window.end_local_time,
        timezone=window.timezone,
        active=window.active,
    )


@router.delete(
    "/me/availability/{window_id}",
    response_model=Message,
    dependencies=[_mutation_limit],
    summary="Remove a weekly window",
)
async def remove_own_availability(
    window_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> Message:
    expert = await ExpertProfileService(session).get_own(user)
    await AvailabilityManager(session).remove_window(expert, window_id)
    await session.commit()
    return Message(message="Availability window removed.")


@router.get(
    "/me/availability/exceptions",
    response_model=list[AvailabilityExceptionResponse],
    summary="Your schedule exceptions",
)
async def list_own_exceptions(
    user: CurrentUser, session: DbSession
) -> list[AvailabilityExceptionResponse]:
    expert = await ExpertProfileService(session).get_own(user)
    rows = await AvailabilityManager(session).list_exceptions(
        expert.id, since=datetime.now(UTC) - timedelta(days=30)
    )
    return [
        AvailabilityExceptionResponse(
            id=row.id,
            exception_type=AvailabilityExceptionType(row.exception_type),
            starts_at_utc=row.starts_at_utc,
            ends_at_utc=row.ends_at_utc,
            reason=row.reason,
        )
        for row in rows
    ]


@router.post(
    "/me/availability/exceptions",
    response_model=AvailabilityExceptionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_mutation_limit],
    summary="Block time, or add extra availability",
)
async def add_own_exception(
    payload: AvailabilityExceptionRequest, user: CurrentUser, session: DbSession
) -> AvailabilityExceptionResponse:
    expert = await ExpertProfileService(session).get_own(user)
    row = await AvailabilityManager(session).add_exception(
        expert,
        exception_type=payload.exception_type,
        starts_at_utc=payload.starts_at_utc,
        ends_at_utc=payload.ends_at_utc,
        reason=payload.reason,
    )
    await session.commit()
    return AvailabilityExceptionResponse(
        id=row.id,
        exception_type=AvailabilityExceptionType(row.exception_type),
        starts_at_utc=row.starts_at_utc,
        ends_at_utc=row.ends_at_utc,
        reason=row.reason,
    )


@router.delete(
    "/me/availability/exceptions/{exception_id}",
    response_model=Message,
    dependencies=[_mutation_limit],
    summary="Remove an exception",
)
async def remove_own_exception(
    exception_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> Message:
    expert = await ExpertProfileService(session).get_own(user)
    await AvailabilityManager(session).remove_exception(expert, exception_id)
    await session.commit()
    return Message(message="Exception removed.")


# --------------------------------------------------------- public detail
#
# Declared after /me/** so that "me" is never captured as an expert id.


@router.get(
    "/{expert_id}",
    response_model=ExpertDetail,
    dependencies=[_search_limit],
    summary="An expert's public profile",
    description=(
        "Active profiles only. The raw weekly schedule is deliberately not "
        "here - bookable times come from `/slots`, which already accounts for "
        "exceptions and existing appointments."
    ),
)
async def get_expert(
    expert_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> ExpertDetail:
    expert = await ExpertProfileService(session).get_public(expert_id)
    detail = await _detail(session, expert, own=False)
    detail.is_favorite = await FavoriteService(session).is_favorite(
        user, expert.id
    )
    return detail


@router.get(
    "/{expert_id}/services",
    response_model=list[ExpertServiceResponse],
    dependencies=[_search_limit],
    summary="An expert's active offerings",
)
async def list_expert_services(
    expert_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> list[ExpertServiceResponse]:
    expert = await ExpertProfileService(session).get_public(expert_id)
    offerings = await ExpertServiceManager(session).list_for_expert(expert.id)
    return [
        await _offering_to_schema(session, offering) for offering in offerings
    ]


@router.get(
    "/{expert_id}/slots",
    response_model=SlotListResponse,
    dependencies=[_search_limit],
    summary="Bookable times for one service",
    description=(
        "Generated from the weekly schedule, its exceptions, existing "
        "appointments and live holds, with the configured buffers, minimum "
        "notice and booking horizon applied. UTC is canonical; the local times "
        "are for display."
    ),
)
async def list_slots(
    expert_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    service_id: uuid.UUID = Query(),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    timezone: str | None = Query(default=None),
) -> SlotListResponse:
    expert = await ExpertProfileService(session).get_public(expert_id)
    offering = await ExpertServiceManager(session).get_public(service_id)
    if offering.expert_id != expert.id:
        raise NotFound("Service not found.")

    now = datetime.now(UTC)
    start = from_ or now
    end = to or (start + timedelta(days=14))
    display = timezone or (user.profile.timezone if user.profile else None) or expert.timezone
    zone(display)

    slots = await SlotGenerator(session).generate(
        expert_id=expert.id,
        service=offering,
        start=start,
        end=end,
        display_timezone=display,
    )

    return SlotListResponse(
        expert_id=expert.id,
        expert_service_id=offering.id,
        duration_minutes=offering.duration_minutes,
        display_timezone=display,
        slots=[
            SlotResponse(
                starts_at_utc=slot.starts_at_utc,
                ends_at_utc=slot.ends_at_utc,
                starts_at_local=slot.local_start,
                ends_at_local=slot.local_end,
                display_timezone=slot.display_timezone,
            )
            for slot in slots
        ],
        generated_at=now,
    )


@router.post(
    "/{expert_id}/hold",
    response_model=SlotHoldResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_booking_limit],
    summary="Hold a slot briefly",
    description=(
        "Claims a slot while an order is placed, so two people filling in the "
        "same booking form do not both believe they have it. The hold expires "
        "on its own."
    ),
)
async def hold_slot(
    expert_id: uuid.UUID,
    payload: SlotHoldRequest,
    user: CurrentUser,
    session: DbSession,
) -> SlotHoldResponse:
    expert = await ExpertProfileService(session).get_public(expert_id)
    offering = await ExpertServiceManager(session).get_public(
        payload.expert_service_id
    )
    if offering.expert_id != expert.id:
        raise NotFound("Service not found.")

    hold = await BookingService(session).hold_slot(
        user, service=offering, starts_at_utc=payload.starts_at_utc
    )
    await session.commit()
    return SlotHoldResponse(
        id=hold.id,
        expert_id=hold.expert_id,
        expert_service_id=hold.expert_service_id,
        starts_at_utc=hold.starts_at_utc,
        ends_at_utc=hold.ends_at_utc,
        expires_at=hold.expires_at,
        status=hold.status,
    )


@router.post(
    "/{expert_id}/favorite",
    response_model=Message,
    summary="Add to favourites",
)
async def add_favorite(
    expert_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> Message:
    await FavoriteService(session).add(user, expert_id)
    await session.commit()
    return Message(message="Added to favourites.")


@router.delete(
    "/{expert_id}/favorite",
    response_model=Message,
    summary="Remove from favourites",
)
async def remove_favorite(
    expert_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> Message:
    await FavoriteService(session).remove(user, expert_id)
    await session.commit()
    return Message(message="Removed from favourites.")


@router.get(
    "/{expert_id}/reviews",
    response_model=None,
    dependencies=[_search_limit],
    summary="An expert's reviews",
)
async def list_expert_reviews(
    expert_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    from app.schemas.marketplace import ReviewListResponse, ReviewResponse

    expert = await ExpertProfileService(session).get_public(expert_id)
    service = ReviewService(session)
    rows, total = await service.list_for_expert(
        expert.id, limit=limit, offset=offset
    )
    summary = await service.summary(expert.id)

    return ReviewListResponse(
        items=[
            ReviewResponse(
                id=row.id,
                expert_id=row.expert_id,
                order_id=row.order_id,
                rating=row.rating,
                comment=row.comment,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ],
        total=total,
        rating_average=summary["rating_average"],
        rating_count=summary["rating_count"],
        distribution=summary["distribution"],
    )
