"""Transit domain types.

A transit is not a single instant: it opens, perfects (possibly several times
when the transiting body stations retrograde) and closes. The model keeps that
shape, because the product shows "3 days left" and "exact at 06:12", and the
expert panel later needs the same structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.enums import AspectNature, AspectType, ChartAngle, Planet


class TransitTargetType(StrEnum):
    NATAL_PLANET = "natal_planet"
    NATAL_ANGLE = "natal_angle"
    HOUSE_INGRESS = "house_ingress"


class TransitStatus(StrEnum):
    APPROACHING = "approaching"
    EXACT = "exact"
    SEPARATING = "separating"


class PassDirection(StrEnum):
    DIRECT = "direct"
    RETROGRADE = "retrograde"


@dataclass(slots=True, frozen=True)
class TransitPass:
    """One perfection of an aspect inside a single transit cycle.

    Saturn trine Venus can perfect three times - direct, retrograde, direct -
    and astrologers treat those as one story with three beats, not three
    separate transits.
    """

    pass_number: int
    exact_at: datetime
    direction: PassDirection
    speed: float


@dataclass(slots=True, frozen=True)
class TransitEvent:
    id: str
    transiting_body: Planet
    target_type: TransitTargetType

    # Exactly one of these is set, depending on target_type.
    target_body: Planet | None = None
    target_angle: ChartAngle | None = None
    target_house: int | None = None

    aspect_type: AspectType | None = None

    orb: float = 0.0
    maximum_orb: float = 0.0
    applying: bool = False

    start_at: datetime | None = None
    exact_at: datetime | None = None
    end_at: datetime | None = None

    status: TransitStatus = TransitStatus.APPROACHING
    strength: int = 0

    passes: list[TransitPass] = field(default_factory=list)
    affected_houses: list[int] = field(default_factory=list)

    # True when the window ran past the search horizon (slow outer planets).
    window_clipped: bool = False

    engine_version: str = ""
    scoring_version: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def nature(self) -> AspectNature:
        return self.aspect_type.nature if self.aspect_type else AspectNature.NEUTRAL

    @property
    def is_multi_pass(self) -> bool:
        return len(self.passes) > 1

    @property
    def target_label(self) -> str:
        if self.target_type is TransitTargetType.NATAL_PLANET and self.target_body:
            return self.target_body.value
        if self.target_type is TransitTargetType.NATAL_ANGLE and self.target_angle:
            return self.target_angle.value
        if self.target_house is not None:
            return f"house_{self.target_house}"
        return "unknown"

    def duration_days(self) -> float | None:
        if self.start_at is None or self.end_at is None:
            return None
        return (self.end_at - self.start_at).total_seconds() / 86400


@dataclass(slots=True, frozen=True)
class HouseIngress:
    """A transiting body crossing a natal house cusp.

    Retrograde motion can take a planet back out of a house and in again, so
    every crossing is its own record and ``re_entry`` marks the repeats.
    """

    id: str
    planet: Planet
    from_house: int
    to_house: int
    entered_at: datetime
    estimated_exit_at: datetime | None = None
    retrograde: bool = False
    re_entry: bool = False
    engine_version: str = ""

    @property
    def is_forward(self) -> bool:
        return not self.retrograde
