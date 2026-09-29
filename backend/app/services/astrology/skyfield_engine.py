"""Skyfield-backed astrology engine.

Why Skyfield and not Swiss Ephemeris: ``pyswisseph`` is AGPL-3.0, which would
force source disclosure for a hosted backend (or a commercial licence).
Skyfield is MIT and reads the public-domain JPL DE ephemerides, so the whole
stack stays permissively licensed. Accuracy for natal work is far beyond what
astrology needs (sub-arcsecond planetary positions).

What is computed here:

* geocentric apparent ecliptic longitude/latitude of the ten bodies,
* longitude speed (numerical derivative) -> real retrograde detection,
* mean lunar nodes (Meeus low-precision series; the true node can be added
  later without changing the interface),
* sidereal time -> RAMC -> Ascendant / MC -> house cusps,
* aspects via :mod:`app.services.astrology.aspects`.
"""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from skyfield.api import Loader, load_file
from skyfield.framelib import ecliptic_frame
from skyfield.timelib import Timescale

from app.core.config import settings
from app.core.exceptions import AstrologyError
from app.domain.astrology import (
    BirthData,
    Chart,
    ChartAngles,
    ChartSubject,
    MoonPhase,
    PlanetPosition,
    normalize_degrees,
)
from app.domain.enums import (
    ChartKind,
    HouseSystem,
    MoonPhaseName,
    Planet,
    ZodiacSign,
)
from app.services.astrology.aspects import NATAL_ORBS, OrbPolicy, find_aspects
from app.services.astrology.houses import (
    OBLIQUITY_J2000,
    compute_angles,
    compute_houses,
    house_of,
    obliquity_of_ecliptic,
)

ENGINE_NAME = "skyfield"
ENGINE_VERSION = "1.0.0-de421"

# Barycentre targets are used for the outer planets: DE421 does not carry the
# individual bodies of the giant-planet systems, and the barycentre offset is
# far below astrological resolution.
_TARGETS: dict[Planet, str] = {
    Planet.SUN: "sun",
    Planet.MOON: "moon",
    Planet.MERCURY: "mercury",
    Planet.VENUS: "venus",
    Planet.MARS: "mars barycenter",
    Planet.JUPITER: "jupiter barycenter",
    Planet.SATURN: "saturn barycenter",
    Planet.URANUS: "uranus barycenter",
    Planet.NEPTUNE: "neptune barycenter",
    Planet.PLUTO: "pluto barycenter",
}

DEFAULT_BODIES: tuple[Planet, ...] = tuple(Planet)

_SPEED_STEP = timedelta(hours=6)

_MOON_PHASE_BOUNDS: tuple[tuple[float, MoonPhaseName], ...] = (
    (0.0, MoonPhaseName.NEW_MOON),
    (45.0, MoonPhaseName.WAXING_CRESCENT),
    (90.0, MoonPhaseName.FIRST_QUARTER),
    (135.0, MoonPhaseName.WAXING_GIBBOUS),
    (180.0, MoonPhaseName.FULL_MOON),
    (225.0, MoonPhaseName.WANING_GIBBOUS),
    (270.0, MoonPhaseName.LAST_QUARTER),
    (315.0, MoonPhaseName.WANING_CRESCENT),
)

_QUARTER_ELONGATIONS: tuple[tuple[float, MoonPhaseName], ...] = (
    (0.0, MoonPhaseName.NEW_MOON),
    (90.0, MoonPhaseName.FIRST_QUARTER),
    (180.0, MoonPhaseName.FULL_MOON),
    (270.0, MoonPhaseName.LAST_QUARTER),
)


class SkyfieldEngine:
    """Thread-safe singleton wrapper around the ephemeris kernel."""

    name = ENGINE_NAME
    version = ENGINE_VERSION

    _instance: "SkyfieldEngine | None" = None
    _lock = threading.Lock()

    def __init__(self, ephemeris_path: Path | None = None) -> None:
        path = Path(ephemeris_path or settings.ephemeris_path)
        if not path.exists():
            raise AstrologyError(
                "Ephemeris kernel is missing. Run scripts/download_ephemeris.py.",
                code="ephemeris_missing",
                details={"path": str(path)},
            )
        self._ephemeris = load_file(str(path))
        # ``builtin=True`` keeps the timescale offline (no IERS download at
        # boot); leap seconds are baked into the Skyfield release.
        self._timescale: Timescale = Loader(str(path.parent)).timescale(builtin=True)
        self._earth = self._ephemeris["earth"]

    @classmethod
    def instance(cls) -> "SkyfieldEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------ positions

    def _ecliptic(self, target: str, moment: datetime) -> tuple[float, float]:
        time = self._timescale.from_datetime(_as_utc(moment))
        astrometric = self._earth.at(time).observe(self._ephemeris[target]).apparent()
        latitude, longitude, _ = astrometric.frame_latlon(ecliptic_frame)
        # Cast out of numpy scalars so the domain layer stays plain Python.
        return normalize_degrees(float(longitude.degrees)), float(latitude.degrees)

    def _mean_node(self, moment: datetime) -> float:
        """Mean ascending node of the Moon (Meeus 47.7)."""
        days = (_as_utc(moment) - datetime(2000, 1, 1, 12, tzinfo=UTC)).total_seconds() / 86400.0
        t = days / 36525.0
        node = (
            125.0445479
            - 1934.1362891 * t
            + 0.0020754 * t**2
            + t**3 / 467441.0
            - t**4 / 60616000.0
        )
        return normalize_degrees(node)

    def _longitude_of(self, planet: Planet, moment: datetime) -> tuple[float, float]:
        if planet == Planet.NORTH_NODE:
            return self._mean_node(moment), 0.0
        if planet == Planet.SOUTH_NODE:
            return normalize_degrees(self._mean_node(moment) + 180.0), 0.0
        return self._ecliptic(_TARGETS[planet], moment)

    def positions(
        self, moment: datetime, *, bodies: tuple[Planet, ...] | None = None
    ) -> list[PlanetPosition]:
        moment = _as_utc(moment)
        wanted = bodies or DEFAULT_BODIES
        result: list[PlanetPosition] = []
        for planet in wanted:
            longitude, latitude = self._longitude_of(planet, moment)
            before, _ = self._longitude_of(planet, moment - _SPEED_STEP)
            after, _ = self._longitude_of(planet, moment + _SPEED_STEP)
            # Central difference over 12 hours, unwrapped across 0/360.
            delta = _unwrap(after - before)
            speed = delta / (2 * _SPEED_STEP.total_seconds() / 86400.0)
            result.append(
                PlanetPosition(
                    planet=planet,
                    longitude=float(longitude),
                    latitude=float(latitude),
                    speed_longitude=float(speed),
                )
            )
        return result

    # ----------------------------------------------------------------- charts

    def chart_for(
        self,
        subject: ChartSubject,
        *,
        orb_policy: OrbPolicy | None = None,
    ) -> Chart:
        """The one chart primitive.

        Natal, horary, solar/lunar return, relocation and event charts differ
        only in the subject handed in, so they all come through here.
        """
        moment = _as_utc(subject.moment_utc)
        positions = self.positions(moment)

        angles: ChartAngles | None = None
        houses: list = []
        effective_system = subject.house_system

        if subject.can_compute_houses:
            time = self._timescale.from_datetime(moment)
            obliquity = obliquity_of_ecliptic((time.tt - 2451545.0) / 36525.0)
            # Apparent sidereal time in hours -> degrees, plus the east
            # longitude of the place gives the local RAMC.
            ramc = normalize_degrees(
                float(time.gast) * 15.0 + (subject.longitude or 0.0)
            )
            angles = compute_angles(ramc, subject.latitude or 0.0, obliquity)
            houses, effective_system = compute_houses(
                system=effective_system,
                ramc_degrees=ramc,
                latitude=subject.latitude or 0.0,
                angles=angles,
                obliquity=obliquity,
            )
            positions = [
                PlanetPosition(
                    planet=position.planet,
                    longitude=position.longitude,
                    latitude=position.latitude,
                    speed_longitude=position.speed_longitude,
                    house=house_of(position.longitude, houses),
                )
                for position in positions
            ]

        return Chart(
            subject=subject,
            computed_at=datetime.now(UTC),
            engine=self.name,
            engine_version=self.version,
            positions=positions,
            houses=houses,
            angles=angles,
            aspects=find_aspects(positions, policy=orb_policy or NATAL_ORBS),
            house_system=effective_system,
        )

    def natal_chart(
        self,
        birth: BirthData,
        *,
        house_system: HouseSystem | None = None,
        orb_policy: OrbPolicy | None = None,
    ) -> Chart:
        """A natal chart is ``chart_for`` with the birth moment as subject.

        Houses additionally require a known birth *time*: without it the
        subject is still valid (noon fallback) but the angles would be
        fiction, so they are left out.
        """
        subject = birth.to_subject()
        if house_system is not None:
            subject = replace(subject, house_system=house_system)
        if not birth.can_compute_houses:
            subject = replace(subject, latitude=None, longitude=None)

        chart = self.chart_for(subject, orb_policy=orb_policy)
        return replace(chart, birth_data=birth)

    def horary_chart(
        self,
        *,
        asked_at: datetime,
        latitude: float,
        longitude: float,
        timezone: str | None = None,
        location_name: str | None = None,
        house_system: HouseSystem = HouseSystem.PLACIDUS,
    ) -> Chart:
        """Cast for the moment and place the question was asked - never for a
        birth date. Used by the horary service in phase B5."""
        return self.chart_for(
            ChartSubject(
                kind=ChartKind.HORARY,
                moment_utc=_as_utc(asked_at),
                latitude=latitude,
                longitude=longitude,
                timezone=timezone,
                location_name=location_name,
                house_system=house_system,
            )
        )

    # ------------------------------------------------------------ moon phase

    def elongation(self, moment: datetime) -> float:
        sun, _ = self._ecliptic("sun", moment)
        moon, _ = self._ecliptic("moon", moment)
        return normalize_degrees(moon - sun)

    def moon_phase(self, moment: datetime) -> MoonPhase:
        moment = _as_utc(moment)
        elongation = self.elongation(moment)
        illumination = (1 - _cos_degrees(elongation)) / 2
        phase = _phase_for(elongation)
        moon_longitude, _ = self._ecliptic("moon", moment)

        next_phase_name: MoonPhaseName | None = None
        next_phase_at: datetime | None = None
        for target, name in _QUARTER_ELONGATIONS:
            candidate = self.next_phase_moment(moment, target)
            if candidate is None:
                continue
            if next_phase_at is None or candidate < next_phase_at:
                next_phase_at = candidate
                next_phase_name = name

        return MoonPhase(
            moment=moment,
            phase=phase,
            illumination=round(illumination, 4),
            age_days=round(elongation / 360.0 * 29.530588853, 3),
            elongation=round(elongation, 4),
            sign=ZodiacSign.from_longitude(moon_longitude),
            next_phase=next_phase_name,
            next_phase_at=next_phase_at,
        )

    def next_phase_moment(
        self, moment: datetime, target_elongation: float, *, search_days: int = 32
    ) -> datetime | None:
        """Bisection on the (signed) distance to the target elongation."""
        moment = _as_utc(moment)

        def offset(when: datetime) -> float:
            return _unwrap(self.elongation(when) - target_elongation)

        step = timedelta(hours=6)
        previous = moment
        previous_offset = offset(previous)
        # Skip the boundary we are already sitting on.
        if abs(previous_offset) < 1e-6:
            previous = moment + step
            previous_offset = offset(previous)

        steps = int(search_days * 24 / 6)
        for _ in range(steps):
            current = previous + step
            current_offset = offset(current)
            if previous_offset < 0 <= current_offset:
                return _bisect(previous, current, offset)
            previous, previous_offset = current, current_offset
        return None


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise AstrologyError(
            "Naive datetimes are not accepted by the engine.",
            code="naive_datetime",
        )
    return moment.astimezone(UTC)


def _unwrap(delta: float) -> float:
    value = delta % 360.0
    return value - 360.0 if value > 180.0 else value


def _cos_degrees(degrees: float) -> float:
    import math

    return math.cos(math.radians(degrees))


def _phase_for(elongation: float) -> MoonPhaseName:
    # Each quarter point owns a 22.5 degree window; the rest are the
    # crescent/gibbous phases.
    for centre, name in _MOON_PHASE_BOUNDS:
        if name in (
            MoonPhaseName.NEW_MOON,
            MoonPhaseName.FIRST_QUARTER,
            MoonPhaseName.FULL_MOON,
            MoonPhaseName.LAST_QUARTER,
        ):
            if abs(_unwrap(elongation - centre)) <= 11.25:
                return name
    if elongation < 90:
        return MoonPhaseName.WAXING_CRESCENT
    if elongation < 180:
        return MoonPhaseName.WAXING_GIBBOUS
    if elongation < 270:
        return MoonPhaseName.WANING_GIBBOUS
    return MoonPhaseName.WANING_CRESCENT


def _bisect(low: datetime, high: datetime, func, iterations: int = 40) -> datetime:
    for _ in range(iterations):
        middle = low + (high - low) / 2
        if func(low) * func(middle) <= 0:
            high = middle
        else:
            low = middle
    return low + (high - low) / 2


def get_engine() -> SkyfieldEngine:
    return SkyfieldEngine.instance()
