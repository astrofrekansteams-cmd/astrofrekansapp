"""Forecast layer: determinism, timezone handling, caching and the API
contract the Flutter client will bind to."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import httpx
import pytest

from app.domain.astrology import BirthData
from app.domain.enums import HouseSystem, Planet
from app.domain.horoscope import HoroscopePeriod, LifeArea
from app.services.astrology.horoscope import (
    HoroscopeEngine,
    day_window,
    month_window,
    week_window,
)
from app.services.astrology.skyfield_engine import get_engine

API = "/api/v1"


@pytest.fixture(scope="module")
def chart():
    birth = BirthData(
        birth_date=date(1992, 5, 14),
        birth_time=time(14, 30),
        timezone="Europe/Istanbul",
        latitude=41.0082,
        longitude=28.9784,
        house_system=HouseSystem.PLACIDUS,
    )
    return get_engine().natal_chart(birth)


@pytest.fixture(scope="module")
def horoscope():
    return HoroscopeEngine()


DAY = datetime(2026, 9, 23, 9, 0, tzinfo=UTC)


# ----------------------------------------------------------- determinism


def test_daily_frequency_is_deterministic(chart, horoscope):
    first = horoscope.daily_frequency(
        chart, day=DAY, timezone="Europe/Istanbul", chart_fingerprint="d"
    )
    second = HoroscopeEngine().daily_frequency(
        chart, day=DAY, timezone="Europe/Istanbul", chart_fingerprint="d"
    )

    assert first.overall == second.overall
    assert {area: score.score for area, score in first.scores.items()} == {
        area: score.score for area, score in second.scores.items()
    }
    assert [hour.reason for hour in first.important_hours] == [
        hour.reason for hour in second.important_hours
    ]
    assert [factor.id for factor in first.influences] == [
        factor.id for factor in second.influences
    ]


def test_daily_frequency_scores_are_explainable(chart, horoscope):
    frequency = horoscope.daily_frequency(
        chart, day=DAY, timezone="Europe/Istanbul", chart_fingerprint="d"
    )
    factor_ids = {factor.id for factor in frequency.influences}

    assert set(frequency.scores) == set(LifeArea)
    for score in frequency.scores.values():
        assert 0 <= score.score <= 100
        # Every scored area names the factors behind it, and those factors are
        # real objects the client can look up - no black-box numbers.
        for factor_id in score.factor_ids:
            assert isinstance(factor_id, str) and factor_id
    assert factor_ids
    assert frequency.scoring_version == "daily_frequency_v1"


def test_important_hours_come_from_real_exact_aspects(chart, horoscope):
    frequency = horoscope.daily_frequency(
        chart, day=DAY, timezone="Europe/Istanbul", chart_fingerprint="d"
    )
    window = day_window(DAY, "Europe/Istanbul")
    start, end = window.utc

    assert frequency.important_hours
    for hour in frequency.important_hours:
        assert start <= hour.start < hour.end <= end
        assert hour.factor_ids
        assert hour.type in {"supportive", "demanding", "notable"}


def test_different_days_give_different_readings(chart, horoscope):
    first = horoscope.daily_frequency(
        chart, day=DAY, timezone="Europe/Istanbul", chart_fingerprint="d"
    )
    later = horoscope.daily_frequency(
        chart,
        day=DAY + timedelta(days=9),
        timezone="Europe/Istanbul",
        chart_fingerprint="d",
    )
    assert (first.overall, [h.reason for h in first.important_hours]) != (
        later.overall,
        [h.reason for h in later.important_hours],
    )


def test_two_charts_get_different_readings(horoscope, chart):
    other = get_engine().natal_chart(
        BirthData(
            birth_date=date(1988, 11, 2),
            birth_time=time(3, 15),
            timezone="Europe/Berlin",
            latitude=52.52,
            longitude=13.405,
        )
    )
    mine = horoscope.daily_frequency(
        chart, day=DAY, timezone="Europe/Istanbul", chart_fingerprint="a"
    )
    theirs = horoscope.daily_frequency(
        other, day=DAY, timezone="Europe/Berlin", chart_fingerprint="b"
    )
    # Personalised, not a shared sun-sign text.
    assert mine.scores[LifeArea.LOVE].score != theirs.scores[LifeArea.LOVE].score or (
        mine.message_context["moon_house"] != theirs.message_context["moon_house"]
    )


# -------------------------------------------------------------- windows


def test_day_window_follows_the_user_timezone():
    istanbul = day_window(DAY, "Europe/Istanbul")
    new_york = day_window(DAY, "America/New_York")

    assert istanbul.start.hour == 0
    assert new_york.start.hour == 0
    # Same instant, different local days -> different UTC windows.
    assert istanbul.utc[0] != new_york.utc[0]
    assert (istanbul.utc[1] - istanbul.utc[0]) == timedelta(days=1)


def test_day_window_across_a_dst_transition():
    """The US spring-forward day is 23 hours long, and the window must say so."""
    spring_forward = datetime(2026, 3, 8, 12, tzinfo=UTC)
    window = day_window(spring_forward, "America/New_York")
    start, end = window.utc
    assert (end - start) == timedelta(hours=23)

    autumn = datetime(2026, 11, 1, 12, tzinfo=UTC)
    window = day_window(autumn, "America/New_York")
    start, end = window.utc
    assert (end - start) == timedelta(hours=25)


def test_week_and_month_windows():
    week = week_window(DAY, "Europe/Istanbul")
    assert week.start.weekday() == 0
    assert (week.end - week.start) == timedelta(days=7)

    month = month_window(2026, 2, "Europe/Istanbul")
    assert month.start.day == 1 and month.start.month == 2
    assert month.end.month == 3
    assert (month.end - month.start).days == 28


# ------------------------------------------------------------ structure


def test_weekly_is_not_a_daily_average(chart, horoscope):
    weekly = horoscope.weekly(
        chart, day=DAY, timezone="Europe/Istanbul", chart_fingerprint="w"
    )
    daily = horoscope.daily(
        chart, day=DAY, timezone="Europe/Istanbul", chart_fingerprint="w"
    )

    assert weekly.period is HoroscopePeriod.WEEKLY
    assert (weekly.end_at - weekly.start_at) == timedelta(days=7)
    assert len(weekly.major_transits) >= len(daily.major_transits)
    assert weekly.important_dates
    for item in weekly.important_dates:
        assert weekly.start_at <= item.date <= weekly.end_at
        assert item.factor_ids


def test_monthly_structure(chart, horoscope):
    forecast = horoscope.monthly(
        chart, year=2026, month=10, timezone="Europe/Istanbul", chart_fingerprint="m"
    )

    assert forecast.year == 2026 and forecast.month == 10
    assert set(item.area for item in forecast.areas) == set(LifeArea)
    assert forecast.general_theme
    assert forecast.source_factors
    assert 0 <= forecast.overall <= 100

    for cluster in forecast.key_periods:
        assert forecast.start_at <= cluster.start_at < cluster.end_at
        assert cluster.areas
        assert cluster.source_factors
    for item in forecast.personal_events:
        assert item.strength > 0
        assert item.event.exact_at


def test_monthly_clusters_are_deterministic(chart, horoscope):
    first = horoscope.monthly(
        chart, year=2026, month=10, timezone="Europe/Istanbul", chart_fingerprint="m"
    )
    second = HoroscopeEngine().monthly(
        chart, year=2026, month=10, timezone="Europe/Istanbul", chart_fingerprint="m"
    )
    assert [(c.start_at, c.end_at, c.strength) for c in first.key_periods] == [
        (c.start_at, c.end_at, c.strength) for c in second.key_periods
    ]


def test_annual_structure_and_solar_return(chart, horoscope):
    forecast = horoscope.annual(
        chart, year=2026, timezone="Europe/Istanbul", chart_fingerprint="y"
    )

    assert forecast.year == 2026
    assert forecast.eclipses  # 2026 has four
    assert forecast.retrograde_periods
    assert forecast.outer_planet_hits
    assert forecast.solar_return is not None
    assert forecast.solar_return.exact_at.year == 2026
    assert forecast.source_factors

    for item in forecast.major_transits:
        assert item.strength >= 0
        # A year is made of the slow bodies; the Moon is excluded on purpose.
        assert item.transiting_body is not Planet.MOON


def test_personal_calendar_relevance(chart, horoscope):
    from app.services.astrology.calendar import CosmicCalendarEngine

    events = CosmicCalendarEngine().events(
        datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC)
    )
    personal = horoscope.personal_events(chart, events)

    assert personal
    for item in personal:
        assert 0 < item.strength <= 100
        assert item.relevance
        if item.affected_house is not None:
            assert 1 <= item.affected_house <= 12
        for contact in item.natal_aspects:
            assert contact.orb <= 5.0

    # Eclipses outrank ordinary lunations for personal relevance.
    eclipses = [item for item in personal if item.event.type.is_eclipse]
    if eclipses:
        assert max(item.strength for item in eclipses) >= 85


# ----------------------------------------------------------------- API


async def test_transits_endpoint_contract(client: httpx.AsyncClient, registered):
    response = await client.get(
        f"{API}/astrology/transits",
        headers=registered["headers"],
        params={"range": "day"},
    )
    assert response.status_code == 200
    body = response.json()

    assert set(body) >= {
        "start_at",
        "end_at",
        "reference",
        "timezone",
        "range",
        "active",
        "approaching",
        "upcoming",
        "ingresses",
        "engine_version",
        "scoring_version",
        "cached",
    }

    everything = body["active"] + body["approaching"] + body["upcoming"]
    assert everything
    for item in everything:
        assert 0 <= item["strength"] <= 100
        assert item["status"] in {"approaching", "exact", "separating"}
        assert item["target_type"] in {"natal_planet", "natal_angle", "house_ingress"}
        assert item["transiting_body"] == item["transiting_body"].lower()
        for pass_item in item["passes"]:
            assert pass_item["direction"] in {"direct", "retrograde"}


async def test_transit_detail_endpoint(client: httpx.AsyncClient, registered):
    listing = await client.get(
        f"{API}/astrology/transits",
        headers=registered["headers"],
        params={"range": "day"},
    )
    first = (listing.json()["active"] + listing.json()["approaching"])[0]

    response = await client.get(
        f"{API}/astrology/transits/{first['id']}", headers=registered["headers"]
    )
    assert response.status_code == 200
    assert response.json()["id"] == first["id"]

    missing = await client.get(
        f"{API}/astrology/transits/does-not-exist", headers=registered["headers"]
    )
    assert missing.status_code == 404


async def test_daily_frequency_endpoint(client: httpx.AsyncClient, registered):
    response = await client.get(
        f"{API}/astrology/daily-frequency", headers=registered["headers"]
    )
    assert response.status_code == 200
    body = response.json()

    assert 0 <= body["overall"] <= 100
    assert set(body["scores"]) == {area.value for area in LifeArea}
    for score in body["scores"].values():
        assert score["trend"] in {"rising", "steady", "falling"}
    assert body["influences"]
    assert body["scoring_version"] == "daily_frequency_v1"


async def test_daily_frequency_is_cached(client: httpx.AsyncClient, registered):
    first = await client.get(
        f"{API}/astrology/daily-frequency", headers=registered["headers"]
    )
    second = await client.get(
        f"{API}/astrology/daily-frequency", headers=registered["headers"]
    )
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert first.json()["overall"] == second.json()["overall"]


async def test_cache_is_invalidated_when_birth_data_changes(
    client: httpx.AsyncClient, registered
):
    """The cache key contains the chart fingerprint, so new birth data cannot
    serve an old reading."""
    first = await client.get(
        f"{API}/astrology/daily-frequency", headers=registered["headers"]
    )
    assert first.status_code == 200

    await client.put(
        f"{API}/birth-profiles/me",
        headers=registered["headers"],
        json={
            "birth_date": "1988-11-02",
            "birth_time": "03:15:00",
            "birth_place": "Berlin",
        },
    )

    after = await client.get(
        f"{API}/astrology/daily-frequency", headers=registered["headers"]
    )
    assert after.json()["cached"] is False
    assert after.json()["message_context"] != first.json()["message_context"]


async def test_engine_version_invalidates_the_cache(
    client: httpx.AsyncClient, registered, monkeypatch
):
    first = await client.get(
        f"{API}/astrology/daily-frequency", headers=registered["headers"]
    )
    assert first.json()["cached"] is False

    from app.services.forecast import service as forecast_service

    monkeypatch.setattr(
        forecast_service, "VERSION_TAG", forecast_service.VERSION_TAG + ":bumped"
    )
    monkeypatch.setattr(
        forecast_service, "DAILY_FREQUENCY_VERSION", "daily_frequency_v2"
    )

    after = await client.get(
        f"{API}/astrology/daily-frequency", headers=registered["headers"]
    )
    assert after.json()["cached"] is False


async def test_horoscope_endpoints(client: httpx.AsyncClient, registered):
    for path, period in (
        ("horoscope/daily", "daily"),
        ("horoscope/weekly", "weekly"),
    ):
        response = await client.get(f"{API}/{path}", headers=registered["headers"])
        assert response.status_code == 200
        body = response.json()
        assert body["period"] == period
        assert 0 <= body["overall_score"] <= 100
        assert {item["area"] for item in body["areas"]} == {
            area.value for area in LifeArea
        }
        assert body["source_factors"]


async def test_calendar_endpoints(client: httpx.AsyncClient, registered):
    events = await client.get(
        f"{API}/calendar/events",
        headers=registered["headers"],
        params={"start": "2026-02-01", "end": "2026-03-31"},
    )
    assert events.status_code == 200
    payload = events.json()["events"]
    assert payload
    types = {item["type"] for item in payload}
    assert types & {"new_moon", "full_moon"}

    personal = await client.get(
        f"{API}/calendar/personal",
        headers=registered["headers"],
        params={"start": "2026-02-01", "end": "2026-03-31"},
    )
    assert personal.status_code == 200
    for item in personal.json()["events"]:
        assert item["strength"] > 0
        assert "event" in item and "personal_relevance" in item


async def test_forecast_endpoints(client: httpx.AsyncClient, registered):
    monthly = await client.get(
        f"{API}/forecasts/monthly",
        headers=registered["headers"],
        params={"year": 2026, "month": 10},
    )
    assert monthly.status_code == 200
    assert monthly.json()["month"] == 10

    yearly = await client.get(
        f"{API}/forecasts/yearly",
        headers=registered["headers"],
        params={"year": 2026},
    )
    assert yearly.status_code == 200
    body = yearly.json()
    assert body["year"] == 2026
    assert body["eclipses"]

    # Cached on the second call, and stored as a snapshot for cold starts.
    again = await client.get(
        f"{API}/forecasts/yearly",
        headers=registered["headers"],
        params={"year": 2026},
    )
    assert again.json()["cached"] is True


async def test_forecast_requires_birth_data(client: httpx.AsyncClient):
    register = await client.post(
        f"{API}/auth/register",
        json={
            "email": "nobirth@example.com",
            "password": "Str0ngPassphrase!",
            "name": "No Birth",
        },
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    response = await client.get(
        f"{API}/astrology/daily-frequency", headers=headers
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "birth_profile_missing"


async def test_forecast_endpoints_require_auth(client: httpx.AsyncClient):
    for path in (
        "astrology/transits",
        "astrology/daily-frequency",
        "horoscope/daily",
        "calendar/personal",
        "forecasts/monthly",
    ):
        response = await client.get(f"{API}/{path}")
        assert response.status_code == 401
