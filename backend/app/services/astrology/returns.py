"""Return charts.

A solar return is cast for the instant the transiting Sun comes back to its
natal longitude; a lunar return the same for the Moon. Both are found by root
search - never by "the birthday at noon", which is off by up to a day and
would put the wrong Ascendant on the chart.

The chart itself is built with the ordinary chart primitive, with
``ChartKind.SOLAR_RETURN`` / ``LUNAR_RETURN``. Interpretation belongs to later
phases; this module only produces correct charts and instants.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.astrology import Chart, ChartSubject
from app.domain.enums import ChartKind, HouseSystem, Planet
from app.services.astrology.sampling import EphemerisSampler
from app.services.astrology.skyfield_engine import SkyfieldEngine, get_engine

# A solar return lands within a day or so of the birthday; a lunar return
# within a couple of days of the monthly anchor.
_SEARCH_WINDOWS: dict[Planet, timedelta] = {
    Planet.SUN: timedelta(days=3),
    Planet.MOON: timedelta(days=3),
}


class ReturnEngine:
    def __init__(
        self,
        engine: SkyfieldEngine | None = None,
        sampler: EphemerisSampler | None = None,
    ) -> None:
        self._engine = engine or get_engine()
        self._sampler = sampler or EphemerisSampler(self._engine)

    # -------------------------------------------------------------- instants

    def return_moment(
        self,
        body: Planet,
        natal_longitude: float,
        *,
        around: datetime,
        window: timedelta | None = None,
    ) -> datetime | None:
        """The instant ``body`` next reaches ``natal_longitude`` near
        ``around``."""
        window = window or _SEARCH_WINDOWS.get(body, timedelta(days=3))
        start = (around - window).astimezone(UTC)
        end = (around + window).astimezone(UTC)

        crossings = self._sampler.crossings(body, natal_longitude, start, end)
        if not crossings:
            return None
        return min(crossings, key=lambda moment: abs(moment - around))

    def solar_return_moment(self, chart: Chart, year: int) -> datetime | None:
        """The Sun's return to its natal degree in the given calendar year."""
        sun = chart.position(Planet.SUN)
        if sun is None:
            return None
        birth = chart.birth_data
        anchor = datetime(
            year,
            birth.birth_date.month if birth else chart.moment_utc.month,
            birth.birth_date.day if birth else chart.moment_utc.day,
            12,
            tzinfo=UTC,
        )
        return self.return_moment(Planet.SUN, sun.longitude, around=anchor)

    def lunar_return_moment(
        self, chart: Chart, *, after: datetime
    ) -> datetime | None:
        """The Moon's next return to its natal degree after ``after``."""
        moon = chart.position(Planet.MOON)
        if moon is None:
            return None
        # The Moon returns every ~27.3 days; search the month ahead.
        return self.return_moment(
            Planet.MOON,
            moon.longitude,
            around=after + timedelta(days=13),
            window=timedelta(days=15),
        )

    # ---------------------------------------------------------------- charts

    def solar_return_chart(
        self,
        chart: Chart,
        year: int,
        *,
        latitude: float | None = None,
        longitude: float | None = None,
        timezone: str | None = None,
        house_system: HouseSystem | None = None,
    ) -> Chart | None:
        """Solar return chart, cast for the return instant.

        Location defaults to the birth place. Astrologers who relocate cast it
        for where the person actually is, which is why it is a parameter.
        """
        moment = self.solar_return_moment(chart, year)
        if moment is None:
            return None
        return self._chart_for_return(
            chart,
            moment,
            ChartKind.SOLAR_RETURN,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            house_system=house_system,
            label=f"solar_return_{year}",
        )

    def lunar_return_chart(
        self,
        chart: Chart,
        *,
        after: datetime,
        latitude: float | None = None,
        longitude: float | None = None,
        timezone: str | None = None,
        house_system: HouseSystem | None = None,
    ) -> Chart | None:
        moment = self.lunar_return_moment(chart, after=after)
        if moment is None:
            return None
        return self._chart_for_return(
            chart,
            moment,
            ChartKind.LUNAR_RETURN,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            house_system=house_system,
            label="lunar_return",
        )

    def _chart_for_return(
        self,
        natal: Chart,
        moment: datetime,
        kind: ChartKind,
        *,
        latitude: float | None,
        longitude: float | None,
        timezone: str | None,
        house_system: HouseSystem | None,
        label: str,
    ) -> Chart:
        subject = ChartSubject(
            kind=kind,
            moment_utc=moment,
            latitude=latitude if latitude is not None else natal.subject.latitude,
            longitude=longitude if longitude is not None else natal.subject.longitude,
            timezone=timezone or natal.subject.timezone,
            house_system=house_system or natal.house_system,
            location_name=natal.subject.location_name,
            label=label,
        )
        return self._engine.chart_for(subject)


_returns: ReturnEngine | None = None


def get_return_engine() -> ReturnEngine:
    global _returns
    if _returns is None:
        _returns = ReturnEngine()
    return _returns
