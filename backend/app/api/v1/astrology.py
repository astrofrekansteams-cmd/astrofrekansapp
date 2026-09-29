from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Query

from app.api.deps import Charts, CurrentUser, DbSession
from app.core.exceptions import MissingBirthData
from app.domain.astrology import BirthData
from app.domain.enums import HouseSystem
from app.schemas.astrology import (
    MoonPhaseResponse,
    NatalChartRequest,
    NatalChartResponse,
    PlanetaryPositionsResponse,
    chart_to_schema,
    moon_phase_to_schema,
    planet_to_schema,
)
from app.services.users.service import UserService

router = APIRouter(prefix="/astrology", tags=["astrology"])


@router.get(
    "/natal-chart/me",
    response_model=NatalChartResponse,
    summary="Natal chart of the signed-in user",
)
async def my_natal_chart(
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
    house_system: HouseSystem | None = Query(default=None),
    refresh: bool = Query(default=False, description="Bypass the cache."),
) -> NatalChartResponse:
    service = UserService(session)
    profile = await service.birth_profiles.get_primary(user.id)
    if profile is None:
        raise MissingBirthData(
            "Add your birth data before requesting a chart.",
            code="birth_profile_missing",
        )

    birth = await service.get_primary_birth_data(user)
    requested = house_system or birth.house_system
    chart = await charts.natal_chart(
        birth,
        session=session,
        user_id=user.id,
        subject_type="user",
        subject_id=profile.id,
        house_system=requested,
        use_cache=not refresh,
    )
    await session.commit()
    return chart_to_schema(chart, requested_house_system=requested)


@router.post(
    "/natal-chart",
    response_model=NatalChartResponse,
    summary="Natal chart for arbitrary birth data",
)
async def natal_chart(
    payload: NatalChartRequest,
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
) -> NatalChartResponse:
    service = UserService(session)
    latitude, longitude, timezone, place = await service.resolve_location(
        place=payload.birth_place,
        latitude=payload.latitude,
        longitude=payload.longitude,
        timezone=payload.timezone,
    )
    birth = BirthData(
        birth_date=payload.birth_date,
        birth_time=payload.birth_time,
        timezone=timezone,
        latitude=latitude,
        longitude=longitude,
        place=place,
        house_system=payload.house_system,
    )
    chart = await charts.natal_chart(
        birth,
        session=session,
        user_id=user.id,
        subject_type="ad_hoc",
        house_system=payload.house_system,
    )
    await session.commit()
    return chart_to_schema(chart, requested_house_system=payload.house_system)


@router.get(
    "/positions",
    response_model=PlanetaryPositionsResponse,
    summary="Current (or given) planetary positions",
)
async def positions(
    _user: CurrentUser,
    charts: Charts,
    moment: datetime | None = Query(
        default=None, description="UTC instant; defaults to now."
    ),
) -> PlanetaryPositionsResponse:
    when = (moment or datetime.now(UTC)).astimezone(UTC)
    return PlanetaryPositionsResponse(
        moment=when,
        positions=[planet_to_schema(item) for item in charts.engine.positions(when)],
    )


@router.get(
    "/moon-phase",
    response_model=MoonPhaseResponse,
    summary="Moon phase, illumination, age and next phase",
)
async def moon_phase(
    _user: CurrentUser,
    charts: Charts,
    moment: datetime | None = Query(default=None),
) -> MoonPhaseResponse:
    when = (moment or datetime.now(UTC)).astimezone(UTC)
    return moon_phase_to_schema(await charts.moon_phase(when))
