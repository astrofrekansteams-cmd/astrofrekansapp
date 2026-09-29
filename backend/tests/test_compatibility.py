"""Synastry, composite and Davison regressions, plus the compatibility API.

The midpoint maths is checked against arithmetic anyone can redo by hand (the
fixtures carry the cases); the synastry geometry against fixed longitudes
whose aspect is determined by the numbers alone, not by our engine.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import httpx
import pytest

from app.domain.astrology import BirthData, separation
from app.domain.compatibility import Direction, RelationshipTheme
from app.domain.enums import AspectType, ChartKind, HouseSystem, Planet
from app.services.astrology.composite import (
    CompositeEngine,
    circular_midpoint,
    geographic_midpoint,
    utc_midpoint,
)
from app.services.astrology.skyfield_engine import get_engine
from app.services.astrology.synastry import SynastryEngine, orb_limit

API = "/api/v1"

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "b5_reference_cases.json").read_text(
        encoding="utf-8"
    )
)


def _chart(case_id: str):
    case = next(item for item in FIXTURES["charts"] if item["id"] == case_id)
    data = case["input"]
    return get_engine().natal_chart(
        BirthData(
            birth_date=date.fromisoformat(data["birth_date"]),
            birth_time=time.fromisoformat(data["birth_time"]),
            timezone=data["timezone"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            house_system=HouseSystem(data["house_system"]),
        )
    )


@pytest.fixture(scope="module")
def chart_a():
    return _chart("person_a_istanbul_1992")


@pytest.fixture(scope="module")
def chart_b():
    return _chart("person_b_london_1994")


@pytest.fixture(scope="module")
def synastry(chart_a, chart_b):
    return SynastryEngine().analyse(chart_a, chart_b)


# ------------------------------------------------------ circular midpoints


def test_circular_midpoints_match_hand_arithmetic():
    for case in FIXTURES["circular_midpoints"]["samples"]:
        midpoint, ambiguous = circular_midpoint(case["a"], case["b"])
        assert midpoint == pytest.approx(case["expected"], abs=1e-6), case
        assert ambiguous is bool(case.get("ambiguous", False))


def test_the_wrap_around_trap():
    """359 and 1 degree meet at 0, not at 180."""
    midpoint, _ = circular_midpoint(359.0, 1.0)
    assert midpoint == pytest.approx(0.0, abs=1e-9)
    assert midpoint != pytest.approx(180.0, abs=1.0)

    # And the order of the arguments does not matter.
    reversed_midpoint, _ = circular_midpoint(1.0, 359.0)
    assert reversed_midpoint == pytest.approx(0.0, abs=1e-9)


def test_exact_opposition_is_flagged_and_deterministic():
    first, ambiguous_first = circular_midpoint(0.0, 180.0)
    second, ambiguous_second = circular_midpoint(0.0, 180.0)
    assert ambiguous_first and ambiguous_second
    assert first == second  # deterministic, not random


# ---------------------------------------------------- geographic midpoints


def test_geographic_midpoints_match_the_sphere():
    for case in FIXTURES["geographic_midpoints"]["samples"]:
        latitude, longitude, degenerate = geographic_midpoint(
            case["a"][0], case["a"][1], case["b"][0], case["b"][1]
        )
        if case.get("degenerate"):
            assert degenerate is True
            continue
        assert degenerate is False
        assert latitude == pytest.approx(case["expected"][0], abs=case["tolerance"])
        assert abs(longitude) == pytest.approx(
            abs(case["expected"][1]), abs=case["tolerance"]
        )


def test_date_line_is_not_averaged_naively():
    """179E and 179W meet on the date line, not in Africa."""
    _, longitude, _ = geographic_midpoint(0.0, 179.0, 0.0, -179.0)
    assert abs(abs(longitude) - 180.0) < 0.01
    assert abs(longitude) > 170  # a naive average would give 0


def test_northern_and_southern_hemispheres():
    latitude, longitude, _ = geographic_midpoint(60.0, 10.0, -40.0, 10.0)
    assert -40.0 < latitude < 60.0
    assert longitude == pytest.approx(10.0, abs=1e-6)


# ---------------------------------------------------------- utc midpoints


def test_utc_midpoints_including_dst():
    for case in FIXTURES["utc_midpoints"]["samples"]:
        result = utc_midpoint(
            datetime.fromisoformat(case["a"]), datetime.fromisoformat(case["b"])
        )
        assert result == datetime.fromisoformat(case["expected"])


def test_local_times_are_never_averaged():
    """Two local times with different offsets must resolve through UTC."""
    from zoneinfo import ZoneInfo

    istanbul = datetime(1992, 5, 14, 14, 30, tzinfo=ZoneInfo("Europe/Istanbul"))
    london = datetime(1994, 8, 21, 9, 45, tzinfo=ZoneInfo("Europe/London"))
    result = utc_midpoint(istanbul, london)

    naive_average = (
        istanbul.replace(tzinfo=UTC) + (london.replace(tzinfo=UTC) - istanbul.replace(tzinfo=UTC)) / 2
    )
    assert result != naive_average
    assert result.tzinfo is UTC


# --------------------------------------------------------------- synastry


def test_synastry_geometry_from_fixed_longitudes():
    """Aspect and orb follow from the two longitudes alone."""
    engine = SynastryEngine()
    for case in FIXTURES["synastry_geometry"]["samples"]:
        hit = engine._match(
            first_longitude=case["a_longitude"],
            second_longitude=case["b_longitude"],
            first_planet=Planet.VENUS,
            second_planet=Planet.MARS,
        )
        if case.get("out_of_orb"):
            assert hit is None, case
            continue
        assert hit is not None, case
        assert hit.aspect.value == case["expected_aspect"]
        assert hit.orb == pytest.approx(case["expected_orb"], abs=1e-6)


def test_aspects_are_symmetric_but_overlays_are_not(chart_a, chart_b):
    engine = SynastryEngine()
    forward = engine.analyse(chart_a, chart_b)
    backward = engine.analyse(chart_b, chart_a)

    # The same pairs are in aspect either way round.
    assert len(forward.aspects) == len(backward.aspects)
    assert forward.overall_score == backward.overall_score

    # Overlays are directional: A's planets in B's houses is a different
    # statement, and swapping the arguments swaps the two lists.
    assert [(item.planet, item.house) for item in forward.overlays_a_in_b] == [
        (item.planet, item.house) for item in backward.overlays_b_in_a
    ]
    assert forward.overlays_a_in_b != forward.overlays_b_in_a


def test_overlay_direction_is_recorded(synastry):
    assert synastry.overlays_a_in_b
    assert all(
        item.direction is Direction.A_TO_B for item in synastry.overlays_a_in_b
    )
    assert all(
        item.direction is Direction.B_TO_A for item in synastry.overlays_b_in_a
    )
    for item in synastry.overlays_a_in_b:
        assert 1 <= item.house <= 12
        assert item.label.startswith("a_")


def test_overlays_place_planets_in_the_right_houses(chart_a, chart_b, synastry):
    from app.services.astrology.houses import house_of

    for overlay in synastry.overlays_a_in_b:
        position = chart_a.position(overlay.planet)
        assert house_of(position.longitude, chart_b.houses) == overlay.house


def test_tighter_orbs_weigh_more():
    engine = SynastryEngine()
    tight = engine._match(
        first_longitude=0.0,
        second_longitude=120.2,
        first_planet=Planet.SUN,
        second_planet=Planet.MOON,
    )
    wide = engine._match(
        first_longitude=0.0,
        second_longitude=125.0,
        first_planet=Planet.SUN,
        second_planet=Planet.MOON,
    )
    assert tight.weight > wide.weight
    assert tight.orb < wide.orb


def test_key_pairs_outweigh_incidental_ones():
    engine = SynastryEngine()
    sun_moon = engine._match(
        first_longitude=0.0, second_longitude=0.5,
        first_planet=Planet.SUN, second_planet=Planet.MOON,
    )
    jupiter_saturn = engine._match(
        first_longitude=0.0, second_longitude=0.5,
        first_planet=Planet.JUPITER, second_planet=Planet.SATURN,
    )
    assert sun_moon.weight > jupiter_saturn.weight

    venus_mars = engine._match(
        first_longitude=0.0, second_longitude=0.5,
        first_planet=Planet.VENUS, second_planet=Planet.MARS,
    )
    assert venus_mars.weight > jupiter_saturn.weight


def test_generational_pairs_are_excluded(chart_a, chart_b, synastry):
    """Pluto square Neptune says something about a generation, not a couple."""
    generational = {Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO}
    for hit in synastry.aspects:
        if hit.person_a_body in generational and hit.person_b_body in generational:
            pytest.fail(f"generational pair reported: {hit.label}")


def test_themes_carry_their_factor_ids(synastry):
    assert {item.theme for item in synastry.themes} == set(RelationshipTheme)
    known = {item.id for item in synastry.aspects} | {
        item.id for item in synastry.overlays_a_in_b + synastry.overlays_b_in_a
    }

    for theme in synastry.themes:
        assert 0 <= theme.score <= 100
        for factor_id in theme.factor_ids:
            assert factor_id in known, "every factor id must resolve"


def test_score_is_deterministic_and_labelled(chart_a, chart_b):
    first = SynastryEngine().analyse(chart_a, chart_b)
    second = SynastryEngine().analyse(chart_a, chart_b)
    assert first.overall_score == second.overall_score
    assert [item.score for item in first.themes] == [
        item.score for item in second.themes
    ]
    # The number must never be presented as a probability.
    assert "index" in first.score_semantics.lower()
    assert "not a probability" in first.score_semantics.lower()


def test_saturn_and_node_contacts_are_scored(chart_a, chart_b, synastry):
    engine = SynastryEngine()
    saturn_moon = engine._match(
        first_longitude=0.0, second_longitude=0.5,
        first_planet=Planet.SATURN, second_planet=Planet.MOON,
    )
    assert RelationshipTheme.LONG_TERM in saturn_moon.themes

    node_venus = engine._match(
        first_longitude=0.0, second_longitude=0.5,
        first_planet=Planet.NORTH_NODE, second_planet=Planet.VENUS,
    )
    assert RelationshipTheme.KARMIC in node_venus.themes


# -------------------------------------------------------------- composite


def test_composite_points_are_midpoints(chart_a, chart_b):
    result = CompositeEngine().composite(chart_a, chart_b)

    for position in result.chart.positions:
        first = chart_a.position(position.planet)
        second = chart_b.position(position.planet)
        expected, _ = circular_midpoint(first.longitude, second.longitude)
        assert position.longitude == pytest.approx(expected, abs=1e-6)

    assert result.method == "midpoint_v1"
    assert result.house_method  # named, never assumed
    assert result.chart.kind is ChartKind.COMPOSITE


def test_composite_aspects_come_from_composite_positions(chart_a, chart_b):
    result = CompositeEngine().composite(chart_a, chart_b)
    longitudes = {
        item.planet.value: item.longitude for item in result.chart.positions
    }

    assert result.aspects
    for aspect in result.aspects:
        gap = separation(longitudes[aspect["first"]], longitudes[aspect["second"]])
        angle = AspectType(aspect["aspect"]).angle
        assert abs(gap - angle) == pytest.approx(aspect["orb"], abs=1e-3)


def test_composite_reports_ambiguity_rather_than_hiding_it():
    """A pair whose Suns are exactly opposite has no unique composite Sun."""
    engine = CompositeEngine()
    base = _chart("person_a_istanbul_1992")

    from dataclasses import replace

    from app.domain.astrology import PlanetPosition

    opposite_positions = [
        replace(item, longitude=(item.longitude + 180.0) % 360)
        for item in base.positions
    ]
    mirrored = replace(base, positions=opposite_positions)

    result = engine.composite(base, mirrored)
    assert result.ambiguous_midpoints
    assert any("ambiguous" in warning for warning in result.warnings)


def test_composite_has_no_speed_fiction(chart_a, chart_b):
    """Composite points are not bodies; they have no motion to report."""
    result = CompositeEngine().composite(chart_a, chart_b)
    assert all(item.speed_longitude == 0.0 for item in result.chart.positions)
    assert all(not item.retrograde for item in result.chart.positions)


# ---------------------------------------------------------------- davison


def test_davison_uses_the_real_midpoint(chart_a, chart_b):
    result = CompositeEngine().davison(chart_a, chart_b)
    expected = FIXTURES["davison_pair"]

    assert result.midpoint_utc == datetime.fromisoformat(
        expected["expected_midpoint_utc"]
    )
    assert result.midpoint_latitude == pytest.approx(
        expected["expected_latitude"], abs=expected["tolerance_degrees"]
    )
    assert result.midpoint_longitude == pytest.approx(
        expected["expected_longitude"], abs=expected["tolerance_degrees"]
    )
    assert result.chart.kind is ChartKind.DAVISON
    assert result.method == "davison_utc_geodesic_v1"


def test_davison_is_a_real_chart(chart_a, chart_b):
    """Unlike a composite, the Davison planets really were there."""
    from app.services.astrology.sampling import EphemerisSampler

    result = CompositeEngine().davison(chart_a, chart_b)
    sampler = EphemerisSampler()

    for planet in (Planet.SUN, Planet.MOON, Planet.MARS):
        position = result.chart.position(planet)
        actual = sampler.value_at(planet, result.midpoint_utc)
        assert separation(position.longitude, actual) < 0.01

    assert len(result.chart.houses) == 12
    assert result.chart.angles is not None


def test_davison_across_the_date_line():
    engine = get_engine()
    tokyo = engine.natal_chart(
        BirthData(
            birth_date=date(1990, 1, 1), birth_time=time(12, 0),
            timezone="Asia/Tokyo", latitude=35.6762, longitude=139.6503,
        )
    )
    hawaii = engine.natal_chart(
        BirthData(
            birth_date=date(1992, 6, 15), birth_time=time(6, 0),
            timezone="Pacific/Honolulu", latitude=21.3069, longitude=-157.8583,
        )
    )
    result = CompositeEngine().davison(tokyo, hawaii)
    # The Pacific midpoint must stay in the Pacific, not jump to Africa.
    assert abs(result.midpoint_longitude) > 100
    assert not result.warnings


def test_davison_flags_antipodal_birthplaces():
    engine = get_engine()
    first = engine.natal_chart(
        BirthData(
            birth_date=date(1990, 1, 1), birth_time=time(12, 0),
            timezone="UTC", latitude=0.0, longitude=0.0,
        )
    )
    second = engine.natal_chart(
        BirthData(
            birth_date=date(1992, 1, 1), birth_time=time(12, 0),
            timezone="UTC", latitude=0.0, longitude=180.0,
        )
    )
    result = CompositeEngine().davison(first, second)
    assert any("antipodal" in warning for warning in result.warnings)


# -------------------------------------------------------------------- API


@pytest.fixture
async def partner_id(client: httpx.AsyncClient, registered) -> str:
    response = await client.post(
        f"{API}/saved-people",
        headers=registered["headers"],
        json={
            "name": "Deniz",
            "relation": "partner",
            "birth_date": "1994-08-21",
            "birth_time": "09:45:00",
            "birth_place": "London",
        },
    )
    return response.json()["id"]


async def test_synastry_endpoint(client: httpx.AsyncClient, registered, partner_id):
    response = await client.post(
        f"{API}/compatibility/synastry",
        headers=registered["headers"],
        json={"person_a": {"me": True}, "person_b": {"saved_person_id": partner_id}},
    )
    assert response.status_code == 200
    body = response.json()

    assert 0 <= body["overall_score"] <= 100
    assert "not a probability" in body["score_semantics"].lower()
    assert len(body["themes"]) == 9
    assert body["overlays_a_in_b"] and body["overlays_b_in_a"]
    assert body["report_id"]
    assert body["cached"] is False

    again = await client.post(
        f"{API}/compatibility/synastry",
        headers=registered["headers"],
        json={"person_a": {"me": True}, "person_b": {"saved_person_id": partner_id}},
    )
    assert again.json()["cached"] is True


async def test_composite_and_davison_endpoints(
    client: httpx.AsyncClient, registered, partner_id
):
    payload = {
        "person_a": {"me": True},
        "person_b": {"saved_person_id": partner_id},
    }

    composite = await client.post(
        f"{API}/compatibility/composite", headers=registered["headers"], json=payload
    )
    assert composite.status_code == 200
    assert composite.json()["method"] == "midpoint_v1"
    assert composite.json()["chart"]["kind"] == "composite"

    davison = await client.post(
        f"{API}/compatibility/davison", headers=registered["headers"], json=payload
    )
    assert davison.status_code == 200
    assert davison.json()["chart"]["kind"] == "davison"
    assert davison.json()["midpoint_utc"]


async def test_unknown_birth_time_composite_has_no_angles_and_davison_is_422(
    client: httpx.AsyncClient, registered
):
    """Without a birth time the charts carry no location: composite still
    answers (angles null, as the contract allows), Davison cannot and says
    so as a 422 - never a 500."""
    payload = {
        "person_a": {"me": True},
        "person_b": {
            "birth_date": "1992-03-14",
            "latitude": 41.0,
            "longitude": 29.0,
            "timezone": "Europe/Istanbul",
            "label": "No time",
        },
    }
    composite = await client.post(
        f"{API}/compatibility/composite", headers=registered["headers"], json=payload
    )
    assert composite.status_code == 200
    assert composite.json()["chart"]["angles"] is None
    assert composite.json()["chart"]["planets"]

    davison = await client.post(
        f"{API}/compatibility/davison", headers=registered["headers"], json=payload
    )
    assert davison.status_code == 422
    error = davison.json()["error"]
    assert error["code"] == "missing_birth_data"
    assert error["details"]["required"] == ["birth_time", "birth_place"]


async def test_inline_birth_data_is_accepted(client: httpx.AsyncClient, registered):
    response = await client.post(
        f"{API}/compatibility/synastry",
        headers=registered["headers"],
        json={
            "person_a": {"me": True},
            "person_b": {
                "birth_date": "1988-11-02",
                "birth_time": "03:15:00",
                "birth_place": "Berlin",
                "label": "Inline person",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["person_b_label"] == "Inline person"


async def test_person_ref_requires_exactly_one_form(
    client: httpx.AsyncClient, registered, partner_id
):
    response = await client.post(
        f"{API}/compatibility/synastry",
        headers=registered["headers"],
        json={
            "person_a": {"me": True, "saved_person_id": partner_id},
            "person_b": {"me": True},
        },
    )
    assert response.status_code == 422


async def test_cannot_use_another_users_saved_person(
    client: httpx.AsyncClient, registered, partner_id
):
    """Guessing an id must not reach someone else's birth data."""
    other = await client.post(
        f"{API}/auth/register",
        json={
            "email": "intruder@example.com",
            "password": "Str0ngPassphrase!",
            "name": "Intruder",
            "birth_date": "1990-01-01",
            "birth_time": "10:00:00",
            "birth_place": "Ankara",
        },
    )
    headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    response = await client.post(
        f"{API}/compatibility/synastry",
        headers=headers,
        json={"person_a": {"me": True}, "person_b": {"saved_person_id": partner_id}},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_reports_are_listed_and_owned(
    client: httpx.AsyncClient, registered, partner_id
):
    await client.post(
        f"{API}/compatibility/synastry",
        headers=registered["headers"],
        json={"person_a": {"me": True}, "person_b": {"saved_person_id": partner_id}},
    )

    listing = await client.get(
        f"{API}/compatibility/reports", headers=registered["headers"]
    )
    assert listing.status_code == 200
    reports = listing.json()
    assert reports

    detail = await client.get(
        f"{API}/compatibility/reports/{reports[0]['id']}",
        headers=registered["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["structured_result"]

    # Another user cannot open it.
    other = await client.post(
        f"{API}/auth/register",
        json={
            "email": "nosy@example.com",
            "password": "Str0ngPassphrase!",
            "name": "Nosy",
        },
    )
    headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    forbidden = await client.get(
        f"{API}/compatibility/reports/{reports[0]['id']}", headers=headers
    )
    assert forbidden.status_code == 404


async def test_report_is_a_snapshot(
    client: httpx.AsyncClient, registered, partner_id
):
    """Editing the saved person later must not rewrite an existing report."""
    first = await client.post(
        f"{API}/compatibility/synastry",
        headers=registered["headers"],
        json={"person_a": {"me": True}, "person_b": {"saved_person_id": partner_id}},
    )
    original_id = first.json()["report_id"]
    original_score = first.json()["overall_score"]

    # Replace the partner with different birth data.
    await client.delete(
        f"{API}/saved-people/{partner_id}", headers=registered["headers"]
    )
    replacement = await client.post(
        f"{API}/saved-people",
        headers=registered["headers"],
        json={
            "name": "Deniz",
            "relation": "partner",
            "birth_date": "1979-03-09",
            "birth_time": "22:10:00",
            "birth_place": "Tokyo",
        },
    )
    new_partner = replacement.json()["id"]

    second = await client.post(
        f"{API}/compatibility/synastry",
        headers=registered["headers"],
        json={"person_a": {"me": True}, "person_b": {"saved_person_id": new_partner}},
    )
    assert second.json()["report_id"] != original_id

    stored = await client.get(
        f"{API}/compatibility/reports/{original_id}", headers=registered["headers"]
    )
    assert stored.json()["structured_result"]["overall_score"] == original_score


async def test_compatibility_requires_auth(client: httpx.AsyncClient):
    for path in ("synastry", "composite", "davison"):
        response = await client.post(f"{API}/compatibility/{path}", json={})
        assert response.status_code == 401
    assert (await client.get(f"{API}/compatibility/reports")).status_code == 401
