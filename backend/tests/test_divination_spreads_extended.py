"""Extended spreads, themes, position descriptions and the whole-spread synthesis."""

from __future__ import annotations

import httpx
import pytest

from app.domain.divination import DeckType
from app.services.divination.spreads import REGISTRY, get_spread
from app.services.divination.synthesis import contextual_meaning

API = "/api/v1"

REQUIRED = {
    DeckType.TAROT: {
        "single_card": 1, "past_present_future": 3, "situation_obstacle_advice": 3,
        "love_three_card": 3, "mind_body_spirit": 3, "five_card": 5, "love_spread": 7,
        "career_spread": 6, "money_spread": 5, "spiritual_guide": 5, "question_insight": 3,
        "celtic_cross": 10,
    },
    DeckType.RUNE: {
        "single_rune": 1, "past_present_future": 3, "problem_hidden_solution": 3,
        "love_rune": 3, "career_rune": 3, "question_rune": 3,
    },
    DeckType.KATINA: {
        "single_card": 1, "relationship_three": 3, "relationship": 5, "love_future": 5,
        "partner_feelings": 3, "relationship_future": 5, "ex_partner": 5, "new_love": 5,
        "question_katina": 3,
    },
}


@pytest.mark.parametrize("deck", list(REQUIRED))
def test_required_spreads_have_the_right_size(deck):
    for code, size in REQUIRED[deck].items():
        assert get_spread(deck, code).card_count == size, code


def test_five_card_positions_match_the_product_brief():
    keys = [p.key for p in get_spread(DeckType.TAROT, "five_card").positions]
    assert keys == [
        "current_situation", "past_influence", "hidden_influence", "advice", "possible_outcome",
    ]


def test_every_position_has_a_turkish_description():
    for deck, spreads in REGISTRY.items():
        for code, spread in spreads.items():
            for position in spread.positions:
                assert position.description("tr"), f"{deck.value}:{code}:{position.key}"


def test_katina_never_reverses_and_never_claims_the_other_persons_feelings():
    for spread in REGISTRY[DeckType.KATINA].values():
        assert spread.allow_reversed is False
    climate = get_spread(DeckType.KATINA, "partner_feelings").positions[0]
    assert "bilemez" in climate.description("tr")
    assert "never claims" in climate.interpretation_role


def test_themes_pick_the_matching_meaning_layer():
    row = {"meaning": "general", "love_meaning": "love", "career_meaning": "", "growth_meaning": "growth"}
    assert contextual_meaning("love", row) == "love"
    assert contextual_meaning("career", row) == "general"  # empty layer falls back
    assert contextual_meaning("spiritual", row) == "growth"
    assert get_spread(DeckType.TAROT, "money_spread").theme == "money"


async def test_reading_carries_synthesis_and_position_meaning(
    client: httpx.AsyncClient, registered
):
    response = await client.post(
        f"{API}/divination/readings",
        headers=registered["headers"],
        json={"deck_type": "tarot", "spread_code": "five_card", "locale": "tr", "question": "İşim?"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["spread_theme"] == "general"
    assert len(body["items"]) == 5
    assert len({item["item_id"] for item in body["items"]}) == 5  # no repeats
    for item in body["items"]:
        assert item["position_description"]
        assert item["contextual_meaning"]
        assert item["orientation"] in ("upright", "reversed")
    synthesis = body["synthesis"]
    assert synthesis["headline"]
    assert len(synthesis["flow"]) == 5
    assert synthesis["counts"]["cards"] == 5


async def test_single_rune_synthesis_names_the_rune(client: httpx.AsyncClient, registered):
    response = await client.post(
        f"{API}/divination/readings",
        headers=registered["headers"],
        json={"deck_type": "rune", "spread_code": "single_rune", "locale": "tr"},
    )
    body = response.json()
    assert body["items"][0]["display_name"] in body["synthesis"]["headline"]


async def test_spread_listing_exposes_theme(client: httpx.AsyncClient, registered):
    response = await client.get(
        f"{API}/divination/decks/katina/spreads",
        params={"locale": "tr"},
        headers=registered["headers"],
    )
    themes = {s["spread_code"]: s["theme"] for s in response.json()}
    assert themes["new_love"] == "love"
    assert themes["ex_partner"] == "relationship"
