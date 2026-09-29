"""The astrology engine contract.

Everything astrological in the product is computed behind this interface.
Today it is implemented by :class:`SkyfieldEngine` (JPL ephemerides); a Swiss
Ephemeris implementation can be dropped in later without touching services,
API or the mobile client.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.domain.astrology import BirthData, MoonPhase, NatalChart, PlanetPosition
from app.domain.enums import HouseSystem, Planet


@runtime_checkable
class AstrologyEngine(Protocol):
    """Positional astronomy + chart construction."""

    name: str
    version: str

    def positions(
        self, moment: datetime, *, bodies: tuple[Planet, ...] | None = None
    ) -> list[PlanetPosition]:
        """Ecliptic positions (longitude, latitude, speed) at a UTC instant."""

    def natal_chart(
        self, birth: BirthData, *, house_system: HouseSystem | None = None
    ) -> NatalChart:
        """Full chart: positions, houses, angles and aspects."""

    def moon_phase(self, moment: datetime) -> MoonPhase:
        """Phase, illumination, age and the next phase boundary."""

    def next_phase_moment(
        self, moment: datetime, target_elongation: float
    ) -> datetime | None:
        """The next time the Sun-Moon elongation reaches the given angle."""
