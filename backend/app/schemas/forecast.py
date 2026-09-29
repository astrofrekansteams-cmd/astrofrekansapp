"""Transit, calendar and horoscope contracts.

Shapes are stable and enum values are snake_case, because the Flutter client
binds to them directly. Every score carries the ids of the factors that
produced it, so "the influences behind this reading" is data, not a guess.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.calendar import CosmicEventType, EclipseSubtype
from app.domain.enums import AspectNature, AspectType, ChartAngle, Planet, ZodiacSign
from app.domain.horoscope import (
    FactorKind,
    HoroscopePeriod,
    LifeArea,
    Trend,
)
from app.domain.transit import PassDirection, TransitStatus, TransitTargetType
from app.schemas.common import APIModel


# ------------------------------------------------------------------ transits


class TransitPassResponse(APIModel):
    pass_number: int
    exact_at: datetime
    direction: PassDirection
    speed: float


class TransitResponse(APIModel):
    id: str
    transiting_body: Planet
    target_type: TransitTargetType
    target_body: Planet | None = None
    target_angle: ChartAngle | None = None
    target_house: int | None = None
    aspect_type: AspectType | None = None
    nature: AspectNature

    orb: float = Field(description="Orb at the reference instant, in degrees.")
    maximum_orb: float
    applying: bool

    start_at: datetime | None
    exact_at: datetime | None
    end_at: datetime | None
    status: TransitStatus
    strength: int = Field(ge=0, le=100)

    passes: list[TransitPassResponse] = Field(default_factory=list)
    affected_houses: list[int] = Field(default_factory=list)
    window_clipped: bool = False
    engine_version: str
    scoring_version: str
    metadata: dict = Field(default_factory=dict)


class HouseIngressResponse(APIModel):
    id: str
    planet: Planet
    from_house: int
    to_house: int
    entered_at: datetime
    estimated_exit_at: datetime | None = None
    retrograde: bool
    re_entry: bool


class TransitListResponse(APIModel):
    start_at: datetime
    end_at: datetime
    reference: datetime
    timezone: str
    range: str

    active: list[TransitResponse] = Field(default_factory=list)
    approaching: list[TransitResponse] = Field(default_factory=list)
    upcoming: list[TransitResponse] = Field(default_factory=list)
    ingresses: list[HouseIngressResponse] = Field(default_factory=list)

    engine_version: str
    scoring_version: str
    cached: bool = False


# ------------------------------------------------------------------ calendar


class CosmicEventResponse(APIModel):
    id: str
    type: CosmicEventType
    exact_at: datetime
    start_at: datetime | None = None
    end_at: datetime | None = None
    planet: Planet | None = None
    secondary_planet: Planet | None = None
    aspect: AspectType | None = None
    sign: ZodiacSign | None = None
    longitude: float | None = None
    degree: int | None = None
    eclipse_subtype: EclipseSubtype | None = None
    eclipse_magnitude: float | None = None
    node_distance: float | None = None
    metadata: dict = Field(default_factory=dict)


class CalendarResponse(APIModel):
    start_at: datetime
    end_at: datetime
    timezone: str
    events: list[CosmicEventResponse] = Field(default_factory=list)
    engine_version: str
    cached: bool = False


class NatalContactResponse(APIModel):
    target_body: Planet | None = None
    target_angle: ChartAngle | None = None
    aspect: AspectType
    orb: float


class PersonalEventResponse(APIModel):
    event: CosmicEventResponse
    affected_house: int | None
    natal_aspects: list[NatalContactResponse] = Field(default_factory=list)
    strength: int
    personal_relevance: str
    source_factors: list[str] = Field(default_factory=list)


class PersonalCalendarResponse(APIModel):
    start_at: datetime
    end_at: datetime
    timezone: str
    events: list[PersonalEventResponse] = Field(default_factory=list)
    engine_version: str
    cached: bool = False


# ----------------------------------------------------------------- scoring


class SourceFactorResponse(APIModel):
    id: str
    kind: FactorKind
    label: str
    contribution: float
    areas: list[LifeArea] = Field(default_factory=list)
    at: datetime | None = None
    detail: dict = Field(default_factory=dict)


class AreaScoreResponse(APIModel):
    area: LifeArea
    score: int = Field(ge=0, le=100)
    trend: Trend
    strength: int
    factor_ids: list[str] = Field(default_factory=list)


class ImportantHourResponse(APIModel):
    start: datetime
    end: datetime
    type: str
    strength: int
    reason: str
    factor_ids: list[str] = Field(default_factory=list)


class ImportantDateResponse(APIModel):
    date: datetime
    label: str
    strength: int
    nature: str
    factor_ids: list[str] = Field(default_factory=list)


class PeriodClusterResponse(APIModel):
    start_at: datetime
    end_at: datetime
    areas: list[LifeArea]
    strength: int
    label: str
    source_factors: list[str] = Field(default_factory=list)


class HouseActivationResponse(APIModel):
    house: int
    planets: list[Planet] = Field(default_factory=list)
    strength: int
    factor_ids: list[str] = Field(default_factory=list)


# --------------------------------------------------------------- horoscope


class DailyFrequencyResponse(APIModel):
    date: datetime
    timezone: str
    overall: int
    scores: dict[LifeArea, AreaScoreResponse]
    important_hours: list[ImportantHourResponse] = Field(default_factory=list)
    influences: list[SourceFactorResponse] = Field(default_factory=list)
    message_context: dict = Field(default_factory=dict)
    engine_version: str
    scoring_version: str
    cached: bool = False


class HoroscopeResponse(APIModel):
    period: HoroscopePeriod
    start_at: datetime
    end_at: datetime
    timezone: str

    overall_score: int
    areas: list[AreaScoreResponse] = Field(default_factory=list)

    important_dates: list[ImportantDateResponse] = Field(default_factory=list)
    important_hours: list[ImportantHourResponse] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    challenges: list[str] = Field(default_factory=list)

    major_transits: list[TransitResponse] = Field(default_factory=list)
    moon_events: list[CosmicEventResponse] = Field(default_factory=list)
    house_activations: list[HouseActivationResponse] = Field(default_factory=list)
    key_periods: list[PeriodClusterResponse] = Field(default_factory=list)

    source_factors: list[SourceFactorResponse] = Field(default_factory=list)
    engine_version: str
    scoring_version: str
    cached: bool = False


class MonthlyForecastResponse(APIModel):
    year: int
    month: int
    start_at: datetime
    end_at: datetime
    timezone: str

    overall: int
    areas: list[AreaScoreResponse] = Field(default_factory=list)
    general_theme: list[LifeArea] = Field(default_factory=list)

    key_periods: list[PeriodClusterResponse] = Field(default_factory=list)
    important_dates: list[ImportantDateResponse] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    challenges: list[str] = Field(default_factory=list)

    major_transits: list[TransitResponse] = Field(default_factory=list)
    moon_events: list[CosmicEventResponse] = Field(default_factory=list)
    retrogrades: list[CosmicEventResponse] = Field(default_factory=list)
    house_activations: list[HouseActivationResponse] = Field(default_factory=list)
    personal_events: list[PersonalEventResponse] = Field(default_factory=list)

    source_factors: list[SourceFactorResponse] = Field(default_factory=list)
    engine_version: str
    scoring_version: str
    cached: bool = False


class SolarReturnResponse(APIModel):
    year: int
    exact_at: datetime
    ascendant: float | None = None
    ascendant_sign: str | None = None
    sun_house: int | None = None


class AnnualForecastResponse(APIModel):
    year: int
    start_at: datetime
    end_at: datetime
    timezone: str

    overall: int
    areas: list[AreaScoreResponse] = Field(default_factory=list)

    major_transits: list[TransitResponse] = Field(default_factory=list)
    retrograde_periods: list[CosmicEventResponse] = Field(default_factory=list)
    eclipses: list[CosmicEventResponse] = Field(default_factory=list)
    jupiter_movements: list[HouseIngressResponse] = Field(default_factory=list)
    saturn_movements: list[HouseIngressResponse] = Field(default_factory=list)
    outer_planet_hits: list[TransitResponse] = Field(default_factory=list)
    house_activations: list[HouseActivationResponse] = Field(default_factory=list)

    key_periods: list[PeriodClusterResponse] = Field(default_factory=list)
    important_dates: list[ImportantDateResponse] = Field(default_factory=list)
    solar_return: SolarReturnResponse | None = None

    source_factors: list[SourceFactorResponse] = Field(default_factory=list)
    engine_version: str
    scoring_version: str
    cached: bool = False
