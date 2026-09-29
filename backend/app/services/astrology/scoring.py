"""Deterministic scoring.

Every number the app shows - the daily frequency dials, a horoscope's love
score, a month's key periods - comes from here, and every one of them carries
the ids of the factors that produced it. That is what lets the UI show "the
influences behind this reading" and lets an expert (or Astro AI) see *why* a
number is what it is.

Rules:

* no randomness anywhere: the same chart, instant and ``SCORING_VERSION``
  always give the same output,
* no magic numbers in this file - they all live in ``weights.py``,
* the AI never produces a score; it only writes prose about these.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.astrology import Chart
from app.domain.calendar import CosmicEvent, CosmicEventType
from app.domain.enums import AspectNature, AspectType, Planet
from app.domain.horoscope import (
    AreaScore,
    FactorKind,
    HouseActivation,
    ImportantDate,
    ImportantHour,
    LifeArea,
    PeriodCluster,
    SourceFactor,
    Trend,
)
from app.domain.transit import HouseIngress, TransitEvent, TransitTargetType
from app.services.astrology import weights as W


@dataclass(slots=True)
class FactorBundle:
    """Factors plus the per-area weight they add up to."""

    factors: list[SourceFactor]
    area_weight: dict[LifeArea, float]
    area_factor_ids: dict[LifeArea, list[str]]

    @classmethod
    def empty(cls) -> "FactorBundle":
        return cls(
            factors=[],
            area_weight=defaultdict(float),
            area_factor_ids=defaultdict(list),
        )

    def add(self, factor: SourceFactor) -> None:
        self.factors.append(factor)
        for area in factor.areas:
            self.area_weight[area] += factor.contribution
            self.area_factor_ids[area].append(factor.id)

    def merge(self, other: "FactorBundle") -> None:
        for factor in other.factors:
            self.add(factor)


# --------------------------------------------------------------- polarity


def aspect_polarity(event: TransitEvent) -> float:
    """How benefic or malefic a contact reads, in [-1, 1].

    Trines and sextiles help, squares and oppositions press; a conjunction
    takes the colour of the transiting body - Jupiter conjunct anything is
    usually welcome, Saturn conjunct anything is usually work.
    """
    aspect = event.aspect_type
    if aspect is None:
        return W.CONJUNCTION_NEUTRAL_SIGN

    nature = aspect.nature
    if nature is AspectNature.HARMONIOUS:
        return W.HARMONIOUS_SIGN
    if nature is AspectNature.CHALLENGING:
        return W.CHALLENGING_SIGN

    if event.transiting_body in W.BENEFIC_BODIES:
        return W.CONJUNCTION_BENEFIC_SIGN
    if event.transiting_body in W.MALEFIC_BODIES:
        return W.CONJUNCTION_MALEFIC_SIGN
    return W.CONJUNCTION_NEUTRAL_SIGN


def transit_areas(event: TransitEvent) -> list[LifeArea]:
    """Which life areas a transit speaks to: the natal point it hits, the
    body doing the hitting, and the houses involved."""
    areas: list[LifeArea] = []
    if event.target_body is not None:
        areas.extend(W.TARGET_AREAS.get(event.target_body, ()))
    areas.extend(W.TRANSITING_AREAS.get(event.transiting_body, ()))
    for house in event.affected_houses:
        areas.extend(W.HOUSE_AREAS.get(house, ()))
    if event.target_type is TransitTargetType.NATAL_ANGLE:
        areas.append(LifeArea.GENERAL_ENERGY)

    ordered: list[LifeArea] = []
    for area in areas:
        if area not in ordered:
            ordered.append(area)
    return ordered


# ----------------------------------------------------------------- factors


def transit_factor(event: TransitEvent, *, scale: float = 1.0) -> SourceFactor:
    """One transit as a scored, explainable factor."""
    polarity = aspect_polarity(event)
    contribution = (event.strength / 100.0) * polarity * scale
    label = _transit_label(event)
    return SourceFactor(
        id=event.id,
        kind=FactorKind.TRANSIT,
        label=label,
        contribution=round(contribution, 5),
        areas=transit_areas(event),
        at=event.exact_at,
        detail={
            "transiting_body": event.transiting_body.value,
            "aspect": event.aspect_type.value if event.aspect_type else None,
            "target": event.target_label,
            "orb": event.orb,
            "strength": event.strength,
            "status": event.status.value,
            "applying": event.applying,
            "passes": len(event.passes),
        },
    )


def _transit_label(event: TransitEvent) -> str:
    aspect = event.aspect_type.value if event.aspect_type else "contact"
    return f"{event.transiting_body.value} {aspect} {event.target_label}"


def moon_house_factor(house: int, strength: float = W.MOON_HOUSE_WEIGHT) -> SourceFactor:
    return SourceFactor(
        id=f"moon_house_{house}",
        kind=FactorKind.MOON_HOUSE,
        label=f"moon_in_house_{house}",
        contribution=round(strength, 5),
        areas=list(W.HOUSE_AREAS.get(house, ())),
        detail={"house": house},
    )


def moon_phase_factor(event: CosmicEvent) -> SourceFactor:
    """New and full moons lift the areas of the house they land in; the
    house part is added by the personal layer."""
    polarity = 1.0 if event.type is CosmicEventType.NEW_MOON else 0.6
    return SourceFactor(
        id=event.id,
        kind=FactorKind.MOON_PHASE,
        label=event.type.value,
        contribution=round(W.MOON_PHASE_WEIGHT * polarity, 5),
        areas=[LifeArea.MOOD, LifeArea.GENERAL_ENERGY],
        at=event.exact_at,
        detail={"type": event.type.value, "sign": event.sign.value if event.sign else None},
    )


def retrograde_factor(event: CosmicEvent) -> SourceFactor:
    planet = event.planet.value if event.planet else "planet"
    areas = list(W.TRANSITING_AREAS.get(event.planet, ())) if event.planet else []
    return SourceFactor(
        id=event.id,
        kind=FactorKind.RETROGRADE,
        label=f"{planet}_retrograde",
        contribution=round(-W.RETROGRADE_PENALTY, 5),
        areas=areas or [LifeArea.GENERAL_ENERGY],
        at=event.exact_at,
        detail={
            "planet": planet,
            "start_at": event.start_at.isoformat() if event.start_at else None,
            "end_at": event.end_at.isoformat() if event.end_at else None,
        },
    )


def ingress_factor(ingress: HouseIngress) -> SourceFactor:
    return SourceFactor(
        id=ingress.id,
        kind=FactorKind.HOUSE_INGRESS,
        label=f"{ingress.planet.value}_enters_house_{ingress.to_house}",
        contribution=round(
            W.TRANSITING_BODY_WEIGHT.get(ingress.planet, 0.5) * 0.5, 5
        ),
        areas=list(W.HOUSE_AREAS.get(ingress.to_house, ())),
        at=ingress.entered_at,
        detail={
            "planet": ingress.planet.value,
            "from_house": ingress.from_house,
            "to_house": ingress.to_house,
            "retrograde": ingress.retrograde,
            "re_entry": ingress.re_entry,
        },
    )


# ------------------------------------------------------------------ scores


def score_areas(
    bundle: FactorBundle,
    *,
    areas: tuple[LifeArea, ...] | None = None,
    previous: dict[LifeArea, int] | None = None,
) -> list[AreaScore]:
    """Turn accumulated factor weight into 0-100 scores per area."""
    wanted = areas or tuple(LifeArea)
    results: list[AreaScore] = []

    for area in wanted:
        weight = bundle.area_weight.get(area, 0.0)
        # tanh keeps the score inside a believable band however many factors
        # pile up, while preserving the ordering between areas.
        saturated = math.tanh(weight / W.AREA_SATURATION)
        raw = W.BASELINE_SCORE + saturated * W.AREA_SENSITIVITY
        score = int(round(min(W.SCORE_MAX, max(W.SCORE_MIN, raw))))

        factor_ids = bundle.area_factor_ids.get(area, [])
        strength = int(round(min(100.0, abs(saturated) * 100.0)))

        trend = Trend.STEADY
        if previous and area in previous:
            delta = score - previous[area]
            if delta >= 4:
                trend = Trend.RISING
            elif delta <= -4:
                trend = Trend.FALLING
        elif saturated > 0.15:
            trend = Trend.RISING
        elif saturated < -0.15:
            trend = Trend.FALLING

        results.append(
            AreaScore(
                area=area,
                score=score,
                trend=trend,
                strength=strength,
                factor_ids=factor_ids[:12],
            )
        )
    return results


def overall_score(scores: list[AreaScore]) -> int:
    if not scores:
        return W.BASELINE_SCORE
    return int(round(sum(item.score for item in scores) / len(scores)))


# --------------------------------------------------------- important hours


def important_hours(
    events: list[TransitEvent],
    *,
    day_start: datetime,
    day_end: datetime,
    limit: int = W.MAX_IMPORTANT_HOURS,
) -> list[ImportantHour]:
    """Windows around the day's real exact contacts.

    Not "lucky hours from a table": every window is anchored to a perfection
    the engine computed, and its width scales with that contact's strength.
    """
    candidates: list[tuple[datetime, TransitEvent]] = []
    for event in events:
        if event.strength < W.IMPORTANT_HOUR_MIN_STRENGTH:
            continue
        for item in event.passes:
            if day_start <= item.exact_at <= day_end:
                candidates.append((item.exact_at, event))

    candidates.sort(key=lambda item: (-item[1].strength, item[0]))
    hours: list[ImportantHour] = []

    for moment, event in candidates[:limit]:
        span = W.IMPORTANT_HOUR_BASE_MINUTES + (
            (W.IMPORTANT_HOUR_MAX_MINUTES - W.IMPORTANT_HOUR_BASE_MINUTES)
            * event.strength
            / 100.0
        )
        half = timedelta(minutes=span / 2)
        polarity = aspect_polarity(event)
        hours.append(
            ImportantHour(
                start=max(day_start, moment - half),
                end=min(day_end, moment + half),
                type=(
                    "supportive"
                    if polarity > 0.2
                    else "demanding"
                    if polarity < -0.2
                    else "notable"
                ),
                strength=event.strength,
                reason=_transit_label(event),
                factor_ids=[event.id],
            )
        )

    hours.sort(key=lambda hour: hour.start)
    return hours


def important_dates(
    events: list[TransitEvent],
    *,
    start: datetime,
    end: datetime,
    limit: int = 10,
) -> list[ImportantDate]:
    """The strongest perfections inside the period."""
    rows: list[ImportantDate] = []
    for event in events:
        for item in event.passes:
            if not (start <= item.exact_at <= end):
                continue
            polarity = aspect_polarity(event)
            rows.append(
                ImportantDate(
                    date=item.exact_at,
                    label=_transit_label(event),
                    strength=event.strength,
                    nature=(
                        "opportunity"
                        if polarity > 0.2
                        else "challenge"
                        if polarity < -0.2
                        else "turning_point"
                    ),
                    factor_ids=[event.id],
                )
            )
    rows.sort(key=lambda row: (-row.strength, row.date))
    return sorted(rows[:limit], key=lambda row: row.date)


def house_activations(
    events: list[TransitEvent],
    ingresses: list[HouseIngress],
    current_houses: dict[Planet, int],
) -> list[HouseActivation]:
    """Which natal houses are busy, and with what."""
    planets: dict[int, list[Planet]] = defaultdict(list)
    strength: dict[int, float] = defaultdict(float)
    factor_ids: dict[int, list[str]] = defaultdict(list)

    for body, house in current_houses.items():
        if body not in planets[house]:
            planets[house].append(body)
        strength[house] += W.TRANSITING_BODY_WEIGHT.get(body, 0.5) * 20

    for event in events:
        for house in event.affected_houses:
            strength[house] += event.strength / 10.0
            if len(factor_ids[house]) < 8:
                factor_ids[house].append(event.id)

    for ingress in ingresses:
        strength[ingress.to_house] += 8.0
        if ingress.planet not in planets[ingress.to_house]:
            planets[ingress.to_house].append(ingress.planet)
        if len(factor_ids[ingress.to_house]) < 8:
            factor_ids[ingress.to_house].append(ingress.id)

    activations = [
        HouseActivation(
            house=house,
            planets=sorted(planets[house], key=lambda body: body.value),
            strength=int(round(min(100.0, value))),
            factor_ids=factor_ids[house],
        )
        for house, value in strength.items()
        if value > 0
    ]
    activations.sort(key=lambda item: -item.strength)
    return activations


# -------------------------------------------------------------- clustering


def cluster_periods(
    events: list[TransitEvent],
    *,
    start: datetime,
    end: datetime,
    threshold: float = W.CLUSTER_THRESHOLD,
    min_days: int = W.CLUSTER_MIN_DAYS,
    max_gap_days: int = W.CLUSTER_MAX_GAP_DAYS,
    limit: int = W.MAX_CLUSTERS,
) -> list[PeriodCluster]:
    """Find stretches of days that share a theme.

    Deterministic by construction: each day gets the weight of every transit
    in orb that day, days above the threshold are grouped, short gaps are
    bridged, and the strongest groups are returned.
    """
    total_days = max(1, int((end - start).total_seconds() // 86400) + 1)
    daily_weight: list[float] = [0.0] * total_days
    daily_areas: list[dict[LifeArea, float]] = [
        defaultdict(float) for _ in range(total_days)
    ]
    daily_factors: list[list[str]] = [[] for _ in range(total_days)]

    for event in events:
        if event.start_at is None or event.end_at is None:
            continue
        first = max(0, int((event.start_at - start).total_seconds() // 86400))
        last = min(
            total_days - 1, int((event.end_at - start).total_seconds() // 86400)
        )
        if last < 0 or first > total_days - 1:
            continue
        weight = event.strength / 100.0
        areas = transit_areas(event)
        for day in range(first, last + 1):
            daily_weight[day] += weight
            for area in areas:
                daily_areas[day][area] += weight
            if len(daily_factors[day]) < 10:
                daily_factors[day].append(event.id)

    # Relative threshold: a "key period" is a stretch that stands out from
    # this period's own baseline, not one that clears a fixed number. A month
    # under three slow transits would otherwise be one long cluster.
    mean = sum(daily_weight) / total_days
    variance = sum((value - mean) ** 2 for value in daily_weight) / total_days
    cutoff = max(threshold, mean + W.CLUSTER_RELATIVE_SIGMA * (variance ** 0.5))

    above = [day for day, value in enumerate(daily_weight) if value >= cutoff]
    if not above:
        return []

    groups: list[list[int]] = [[above[0]]]
    for day in above[1:]:
        if day - groups[-1][-1] <= max_gap_days + 1:
            groups[-1].append(day)
        else:
            groups.append([day])

    clusters: list[PeriodCluster] = []
    for group in groups:
        first, last = group[0], group[-1]
        if last - first + 1 < min_days:
            continue

        area_totals: dict[LifeArea, float] = defaultdict(float)
        factor_ids: list[str] = []
        for day in range(first, last + 1):
            for area, value in daily_areas[day].items():
                area_totals[area] += value
            for factor in daily_factors[day]:
                if factor not in factor_ids:
                    factor_ids.append(factor)

        top_areas = [
            area
            for area, _ in sorted(
                area_totals.items(), key=lambda item: (-item[1], item[0].value)
            )[:3]
        ]
        peak = max(daily_weight[first : last + 1])
        relative = peak / cutoff if cutoff else 1.0
        clusters.append(
            PeriodCluster(
                start_at=start + timedelta(days=first),
                end_at=start + timedelta(days=last + 1) - timedelta(seconds=1),
                areas=top_areas,
                strength=int(round(min(100.0, 55.0 * relative))),
                source_factors=factor_ids[:12],
                label="_".join(area.value for area in top_areas[:2]),
            )
        )

    clusters.sort(key=lambda cluster: -cluster.strength)
    return sorted(clusters[:limit], key=lambda cluster: cluster.start_at)


# ----------------------------------------------------- opportunities / risks


def split_opportunities(
    events: list[TransitEvent], *, limit: int = 5
) -> tuple[list[str], list[str]]:
    """Two human-readable lists, derived from aspect polarity."""
    opportunities: list[str] = []
    challenges: list[str] = []
    for event in sorted(events, key=lambda item: -item.strength):
        polarity = aspect_polarity(event)
        label = _transit_label(event)
        if polarity > 0.2 and len(opportunities) < limit:
            opportunities.append(label)
        elif polarity < -0.2 and len(challenges) < limit:
            challenges.append(label)
    return opportunities, challenges
