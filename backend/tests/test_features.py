"""Server-side premium gating driven by the single feature catalogue."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.domain.divination import DeckType
from app.domain.enums import SubscriptionTier
from app.services import features
from app.services.divination.spreads import REGISTRY
from app.services.features import Feature

API = "/api/v1"


@pytest.fixture
def gating(monkeypatch):
    monkeypatch.setattr(settings, "premium_gating_enabled", True)


def test_free_spreads_exist_in_the_registry():
    for deck, codes in features.FREE_SPREADS.items():
        for code in codes:
            assert code in REGISTRY[deck], f"{deck.value}:{code}"


def test_every_deck_keeps_advanced_spreads_premium():
    for deck in DeckType:
        premium = [c for c in REGISTRY[deck] if features.spread_feature(deck, c) is not None]
        assert premium, deck
    assert features.spread_feature(DeckType.TAROT, "celtic_cross") is Feature.ADVANCED_TAROT
    assert features.spread_feature(DeckType.TAROT, "single_card") is None


def test_has_feature_respects_tier_and_switch(monkeypatch):
    monkeypatch.setattr(settings, "premium_gating_enabled", True)
    assert not features.has_feature(SubscriptionTier.FREE, Feature.SYNASTRY)
    # Relationship charts moved to Kozmik+; premium keeps the everyday extras.
    assert not features.has_feature(SubscriptionTier.PREMIUM, Feature.SYNASTRY)
    assert features.has_feature(SubscriptionTier.COSMIC_PLUS, Feature.SYNASTRY)
    assert features.has_feature(SubscriptionTier.PREMIUM, Feature.MONTHLY_FORECAST)
    assert features.has_feature(SubscriptionTier.FREE, None)
    monkeypatch.setattr(settings, "premium_gating_enabled", False)
    assert features.has_feature(SubscriptionTier.FREE, Feature.SYNASTRY)


def test_production_refuses_disabled_gating(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "premium_gating_enabled", False)
    with pytest.raises(RuntimeError, match="PREMIUM_GATING_ENABLED"):
        settings.assert_production_ready()


async def test_catalogue_is_served(client: httpx.AsyncClient, registered, gating):
    response = await client.get(f"{API}/billing/features", headers=registered["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["gating_enabled"] is True
    assert "synastry" in body["premium_features"]
    assert "single_card" in body["free_spreads"]["tarot"]


async def test_free_user_is_refused_premium_routes(client: httpx.AsyncClient, registered, gating):
    headers = registered["headers"]
    person = {"birth_date": "1992-11-03", "birth_time": "08:10:00", "birth_place": "Ankara"}
    refused = [
        await client.post(
            f"{API}/divination/readings",
            headers=headers,
            json={"deck_type": "tarot", "spread_code": "celtic_cross", "locale": "tr"},
        ),
        await client.post(
            f"{API}/compatibility/synastry",
            headers=headers,
            json={"person_a": {"me": True}, "person_b": person},
        ),
        await client.get(f"{API}/forecasts/monthly", headers=headers),
        await client.get(f"{API}/forecasts/yearly", headers=headers),
        await client.get(f"{API}/astrology/transits", params={"range": "month"}, headers=headers),
        await client.get(f"{API}/astrology/solar-return", params={"year": 2026}, headers=headers),
        await client.get(f"{API}/astrology/lunar-return", headers=headers),
    ]
    for response in refused:
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "premium_required"


async def test_free_user_keeps_free_features(client: httpx.AsyncClient, registered, gating):
    headers = registered["headers"]
    draw = await client.post(
        f"{API}/divination/readings",
        headers=headers,
        json={"deck_type": "tarot", "spread_code": "single_card", "locale": "tr"},
    )
    assert draw.status_code == 201
    week = await client.get(f"{API}/astrology/transits", params={"range": "week"}, headers=headers)
    assert week.status_code == 200
    moon = await client.get(f"{API}/astrology/moon-guide", headers=headers)
    assert moon.status_code == 200
