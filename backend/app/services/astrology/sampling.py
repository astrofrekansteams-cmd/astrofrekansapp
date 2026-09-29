"""Vectorised ephemeris sampling and root finding.

Scalar Skyfield calls cost ~2.4 ms each; sampling 8760 instants in one
vectorised call costs ~0.08 ms per point. Every scan in this package therefore
works the same way:

1. sample the body's longitude on a coarse grid in **one** vectorised call,
2. find brackets where the target function changes sign (pure numpy),
3. refine the brackets to the second with a couple of batched evaluations.

Accuracy is checked against the grid step in the tests: the refined exact
times are stable to well under a minute for the Moon and to seconds for slower
bodies.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
from skyfield.framelib import ecliptic_frame

from app.domain.enums import Planet
from app.services.astrology.skyfield_engine import _TARGETS, SkyfieldEngine

# Coarse grid step per body, chosen so no in-orb window can be stepped over.
GRID_STEP: dict[Planet, timedelta] = {
    Planet.MOON: timedelta(hours=2),
    Planet.SUN: timedelta(hours=12),
    Planet.MERCURY: timedelta(hours=8),
    Planet.VENUS: timedelta(hours=12),
    Planet.MARS: timedelta(days=1),
    Planet.JUPITER: timedelta(days=2),
    Planet.SATURN: timedelta(days=2),
    Planet.URANUS: timedelta(days=4),
    Planet.NEPTUNE: timedelta(days=4),
    Planet.PLUTO: timedelta(days=4),
    Planet.NORTH_NODE: timedelta(days=2),
    Planet.SOUTH_NODE: timedelta(days=2),
}

# Mean daily motion, used to size search windows and to sanity-check speeds.
MEAN_DAILY_MOTION: dict[Planet, float] = {
    Planet.MOON: 13.176,
    Planet.SUN: 0.9856,
    Planet.MERCURY: 1.383,
    Planet.VENUS: 1.602,
    Planet.MARS: 0.524,
    Planet.JUPITER: 0.083,
    Planet.SATURN: 0.033,
    Planet.URANUS: 0.0117,
    Planet.NEPTUNE: 0.006,
    Planet.PLUTO: 0.004,
    Planet.NORTH_NODE: 0.053,
    Planet.SOUTH_NODE: 0.053,
}


def wrap180(values: np.ndarray | float) -> np.ndarray | float:
    """Map angles to (-180, 180]."""
    return (np.asarray(values) + 180.0) % 360.0 - 180.0


@dataclass(slots=True)
class LongitudeGrid:
    """Sampled longitudes for one body over one window."""

    planet: Planet
    times: list[datetime]
    seconds: np.ndarray  # seconds since ``times[0]``
    longitudes: np.ndarray  # degrees, 0-360

    def at_index(self, index: int) -> tuple[datetime, float]:
        return self.times[index], float(self.longitudes[index])


class EphemerisSampler:
    """Batch access to the ephemeris, with a per-instance grid cache."""

    def __init__(self, engine: SkyfieldEngine | None = None) -> None:
        from app.services.astrology.skyfield_engine import get_engine

        self._engine = engine or get_engine()
        self._grids: dict[tuple[Planet, str, str, int], LongitudeGrid] = {}
        # Bisection revisits the same instants repeatedly; a scalar call costs
        # ~2.4 ms, a cache hit nothing.
        self._scalar_cache: dict[tuple[Planet, int], float] = {}

    @property
    def engine(self) -> SkyfieldEngine:
        return self._engine

    # ------------------------------------------------------------ sampling

    def longitudes(self, planet: Planet, moments: Sequence[datetime]) -> np.ndarray:
        """Ecliptic longitudes for many instants in one ephemeris call."""
        if not moments:
            return np.empty(0)

        if planet in (Planet.NORTH_NODE, Planet.SOUTH_NODE):
            offset = 180.0 if planet is Planet.SOUTH_NODE else 0.0
            return np.array(
                [
                    (self._engine._mean_node(moment) + offset) % 360.0
                    for moment in moments
                ]
            )

        timescale = self._engine._timescale
        times = timescale.from_datetimes(
            [moment.astimezone(UTC) for moment in moments]
        )
        astrometric = (
            self._engine._earth.at(times)
            .observe(self._engine._ephemeris[_TARGETS[planet]])
            .apparent()
        )
        _, longitude, _ = astrometric.frame_latlon(ecliptic_frame)
        return np.asarray(longitude.degrees) % 360.0

    def grid(
        self,
        planet: Planet,
        start: datetime,
        end: datetime,
        step: timedelta | None = None,
    ) -> LongitudeGrid:
        step = step or GRID_STEP[planet]
        key = (planet, start.isoformat(), end.isoformat(), int(step.total_seconds()))
        cached = self._grids.get(key)
        if cached is not None:
            return cached

        count = max(int((end - start) / step) + 2, 2)
        times = [start + step * index for index in range(count)]
        grid = LongitudeGrid(
            planet=planet,
            times=times,
            seconds=np.array(
                [(moment - start).total_seconds() for moment in times]
            ),
            longitudes=self.longitudes(planet, times),
        )
        self._grids[key] = grid
        return grid

    # --------------------------------------------------------- root finding

    def crossings(
        self,
        planet: Planet,
        target_longitude: float,
        start: datetime,
        end: datetime,
        *,
        step: timedelta | None = None,
    ) -> list[datetime]:
        """Every instant the body's longitude equals ``target_longitude``.

        Retrograde motion produces several crossings of the same degree, which
        is exactly how a transit perfects three times - they are all returned,
        in order.
        """
        grid = self.grid(planet, start, end, step)
        offsets = np.asarray(wrap180(grid.longitudes - target_longitude))

        # A sign flip that is really the 0/360 wrap (|offset| near 180) is not
        # a crossing of the target.
        near = np.abs(offsets) < 90.0
        sign_change = (offsets[:-1] * offsets[1:] < 0) & near[:-1] & near[1:]
        exact_hits = np.isclose(offsets, 0.0, atol=1e-9)

        results: list[datetime] = []
        for index in np.flatnonzero(sign_change):
            moment = self._refine(
                planet,
                target_longitude,
                grid.times[index],
                grid.times[index + 1],
            )
            if moment is not None and start <= moment <= end:
                results.append(moment)
        for index in np.flatnonzero(exact_hits):
            moment = grid.times[index]
            if start <= moment <= end and all(
                abs((moment - found).total_seconds()) > 60 for found in results
            ):
                results.append(moment)

        results.sort()
        return results

    def _refine(
        self,
        planet: Planet,
        target_longitude: float,
        low: datetime,
        high: datetime,
        *,
        tolerance_seconds: float = 20.0,
        max_iterations: int = 24,
    ) -> datetime | None:
        """Bisection on the bracketed crossing, to the second."""

        def offset(moment: datetime) -> float:
            return float(wrap180(self.value_at(planet, moment) - target_longitude))

        low_value = offset(low)
        high_value = offset(high)
        if low_value == 0.0:
            return low
        if high_value == 0.0:
            return high
        if low_value * high_value > 0:
            return None

        for _ in range(max_iterations):
            if (high - low).total_seconds() <= tolerance_seconds:
                break
            middle = low + (high - low) / 2
            middle_value = offset(middle)
            if middle_value == 0.0:
                return middle
            if low_value * middle_value < 0:
                high, high_value = middle, middle_value
            else:
                low, low_value = middle, middle_value

        return low + (high - low) / 2

    def speed(self, planet: Planet, moment: datetime, hours: float = 6.0) -> float:
        """Longitude speed in degrees per day (central difference)."""
        delta = timedelta(hours=hours)
        before, after = self.longitudes(
            planet, [moment - delta, moment + delta]
        )
        return float(wrap180(after - before)) / (2 * hours / 24.0)

    def value_at(self, planet: Planet, moment: datetime) -> float:
        """Single longitude, memoised to the second."""
        key = (planet, int(moment.timestamp()))
        cached = self._scalar_cache.get(key)
        if cached is None:
            cached = float(self.longitudes(planet, [moment])[0])
            self._scalar_cache[key] = cached
        return cached

    # ------------------------------------------------------- batched search

    def bisect_batch(
        self,
        planet: Planet,
        items: list[tuple[datetime, datetime, "Callable[[float], float]"]],
        *,
        tolerance_seconds: float = 45.0,
        iterations: int = 20,
    ) -> list[datetime | None]:
        """Bisect many brackets at once.

        Each item is ``(low, high, f)`` where ``f`` maps a longitude to a value
        whose sign flips across the root. Every iteration evaluates *all* still
        open brackets in a single vectorised ephemeris call, which is what
        makes a full-year scan affordable: ~20 calls instead of one per
        halving per bracket.
        """
        if not items:
            return []

        lows = [item[0] for item in items]
        highs = [item[1] for item in items]
        funcs = [item[2] for item in items]

        low_values = [
            func(float(value))
            for func, value in zip(funcs, self.longitudes(planet, lows), strict=True)
        ]
        high_values = [
            func(float(value))
            for func, value in zip(funcs, self.longitudes(planet, highs), strict=True)
        ]

        bracketed = {
            index
            for index in range(len(items))
            if low_values[index] * high_values[index] <= 0
        }

        for _ in range(iterations):
            pending = [
                index
                for index in bracketed
                if (highs[index] - lows[index]).total_seconds() > tolerance_seconds
            ]
            if not pending:
                break
            middles = [
                lows[index] + (highs[index] - lows[index]) / 2 for index in pending
            ]
            sampled = self.longitudes(planet, middles)
            for index, middle, longitude in zip(
                pending, middles, sampled, strict=True
            ):
                value = funcs[index](float(longitude))
                if low_values[index] * value <= 0:
                    highs[index], high_values[index] = middle, value
                else:
                    lows[index], low_values[index] = middle, value

        return [
            (lows[index] + (highs[index] - lows[index]) / 2)
            if index in bracketed
            else None
            for index in range(len(items))
        ]

    def speeds_at(self, planet: Planet, moments: list[datetime]) -> list[float]:
        """Longitude speeds (deg/day) for many instants, in two calls."""
        if not moments:
            return []
        delta = timedelta(hours=6)
        before = self.longitudes(planet, [moment - delta for moment in moments])
        after = self.longitudes(planet, [moment + delta for moment in moments])
        return [
            float(wrap180(float(a) - float(b))) / 0.5
            for a, b in zip(after, before, strict=True)
        ]
