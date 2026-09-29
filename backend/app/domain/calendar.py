"""Cosmic calendar domain types.

Global sky events (moon phases, stations, eclipses, ingresses, mundane
aspects) are independent of any user. A *personal* event is one of those
intersected with a natal chart: which house it falls in, what it aspects, how
much it matters to that person.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.enums import AspectType, ChartAngle, Planet, ZodiacSign


class CosmicEventType(StrEnum):
    NEW_MOON = "new_moon"
    FULL_MOON = "full_moon"
    FIRST_QUARTER = "first_quarter"
    LAST_QUARTER = "last_quarter"

    STATION_RETROGRADE = "station_retrograde"
    STATION_DIRECT = "station_direct"

    SOLAR_ECLIPSE = "solar_eclipse"
    LUNAR_ECLIPSE = "lunar_eclipse"

    INGRESS = "ingress"

    CONJUNCTION = "conjunction"
    OPPOSITION = "opposition"
    SQUARE = "square"
    TRINE = "trine"
    SEXTILE = "sextile"

    @property
    def is_moon_phase(self) -> bool:
        return self in (
            CosmicEventType.NEW_MOON,
            CosmicEventType.FULL_MOON,
            CosmicEventType.FIRST_QUARTER,
            CosmicEventType.LAST_QUARTER,
        )

    @property
    def is_eclipse(self) -> bool:
        return self in (
            CosmicEventType.SOLAR_ECLIPSE,
            CosmicEventType.LUNAR_ECLIPSE,
        )

    @property
    def is_station(self) -> bool:
        return self in (
            CosmicEventType.STATION_RETROGRADE,
            CosmicEventType.STATION_DIRECT,
        )

    @classmethod
    def for_aspect(cls, aspect: AspectType) -> "CosmicEventType":
        return cls(aspect.value)


class EclipseSubtype(StrEnum):
    """Left ``None`` unless the geometry actually supports the call.

    A wrong 'total eclipse' is worse than no subtype, so the engine only
    assigns one when the umbral geometry is unambiguous.
    """

    PARTIAL = "partial"
    TOTAL = "total"
    ANNULAR = "annular"
    PENUMBRAL = "penumbral"


@dataclass(slots=True, frozen=True)
class CosmicEvent:
    id: str
    type: CosmicEventType
    exact_at: datetime

    # Retrogrades and long aspects have a window; instants do not.
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

    # How far the syzygy sat from the lunar node, in degrees - the reason an
    # eclipse was (or was not) called.
    node_distance: float | None = None

    engine_version: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def is_range(self) -> bool:
        return self.start_at is not None and self.end_at is not None


@dataclass(slots=True, frozen=True)
class NatalContact:
    """How a sky event touches one natal point."""

    target_body: Planet | None
    target_angle: ChartAngle | None
    aspect: AspectType
    orb: float

    @property
    def label(self) -> str:
        if self.target_body is not None:
            return self.target_body.value
        return self.target_angle.value if self.target_angle else "unknown"


@dataclass(slots=True, frozen=True)
class PersonalCosmicEvent:
    """A global event seen through one chart."""

    event: CosmicEvent
    affected_house: int | None
    natal_aspects: list[NatalContact] = field(default_factory=list)
    strength: int = 0
    relevance: str = ""
    source_factors: list[str] = field(default_factory=list)
