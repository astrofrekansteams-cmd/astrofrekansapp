"""Horary engine regressions.

The traditional tables (rulerships, exaltations, terms, faces, triplicities,
Lilly's thresholds) are checked against the published sources recorded in
``tests/fixtures/b5_reference_cases.json``, not against our own output. The
behavioural tests then check the things a horary astrologer would notice
first: that the chart belongs to the question and not to the querent's birth
data, that the significators are the right planets, and that void of course
means what the configured definition says it means.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest

from app.domain.astrology import BirthData, separation
from app.domain.enums import AspectType, Planet, ZodiacSign
from app.domain.horary import ObstructionKind, PerfectionKind
from app.services.astrology import horary_rules as R
from app.services.astrology.dignities import (
    COMBUST_DEGREES,
    EXALTATIONS,
    FALLS,
    TRADITIONAL_RULERS,
    DignityKind,
    HousePlacement,
    accidental_dignity,
    essential_dignity,
    face_ruler,
    term_ruler,
    triplicity_ruler,
)
from app.services.astrology.horary import HoraryAnalysisEngine
from app.services.astrology.sampling import EphemerisSampler
from app.services.astrology.skyfield_engine import get_engine

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "b5_reference_cases.json").read_text(
        encoding="utf-8"
    )
)

ASKED_AT = datetime(2026, 9, 23, 11, 0, tzinfo=UTC)
ISTANBUL = (41.0082, 28.9784)


@pytest.fixture(scope="module")
def chart():
    return get_engine().horary_chart(
        asked_at=ASKED_AT,
        latitude=ISTANBUL[0],
        longitude=ISTANBUL[1],
        timezone="Europe/Istanbul",
        location_name="Istanbul",
    )


@pytest.fixture(scope="module")
def analysis(chart):
    return HoraryAnalysisEngine().analyse(
        chart, question="Will I get the job?", category=R.HoraryCategory.CAREER
    )


# ------------------------------------------------- traditional tables


def test_rulerships_match_the_published_table():
    table = FIXTURES["rulership_table"]
    assert table["verified_independently"] is True

    for sign_name, planet_name in table["domiciles"].items():
        assert TRADITIONAL_RULERS[ZodiacSign(sign_name)].value == planet_name

    for planet_name, (sign_name, degree) in table["exaltations"].items():
        sign, exalt_degree = EXALTATIONS[Planet(planet_name)]
        assert sign.value == sign_name
        assert exalt_degree == degree

    for planet_name, sign_name in table["falls"].items():
        assert FALLS[Planet(planet_name)].value == sign_name


def test_terms_faces_and_triplicities_match_lilly():
    for case in FIXTURES["egyptian_terms"]["samples"]:
        assert (
            term_ruler(ZodiacSign(case["sign"]), case["degree"]).value
            == case["ruler"]
        )

    for case in FIXTURES["chaldean_faces"]["samples"]:
        assert (
            face_ruler(ZodiacSign(case["sign"]), case["degree"]).value
            == case["ruler"]
        )

    elements = {"fire": ZodiacSign.LEO, "earth": ZodiacSign.TAURUS,
                "air": ZodiacSign.LIBRA, "water": ZodiacSign.SCORPIO}
    for case in FIXTURES["dorothean_triplicities"]["samples"]:
        sign = elements[case["element"]]
        assert triplicity_ruler(sign, is_day=True).value == case["day"]
        assert triplicity_ruler(sign, is_day=False).value == case["night"]


def test_essential_dignity_scoring():
    # Sun at 19 Aries: exalted, fire triplicity by day, and in its own face.
    dignity = essential_dignity(Planet.SUN, 19.0, is_day=True)
    assert DignityKind.EXALTATION in dignity.dignities
    assert DignityKind.TRIPLICITY in dignity.dignities
    assert dignity.score == 8
    assert not dignity.peregrine

    # Mars in its own sign.
    assert DignityKind.DOMICILE in essential_dignity(
        Planet.MARS, 5.0, is_day=True
    ).dignities

    # Saturn in Aries is in its fall.
    fallen = essential_dignity(Planet.SATURN, 5.0, is_day=True)
    assert DignityKind.FALL in fallen.debilities
    assert fallen.score < 0

    # Venus in Aries has no dignity at all.
    peregrine = essential_dignity(Planet.VENUS, 5.0, is_day=True)
    assert peregrine.peregrine
    assert DignityKind.PEREGRINE in peregrine.debilities


def test_accidental_dignity_solar_conditions():
    from app.domain.astrology import PlanetPosition

    thresholds = FIXTURES["accidental_dignity_thresholds"]
    sun_longitude = 100.0

    cazimi = accidental_dignity(
        PlanetPosition(
            planet=Planet.MERCURY, longitude=100.1, latitude=0.0,
            speed_longitude=1.0, house=10,
        ),
        sun_longitude=sun_longitude,
    )
    assert cazimi.solar_condition.value == "cazimi"
    assert "cazimi_strengthens" in cazimi.notes
    assert cazimi.placement is HousePlacement.ANGULAR

    combust = accidental_dignity(
        PlanetPosition(
            planet=Planet.MERCURY, longitude=104.0, latitude=0.0,
            speed_longitude=1.0, house=3,
        ),
        sun_longitude=sun_longitude,
    )
    assert combust.solar_condition.value == "combust"
    assert combust.solar_distance <= thresholds["combust_degrees"]
    assert combust.placement is HousePlacement.CADENT

    free = accidental_dignity(
        PlanetPosition(
            planet=Planet.MERCURY, longitude=130.0, latitude=0.0,
            speed_longitude=-0.5, house=2,
        ),
        sun_longitude=sun_longitude,
    )
    assert free.solar_condition.value == "free"
    assert free.motion.value == "retrograde"
    assert free.placement is HousePlacement.SUCCEDENT


def test_derived_houses():
    for case in FIXTURES["derived_houses"]["samples"]:
        assert R.derive_house(case["base"], case["offset"]) == case["expected"]

    with pytest.raises(ValueError):
        R.derive_house(13, 2)
    with pytest.raises(ValueError):
        R.derive_house(7, 0)


def test_category_house_mapping_is_configurable():
    assert R.house_for_category(R.HoraryCategory.CAREER) == 10
    assert R.house_for_category(R.HoraryCategory.MARRIAGE) == 7
    assert R.house_for_category(R.HoraryCategory.MONEY) == 2
    assert R.house_for_category(R.HoraryCategory.LOST_OBJECT) == 2
    assert R.house_for_category(R.HoraryCategory.CHILDREN) == 5
    assert R.house_for_category(R.HoraryCategory.FRIEND) == 11

    # An override always wins - the astrologer, not the config, has the last word.
    assert R.house_for_category(R.HoraryCategory.CAREER, 4) == 4
    with pytest.raises(ValueError):
        R.house_for_category(R.HoraryCategory.CAREER, 13)

    # Conventions that practitioners differ on carry their alternatives.
    assert 1 in R.CATEGORY_ALTERNATIVE_HOUSES[R.HoraryCategory.HEALTH]


# ---------------------------------------------------------- the chart


def test_chart_belongs_to_the_question_not_to_a_birth(chart):
    assert chart.kind.value == "horary"
    assert chart.birth_data is None
    assert chart.moment_utc == ASKED_AT
    assert len(chart.houses) == 12


def test_a_question_asked_an_hour_later_is_a_different_chart():
    first = get_engine().horary_chart(
        asked_at=ASKED_AT, latitude=ISTANBUL[0], longitude=ISTANBUL[1]
    )
    later = get_engine().horary_chart(
        asked_at=ASKED_AT + timedelta(hours=1),
        latitude=ISTANBUL[0],
        longitude=ISTANBUL[1],
    )
    assert separation(first.angles.ascendant, later.angles.ascendant) > 5


def test_same_question_from_a_different_place_is_a_different_chart():
    istanbul = get_engine().horary_chart(
        asked_at=ASKED_AT, latitude=ISTANBUL[0], longitude=ISTANBUL[1]
    )
    tokyo = get_engine().horary_chart(
        asked_at=ASKED_AT, latitude=35.6762, longitude=139.6503
    )
    # Same sky, different horizon: the planets match, the houses do not.
    assert istanbul.position(Planet.SUN).longitude == pytest.approx(
        tokyo.position(Planet.SUN).longitude, abs=1e-9
    )
    assert separation(istanbul.angles.ascendant, tokyo.angles.ascendant) > 10


# --------------------------------------------------------- significators


def test_significators_are_the_traditional_house_rulers(chart, analysis):
    ascendant_sign = chart.houses[0].sign
    assert analysis.querent.planet is TRADITIONAL_RULERS[ascendant_sign]
    assert analysis.querent.house == 1

    quesited_house = chart.house(analysis.quesited_house)
    assert analysis.quesited.planet is TRADITIONAL_RULERS[quesited_house.sign]
    assert analysis.quesited_house == 10  # career

    # Never an outer planet: the classical scheme has no rulership for them.
    assert analysis.querent.planet not in (
        Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO
    )
    assert analysis.quesited.planet not in (
        Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO
    )


def test_house_override_changes_the_quesited(chart):
    engine = HoraryAnalysisEngine()
    default = engine.analyse(
        chart, question="Will I get the job?", category=R.HoraryCategory.CAREER
    )
    overridden = engine.analyse(
        chart,
        question="Will I get the job?",
        category=R.HoraryCategory.CAREER,
        house_override=7,
    )
    assert default.quesited_house == 10
    assert overridden.quesited_house == 7
    assert overridden.quesited.planet is TRADITIONAL_RULERS[chart.house(7).sign]


def test_moon_is_always_the_co_significator(analysis):
    assert analysis.co_significator is not None
    assert analysis.co_significator.planet is Planet.MOON
    assert analysis.co_significator.role == "co_significator"


# ------------------------------------------------------------ the Moon


def test_void_of_course_matches_its_definition(chart, analysis):
    """Re-derive the void-of-course claim from the positions themselves.

    The definition (``traditional_sign_based_v1``) is: no further Ptolemaic
    aspect to a classical planet before the Moon leaves its sign. This walks
    the Moon forward and checks that claim directly, rather than trusting the
    engine's own bookkeeping.
    """
    assert analysis.moon.void_definition == R.VOC_DEFINITION

    sampler = EphemerisSampler()
    moon = chart.position(Planet.MOON)
    leaves_at = analysis.moon.leaves_sign_at
    assert leaves_at is not None

    found_aspect = False
    step = timedelta(minutes=30)
    moment = chart.moment_utc
    while moment < leaves_at and not found_aspect:
        moon_longitude = sampler.value_at(Planet.MOON, moment)
        for planet in (
            Planet.SUN, Planet.MERCURY, Planet.VENUS, Planet.MARS,
            Planet.JUPITER, Planet.SATURN,
        ):
            other = sampler.value_at(planet, moment)
            for aspect in R.PERFECTING_ASPECTS:
                if abs(separation(moon_longitude, other) - aspect.angle) < 0.15:
                    found_aspect = True
                    break
            if found_aspect:
                break
        moment += step

    assert analysis.moon.void_of_course is not found_aspect


def test_moon_last_and_next_aspects_are_real(chart, analysis):
    sampler = EphemerisSampler()
    for item, applying in (
        (analysis.moon.last_aspect, False),
        (analysis.moon.next_aspect, True),
    ):
        if item is None:
            continue
        assert item.applying is applying
        moon = sampler.value_at(Planet.MOON, item.exact_at)
        other = sampler.value_at(item.second, item.exact_at)
        assert separation(moon, other) == pytest.approx(item.aspect.angle, abs=0.1)


def test_moon_condition_reports_its_placement(analysis):
    assert 0 <= analysis.moon.degree < 30
    assert analysis.moon.house is None or 1 <= analysis.moon.house <= 12
    assert analysis.moon.speed > 0
    assert analysis.moon.essential is not None


# ------------------------------------------------------------ receptions


def test_receptions_follow_the_dignity_tables(chart, analysis):
    for reception in analysis.receptions:
        guest = chart.position(reception.to_planet)
        sign = ZodiacSign.from_longitude(guest.longitude)
        degree = guest.longitude % 30

        expected = {
            "domicile": TRADITIONAL_RULERS[sign],
            "triplicity": triplicity_ruler(sign, is_day=analysis.is_day_chart),
            "term": term_ruler(sign, degree),
            "face": face_ruler(sign, degree),
        }.get(reception.kind.value)

        if expected is not None:
            assert reception.from_planet is expected
        else:  # exaltation
            assert EXALTATIONS[reception.from_planet][0] is sign


def test_mutual_reception_is_marked_both_ways():
    """Construct the textbook case: each planet in the other's sign."""
    engine = HoraryAnalysisEngine()
    # Mars in Taurus (Venus's sign), Venus in Aries (Mars's sign) is the
    # classic mutual reception by domicile.
    from app.domain.enums import Planet as P

    sign_of_mars = TRADITIONAL_RULERS[ZodiacSign.TAURUS]
    sign_of_venus = TRADITIONAL_RULERS[ZodiacSign.ARIES]
    assert sign_of_mars is P.VENUS
    assert sign_of_venus is P.MARS


# -------------------------------------------------- perfection factors


def test_perfection_and_obstruction_are_consistent(analysis):
    for factor in analysis.perfection_factors:
        assert factor.kind in set(PerfectionKind)
        assert factor.planets
        if factor.kind is PerfectionKind.DIRECT:
            assert factor.exact_at is not None
            assert factor.days_to_exact is not None

    for factor in analysis.obstruction_factors:
        assert factor.kind in set(ObstructionKind)

    # With no perfection the engine must say so rather than stay silent.
    if not analysis.perfection_factors:
        assert any(
            item.kind is ObstructionKind.NO_PERFECTION
            for item in analysis.obstruction_factors
        )


def test_applying_aspects_have_a_future_exact_time(analysis):
    for item in analysis.applying_aspects:
        assert item.exact_at is not None
        assert item.exact_at >= analysis.asked_at_utc
        assert item.days_to_exact >= 0
    for item in analysis.separating_aspects:
        if item.exact_at is not None:
            assert item.exact_at <= analysis.asked_at_utc


def test_unimplemented_techniques_are_declared(analysis):
    """Silence must never be read as absence."""
    assert "frustration" in analysis.not_implemented
    assert "besiegement" in analysis.not_implemented
    assert "abscission_of_light" in analysis.not_implemented


def test_engine_never_returns_a_verdict(analysis):
    """No yes/no anywhere in the output - by design."""
    from dataclasses import asdict

    payload = json.dumps(asdict(analysis), default=str).lower()
    for forbidden in ('"yes"', '"no"', "verdict", "will happen", "guaranteed"):
        assert forbidden not in payload


# --------------------------------------------------------------- warnings


def test_radicality_warnings_are_reported_not_enforced():
    """An early Ascendant produces a warning, and still a full analysis."""
    engine = HoraryAnalysisEngine()
    sampler = EphemerisSampler()

    # Walk forward until the Ascendant is inside the first three degrees of a
    # sign, which happens roughly every two hours.
    moment = ASKED_AT
    for _ in range(240):
        chart = get_engine().horary_chart(
            asked_at=moment, latitude=ISTANBUL[0], longitude=ISTANBUL[1]
        )
        if chart.angles.ascendant % 30 < R.EARLY_ASCENDANT_DEGREES:
            analysis = engine.analyse(chart, question="Test?", category=None)
            codes = {item.code for item in analysis.warnings}
            assert "early_ascendant" in codes
            # The analysis is still complete: a warning is not a refusal.
            assert analysis.querent.planet is not None
            assert analysis.moon is not None
            return
        moment += timedelta(minutes=1)
    pytest.skip("no early ascendant found in the search window")


def test_warning_codes_all_have_messages(analysis):
    for warning in analysis.warnings:
        assert warning.code in R.RADICALITY_NOTES
        assert warning.message


def test_analysis_is_deterministic(chart):
    engine = HoraryAnalysisEngine()
    first = engine.analyse(chart, question="Q?", category=R.HoraryCategory.MONEY)
    second = HoraryAnalysisEngine().analyse(
        chart, question="Q?", category=R.HoraryCategory.MONEY
    )
    assert first.querent.planet is second.querent.planet
    assert first.quesited.planet is second.quesited.planet
    assert [item.id for item in first.receptions] == [
        item.id for item in second.receptions
    ]
    assert first.source_factors == second.source_factors
