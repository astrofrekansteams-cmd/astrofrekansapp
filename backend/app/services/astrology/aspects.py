"""Aspect detection with a configurable orb policy.

Orbs are data, not magic numbers scattered through the code: the default
policy below is documented in ``docs/astrology_engine.md`` and can be replaced
per request (tight orbs for transits, wider for natal work).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.astrology import AspectHit, PlanetPosition, separation, signed_separation
from app.domain.enums import AspectType, Planet


@dataclass(slots=True, frozen=True)
class OrbPolicy:
    """Maximum orb (degrees) per aspect, with per-body modifiers."""

    base: dict[AspectType, float] = field(
        default_factory=lambda: {
            AspectType.CONJUNCTION: 8.0,
            AspectType.OPPOSITION: 8.0,
            AspectType.TRINE: 7.0,
            AspectType.SQUARE: 6.0,
            AspectType.SEXTILE: 4.0,
        }
    )
    luminary_bonus: float = 2.0
    node_penalty: float = -2.0

    def limit(self, aspect: AspectType, first: Planet, second: Planet) -> float:
        orb = self.base[aspect]
        if first.is_luminary or second.is_luminary:
            orb += self.luminary_bonus
        if first.is_point or second.is_point:
            orb += self.node_penalty
        return max(orb, 1.0)


NATAL_ORBS = OrbPolicy()
TRANSIT_ORBS = OrbPolicy(
    base={
        AspectType.CONJUNCTION: 3.0,
        AspectType.OPPOSITION: 3.0,
        AspectType.TRINE: 3.0,
        AspectType.SQUARE: 3.0,
        AspectType.SEXTILE: 2.0,
    },
    luminary_bonus=1.0,
    node_penalty=-1.0,
)


def classify_pair(
    *,
    first_longitude: float,
    second_longitude: float,
    first: Planet,
    second: Planet,
    first_speed: float = 0.0,
    second_speed: float = 0.0,
    policy: OrbPolicy = NATAL_ORBS,
    aspects: tuple[AspectType, ...] = tuple(AspectType),
) -> AspectHit | None:
    """The tightest aspect between two longitudes, or ``None``."""
    gap = separation(first_longitude, second_longitude)
    best: AspectHit | None = None

    for aspect in aspects:
        orb = abs(gap - aspect.angle)
        if orb > policy.limit(aspect, first, second):
            continue
        if best is not None and orb >= best.orb:
            continue
        best = AspectHit(
            first=first,
            second=second,
            aspect=aspect,
            orb=round(orb, 4),
            applying=_is_applying(
                first_longitude,
                second_longitude,
                first_speed,
                second_speed,
                aspect.angle,
            ),
            exact_angle=aspect.angle,
        )
    return best


def _is_applying(
    first_longitude: float,
    second_longitude: float,
    first_speed: float,
    second_speed: float,
    aspect_angle: float,
) -> bool:
    """True when the separation is moving *towards* the exact angle.

    Compares the current orb with the orb a short step later, using the two
    bodies' longitude speeds. With no speed information it returns False
    rather than guessing.
    """
    if first_speed == 0.0 and second_speed == 0.0:
        return False
    step = 0.01  # days
    current = abs(separation(first_longitude, second_longitude) - aspect_angle)
    later = abs(
        separation(
            first_longitude + first_speed * step,
            second_longitude + second_speed * step,
        )
        - aspect_angle
    )
    return later < current


def find_aspects(
    positions: list[PlanetPosition],
    *,
    policy: OrbPolicy = NATAL_ORBS,
    include_nodes: bool = True,
) -> list[AspectHit]:
    """All aspects inside one chart, tightest orb first."""
    bodies = [
        position
        for position in positions
        if include_nodes or not position.planet.is_point
    ]
    # The south node mirrors the north node exactly; listing both would double
    # every aspect it makes.
    bodies = [p for p in bodies if p.planet != Planet.SOUTH_NODE]

    hits: list[AspectHit] = []
    for index, first in enumerate(bodies):
        for second in bodies[index + 1 :]:
            hit = classify_pair(
                first_longitude=first.longitude,
                second_longitude=second.longitude,
                first=first.planet,
                second=second.planet,
                first_speed=first.speed_longitude,
                second_speed=second.speed_longitude,
                policy=policy,
            )
            if hit is not None:
                hits.append(hit)
    hits.sort(key=lambda hit: (hit.orb, hit.first.value, hit.second.value))
    return hits


def cross_chart_aspects(
    first_positions: list[PlanetPosition],
    second_positions: list[PlanetPosition],
    *,
    policy: OrbPolicy = NATAL_ORBS,
) -> list[AspectHit]:
    """Synastry style: every body of chart A against every body of chart B."""
    hits: list[AspectHit] = []
    for first in first_positions:
        if first.planet == Planet.SOUTH_NODE:
            continue
        for second in second_positions:
            if second.planet == Planet.SOUTH_NODE:
                continue
            hit = classify_pair(
                first_longitude=first.longitude,
                second_longitude=second.longitude,
                first=first.planet,
                second=second.planet,
                first_speed=first.speed_longitude,
                second_speed=second.speed_longitude,
                policy=policy,
            )
            if hit is not None:
                hits.append(hit)
    hits.sort(key=lambda hit: hit.orb)
    return hits


def angular_distance_to_aspect(
    longitude: float, target: float, aspect: AspectType
) -> float:
    """Signed distance to exactness; negative means the aspect is behind."""
    return signed_separation(separation(longitude, target), aspect.angle)
