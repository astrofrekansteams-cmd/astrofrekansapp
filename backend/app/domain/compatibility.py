"""Compatibility domain types.

Synastry, composite and Davison all produce *structured* results with the
factor ids behind every score. No prose - that is phase B6 - and no
prediction: the score is an astrological factor index, never a probability
that a relationship will work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.astrology import Chart
from app.domain.enums import AspectNature, AspectType, ChartAngle, Planet


class CompatibilityKind(StrEnum):
    SYNASTRY = "synastry"
    COMPOSITE = "composite"
    DAVISON = "davison"


class RelationshipTheme(StrEnum):
    GENERAL = "general"
    EMOTIONAL = "emotional"
    COMMUNICATION = "communication"
    ROMANCE = "romance"
    SEXUAL_CHEMISTRY = "sexual_chemistry"
    TRUST = "trust"
    LONG_TERM = "long_term"
    CONFLICT = "conflict"
    KARMIC = "karmic"


class Direction(StrEnum):
    """House overlays are directional; aspects are not.

    ``A_TO_B`` means "person A's planet in person B's house".
    """

    A_TO_B = "a_to_b"
    B_TO_A = "b_to_a"
    MUTUAL = "mutual"


@dataclass(slots=True, frozen=True)
class SynastryAspect:
    id: str
    person_a_body: Planet | None
    person_a_angle: ChartAngle | None
    person_b_body: Planet | None
    person_b_angle: ChartAngle | None
    aspect: AspectType
    orb: float
    max_orb: float
    weight: float
    nature: AspectNature
    themes: list[RelationshipTheme] = field(default_factory=list)

    @property
    def label(self) -> str:
        left = self.person_a_body.value if self.person_a_body else (
            self.person_a_angle.value if self.person_a_angle else "?"
        )
        right = self.person_b_body.value if self.person_b_body else (
            self.person_b_angle.value if self.person_b_angle else "?"
        )
        return f"a_{left} {self.aspect.value} b_{right}"


@dataclass(slots=True, frozen=True)
class HouseOverlay:
    """One person's planet falling in the other's house.

    Directional on purpose: "her Venus in his 7th" and "his Venus in her 7th"
    are different statements about the relationship, and averaging them away
    loses the asymmetry that makes synastry useful.
    """

    id: str
    direction: Direction
    planet: Planet
    house: int
    longitude: float
    weight: float
    themes: list[RelationshipTheme] = field(default_factory=list)

    @property
    def label(self) -> str:
        owner, host = ("a", "b") if self.direction is Direction.A_TO_B else ("b", "a")
        return f"{owner}_{self.planet.value} in {host}_house_{self.house}"


@dataclass(slots=True, frozen=True)
class ThemeScore:
    theme: RelationshipTheme
    score: int
    strength: int
    positive_factors: list[str] = field(default_factory=list)
    challenging_factors: list[str] = field(default_factory=list)
    factor_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class SynastryResult:
    overall_score: int
    score_semantics: str
    themes: list[ThemeScore]
    aspects: list[SynastryAspect]
    overlays_a_in_b: list[HouseOverlay]
    overlays_b_in_a: list[HouseOverlay]
    highlights: list[str] = field(default_factory=list)
    source_factors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    engine_version: str = ""
    scoring_version: str = ""


@dataclass(slots=True, frozen=True)
class CompositeResult:
    """A midpoint composite chart plus its aspects."""

    chart: Chart
    method: str
    house_method: str
    aspects: list[dict] = field(default_factory=list)
    elements: dict = field(default_factory=dict)
    modalities: dict = field(default_factory=dict)
    dominant_element: str | None = None
    dominant_modality: str | None = None
    ambiguous_midpoints: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    engine_version: str = ""


@dataclass(slots=True, frozen=True)
class DavisonResult:
    """A real chart for the midpoint time and place."""

    chart: Chart
    midpoint_utc: datetime
    midpoint_latitude: float
    midpoint_longitude: float
    method: str
    warnings: list[str] = field(default_factory=list)
    engine_version: str = ""
