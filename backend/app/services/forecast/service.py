"""Forecast service: engines + caching + persistence.

A forecast is a pure function of (natal chart, window, engine version, orb
policy, scoring version), so every result is cacheable and every cache key
carries all five. Changing a weight bumps ``SCORING_VERSION`` and the old
entries simply stop being addressed - no invalidation sweep, no stale numbers.

Two tiers:

* **Redis** for everything, with a TTL that matches how fast the answer moves
  (a day's transits expire sooner than a year's),
* **``forecast_snapshots``** for the expensive periods (monthly, annual), so a
  cold cache after a deploy does not re-run a year of ephemeris per user.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_cache
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.forecast import ForecastSnapshot
from app.domain.astrology import Chart
from app.domain.horoscope import HoroscopePeriod
from app.schemas.forecast import (
    AnnualForecastResponse,
    CalendarResponse,
    DailyFrequencyResponse,
    HoroscopeResponse,
    MonthlyForecastResponse,
    PersonalCalendarResponse,
    TransitListResponse,
)
from app.services.astrology.calendar import CosmicCalendarEngine, get_calendar_engine
from app.services.astrology.horoscope import (
    HoroscopeEngine,
    get_horoscope_engine,
    day_window,
    month_window,
    week_window,
    year_window,
)
from app.services.astrology.skyfield_engine import ENGINE_VERSION
from app.services.astrology.transits import TransitEngine, get_transit_engine
from app.services.astrology.weights import (
    DAILY_FREQUENCY_VERSION,
    ORB_POLICY_VERSION,
    SCORING_VERSION,
)
from app.services.forecast import mapping

logger = get_logger(__name__)

# Ranges the transit endpoint understands, and how long their answers keep.
RANGE_DAYS: dict[str, int] = {
    "day": 1,
    "tomorrow": 1,
    "week": 7,
    "month": 31,
    "year": 365,
}

CACHE_TTL: dict[str, int] = {
    "day": 60 * 60 * 6,
    "tomorrow": 60 * 60 * 6,
    "week": 60 * 60 * 24,
    "month": 60 * 60 * 24 * 3,
    "year": 60 * 60 * 24 * 14,
    "calendar": 60 * 60 * 24 * 30,
    "daily_frequency": 60 * 60 * 6,
    "horoscope_daily": 60 * 60 * 6,
    "horoscope_weekly": 60 * 60 * 24,
    "monthly": 60 * 60 * 24 * 3,
    "annual": 60 * 60 * 24 * 14,
    "transit_detail": 60 * 60 * 24 * 3,
}

# Bumped together with the engine, orb policy or scoring version; every key
# below carries it, so old entries are never read back.
VERSION_TAG = f"{ENGINE_VERSION}:{ORB_POLICY_VERSION}:{SCORING_VERSION}"


def _key(*parts: str) -> str:
    return "forecast:" + ":".join(parts)


def _hash(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


class ForecastService:
    def __init__(
        self,
        transits: TransitEngine | None = None,
        calendar: CosmicCalendarEngine | None = None,
        horoscope: HoroscopeEngine | None = None,
    ) -> None:
        self._transits = transits or get_transit_engine()
        self._calendar = calendar or get_calendar_engine()
        self._horoscope = horoscope or get_horoscope_engine()

    # ---------------------------------------------------------- transits

    async def transits(
        self,
        chart: Chart,
        *,
        fingerprint: str,
        range_key: str = "day",
        date: datetime | None = None,
        timezone: str = "UTC",
        include_minor: bool = False,
        refresh: bool = False,
    ) -> TransitListResponse:
        window = self._window_for(range_key, date, timezone)
        start_utc, end_utc = window
        reference = _reference_for(range_key, start_utc, end_utc, date)

        cache_key = _key(
            "transits",
            fingerprint,
            VERSION_TAG,
            range_key,
            start_utc.strftime("%Y%m%d%H"),
            str(include_minor),
        )
        if not refresh:
            cached = await get_cache().get(cache_key)
            if cached is not None:
                payload = TransitListResponse.model_validate(cached)
                return payload.model_copy(update={"cached": True})

        transit_set = self._transits.scan(
            chart,
            start=start_utc,
            end=end_utc,
            reference=reference,
            include_moon=range_key in ("day", "tomorrow", "week"),
            chart_fingerprint=fingerprint,
        )

        active = [mapping.transit_to_schema(item) for item in transit_set.active()]
        approaching = [
            mapping.transit_to_schema(item) for item in transit_set.approaching()
        ]
        seen = {item.id for item in active} | {item.id for item in approaching}
        upcoming = [
            mapping.transit_to_schema(item)
            for item in transit_set.events
            if item.id not in seen
        ]

        response = TransitListResponse(
            start_at=start_utc,
            end_at=end_utc,
            reference=reference,
            timezone=timezone,
            range=range_key,
            active=active,
            approaching=approaching,
            upcoming=upcoming,
            ingresses=[
                mapping.ingress_to_schema(item) for item in transit_set.ingresses
            ],
            engine_version=transit_set.engine_version,
            scoring_version=transit_set.scoring_version,
        )

        payload = response.model_dump(mode="json")
        await get_cache().set(cache_key, payload, CACHE_TTL.get(range_key, 3600))

        # Index the individual transits so the detail endpoint does not have to
        # rescan the sky for one card.
        for item in transit_set.events:
            await get_cache().set(
                _key("transit", fingerprint, VERSION_TAG, item.id),
                mapping.transit_to_schema(item).model_dump(mode="json"),
                CACHE_TTL["transit_detail"],
            )

        return response

    async def transit_by_id(
        self,
        chart: Chart,
        *,
        fingerprint: str,
        transit_id: str,
        timezone: str = "UTC",
    ) -> dict[str, Any] | None:
        """Look a transit up by id, warming the usual windows if needed."""
        cache_key = _key("transit", fingerprint, VERSION_TAG, transit_id)
        cached = await get_cache().get(cache_key)
        if cached is not None:
            return cached

        for range_key in ("day", "week", "month", "year"):
            await self.transits(
                chart,
                fingerprint=fingerprint,
                range_key=range_key,
                timezone=timezone,
            )
            cached = await get_cache().get(cache_key)
            if cached is not None:
                return cached
        return None

    # ---------------------------------------------------------- calendar

    async def calendar(
        self,
        *,
        start: datetime,
        end: datetime,
        timezone: str = "UTC",
        refresh: bool = False,
    ) -> CalendarResponse:
        """Global sky events. Independent of any user, so the cache is shared."""
        cache_key = _key(
            "calendar",
            VERSION_TAG,
            start.strftime("%Y%m%d"),
            end.strftime("%Y%m%d"),
        )
        if not refresh:
            cached = await get_cache().get(cache_key)
            if cached is not None:
                return CalendarResponse.model_validate(cached).model_copy(
                    update={"cached": True}
                )

        events = self._calendar.events(start, end)
        response = CalendarResponse(
            start_at=start,
            end_at=end,
            timezone=timezone,
            events=[mapping.event_to_schema(event) for event in events],
            engine_version=ENGINE_VERSION,
        )
        await get_cache().set(
            cache_key, response.model_dump(mode="json"), CACHE_TTL["calendar"]
        )
        return response

    async def personal_calendar(
        self,
        chart: Chart,
        *,
        fingerprint: str,
        start: datetime,
        end: datetime,
        timezone: str = "UTC",
        refresh: bool = False,
    ) -> PersonalCalendarResponse:
        cache_key = _key(
            "personal_calendar",
            fingerprint,
            VERSION_TAG,
            start.strftime("%Y%m%d"),
            end.strftime("%Y%m%d"),
        )
        if not refresh:
            cached = await get_cache().get(cache_key)
            if cached is not None:
                return PersonalCalendarResponse.model_validate(cached).model_copy(
                    update={"cached": True}
                )

        events = self._calendar.events(start, end)
        personal = self._horoscope.personal_events(chart, events)
        response = PersonalCalendarResponse(
            start_at=start,
            end_at=end,
            timezone=timezone,
            events=[mapping.personal_event_to_schema(item) for item in personal],
            engine_version=ENGINE_VERSION,
        )
        await get_cache().set(
            cache_key, response.model_dump(mode="json"), CACHE_TTL["calendar"]
        )
        return response

    # -------------------------------------------------- daily frequency

    async def daily_frequency(
        self,
        chart: Chart,
        *,
        fingerprint: str,
        day: datetime,
        timezone: str,
        refresh: bool = False,
    ) -> DailyFrequencyResponse:
        window = day_window(day, timezone)
        cache_key = _key(
            "daily_frequency",
            fingerprint,
            f"{ENGINE_VERSION}:{ORB_POLICY_VERSION}:{DAILY_FREQUENCY_VERSION}",
            window.start.strftime("%Y%m%d"),
            timezone,
        )
        if not refresh:
            cached = await get_cache().get(cache_key)
            if cached is not None:
                return DailyFrequencyResponse.model_validate(cached).model_copy(
                    update={"cached": True}
                )

        frequency = self._horoscope.daily_frequency(
            chart, day=day, timezone=timezone, chart_fingerprint=fingerprint
        )
        response = mapping.daily_frequency_to_schema(frequency)
        await get_cache().set(
            cache_key,
            response.model_dump(mode="json"),
            CACHE_TTL["daily_frequency"],
        )
        return response

    # ----------------------------------------------------- horoscopes

    async def horoscope(
        self,
        chart: Chart,
        *,
        fingerprint: str,
        period: HoroscopePeriod,
        day: datetime,
        timezone: str,
        refresh: bool = False,
    ) -> HoroscopeResponse:
        window = (
            day_window(day, timezone)
            if period is HoroscopePeriod.DAILY
            else week_window(day, timezone)
        )
        cache_key = _key(
            "horoscope",
            fingerprint,
            VERSION_TAG,
            period.value,
            window.start.strftime("%Y%m%d"),
            timezone,
        )
        if not refresh:
            cached = await get_cache().get(cache_key)
            if cached is not None:
                return HoroscopeResponse.model_validate(cached).model_copy(
                    update={"cached": True}
                )

        horoscope = (
            self._horoscope.daily(
                chart, day=day, timezone=timezone, chart_fingerprint=fingerprint
            )
            if period is HoroscopePeriod.DAILY
            else self._horoscope.weekly(
                chart, day=day, timezone=timezone, chart_fingerprint=fingerprint
            )
        )
        response = mapping.horoscope_to_schema(horoscope)
        await get_cache().set(
            cache_key,
            response.model_dump(mode="json"),
            CACHE_TTL[f"horoscope_{period.value}"],
        )
        return response

    async def monthly(
        self,
        chart: Chart,
        *,
        fingerprint: str,
        year: int,
        month: int,
        timezone: str,
        session: AsyncSession | None = None,
        user_id: uuid.UUID | None = None,
        refresh: bool = False,
    ) -> MonthlyForecastResponse:
        period_key = f"{year:04d}-{month:02d}"
        return await self._cached_snapshot(
            kind="monthly",
            period_key=period_key,
            fingerprint=fingerprint,
            timezone=timezone,
            session=session,
            user_id=user_id,
            refresh=refresh,
            ttl=CACHE_TTL["monthly"],
            model=MonthlyForecastResponse,
            build=lambda: mapping.monthly_to_schema(
                self._horoscope.monthly(
                    chart,
                    year=year,
                    month=month,
                    timezone=timezone,
                    chart_fingerprint=fingerprint,
                )
            ),
        )

    async def annual(
        self,
        chart: Chart,
        *,
        fingerprint: str,
        year: int,
        timezone: str,
        session: AsyncSession | None = None,
        user_id: uuid.UUID | None = None,
        refresh: bool = False,
    ) -> AnnualForecastResponse:
        return await self._cached_snapshot(
            kind="annual",
            period_key=str(year),
            fingerprint=fingerprint,
            timezone=timezone,
            session=session,
            user_id=user_id,
            refresh=refresh,
            ttl=CACHE_TTL["annual"],
            model=AnnualForecastResponse,
            build=lambda: mapping.annual_to_schema(
                self._horoscope.annual(
                    chart,
                    year=year,
                    timezone=timezone,
                    chart_fingerprint=fingerprint,
                )
            ),
        )

    # ------------------------------------------------------------ helpers

    async def _cached_snapshot(
        self,
        *,
        kind: str,
        period_key: str,
        fingerprint: str,
        timezone: str,
        session: AsyncSession | None,
        user_id: uuid.UUID | None,
        refresh: bool,
        ttl: int,
        model: type,
        build,
    ):
        cache_key = _key(kind, fingerprint, VERSION_TAG, period_key, timezone)

        if not refresh:
            cached = await get_cache().get(cache_key)
            if cached is not None:
                return model.model_validate(cached).model_copy(
                    update={"cached": True}
                )

            if session is not None:
                row = await session.scalar(
                    select(ForecastSnapshot).where(
                        ForecastSnapshot.input_hash
                        == _snapshot_hash(kind, fingerprint, period_key, timezone)
                    )
                )
                if row is not None:
                    await get_cache().set(cache_key, row.payload, ttl)
                    return model.model_validate(row.payload).model_copy(
                        update={"cached": True}
                    )

        response = build()
        payload = response.model_dump(mode="json")
        await get_cache().set(cache_key, payload, ttl)

        if session is not None:
            input_hash = _snapshot_hash(kind, fingerprint, period_key, timezone)
            existing = await session.scalar(
                select(ForecastSnapshot).where(
                    ForecastSnapshot.input_hash == input_hash
                )
            )
            if existing is None:
                session.add(
                    ForecastSnapshot(
                        user_id=user_id,
                        kind=kind,
                        period_key=period_key,
                        timezone=timezone,
                        input_hash=input_hash,
                        engine_version=ENGINE_VERSION,
                        scoring_version=SCORING_VERSION,
                        payload=payload,
                    )
                )
            else:
                existing.payload = payload
                existing.engine_version = ENGINE_VERSION
                existing.scoring_version = SCORING_VERSION
            await session.flush()

        return response

    def _window_for(
        self, range_key: str, date: datetime | None, timezone: str
    ) -> tuple[datetime, datetime]:
        anchor = (date or datetime.now(UTC)).astimezone(UTC)

        if range_key == "tomorrow":
            window = day_window(anchor + timedelta(days=1), timezone)
        elif range_key == "day":
            window = day_window(anchor, timezone)
        elif range_key == "week":
            window = week_window(anchor, timezone)
        elif range_key == "month":
            window = month_window(anchor.year, anchor.month, timezone)
        elif range_key == "year":
            window = year_window(anchor.year, timezone)
        else:  # pragma: no cover - guarded by the schema
            window = day_window(anchor, timezone)

        return window.utc


def _reference_for(
    range_key: str,
    start: datetime,
    end: datetime,
    date: datetime | None,
) -> datetime:
    """What "now" means for a window.

    For today it is the actual instant (so "active" is true right now); for a
    longer window it is the midpoint, which is what a period summary needs.
    """
    now = (date or datetime.now(UTC)).astimezone(UTC)
    if start <= now <= end:
        return now
    if range_key in ("day", "tomorrow"):
        return start + (end - start) / 2
    return start + (end - start) / 2


def _snapshot_hash(
    kind: str, fingerprint: str, period_key: str, timezone: str
) -> str:
    return _hash(
        {
            "kind": kind,
            "chart": fingerprint,
            "period": period_key,
            "timezone": timezone,
            "engine": ENGINE_VERSION,
            "scoring": SCORING_VERSION,
            "orbs": ORB_POLICY_VERSION,
        }
    )


_service: ForecastService | None = None


def get_forecast_service() -> ForecastService:
    global _service
    if _service is None:
        _service = ForecastService()
    return _service
