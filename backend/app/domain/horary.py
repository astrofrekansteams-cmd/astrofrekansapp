"""Horary domain types.

The engine produces *structured factors*, never a verdict. There is no
"yes"/"no" field anywhere in this module by design: the judgement belongs to
the astrologer (expert mode) or to Astro AI reading these factors with proper
framing (phase B6). A backend that answers "yes, you will get the job" would
be making a claim the astrology cannot support and the product should not
make.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.enums import AspectType, Planet, ZodiacSign
from app.services.astrology.dignities import (
    AccidentalDignity,
    DignityKind,
    EssentialDignity,
)


class HoraryStatus(StrEnum):
    CREATED = "created"
    CALCULATED = "calculated"
    READY = "ready"
    FAILED = "failed"


class ReceptionKind(StrEnum):
    DOMICILE = "domicile"
    EXALTATION = "exaltation"
    TRIPLICITY = "triplicity"
    TERM = "term"
    FACE = "face"


class PerfectionKind(StrEnum):
    DIRECT = "direct_perfection"
    TRANSLATION = "translation_of_light"
    COLLECTION = "collection_of_light"
    MUTUAL_RECEPTION = "mutual_reception"


class ObstructionKind(StrEnum):
    PROHIBITION = "prohibition"
    REFRANATION = "refranation"
    SEPARATING = "separating_significators"
    COMBUSTION = "significator_combust"
    NO_PERFECTION = "no_perfection_found"

    # Documented but not implemented; see ``NOT_IMPLEMENTED_TECHNIQUES``.
    FRUSTRATION = "frustration"


# Techniques the engine deliberately does not claim to detect. They are
# reported in the response so nobody assumes silence means absence.
NOT_IMPLEMENTED_TECHNIQUES: tuple[str, ...] = (
    "frustration",
    "besiegement",
    "abscission_of_light",
)


@dataclass(slots=True, frozen=True)
class Significator:
    """A planet standing for a person or a matter."""

    role: str  # "querent", "quesited", "co_significator"
    house: int
    sign: ZodiacSign
    planet: Planet
    longitude: float
    speed: float
    retrograde: bool
    in_house: int | None
    essential: EssentialDignity | None = None
    accidental: AccidentalDignity | None = None
    note: str | None = None

    @property
    def is_dignified(self) -> bool:
        return bool(self.essential and self.essential.is_dignified)


@dataclass(slots=True, frozen=True)
class HoraryAspect:
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
    note: str | None = None


@dataclass(slots=True, frozen=True)
class Reception:
    id: str
    from_planet: Planet
    to_planet: Planet
    kind: ReceptionKind
    mutual: bool
    strength: int
    note: str | None = None


@dataclass(slots=True, frozen=True)
class MoonCondition:
    sign: ZodiacSign
    degree: float
    house: int | None
    speed: float
    phase: str
    void_of_course: bool
    void_definition: str
    last_aspect: HoraryAspect | None
    next_aspect: HoraryAspect | None
    leaves_sign_at: datetime | None
    in_via_combusta: bool
    essential: EssentialDignity | None = None
    accidental: AccidentalDignity | None = None


@dataclass(slots=True, frozen=True)
class PerfectionFactor:
    id: str
    kind: PerfectionKind
    planets: list[Planet]
    aspect: AspectType | None
    exact_at: datetime | None
    days_to_exact: float | None
    detail: dict = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ObstructionFactor:
    id: str
    kind: ObstructionKind
    planets: list[Planet]
    detail: dict = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class DignityFactor:
    id: str
    planet: Planet
    role: str
    kinds: list[DignityKind]
    score: int
    detail: dict = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class HoraryWarning:
    code: str
    message: str
    detail: dict = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class HoraryAnalysis:
    """Everything the engine can say, and nothing it cannot."""

    question: str
    category: str | None
    asked_at_utc: datetime

    querent_house: int
    quesited_house: int
    alternative_quesited_houses: list[int]

    querent: Significator
    quesited: Significator
    co_significator: Significator | None

    moon: MoonCondition

    receptions: list[Reception] = field(default_factory=list)
    applying_aspects: list[HoraryAspect] = field(default_factory=list)
    separating_aspects: list[HoraryAspect] = field(default_factory=list)

    perfection_factors: list[PerfectionFactor] = field(default_factory=list)
    obstruction_factors: list[ObstructionFactor] = field(default_factory=list)
    dignity_factors: list[DignityFactor] = field(default_factory=list)

    house_rulers: dict[int, Planet] = field(default_factory=dict)
    warnings: list[HoraryWarning] = field(default_factory=list)
    source_factors: list[str] = field(default_factory=list)

    is_day_chart: bool = True
    not_implemented: list[str] = field(default_factory=list)
    confidence_metadata: dict = field(default_factory=dict)

    engine_version: str = ""
    rules_version: str = ""
    dignity_version: str = ""
