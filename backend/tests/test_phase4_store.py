"""Phase 4: store readiness - Android notification channel, Firebase
revocation checks, store product catalogue and entitlements."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.firebase import firebase_provider
from app.services.firebase.provider import DataPushMessage, PushMessage
from tests.test_payments import (  # noqa: F401 - fixtures
    buyer,
    google_verify,
    product_ids,
    stores,
    tier,
)

# ============================================================ push channel


@pytest.fixture
def sent(monkeypatch):
    """Capture what would be handed to FCM."""
    from firebase_admin import messaging

    payloads: list = []

    def fake_send(payload, app=None):  # noqa: ANN001, ANN202
        payloads.append(payload)
        ok = SimpleNamespace(success=True, exception=None)
        return SimpleNamespace(
            responses=[ok] * len(payload.tokens),
            success_count=len(payload.tokens),
            failure_count=0,
        )

    monkeypatch.setattr(firebase_provider, "_configured", lambda: True)
    monkeypatch.setattr(firebase_provider, "get_app", lambda: None)
    monkeypatch.setattr(messaging, "send_each_for_multicast", fake_send)
    return payloads


async def test_ordinary_push_uses_the_named_android_channel_and_default_sound(sent):
    provider = firebase_provider.FirebasePushProviderImpl()
    await provider.send_multicast(
        ["token-1"],
        PushMessage(title="Astrofrekans", body="Raporun hazır.", data={"event": "ai_report_ready"}),
    )
    android = sent[0].android
    assert android.notification.channel_id == "astrofrekans_default"
    assert android.notification.sound == "default"
    assert android.priority == "high"
    # Deep-link data untouched.
    assert sent[0].data == {"event": "ai_report_ready"}


async def test_call_push_stays_data_only_without_a_channel(sent):
    provider = firebase_provider.FirebasePushProviderImpl()
    await provider.send_data(["token-1"], DataPushMessage(data={"event": "incoming_call"}))
    assert sent[0].notification is None
    assert sent[0].android.notification is None


# ================================================== firebase check_revoked


@pytest.fixture
def sdk(monkeypatch):
    """The real provider over a stubbed firebase_admin.auth.verify_id_token."""
    from firebase_admin import auth

    calls: list[dict] = []
    outcome: dict = {"raise": None}

    def fake_verify(token, app=None, check_revoked=False, clock_skew_seconds=0):  # noqa: ANN001, ANN202
        calls.append({"check_revoked": check_revoked})
        if outcome["raise"] is not None:
            raise outcome["raise"]
        return {"uid": "uid-1", "email": "fb@example.com", "firebase": {"sign_in_provider": "password"}}

    monkeypatch.setattr(firebase_provider, "_configured", lambda: True)
    monkeypatch.setattr(firebase_provider, "get_app", lambda: None)
    monkeypatch.setattr(auth, "verify_id_token", fake_verify)
    return SimpleNamespace(calls=calls, outcome=outcome, provider=firebase_provider.FirebaseIdentityProviderImpl())


@pytest.mark.parametrize("flag", [False, True])
async def test_the_setting_decides_whether_firebase_is_asked(sdk, monkeypatch, flag):
    from app.core.config import settings

    monkeypatch.setattr(settings, "firebase_check_revoked", flag)
    identity = await sdk.provider.verify_id_token("id-token")
    assert identity.uid == "uid-1"
    assert sdk.calls == [{"check_revoked": flag}]


async def test_revoked_disabled_and_deleted_accounts_are_refused(sdk, monkeypatch):
    from firebase_admin import auth

    from app.core.config import settings
    from app.services.firebase.provider import (
        FirebaseAccountDisabled,
        FirebaseTokenInvalid,
        FirebaseTokenRevoked,
    )

    monkeypatch.setattr(settings, "firebase_check_revoked", True)
    for error, expected, status in [
        (auth.RevokedIdTokenError("revoked"), FirebaseTokenRevoked, 401),
        (auth.UserDisabledError("disabled"), FirebaseAccountDisabled, 403),
        (auth.UserNotFoundError("gone"), FirebaseTokenInvalid, 401),
    ]:
        sdk.outcome["raise"] = error
        with pytest.raises(expected) as caught:
            await sdk.provider.verify_id_token("id-token")
        assert caught.value.status_code == status


async def test_firebase_unreachable_is_a_server_error_not_a_sign_out(sdk, monkeypatch, caplog):
    from firebase_admin import exceptions as firebase_exceptions

    from app.core.config import settings
    from app.services.firebase.provider import FirebaseError

    monkeypatch.setattr(settings, "firebase_check_revoked", True)
    sdk.outcome["raise"] = firebase_exceptions.UnavailableError("backend unavailable")
    with pytest.raises(FirebaseError) as caught:
        await sdk.provider.verify_id_token("secret-id-token-value")
    assert caught.value.status_code == 502
    assert caught.value.code == "firebase_unavailable"
    assert "secret-id-token-value" not in caplog.text


async def test_revoked_token_through_the_api_in_both_modes(client, monkeypatch):
    from app.core.config import settings
    from app.services.firebase import factory

    monkeypatch.setattr(settings, "firebase_provider", "fake")
    monkeypatch.setattr(settings, "firebase_project_id", "astrofrekans-test")
    providers = factory.fake_providers()
    factory.set_firebase(providers)
    try:
        providers.identity.register("fb-id-token-revoked-f4", uid="uid-revoked", email="rv@example.com")
        headers = {"Authorization": "Bearer fb-id-token-revoked-f4"}
        assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 200
        providers.identity.revoked.add("fb-id-token-revoked-f4")

        monkeypatch.setattr(settings, "firebase_check_revoked", False)
        # Default: a revoked token still works until it expires (<= 1 h).
        assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 200

        monkeypatch.setattr(settings, "firebase_check_revoked", True)
        refused = await client.get("/api/v1/users/me", headers=headers)
        assert refused.status_code == 401
        assert refused.json()["error"]["code"] == "firebase_token_revoked"
    finally:
        factory.set_firebase(None)


# ======================================================== store product ids


def test_the_catalogue_has_the_expected_products_and_types():
    from app.domain.payments import StoreProductType
    from app.services.payments.catalog import CATALOG, COINS, COSMIC_PLUS, PREMIUM

    by_code = {d.code: d for d in CATALOG}
    assert len(by_code) == len(CATALOG), "duplicate code"
    subs = {"premium_monthly": PREMIUM, "premium_yearly": PREMIUM,
            "cosmic_plus_monthly": COSMIC_PLUS, "cosmic_plus_yearly": COSMIC_PLUS}
    for code, entitlement in subs.items():
        assert by_code[code].product_type is StoreProductType.SUBSCRIPTION
        assert by_code[code].entitlement_code == entitlement
    for code, coins in {"coins_120": 120, "coins_350": 350, "coins_800": 800}.items():
        assert by_code[code].product_type is StoreProductType.CONSUMABLE
        assert (by_code[code].entitlement_code, by_code[code].coins) == (COINS, coins)
    for code in ("natal_report", "synastry_report", "annual_forecast_report", "ai_pre_analysis"):
        assert by_code[code].product_type is StoreProductType.CONSUMABLE
    # No non-consumables: nothing to "restore" except subscriptions.
    assert not [d for d in CATALOG if d.product_type is StoreProductType.NON_CONSUMABLE]


def test_store_ids_are_checked_for_typos_and_duplicates():
    import json

    from app.services.payments.catalog import store_catalog_problems

    good = {
        "premium_monthly": {"apple": "com.astrofrekans.premium.monthly", "google": "premium_monthly"},
        "premium_yearly": {"apple": "com.astrofrekans.premium.yearly", "google": "premium_yearly"},
        "coins_120": {"google": "coins_120"},
    }
    assert store_catalog_problems(json.dumps(good)) == []
    assert store_catalog_problems("") == []

    bad = {
        "premium_montly": {"google": "x"},
        "premium_monthly": {"google": "premium"},
        "premium_yearly": {"google": "premium", "amazon": "y"},
    }
    problems = store_catalog_problems(json.dumps(bad))
    assert any("unknown product code 'premium_montly'" in p for p in problems)
    assert any("google id 'premium' is used by both premium_monthly and premium_yearly" in p for p in problems)
    assert any("unknown store 'amazon'" in p for p in problems)
    assert store_catalog_problems("{not json") == ["STORE_PRODUCT_IDS is not valid JSON"]


def test_production_refuses_bad_store_ids(monkeypatch):
    import json

    from app.core.config import settings

    monkeypatch.setattr(settings, "store_product_ids", json.dumps({"premium_montly": {"google": "x"}}))
    problems: list[str] = []
    monkeypatch.setattr(settings, "environment", "production")
    try:
        settings.assert_production_ready()
    except RuntimeError as exc:
        problems.append(str(exc))
    except Exception as exc:  # noqa: BLE001 - whatever the refusal type is
        problems.append(str(exc))
    assert problems and "premium_montly" in problems[0]


async def test_a_code_removed_from_the_catalogue_is_no_longer_offered(db_session):
    from sqlalchemy import select

    from app.db.models.payments import StoreProduct
    from app.domain.payments import ClientPlatform
    from app.services.payments.catalog import StoreCatalogService

    db_session.add(StoreProduct(
        code="old_lifetime_pass", product_type="non_consumable", entitlement_code="old",
        units_per_purchase=1, google_product_id="old_lifetime_pass", active=True,
    ))
    await db_session.flush()
    offered = await StoreCatalogService(db_session).for_platform(ClientPlatform.ANDROID)
    assert "old_lifetime_pass" not in {p.code for p in offered}
    row = await db_session.scalar(select(StoreProduct).where(StoreProduct.code == "old_lifetime_pass"))
    assert row.active is False


# ============================================== plans end to end (Google)


async def test_google_plan_lifecycle_free_premium_upgrade_duplicate_expiry(
    client, buyer, stores, monkeypatch, session_factory  # noqa: F811
):
    """Free -> Premium -> upgrade to Kozmik+ (Play replaces the purchase) ->
    a store notification delivered twice -> the subscription expires."""
    from datetime import timedelta

    from sqlalchemy import select

    from app.core.config import settings
    from app.db.models.payments import StorePurchase
    from app.services.payments.purchases import google_account_id

    monkeypatch.setattr(settings, "premium_gating_enabled", True)
    monkeypatch.setattr(
        settings,
        "store_product_ids",
        product_ids({"cosmic_plus_monthly": {"apple": None, "google": "cosmic_plus_monthly"}}),
    )
    google = stores["google"]
    account = google_account_id(buyer["id"])
    headers = buyer["headers"]

    async def wallet() -> dict:
        return (await client.get("/api/v1/coins/wallet", headers=headers)).json()

    async def can(path: str) -> bool:
        return (await client.get(path, headers=headers)).status_code == 200

    # Free: no bonus, plan features locked.
    assert await tier(client, buyer) == "free"
    assert (await wallet())["bonus_granted"] == 0
    assert not await can("/api/v1/forecasts/monthly")

    # Premium: monthly bonus once, premium features on, Kozmik+ features off.
    google.add_subscription("tok-f4-premium-0001", product_id="premium_monthly", account=account)
    assert (await google_verify(client, buyer, "tok-f4-premium-0001")).status_code == 200
    assert await tier(client, buyer) == "premium"
    first = await wallet()
    assert (first["bonus_granted"], first["balance"]) == (settings.monthly_coins_premium,) * 2
    assert (await wallet())["bonus_granted"] == 0
    assert await can("/api/v1/forecasts/monthly")
    assert not await can("/api/v1/forecasts/yearly")

    # Upgrade: the new Play purchase names the old one; the old stops
    # entitling, the bonus tops up to Kozmik+'s - once.
    google.add_subscription(
        "tok-f4-cosmic-0001", product_id="cosmic_plus_monthly", account=account,
        linked_token="tok-f4-premium-0001",
    )
    upgraded = await google_verify(client, buyer, "tok-f4-cosmic-0001", product_code="cosmic_plus_monthly")
    assert upgraded.status_code == 200, upgraded.text
    assert await tier(client, buyer) == "cosmic_plus"
    async with session_factory() as session:
        statuses = {
            p.purchase_key[:6]: p.status
            for p in (await session.scalars(select(StorePurchase))).all()
        }
    assert sorted(statuses.values()) == ["active", "expired"]
    top_up = await wallet()
    assert top_up["bonus_granted"] == settings.monthly_coins_cosmic_plus - settings.monthly_coins_premium
    assert top_up["balance"] == settings.monthly_coins_cosmic_plus
    assert (await wallet())["bonus_granted"] == 0
    assert await can("/api/v1/forecasts/yearly")

    # The same store notification twice changes things once.
    renewal = google.push_body(
        {"subscriptionNotification": {"version": "1.0", "notificationType": 2,
                                      "purchaseToken": "tok-f4-cosmic-0001"}},
        message_id="f4-renewal",
    )
    auth = {"Authorization": google.push_authorization()}
    first_push = await client.post("/api/v1/webhooks/google/play", content=renewal, headers=auth)
    again = await client.post("/api/v1/webhooks/google/play", content=renewal, headers=auth)
    assert first_push.json()["outcome"] == "applied"
    assert again.json()["outcome"] == "duplicate"
    assert await tier(client, buyer) == "cosmic_plus"

    # Expiry: back to free, features locked, no new bonus; coins already
    # granted stay (the economy does not claw back a paid month's bonus).
    google.add_subscription(
        "tok-f4-cosmic-0001", product_id="cosmic_plus_monthly", account=account,
        state="SUBSCRIPTION_STATE_EXPIRED", expires_in=timedelta(days=-1), acknowledged=True,
        linked_token="tok-f4-premium-0001",
    )
    expiry = google.push_body(
        {"subscriptionNotification": {"version": "1.0", "notificationType": 13,
                                      "purchaseToken": "tok-f4-cosmic-0001"}},
        message_id="f4-expiry",
    )
    assert (await client.post("/api/v1/webhooks/google/play", content=expiry, headers=auth)).json()[
        "outcome"
    ] == "applied"
    assert await tier(client, buyer) == "free"
    assert not await can("/api/v1/forecasts/yearly")
    assert not await can("/api/v1/forecasts/monthly")
    after = await wallet()
    assert after["bonus_granted"] == 0
    assert after["balance"] == settings.monthly_coins_cosmic_plus
