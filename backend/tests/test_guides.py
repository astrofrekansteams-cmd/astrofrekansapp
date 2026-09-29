"""Moon guide, returns, numerology and stones: engine checks and API contract."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import httpx
import pytest

from app.domain.astrology import BirthData, separation
from app.domain.enums import Element, MoonPhaseName, Planet, ZodiacSign
from app.services.astrology.skyfield_engine import get_engine
from app.services.guides import numerology
from app.services.guides.moon_guide import MoonGuideService
from app.services.guides.returns_guide import ReturnsGuide
from app.services.guides.stones import CATALOGUE, Intent, StoneGuide, StoneMode

API = "/api/v1"


@pytest.fixture(scope="module")
def natal():
    birth = BirthData(
        birth_date=date(1990, 5, 15),
        birth_time=time(14, 30),
        timezone="Europe/Istanbul",
        latitude=41.0082,
        longitude=28.9784,
        place="Istanbul",
    )
    return get_engine().natal_chart(birth)


# ------------------------------------------------------------------ numerology


@pytest.mark.parametrize(
    ("birth", "expected"),
    [
        (date(1990, 5, 15), 3),  # 5 + (1+5) + (1+9+9+0 -> 1) = 12 -> 3
        (date(1987, 11, 29), 11),  # 11 + 11 + (1+9+8+7=25 -> 7) = 29 -> 11 (master)
        (date(2000, 2, 20), 6),  # 2 + 2 + 2 = 6
    ],
)
def test_life_path_reduces_components_and_keeps_masters(birth, expected):
    assert numerology.life_path(birth) == expected


def test_name_numbers_fold_turkish_letters():
    # Ş->S, Ö->O, Ç->C, Ğ->G, İ->I, Ü->U
    assert numerology.normalize_name("Şöçğİü ı") == "SOCGIUI"
    # N5 I9 C3 A1 T2 + T2 E5 S1 T2 = 30 -> 3
    assert numerology.destiny("Nicat Test") == 3
    assert numerology.soul_urge("Nicat Test") == 6  # I9 A1 E5 = 15
    assert numerology.personality("Nicat Test") == 6  # N5 C3 T2 T2 S1 T2 = 15


def test_personal_year_and_month():
    birth = date(1990, 5, 15)
    assert numerology.personal_year(birth, 2026) == 3  # 5 + 6 + 1
    assert numerology.personal_month(birth, 2026, 9) == 3  # 3 + 9 = 12 -> 3
    assert numerology.birthday_number(date(1990, 5, 29)) == 11


def test_numerology_refuses_a_name_without_letters():
    with pytest.raises(ValueError):
        numerology.profile("123", date(1990, 5, 15), date(2026, 1, 1))


# ------------------------------------------------------------------ moon guide


def test_moon_guide_on_the_september_2026_full_moon(natal):
    guide = MoonGuideService().guide(datetime(2026, 9, 26, 17, tzinfo=UTC), natal)
    assert guide.phase == MoonPhaseName.FULL_MOON
    assert guide.sign == ZodiacSign.ARIES
    assert guide.next_sign == ZodiacSign.TAURUS
    assert guide.next_sign_at is not None and guide.next_sign_at > guide.moment
    assert guide.natal_house is not None
    # The opposition to the Sun defines a full Moon.
    assert any(a.body == Planet.SUN and a.aspect == "opposition" for a in guide.sky_aspects)
    assert guide.good_for and guide.careful_with and guide.summary


def test_moon_ingress_is_precise(natal):
    guide = MoonGuideService().guide(datetime(2026, 9, 26, 12, tzinfo=UTC), natal)
    moon = get_engine().positions(guide.next_sign_at, bodies=(Planet.MOON,))[0]
    assert separation(moon.longitude, 30.0) < 0.05  # within ~4 minutes of arc


def test_moon_guide_without_birth_time_has_no_house():
    chart = get_engine().natal_chart(
        BirthData(
            birth_date=date(1990, 5, 15),
            birth_time=None,
            timezone="Europe/Istanbul",
            latitude=41.0082,
            longitude=28.9784,
        )
    )
    guide = MoonGuideService().guide(datetime(2026, 9, 26, 12, tzinfo=UTC), chart)
    assert guide.natal_house is None


# --------------------------------------------------------------------- returns


def test_solar_return_sun_matches_natal_sun(natal):
    reading = ReturnsGuide().solar(natal, 2026)
    natal_sun = natal.position(Planet.SUN)
    return_sun = reading.chart.position(Planet.SUN)
    assert reading.moment.year == 2026 and reading.moment.month == 5
    assert separation(natal_sun.longitude, return_sun.longitude) < 0.001
    assert reading.theme.headline and reading.theme.lines


def test_lunar_return_moon_matches_natal_moon(natal):
    after = datetime(2026, 9, 26, tzinfo=UTC)
    reading = ReturnsGuide().lunar(natal, after)
    assert after < reading.moment < datetime(2026, 10, 25, tzinfo=UTC)
    natal_moon = natal.position(Planet.MOON)
    return_moon = reading.chart.position(Planet.MOON)
    assert separation(natal_moon.longitude, return_moon.longitude) < 0.01


# ---------------------------------------------------------------------- stones


def test_every_stone_is_complete():
    keys = [stone.key for stone in CATALOGUE]
    assert len(keys) == len(set(keys))
    for stone in CATALOGUE:
        assert stone.elements and stone.planets and stone.signs and stone.intents
        assert stone.color.startswith("#") and len(stone.color) == 7
    for intent in Intent:
        assert sum(intent in s.intents for s in CATALOGUE) >= 3


def test_stone_suggestions_follow_the_intent_and_explain_themselves(natal):
    result = StoneGuide().recommend(
        natal,
        mode=StoneMode.PERSONAL,
        intent=Intent.COMMUNICATION,
        moment=datetime(2026, 9, 26, tzinfo=UTC),
    )
    assert result.suggestions
    for suggestion in result.suggestions:
        assert Intent.COMMUNICATION in suggestion.stone.intents
        assert suggestion.score == sum(r.weight for r in suggestion.reasons)
        assert suggestion.reasons[0].kind == "intent"
    scores = [s.score for s in result.suggestions]
    assert scores == sorted(scores, reverse=True)
    assert "tıbbi" in result.disclaimer


def test_weakest_element_is_from_the_chart(natal):
    result = StoneGuide().recommend(
        natal, mode=StoneMode.PERSONAL, intent=None, moment=datetime(2026, 9, 26, tzinfo=UTC)
    )
    assert sum(result.element_balance.values()) == 10
    lowest = min(result.element_balance.values())
    assert all(result.element_balance[e] == lowest for e in result.weakest_elements)
    assert set(result.element_balance) == set(Element)


def test_today_mode_is_deterministic(natal):
    moment = datetime(2026, 9, 26, 12, tzinfo=UTC)
    sky = get_engine().positions(moment)
    first = StoneGuide().recommend(natal, mode=StoneMode.TODAY, intent=Intent.LOVE, moment=moment, sky=sky)
    second = StoneGuide().recommend(natal, mode=StoneMode.TODAY, intent=Intent.LOVE, moment=moment, sky=sky)
    assert [s.stone.key for s in first.suggestions] == [s.stone.key for s in second.suggestions]


# ------------------------------------------------------------------------- API


async def test_guide_routes_are_served(client: httpx.AsyncClient, registered):
    headers = registered["headers"]

    moon = await client.get(f"{API}/astrology/moon-guide", headers=headers)
    assert moon.status_code == 200, moon.text
    assert moon.json()["natal_house"] is not None

    solar = await client.get(f"{API}/astrology/solar-return", params={"year": 2026}, headers=headers)
    assert solar.status_code == 200, solar.text
    body = solar.json()
    assert body["kind"] == "solar_return"
    assert len(body["chart"]["planets"]) >= 10 and len(body["chart"]["houses"]) == 12

    lunar = await client.get(
        f"{API}/astrology/lunar-return", params={"after": "2026-09-26"}, headers=headers
    )
    assert lunar.status_code == 200, lunar.text

    numbers = await client.get(
        f"{API}/numerology/me", params={"reference": "2026-09-26", "locale": "en"}, headers=headers
    )
    assert numbers.status_code == 200, numbers.text
    assert numbers.json()["life_path"]["number"] == numerology.life_path(date(1992, 5, 14))

    stones = await client.get(
        f"{API}/stones/recommendation", params={"mode": "today", "intent": "calm"}, headers=headers
    )
    assert stones.status_code == 200, stones.text
    assert all("calm" in s["stone"]["intents"] for s in stones.json()["suggestions"])


async def test_guides_require_birth_data(client: httpx.AsyncClient):
    response = await client.post(
        f"{API}/auth/register",
        json={"email": "nobirth@example.com", "password": "Str0ngPassphrase!", "name": "No Birth"},
    )
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    for path in ("/astrology/moon-guide", "/numerology/me", "/stones/recommendation"):
        result = await client.get(f"{API}{path}", headers=headers)
        assert result.status_code in (400, 422), path
        assert result.json()["error"]["code"] == "birth_profile_missing"


async def test_solar_return_rejects_half_a_relocation(client: httpx.AsyncClient, registered):
    response = await client.get(
        f"{API}/astrology/solar-return",
        params={"year": 2026, "latitude": 40.0},
        headers=registered["headers"],
    )
    assert response.status_code == 422


def test_universal_stone_gets_no_element_balance_bonus(natal):
    result = StoneGuide().recommend(
        natal, mode=StoneMode.PERSONAL, intent=Intent.MEDITATION, moment=datetime(2026, 9, 26, tzinfo=UTC)
    )
    quartz = next((s for s in result.suggestions if s.stone.key == "clear_quartz"), None)
    if quartz is not None:
        assert all(r.kind != "element" for r in quartz.reasons)
