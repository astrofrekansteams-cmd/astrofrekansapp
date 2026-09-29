"""Regression tests for the astrology engine.

Two kinds of assertions:

* **Known dates** - published astronomical events (equinoxes, solstices, the
  1993 Uranus-Neptune conjunction). External ground truth, not fixtures
  generated from our own code.
* **Physics invariants** - synodic month length, retrograde frequency, speed
  ranges. These catch a class of silent errors a single date cannot.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.domain.astrology import BirthData, separation
from app.domain.enums import HouseSystem, Planet, ZodiacSign
from app.services.astrology.houses import compute_angles, compute_houses, house_of
from app.services.astrology.skyfield_engine import get_engine


@pytest.fixture(scope="module")
def engine():
    return get_engine()


def _sun(engine, moment: datetime) -> float:
    return engine.positions(moment, bodies=(Planet.SUN,))[0].longitude


# --------------------------------------------------------------- known dates

KNOWN_SUN_EVENTS = [
    ("2026-03-20T14:46:00+00:00", 0.0),  # March equinox 2026
    ("2026-06-21T08:25:00+00:00", 90.0),  # June solstice 2026
    ("2025-12-21T15:03:00+00:00", 270.0),  # December solstice 2025
]


@pytest.mark.parametrize(("moment", "expected"), KNOWN_SUN_EVENTS)
def test_sun_longitude_matches_published_events(engine, moment: str, expected: float):
    longitude = _sun(engine, datetime.fromisoformat(moment))
    # Published times are given to the minute; the Sun moves 0.041 deg/hour.
    assert separation(longitude, expected) < 0.02


def test_sun_sign_boundaries(engine):
    equinox = datetime(2026, 3, 20, 14, 46, tzinfo=UTC)
    assert (
        engine.positions(equinox + timedelta(days=1), bodies=(Planet.SUN,))[0].sign
        is ZodiacSign.ARIES
    )
    assert (
        engine.positions(equinox + timedelta(days=188), bodies=(Planet.SUN,))[0].sign
        is ZodiacSign.LIBRA
    )


def test_uranus_neptune_conjunction_of_1993(engine):
    """A documented outer-planet event: Uranus met Neptune in 1993."""
    positions = {
        item.planet: item
        for item in engine.positions(
            datetime(1993, 2, 2, 12, tzinfo=UTC),
            bodies=(Planet.URANUS, Planet.NEPTUNE),
        )
    }
    gap = separation(
        positions[Planet.URANUS].longitude, positions[Planet.NEPTUNE].longitude
    )
    assert gap < 1.0


# --------------------------------------------------------- physics invariants


def test_moon_speed_is_within_real_bounds(engine):
    for day in range(0, 30, 3):
        moon = engine.positions(
            datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day),
            bodies=(Planet.MOON,),
        )[0]
        assert 11.0 < moon.speed_longitude < 15.5
        assert not moon.retrograde


def test_synodic_month_between_consecutive_new_moons(engine):
    first = engine.next_phase_moment(datetime(2026, 1, 1, tzinfo=UTC), 0.0)
    second = engine.next_phase_moment(first + timedelta(days=2), 0.0)
    length = (second - first).total_seconds() / 86400
    assert 29.2 < length < 29.9  # true synodic month: 29.53 days


def test_new_and_full_moon_geometry(engine):
    new_moon = engine.next_phase_moment(datetime(2026, 5, 1, tzinfo=UTC), 0.0)
    full_moon = engine.next_phase_moment(datetime(2026, 5, 1, tzinfo=UTC), 180.0)

    assert separation(engine.elongation(new_moon), 0.0) < 0.05
    assert separation(engine.elongation(full_moon), 180.0) < 0.05
    assert engine.moon_phase(new_moon).illumination < 0.01
    assert engine.moon_phase(full_moon).illumination > 0.99


def test_moon_phase_reports_next_phase(engine):
    phase = engine.moon_phase(datetime(2026, 4, 10, 12, tzinfo=UTC))
    assert phase.next_phase is not None
    assert phase.next_phase_at > phase.moment
    assert (phase.next_phase_at - phase.moment) < timedelta(days=8)
    assert 0.0 <= phase.illumination <= 1.0
    assert 0.0 <= phase.age_days <= 29.6


def test_mercury_retrograde_frequency(engine):
    """Mercury is retrograde ~19% of the time, in three runs of about 3 weeks."""
    retrograde_days = 0
    runs: list[int] = []
    current = 0
    for offset in range(365):
        moment = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=offset)
        if engine.positions(moment, bodies=(Planet.MERCURY,))[0].retrograde:
            retrograde_days += 1
            current += 1
        elif current:
            runs.append(current)
            current = 0
    if current:
        runs.append(current)

    assert 0.15 < retrograde_days / 365 < 0.23
    assert len(runs) == 3
    assert all(15 <= run <= 27 for run in runs)


def test_sun_and_moon_never_retrograde(engine):
    positions = engine.positions(
        datetime(2026, 7, 4, tzinfo=UTC), bodies=(Planet.SUN, Planet.MOON)
    )
    assert all(not position.retrograde for position in positions)


def test_lunar_nodes_are_opposite_and_retrograde(engine):
    moment = datetime(2026, 2, 2, tzinfo=UTC)
    north, south = engine.positions(
        moment, bodies=(Planet.NORTH_NODE, Planet.SOUTH_NODE)
    )
    assert separation(north.longitude, south.longitude) == pytest.approx(180, abs=1e-6)
    assert north.retrograde and south.retrograde


# ----------------------------------------------------------------- the chart


@pytest.fixture
def istanbul_birth() -> BirthData:
    return BirthData(
        birth_date=date(1992, 5, 14),
        birth_time=time(14, 30),
        timezone="Europe/Istanbul",
        latitude=41.0082,
        longitude=28.9784,
        place="Istanbul, TR",
        house_system=HouseSystem.PLACIDUS,
    )


def test_natal_chart_structure(engine, istanbul_birth: BirthData):
    chart = engine.natal_chart(istanbul_birth)

    assert len(chart.positions) == 12
    assert len(chart.houses) == 12
    assert chart.angles is not None
    assert chart.house_system is HouseSystem.PLACIDUS
    assert chart.sun.sign is ZodiacSign.TAURUS  # mid-May
    assert all(position.house is not None for position in chart.positions)
    assert sum(chart.element_distribution.values()) == 10  # nodes excluded


def test_chart_angles_are_consistent(engine, istanbul_birth: BirthData):
    chart = engine.natal_chart(istanbul_birth)
    angles = chart.angles

    assert separation(angles.descendant, angles.ascendant) == pytest.approx(
        180, abs=1e-6
    )
    assert separation(angles.imum_coeli, angles.midheaven) == pytest.approx(
        180, abs=1e-6
    )
    assert chart.houses[0].cusp_longitude == pytest.approx(angles.ascendant, abs=1e-9)
    assert chart.houses[9].cusp_longitude == pytest.approx(angles.midheaven, abs=1e-9)


def test_houses_cover_the_whole_circle(engine, istanbul_birth: BirthData):
    chart = engine.natal_chart(istanbul_birth)
    spans = []
    for index, house in enumerate(chart.houses):
        following = chart.houses[(index + 1) % 12]
        spans.append((following.cusp_longitude - house.cusp_longitude) % 360)
    assert sum(spans) == pytest.approx(360.0, abs=1e-6)
    assert all(span > 0 for span in spans)

    for number in range(1, 7):
        assert separation(
            chart.houses[number - 1].cusp_longitude,
            chart.houses[number + 5].cusp_longitude,
        ) == pytest.approx(180, abs=1e-6)


def test_aspects_are_within_their_orbs(engine, istanbul_birth: BirthData):
    chart = engine.natal_chart(istanbul_birth)
    assert chart.aspects
    for hit in chart.aspects:
        gap = separation(
            chart.position(hit.first).longitude, chart.position(hit.second).longitude
        )
        assert abs(gap - hit.aspect.angle) == pytest.approx(hit.orb, abs=1e-3)
        assert hit.orb <= 10.0
        assert hit.first is not hit.second


def test_dominants_are_deterministic(engine, istanbul_birth: BirthData):
    first = engine.natal_chart(istanbul_birth)
    second = engine.natal_chart(istanbul_birth)
    assert first.dominant_planet == second.dominant_planet
    assert first.dominant_element == second.dominant_element
    assert first.dominant_modality == second.dominant_modality
    assert sum(first.modality_distribution.values()) == 10


def test_ascendant_at_the_equator_is_zero_cancer():
    """RAMC 0 at latitude 0 puts 0 Cancer on the horizon - a textbook case."""
    angles = compute_angles(0.0, 0.0)
    assert angles.midheaven == pytest.approx(0.0, abs=1e-9)
    assert angles.ascendant == pytest.approx(90.0, abs=1e-9)


def test_placidus_trisection_at_the_equator():
    angles = compute_angles(0.0, 0.0)
    houses, system = compute_houses(
        system=HouseSystem.PLACIDUS, ramc_degrees=0.0, latitude=0.0, angles=angles
    )
    assert system is HouseSystem.PLACIDUS
    # Semi-arcs are all 90 degrees at the equator, so the cusps are the
    # ecliptic points whose right ascensions are 30 and 60 degrees.
    assert separation(houses[10].cusp_longitude, 32.2) < 1.0
    assert separation(houses[11].cusp_longitude, 62.1) < 1.0


def test_placidus_is_unequal_at_high_latitude():
    angles = compute_angles(0.0, 55.0)
    houses, _ = compute_houses(
        system=HouseSystem.PLACIDUS, ramc_degrees=0.0, latitude=55.0, angles=angles
    )
    spans = [
        (houses[(index + 1) % 12].cusp_longitude - house.cusp_longitude) % 360
        for index, house in enumerate(houses)
    ]
    # Placidus houses are markedly unequal away from the equator.
    assert max(spans) - min(spans) > 15.0


def test_placidus_falls_back_inside_the_polar_circle():
    angles = compute_angles(120.0, 70.0)
    _, system = compute_houses(
        system=HouseSystem.PLACIDUS, ramc_degrees=120.0, latitude=70.0, angles=angles
    )
    assert system is HouseSystem.WHOLE_SIGN


def test_whole_sign_and_equal_houses():
    angles = compute_angles(0.0, 41.0)
    whole, _ = compute_houses(
        system=HouseSystem.WHOLE_SIGN, ramc_degrees=0.0, latitude=41.0, angles=angles
    )
    equal, _ = compute_houses(
        system=HouseSystem.EQUAL, ramc_degrees=0.0, latitude=41.0, angles=angles
    )
    assert whole[0].cusp_longitude % 30 == pytest.approx(0.0, abs=1e-9)
    assert equal[0].cusp_longitude == pytest.approx(angles.ascendant, abs=1e-9)
    assert equal[6].cusp_longitude == pytest.approx(angles.descendant, abs=1e-6)


def test_house_lookup_handles_wrap_around():
    angles = compute_angles(0.0, 41.0)
    houses, _ = compute_houses(
        system=HouseSystem.PLACIDUS, ramc_degrees=0.0, latitude=41.0, angles=angles
    )
    for house in houses:
        assert house_of((house.cusp_longitude + 0.001) % 360, houses) == house.number


def test_chart_without_birth_time_has_no_houses(engine):
    birth = BirthData(
        birth_date=date(1992, 5, 14),
        birth_time=None,
        timezone="Europe/Istanbul",
        latitude=41.0082,
        longitude=28.9784,
    )
    chart = engine.natal_chart(birth)
    assert chart.houses == []
    assert chart.angles is None
    assert chart.sun is not None  # planets are still available


def test_engine_rejects_naive_datetimes(engine):
    from app.core.exceptions import AstrologyError

    with pytest.raises(AstrologyError):
        engine.positions(datetime(2026, 1, 1, 12))  # noqa: DTZ001 - that is the point
