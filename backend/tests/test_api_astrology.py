"""End-to-end API tests for users, birth profiles and charts."""

from __future__ import annotations

import httpx

API = "/api/v1"


# ----------------------------------------------------------------- probes


async def test_health_is_public(client: httpx.AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_ready_reports_dependencies(client: httpx.AsyncClient):
    response = await client.get("/ready")
    body = response.json()
    assert set(body["checks"]) == {"database", "cache", "ephemeris"}
    assert body["checks"]["ephemeris"] == "ok"


async def test_openapi_is_served(client: httpx.AsyncClient):
    response = await client.get(f"{API}/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for path in (
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/users/me",
        "/api/v1/birth-profiles/me",
        "/api/v1/astrology/natal-chart/me",
        "/api/v1/astrology/moon-phase",
    ):
        assert path in paths


# ------------------------------------------------------------ birth profile


async def test_registration_geocodes_the_birth_place(
    client: httpx.AsyncClient, registered
):
    response = await client.get(
        f"{API}/birth-profiles/me", headers=registered["headers"]
    )
    assert response.status_code == 200
    profile = response.json()
    assert profile["timezone"] == "Europe/Istanbul"
    assert profile["latitude"] == 41.0082
    assert profile["utc_offset_hours"] == 3.0  # Turkey was on UTC+3 in May 1992
    assert profile["can_compute_houses"] is True
    assert profile["house_system"] == "placidus"


async def test_birth_profile_upsert_replaces_the_primary(
    client: httpx.AsyncClient, registered
):
    first = await client.put(
        f"{API}/birth-profiles/me",
        headers=registered["headers"],
        json={
            "birth_date": "1988-11-02",
            "birth_time": "03:15:00",
            "birth_place": "Berlin",
        },
    )
    assert first.status_code == 200
    assert first.json()["timezone"] == "Europe/Berlin"

    listing = await client.get(f"{API}/birth-profiles", headers=registered["headers"])
    assert len([p for p in listing.json() if p["is_primary"]]) == 1


async def test_explicit_coordinates_win_over_the_place_name(
    client: httpx.AsyncClient, registered
):
    response = await client.put(
        f"{API}/birth-profiles/me",
        headers=registered["headers"],
        json={
            "birth_date": "1990-06-01",
            "birth_time": "08:00:00",
            "birth_place": "Somewhere remote",
            "latitude": -33.8688,
            "longitude": 151.2093,
        },
    )
    assert response.status_code == 200
    # The timezone is derived from the coordinates, not from the free text.
    assert response.json()["timezone"] == "Australia/Sydney"


async def test_birth_profile_requires_authentication(client: httpx.AsyncClient):
    assert (await client.get(f"{API}/birth-profiles/me")).status_code == 401


async def test_geocode_endpoint(client: httpx.AsyncClient, registered):
    response = await client.get(
        f"{API}/geocode", params={"query": "Istanbul"}, headers=registered["headers"]
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["timezone"] == "Europe/Istanbul"
    assert -90 <= results[0]["latitude"] <= 90


# ------------------------------------------------------------- saved people


async def test_saved_people_round_trip(client: httpx.AsyncClient, registered):
    created = await client.post(
        f"{API}/saved-people",
        headers=registered["headers"],
        json={
            "name": "Deniz",
            "relation": "partner",
            "birth_date": "1994-08-21",
            "birth_time": "09:45:00",
            "birth_place": "Izmir",
        },
    )
    assert created.status_code == 201
    person = created.json()
    assert person["relation"] == "partner"
    assert person["timezone"] == "Europe/Istanbul"

    listing = await client.get(f"{API}/saved-people", headers=registered["headers"])
    assert len(listing.json()) == 1

    deleted = await client.delete(
        f"{API}/saved-people/{person['id']}", headers=registered["headers"]
    )
    assert deleted.status_code == 200
    assert (
        await client.get(f"{API}/saved-people", headers=registered["headers"])
    ).json() == []


# -------------------------------------------------------------- natal chart


async def test_my_natal_chart(client: httpx.AsyncClient, registered):
    response = await client.get(
        f"{API}/astrology/natal-chart/me", headers=registered["headers"]
    )
    assert response.status_code == 200
    chart = response.json()

    assert chart["engine"] == "skyfield"
    assert chart["house_system"] == "placidus"
    assert len(chart["planets"]) == 12
    assert len(chart["houses"]) == 12
    assert chart["warnings"] == []

    sun = next(p for p in chart["planets"] if p["planet"] == "sun")
    assert sun["sign"] == "taurus"
    assert 0 <= sun["degree"] < 30
    assert 0 <= sun["minute"] < 60
    assert sun["house"] is not None

    assert chart["angles"]["ascendant_sign"] in {
        "aries", "taurus", "gemini", "cancer", "leo", "virgo",
        "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
    }
    assert sum(chart["elements"].values()) == 10
    assert sum(chart["modalities"].values()) == 10
    assert chart["dominant_planet"]
    assert chart["big_three"]["sun"] == "taurus"
    assert chart["birth_data"]["utc_offset_hours"] == 3.0
    assert chart["birth_data"]["utc_datetime"].endswith("Z")  # UTC instant


async def test_chart_is_cached_and_identical(client: httpx.AsyncClient, registered):
    first = await client.get(
        f"{API}/astrology/natal-chart/me", headers=registered["headers"]
    )
    second = await client.get(
        f"{API}/astrology/natal-chart/me", headers=registered["headers"]
    )
    assert first.json()["planets"] == second.json()["planets"]
    assert first.json()["computed_at"] == second.json()["computed_at"]  # cache hit


async def test_chart_house_system_override(client: httpx.AsyncClient, registered):
    response = await client.get(
        f"{API}/astrology/natal-chart/me",
        headers=registered["headers"],
        params={"house_system": "whole_sign"},
    )
    assert response.status_code == 200
    chart = response.json()
    assert chart["house_system"] == "whole_sign"
    assert chart["houses"][0]["cusp_longitude"] % 30 == 0


async def test_ad_hoc_chart_for_another_person(client: httpx.AsyncClient, registered):
    response = await client.post(
        f"{API}/astrology/natal-chart",
        headers=registered["headers"],
        json={
            "birth_date": "1994-08-21",
            "birth_time": "09:45:00",
            "birth_place": "London",
            "house_system": "placidus",
        },
    )
    assert response.status_code == 200
    chart = response.json()
    assert chart["birth_data"]["timezone"] == "Europe/London"
    assert chart["birth_data"]["utc_offset_hours"] == 1.0  # BST in August
    assert next(p for p in chart["planets"] if p["planet"] == "sun")["sign"] == "leo"


async def test_chart_without_birth_time_warns_and_omits_houses(
    client: httpx.AsyncClient, registered
):
    response = await client.post(
        f"{API}/astrology/natal-chart",
        headers=registered["headers"],
        json={"birth_date": "1994-08-21", "birth_place": "London"},
    )
    assert response.status_code == 200
    chart = response.json()
    assert chart["houses"] == []
    assert chart["angles"] is None
    assert any("birth_time_unknown" in warning for warning in chart["warnings"])


async def test_chart_requires_a_birth_profile(client: httpx.AsyncClient):
    register = await client.post(
        f"{API}/auth/register",
        json={
            "email": "empty@example.com",
            "password": "Str0ngPassphrase!",
            "name": "Empty",
        },
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    response = await client.get(f"{API}/astrology/natal-chart/me", headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "birth_profile_missing"


# ---------------------------------------------------------- sky endpoints


async def test_moon_phase_endpoint(client: httpx.AsyncClient, registered):
    response = await client.get(
        f"{API}/astrology/moon-phase",
        headers=registered["headers"],
        params={"moment": "2026-05-01T12:00:00+00:00"},
    )
    assert response.status_code == 200
    body = response.json()
    assert 0.0 <= body["illumination"] <= 1.0
    assert body["phase"] in {
        "new_moon", "waxing_crescent", "first_quarter", "waxing_gibbous",
        "full_moon", "waning_gibbous", "last_quarter", "waning_crescent",
    }
    assert body["next_phase_at"] > body["moment"]


async def test_positions_endpoint(client: httpx.AsyncClient, registered):
    response = await client.get(
        f"{API}/astrology/positions",
        headers=registered["headers"],
        params={"moment": "2026-03-20T14:46:00+00:00"},
    )
    assert response.status_code == 200
    positions = response.json()["positions"]
    sun = next(p for p in positions if p["planet"] == "sun")
    assert sun["longitude"] < 0.02 or sun["longitude"] > 359.98  # 0 Aries
    assert len(positions) == 12


# ---------------------------------------------------------------- profile


async def test_profile_update_and_invalid_timezone(
    client: httpx.AsyncClient, registered
):
    updated = await client.patch(
        f"{API}/users/me",
        headers=registered["headers"],
        json={"name": "Nova Star", "language": "en", "timezone": "Europe/Berlin"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Nova Star"
    assert updated.json()["timezone"] == "Europe/Berlin"

    bad = await client.patch(
        f"{API}/users/me",
        headers=registered["headers"],
        json={"timezone": "Mars/Olympus_Mons"},
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "validation_error"


async def test_account_deletion_is_soft_and_revokes_access(
    client: httpx.AsyncClient, registered
):
    response = await client.request(
        "DELETE", f"{API}/users/me", headers=registered["headers"],
        json={"password": registered["password"]},
    )
    assert response.status_code == 200
    assert (
        await client.get(f"{API}/users/me", headers=registered["headers"])
    ).status_code == 401
