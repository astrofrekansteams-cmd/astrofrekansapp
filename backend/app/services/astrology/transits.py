"""Transit engine.

For a natal chart and a date range it finds:

* aspects from transiting bodies to natal planets and to the Ascendant and
  Midheaven, with the **window** they stay in orb and every **pass** where they
  perfect (a retrograding body perfects the same aspect up to three times),
* house ingresses, including retrograde re-entries.

Method, and why it is shaped this way: a scalar ephemeris call costs ~2.4 ms,
so nothing is evaluated one instant at a time. Each body is sampled once on a
coarse grid in a single vectorised call, in-orb stretches and crossings are
located in numpy, and then *all* brackets are refined together - every
bisection round is one more vectorised call, not one per bracket.

Strength is a documented deterministic formula (``docs/transit_engine.md``).
No randomness, and no LLM anywhere near a number.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import numpy as np

from app.domain.astrology import Chart, separation
from app.domain.enums import AspectType, ChartAngle, Planet
from app.domain.transit import (
    HouseIngress,
    PassDirection,
    TransitEvent,
    TransitPass,
    TransitStatus,
    TransitTargetType,
)
from app.services.astrology import weights as W
from app.services.astrology.houses import house_of
from app.services.astrology.sampling import (
    MEAN_DAILY_MOTION,
    EphemerisSampler,
    LongitudeGrid,
    wrap180,
)
from app.services.astrology.skyfield_engine import ENGINE_VERSION

DEFAULT_TRANSITING: tuple[Planet, ...] = (
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
)

SLOW_BODIES: tuple[Planet, ...] = (
    Planet.JUPITER,
    Planet.SATURN,
    Planet.URANUS,
    Planet.NEPTUNE,
    Planet.PLUTO,
)

NATAL_TARGETS: tuple[Planet, ...] = (
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
)

ANGLE_TARGETS: tuple[ChartAngle, ...] = (ChartAngle.ASC, ChartAngle.MC)

# How far outside the requested range a window edge is chased. Pluto can hold
# an orb for years; past this horizon the window is reported as clipped rather
# than searched to the end of the decade.
MAX_WINDOW_DAYS: dict[Planet, int] = {
    Planet.MOON: 3,
    Planet.SUN: 20,
    Planet.MERCURY: 25,
    Planet.VENUS: 25,
    Planet.MARS: 90,
    Planet.JUPITER: 180,
    Planet.SATURN: 270,
    Planet.URANUS: 400,
    Planet.NEPTUNE: 400,
    Planet.PLUTO: 400,
    Planet.NORTH_NODE: 120,
    Planet.SOUTH_NODE: 120,
}


def transit_orb_limit(body: Planet, aspect: AspectType) -> float:
    return W.TRANSIT_ORBS[aspect] * W.BODY_ORB_FACTOR[body]


@dataclass(slots=True, frozen=True)
class TransitSet:
    """Everything found for one chart and one window."""

    start: datetime
    end: datetime
    reference: datetime
    events: list[TransitEvent]
    ingresses: list[HouseIngress]
    engine_version: str = ENGINE_VERSION
    scoring_version: str = W.SCORING_VERSION

    def active(self) -> list[TransitEvent]:
        return [
            event
            for event in self.events
            if event.start_at
            and event.end_at
            and event.start_at <= self.reference <= event.end_at
        ]

    def approaching(self) -> list[TransitEvent]:
        return [
            event
            for event in self.events
            if event.start_at and event.start_at > self.reference
        ]

    def exact_within(self, start: datetime, end: datetime) -> list[TransitEvent]:
        return [
            event
            for event in self.events
            if any(start <= item.exact_at <= end for item in event.passes)
        ]

    def by_id(self, transit_id: str) -> TransitEvent | None:
        for event in self.events:
            if event.id == transit_id:
                return event
        return None


@dataclass(slots=True)
class _Candidate:
    """An in-orb stretch found on the grid, before refinement."""

    body: Planet
    aspect: AspectType
    target_label: str
    target_longitude: float
    target_meta: dict
    orb_limit: float
    first_index: int
    last_index: int
    window_start: datetime | None = None
    window_end: datetime | None = None
    clipped_start: bool = False
    clipped_end: bool = False
    passes: list[TransitPass] | None = None


def _event_id(
    chart_fingerprint: str,
    body: Planet,
    target_label: str,
    aspect: AspectType | None,
    anchor: datetime,
) -> str:
    """Stable id, so `/transits/{id}` finds the same event on a later call."""
    raw = "|".join(
        [
            chart_fingerprint,
            body.value,
            target_label,
            aspect.value if aspect else "ingress",
            anchor.astimezone(UTC).strftime("%Y%m%d%H%M"),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


class TransitEngine:
    def __init__(self, sampler: EphemerisSampler | None = None) -> None:
        self._sampler = sampler or EphemerisSampler()

    @property
    def sampler(self) -> EphemerisSampler:
        return self._sampler

    # ------------------------------------------------------------- scanning

    def scan(
        self,
        chart: Chart,
        *,
        start: datetime,
        end: datetime,
        reference: datetime | None = None,
        bodies: tuple[Planet, ...] = DEFAULT_TRANSITING,
        include_moon: bool = True,
        include_ingresses: bool = True,
        chart_fingerprint: str = "",
    ) -> TransitSet:
        start = start.astimezone(UTC)
        end = end.astimezone(UTC)
        reference = (reference or start).astimezone(UTC)

        targets = self._natal_targets(chart)
        events: list[TransitEvent] = []
        ingresses: list[HouseIngress] = []

        for body in bodies:
            if body is Planet.MOON and not include_moon:
                continue

            pad = self._pad_for(body)
            grid = self._sampler.grid(body, start - pad, end + pad)

            candidates = self._find_candidates(body, grid, targets)
            self._refine_windows(body, grid, candidates)
            candidates = [
                candidate
                for candidate in candidates
                if candidate.window_start is not None
                and candidate.window_end is not None
                and candidate.window_end >= start
                and candidate.window_start <= end
            ]
            self._refine_passes(body, grid, candidates)

            events.extend(
                self._build_events(
                    chart=chart,
                    body=body,
                    candidates=candidates,
                    reference=reference,
                    window=(start, end),
                    chart_fingerprint=chart_fingerprint,
                )
            )

            if include_ingresses and chart.houses:
                ingresses.extend(
                    self._scan_ingresses(
                        chart=chart,
                        body=body,
                        grid=grid,
                        start=start,
                        end=end,
                        chart_fingerprint=chart_fingerprint,
                    )
                )

        events.sort(key=lambda event: (-event.strength, event.exact_at or end))
        ingresses.sort(key=lambda ingress: ingress.entered_at)
        return TransitSet(
            start=start,
            end=end,
            reference=reference,
            events=events,
            ingresses=ingresses,
        )

    def _pad_for(self, body: Planet) -> timedelta:
        """How far outside the range a window of this body can reach."""
        widest = max(transit_orb_limit(body, aspect) for aspect in AspectType)
        days = widest / max(MEAN_DAILY_MOTION[body], 1e-4)
        return timedelta(days=min(MAX_WINDOW_DAYS[body], max(2.0, days + 2.0)))

    def _natal_targets(self, chart: Chart) -> list[tuple[str, float, dict]]:
        targets: list[tuple[str, float, dict]] = []
        for planet in NATAL_TARGETS:
            position = chart.position(planet)
            if position is None:
                continue
            targets.append(
                (
                    planet.value,
                    position.longitude,
                    {
                        "target_type": TransitTargetType.NATAL_PLANET,
                        "target_body": planet,
                        "house": position.house,
                    },
                )
            )

        if chart.angles is not None:
            angle_longitudes = {
                ChartAngle.ASC: chart.angles.ascendant,
                ChartAngle.MC: chart.angles.midheaven,
            }
            for angle in ANGLE_TARGETS:
                targets.append(
                    (
                        angle.value,
                        angle_longitudes[angle],
                        {
                            "target_type": TransitTargetType.NATAL_ANGLE,
                            "target_angle": angle,
                            "house": 1 if angle is ChartAngle.ASC else 10,
                        },
                    )
                )
        return targets

    # ------------------------------------------------------ candidate search

    def _find_candidates(
        self,
        body: Planet,
        grid: LongitudeGrid,
        targets: list[tuple[str, float, dict]],
    ) -> list[_Candidate]:
        candidates: list[_Candidate] = []
        for target_label, target_longitude, target_meta in targets:
            separations = np.abs(wrap180(grid.longitudes - target_longitude))
            for aspect in AspectType:
                orb_limit = transit_orb_limit(body, aspect)
                in_orb = np.abs(separations - aspect.angle) <= orb_limit
                if not in_orb.any():
                    continue
                for first, last in _true_runs(in_orb):
                    candidates.append(
                        _Candidate(
                            body=body,
                            aspect=aspect,
                            target_label=target_label,
                            target_longitude=target_longitude,
                            target_meta=target_meta,
                            orb_limit=orb_limit,
                            first_index=first,
                            last_index=last,
                        )
                    )
        return candidates

    def _refine_windows(
        self, body: Planet, grid: LongitudeGrid, candidates: list[_Candidate]
    ) -> None:
        """Refine every window edge of this body in one batched pass."""
        brackets: list[tuple[datetime, datetime, object]] = []
        slots: list[tuple[int, str]] = []
        last_index = len(grid.times) - 1

        for index, candidate in enumerate(candidates):
            edge = _orb_edge_function(
                candidate.target_longitude, candidate.aspect, candidate.orb_limit
            )
            if candidate.first_index == 0:
                candidate.window_start = grid.times[0]
                candidate.clipped_start = True
            else:
                brackets.append(
                    (
                        grid.times[candidate.first_index - 1],
                        grid.times[candidate.first_index],
                        edge,
                    )
                )
                slots.append((index, "start"))

            if candidate.last_index >= last_index:
                candidate.window_end = grid.times[last_index]
                candidate.clipped_end = True
            else:
                brackets.append(
                    (
                        grid.times[candidate.last_index],
                        grid.times[candidate.last_index + 1],
                        edge,
                    )
                )
                slots.append((index, "end"))

        resolved = self._sampler.bisect_batch(
            body, brackets, tolerance_seconds=300.0, iterations=16
        )
        for (index, which), moment in zip(slots, resolved, strict=True):
            candidate = candidates[index]
            if which == "start":
                candidate.window_start = moment or grid.times[
                    max(candidate.first_index - 1, 0)
                ]
            else:
                candidate.window_end = moment or grid.times[
                    min(candidate.last_index + 1, last_index)
                ]

    def _refine_passes(
        self, body: Planet, grid: LongitudeGrid, candidates: list[_Candidate]
    ) -> None:
        """Find every perfection inside every window, in one batched pass."""
        brackets: list[tuple[datetime, datetime, object]] = []
        owners: list[int] = []

        for index, candidate in enumerate(candidates):
            candidate.passes = []
            contact_points = {
                (candidate.target_longitude + candidate.aspect.angle) % 360.0
            }
            if candidate.aspect.angle not in (0.0, 180.0):
                contact_points.add(
                    (candidate.target_longitude - candidate.aspect.angle) % 360.0
                )

            low = max(candidate.first_index - 1, 0)
            high = min(candidate.last_index + 1, len(grid.times) - 1)
            for point in contact_points:
                offsets = np.asarray(wrap180(grid.longitudes[low : high + 1] - point))
                near = np.abs(offsets) < 90.0
                flips = (offsets[:-1] * offsets[1:] < 0) & near[:-1] & near[1:]
                for offset_index in np.flatnonzero(flips):
                    position = low + int(offset_index)
                    brackets.append(
                        (
                            grid.times[position],
                            grid.times[position + 1],
                            _crossing_function(point),
                        )
                    )
                    owners.append(index)

        resolved = self._sampler.bisect_batch(
            body, brackets, tolerance_seconds=20.0, iterations=22
        )
        found: list[tuple[int, datetime]] = [
            (owner, moment)
            for owner, moment in zip(owners, resolved, strict=True)
            if moment is not None
        ]
        speeds = self._sampler.speeds_at(body, [moment for _, moment in found])

        for (owner, moment), speed in zip(found, speeds, strict=True):
            candidate = candidates[owner]
            if candidate.window_start and moment < candidate.window_start:
                continue
            if candidate.window_end and moment > candidate.window_end:
                continue
            candidate.passes.append(
                TransitPass(
                    pass_number=0,
                    exact_at=moment,
                    direction=(
                        PassDirection.RETROGRADE if speed < 0 else PassDirection.DIRECT
                    ),
                    speed=round(speed, 6),
                )
            )

        for candidate in candidates:
            ordered = sorted(candidate.passes or [], key=lambda item: item.exact_at)
            candidate.passes = [
                replace(item, pass_number=number)
                for number, item in enumerate(ordered, start=1)
            ]

    # -------------------------------------------------------------- building

    def _build_events(
        self,
        *,
        chart: Chart,
        body: Planet,
        candidates: list[_Candidate],
        reference: datetime,
        window: tuple[datetime, datetime],
        chart_fingerprint: str,
    ) -> list[TransitEvent]:
        if not candidates:
            return []

        window_start, window_end = window

        # One sample at the reference instant serves every candidate, plus one
        # six hours later for the "is the orb closing?" test.
        longitude_now, longitude_later = (
            float(value)
            for value in self._sampler.longitudes(
                body, [reference, reference + timedelta(hours=6)]
            )
        )
        transit_house = house_of(longitude_now, chart.houses) if chart.houses else None

        # How close each transit gets *inside the requested window*. Judging a
        # Moon transit by its orb at one arbitrary instant scores it at zero by
        # mid-afternoon, even when it perfected that morning - the strength has
        # to describe the period, not the sampling instant.
        peak_orbs = self._peak_orbs(body, candidates, window_start, window_end)

        events: list[TransitEvent] = []
        for candidate in candidates:
            passes = candidate.passes or []
            exact_at = _closest_pass(passes, reference)
            orb_now = abs(
                separation(longitude_now, candidate.target_longitude)
                - candidate.aspect.angle
            )

            if exact_at is not None:
                applying = reference < exact_at
            else:
                # The aspect grazes the orb without ever perfecting: compare
                # the orb now with the orb six hours later.
                orb_later = abs(
                    separation(longitude_later, candidate.target_longitude)
                    - candidate.aspect.angle
                )
                applying = orb_later < orb_now

            peak_orb = peak_orbs[id(candidate)]
            strength = compute_strength(
                body=body,
                aspect=candidate.aspect,
                orb=peak_orb,
                orb_limit=candidate.orb_limit,
                applying=applying,
                target_meta=candidate.target_meta,
                pass_count=len(passes),
            )
            affected = sorted(
                {
                    value
                    for value in (candidate.target_meta.get("house"), transit_house)
                    if value is not None
                }
            )

            events.append(
                TransitEvent(
                    id=_event_id(
                        chart_fingerprint,
                        body,
                        candidate.target_label,
                        candidate.aspect,
                        candidate.window_start,
                    ),
                    transiting_body=body,
                    target_type=candidate.target_meta["target_type"],
                    target_body=candidate.target_meta.get("target_body"),
                    target_angle=candidate.target_meta.get("target_angle"),
                    target_house=candidate.target_meta.get("house"),
                    aspect_type=candidate.aspect,
                    orb=round(orb_now, 4),
                    maximum_orb=round(candidate.orb_limit, 4),
                    applying=applying,
                    start_at=candidate.window_start,
                    exact_at=exact_at,
                    end_at=candidate.window_end,
                    status=_status_for(
                        reference,
                        candidate.window_start,
                        exact_at,
                        candidate.window_end,
                        applying,
                    ),
                    strength=strength,
                    passes=passes,
                    affected_houses=affected,
                    window_clipped=candidate.clipped_start or candidate.clipped_end,
                    engine_version=ENGINE_VERSION,
                    scoring_version=W.SCORING_VERSION,
                    metadata={
                        "transiting_house": transit_house,
                        "target_longitude": round(candidate.target_longitude, 6),
                        "pass_count": len(passes),
                        "peak_orb": round(peak_orb, 4),
                    },
                )
            )
        return events

    def _peak_orbs(
        self,
        body: Planet,
        candidates: list[_Candidate],
        window_start: datetime,
        window_end: datetime,
    ) -> dict[int, float]:
        """Tightest orb each candidate reaches inside the window.

        Zero when the aspect perfects there; otherwise the best of the two
        clamped window edges, sampled in one batched call.
        """
        peaks: dict[int, float] = {}
        probes: list[datetime] = []
        owners: list[tuple[int, _Candidate]] = []

        for candidate in candidates:
            perfects_inside = any(
                window_start <= item.exact_at <= window_end
                for item in (candidate.passes or [])
            )
            if perfects_inside:
                peaks[id(candidate)] = 0.0
                continue

            first = max(candidate.window_start, window_start)
            last = min(candidate.window_end, window_end)
            if last < first:
                first = last = candidate.window_start
            probes.extend([first, last])
            owners.append((len(probes) - 2, candidate))

        if probes:
            sampled = self._sampler.longitudes(body, probes)
            for index, candidate in owners:
                orbs = [
                    abs(
                        separation(float(sampled[offset]), candidate.target_longitude)
                        - candidate.aspect.angle
                    )
                    for offset in (index, index + 1)
                ]
                peaks[id(candidate)] = min(orbs)

        return peaks

    # ------------------------------------------------------------ ingresses

    def _scan_ingresses(
        self,
        *,
        chart: Chart,
        body: Planet,
        grid: LongitudeGrid,
        start: datetime,
        end: datetime,
        chart_fingerprint: str,
    ) -> list[HouseIngress]:
        brackets: list[tuple[datetime, datetime, object]] = []
        owners: list[int] = []

        for house in chart.houses:
            offsets = np.asarray(wrap180(grid.longitudes - house.cusp_longitude))
            near = np.abs(offsets) < 90.0
            flips = (offsets[:-1] * offsets[1:] < 0) & near[:-1] & near[1:]
            for index in np.flatnonzero(flips):
                position = int(index)
                if grid.times[position + 1] < start or grid.times[position] > end:
                    continue
                brackets.append(
                    (
                        grid.times[position],
                        grid.times[position + 1],
                        _crossing_function(house.cusp_longitude),
                    )
                )
                owners.append(house.number)

        resolved = self._sampler.bisect_batch(
            body, brackets, tolerance_seconds=30.0, iterations=20
        )
        crossings = sorted(
            (
                (moment, house_number)
                for moment, house_number in zip(resolved, owners, strict=True)
                if moment is not None and start <= moment <= end
            ),
            key=lambda item: item[0],
        )
        if not crossings:
            return []

        speeds = self._sampler.speeds_at(body, [moment for moment, _ in crossings])
        results: list[HouseIngress] = []
        seen: set[int] = set()

        for (moment, house_number), speed in zip(crossings, speeds, strict=True):
            retrograde = speed < 0
            # Crossing a cusp forwards enters that house; backwards it steps
            # back into the previous one.
            to_house = house_number if not retrograde else (house_number - 2) % 12 + 1
            from_house = (to_house - 2) % 12 + 1 if not retrograde else house_number
            exit_at = next(
                (
                    later
                    for later, _ in crossings
                    if later > moment + timedelta(minutes=5)
                ),
                None,
            )
            results.append(
                HouseIngress(
                    id=_event_id(
                        chart_fingerprint, body, f"house_{to_house}", None, moment
                    ),
                    planet=body,
                    from_house=from_house,
                    to_house=to_house,
                    entered_at=moment,
                    estimated_exit_at=exit_at,
                    retrograde=retrograde,
                    re_entry=to_house in seen,
                    engine_version=ENGINE_VERSION,
                )
            )
            seen.add(to_house)
        return results

    # -------------------------------------------------------- current state

    def positions_at(self, moment: datetime) -> dict[Planet, float]:
        """Longitudes of every transiting body at one instant."""
        return {
            body: float(self._sampler.longitudes(body, [moment])[0])
            for body in DEFAULT_TRANSITING
        }

    def current_houses(self, chart: Chart, moment: datetime) -> dict[Planet, int]:
        """Which natal house each transiting body occupies at ``moment``."""
        if not chart.houses:
            return {}
        result: dict[Planet, int] = {}
        for body, longitude in self.positions_at(moment).items():
            house = house_of(longitude, chart.houses)
            if house is not None:
                result[body] = house
        return result


# --------------------------------------------------------------- functions


def _crossing_function(target_longitude: float):
    """f(longitude) = signed distance to a degree, for bisection."""

    def function(longitude: float) -> float:
        return float(wrap180(longitude - target_longitude))

    return function


def _orb_edge_function(target_longitude: float, aspect: AspectType, orb_limit: float):
    """f(longitude) = orb minus its limit; zero at the window edge."""

    def function(longitude: float) -> float:
        gap = abs(float(wrap180(longitude - target_longitude)))
        return abs(gap - aspect.angle) - orb_limit

    return function


def compute_strength(
    *,
    body: Planet,
    aspect: AspectType,
    orb: float,
    orb_limit: float,
    applying: bool,
    target_meta: dict,
    pass_count: int,
) -> int:
    """Deterministic 0-100 strength; the formula is in
    ``docs/transit_engine.md``."""
    closeness = max(0.0, 1.0 - (orb / orb_limit)) ** W.ORB_FALLOFF_EXPONENT

    if target_meta["target_type"] is TransitTargetType.NATAL_ANGLE:
        target_weight = W.ANGLE_TARGET_WEIGHT[target_meta["target_angle"]]
    else:
        target_weight = W.NATAL_TARGET_WEIGHT.get(target_meta.get("target_body"), 0.5)

    score = (
        100.0
        * closeness
        * W.ASPECT_WEIGHT[aspect]
        * W.TRANSITING_BODY_WEIGHT[body]
        * target_weight
    )
    score *= W.APPLYING_FACTOR if applying else W.SEPARATING_FACTOR
    if target_meta["target_type"] is TransitTargetType.NATAL_ANGLE:
        score *= W.ANGLE_INVOLVEMENT_BONUS
    if pass_count > 1:
        score *= W.MULTI_PASS_BONUS

    return int(round(min(100.0, max(0.0, score))))


def _true_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Contiguous stretches of True as (first_index, last_index)."""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(mask):
        if value and start is None:
            start = index
        elif not value and start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(mask) - 1))
    return runs


def _closest_pass(passes: list[TransitPass], reference: datetime) -> datetime | None:
    if not passes:
        return None
    upcoming = [item.exact_at for item in passes if item.exact_at >= reference]
    if upcoming:
        return min(upcoming)
    return max(item.exact_at for item in passes)


def _status_for(
    reference: datetime,
    window_start: datetime | None,
    exact_at: datetime | None,
    window_end: datetime | None,
    applying: bool,
) -> TransitStatus:
    if window_start and reference < window_start:
        return TransitStatus.APPROACHING
    if exact_at is None:
        return TransitStatus.APPROACHING if applying else TransitStatus.SEPARATING
    # "Exact" is the half day either side of perfection - what the app shows
    # as today's headline transit.
    if abs((reference - exact_at).total_seconds()) <= 12 * 3600:
        return TransitStatus.EXACT
    return (
        TransitStatus.APPROACHING if reference < exact_at else TransitStatus.SEPARATING
    )


def with_status(event: TransitEvent, reference: datetime) -> TransitEvent:
    """Re-evaluate status against a different reference instant."""
    if event.exact_at is None:
        return event
    applying = reference < event.exact_at
    return replace(
        event,
        status=_status_for(
            reference, event.start_at, event.exact_at, event.end_at, applying
        ),
        applying=applying,
    )


_engine: TransitEngine | None = None


def get_transit_engine() -> TransitEngine:
    global _engine
    if _engine is None:
        _engine = TransitEngine()
    return _engine
