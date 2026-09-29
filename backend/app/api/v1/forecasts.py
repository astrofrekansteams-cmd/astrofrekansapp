"""Transits, cosmic calendar, horoscopes and forecasts.

Everything here is personal: a horoscope is built from the caller's own natal
chart and the sky that actually touches it, never from a sun-sign template.
Date-only queries are resolved in the user's timezone, so "today" means their
today.
"""

from __future__ import annotations

from datetime import UTC, date as date_type, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, Request

from app.api.deps import Charts, CurrentUser, DbSession
from app.core.exceptions import MissingBirthData, NotFound
from app.domain.horoscope import HoroscopePeriod
from app.schemas.forecast import (
    AnnualForecastResponse,
    CalendarResponse,
    DailyFrequencyResponse,
    HoroscopeResponse,
    MonthlyForecastResponse,
    PersonalCalendarResponse,
    TransitListResponse,
    TransitResponse,
)
from app.services.astrology.service import chart_fingerprint as make_fingerprint
from app.services.forecast.service import get_forecast_service
from app.services.users.service import UserService
from app.services.coins.unlock import coin_gate
from app.services.features import PREMIUM_TRANSIT_RANGES, Feature


router = APIRouter(tags=["forecast"])

TransitRange = Literal["day", "tomorrow", "week", "month", "year"]


async def _chart_for(user, session, charts):
    """The caller's natal chart plus the fingerprint every cache key uses."""
    service = UserService(session)
    profile = await service.birth_profiles.get_primary(user.id)
    if profile is None:
        raise MissingBirthData(
            "Add your birth data before requesting a forecast.",
            code="birth_profile_missing",
        )

    birth = await service.get_primary_birth_data(user)
    chart = await charts.natal_chart(
        birth,
        session=session,
        user_id=user.id,
        subject_type="birth_profile",
        subject_id=profile.id,
    )
    fingerprint = make_fingerprint(chart.subject, charts.engine.version)
    timezone = (
        user.profile.timezone if user.profile else None
    ) or birth.timezone or "UTC"
    return chart, fingerprint, timezone


def _resolve_day(value: date_type | None, timezone: str) -> datetime:
    """A date in the user's zone becomes that day's noon, in UTC."""
    zone = ZoneInfo(timezone)
    if value is None:
        return datetime.now(UTC)
    return datetime(value.year, value.month, value.day, 12, tzinfo=zone).astimezone(UTC)


# ------------------------------------------------------------------ transits


@router.get(
    "/astrology/transits",
    response_model=TransitListResponse,
    summary="Transits to the natal chart",
    description=(
        "Grouped into `active` (in orb now), `approaching` (window opens "
        "later) and `upcoming` (the rest of the window). Each transit carries "
        "its window, every exact pass - a retrograding planet perfects the "
        "same aspect up to three times - and a deterministic 0-100 strength."
    ),
)
async def transits(
    request: Request,
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
    date: date_type | None = Query(default=None),
    range: TransitRange = Query(default="day"),
    include_minor: bool = Query(
        default=False, description="Reserved for quincunx and semisextile."
    ),
    refresh: bool = Query(default=False),
) -> TransitListResponse:
    gate = (
        await coin_gate(session, user, Feature.ADVANCED_TRANSITS, request)
        if range in PREMIUM_TRANSIT_RANGES
        else None
    )
    chart, fingerprint, timezone = await _chart_for(user, session, charts)
    await session.commit()

    response = await get_forecast_service().transits(
        chart,
        fingerprint=fingerprint,
        range_key=range,
        date=_resolve_day(date, timezone),
        timezone=timezone,
        include_minor=include_minor,
        refresh=refresh,
    )
    if gate is not None and gate.paid:
        await gate.charge()
        await session.commit()
    return response


@router.get(
    "/astrology/transits/{transit_id}",
    response_model=TransitResponse,
    summary="One transit in detail",
)
async def transit_detail(
    transit_id: str,
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
) -> TransitResponse:
    chart, fingerprint, timezone = await _chart_for(user, session, charts)
    await session.commit()

    payload = await get_forecast_service().transit_by_id(
        chart, fingerprint=fingerprint, transit_id=transit_id, timezone=timezone
    )
    if payload is None:
        raise NotFound("Unknown transit.", details={"id": transit_id})
    return TransitResponse.model_validate(payload)


# ------------------------------------------------------------ daily frequency


@router.get(
    "/astrology/daily-frequency",
    response_model=DailyFrequencyResponse,
    summary="The day's frequency scores",
    description=(
        "Deterministic scores per life area with the factors that produced "
        "them, plus important hours derived from the day's real exact aspects."
    ),
)
async def daily_frequency(
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
    date: date_type | None = Query(default=None),
    refresh: bool = Query(default=False),
) -> DailyFrequencyResponse:
    chart, fingerprint, timezone = await _chart_for(user, session, charts)
    await session.commit()

    return await get_forecast_service().daily_frequency(
        chart,
        fingerprint=fingerprint,
        day=_resolve_day(date, timezone),
        timezone=timezone,
        refresh=refresh,
    )


# ----------------------------------------------------------------- calendar


@router.get(
    "/calendar/events",
    response_model=CalendarResponse,
    summary="Cosmic calendar (global events)",
    description=(
        "Moon phases, stations, eclipses, ingresses and mundane aspects. "
        "Eclipses are detected from actual geometry, not from 'this full moon "
        "is near a node'."
    ),
)
async def calendar_events(
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    refresh: bool = Query(default=False),
) -> CalendarResponse:
    timezone = (user.profile.timezone if user.profile else None) or "UTC"
    zone = ZoneInfo(timezone)
    start_dt = (
        datetime(start.year, start.month, start.day, tzinfo=zone)
        if start
        else datetime.now(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    )
    end_dt = (
        datetime(end.year, end.month, end.day, tzinfo=zone)
        if end
        else start_dt + timedelta(days=30)
    )

    return await get_forecast_service().calendar(
        start=start_dt.astimezone(UTC),
        end=end_dt.astimezone(UTC),
        timezone=timezone,
        refresh=refresh,
    )


@router.get(
    "/calendar/personal",
    response_model=PersonalCalendarResponse,
    summary="Cosmic calendar filtered through the natal chart",
    description=(
        "The same events, but with the natal house they land in, the natal "
        "aspects they make and a relevance score."
    ),
)
async def personal_calendar(
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    refresh: bool = Query(default=False),
) -> PersonalCalendarResponse:
    chart, fingerprint, timezone = await _chart_for(user, session, charts)
    await session.commit()

    zone = ZoneInfo(timezone)
    start_dt = (
        datetime(start.year, start.month, start.day, tzinfo=zone)
        if start
        else datetime.now(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    )
    end_dt = (
        datetime(end.year, end.month, end.day, tzinfo=zone)
        if end
        else start_dt + timedelta(days=30)
    )

    return await get_forecast_service().personal_calendar(
        chart,
        fingerprint=fingerprint,
        start=start_dt.astimezone(UTC),
        end=end_dt.astimezone(UTC),
        timezone=timezone,
        refresh=refresh,
    )


# ---------------------------------------------------------------- horoscope


@router.get(
    "/horoscope/daily",
    response_model=HoroscopeResponse,
    summary="Personalised daily horoscope",
)
async def daily_horoscope(
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
    date: date_type | None = Query(default=None),
    refresh: bool = Query(default=False),
) -> HoroscopeResponse:
    chart, fingerprint, timezone = await _chart_for(user, session, charts)
    await session.commit()

    return await get_forecast_service().horoscope(
        chart,
        fingerprint=fingerprint,
        period=HoroscopePeriod.DAILY,
        day=_resolve_day(date, timezone),
        timezone=timezone,
        refresh=refresh,
    )


@router.get(
    "/horoscope/weekly",
    response_model=HoroscopeResponse,
    summary="Personalised weekly horoscope",
    description=(
        "Built from the week's exact contacts, the Moon's path, stations and "
        "ingresses - not an average of seven daily readings."
    ),
)
async def weekly_horoscope(
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
    date: date_type | None = Query(default=None),
    refresh: bool = Query(default=False),
) -> HoroscopeResponse:
    chart, fingerprint, timezone = await _chart_for(user, session, charts)
    await session.commit()

    return await get_forecast_service().horoscope(
        chart,
        fingerprint=fingerprint,
        period=HoroscopePeriod.WEEKLY,
        day=_resolve_day(date, timezone),
        timezone=timezone,
        refresh=refresh,
    )


@router.get(
    "/forecasts/monthly",
    response_model=MonthlyForecastResponse,
    summary="Monthly forecast",
    description=(
        "Structured month ahead: area scores, key periods found by clustering "
        "the month's transits, important dates, retrogrades, moon events and "
        "the personal events that touch the chart."
    ),
)
async def monthly_forecast(
    request: Request,
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
    year: int | None = Query(default=None, ge=1900, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    refresh: bool = Query(default=False),
) -> MonthlyForecastResponse:
    gate = await coin_gate(session, user, Feature.MONTHLY_FORECAST, request)
    chart, fingerprint, timezone = await _chart_for(user, session, charts)

    now = datetime.now(ZoneInfo(timezone))
    response = await get_forecast_service().monthly(
        chart,
        fingerprint=fingerprint,
        year=year or now.year,
        month=month or now.month,
        timezone=timezone,
        session=session,
        user_id=user.id,
        refresh=refresh,
    )
    await gate.charge()
    await session.commit()
    return response


@router.get(
    "/forecasts/yearly",
    response_model=AnnualForecastResponse,
    summary="Annual forecast",
    description=(
        "The astrological data layer for the year: outer-planet transits, "
        "retrograde periods, eclipses, Jupiter and Saturn house movements, "
        "key periods and the solar return instant. Interpretation arrives in "
        "phase B6."
    ),
)
async def annual_forecast(
    request: Request,
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
    year: int | None = Query(default=None, ge=1900, le=2100),
    refresh: bool = Query(default=False),
) -> AnnualForecastResponse:
    gate = await coin_gate(session, user, Feature.YEARLY_FORECAST, request)
    chart, fingerprint, timezone = await _chart_for(user, session, charts)

    now = datetime.now(ZoneInfo(timezone))
    response = await get_forecast_service().annual(
        chart,
        fingerprint=fingerprint,
        year=year or now.year,
        timezone=timezone,
        session=session,
        user_id=user.id,
        refresh=refresh,
    )
    await gate.charge()
    await session.commit()
    return response
