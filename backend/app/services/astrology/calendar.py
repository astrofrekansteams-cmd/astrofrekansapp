"""Cosmic calendar engine.

Global sky events, independent of any user:

* moon phases (new, first quarter, full, last quarter) at the instant the
  Sun-Moon elongation reaches 0, 90, 180 and 270 degrees,
* retrograde and direct stations, found where the longitude speed changes
  sign - not from a lookup table,
* eclipses, from actual geometry at the syzygy rather than "this full moon is
  near a node, call it an eclipse",
* sign ingresses,
* mundane aspects between the slower planets.

Everything is computed with the same batched sampling the transit engine uses.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
from skyfield.framelib import ecliptic_frame

from app.domain.calendar import CosmicEvent, CosmicEventType, EclipseSubtype
from app.domain.enums import AspectType, Planet, ZodiacSign
from app.services.astrology.sampling import EphemerisSampler, wrap180
from app.services.astrology.skyfield_engine import ENGINE_VERSION, _TARGETS

# Bodies whose stations the calendar reports. Mercury, Venus and Mars matter
# most to users; the outer planets station every year and are included because
# the forecast layer uses them.
STATION_BODIES: tuple[Planet, ...] = (
    Planet.MERCURY,
    Planet.VENUS,
    Planet.MARS,
    Planet.JUPITER,
    Planet.SATURN,
    Planet.URANUS,
    Planet.NEPTUNE,
    Planet.PLUTO,
)

INGRESS_BODIES: tuple[Planet, ...] = (
    Planet.SUN,
    Planet.MERCURY,
    Planet.VENUS,
    Planet.MARS,
    Planet.JUPITER,
    Planet.SATURN,
    Planet.URANUS,
    Planet.NEPTUNE,
    Planet.PLUTO,
)

# Mundane aspects are only meaningful between the slow bodies; Mercury square
# Venus three times a month is noise.
MUNDANE_BODIES: tuple[Planet, ...] = (
    Planet.MARS,
    Planet.JUPITER,
    Planet.SATURN,
    Planet.URANUS,
    Planet.NEPTUNE,
    Planet.PLUTO,
)

MOON_PHASE_ANGLES: tuple[tuple[float, CosmicEventType], ...] = (
    (0.0, CosmicEventType.NEW_MOON),
    (90.0, CosmicEventType.FIRST_QUARTER),
    (180.0, CosmicEventType.FULL_MOON),
    (270.0, CosmicEventType.LAST_QUARTER),
)

# Eclipse limits: past these distances from a node, no eclipse is
# geometrically possible, so the expensive geometry search is skipped. The
# values are the classic outer limits (Meeus ch. 54) with margin.
SOLAR_ECLIPSE_NODE_LIMIT = 18.6
LUNAR_ECLIPSE_NODE_LIMIT = 12.5

# Mean radii in km, for the eclipse geometry.
SUN_RADIUS_KM = 696_000.0
MOON_RADIUS_KM = 1_737.4
EARTH_RADIUS_KM = 6_378.14

AU_KM = 149_597_870.7


def _event_id(kind: str, moment: datetime, *parts: str) -> str:
    raw = "|".join(
        [kind, moment.astimezone(UTC).strftime("%Y%m%d%H%M"), *parts]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


@dataclass(slots=True, frozen=True)
class EclipseGeometry:
    """What the sky actually looked like at a syzygy."""

    separation: float
    moon_latitude: float
    sun_semi_diameter: float
    moon_semi_diameter: float
    moon_parallax: float
    umbra_radius: float | None = None
    penumbra_radius: float | None = None


class CosmicCalendarEngine:
    def __init__(self, sampler: EphemerisSampler | None = None) -> None:
        self._sampler = sampler or EphemerisSampler()
        # ``events`` and ``retrograde_periods`` both want stations; computing
        # them twice for the same window is pure waste.
        self._station_cache: dict[tuple[str, str, tuple], list[CosmicEvent]] = {}

    @property
    def sampler(self) -> EphemerisSampler:
        return self._sampler

    # ---------------------------------------------------------------- entry

    def events(
        self,
        start: datetime,
        end: datetime,
        *,
        include_moon_phases: bool = True,
        include_quarters: bool = True,
        include_stations: bool = True,
        include_eclipses: bool = True,
        include_ingresses: bool = True,
        include_aspects: bool = True,
    ) -> list[CosmicEvent]:
        start = start.astimezone(UTC)
        end = end.astimezone(UTC)

        events: list[CosmicEvent] = []
        syzygies: list[tuple[datetime, CosmicEventType]] = []

        if include_moon_phases or include_eclipses:
            syzygies = self.moon_phase_moments(
                start, end, quarters=include_quarters
            )
        if include_moon_phases:
            events.extend(self._moon_phase_events(syzygies))
        if include_eclipses:
            events.extend(self._eclipse_events(syzygies))
        if include_stations:
            events.extend(self.stations(start, end))
        if include_ingresses:
            events.extend(self.ingresses(start, end))
        if include_aspects:
            events.extend(self.mundane_aspects(start, end))

        events.sort(key=lambda event: event.exact_at)
        return events

    # ---------------------------------------------------------- moon phases

    def moon_phase_moments(
        self, start: datetime, end: datetime, *, quarters: bool = True
    ) -> list[tuple[datetime, CosmicEventType]]:
        """Exact phase instants, from the true Sun-Moon elongation."""
        step = timedelta(hours=6)
        pad = timedelta(days=2)
        times = _time_range(start - pad, end + pad, step)

        sun = self._sampler.longitudes(Planet.SUN, times)
        moon = self._sampler.longitudes(Planet.MOON, times)
        elongation = (moon - sun) % 360.0

        brackets: list[tuple[datetime, datetime, float]] = []
        kinds: list[CosmicEventType] = []

        for angle, kind in MOON_PHASE_ANGLES:
            if not quarters and kind in (
                CosmicEventType.FIRST_QUARTER,
                CosmicEventType.LAST_QUARTER,
            ):
                continue
            offsets = np.asarray(wrap180(elongation - angle))
            near = np.abs(offsets) < 90.0
            flips = (offsets[:-1] * offsets[1:] < 0) & near[:-1] & near[1:]
            for index in np.flatnonzero(flips):
                position = int(index)
                brackets.append((times[position], times[position + 1], angle))
                kinds.append(kind)

        # All phase instants are bisected together: one Sun call and one Moon
        # call per round, instead of two per bracket per round.
        moments = self._refine_elongations(brackets)
        found = [
            (moment, kind)
            for moment, kind in zip(moments, kinds, strict=True)
            if moment is not None and start <= moment <= end
        ]
        found.sort(key=lambda item: item[0])
        return found

    def _refine_elongations(
        self,
        brackets: list[tuple[datetime, datetime, float]],
        *,
        tolerance_seconds: float = 30.0,
        iterations: int = 18,
    ) -> list[datetime | None]:
        """Bisect many Sun-Moon elongation crossings at once."""
        if not brackets:
            return []

        lows = [item[0] for item in brackets]
        highs = [item[1] for item in brackets]
        angles = [item[2] for item in brackets]

        def offsets(moments: list[datetime]) -> list[float]:
            sun = self._sampler.longitudes(Planet.SUN, moments)
            moon = self._sampler.longitudes(Planet.MOON, moments)
            return [
                float(wrap180(float(m) - float(s) - angle))
                for m, s, angle in zip(moon, sun, angles, strict=True)
            ]

        low_values = offsets(lows)
        high_values = offsets(highs)
        bracketed = {
            index
            for index in range(len(brackets))
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
            sun = self._sampler.longitudes(Planet.SUN, middles)
            moon = self._sampler.longitudes(Planet.MOON, middles)
            for offset, index in enumerate(pending):
                value = float(
                    wrap180(
                        float(moon[offset]) - float(sun[offset]) - angles[index]
                    )
                )
                if low_values[index] * value <= 0:
                    highs[index], high_values[index] = middles[offset], value
                else:
                    lows[index], low_values[index] = middles[offset], value

        return [
            (lows[index] + (highs[index] - lows[index]) / 2)
            if index in bracketed
            else None
            for index in range(len(brackets))
        ]

    def _refine_elongation(
        self,
        low: datetime,
        high: datetime,
        angle: float,
        *,
        tolerance_seconds: float = 15.0,
        iterations: int = 24,
    ) -> datetime | None:
        def offset(moment: datetime) -> float:
            sun, moon = self._sampler.longitudes(
                Planet.SUN, [moment]
            ), self._sampler.longitudes(Planet.MOON, [moment])
            return float(wrap180(float(moon[0]) - float(sun[0]) - angle))

        low_value = offset(low)
        high_value = offset(high)
        if low_value * high_value > 0:
            return None

        for _ in range(iterations):
            if (high - low).total_seconds() <= tolerance_seconds:
                break
            middle = low + (high - low) / 2
            middle_value = offset(middle)
            if low_value * middle_value <= 0:
                high, high_value = middle, middle_value
            else:
                low, low_value = middle, middle_value
        return low + (high - low) / 2

    def _moon_phase_events(
        self, syzygies: list[tuple[datetime, CosmicEventType]]
    ) -> list[CosmicEvent]:
        events: list[CosmicEvent] = []
        for moment, kind in syzygies:
            longitude = float(self._sampler.longitudes(Planet.MOON, [moment])[0])
            events.append(
                CosmicEvent(
                    id=_event_id(kind.value, moment),
                    type=kind,
                    exact_at=moment,
                    planet=Planet.MOON,
                    sign=ZodiacSign.from_longitude(longitude),
                    longitude=round(longitude, 4),
                    degree=int(longitude % 30),
                    engine_version=ENGINE_VERSION,
                )
            )
        return events

    # ------------------------------------------------------------- eclipses

    def _eclipse_events(
        self, syzygies: list[tuple[datetime, CosmicEventType]]
    ) -> list[CosmicEvent]:
        events: list[CosmicEvent] = []
        for moment, kind in syzygies:
            if kind not in (CosmicEventType.NEW_MOON, CosmicEventType.FULL_MOON):
                continue

            # Cheap gate first: a syzygy far from the lunar nodes cannot be an
            # eclipse, and skipping it avoids the expensive geometry search on
            # the ~80% of new and full moons that are ordinary.
            node_distance = self._node_distance(moment)
            limit = (
                SOLAR_ECLIPSE_NODE_LIMIT
                if kind is CosmicEventType.NEW_MOON
                else LUNAR_ECLIPSE_NODE_LIMIT
            )
            if node_distance > limit:
                continue

            event = (
                self.solar_eclipse_at(moment)
                if kind is CosmicEventType.NEW_MOON
                else self.lunar_eclipse_at(moment)
            )
            if event is not None:
                events.append(event)
        return events

    def _geometry(self, moment: datetime) -> EclipseGeometry:
        """Apparent sizes and the Sun-Moon geometry at one instant."""
        engine = self._sampler.engine
        time = engine._timescale.from_datetime(moment.astimezone(UTC))
        earth = engine._earth

        sun_position = earth.at(time).observe(engine._ephemeris[_TARGETS[Planet.SUN]]).apparent()
        moon_position = earth.at(time).observe(engine._ephemeris[_TARGETS[Planet.MOON]]).apparent()

        sun_lat, sun_lon, sun_distance = sun_position.frame_latlon(ecliptic_frame)
        moon_lat, moon_lon, moon_distance = moon_position.frame_latlon(ecliptic_frame)

        sun_km = float(sun_distance.km)
        moon_km = float(moon_distance.km)

        sun_semi = np.degrees(np.arcsin(SUN_RADIUS_KM / sun_km))
        moon_semi = np.degrees(np.arcsin(MOON_RADIUS_KM / moon_km))
        moon_parallax = np.degrees(np.arcsin(EARTH_RADIUS_KM / moon_km))
        sun_parallax = np.degrees(np.arcsin(EARTH_RADIUS_KM / sun_km))

        separation = float(sun_position.separation_from(moon_position).degrees)

        # Meeus 54: shadow radii at the Moon's distance, in degrees.
        penumbra = 1.02 * (moon_parallax + sun_parallax + sun_semi)
        umbra = 1.02 * (moon_parallax + sun_parallax - sun_semi)

        return EclipseGeometry(
            separation=separation,
            moon_latitude=float(moon_lat.degrees),
            sun_semi_diameter=float(sun_semi),
            moon_semi_diameter=float(moon_semi),
            moon_parallax=float(moon_parallax),
            umbra_radius=float(umbra),
            penumbra_radius=float(penumbra),
        )

    def solar_eclipse_at(self, new_moon: datetime) -> CosmicEvent | None:
        """A solar eclipse happens somewhere on Earth when the Moon's shadow
        cone reaches it: the geocentric Sun-Moon separation at conjunction is
        then smaller than the sum of the two semi-diameters plus the Moon's
        horizontal parallax.

        The *subtype* (total, annular, partial) depends on where the shadow
        axis lands, which needs Besselian elements this engine does not
        compute - so it is left null rather than guessed.
        """
        moment = self._minimum_separation(new_moon)
        geometry = self._geometry(moment)
        limit = (
            geometry.sun_semi_diameter
            + geometry.moon_semi_diameter
            + geometry.moon_parallax
        )
        if geometry.separation > limit:
            return None

        node_distance = self._node_distance(moment)
        return CosmicEvent(
            id=_event_id("solar_eclipse", moment),
            type=CosmicEventType.SOLAR_ECLIPSE,
            exact_at=moment,
            planet=Planet.SUN,
            sign=ZodiacSign.from_longitude(
                float(self._sampler.longitudes(Planet.SUN, [moment])[0])
            ),
            eclipse_subtype=None,
            node_distance=round(node_distance, 4),
            engine_version=ENGINE_VERSION,
            metadata={
                "geocentric_separation_deg": round(geometry.separation, 5),
                "limit_deg": round(limit, 5),
                "moon_latitude_deg": round(geometry.moon_latitude, 5),
                "subtype_note": (
                    "Requires Besselian elements; not computed by this engine."
                ),
            },
        )

    def lunar_eclipse_at(self, full_moon: datetime) -> CosmicEvent | None:
        """Lunar eclipses are geocentric, so the geometry settles the subtype.

        The Moon's distance from the shadow axis is compared with the umbral
        and penumbral radii (Meeus, ch. 54).
        """
        moment = self._minimum_separation(full_moon, opposition=True)
        geometry = self._geometry(moment)

        # Distance from the antisolar point.
        axis_distance = abs(180.0 - geometry.separation)
        penumbra = geometry.penumbra_radius or 0.0
        umbra = geometry.umbra_radius or 0.0

        if axis_distance > penumbra + geometry.moon_semi_diameter:
            return None

        if axis_distance < umbra - geometry.moon_semi_diameter:
            subtype = EclipseSubtype.TOTAL
        elif axis_distance < umbra + geometry.moon_semi_diameter:
            subtype = EclipseSubtype.PARTIAL
        else:
            subtype = EclipseSubtype.PENUMBRAL

        magnitude = (
            (umbra + geometry.moon_semi_diameter - axis_distance)
            / (2 * geometry.moon_semi_diameter)
            if geometry.moon_semi_diameter
            else None
        )

        return CosmicEvent(
            id=_event_id("lunar_eclipse", moment),
            type=CosmicEventType.LUNAR_ECLIPSE,
            exact_at=moment,
            planet=Planet.MOON,
            sign=ZodiacSign.from_longitude(
                float(self._sampler.longitudes(Planet.MOON, [moment])[0])
            ),
            eclipse_subtype=subtype,
            eclipse_magnitude=(
                round(float(magnitude), 4) if magnitude is not None else None
            ),
            node_distance=round(self._node_distance(moment), 4),
            engine_version=ENGINE_VERSION,
            metadata={
                "axis_distance_deg": round(axis_distance, 5),
                "umbra_radius_deg": round(umbra, 5),
                "penumbra_radius_deg": round(penumbra, 5),
            },
        )

    def _minimum_separation(
        self, around: datetime, *, opposition: bool = False, span_hours: int = 8
    ) -> datetime:
        """Refine a syzygy to the instant of least separation.

        Phase exactness is measured in ecliptic longitude; eclipse geometry
        cares about the true angular separation, which is least a little
        earlier or later because of the Moon's latitude. Two passes - coarse
        then fine - instead of one dense sweep, because each sample costs two
        full apparent-position computations.
        """

        def scan(centre: datetime, span_minutes: int, step_minutes: int) -> datetime:
            best_moment = centre
            best_value: float | None = None
            for minutes in range(-span_minutes, span_minutes + 1, step_minutes):
                moment = centre + timedelta(minutes=minutes)
                geometry = self._geometry(moment)
                value = (
                    abs(180.0 - geometry.separation)
                    if opposition
                    else geometry.separation
                )
                if best_value is None or value < best_value:
                    best_value, best_moment = value, moment
            return best_moment

        coarse = scan(around, span_hours * 60, 40)
        return scan(coarse, 40, 5)

    def _node_distance(self, moment: datetime) -> float:
        node = self._sampler.engine._mean_node(moment)
        sun = float(self._sampler.longitudes(Planet.SUN, [moment])[0])
        return float(
            min(
                abs(wrap180(sun - node)),
                abs(wrap180(sun - (node + 180.0))),
            )
        )

    # ------------------------------------------------------------- stations

    def stations(
        self, start: datetime, end: datetime, bodies: tuple[Planet, ...] = STATION_BODIES
    ) -> list[CosmicEvent]:
        """Retrograde and direct stations, where longitude speed crosses zero."""
        cache_key = (start.isoformat(), end.isoformat(), tuple(bodies))
        cached = self._station_cache.get(cache_key)
        if cached is not None:
            return cached

        events: list[CosmicEvent] = []
        step = timedelta(days=1)
        times = _time_range(start - timedelta(days=2), end + timedelta(days=2), step)

        for body in bodies:
            longitudes = self._sampler.longitudes(body, times)
            speeds = np.asarray(wrap180(np.diff(longitudes)))
            flips = speeds[:-1] * speeds[1:] < 0
            brackets = [
                (times[int(index)], times[int(index) + 2])
                for index in np.flatnonzero(flips)
            ]
            moments = [
                moment
                for moment in self._refine_stations(body, brackets)
                if moment is not None and start <= moment <= end
            ]
            if not moments:
                continue

            after = self._sampler.speeds_at(
                body, [moment + timedelta(days=1) for moment in moments]
            )
            longitudes_at = self._sampler.longitudes(body, moments)
            for moment, speed, longitude in zip(
                moments, after, longitudes_at, strict=True
            ):
                kind = (
                    CosmicEventType.STATION_RETROGRADE
                    if speed < 0
                    else CosmicEventType.STATION_DIRECT
                )
                longitude = float(longitude)
                events.append(
                    CosmicEvent(
                        id=_event_id(kind.value, moment, body.value),
                        type=kind,
                        exact_at=moment,
                        planet=body,
                        sign=ZodiacSign.from_longitude(longitude),
                        longitude=round(longitude, 4),
                        degree=int(longitude % 30),
                        engine_version=ENGINE_VERSION,
                    )
                )

        self._station_cache[cache_key] = events
        return events

    def _refine_stations(
        self,
        body: Planet,
        brackets: list[tuple[datetime, datetime]],
        *,
        tolerance_seconds: float = 1800.0,
        iterations: int = 12,
    ) -> list[datetime | None]:
        """Bisect several stations of one body together.

        Half an hour of tolerance is far below anything a reader notices - a
        station is a day-scale event - and each extra halving is another
        ephemeris round trip.
        """
        if not brackets:
            return []

        lows = [item[0] for item in brackets]
        highs = [item[1] for item in brackets]
        low_values = self._sampler.speeds_at(body, lows)
        high_values = self._sampler.speeds_at(body, highs)
        bracketed = {
            index
            for index in range(len(brackets))
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
            speeds = self._sampler.speeds_at(body, middles)
            for offset, index in enumerate(pending):
                value = speeds[offset]
                if low_values[index] * value <= 0:
                    highs[index], high_values[index] = middles[offset], value
                else:
                    lows[index], low_values[index] = middles[offset], value

        return [
            (lows[index] + (highs[index] - lows[index]) / 2)
            if index in bracketed
            else None
            for index in range(len(brackets))
        ]

    def _refine_station(
        self,
        body: Planet,
        low: datetime,
        high: datetime,
        *,
        tolerance_seconds: float = 600.0,
        iterations: int = 18,
    ) -> datetime | None:
        low_speed, high_speed = self._sampler.speeds_at(body, [low, high])
        if low_speed * high_speed > 0:
            return None
        for _ in range(iterations):
            if (high - low).total_seconds() <= tolerance_seconds:
                break
            middle = low + (high - low) / 2
            middle_speed = self._sampler.speeds_at(body, [middle])[0]
            if low_speed * middle_speed <= 0:
                high, high_speed = middle, middle_speed
            else:
                low, low_speed = middle, middle_speed
        return low + (high - low) / 2

    def retrograde_periods(
        self, start: datetime, end: datetime, bodies: tuple[Planet, ...] = STATION_BODIES
    ) -> list[CosmicEvent]:
        """Station pairs turned into retrograde windows.

        The search runs wider than the requested range so a retrograde that
        began earlier is still reported with its real start.
        """
        padded_start = start - timedelta(days=200)
        padded_end = end + timedelta(days=200)
        stations = self.stations(padded_start, padded_end, bodies)

        periods: list[CosmicEvent] = []
        for body in bodies:
            body_stations = [
                event for event in stations if event.planet is body
            ]
            body_stations.sort(key=lambda event: event.exact_at)
            for index, event in enumerate(body_stations):
                if event.type is not CosmicEventType.STATION_RETROGRADE:
                    continue
                direct = next(
                    (
                        later
                        for later in body_stations[index + 1 :]
                        if later.type is CosmicEventType.STATION_DIRECT
                    ),
                    None,
                )
                if direct is None:
                    continue
                if direct.exact_at < start or event.exact_at > end:
                    continue
                periods.append(
                    CosmicEvent(
                        id=_event_id("retrograde", event.exact_at, body.value),
                        type=CosmicEventType.STATION_RETROGRADE,
                        exact_at=event.exact_at,
                        start_at=event.exact_at,
                        end_at=direct.exact_at,
                        planet=body,
                        sign=event.sign,
                        longitude=event.longitude,
                        engine_version=ENGINE_VERSION,
                        metadata={
                            "station_direct_at": direct.exact_at.isoformat(),
                            "direct_sign": direct.sign.value if direct.sign else None,
                            "days": round(
                                (direct.exact_at - event.exact_at).total_seconds()
                                / 86400,
                                2,
                            ),
                        },
                    )
                )
        periods.sort(key=lambda event: event.exact_at)
        return periods

    # ------------------------------------------------------------ ingresses

    def ingresses(
        self,
        start: datetime,
        end: datetime,
        bodies: tuple[Planet, ...] = INGRESS_BODIES,
    ) -> list[CosmicEvent]:
        """Sign changes: a body crossing a multiple of 30 degrees."""
        events: list[CosmicEvent] = []
        for body in bodies:
            grid = self._sampler.grid(body, start, end)
            brackets: list[tuple[datetime, datetime, object]] = []
            for boundary in range(0, 360, 30):
                offsets = np.asarray(wrap180(grid.longitudes - boundary))
                near = np.abs(offsets) < 90.0
                flips = (offsets[:-1] * offsets[1:] < 0) & near[:-1] & near[1:]
                for index in np.flatnonzero(flips):
                    position = int(index)
                    brackets.append(
                        (
                            grid.times[position],
                            grid.times[position + 1],
                            _crossing(float(boundary)),
                        )
                    )

            moments = [
                moment
                for moment in self._sampler.bisect_batch(
                    body, brackets, tolerance_seconds=60.0, iterations=20
                )
                if moment is not None and start <= moment <= end
            ]
            if not moments:
                continue
            speeds = self._sampler.speeds_at(body, moments)
            longitudes = self._sampler.longitudes(body, moments)
            for moment, speed, longitude in zip(
                moments, speeds, longitudes, strict=True
            ):
                sign = ZodiacSign.from_longitude(
                    float(longitude) + (0.01 if speed >= 0 else -0.01)
                )
                events.append(
                    CosmicEvent(
                        id=_event_id("ingress", moment, body.value, sign.value),
                        type=CosmicEventType.INGRESS,
                        exact_at=moment,
                        planet=body,
                        sign=sign,
                        longitude=round(float(longitude), 4),
                        degree=0,
                        engine_version=ENGINE_VERSION,
                        metadata={"retrograde": speed < 0},
                    )
                )
        return events

    # ------------------------------------------------------- mundane aspects

    def mundane_aspects(
        self,
        start: datetime,
        end: datetime,
        bodies: tuple[Planet, ...] = MUNDANE_BODIES,
    ) -> list[CosmicEvent]:
        """Exact aspects between the slower planets (Mars outwards)."""
        step = timedelta(days=1)
        times = _time_range(start, end, step)
        if len(times) < 2:
            return []

        longitudes = {body: self._sampler.longitudes(body, times) for body in bodies}
        events: list[CosmicEvent] = []

        for first_index, first in enumerate(bodies):
            for second in bodies[first_index + 1 :]:
                separations = np.abs(wrap180(longitudes[first] - longitudes[second]))

                brackets: list[tuple[datetime, datetime, float]] = []
                aspects: list[AspectType] = []
                for aspect in AspectType:
                    offsets = separations - aspect.angle
                    flips = offsets[:-1] * offsets[1:] < 0
                    for index in np.flatnonzero(flips):
                        position = int(index)
                        brackets.append(
                            (times[position], times[position + 1], aspect.angle)
                        )
                        aspects.append(aspect)

                # Every aspect of this pair is bisected together: two calls per
                # round for the whole pair rather than two per bracket.
                moments = self._refine_pairs(first, second, brackets)
                found = [
                    (moment, aspect)
                    for moment, aspect in zip(moments, aspects, strict=True)
                    if moment is not None and start <= moment <= end
                ]
                if not found:
                    continue

                positions = self._sampler.longitudes(
                    first, [moment for moment, _ in found]
                )
                for (moment, aspect), longitude in zip(
                    found, positions, strict=True
                ):
                    longitude = float(longitude)
                    events.append(
                        CosmicEvent(
                            id=_event_id(
                                "mundane",
                                moment,
                                first.value,
                                second.value,
                                aspect.value,
                            ),
                            type=CosmicEventType.for_aspect(aspect),
                            exact_at=moment,
                            planet=first,
                            secondary_planet=second,
                            aspect=aspect,
                            sign=ZodiacSign.from_longitude(longitude),
                            longitude=round(longitude, 4),
                            engine_version=ENGINE_VERSION,
                        )
                    )
        return events

    def _refine_pairs(
        self,
        first: Planet,
        second: Planet,
        brackets: list[tuple[datetime, datetime, float]],
        *,
        tolerance_seconds: float = 900.0,
        iterations: int = 14,
    ) -> list[datetime | None]:
        """Bisect several aspects between the same two bodies at once."""
        if not brackets:
            return []

        lows = [item[0] for item in brackets]
        highs = [item[1] for item in brackets]
        angles = [item[2] for item in brackets]

        def offsets(moments: list[datetime]) -> list[float]:
            first_longitudes = self._sampler.longitudes(first, moments)
            second_longitudes = self._sampler.longitudes(second, moments)
            return [
                abs(float(wrap180(float(a) - float(b)))) - angle
                for a, b, angle in zip(
                    first_longitudes, second_longitudes, angles, strict=True
                )
            ]

        low_values = offsets(lows)
        high_values = offsets(highs)
        bracketed = {
            index
            for index in range(len(brackets))
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
            first_longitudes = self._sampler.longitudes(first, middles)
            second_longitudes = self._sampler.longitudes(second, middles)
            for offset, index in enumerate(pending):
                value = (
                    abs(
                        float(
                            wrap180(
                                float(first_longitudes[offset])
                                - float(second_longitudes[offset])
                            )
                        )
                    )
                    - angles[index]
                )
                if low_values[index] * value <= 0:
                    highs[index], high_values[index] = middles[offset], value
                else:
                    lows[index], low_values[index] = middles[offset], value

        return [
            (lows[index] + (highs[index] - lows[index]) / 2)
            if index in bracketed
            else None
            for index in range(len(brackets))
        ]

    def _refine_pair(
        self,
        first: Planet,
        second: Planet,
        aspect: AspectType,
        low: datetime,
        high: datetime,
        *,
        tolerance_seconds: float = 600.0,
        iterations: int = 18,
    ) -> datetime | None:
        def offset(moment: datetime) -> float:
            first_longitude = float(self._sampler.longitudes(first, [moment])[0])
            second_longitude = float(self._sampler.longitudes(second, [moment])[0])
            gap = abs(float(wrap180(first_longitude - second_longitude)))
            return gap - aspect.angle

        low_value = offset(low)
        high_value = offset(high)
        if low_value * high_value > 0:
            return None
        for _ in range(iterations):
            if (high - low).total_seconds() <= tolerance_seconds:
                break
            middle = low + (high - low) / 2
            middle_value = offset(middle)
            if low_value * middle_value <= 0:
                high, high_value = middle, middle_value
            else:
                low, low_value = middle, middle_value
        return low + (high - low) / 2


def _crossing(target: float):
    def function(longitude: float) -> float:
        return float(wrap180(longitude - target))

    return function


def _time_range(start: datetime, end: datetime, step: timedelta) -> list[datetime]:
    count = max(int((end - start) / step) + 2, 2)
    return [start + step * index for index in range(count)]


_calendar: CosmicCalendarEngine | None = None


def get_calendar_engine() -> CosmicCalendarEngine:
    global _calendar
    if _calendar is None:
        _calendar = CosmicCalendarEngine()
    return _calendar
