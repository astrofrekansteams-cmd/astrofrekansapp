"""Horary analysis engine.

Produces the structured factors a horary judgement is built from: the
significators, their dignities, the aspects between them and whether they
perfect, receptions, the Moon's condition, and the classical warnings.

It does **not** answer the question. There is no yes/no in the output, and
that is deliberate - the judgement belongs to the astrologer, or to Astro AI
in phase B6 with proper framing. A backend that returned "yes, you will get
the job" would be making a claim neither the astrology nor the product can
stand behind.

Conventions: Lilly, *Christian Astrology* (1647), configured in
``horary_rules.py`` (``horary_rules_v1``) and ``dignities.py``
(``dignity_rules_v1``). Techniques the engine cannot detect reliably are
listed in ``NOT_IMPLEMENTED_TECHNIQUES`` rather than silently omitted.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from app.domain.astrology import Chart, separation, signed_separation
from app.domain.enums import AspectType, Planet, ZodiacSign
from app.domain.horary import (
    NOT_IMPLEMENTED_TECHNIQUES,
    DignityFactor,
    HoraryAnalysis,
    HoraryAspect,
    HoraryWarning,
    MoonCondition,
    ObstructionFactor,
    ObstructionKind,
    PerfectionFactor,
    PerfectionKind,
    Reception,
    ReceptionKind,
    Significator,
)
from app.services.astrology import horary_rules as R
from app.services.astrology.dignities import (
    CLASSICAL_PLANETS,
    DIGNITY_RULES_VERSION,
    EXALTATIONS,
    TRADITIONAL_RULERS,
    accidental_dignity,
    essential_dignity,
    face_ruler,
    is_day_chart,
    term_ruler,
    triplicity_ruler,
)
from app.services.astrology.sampling import EphemerisSampler
from app.services.astrology.skyfield_engine import ENGINE_VERSION


def _factor_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]


class HoraryAnalysisEngine:
    def __init__(self, sampler: EphemerisSampler | None = None) -> None:
        self._sampler = sampler or EphemerisSampler()

    # ------------------------------------------------------------- entry

    def analyse(
        self,
        chart: Chart,
        *,
        question: str,
        category: R.HoraryCategory | None = None,
        house_override: int | None = None,
        duplicate_suspected: bool = False,
    ) -> HoraryAnalysis:
        if not chart.houses or chart.angles is None:
            raise ValueError("A horary chart needs houses and angles.")

        moment = chart.moment_utc
        day_chart = is_day_chart(chart)
        rulers = chart.house_rulers_traditional()

        quesited_house = R.house_for_category(category, house_override)
        alternatives = list(
            R.CATEGORY_ALTERNATIVE_HOUSES.get(category, ()) if category else ()
        )

        querent = self._significator(
            chart, R.QUERENT_HOUSE, "querent", day_chart, rulers
        )
        quesited = self._significator(
            chart, quesited_house, "quesited", day_chart, rulers
        )
        co_significator = self._moon_significator(chart, day_chart)

        moon = self._moon_condition(chart, day_chart)

        aspects = self._significator_aspects(chart, querent, quesited, moment)
        applying = [item for item in aspects if item.applying]
        separating = [item for item in aspects if not item.applying]

        receptions = self._receptions(chart, querent, quesited, day_chart)

        perfection = self._perfection_factors(
            chart, querent, quesited, applying, receptions, moment
        )
        obstruction = self._obstruction_factors(
            chart, querent, quesited, applying, separating, perfection, moment
        )
        dignity_factors = self._dignity_factors(querent, quesited, co_significator)
        warnings = self._warnings(
            chart, querent, quesited, moon, duplicate_suspected
        )

        source_factors = (
            [item.id for item in aspects]
            + [item.id for item in receptions]
            + [item.id for item in perfection]
            + [item.id for item in obstruction]
            + [item.id for item in dignity_factors]
        )

        return HoraryAnalysis(
            question=question,
            category=category.value if category else None,
            asked_at_utc=moment,
            querent_house=R.QUERENT_HOUSE,
            quesited_house=quesited_house,
            alternative_quesited_houses=alternatives,
            querent=querent,
            quesited=quesited,
            co_significator=co_significator,
            moon=moon,
            receptions=receptions,
            applying_aspects=applying,
            separating_aspects=separating,
            perfection_factors=perfection,
            obstruction_factors=obstruction,
            dignity_factors=dignity_factors,
            house_rulers=rulers,
            warnings=warnings,
            source_factors=source_factors,
            is_day_chart=day_chart,
            not_implemented=list(NOT_IMPLEMENTED_TECHNIQUES),
            confidence_metadata={
                "significators_identical": querent.planet is quesited.planet,
                "perfection_count": len(perfection),
                "obstruction_count": len(obstruction),
                "warning_count": len(warnings),
                "moon_void_of_course": moon.void_of_course,
                "note": (
                    "Structured factors only. This engine does not judge the "
                    "question; it reports what the chart contains."
                ),
            },
            engine_version=ENGINE_VERSION,
            rules_version=R.HORARY_RULES_VERSION,
            dignity_version=DIGNITY_RULES_VERSION,
        )

    # ------------------------------------------------------ significators

    def _significator(
        self,
        chart: Chart,
        house_number: int,
        role: str,
        day_chart: bool,
        rulers: dict[int, Planet],
    ) -> Significator:
        house = chart.house(house_number)
        ruler = rulers[house_number]
        position = chart.position(ruler)

        essential = (
            essential_dignity(ruler, position.longitude, is_day=day_chart)
            if position
            else None
        )
        sun = chart.position(Planet.SUN)
        accidental = (
            accidental_dignity(position, sun_longitude=sun.longitude)
            if position and sun
            else None
        )

        return Significator(
            role=role,
            house=house_number,
            sign=house.sign,
            planet=ruler,
            longitude=round(position.longitude, 6) if position else 0.0,
            speed=round(position.speed_longitude, 6) if position else 0.0,
            retrograde=bool(position and position.retrograde),
            in_house=position.house if position else None,
            essential=essential,
            accidental=accidental,
            note=(
                "Traditional ruler of the house cusp sign; outer planets are "
                "never used as significators."
            ),
        )

    def _moon_significator(self, chart: Chart, day_chart: bool) -> Significator:
        """The Moon co-signifies the querent in every horary chart."""
        position = chart.position(Planet.MOON)
        sun = chart.position(Planet.SUN)
        return Significator(
            role="co_significator",
            house=R.QUERENT_HOUSE,
            sign=position.sign,
            planet=Planet.MOON,
            longitude=round(position.longitude, 6),
            speed=round(position.speed_longitude, 6),
            retrograde=False,
            in_house=position.house,
            essential=essential_dignity(
                Planet.MOON, position.longitude, is_day=day_chart
            ),
            accidental=(
                accidental_dignity(position, sun_longitude=sun.longitude)
                if sun
                else None
            ),
            note="The Moon co-signifies the querent and carries the flow of events.",
        )

    # --------------------------------------------------------------- moon

    def _moon_condition(self, chart: Chart, day_chart: bool) -> MoonCondition:
        position = chart.position(Planet.MOON)
        moment = chart.moment_utc
        sun = chart.position(Planet.SUN)

        leaves_at = self._sign_exit(Planet.MOON, position.longitude, moment)
        last_aspect = self._moon_last_aspect(chart, moment)
        next_aspect = self._moon_next_aspect(chart, moment, leaves_at)

        elongation = (
            (position.longitude - sun.longitude) % 360 if sun else 0.0
        )
        phase = _phase_name(elongation)

        return MoonCondition(
            sign=position.sign,
            degree=round(position.longitude % 30, 4),
            house=position.house,
            speed=round(position.speed_longitude, 5),
            phase=phase,
            # Void of course: no further Ptolemaic aspect to a classical
            # planet before leaving the sign (traditional_sign_based_v1).
            void_of_course=next_aspect is None,
            void_definition=R.VOC_DEFINITION,
            last_aspect=last_aspect,
            next_aspect=next_aspect,
            leaves_sign_at=leaves_at,
            in_via_combusta=(
                R.VIA_COMBUSTA_START <= position.longitude <= R.VIA_COMBUSTA_END
            ),
            essential=essential_dignity(
                Planet.MOON, position.longitude, is_day=day_chart
            ),
            accidental=(
                accidental_dignity(position, sun_longitude=sun.longitude)
                if sun
                else None
            ),
        )

    def _sign_exit(
        self, planet: Planet, longitude: float, moment: datetime
    ) -> datetime | None:
        """When the body next crosses into the following sign."""
        boundary = (int(longitude // 30) + 1) * 30.0 % 360.0
        crossings = self._sampler.crossings(
            planet,
            boundary,
            moment,
            moment + timedelta(days=_sign_search_days(planet)),
        )
        return crossings[0] if crossings else None

    def _moon_next_aspect(
        self, chart: Chart, moment: datetime, leaves_at: datetime | None
    ) -> HoraryAspect | None:
        """The Moon's next Ptolemaic aspect to a classical planet, if it
        happens before the Moon leaves its sign."""
        horizon = leaves_at or moment + timedelta(days=3)
        moon_position = chart.position(Planet.MOON)
        best: HoraryAspect | None = None

        for planet in CLASSICAL_PLANETS:
            if planet is Planet.MOON:
                continue
            other = chart.position(planet)
            if other is None:
                continue
            for aspect in R.PERFECTING_ASPECTS:
                # Both bodies move: a fixed-target search would mis-call void
                # of course near a boundary, and void of course is a headline
                # warning.
                exact_at = self._search_pair(
                    Planet.MOON, planet, aspect, moment, horizon
                )
                if exact_at is None:
                    continue
                if best is None or exact_at < best.exact_at:
                    best = self._build_aspect(
                        Planet.MOON,
                        planet,
                        aspect,
                        moon_position.longitude,
                        other.longitude,
                        moment,
                        exact_at,
                        applying=True,
                        perfects_before_sign_change=True,
                    )
        return best

    def _moon_last_aspect(
        self, chart: Chart, moment: datetime
    ) -> HoraryAspect | None:
        """The Moon's most recent separating Ptolemaic aspect."""
        moon_position = chart.position(Planet.MOON)
        best: HoraryAspect | None = None

        for planet in CLASSICAL_PLANETS:
            if planet is Planet.MOON:
                continue
            other = chart.position(planet)
            if other is None:
                continue
            for aspect in R.PERFECTING_ASPECTS:
                exact_at = self._search_pair(
                    Planet.MOON,
                    planet,
                    aspect,
                    moment - timedelta(days=3),
                    moment,
                    last=True,
                )
                if exact_at is None:
                    continue
                if best is None or exact_at > best.exact_at:
                    best = self._build_aspect(
                        Planet.MOON,
                        planet,
                        aspect,
                        moon_position.longitude,
                        other.longitude,
                        moment,
                        exact_at,
                        applying=False,
                        perfects_before_sign_change=None,
                    )
        return best

    # ------------------------------------------------------------ aspects

    def _significator_aspects(
        self,
        chart: Chart,
        querent: Significator,
        quesited: Significator,
        moment: datetime,
    ) -> list[HoraryAspect]:
        """Aspects between the two significators, in orb by Lilly's moieties."""
        if querent.planet is quesited.planet:
            return []

        results: list[HoraryAspect] = []
        max_orb = R.aspect_orb(querent.planet.value, quesited.planet.value)

        for aspect in R.PERFECTING_ASPECTS:
            gap = separation(querent.longitude, quesited.longitude)
            orb = abs(gap - aspect.angle)
            if orb > max_orb:
                continue

            exact_at = self._next_exact(
                querent.planet,
                quesited.longitude,
                aspect,
                moment,
                moment + timedelta(days=R.PERFECTION_SEARCH_DAYS),
                moving_target=quesited.planet,
            )
            applying = exact_at is not None
            if exact_at is None:
                exact_at = self._previous_exact(
                    querent.planet,
                    quesited.longitude,
                    aspect,
                    moment,
                    moving_target=quesited.planet,
                )

            perfects_in_sign = None
            if applying:
                exit_querent = self._sign_exit(
                    querent.planet, querent.longitude, moment
                )
                exit_quesited = self._sign_exit(
                    quesited.planet, quesited.longitude, moment
                )
                limits = [item for item in (exit_querent, exit_quesited) if item]
                perfects_in_sign = not limits or exact_at <= min(limits)

            results.append(
                self._build_aspect(
                    querent.planet,
                    quesited.planet,
                    aspect,
                    querent.longitude,
                    quesited.longitude,
                    moment,
                    exact_at,
                    applying=applying,
                    perfects_before_sign_change=perfects_in_sign,
                )
            )
        return results

    def _build_aspect(
        self,
        first: Planet,
        second: Planet,
        aspect: AspectType,
        first_longitude: float,
        second_longitude: float,
        moment: datetime,
        exact_at: datetime | None,
        *,
        applying: bool,
        perfects_before_sign_change: bool | None,
    ) -> HoraryAspect:
        orb = abs(separation(first_longitude, second_longitude) - aspect.angle)
        days = (
            (exact_at - moment).total_seconds() / 86400 if exact_at else None
        )
        return HoraryAspect(
            id=_factor_id(
                "aspect", first.value, second.value, aspect.value,
                moment.isoformat(),
            ),
            first=first,
            second=second,
            aspect=aspect,
            orb=round(orb, 4),
            max_orb=round(R.aspect_orb(first.value, second.value), 4),
            applying=applying,
            exact_at=exact_at,
            perfects_before_sign_change=perfects_before_sign_change,
            days_to_exact=round(days, 4) if days is not None else None,
        )

    def _next_exact(
        self,
        mover: Planet,
        target_longitude: float,
        aspect: AspectType,
        start: datetime,
        end: datetime,
        *,
        moving_target: Planet | None = None,
    ) -> datetime | None:
        """When the aspect next perfects, searching forward.

        With ``moving_target`` both bodies move, which is the real case for
        two significators; the search then walks the separation rather than a
        fixed degree.
        """
        if moving_target is None:
            points = {(target_longitude + aspect.angle) % 360}
            if aspect.angle not in (0.0, 180.0):
                points.add((target_longitude - aspect.angle) % 360)
            moments = [
                item
                for point in points
                for item in self._sampler.crossings(mover, point, start, end)
            ]
            return min(moments) if moments else None

        return self._search_pair(mover, moving_target, aspect, start, end)

    def _previous_exact(
        self,
        mover: Planet,
        target_longitude: float,
        aspect: AspectType,
        moment: datetime,
        *,
        moving_target: Planet | None = None,
        lookback_days: int = 30,
    ) -> datetime | None:
        start = moment - timedelta(days=lookback_days)
        if moving_target is None:
            points = {(target_longitude + aspect.angle) % 360}
            if aspect.angle not in (0.0, 180.0):
                points.add((target_longitude - aspect.angle) % 360)
            moments = [
                item
                for point in points
                for item in self._sampler.crossings(mover, point, start, moment)
            ]
            return max(moments) if moments else None
        return self._search_pair(mover, moving_target, aspect, start, moment, last=True)

    def _search_pair(
        self,
        first: Planet,
        second: Planet,
        aspect: AspectType,
        start: datetime,
        end: datetime,
        *,
        last: bool = False,
        step_hours: int | None = None,
    ) -> datetime | None:
        """Find where the separation between two moving bodies equals the
        aspect angle."""
        if step_hours is None:
            # The Moon covers 13 degrees a day, so a six-hour step could walk
            # straight over a contact.
            step_hours = 2 if Planet.MOON in (first, second) else 6
        steps = max(int((end - start).total_seconds() // (step_hours * 3600)), 2)
        times = [start + timedelta(hours=step_hours * index) for index in range(steps + 1)]
        first_longitudes = self._sampler.longitudes(first, times)
        second_longitudes = self._sampler.longitudes(second, times)
        offsets = [
            separation(float(a), float(b)) - aspect.angle
            for a, b in zip(first_longitudes, second_longitudes, strict=True)
        ]

        crossings: list[datetime] = []
        for index in range(len(offsets) - 1):
            if offsets[index] == 0.0:
                crossings.append(times[index])
            elif offsets[index] * offsets[index + 1] < 0:
                crossings.append(
                    self._bisect_pair(
                        first, second, aspect, times[index], times[index + 1]
                    )
                )
        if not crossings:
            return None
        return max(crossings) if last else min(crossings)

    def _bisect_pair(
        self,
        first: Planet,
        second: Planet,
        aspect: AspectType,
        low: datetime,
        high: datetime,
        *,
        iterations: int = 18,
        tolerance_seconds: float = 60.0,
    ) -> datetime:
        def offset(moment: datetime) -> float:
            a = self._sampler.value_at(first, moment)
            b = self._sampler.value_at(second, moment)
            return separation(a, b) - aspect.angle

        low_value = offset(low)
        for _ in range(iterations):
            if (high - low).total_seconds() <= tolerance_seconds:
                break
            middle = low + (high - low) / 2
            middle_value = offset(middle)
            if low_value * middle_value <= 0:
                high = middle
            else:
                low, low_value = middle, middle_value
        return low + (high - low) / 2

    # --------------------------------------------------------- receptions

    def _receptions(
        self,
        chart: Chart,
        querent: Significator,
        quesited: Significator,
        day_chart: bool,
    ) -> list[Reception]:
        """Which significator receives the other, and by what dignity."""
        pairs = [(querent, quesited), (quesited, querent)]
        found: dict[tuple[Planet, Planet, ReceptionKind], Reception] = {}

        for host, guest in pairs:
            host_planet = host.planet
            guest_planet = guest.planet
            if host_planet is guest_planet:
                continue

            guest_sign = ZodiacSign.from_longitude(guest.longitude)
            guest_degree = guest.longitude % 30

            checks: list[tuple[ReceptionKind, Planet, int]] = [
                (ReceptionKind.DOMICILE, TRADITIONAL_RULERS[guest_sign], 5),
                (
                    ReceptionKind.TRIPLICITY,
                    triplicity_ruler(guest_sign, is_day=day_chart),
                    3,
                ),
                (ReceptionKind.TERM, term_ruler(guest_sign, guest_degree), 2),
                (ReceptionKind.FACE, face_ruler(guest_sign, guest_degree), 1),
            ]
            exaltation = EXALTATIONS.get(host_planet)
            if exaltation is not None and exaltation[0] is guest_sign:
                checks.append((ReceptionKind.EXALTATION, host_planet, 4))

            for kind, ruler, strength in checks:
                if ruler is not host_planet:
                    continue
                found[(host_planet, guest_planet, kind)] = Reception(
                    id=_factor_id(
                        "reception", host_planet.value, guest_planet.value, kind.value
                    ),
                    from_planet=host_planet,
                    to_planet=guest_planet,
                    kind=kind,
                    mutual=False,
                    strength=strength,
                    note=f"{host_planet.value} receives {guest_planet.value} by {kind.value}",
                )

        # Mutual when each receives the other, by any dignity.
        receptions = list(found.values())
        for reception in receptions:
            mirrored = any(
                other.from_planet is reception.to_planet
                and other.to_planet is reception.from_planet
                for other in receptions
            )
            if mirrored:
                found[
                    (reception.from_planet, reception.to_planet, reception.kind)
                ] = Reception(
                    id=reception.id,
                    from_planet=reception.from_planet,
                    to_planet=reception.to_planet,
                    kind=reception.kind,
                    mutual=True,
                    strength=reception.strength,
                    note=reception.note,
                )

        return sorted(
            found.values(), key=lambda item: (-item.strength, item.from_planet.value)
        )

    # ------------------------------------------------- perfection factors

    def _perfection_factors(
        self,
        chart: Chart,
        querent: Significator,
        quesited: Significator,
        applying: list[HoraryAspect],
        receptions: list[Reception],
        moment: datetime,
    ) -> list[PerfectionFactor]:
        factors: list[PerfectionFactor] = []

        for aspect in applying:
            if aspect.perfects_before_sign_change is False:
                continue
            factors.append(
                PerfectionFactor(
                    id=_factor_id("perfection", "direct", aspect.id),
                    kind=PerfectionKind.DIRECT,
                    planets=[aspect.first, aspect.second],
                    aspect=aspect.aspect,
                    exact_at=aspect.exact_at,
                    days_to_exact=aspect.days_to_exact,
                    detail={
                        "orb": aspect.orb,
                        "aspect_id": aspect.id,
                        "perfects_before_sign_change": (
                            aspect.perfects_before_sign_change
                        ),
                    },
                )
            )

        mutual = [item for item in receptions if item.mutual]
        if mutual:
            factors.append(
                PerfectionFactor(
                    id=_factor_id("perfection", "mutual_reception", mutual[0].id),
                    kind=PerfectionKind.MUTUAL_RECEPTION,
                    planets=[mutual[0].from_planet, mutual[0].to_planet],
                    aspect=None,
                    exact_at=None,
                    days_to_exact=None,
                    detail={
                        "kinds": sorted({item.kind.value for item in mutual}),
                        "note": (
                            "Mutual reception can bring the matter about even "
                            "without a perfecting aspect."
                        ),
                    },
                )
            )

        factors.extend(
            self._translation_and_collection(chart, querent, quesited, moment)
        )
        return factors

    def _translation_and_collection(
        self,
        chart: Chart,
        querent: Significator,
        quesited: Significator,
        moment: datetime,
    ) -> list[PerfectionFactor]:
        """Translation and collection of light.

        *Translation*: a faster planet separating from one significator and
        applying to the other carries the light between them.
        *Collection*: a slower planet to which both significators apply
        gathers their light.
        """
        factors: list[PerfectionFactor] = []
        if querent.planet is quesited.planet:
            return factors

        for planet in CLASSICAL_PLANETS:
            if planet in (querent.planet, quesited.planet):
                continue
            position = chart.position(planet)
            if position is None:
                continue

            to_querent = self._relation(position, querent, moment)
            to_quesited = self._relation(position, quesited, moment)
            if to_querent is None or to_quesited is None:
                continue

            faster_than_both = abs(position.speed_longitude) > max(
                abs(querent.speed), abs(quesited.speed)
            )
            slower_than_both = abs(position.speed_longitude) < min(
                abs(querent.speed), abs(quesited.speed)
            )

            separating, applying_to = to_querent, to_quesited
            if to_querent[0] and not to_quesited[0]:
                separating, applying_to = to_quesited, to_querent

            if (
                faster_than_both
                and not separating[0]
                and applying_to[0]
            ):
                # separating[0] False means it is separating from that body.
                factors.append(
                    PerfectionFactor(
                        id=_factor_id("perfection", "translation", planet.value,
                                      moment.isoformat()),
                        kind=PerfectionKind.TRANSLATION,
                        planets=[planet, querent.planet, quesited.planet],
                        aspect=applying_to[1],
                        exact_at=applying_to[2],
                        days_to_exact=(
                            (applying_to[2] - moment).total_seconds() / 86400
                            if applying_to[2]
                            else None
                        ),
                        detail={
                            "translator": planet.value,
                            "separating_from": (
                                querent.planet.value
                                if separating is to_querent
                                else quesited.planet.value
                            ),
                            "applying_to": (
                                quesited.planet.value
                                if applying_to is to_quesited
                                else querent.planet.value
                            ),
                        },
                    )
                )

            if slower_than_both and to_querent[0] and to_quesited[0]:
                factors.append(
                    PerfectionFactor(
                        id=_factor_id("perfection", "collection", planet.value,
                                      moment.isoformat()),
                        kind=PerfectionKind.COLLECTION,
                        planets=[planet, querent.planet, quesited.planet],
                        aspect=None,
                        exact_at=None,
                        days_to_exact=None,
                        detail={
                            "collector": planet.value,
                            "note": (
                                "Both significators apply to a slower planet, "
                                "which collects their light."
                            ),
                        },
                    )
                )

        return factors

    def _relation(
        self, position, significator: Significator, moment: datetime
    ) -> tuple[bool, AspectType, datetime | None] | None:
        """Is ``position`` applying to the significator, and by which aspect?"""
        max_orb = R.aspect_orb(position.planet.value, significator.planet.value)
        for aspect in R.PERFECTING_ASPECTS:
            orb = abs(
                separation(position.longitude, significator.longitude) - aspect.angle
            )
            if orb > max_orb:
                continue
            exact_at = self._search_pair(
                position.planet,
                significator.planet,
                aspect,
                moment,
                moment + timedelta(days=R.PERFECTION_SEARCH_DAYS),
            )
            return (exact_at is not None, aspect, exact_at)
        return None

    # ------------------------------------------------ obstruction factors

    def _obstruction_factors(
        self,
        chart: Chart,
        querent: Significator,
        quesited: Significator,
        applying: list[HoraryAspect],
        separating: list[HoraryAspect],
        perfection: list[PerfectionFactor],
        moment: datetime,
    ) -> list[ObstructionFactor]:
        factors: list[ObstructionFactor] = []

        if not perfection:
            factors.append(
                ObstructionFactor(
                    id=_factor_id("obstruction", "no_perfection", moment.isoformat()),
                    kind=ObstructionKind.NO_PERFECTION,
                    planets=[querent.planet, quesited.planet],
                    detail={
                        "note": (
                            "No applying aspect between the significators "
                            "perfects before they change sign, and no "
                            "translation, collection or mutual reception was "
                            "found."
                        )
                    },
                )
            )

        if separating and not applying:
            factors.append(
                ObstructionFactor(
                    id=_factor_id("obstruction", "separating", moment.isoformat()),
                    kind=ObstructionKind.SEPARATING,
                    planets=[querent.planet, quesited.planet],
                    detail={"aspect_ids": [item.id for item in separating]},
                )
            )

        for significator in (querent, quesited):
            if (
                significator.accidental is not None
                and significator.accidental.solar_condition.value == "combust"
            ):
                factors.append(
                    ObstructionFactor(
                        id=_factor_id(
                            "obstruction", "combust", significator.planet.value
                        ),
                        kind=ObstructionKind.COMBUSTION,
                        planets=[significator.planet],
                        detail={
                            "role": significator.role,
                            "distance_from_sun": (
                                significator.accidental.solar_distance
                            ),
                        },
                    )
                )

        factors.extend(
            self._prohibition_and_refranation(
                chart, querent, quesited, applying, moment
            )
        )
        return factors

    def _prohibition_and_refranation(
        self,
        chart: Chart,
        querent: Significator,
        quesited: Significator,
        applying: list[HoraryAspect],
        moment: datetime,
    ) -> list[ObstructionFactor]:
        """Prohibition and refranation, narrowly defined.

        *Prohibition*: a third planet perfects with one of the significators
        **before** the significators perfect with each other.
        *Refranation*: the applying significator turns retrograde (or the
        other one does) before the aspect perfects.

        Frustration, besiegement and abscission are **not** implemented - the
        definitions vary between authors and a wrong claim is worse than an
        honest gap. They are listed in ``not_implemented``.
        """
        factors: list[ObstructionFactor] = []
        perfecting = [
            item
            for item in applying
            if item.exact_at is not None and item.perfects_before_sign_change
        ]
        if not perfecting:
            return factors

        first_perfection = min(item.exact_at for item in perfecting)

        for planet in CLASSICAL_PLANETS:
            if planet in (querent.planet, quesited.planet):
                continue
            position = chart.position(planet)
            if position is None:
                continue
            for significator in (querent, quesited):
                relation = self._relation(position, significator, moment)
                if relation is None or not relation[0] or relation[2] is None:
                    continue
                if relation[2] < first_perfection:
                    factors.append(
                        ObstructionFactor(
                            id=_factor_id(
                                "obstruction", "prohibition", planet.value,
                                significator.planet.value, moment.isoformat(),
                            ),
                            kind=ObstructionKind.PROHIBITION,
                            planets=[planet, significator.planet],
                            detail={
                                "prohibitor": planet.value,
                                "blocks": significator.role,
                                "aspect": relation[1].value,
                                "exact_at": relation[2].isoformat(),
                                "before_perfection_at": first_perfection.isoformat(),
                            },
                        )
                    )

        # Refranation: does either significator station before perfection?
        for significator in (querent, quesited):
            station = self._station_before(
                significator.planet, significator.speed, moment, first_perfection
            )
            if station is not None:
                factors.append(
                    ObstructionFactor(
                        id=_factor_id(
                            "obstruction", "refranation", significator.planet.value,
                            moment.isoformat(),
                        ),
                        kind=ObstructionKind.REFRANATION,
                        planets=[significator.planet],
                        detail={
                            "role": significator.role,
                            "station_at": station.isoformat(),
                            "before_perfection_at": first_perfection.isoformat(),
                        },
                    )
                )
        return factors

    def _station_before(
        self, planet: Planet, speed: float, start: datetime, limit: datetime
    ) -> datetime | None:
        if planet is Planet.MOON or limit <= start:
            return None
        steps = max(int((limit - start).total_seconds() // 86400), 1)
        times = [start + timedelta(days=index) for index in range(steps + 1)]
        speeds = self._sampler.speeds_at(planet, times)
        for index in range(len(speeds) - 1):
            if speeds[index] * speeds[index + 1] < 0:
                return times[index + 1]
        return None

    # ------------------------------------------------------- dignities

    def _dignity_factors(
        self,
        querent: Significator,
        quesited: Significator,
        co_significator: Significator | None,
    ) -> list[DignityFactor]:
        factors: list[DignityFactor] = []
        for significator in (querent, quesited, co_significator):
            if significator is None or significator.essential is None:
                continue
            essential = significator.essential
            factors.append(
                DignityFactor(
                    id=_factor_id(
                        "dignity", significator.role, significator.planet.value
                    ),
                    planet=significator.planet,
                    role=significator.role,
                    kinds=essential.dignities + essential.debilities,
                    score=essential.score,
                    detail={
                        "sign": essential.sign.value,
                        "degree": essential.degree,
                        "peregrine": essential.peregrine,
                        "triplicity_ruler": essential.triplicity_ruler.value
                        if essential.triplicity_ruler
                        else None,
                        "term_ruler": essential.term_ruler.value
                        if essential.term_ruler
                        else None,
                        "face_ruler": essential.face_ruler.value
                        if essential.face_ruler
                        else None,
                        "house": significator.in_house,
                        "placement": (
                            significator.accidental.placement.value
                            if significator.accidental
                            and significator.accidental.placement
                            else None
                        ),
                        "solar_condition": (
                            significator.accidental.solar_condition.value
                            if significator.accidental
                            else None
                        ),
                        "motion": (
                            significator.accidental.motion.value
                            if significator.accidental
                            else None
                        ),
                    },
                )
            )
        return factors

    # -------------------------------------------------------- warnings

    def _warnings(
        self,
        chart: Chart,
        querent: Significator,
        quesited: Significator,
        moon: MoonCondition,
        duplicate_suspected: bool,
    ) -> list[HoraryWarning]:
        """Lilly's considerations before judgement - reported, never enforced."""
        warnings: list[HoraryWarning] = []
        ascendant_degree = chart.angles.ascendant % 30

        def add(code: str, **detail) -> None:
            warnings.append(
                HoraryWarning(
                    code=code, message=R.RADICALITY_NOTES[code], detail=detail
                )
            )

        if ascendant_degree < R.EARLY_ASCENDANT_DEGREES:
            add("early_ascendant", ascendant_degree=round(ascendant_degree, 3))
        if ascendant_degree > R.LATE_ASCENDANT_DEGREES:
            add("late_ascendant", ascendant_degree=round(ascendant_degree, 3))

        saturn = chart.position(Planet.SATURN)
        if saturn is not None and saturn.house == 7:
            add("saturn_in_seventh", house=7)

        if moon.void_of_course:
            add("void_of_course_moon", definition=moon.void_definition)
        if moon.in_via_combusta:
            add("moon_via_combusta", degree=moon.degree, sign=moon.sign.value)

        for significator in (querent, quesited):
            if (
                significator.accidental is not None
                and significator.accidental.solar_condition.value == "combust"
            ):
                add(
                    "significator_combust",
                    role=significator.role,
                    planet=significator.planet.value,
                )

        if querent.planet is quesited.planet:
            add("significators_identical", planet=querent.planet.value)

        if duplicate_suspected:
            add("question_repeat_suspected", window_hours=R.DUPLICATE_QUESTION_HOURS)

        return warnings


def _phase_name(elongation: float) -> str:
    if elongation < 90:
        return "waxing_crescent" if elongation > 11.25 else "new_moon"
    if elongation < 180:
        return "waxing_gibbous" if elongation > 101.25 else "first_quarter"
    if elongation < 270:
        return "waning_gibbous" if elongation > 191.25 else "full_moon"
    return "waning_crescent" if elongation > 281.25 else "last_quarter"


def _sign_search_days(planet: Planet) -> int:
    return {
        Planet.MOON: 3,
        Planet.SUN: 35,
        Planet.MERCURY: 60,
        Planet.VENUS: 60,
        Planet.MARS: 120,
    }.get(planet, 400)


_engine: HoraryAnalysisEngine | None = None


def get_horary_engine() -> HoraryAnalysisEngine:
    global _engine
    if _engine is None:
        _engine = HoraryAnalysisEngine()
    return _engine
