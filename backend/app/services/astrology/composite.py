"""Composite and Davison charts.

Two different things that are often confused:

* **Composite** (``midpoint_v1``): not a real chart. Every point is the
  midpoint of the two natal positions, so the "planets" never existed in the
  sky together. Houses are derived from the composite Midheaven.
* **Davison**: a *real* chart, cast for the midpoint in time between the two
  births and the geographic midpoint between the two birthplaces. The planets
  really were there at that instant.

Two arithmetic traps, both handled and both tested:

1. **Circular midpoints.** 359° and 1° meet at 0°, not 180°. Every midpoint
   here goes through :func:`circular_midpoint`, which walks the short arc.
   Exact oppositions are genuinely ambiguous (two equally valid midpoints);
   the engine picks one deterministically and *says so* in
   ``ambiguous_midpoints``.
2. **Geographic midpoints.** Averaging longitudes puts the midpoint of 179°E
   and 179°W in the middle of Africa instead of on the date line, so Davison
   uses the spherical midpoint of the two positions as 3-D vectors.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from app.domain.astrology import (
    Chart,
    ChartAngles,
    ChartSubject,
    HousePosition,
    PlanetPosition,
    normalize_degrees,
    signed_separation,
)
from app.domain.compatibility import CompositeResult, DavisonResult
from app.domain.enums import AspectType, ChartKind, HouseSystem, Planet, ZodiacSign
from app.services.astrology.aspects import NATAL_ORBS, find_aspects
from app.services.astrology.houses import compute_houses, house_of
from app.services.astrology.skyfield_engine import ENGINE_VERSION, SkyfieldEngine, get_engine

COMPOSITE_METHOD = "midpoint_v1"
COMPOSITE_HOUSE_METHOD = "midpoint_mc_derived_v1"
DAVISON_METHOD = "davison_utc_geodesic_v1"

# Two longitudes this close to exactly opposite have no preferred midpoint.
OPPOSITION_TOLERANCE = 1e-6

# Two places this close to antipodal have no meaningful geographic midpoint.
ANTIPODAL_TOLERANCE_DEGREES = 0.5

COMPOSITE_BODIES: tuple[Planet, ...] = (
    Planet.SUN,
    Planet.MOON,
    Planet.MERCURY,
    Planet.VENUS,
    Planet.MARS,
    Planet.JUPITER,
    Planet.SATURN,
    Planet.URANUS,
    Planet.NEPTUNE,
    Planet.PLUTO,
    Planet.NORTH_NODE,
    Planet.SOUTH_NODE,
)


def circular_midpoint(first: float, second: float) -> tuple[float, bool]:
    """Midpoint of two ecliptic longitudes along the **short** arc.

    Returns ``(midpoint, ambiguous)``. 359° and 1° give 0°, not 180°. When the
    two points are exactly opposite, both midpoints are equally valid; the
    function returns the one 90° ahead of ``first`` and flags it, so the caller
    can tell the user rather than pretending the answer is unique.
    """
    difference = signed_separation(second, first)
    ambiguous = abs(abs(difference) - 180.0) < OPPOSITION_TOLERANCE
    if ambiguous:
        return normalize_degrees(first + 90.0), True
    return normalize_degrees(first + difference / 2.0), False


def geographic_midpoint(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> tuple[float, float, bool]:
    """Spherical midpoint of two places.

    Averaging the numbers fails across the date line (179°E and 179°W would
    average to 0°), so both points become unit vectors, the vectors are
    averaged, and the result is converted back. Returns
    ``(latitude, longitude, degenerate)``; ``degenerate`` is True for
    (near-)antipodal inputs, where the midpoint is not defined and the caller
    must decide what to do.
    """
    phi_a, phi_b = math.radians(latitude_a), math.radians(latitude_b)
    lambda_a, lambda_b = math.radians(longitude_a), math.radians(longitude_b)

    x = math.cos(phi_a) * math.cos(lambda_a) + math.cos(phi_b) * math.cos(lambda_b)
    y = math.cos(phi_a) * math.sin(lambda_a) + math.cos(phi_b) * math.sin(lambda_b)
    z = math.sin(phi_a) + math.sin(phi_b)

    magnitude = math.sqrt(x * x + y * y + z * z)
    if magnitude < 1e-9:
        # Antipodal: every point on the great circle is equidistant.
        return 0.0, normalize_degrees((longitude_a + longitude_b) / 2), True

    longitude = math.degrees(math.atan2(y, x))
    hypotenuse = math.sqrt(x * x + y * y)
    latitude = math.degrees(math.atan2(z, hypotenuse))

    degenerate = _is_near_antipodal(latitude_a, longitude_a, latitude_b, longitude_b)
    return round(latitude, 8), round(_wrap_longitude(longitude), 8), degenerate


def _wrap_longitude(value: float) -> float:
    wrapped = (value + 180.0) % 360.0 - 180.0
    return 180.0 if wrapped == -180.0 else wrapped


def _is_near_antipodal(
    latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float
) -> bool:
    phi_a, phi_b = math.radians(latitude_a), math.radians(latitude_b)
    delta = math.radians(longitude_b - longitude_a)
    central = math.acos(
        max(
            -1.0,
            min(
                1.0,
                math.sin(phi_a) * math.sin(phi_b)
                + math.cos(phi_a) * math.cos(phi_b) * math.cos(delta),
            ),
        )
    )
    return abs(math.degrees(central) - 180.0) < ANTIPODAL_TOLERANCE_DEGREES


def utc_midpoint(first: datetime, second: datetime) -> datetime:
    """Midpoint of two instants, in UTC.

    Both are converted to UTC first: averaging local wall-clock times would
    fold two different offsets (and possibly two DST states) into a time that
    never existed.
    """
    a = first.astimezone(UTC)
    b = second.astimezone(UTC)
    return a + (b - a) / 2


class CompositeEngine:
    def __init__(self, engine: SkyfieldEngine | None = None) -> None:
        self._engine = engine or get_engine()

    # ------------------------------------------------------------ composite

    def composite(self, chart_a: Chart, chart_b: Chart) -> CompositeResult:
        warnings: list[str] = []
        ambiguous: list[str] = []
        positions: list[PlanetPosition] = []

        for planet in COMPOSITE_BODIES:
            first = chart_a.position(planet)
            second = chart_b.position(planet)
            if first is None or second is None:
                continue
            midpoint, is_ambiguous = circular_midpoint(
                first.longitude, second.longitude
            )
            if is_ambiguous:
                ambiguous.append(planet.value)
            positions.append(
                PlanetPosition(
                    planet=planet,
                    longitude=midpoint,
                    latitude=(first.latitude + second.latitude) / 2,
                    # A composite point does not move; speed is meaningless
                    # here, so it is zero rather than an invented value.
                    speed_longitude=0.0,
                )
            )

        angles: ChartAngles | None = None
        houses: list[HousePosition] = []
        house_method = COMPOSITE_HOUSE_METHOD

        if chart_a.angles is not None and chart_b.angles is not None:
            midheaven, mc_ambiguous = circular_midpoint(
                chart_a.angles.midheaven, chart_b.angles.midheaven
            )
            ascendant, asc_ambiguous = circular_midpoint(
                chart_a.angles.ascendant, chart_b.angles.ascendant
            )
            if mc_ambiguous:
                ambiguous.append("midheaven")
            if asc_ambiguous:
                ambiguous.append("ascendant")

            angles = ChartAngles(ascendant=ascendant, midheaven=midheaven)

            # Houses from the composite Ascendant, equal-house style. Software
            # differs here (some derive Placidus cusps from the composite MC
            # and the mean latitude); the method is named in the response so a
            # comparison with another tool is a conversation, not a bug report.
            houses, _ = compute_houses(
                system=HouseSystem.EQUAL,
                ramc_degrees=midheaven,
                latitude=0.0,
                angles=angles,
            )
            positions = [
                PlanetPosition(
                    planet=item.planet,
                    longitude=item.longitude,
                    latitude=item.latitude,
                    speed_longitude=item.speed_longitude,
                    house=house_of(item.longitude, houses),
                )
                for item in positions
            ]
        else:
            warnings.append(
                "composite_houses_unavailable: one chart has no angles, so the "
                "composite has planets but no houses."
            )

        if ambiguous:
            warnings.append(
                "ambiguous_midpoints: "
                + ", ".join(sorted(set(ambiguous)))
                + " are exactly opposite in the two charts, so the midpoint is "
                "not unique; the nearer of the two was chosen deterministically."
            )

        subject = ChartSubject(
            kind=ChartKind.COMPOSITE,
            # A composite is not cast for an instant; the reference moment is
            # recorded only so the object is well formed.
            moment_utc=utc_midpoint(chart_a.moment_utc, chart_b.moment_utc),
            latitude=None,
            longitude=None,
            timezone=None,
            house_system=HouseSystem.EQUAL,
            label="composite",
        )

        chart = Chart(
            subject=subject,
            computed_at=datetime.now(UTC),
            engine=ENGINE_VERSION,
            engine_version=ENGINE_VERSION,
            positions=positions,
            houses=houses,
            angles=angles,
            aspects=find_aspects(positions, policy=NATAL_ORBS),
            house_system=HouseSystem.EQUAL,
        )

        return CompositeResult(
            chart=chart,
            method=COMPOSITE_METHOD,
            house_method=house_method,
            aspects=[
                {
                    "first": hit.first.value,
                    "second": hit.second.value,
                    "aspect": hit.aspect.value,
                    "orb": hit.orb,
                    "nature": hit.aspect.nature.value,
                }
                for hit in chart.aspects
            ],
            elements={
                element.value: count
                for element, count in chart.element_distribution.items()
            },
            modalities={
                modality.value: count
                for modality, count in chart.modality_distribution.items()
            },
            dominant_element=chart.dominant_element.value,
            dominant_modality=chart.dominant_modality.value,
            ambiguous_midpoints=sorted(set(ambiguous)),
            warnings=warnings,
            engine_version=ENGINE_VERSION,
        )

    # -------------------------------------------------------------- davison

    def davison(
        self,
        chart_a: Chart,
        chart_b: Chart,
        *,
        house_system: HouseSystem = HouseSystem.PLACIDUS,
    ) -> DavisonResult:
        warnings: list[str] = []

        moment = utc_midpoint(chart_a.moment_utc, chart_b.moment_utc)

        latitude_a = chart_a.subject.latitude
        longitude_a = chart_a.subject.longitude
        latitude_b = chart_b.subject.latitude
        longitude_b = chart_b.subject.longitude

        if None in (latitude_a, longitude_a, latitude_b, longitude_b):
            raise ValueError(
                "A Davison chart needs both birth places; one of them is unknown."
            )

        latitude, longitude, degenerate = geographic_midpoint(
            latitude_a, longitude_a, latitude_b, longitude_b
        )
        if degenerate:
            warnings.append(
                "antipodal_birthplaces: the two places are (near) opposite "
                "points on the globe, so the geographic midpoint is not "
                "unique; the engine used the great-circle fallback and the "
                "houses should be treated with caution."
            )

        subject = ChartSubject(
            kind=ChartKind.DAVISON,
            moment_utc=moment,
            latitude=latitude,
            longitude=longitude,
            # The chart maths needs the UTC instant and the coordinates, not a
            # zone; a display zone can be derived later for presentation.
            timezone=None,
            house_system=house_system,
            label="davison",
        )
        chart = self._engine.chart_for(subject)

        return DavisonResult(
            chart=chart,
            midpoint_utc=moment,
            midpoint_latitude=latitude,
            midpoint_longitude=longitude,
            method=DAVISON_METHOD,
            warnings=warnings,
            engine_version=ENGINE_VERSION,
        )


_engine: CompositeEngine | None = None


def get_composite_engine() -> CompositeEngine:
    global _engine
    if _engine is None:
        _engine = CompositeEngine()
    return _engine
