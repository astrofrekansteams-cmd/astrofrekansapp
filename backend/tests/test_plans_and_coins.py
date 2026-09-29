"""Plans (free / premium / cosmic_plus), AstroCoins and profile customisation."""

from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.db.models.coins import CoinTransaction, CoinWallet
from app.domain.enums import SubscriptionTier
from app.services.features import Feature, has_feature
from tests.test_payments import (  # noqa: F401 - fixtures
    APPLE_IDS,
    GOOGLE_IDS,
    apple_verify,
    buyer,
    product_ids,
    stores,
    tier,
)

API = "/api/v1"

PLAN_IDS = {
    "premium_monthly": {"apple": APPLE_IDS["premium_monthly"], "google": GOOGLE_IDS["premium_monthly"]},
    "cosmic_plus_monthly": {"apple": "com.astro.cosmic.monthly", "google": "cosmic_monthly"},
    "coins_350": {"apple": "com.astro.coins.350", "google": "coins_350"},
}


@pytest.fixture
def plan_products(monkeypatch, stores):  # noqa: F811
    monkeypatch.setattr(settings, "store_product_ids", product_ids(PLAN_IDS))
    return stores


@pytest.fixture
def gating(monkeypatch):
    monkeypatch.setattr(settings, "premium_gating_enabled", True)


@pytest.fixture
def mock_ads(monkeypatch):
    monkeypatch.setattr(settings, "ad_reward_verifier", "mock")


async def wallet(client, account) -> dict:
    response = await client.get(f"{API}/coins/wallet", headers=account["headers"])
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------------ tiers


def test_tier_order_and_feature_plans(monkeypatch):
    monkeypatch.setattr(settings, "premium_gating_enabled", True)
    free, premium, cosmic = SubscriptionTier.FREE, SubscriptionTier.PREMIUM, SubscriptionTier.COSMIC_PLUS
    assert cosmic.includes(premium) and premium.includes(free)
    assert not premium.includes(cosmic)

    assert has_feature(premium, Feature.MONTHLY_FORECAST)
    assert has_feature(premium, Feature.ADVANCED_TAROT)
    assert not has_feature(premium, Feature.SYNASTRY)
    assert not has_feature(premium, Feature.YEARLY_FORECAST)
    assert not has_feature(premium, Feature.SOLAR_RETURN)
    for feature in Feature:
        assert has_feature(cosmic, feature), feature
    assert not has_feature(free, Feature.MONTHLY_FORECAST)


async def test_features_catalogue_says_which_plan_unlocks_what(client, registered):
    body = (await client.get(f"{API}/billing/features", headers=registered["headers"])).json()
    assert body["feature_tiers"]["synastry"] == "cosmic_plus"
    assert body["feature_tiers"]["monthly_forecast"] == "premium"
    assert set(body["daily_draw_limits"]) == {"free", "premium", "cosmic_plus"}
    # Older clients still read the flat list.
    assert "synastry" in body["premium_features"]


async def test_cosmic_plus_subscription(client, buyer, plan_products, gating):  # noqa: F811
    apple = plan_products["apple"]
    jws = apple.transaction(
        product_id="com.astro.cosmic.monthly", app_account_token=str(buyer["id"])
    )
    response = await apple_verify(client, buyer, jws, product_code="cosmic_plus_monthly")
    assert response.status_code == 200, response.text
    summary = response.json()["entitlements"]
    assert summary["tier"] == "cosmic_plus"
    assert summary["premium"] is True
    assert summary["capabilities"]["monthly_coins"] == settings.monthly_coins_cosmic_plus
    assert summary["capabilities"]["ad_free"] is True
    assert await tier(client, buyer) == "cosmic_plus"

    # Kozmik+ opens what premium does not.
    synastry = await client.post(
        f"{API}/compatibility/synastry",
        headers=buyer["headers"],
        json={
            "person_a": {"me": True},
            "person_b": {"birth_date": "1992-03-14", "birth_time": "08:30:00", "birth_place": "Ankara"},
        },
    )
    assert synastry.status_code == 200, synastry.text


async def test_premium_is_refused_a_cosmic_plus_feature(client, buyer, plan_products, gating):  # noqa: F811
    jws = plan_products["apple"].transaction(
        product_id=APPLE_IDS["premium_monthly"], app_account_token=str(buyer["id"])
    )
    await apple_verify(client, buyer, jws)
    assert await tier(client, buyer) == "premium"
    refused = await client.post(
        f"{API}/compatibility/synastry",
        headers=buyer["headers"],
        json={
            "person_a": {"me": True},
            "person_b": {"birth_date": "1992-03-14", "birth_time": "08:30:00", "birth_place": "Ankara"},
        },
    )
    assert refused.status_code == 403
    assert refused.json()["error"]["details"]["required_tier"] == "cosmic_plus"


async def test_the_higher_plan_wins(client, buyer, plan_products, gating):  # noqa: F811
    apple = plan_products["apple"]
    await apple_verify(
        client,
        buyer,
        apple.transaction(product_id=APPLE_IDS["premium_monthly"], transaction_id="p1",
                          app_account_token=str(buyer["id"])),
    )
    await apple_verify(
        client,
        buyer,
        apple.transaction(product_id="com.astro.cosmic.monthly", transaction_id="c1",
                          app_account_token=str(buyer["id"])),
        product_code="cosmic_plus_monthly",
    )
    assert await tier(client, buyer) == "cosmic_plus"


# ------------------------------------------------------------------ coins


async def test_a_new_wallet_is_empty_and_free_gets_no_bonus(client, registered):
    body = await wallet(client, registered)
    assert body["balance"] == 0
    assert body["tier"] == "free"
    assert body["monthly_bonus"] == 0
    assert body["bonus_granted"] == 0


async def test_monthly_bonus_is_granted_once(client, buyer, plan_products, session_factory):  # noqa: F811
    await apple_verify(
        client,
        buyer,
        plan_products["apple"].transaction(product_id=APPLE_IDS["premium_monthly"],
                                           app_account_token=str(buyer["id"])),
    )
    first = await wallet(client, buyer)
    assert first["bonus_granted"] == settings.monthly_coins_premium
    assert first["balance"] == settings.monthly_coins_premium
    again = await wallet(client, buyer)
    assert again["bonus_granted"] == 0
    assert again["balance"] == settings.monthly_coins_premium


async def test_a_coin_pack_credits_once_and_a_refund_takes_it_back(
    client, buyer, plan_products, session_factory  # noqa: F811
):
    apple = plan_products["apple"]
    jws = apple.transaction(product_id="com.astro.coins.350", type_="Consumable",
                            expires_in=None, transaction_id="coin-1",
                            app_account_token=str(buyer["id"]))
    for _ in range(3):  # client, retry, restore
        response = await apple_verify(client, buyer, jws, product_code="coins_350")
        assert response.status_code == 200, response.text
    # Coins are a balance, not report credits.
    assert response.json()["entitlements"]["credits"] == {}
    assert (await wallet(client, buyer))["balance"] == 350

    history = (await client.get(f"{API}/coins/transactions", headers=buyer["headers"])).json()
    assert [(row["kind"], row["amount"], row["reason"]) for row in history] == [
        ("purchase", 350, "coins_350")
    ]

    refunded = apple.transaction(product_id="com.astro.coins.350", type_="Consumable",
                                 expires_in=None, transaction_id="coin-1", revoked=True)
    payload = apple.notification(notification_type="REFUND", signed_transaction=refunded)
    await client.post(f"{API}/webhooks/apple/app-store", json={"signedPayload": payload})
    assert (await wallet(client, buyer))["balance"] == 0


async def test_ads_are_off_without_a_verifier(client, registered):
    body = await wallet(client, registered)
    assert body["ads_enabled"] is False
    response = await client.post(
        f"{API}/coins/ads/reward", headers=registered["headers"], json={"token": "reward-token-1"}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ad_rewards_unavailable"


async def test_rewarded_ads_pay_once_per_token_and_are_capped(
    client, registered, mock_ads, monkeypatch
):
    monkeypatch.setattr(settings, "ad_rewards_per_day", 2)
    url = f"{API}/coins/ads/reward"
    first = await client.post(url, headers=registered["headers"], json={"token": "reward-token-1"})
    assert first.status_code == 200, first.text
    replay = await client.post(url, headers=registered["headers"], json={"token": "reward-token-1"})
    assert replay.json()["transaction"]["id"] == first.json()["transaction"]["id"]
    second = await client.post(url, headers=registered["headers"], json={"token": "reward-token-2"})
    assert second.json()["wallet"]["balance"] == 2 * settings.ad_reward_coins
    third = await client.post(url, headers=registered["headers"], json={"token": "reward-token-3"})
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "ad_reward_limit_reached"


def test_the_mock_ad_verifier_is_refused_in_production(monkeypatch):
    from app.services.coins.ads import AdRewardsUnavailable, get_ad_verifier

    monkeypatch.setattr(settings, "ad_reward_verifier", "mock")
    monkeypatch.setattr(settings, "environment", "production", raising=False)
    monkeypatch.setattr(type(settings), "is_production", property(lambda self: True))
    with pytest.raises(AdRewardsUnavailable):
        get_ad_verifier()


async def test_catalog_lists_plans_packs_and_prices(client, registered):
    body = (await client.get(f"{API}/coins/catalog", headers=registered["headers"])).json()
    assert [plan["tier"] for plan in body["plans"]] == ["free", "premium", "cosmic_plus"]
    assert {pack["product_code"] for pack in body["coin_packs"]} >= {"coins_120", "coins_350", "coins_800"}
    items = {item["code"]: item for item in body["spend_items"]}
    assert items["extra_draw"]["available"] is True
    assert items["advanced_spread"]["available"] is True
    # No prices in money anywhere: the stores own them.
    assert "price_minor" not in str(body)


# ------------------------------------------------- divination allowance


async def _create(client, headers, *, ref=None, spread="three_card", coins=False):
    return await client.post(
        f"{API}/divination/sessions",
        headers=headers,
        json={
            "consumer_ref": ref or f"test-{uuid.uuid4().hex}",
            "deck_type": "tarot",
            "spread_code": spread,
            "locale": "tr",
            "pay_with_coins": coins,
        },
    )


async def _give_coins(session_factory, user_id: uuid.UUID, amount: int) -> None:
    from app.services.coins.service import CoinService

    async with session_factory() as session:
        await CoinService(session)._apply(
            user_id, amount, kind="ad_reward", reason="test", key=f"test:{uuid.uuid4().hex}"
        )
        await session.commit()


async def _user_id(client, account) -> uuid.UUID:
    return uuid.UUID((await client.get(f"{API}/auth/me", headers=account["headers"])).json()["id"])


async def test_daily_allowance_then_coins(client, registered, gating, monkeypatch, session_factory):
    monkeypatch.setattr(settings, "daily_draws_free", 2)
    headers = registered["headers"]
    for _ in range(2):
        assert (await _create(client, headers)).status_code == 200

    allowance = (await client.get(f"{API}/divination/allowance", headers=headers)).json()
    assert allowance == {**allowance, "daily_limit": 2, "used_today": 2, "remaining": 0}

    over = await _create(client, headers)
    assert over.status_code == 429
    assert over.json()["error"]["code"] == "daily_draw_limit_reached"
    assert over.json()["error"]["details"]["extra_draw_price"] == 10

    broke = await _create(client, headers, coins=True)
    assert broke.status_code == 402
    assert broke.json()["error"]["code"] == "insufficient_coins"

    await _give_coins(session_factory, await _user_id(client, registered), 25)
    ref = f"test-{uuid.uuid4().hex}"
    paid = await _create(client, headers, ref=ref, coins=True)
    assert paid.status_code == 200, paid.text
    assert paid.json()["coins_spent"] == 10
    # A retry of the same shuffle is neither blocked nor charged again.
    retry = await _create(client, headers, ref=ref, coins=True)
    assert retry.status_code == 200
    assert retry.json()["session_id"] == paid.json()["session_id"]
    assert (await wallet(client, registered))["balance"] == 15


async def test_an_advanced_spread_can_be_paid_with_coins(client, registered, gating, session_factory):
    headers = registered["headers"]
    refused = await _create(client, headers, spread="celtic_cross")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "premium_required"

    await _give_coins(session_factory, await _user_id(client, registered), 30)
    paid = await _create(client, headers, spread="celtic_cross", coins=True)
    assert paid.status_code == 200, paid.text
    assert paid.json()["coins_spent"] == 25
    history = (await client.get(f"{API}/coins/transactions", headers=headers)).json()
    assert history[0]["kind"] == "spend" and history[0]["amount"] == -25


async def test_concurrent_spends_never_go_negative(client, registered, gating, monkeypatch, session_factory):
    monkeypatch.setattr(settings, "daily_draws_free", 0)
    await _give_coins(session_factory, await _user_id(client, registered), 15)
    results = await asyncio.gather(
        *(_create(client, registered["headers"], coins=True) for _ in range(4))
    )
    assert sum(1 for r in results if r.status_code == 200) == 1
    async with session_factory() as session:
        [row] = list(await session.scalars(select(CoinWallet)))
        assert row.balance == 5
        spent = await session.scalar(
            select(func.count()).select_from(CoinTransaction).where(CoinTransaction.kind == "spend")
        )
        assert spent == 1


# ---------------------------------------------------------------- profile


async def test_profile_customisation(client, registered):
    headers = registered["headers"]
    me = (await client.get(f"{API}/users/me", headers=headers)).json()
    assert me["cover_theme"] == "cosmic_night"
    assert me["privacy"]["show_birth_date"] is False
    assert me["notification_prefs"]["promotions"] is False

    updated = await client.patch(
        f"{API}/users/me",
        headers=headers,
        json={
            "name": "Nova Star",
            "bio": "  Balık Güneş, Akrep yükselen.  ",
            "avatar_preset": "pisces",
            "cover_theme": "aurora",
            "language": "en",
            "privacy": {"show_rising_sign": False, "show_birth_date": False},
            "notification_prefs": {"transit_alerts": False, "promotions": True},
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["bio"] == "Balık Güneş, Akrep yükselen."
    assert body["avatar_preset"] == "pisces"
    assert body["cover_theme"] == "aurora"
    assert body["language"] == "en"
    assert body["privacy"]["show_rising_sign"] is False
    assert body["privacy"]["show_sun_sign"] is True
    assert body["notification_prefs"] == {**body["notification_prefs"], "transit_alerts": False, "promotions": True}

    cleared = await client.patch(f"{API}/users/me", headers=headers, json={"avatar_preset": ""})
    assert cleared.json()["avatar_preset"] is None


@pytest.mark.parametrize(
    "patch",
    [{"avatar_preset": "dragon"}, {"cover_theme": "neon"}, {"language": "xx"}, {"bio": "x" * 281}],
)
async def test_profile_rejects_unknown_choices(client, registered, patch):
    response = await client.patch(f"{API}/users/me", headers=registered["headers"], json=patch)
    assert response.status_code == 422
