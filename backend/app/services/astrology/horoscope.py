"""Personalised horoscope and forecast engine.

There is no sun-sign text here and no template: a reading is built from *this*
chart's transits, the Moon's placement in *these* houses, and the sky events
that actually touch the chart. The output is structured data with the source
factors attached, so phase B6 can write prose from it, an expert can read the
same numbers in their panel, and the app can list "the influences behind this
reading".
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.astrology import Chart, separation
from app.domain.calendar import (
    CosmicEvent,
    CosmicEventType,
    NatalContact,
    PersonalCosmicEvent,
)
from app.domain.enums import AspectType, ChartAngle, Planet
from app.domain.horoscope import (
    AnnualForecast,
    DailyFrequency,
    HoroscopePeriod,
    LifeArea,
    MonthlyForecast,
    PersonalHoroscope,
    SolarReturnSummary,
)
from app.domain.transit import TransitEvent
from app.services.astrology import scoring
from app.services.astrology import weights as W
from app.services.astrology.calendar import CosmicCalendarEngine, get_calendar_engine
from app.services.astrology.houses import house_of
from app.services.astrology.returns import ReturnEngine, get_return_engine
from app.services.astrology.transits import (
    DEFAULT_TRANSITING,
    SLOW_BODIES,
    TransitEngine,
    TransitSet,
    get_transit_engine,
)
from app.services.astrology.skyfield_engine import ENGINE_VERSION

# Personal relevance: how close a sky event has to come to a natal point.
PERSONAL_ASPECT_ORB: dict[AspectType, float] = {
    AspectType.CONJUNCTION: 5.0,
    AspectType.OPPOSITION: 5.0,
    AspectType.SQUARE: 4.0,
    AspectType.TRINE: 4.0,
    AspectType.SEXTILE: 3.0,
}


@dataclass(slots=True, frozen=True)
class PeriodWindow:
    start: datetime
    end: datetime
    timezone: str

    @property
    def utc(self) -> tuple[datetime, datetime]:
        return self.start.astimezone(UTC), self.end.astimezone(UTC)


def day_window(day: datetime, timezone: str) -> PeriodWindow:
    """A calendar day *in the user's timezone*, not a UTC day.

    "Today" must mean the user's today; a UTC day would shift the reading by
    hours and break the important-hours list.
    """
    zone = ZoneInfo(timezone)
    local = day.astimezone(zone)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return PeriodWindow(start=start, end=start + timedelta(days=1), timezone=timezone)


def week_window(day: datetime, timezone: str) -> PeriodWindow:
    zone = ZoneInfo(timezone)
    local = day.astimezone(zone)
    start = (local - timedelta(days=local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return PeriodWindow(start=start, end=start + timedelta(days=7), timezone=timezone)


def month_window(year: int, month: int, timezone: str) -> PeriodWindow:
    zone = ZoneInfo(timezone)
    start = datetime(year, month, 1, tzinfo=zone)
    end = (
        datetime(year + 1, 1, 1, tzinfo=zone)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=zone)
    )
    return PeriodWindow(start=start, end=end, timezone=timezone)


def year_window(year: int, timezone: str) -> PeriodWindow:
    zone = ZoneInfo(timezone)
    return PeriodWindow(
        start=datetime(year, 1, 1, tzinfo=zone),
        end=datetime(year + 1, 1, 1, tzinfo=zone),
        timezone=timezone,
    )


class HoroscopeEngine:
    def __init__(
        self,
        transits: TransitEngine | None = None,
        calendar: CosmicCalendarEngine | None = None,
        returns: ReturnEngine | None = None,
    ) -> None:
        self._transits = transits or get_transit_engine()
        self._calendar = calendar or get_calendar_engine()
        self._returns = returns or get_return_engine()

    # ----------------------------------------------------------- daily

    def daily_frequency(
        self,
        chart: Chart,
        *,
        day: datetime,
        timezone: str,
        transit_set: TransitSet | None = None,
        chart_fingerprint: str = "",
    ) -> DailyFrequency:
        window = day_window(day, timezone)
        start_utc, end_utc = window.utc
        midday = start_utc + (end_utc - start_utc) / 2

        transit_set = transit_set or self._transits.scan(
            chart,
            start=start_utc,
            end=end_utc,
            reference=midday,
            chart_fingerprint=chart_fingerprint,
        )

        bundle = scoring.FactorBundle.empty()
        for event in transit_set.events:
            bundle.add(scoring.transit_factor(event))

        moon_house = self._moon_house(chart, midday)
        if moon_house is not None:
            bundle.add(scoring.moon_house_factor(moon_house))

        for event in self._calendar.events(
            start_utc - timedelta(days=1),
            end_utc + timedelta(days=1),
            include_quarters=False,
            include_stations=False,
            include_ingresses=False,
            include_aspects=False,
            include_eclipses=False,
        ):
            if event.type.is_moon_phase:
                bundle.add(scoring.moon_phase_factor(event))

        for period in self._calendar.retrograde_periods(start_utc, end_utc):
            if period.start_at and period.end_at and period.start_at <= midday <= period.end_at:
                bundle.add(scoring.retrograde_factor(period))

        areas = scoring.score_areas(bundle)
        scores = {item.area: item for item in areas}

        return DailyFrequency(
            date=window.start,
            timezone=timezone,
            overall=scoring.overall_score(areas),
            scores=scores,
            important_hours=scoring.important_hours(
                transit_set.events, day_start=start_utc, day_end=end_utc
            ),
            influences=sorted(
                bundle.factors, key=lambda factor: -abs(factor.contribution)
            )[:12],
            message_context={
                "moon_house": moon_house,
                "moon_sign": self._moon_sign(midday),
                "strongest_transit": (
                    transit_set.events[0].id if transit_set.events else None
                ),
                "active_transits": len(transit_set.active()),
            },
            engine_version=ENGINE_VERSION,
            scoring_version=W.DAILY_FREQUENCY_VERSION,
        )

    def daily(
        self,
        chart: Chart,
        *,
        day: datetime,
        timezone: str,
        chart_fingerprint: str = "",
    ) -> PersonalHoroscope:
        window = day_window(day, timezone)
        return self._build_period(
            chart,
            window=window,
            period=HoroscopePeriod.DAILY,
            include_moon=True,
            chart_fingerprint=chart_fingerprint,
        )

    def weekly(
        self,
        chart: Chart,
        *,
        day: datetime,
        timezone: str,
        chart_fingerprint: str = "",
    ) -> PersonalHoroscope:
        """A week is not an average of seven days.

        It is built from the exact contacts that perfect during the week, the
        Moon's path through the houses, stations and ingresses - the things
        that actually distinguish one week from the next.
        """
        window = week_window(day, timezone)
        return self._build_period(
            chart,
            window=window,
            period=HoroscopePeriod.WEEKLY,
            include_moon=True,
            chart_fingerprint=chart_fingerprint,
        )

    def _build_period(
        self,
        chart: Chart,
        *,
        window: PeriodWindow,
        period: HoroscopePeriod,
        include_moon: bool,
        chart_fingerprint: str,
    ) -> PersonalHoroscope:
        start_utc, end_utc = window.utc
        reference = start_utc + (end_utc - start_utc) / 2

        transit_set = self._transits.scan(
            chart,
            start=start_utc,
            end=end_utc,
            reference=reference,
            include_moon=include_moon,
            chart_fingerprint=chart_fingerprint,
        )
        events = self._calendar.events(
            start_utc,
            end_utc,
            include_quarters=True,
            include_aspects=period
            in (HoroscopePeriod.MONTHLY, HoroscopePeriod.YEARLY),
        )

        bundle = scoring.FactorBundle.empty()
        for event in transit_set.events:
            bundle.add(scoring.transit_factor(event))
        for ingress in transit_set.ingresses:
            bundle.add(scoring.ingress_factor(ingress))
        for event in events:
            if event.type.is_moon_phase:
                bundle.add(scoring.moon_phase_factor(event))

        areas = scoring.score_areas(bundle)
        major = _major_transits(transit_set.events, period)
        opportunities, challenges = scoring.split_opportunities(major)

        return PersonalHoroscope(
            period=period,
            start_at=window.start,
            end_at=window.end,
            timezone=window.timezone,
            overall_score=scoring.overall_score(areas),
            areas=areas,
            important_dates=scoring.important_dates(
                transit_set.events, start=start_utc, end=end_utc
            ),
            important_hours=(
                scoring.important_hours(
                    transit_set.events, day_start=start_utc, day_end=end_utc
                )
                if period is HoroscopePeriod.DAILY
                else []
            ),
            opportunities=opportunities,
            challenges=challenges,
            major_transits=major,
            moon_events=[event for event in events if event.type.is_moon_phase],
            house_activations=scoring.house_activations(
                transit_set.events,
                transit_set.ingresses,
                self._transits.current_houses(chart, reference),
            ),
            key_periods=(
                scoring.cluster_periods(
                    transit_set.events, start=start_utc, end=end_utc
                )
                if period is not HoroscopePeriod.DAILY
                else []
            ),
            source_factors=sorted(
                bundle.factors, key=lambda factor: -abs(factor.contribution)
            )[:40],
            engine_version=ENGINE_VERSION,
            scoring_version=W.SCORING_VERSION,
        )

    # --------------------------------------------------------- monthly

    def monthly(
        self,
        chart: Chart,
        *,
        year: int,
        month: int,
        timezone: str,
        chart_fingerprint: str = "",
    ) -> MonthlyForecast:
        window = month_window(year, month, timezone)
        start_utc, end_utc = window.utc
        reference = start_utc + (end_utc - start_utc) / 2

        transit_set = self._transits.scan(
            chart,
            start=start_utc,
            end=end_utc,
            reference=reference,
            include_moon=False,
            chart_fingerprint=chart_fingerprint,
        )
        events = self._calendar.events(start_utc, end_utc)
        retrogrades = self._calendar.retrograde_periods(start_utc, end_utc)

        bundle = scoring.FactorBundle.empty()
        for event in transit_set.events:
            bundle.add(scoring.transit_factor(event))
        for ingress in transit_set.ingresses:
            bundle.add(scoring.ingress_factor(ingress))
        for event in events:
            if event.type.is_moon_phase:
                bundle.add(scoring.moon_phase_factor(event))
        for period in retrogrades:
            bundle.add(scoring.retrograde_factor(period))

        areas = scoring.score_areas(bundle)
        major = _major_transits(transit_set.events, HoroscopePeriod.MONTHLY)
        opportunities, challenges = scoring.split_opportunities(major)
        clusters = scoring.cluster_periods(
            transit_set.events, start=start_utc, end=end_utc
        )

        theme = [
            item.area
            for item in sorted(areas, key=lambda item: -abs(item.score - W.BASELINE_SCORE))[:3]
        ]

        return MonthlyForecast(
            year=year,
            month=month,
            start_at=window.start,
            end_at=window.end,
            timezone=timezone,
            overall=scoring.overall_score(areas),
            areas=areas,
            general_theme=theme,
            key_periods=clusters,
            important_dates=scoring.important_dates(
                transit_set.events, start=start_utc, end=end_utc, limit=12
            ),
            opportunities=opportunities,
            challenges=challenges,
            major_transits=major,
            moon_events=[event for event in events if event.type.is_moon_phase],
            retrogrades=retrogrades,
            house_activations=scoring.house_activations(
                transit_set.events,
                transit_set.ingresses,
                self._transits.current_houses(chart, reference),
            ),
            personal_events=self.personal_events(chart, events),
            source_factors=sorted(
                bundle.factors, key=lambda factor: -abs(factor.contribution)
            )[:60],
            engine_version=ENGINE_VERSION,
            scoring_version=W.SCORING_VERSION,
        )

    # ---------------------------------------------------------- annual

    def annual(
        self,
        chart: Chart,
        *,
        year: int,
        timezone: str,
        chart_fingerprint: str = "",
        include_solar_return: bool = True,
    ) -> AnnualForecast:
        window = year_window(year, timezone)
        start_utc, end_utc = window.utc
        reference = start_utc + (end_utc - start_utc) / 2

        # The Moon would add thousands of contacts and say nothing about a
        # year; the slow bodies are what a year is made of.
        transit_set = self._transits.scan(
            chart,
            start=start_utc,
            end=end_utc,
            reference=reference,
            include_moon=False,
            chart_fingerprint=chart_fingerprint,
        )
        events = self._calendar.events(start_utc, end_utc)
        retrogrades = self._calendar.retrograde_periods(start_utc, end_utc)

        bundle = scoring.FactorBundle.empty()
        for event in transit_set.events:
            bundle.add(scoring.transit_factor(event))
        for ingress in transit_set.ingresses:
            bundle.add(scoring.ingress_factor(ingress))
        for period in retrogrades:
            bundle.add(scoring.retrograde_factor(period))

        areas = scoring.score_areas(bundle)
        outer_hits = [
            event
            for event in transit_set.events
            if event.transiting_body in SLOW_BODIES
        ]

        solar_return = None
        if include_solar_return:
            solar_return = self.solar_return_summary(chart, year)

        return AnnualForecast(
            year=year,
            start_at=window.start,
            end_at=window.end,
            timezone=timezone,
            overall=scoring.overall_score(areas),
            areas=areas,
            major_transits=_major_transits(
                transit_set.events, HoroscopePeriod.YEARLY
            ),
            retrograde_periods=retrogrades,
            eclipses=[event for event in events if event.type.is_eclipse],
            jupiter_movements=[
                ingress
                for ingress in transit_set.ingresses
                if ingress.planet is Planet.JUPITER
            ],
            saturn_movements=[
                ingress
                for ingress in transit_set.ingresses
                if ingress.planet is Planet.SATURN
            ],
            outer_planet_hits=sorted(
                outer_hits, key=lambda event: -event.strength
            )[:30],
            house_activations=scoring.house_activations(
                transit_set.events,
                transit_set.ingresses,
                self._transits.current_houses(chart, reference),
            ),
            key_periods=scoring.cluster_periods(
                transit_set.events,
                start=start_utc,
                end=end_utc,
                limit=8,
            ),
            important_dates=scoring.important_dates(
                transit_set.events, start=start_utc, end=end_utc, limit=20
            ),
            solar_return=solar_return,
            source_factors=sorted(
                bundle.factors, key=lambda factor: -abs(factor.contribution)
            )[:80],
            engine_version=ENGINE_VERSION,
            scoring_version=W.SCORING_VERSION,
        )

    def solar_return_summary(
        self, chart: Chart, year: int
    ) -> SolarReturnSummary | None:
        moment = self._returns.solar_return_moment(chart, year)
        if moment is None:
            return None

        return_chart = self._returns.solar_return_chart(chart, year)
        ascendant = return_chart.angles.ascendant if return_chart and return_chart.angles else None
        sun = return_chart.position(Planet.SUN) if return_chart else None

        from app.domain.enums import ZodiacSign

        return SolarReturnSummary(
            year=year,
            exact_at=moment,
            ascendant=round(ascendant, 4) if ascendant is not None else None,
            ascendant_sign=(
                ZodiacSign.from_longitude(ascendant).value
                if ascendant is not None
                else None
            ),
            sun_house=sun.house if sun else None,
        )

    # ------------------------------------------------- personal calendar

    def personal_events(
        self, chart: Chart, events: list[CosmicEvent]
    ) -> list[PersonalCosmicEvent]:
        """Intersect global sky events with this chart.

        A full moon matters because of the house it lands in and what it
        aspects natally - not because it is a full moon.
        """
        personal: list[PersonalCosmicEvent] = []

        for event in events:
            longitude = event.longitude
            if longitude is None and event.planet is not None:
                longitude = float(
                    self._transits.sampler.longitudes(event.planet, [event.exact_at])[0]
                )
            if longitude is None:
                continue

            house = house_of(longitude, chart.houses) if chart.houses else None
            contacts = self._natal_contacts(chart, longitude)
            if house is None and not contacts:
                continue

            strength = _personal_strength(event, contacts, house)
            factor_ids = [event.id]
            personal.append(
                PersonalCosmicEvent(
                    event=event,
                    affected_house=house,
                    natal_aspects=contacts,
                    strength=strength,
                    relevance=_relevance_label(event, contacts, house),
                    source_factors=factor_ids,
                )
            )

        personal.sort(key=lambda item: (-item.strength, item.event.exact_at))
        return personal

    def _natal_contacts(
        self, chart: Chart, longitude: float
    ) -> list[NatalContact]:
        contacts: list[NatalContact] = []
        for position in chart.positions:
            for aspect, orb_limit in PERSONAL_ASPECT_ORB.items():
                orb = abs(separation(longitude, position.longitude) - aspect.angle)
                if orb <= orb_limit:
                    contacts.append(
                        NatalContact(
                            target_body=position.planet,
                            target_angle=None,
                            aspect=aspect,
                            orb=round(orb, 4),
                        )
                    )
                    break

        if chart.angles is not None:
            for angle, angle_longitude in (
                (ChartAngle.ASC, chart.angles.ascendant),
                (ChartAngle.MC, chart.angles.midheaven),
            ):
                for aspect, orb_limit in PERSONAL_ASPECT_ORB.items():
                    orb = abs(separation(longitude, angle_longitude) - aspect.angle)
                    if orb <= orb_limit:
                        contacts.append(
                            NatalContact(
                                target_body=None,
                                target_angle=angle,
                                aspect=aspect,
                                orb=round(orb, 4),
                            )
                        )
                        break

        contacts.sort(key=lambda contact: contact.orb)
        return contacts

    # ---------------------------------------------------------- helpers

    def _moon_house(self, chart: Chart, moment: datetime) -> int | None:
        if not chart.houses:
            return None
        longitude = float(
            self._transits.sampler.longitudes(Planet.MOON, [moment])[0]
        )
        return house_of(longitude, chart.houses)

    def _moon_sign(self, moment: datetime) -> str:
        from app.domain.enums import ZodiacSign

        longitude = float(
            self._transits.sampler.longitudes(Planet.MOON, [moment])[0]
        )
        return ZodiacSign.from_longitude(longitude).value


def _major_transits(
    events: list[TransitEvent], period: HoroscopePeriod
) -> list[TransitEvent]:
    limit = W.MAJOR_TRANSIT_LIMIT[period.value]
    strong = [
        event for event in events if event.strength >= W.MIN_MAJOR_STRENGTH
    ]
    return sorted(strong, key=lambda event: -event.strength)[:limit]


def _personal_strength(
    event: CosmicEvent, contacts: list[NatalContact], house: int | None
) -> int:
    base = {
        CosmicEventType.SOLAR_ECLIPSE: 90,
        CosmicEventType.LUNAR_ECLIPSE: 85,
        CosmicEventType.NEW_MOON: 55,
        CosmicEventType.FULL_MOON: 60,
        CosmicEventType.STATION_RETROGRADE: 50,
        CosmicEventType.STATION_DIRECT: 45,
        CosmicEventType.INGRESS: 30,
    }.get(event.type, 35)

    if contacts:
        tightest = min(contact.orb for contact in contacts)
        base += int(round(25 * max(0.0, 1.0 - tightest / 5.0)))
    if house in (1, 4, 7, 10):
        base += 10
    elif house is not None:
        base += 5
    return int(min(100, base))


def _relevance_label(
    event: CosmicEvent, contacts: list[NatalContact], house: int | None
) -> str:
    parts: list[str] = []
    if house is not None:
        parts.append(f"house_{house}")
    if contacts:
        first = contacts[0]
        parts.append(f"{first.aspect.value}_natal_{first.label}")
    return "|".join(parts) or "general"


_horoscope: HoroscopeEngine | None = None


def get_horoscope_engine() -> HoroscopeEngine:
    global _horoscope
    if _horoscope is None:
        _horoscope = HoroscopeEngine()
    return _horoscope
