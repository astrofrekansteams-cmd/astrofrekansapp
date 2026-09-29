"""Personal guides: moon guide, solar/lunar returns, numerology, stones.

Every value is computed by the engine or by arithmetic; the text is picked
from fixed content tables. Nothing on these routes calls the AI provider.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, Query, Request

from app.api.deps import Charts, CurrentUser, DbSession
from app.core.exceptions import MissingBirthData, ValidationFailed
from app.db.models.user import User
from app.domain.astrology import Chart
from app.schemas.guides import (
    MoonGuideResponse,
    NumerologyResponse,
    ReturnChartResponse,
    StoneRecommendationResponse,
    moon_guide_to_schema,
    numerology_to_schema,
    return_to_schema,
    stones_to_schema,
)
from app.services.astrology.service import ChartService
from app.services.coins.unlock import coin_gate
from app.services.features import Feature
from app.services.guides import numerology
from app.services.guides.moon_guide import get_moon_guide_service
from app.services.guides.returns_guide import get_returns_guide
from app.services.guides.stones import Intent, StoneGuide, StoneMode
from app.services.users.service import UserService

router = APIRouter(tags=["guides"])

Locale = Query(default="tr", pattern="^(tr|en|az)$")


async def _natal(user: User, session: DbSession, charts: ChartService) -> Chart:
    service = UserService(session)
    profile = await service.birth_profiles.get_primary(user.id)
    if profile is None:
        raise MissingBirthData(
            "Add your birth data before requesting a guide.",
            code="birth_profile_missing",
        )
    birth = await service.get_primary_birth_data(user)
    chart = await charts.natal_chart(
        birth,
        session=session,
        user_id=user.id,
        subject_type="user",
        subject_id=profile.id,
    )
    await session.commit()
    return chart


@router.get(
    "/astrology/moon-guide",
    response_model=MoonGuideResponse,
    summary="Moon sign, phase, aspects, natal house and what the day suits",
)
async def moon_guide(
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
    moment: datetime | None = Query(default=None, description="UTC instant; defaults to now."),
    locale: str = Locale,
) -> MoonGuideResponse:
    natal = await _natal(user, session, charts)
    when = (moment or datetime.now(UTC)).astimezone(UTC)
    phase = await charts.moon_phase(when)  # hourly cache
    return moon_guide_to_schema(
        get_moon_guide_service().guide(when, natal, locale=locale, phase=phase)
    )


@router.get(
    "/astrology/solar-return",
    response_model=ReturnChartResponse,
    summary="Solar return chart and theme for a birthday year",
)
async def solar_return(
    request: Request,
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
    year: int = Query(ge=1900, le=2150),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    timezone: str | None = Query(default=None, max_length=64),
    locale: str = Locale,
) -> ReturnChartResponse:
    gate = await coin_gate(session, user, Feature.SOLAR_RETURN, request)
    if (latitude is None) != (longitude is None):
        raise ValidationFailed("Give both latitude and longitude, or neither.")
    natal = await _natal(user, session, charts)
    reading = get_returns_guide().solar(
        natal, year, locale=locale, latitude=latitude, longitude=longitude, timezone=timezone
    )
    response = return_to_schema(reading)
    if gate.paid:
        await gate.charge()
        await session.commit()
    return response


@router.get(
    "/astrology/lunar-return",
    response_model=ReturnChartResponse,
    summary="Next lunar return after a date, with its monthly theme",
)
async def lunar_return(
    request: Request,
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
    after: date | None = Query(default=None, description="Defaults to today (UTC)."),
    locale: str = Locale,
) -> ReturnChartResponse:
    gate = await coin_gate(session, user, Feature.LUNAR_RETURN, request)
    natal = await _natal(user, session, charts)
    start = datetime.combine(after or datetime.now(UTC).date(), datetime.min.time(), UTC)
    response = return_to_schema(get_returns_guide().lunar(natal, start, locale=locale))
    if gate.paid:
        await gate.charge()
        await session.commit()
    return response


@router.get(
    "/numerology/me",
    response_model=NumerologyResponse,
    summary="Pythagorean numerology from the profile name and birth date",
)
async def my_numerology(
    user: CurrentUser,
    session: DbSession,
    name: str | None = Query(
        default=None, min_length=2, max_length=160, description="Full birth name; defaults to the profile name."
    ),
    reference: date | None = Query(default=None, description="Date for the personal year/month."),
    locale: str = Locale,
) -> NumerologyResponse:
    service = UserService(session)
    profile = await service.birth_profiles.get_primary(user.id)
    if profile is None:
        raise MissingBirthData(
            "Add your birth date before requesting numerology.",
            code="birth_profile_missing",
        )
    full_name = name or (user.profile.name if user.profile else "")
    try:
        result = numerology.profile(
            full_name, profile.birth_date, reference or datetime.now(UTC).date()
        )
    except ValueError as exc:
        raise ValidationFailed("The name needs at least one letter.") from exc
    return numerology_to_schema(result, locale)


@router.get(
    "/stones/recommendation",
    response_model=StoneRecommendationResponse,
    summary="Stone of the day or personal stone, with the reasons behind it",
)
async def stone_recommendation(
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
    mode: StoneMode = Query(default=StoneMode.TODAY),
    intent: Intent | None = Query(default=None),
    locale: str = Locale,
) -> StoneRecommendationResponse:
    natal = await _natal(user, session, charts)
    now = datetime.now(UTC)
    sky = charts.engine.positions(now) if mode == StoneMode.TODAY else None
    result = StoneGuide().recommend(
        natal, mode=mode, intent=intent, moment=now, sky=sky, locale=locale
    )
    return stones_to_schema(result, locale)
