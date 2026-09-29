"""Synastry engine.

Two real natal charts in, structured relationship factors out:

* **inter-aspects** between the two sets of bodies, plus contacts to each
  other's Ascendant and Midheaven,
* **house overlays**, kept directional - "her Venus in his 7th" and "his Venus
  in her 7th" are different statements, and averaging them away throws out
  what makes synastry worth reading,
* **theme scores** with the factor ids behind them.

The score is an astrological factor index, documented in
``docs/synastry_engine.md`` and versioned as ``synastry_score_v1``. It is not
a probability, and the API says so in ``score_semantics``.
"""

from __future__ import annotations

import hashlib
import math

from app.domain.astrology import Chart, separation
from app.domain.compatibility import (
    Direction,
    HouseOverlay,
    RelationshipTheme,
    SynastryAspect,
    SynastryResult,
    ThemeScore,
)
from app.domain.enums import AspectNature, AspectType, ChartAngle, Planet
from app.services.astrology import synastry_weights as W
from app.services.astrology.houses import house_of
from app.services.astrology.skyfield_engine import ENGINE_VERSION

SYNASTRY_BODIES: tuple[Planet, ...] = (
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

ANGLES: tuple[ChartAngle, ...] = (ChartAngle.ASC, ChartAngle.MC)

# Uranus, Neptune and Pluto move so slowly that two people born within a few
# years of each other share the same aspects between them. Those contacts say
# something about a generation, not about a relationship, so pairs where both
# bodies are generational are skipped - as is node-to-node, for the same
# reason. A generational planet contacting a *personal* planet still counts.
GENERATIONAL: frozenset[Planet] = frozenset(
    {Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO}
)


def is_generational_pair(first: Planet, second: Planet) -> bool:
    if first in GENERATIONAL and second in GENERATIONAL:
        return True
    return first.is_point and second.is_point


def _factor_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]


def pair_weight(first: Planet, second: Planet) -> float:
    key = frozenset({first, second})
    return W.PAIR_WEIGHTS.get(key, W.DEFAULT_PAIR_WEIGHT)


def pair_themes(first: Planet, second: Planet) -> list[RelationshipTheme]:
    key = frozenset({first, second})
    return list(W.PAIR_THEMES.get(key, W.DEFAULT_THEMES))


def orb_limit(
    first: Planet | None, second: Planet | None, aspect: AspectType, *, angle: bool
) -> float:
    limit = W.SYNASTRY_ORBS[aspect]
    if angle:
        limit += W.ANGLE_ORB_BONUS
    for planet in (first, second):
        if planet is None:
            continue
        if planet.is_luminary:
            limit += W.LUMINARY_ORB_BONUS / 2
        if planet.is_point:
            limit += W.NODE_ORB_PENALTY / 2
    return max(W.MIN_ORB, limit)


class SynastryEngine:
    def analyse(self, chart_a: Chart, chart_b: Chart) -> SynastryResult:
        warnings: list[str] = []
        if not chart_a.houses or not chart_b.houses:
            warnings.append(
                "house_overlays_unavailable: one chart has no houses (unknown "
                "birth time), so only inter-aspects are reported."
            )
        if chart_a.angles is None or chart_b.angles is None:
            warnings.append(
                "angle_contacts_unavailable: one chart has no angles, so "
                "Ascendant and Midheaven contacts are omitted."
            )

        aspects = self._aspects(chart_a, chart_b)
        overlays_a = self._overlays(chart_a, chart_b, Direction.A_TO_B)
        overlays_b = self._overlays(chart_b, chart_a, Direction.B_TO_A)

        themes = self._themes(aspects, overlays_a + overlays_b)
        overall = self._overall(themes)

        highlights = [
            item.label
            for item in sorted(aspects, key=lambda hit: -hit.weight)
            if item.weight >= W.MIN_HIGHLIGHT_WEIGHT
        ][: W.HIGHLIGHT_LIMIT]

        return SynastryResult(
            overall_score=overall,
            score_semantics=W.SCORE_SEMANTICS,
            themes=themes,
            aspects=aspects,
            overlays_a_in_b=overlays_a,
            overlays_b_in_a=overlays_b,
            highlights=highlights,
            source_factors=(
                [item.id for item in aspects]
                + [item.id for item in overlays_a]
                + [item.id for item in overlays_b]
            ),
            warnings=warnings,
            engine_version=ENGINE_VERSION,
            scoring_version=W.SYNASTRY_SCORING_VERSION,
        )

    # ------------------------------------------------------------ aspects

    def _aspects(self, chart_a: Chart, chart_b: Chart) -> list[SynastryAspect]:
        results: list[SynastryAspect] = []

        for position_a in chart_a.positions:
            if position_a.planet not in SYNASTRY_BODIES:
                continue
            for position_b in chart_b.positions:
                if position_b.planet not in SYNASTRY_BODIES:
                    continue
                if is_generational_pair(position_a.planet, position_b.planet):
                    continue
                hit = self._match(
                    first_longitude=position_a.longitude,
                    second_longitude=position_b.longitude,
                    first_planet=position_a.planet,
                    second_planet=position_b.planet,
                )
                if hit is not None:
                    results.append(hit)

        # Contacts to the other person's angles.
        for owner, other, direction in (
            (chart_a, chart_b, "a_planet_to_b_angle"),
            (chart_b, chart_a, "b_planet_to_a_angle"),
        ):
            if other.angles is None:
                continue
            angle_longitudes = {
                ChartAngle.ASC: other.angles.ascendant,
                ChartAngle.MC: other.angles.midheaven,
            }
            for position in owner.positions:
                if position.planet not in SYNASTRY_BODIES:
                    continue
                for angle in ANGLES:
                    hit = self._match_angle(
                        planet=position.planet,
                        planet_longitude=position.longitude,
                        angle=angle,
                        angle_longitude=angle_longitudes[angle],
                        direction=direction,
                    )
                    if hit is not None:
                        results.append(hit)

        results.sort(key=lambda item: (-item.weight, item.orb))
        return results

    def _match(
        self,
        *,
        first_longitude: float,
        second_longitude: float,
        first_planet: Planet,
        second_planet: Planet,
    ) -> SynastryAspect | None:
        gap = separation(first_longitude, second_longitude)
        best: SynastryAspect | None = None

        for aspect in AspectType:
            limit = orb_limit(first_planet, second_planet, aspect, angle=False)
            orb = abs(gap - aspect.angle)
            if orb > limit:
                continue
            if best is not None and orb >= best.orb:
                continue

            closeness = 1.0 - orb / limit
            weight = (
                closeness
                * W.ASPECT_WEIGHT[aspect]
                * pair_weight(first_planet, second_planet)
            )
            best = SynastryAspect(
                id=_factor_id(
                    "syn", first_planet.value, second_planet.value, aspect.value
                ),
                person_a_body=first_planet,
                person_a_angle=None,
                person_b_body=second_planet,
                person_b_angle=None,
                aspect=aspect,
                orb=round(orb, 4),
                max_orb=round(limit, 4),
                weight=round(weight, 5),
                nature=aspect.nature,
                themes=pair_themes(first_planet, second_planet),
            )
        return best

    def _match_angle(
        self,
        *,
        planet: Planet,
        planet_longitude: float,
        angle: ChartAngle,
        angle_longitude: float,
        direction: str,
    ) -> SynastryAspect | None:
        gap = separation(planet_longitude, angle_longitude)
        best: SynastryAspect | None = None

        for aspect in AspectType:
            limit = orb_limit(planet, None, aspect, angle=True)
            orb = abs(gap - aspect.angle)
            if orb > limit:
                continue
            if best is not None and orb >= best.orb:
                continue

            closeness = 1.0 - orb / limit
            weight = (
                closeness
                * W.ASPECT_WEIGHT[aspect]
                * W.ANGLE_WEIGHTS[angle]
                * W.ANGLE_PLANET_WEIGHTS.get(planet, 0.5)
            )
            is_a_planet = direction == "a_planet_to_b_angle"
            best = SynastryAspect(
                id=_factor_id("syn_angle", direction, planet.value, angle.value,
                              aspect.value),
                person_a_body=planet if is_a_planet else None,
                person_a_angle=None if is_a_planet else angle,
                person_b_body=None if is_a_planet else planet,
                person_b_angle=angle if is_a_planet else None,
                aspect=aspect,
                orb=round(orb, 4),
                max_orb=round(limit, 4),
                weight=round(weight, 5),
                nature=aspect.nature,
                themes=[RelationshipTheme.GENERAL]
                + (
                    [RelationshipTheme.LONG_TERM]
                    if angle is ChartAngle.MC
                    else [RelationshipTheme.ROMANCE]
                ),
            )
        return best

    # ----------------------------------------------------------- overlays

    def _overlays(
        self, owner: Chart, host: Chart, direction: Direction
    ) -> list[HouseOverlay]:
        """Owner's planets placed in the host's houses. Directional."""
        if not host.houses:
            return []

        overlays: list[HouseOverlay] = []
        for position in owner.positions:
            if position.planet not in SYNASTRY_BODIES:
                continue
            house = house_of(position.longitude, host.houses)
            if house is None:
                continue

            weight = (
                W.OVERLAY_HOUSE_WEIGHTS.get(house, 0.4)
                * W.OVERLAY_PLANET_WEIGHTS.get(position.planet, 0.5)
                * W.OVERLAY_SCALE
            )
            overlays.append(
                HouseOverlay(
                    id=_factor_id(
                        "overlay", direction.value, position.planet.value, str(house)
                    ),
                    direction=direction,
                    planet=position.planet,
                    house=house,
                    longitude=round(position.longitude, 4),
                    weight=round(weight, 5),
                    themes=list(W.HOUSE_THEMES.get(house, (RelationshipTheme.GENERAL,))),
                )
            )

        overlays.sort(key=lambda item: -item.weight)
        return overlays

    # ------------------------------------------------------------- themes

    def _themes(
        self, aspects: list[SynastryAspect], overlays: list[HouseOverlay]
    ) -> list[ThemeScore]:
        totals: dict[RelationshipTheme, float] = {
            theme: 0.0 for theme in RelationshipTheme
        }
        positives: dict[RelationshipTheme, list[str]] = {
            theme: [] for theme in RelationshipTheme
        }
        negatives: dict[RelationshipTheme, list[str]] = {
            theme: [] for theme in RelationshipTheme
        }
        factor_ids: dict[RelationshipTheme, list[str]] = {
            theme: [] for theme in RelationshipTheme
        }

        for hit in aspects:
            kind = (
                "conjunction"
                if hit.aspect is AspectType.CONJUNCTION
                else "harmonious"
                if hit.nature is AspectNature.HARMONIOUS
                else "challenging"
            )
            for theme in hit.themes:
                polarity = W.THEME_POLARITY[theme][kind]
                contribution = hit.weight * polarity
                totals[theme] += contribution
                factor_ids[theme].append(hit.id)
                (positives if contribution >= 0 else negatives)[theme].append(hit.id)

        for overlay in overlays:
            for theme in overlay.themes:
                totals[theme] += overlay.weight
                factor_ids[theme].append(overlay.id)
                positives[theme].append(overlay.id)

        scores: list[ThemeScore] = []
        for theme in RelationshipTheme:
            saturated = math.tanh(totals[theme] / W.THEME_SATURATION)
            raw = W.THEME_BASELINE + saturated * W.THEME_SENSITIVITY
            score = int(round(min(W.THEME_MAX, max(W.THEME_MIN, raw))))
            scores.append(
                ThemeScore(
                    theme=theme,
                    score=score,
                    strength=int(round(min(100.0, abs(saturated) * 100))),
                    positive_factors=positives[theme][:10],
                    challenging_factors=negatives[theme][:10],
                    factor_ids=factor_ids[theme][:20],
                )
            )
        return scores

    def _overall(self, themes: list[ThemeScore]) -> int:
        """Weighted mean of the themes, with conflict inverted.

        A high conflict index is not a high compatibility index, so it is
        flipped before it joins the average instead of quietly inflating it.
        """
        total = 0.0
        weight_sum = 0.0
        for item in themes:
            weight = W.OVERALL_THEME_WEIGHTS.get(item.theme, 1.0)
            value = (
                100 - item.score if item.theme in W.INVERTED_THEMES else item.score
            )
            total += value * weight
            weight_sum += weight
        return int(round(total / weight_sum)) if weight_sum else W.THEME_BASELINE


_engine: SynastryEngine | None = None


def get_synastry_engine() -> SynastryEngine:
    global _engine
    if _engine is None:
        _engine = SynastryEngine()
    return _engine
