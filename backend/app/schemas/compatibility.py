"""Compatibility API contracts (synastry, composite, Davison)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from pydantic import Field, model_validator

from app.domain.compatibility import (
    CompatibilityKind,
    Direction,
    RelationshipTheme,
)
from app.domain.enums import (
    AspectNature,
    AspectType,
    ChartAngle,
    HouseSystem,
    Planet,
)
from app.domain.ai import Locale
from app.schemas.astrology import NatalChartResponse
from app.schemas.common import APIModel


class PersonRef(APIModel):
    """Who a chart is for.

    Exactly one of the three forms: the signed-in user, one of their saved
    people, or inline birth data. Saved people are always checked against the
    caller - a report can never be built from someone else's saved person by
    guessing an id.
    """

    me: bool = False
    saved_person_id: uuid.UUID | None = None

    birth_date: date | None = None
    birth_time: time | None = None
    birth_place: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = Field(default=None, max_length=64)
    house_system: HouseSystem = HouseSystem.PLACIDUS
    label: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def exactly_one_form(self) -> "PersonRef":
        forms = [self.me, self.saved_person_id is not None, self.birth_date is not None]
        if sum(1 for item in forms if item) != 1:
            raise ValueError(
                "Provide exactly one of: me, saved_person_id, or inline birth data."
            )
        return self


class CompatibilityInterpretRequest(APIModel):
    """Ask for the AI reading of a stored compatibility calculation."""

    locale: Locale | None = None
    refresh: bool = Field(
        default=False,
        description=(
            "Generate a new reading. The calculation never changes - only the "
            "reading of it."
        ),
    )
    background: bool = Field(
        default=True,
        description="Queue the generation and answer 202 with a job to poll.",
    )


class CompatibilityRequest(APIModel):
    person_a: PersonRef
    person_b: PersonRef
    house_system: HouseSystem = HouseSystem.PLACIDUS
    refresh: bool = False


class SynastryAspectResponse(APIModel):
    id: str
    person_a_body: Planet | None = None
    person_a_angle: ChartAngle | None = None
    person_b_body: Planet | None = None
    person_b_angle: ChartAngle | None = None
    aspect: AspectType
    nature: AspectNature
    orb: float
    max_orb: float
    weight: float
    themes: list[RelationshipTheme] = Field(default_factory=list)
    label: str


class HouseOverlayResponse(APIModel):
    id: str
    direction: Direction
    planet: Planet
    house: int
    longitude: float
    weight: float
    themes: list[RelationshipTheme] = Field(default_factory=list)
    label: str


class ThemeScoreResponse(APIModel):
    theme: RelationshipTheme
    score: int = Field(ge=0, le=100)
    strength: int
    positive_factors: list[str] = Field(default_factory=list)
    challenging_factors: list[str] = Field(default_factory=list)
    factor_ids: list[str] = Field(default_factory=list)


class SynastryResponse(APIModel):
    report_id: uuid.UUID | None = None
    kind: CompatibilityKind = CompatibilityKind.SYNASTRY

    overall_score: int = Field(ge=0, le=100)
    score_semantics: str = Field(
        description=(
            "What the number means. It is an astrological factor index, not a "
            "probability and not a prediction."
        )
    )
    themes: list[ThemeScoreResponse] = Field(default_factory=list)
    aspects: list[SynastryAspectResponse] = Field(default_factory=list)

    # Directional on purpose: A's planets in B's houses is a different
    # statement from B's planets in A's houses.
    overlays_a_in_b: list[HouseOverlayResponse] = Field(default_factory=list)
    overlays_b_in_a: list[HouseOverlayResponse] = Field(default_factory=list)

    highlights: list[str] = Field(default_factory=list)
    source_factors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    person_a_label: str | None = None
    person_b_label: str | None = None
    engine_version: str
    scoring_version: str
    cached: bool = False


class CompositeResponse(APIModel):
    report_id: uuid.UUID | None = None
    kind: CompatibilityKind = CompatibilityKind.COMPOSITE

    method: str = Field(description="Midpoint method, e.g. midpoint_v1.")
    house_method: str = Field(
        description=(
            "How the composite houses were derived. Software differs here, so "
            "the method is named rather than assumed."
        )
    )
    chart: NatalChartResponse
    aspects: list[dict] = Field(default_factory=list)
    elements: dict[str, int] = Field(default_factory=dict)
    modalities: dict[str, int] = Field(default_factory=dict)
    dominant_element: str | None = None
    dominant_modality: str | None = None
    ambiguous_midpoints: list[str] = Field(
        default_factory=list,
        description=(
            "Points that were exactly opposite in the two charts, where the "
            "midpoint is not unique."
        ),
    )
    warnings: list[str] = Field(default_factory=list)
    engine_version: str
    cached: bool = False


class DavisonResponse(APIModel):
    report_id: uuid.UUID | None = None
    kind: CompatibilityKind = CompatibilityKind.DAVISON

    method: str
    midpoint_utc: datetime
    midpoint_latitude: float
    midpoint_longitude: float
    chart: NatalChartResponse
    warnings: list[str] = Field(default_factory=list)
    engine_version: str
    cached: bool = False


class CompatibilityReportSummary(APIModel):
    id: uuid.UUID
    kind: CompatibilityKind
    person_a_label: str | None
    person_b_label: str | None
    person_a_ref: str
    person_b_ref: str
    engine_version: str
    scoring_version: str
    created_at: datetime


class CompatibilityReportResponse(CompatibilityReportSummary):
    """A stored report, exactly as it was produced.

    Reports are snapshots: editing a saved person afterwards never rewrites
    one, it produces a new report.
    """

    structured_result: dict
