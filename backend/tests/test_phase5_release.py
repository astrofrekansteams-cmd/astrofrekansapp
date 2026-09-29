"""Phase 5: release configuration - what production refuses to start with,
the seven store products, and revocation checks on sensitive actions."""

from __future__ import annotations

import json

import pytest

from app.core.config import settings
from app.services.payments.catalog import LEGACY_CODES, SELLABLE_CODES
from tests.test_payments import (  # noqa: F401 - fixtures
    buyer,
    google_verify,
    product_ids,
    stores,
)

API = "/api/v1"

SEVEN = {
    "premium_monthly", "premium_yearly", "cosmic_plus_monthly", "cosmic_plus_yearly",
    "coins_120", "coins_350", "coins_800",
}
GOOGLE_ONLY = {code: {"google": code} for code in SEVEN}


# ================================================================ helpers


@pytest.fixture
def production(monkeypatch):
    """A complete, correct production configuration (Android-first: Google
    Play verified, App Store not yet). Tests break one thing at a time."""
    good = {
        "environment": "production",
        "auth_mode": "hybrid",
        "jwt_secret": "p" * 48,
        "jwt_refresh_secret": "r" * 48,
        "cors_origins": "https://astrofrekans.org",
        "debug": False,
        "premium_gating_enabled": True,
        "ai_provider": "openai",
        "firebase_provider": "firebase",
        "realtime_provider": "firebase",
        "store_provider": "real",
        "apns_provider": "real",
        "external_payment_provider": "disabled",
        "mail_provider": "smtp",
        "smtp_host": "smtp.example.com",
        "mail_from": "noreply@example.com",
        "smtp_username": "release-user",
        "smtp_password": "release-password",
        "smtp_ssl": False,
        "smtp_starttls": True,
        "password_reset_url_base": "https://astrofrekansteams-cmd.github.io/astrofrekansapp/reset-password.html",
        "store_product_ids": json.dumps(GOOGLE_ONLY),
        "google_play_package_name": "com.astrofrekans.astrofrekans",
        "google_play_service_account_json": "{}",
        "google_pubsub_push_audience": "https://api.astrofrekans.org/api/v1/webhooks/google/play",
        "apple_bundle_id": None,
        "livekit_url": "wss://live.astrofrekans.org",
        "firebase_project_id": "astrofrekans",
        "ad_reward_verifier": "",
        "firebase_auth_emulator_host": None,
        "firestore_emulator_host": None,
        "firebase_database_emulator_host": None,
        "firebase_storage_emulator_host": None,
    }
    for name, value in good.items():
        monkeypatch.setattr(settings, name, value)
    return monkeypatch


def refusal() -> str:
    """The production refusal, or '' when the configuration may start."""
    try:
        settings.assert_production_ready()
    except RuntimeError as exc:
        return str(exc)
    return ""


# ====================================================== production refuses


def test_a_complete_production_configuration_starts(production):
    assert refusal() == ""


def test_mobile_only_production_needs_no_browser_origin(production):
    production.setattr(settings, "cors_origins", "")
    assert refusal() == ""


def test_password_reset_must_be_available_in_production(production):
    production.setattr(settings, "mail_provider", "disabled")
    assert "MAIL_PROVIDER=disabled" in refusal()


@pytest.mark.parametrize(
    ("name", "value", "says"),
    [
        ("store_provider", "fake", "STORE_PROVIDER=fake"),
        ("firebase_provider", "fake", "FIREBASE_PROVIDER=fake"),
        ("external_payment_provider", "fake", "EXTERNAL_PAYMENT_PROVIDER=fake"),
        ("ai_provider", "fake", "AI_PROVIDER=fake"),
        ("ad_reward_verifier", "mock", "AD_REWARD_VERIFIER=mock"),
        ("mail_provider", "log", "MAIL_PROVIDER=log"),
    ],
)
def test_mock_and_test_providers_are_refused(production, name, value, says):
    production.setattr(settings, name, value)
    assert says in refusal()


def test_empty_store_product_ids_say_what_is_missing(production):
    production.setattr(settings, "store_product_ids", "")
    message = refusal()
    assert "STORE_PRODUCT_IDS is empty" in message
    for code in SEVEN:
        assert code in message


def test_a_legacy_product_can_never_get_a_store_id(production):
    for code in LEGACY_CODES:
        production.setattr(settings, "store_product_ids", json.dumps({**GOOGLE_ONLY, code: {"google": code}}))
        assert f"{code} is a legacy product" in refusal()


def test_the_seven_products_need_ids_on_every_verified_store(production):
    missing = dict(GOOGLE_ONLY)
    missing.pop("coins_800")
    production.setattr(settings, "store_product_ids", json.dumps(missing))
    assert "no google id for coins_800" in refusal()

    production.setattr(settings, "store_product_ids", json.dumps(GOOGLE_ONLY))
    production.setattr(settings, "google_play_service_account_json", None)
    assert "google ids but Google Play" in refusal()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("password_reset_url_base", "https://localhost/reset-password.html"),
        ("password_reset_url_base", "https://10.0.2.2/reset-password.html"),
        ("livekit_url", "wss://192.168.1.20:7880"),
        ("cors_origins", "https://astrofrekans.org,http://localhost:3000"),
        ("google_pubsub_push_audience", "http://127.0.0.1:8000/api/v1/webhooks/google/play"),
    ],
)
def test_local_addresses_are_refused(production, name, value):
    production.setattr(settings, name, value)
    assert "must not point at a local address" in refusal()


def test_the_reset_url_must_be_https(production):
    production.setattr(settings, "password_reset_url_base", "http://astrofrekans.org/reset-password.html")
    assert "PASSWORD_RESET_URL_BASE must be an https URL" in refusal()


def test_an_incomplete_smtp_setup_does_not_start(production):
    production.setattr(settings, "mail_provider", "smtp")
    production.setattr(settings, "smtp_host", None)
    production.setattr(settings, "mail_from", None)
    message = refusal()
    assert "SMTP" in message or "MAIL_FROM" in message


def test_a_staging_firebase_project_or_the_emulator_does_not_start(production):
    production.setattr(settings, "firebase_project_id", "astrofrekans-staging")
    assert "looks like a staging/dev project" in refusal()
    production.setattr(settings, "firebase_project_id", "astrofrekans")
    production.setattr(settings, "firebase_auth_emulator_host", "localhost:9099")
    assert "FIREBASE_AUTH_EMULATOR_HOST points at the Firebase emulator" in refusal()


def test_revocation_is_checked_per_action_not_globally():
    assert settings.model_fields["firebase_check_revoked"].default is False


# =========================================================== store catalogue


def test_exactly_seven_products_are_sold():
    assert set(SELLABLE_CODES) == SEVEN
    assert set(LEGACY_CODES) == {"natal_report", "synastry_report", "annual_forecast_report", "ai_pre_analysis"}


async def test_legacy_products_stay_off_sale_even_with_ids(db_session, monkeypatch):
    from app.domain.payments import ClientPlatform
    from app.services.payments.catalog import StoreCatalogService

    everything = {code: {"google": f"g.{code}", "apple": f"a.{code}"} for code in SEVEN | set(LEGACY_CODES)}
    monkeypatch.setattr(settings, "store_product_ids", json.dumps(everything))
    for platform in (ClientPlatform.ANDROID, ClientPlatform.IOS):
        offered = await StoreCatalogService(db_session).for_platform(platform)
        assert {p.code for p in offered} == SEVEN
    catalog = StoreCatalogService(db_session)
    for code in LEGACY_CODES:
        row = await catalog.by_code(code)
        assert row is None  # inactive: not offered, not buyable


async def test_restoring_a_coin_pack_never_pays_twice(client, buyer, stores, monkeypatch):  # noqa: F811
    from app.services.payments.purchases import google_account_id

    monkeypatch.setattr(settings, "store_product_ids", product_ids({"coins_120": {"apple": None, "google": "coins_120"}}))
    google = stores["google"]
    google.add_product("tok-coins-restore-0001", product_id="coins_120", account=google_account_id(buyer["id"]))
    assert (await google_verify(client, buyer, "tok-coins-restore-0001", product_code="coins_120")).status_code == 200
    wallet = lambda: client.get(f"{API}/coins/wallet", headers=buyer["headers"])  # noqa: E731
    assert (await wallet()).json()["balance"] == 120

    for _ in range(2):  # a restore, then another
        restored = await client.post(
            f"{API}/billing/reconcile",
            headers=buyer["headers"],
            json={"google": [{"product_code": "coins_120", "purchase_token": "tok-coins-restore-0001"}]},
        )
        assert restored.status_code == 200, restored.text
        # Coins are never an entitlement: restore opens nothing.
        assert restored.json()["entitlements"]["premium"] is False
    assert (await wallet()).json()["balance"] == 120


# ================================================= revocation on sensitive


@pytest.fixture
def firebase_user(client, monkeypatch):
    from app.services.firebase import factory

    monkeypatch.setattr(settings, "firebase_provider", "fake")
    monkeypatch.setattr(settings, "firebase_project_id", "astrofrekans-test")
    monkeypatch.setattr(settings, "firebase_check_revoked", False)
    providers = factory.fake_providers()
    factory.set_firebase(providers)
    providers.identity.register("fb-id-token-sensitive-01", uid="uid-sensitive", email="s@example.com")
    yield providers, {"Authorization": "Bearer fb-id-token-sensitive-01"}
    factory.set_firebase(None)


SENSITIVE = [
    ("GET", "/auth/sessions", None),
    ("POST", "/auth/logout-all", None),
    ("POST", "/auth/change-password", {"current_password": "whatever-1", "new_password": "NewPass-2026!"}),
    ("POST", "/users/me/delete", {"confirm": True}),
    ("POST", "/billing/google/verify", {"product_code": "premium_monthly", "purchase_token": "tok-0000000000"}),
    ("POST", "/billing/reconcile", {"apple": [], "google": []}),
]


async def test_a_revoked_firebase_sign_in_still_reads_but_cannot_act(client, firebase_user):
    providers, headers = firebase_user
    assert (await client.get(f"{API}/users/me", headers=headers)).status_code == 200
    providers.identity.revoked.add("fb-id-token-sensitive-01")

    # Everyday reads keep working until the ID token expires (<= 1 h)...
    assert (await client.get(f"{API}/users/me", headers=headers)).status_code == 200
    # ...security-sensitive actions stop now.
    for method, path, body in SENSITIVE:
        response = await client.request(method, f"{API}{path}", headers=headers, json=body)
        assert response.status_code == 401, (path, response.text)
        assert response.json()["error"]["code"] == "firebase_token_revoked"


async def test_a_disabled_account_is_stopped_and_an_outage_is_not_a_sign_out(client, firebase_user, monkeypatch):
    from app.services.firebase.provider import FirebaseError

    providers, headers = firebase_user
    providers.identity.disabled.add("fb-id-token-sensitive-01")
    disabled = await client.get(f"{API}/auth/sessions", headers=headers)
    assert disabled.status_code == 403
    providers.identity.disabled.discard("fb-id-token-sensitive-01")

    original = providers.identity.verify_id_token

    async def unreachable(token, *, check_revoked=False):  # noqa: ANN001, ANN202
        if check_revoked:
            raise FirebaseError("Could not verify the sign-in token right now.")
        return await original(token, check_revoked=check_revoked)

    monkeypatch.setattr(providers.identity, "verify_id_token", unreachable)
    outage = await client.get(f"{API}/auth/sessions", headers=headers)
    assert outage.status_code == 502
    assert (await client.get(f"{API}/users/me", headers=headers)).status_code == 200


async def test_local_sign_ins_are_not_sent_to_firebase(client, buyer, monkeypatch):  # noqa: F811
    from app.services.firebase import factory

    calls: list = []

    class Boom:
        async def verify_id_token(self, *a, **k):  # noqa: ANN002, ANN003, ANN202
            calls.append(1)
            raise AssertionError("local JWT must not reach Firebase")

    monkeypatch.setattr(factory, "get_firebase", lambda: type("P", (), {"identity": Boom()})())
    response = await client.get(f"{API}/auth/sessions", headers=buyer["headers"])
    assert response.status_code == 200
    assert calls == []
