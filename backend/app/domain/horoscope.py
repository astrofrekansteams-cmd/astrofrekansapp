"""Structured horoscope and forecast results.

Everything here is *data*, not prose. Astro AI (phase B6) writes the text from
these numbers, an expert reads the same numbers in their panel, and the app can
show "the influences behind this reading" because every score carries the ids
of the factors that produced it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.calendar import CosmicEvent, PersonalCosmicEvent
from app.domain.enums import Planet
from app.domain.transit import HouseIngress, TransitEvent


class HoroscopePeriod(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class LifeArea(StrEnum):
    """The scored categories, shared by horoscopes and the daily frequency."""

    GENERAL_ENERGY = "general_energy"
    LOVE = "love"
    RELATIONSHIPS = "relationships"
    CAREER = "career"
    MONEY = "money"
    HEALTH_BALANCE = "health_balance"
    PERSONAL_GROWTH = "personal_growth"
    LUCK = "luck"
    MOOD = "mood"


class Trend(StrEnum):
    RISING = "rising"
    STEADY = "steady"
    FALLING = "falling"


class FactorKind(StrEnum):
    TRANSIT = "transit"
    HOUSE_INGRESS = "house_ingress"
    MOON_HOUSE = "moon_house"
    MOON_PHASE = "moon_phase"
    COSMIC_EVENT = "cosmic_event"
    RETROGRADE = "retrograde"


@dataclass(slots=True, frozen=True)
class SourceFactor:
    """One reason a score moved, kept so the UI can list it.

    ``id`` is stable for a given chart and moment, so the client can match a
    factor to the transit card it already shows.
    """

    id: str
    kind: FactorKind
    label: str
    contribution: float
    areas: list[LifeArea] = field(default_factory=list)
    at: datetime | None = None
    detail: dict = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class AreaScore:
    area: LifeArea
    score: int
    trend: Trend
    strength: int
    factor_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class ImportantHour:
    """A window inside the day, derived from real exact aspect times."""

    start: datetime
    end: datetime
    type: str
    strength: int
    reason: str
    factor_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class ImportantDate:
    date: datetime
    label: str
    strength: int
    nature: str
    factor_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class PeriodCluster:
    """A stretch of days that share a theme, found by clustering the events."""

    start_at: datetime
    end_at: datetime
    areas: list[LifeArea]
    strength: int
    source_factors: list[str] = field(default_factory=list)
    label: str = ""


@dataclass(slots=True, frozen=True)
class HouseActivation:
    house: int
    planets: list[Planet]
    strength: int
    factor_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class PersonalHoroscope:
    period: HoroscopePeriod
    start_at: datetime
    end_at: datetime
    timezone: str

    overall_score: int
    areas: list[AreaScore] = field(default_factory=list)

    important_dates: list[ImportantDate] = field(default_factory=list)
    important_hours: list[ImportantHour] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    challenges: list[str] = field(default_factory=list)

    major_transits: list[TransitEvent] = field(default_factory=list)
    moon_events: list[CosmicEvent] = field(default_factory=list)
    house_activations: list[HouseActivation] = field(default_factory=list)
    key_periods: list[PeriodCluster] = field(default_factory=list)

    source_factors: list[SourceFactor] = field(default_factory=list)

    engine_version: str = ""
    scoring_version: str = ""

    def area(self, area: LifeArea) -> AreaScore | None:
        for item in self.areas:
            if item.area is area:
                return item
        return None


@dataclass(slots=True, frozen=True)
class DailyFrequency:
    """The Home screen's daily numbers - deterministic, never random."""

    date: datetime
    timezone: str
    overall: int
    scores: dict[LifeArea, AreaScore]
    important_hours: list[ImportantHour] = field(default_factory=list)
    influences: list[SourceFactor] = field(default_factory=list)
    message_context: dict = field(default_factory=dict)
    engine_version: str = ""
    scoring_version: str = ""


@dataclass(slots=True, frozen=True)
class MonthlyForecast:
    year: int
    month: int
    start_at: datetime
    end_at: datetime
    timezone: str

    overall: int
    areas: list[AreaScore] = field(default_factory=list)
    general_theme: list[LifeArea] = field(default_factory=list)

    key_periods: list[PeriodCluster] = field(default_factory=list)
    important_dates: list[ImportantDate] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    challenges: list[str] = field(default_factory=list)

    major_transits: list[TransitEvent] = field(default_factory=list)
    moon_events: list[CosmicEvent] = field(default_factory=list)
    retrogrades: list[CosmicEvent] = field(default_factory=list)
    house_activations: list[HouseActivation] = field(default_factory=list)
    personal_events: list[PersonalCosmicEvent] = field(default_factory=list)

    source_factors: list[SourceFactor] = field(default_factory=list)
    engine_version: str = ""
    scoring_version: str = ""


@dataclass(slots=True, frozen=True)
class SolarReturnSummary:
    year: int
    exact_at: datetime
    ascendant: float | None
    ascendant_sign: str | None
    sun_house: int | None
    chart_id: str | None = None


@dataclass(slots=True, frozen=True)
class AnnualForecast:
    year: int
    start_at: datetime
    end_at: datetime
    timezone: str

    overall: int
    areas: list[AreaScore] = field(default_factory=list)

    major_transits: list[TransitEvent] = field(default_factory=list)
    retrograde_periods: list[CosmicEvent] = field(default_factory=list)
    eclipses: list[CosmicEvent] = field(default_factory=list)
    jupiter_movements: list[HouseIngress] = field(default_factory=list)
    saturn_movements: list[HouseIngress] = field(default_factory=list)
    outer_planet_hits: list[TransitEvent] = field(default_factory=list)
    house_activations: list[HouseActivation] = field(default_factory=list)

    key_periods: list[PeriodCluster] = field(default_factory=list)
    important_dates: list[ImportantDate] = field(default_factory=list)
    solar_return: SolarReturnSummary | None = None

    source_factors: list[SourceFactor] = field(default_factory=list)
    engine_version: str = ""
    scoring_version: str = ""
