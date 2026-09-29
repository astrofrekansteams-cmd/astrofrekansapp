"""Horary API contracts.

There is no verdict field anywhere in here. The engine reports what the chart
contains - significators, dignities, perfection and obstruction factors,
warnings - and the judgement is the astrologer's (or, in phase B6, Astro AI's
with proper framing).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field, field_validator

from app.domain.enums import AspectType, Planet, ZodiacSign
from app.domain.horary import (
    HoraryStatus,
    ObstructionKind,
    PerfectionKind,
    ReceptionKind,
)
from app.schemas.common import APIModel
from app.services.astrology.dignities import (
    DignityKind,
    HousePlacement,
    MotionState,
    SolarCondition,
)
from app.services.astrology.horary_rules import HoraryCategory


class HoraryQuestionRequest(APIModel):
    question: str = Field(min_length=3, max_length=500)
    category: HoraryCategory | None = None

    # The moment the question was asked. Defaults to now, because that is
    # what horary means; a client may send it explicitly when the user typed
    # the question offline.
    asked_at: datetime | None = None
    timezone: str | None = Field(default=None, max_length=64)

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_name: str | None = Field(default=None, max_length=255)

    # An astrologer can point the question at a different house.
    house_override: int | None = Field(default=None, ge=1, le=12)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("The question is too short.")
        return cleaned


class HoraryQuestionResponse(APIModel):
    id: uuid.UUID
    question: str
    category: HoraryCategory | None
    status: HoraryStatus
    asked_at_utc: datetime
    timezone: str
    latitude: float
    longitude: float
    location_name: str | None
    house_override: int | None = None
    chart_id: uuid.UUID | None = None
    duplicate_suspected: bool = False
    created_at: datetime


class EssentialDignityResponse(APIModel):
    planet: Planet
    sign: ZodiacSign
    degree: float
    dignities: list[DignityKind]
    debilities: list[DignityKind]
    triplicity_ruler: Planet | None
    term_ruler: Planet | None
    face_ruler: Planet | None
    peregrine: bool
    score: int


class AccidentalDignityResponse(APIModel):
    planet: Planet
    house: int | None
    placement: HousePlacement | None
    motion: MotionState
    speed: float
    speed_ratio: float
    solar_condition: SolarCondition
    solar_distance: float
    notes: list[str] = Field(default_factory=list)


class SignificatorResponse(APIModel):
    role: str
    house: int
    sign: ZodiacSign
    planet: Planet
    longitude: float
    speed: float
    retrograde: bool
    in_house: int | None
    essential: EssentialDignityResponse | None = None
    accidental: AccidentalDignityResponse | None = None
    note: str | None = None


class HoraryAspectResponse(APIModel):
    id: str
    first: Planet
    second: Planet
    aspect: AspectType
    orb: float
    max_orb: float
    applying: bool
    exact_at: datetime | None
    perfects_before_sign_change: bool | None
    days_to_exact: float | None


class ReceptionResponse(APIModel):
    id: str
    from_planet: Planet
    to_planet: Planet
    kind: ReceptionKind
    mutual: bool
    strength: int
    note: str | None = None


class MoonConditionResponse(APIModel):
    sign: ZodiacSign
    degree: float
    house: int | None
    speed: float
    phase: str
    void_of_course: bool
    void_definition: str
    last_aspect: HoraryAspectResponse | None
    next_aspect: HoraryAspectResponse | None
    leaves_sign_at: datetime | None
    in_via_combusta: bool
    essential: EssentialDignityResponse | None = None
    accidental: AccidentalDignityResponse | None = None


class PerfectionFactorResponse(APIModel):
    id: str
    kind: PerfectionKind
    planets: list[Planet]
    aspect: AspectType | None
    exact_at: datetime | None
    days_to_exact: float | None
    detail: dict = Field(default_factory=dict)


class ObstructionFactorResponse(APIModel):
    id: str
    kind: ObstructionKind
    planets: list[Planet]
    detail: dict = Field(default_factory=dict)


class DignityFactorResponse(APIModel):
    id: str
    planet: Planet
    role: str
    kinds: list[DignityKind]
    score: int
    detail: dict = Field(default_factory=dict)


class HoraryWarningResponse(APIModel):
    code: str
    message: str
    detail: dict = Field(default_factory=dict)


class HoraryAnalysisResponse(APIModel):
    question_id: uuid.UUID
    question: str
    category: str | None
    asked_at_utc: datetime

    querent_house: int
    quesited_house: int
    alternative_quesited_houses: list[int] = Field(default_factory=list)

    querent: SignificatorResponse
    quesited: SignificatorResponse
    co_significator: SignificatorResponse | None

    moon: MoonConditionResponse
    house_rulers: dict[int, Planet] = Field(default_factory=dict)

    receptions: list[ReceptionResponse] = Field(default_factory=list)
    applying_aspects: list[HoraryAspectResponse] = Field(default_factory=list)
    separating_aspects: list[HoraryAspectResponse] = Field(default_factory=list)

    perfection_factors: list[PerfectionFactorResponse] = Field(default_factory=list)
    obstruction_factors: list[ObstructionFactorResponse] = Field(default_factory=list)
    dignity_factors: list[DignityFactorResponse] = Field(default_factory=list)

    warnings: list[HoraryWarningResponse] = Field(default_factory=list)
    source_factors: list[str] = Field(default_factory=list)

    is_day_chart: bool
    not_implemented: list[str] = Field(
        default_factory=list,
        description=(
            "Classical techniques this engine does not detect. Listed so "
            "silence is never read as absence."
        ),
    )
    confidence_metadata: dict = Field(default_factory=dict)

    engine_version: str
    rules_version: str
    dignity_version: str
    cached: bool = False
