"""Payments: store policy, store verification, entitlements, ledger, settlement.

The properties worth breaking a build over:

* **Classification decides the rail.** Digital content is store-only; live 1:1
  voice/video is external-eligible; chat and written reports fail closed.
* **Nothing is granted on the client's say-so.** Entitlements exist only after
  Apple's signature (verified by Apple's own library) or Google's API answer.
* **A purchase belongs to one account.** Replaying a transaction id or a token
  from another account is refused.
* **Everything happens once.** Verify twice, notify twice, race a
  notification against a verification: one purchase, one entitlement, one
  ledger effect.
* **The ledger balances** and the B8 commission rounding survives refunds.
* **No refund percentage is invented.** The policy advises; a person decides.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, time, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models.marketplace import Expert, ExpertAvailability, ExpertService, ServiceOrder
from app.db.models.payments import (
    LedgerEntry,
    OrderLineItem,
    PaymentIntent,
    PaymentProviderEvent,
    PaymentTransaction,
    RefundRequest,
    StorePurchase,
    UserEntitlement,
)
from app.db.models.chat import NotificationOutbox
from app.db.models.service import ServiceDefinition
from app.db.models.user import User
from app.domain.marketplace import DeliveryType, ExpertStatus
from app.domain.payments import (
    ClientPlatform,
    PaymentClassification,
    PaymentRail,
    RefundDecision,
    RefundReason,
)
from app.services.payments import factory as payment_factory
from app.services.payments.classification import (
    PaymentClassificationService,
    PaymentRouter,
)
from app.services.payments.ledger import LedgerService, Posting, UnbalancedJournal
from app.services.payments.providers.external import (
    SIGNATURE_HEADER,
    FakeExternalMarketplacePaymentProvider,
)
from app.services.payments.providers.fakes import (
    FAKE_PACKAGE,
    FakeAppleStoreProvider,
    FakeGooglePlayProvider,
)
from app.services.payments.purchases import apple_account_token, google_account_id

API = "/api/v1"

APPLE_IDS = {
    "premium_monthly": "com.astro.premium.monthly",
    "premium_yearly": "com.astro.premium.yearly",
    "natal_report": "com.astro.report.natal",
}
GOOGLE_IDS = {
    "premium_monthly": "premium_monthly",
    "premium_yearly": "premium_yearly",
    "natal_report": "report_natal",
}


def product_ids(extra: dict | None = None) -> str:
    mapping = {
        code: {"apple": APPLE_IDS.get(code), "google": GOOGLE_IDS.get(code)}
        for code in set(APPLE_IDS) | set(GOOGLE_IDS)
    }
    mapping.update(extra or {})
    return json.dumps(mapping)


# ================================================================ fixtures


@pytest.fixture
def stores(monkeypatch):
    monkeypatch.setattr(settings, "store_provider", "fake")
    monkeypatch.setattr(settings, "external_payment_provider", "fake")
    monkeypatch.setattr(settings, "google_play_package_name", FAKE_PACKAGE)
    monkeypatch.setattr(settings, "store_product_ids", product_ids())
    apple = FakeAppleStoreProvider()
    google = FakeGooglePlayProvider()
    external = FakeExternalMarketplacePaymentProvider()
    payment_factory.set_payment_providers(apple=apple, google=google, external=external)
    yield {"apple": apple, "google": google, "external": external}
    payment_factory.set_payment_providers()


async def register(client: httpx.AsyncClient, email: str) -> dict:
    response = await client.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "Str0ngPassphrase!",
            "name": "Person",
            "birth_date": "1990-04-04",
            "birth_time": "11:00:00",
            "birth_place": "Istanbul",
        },
    )
    assert response.status_code == 201, response.text
    me = await client.get(
        f"{API}/auth/me",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    )
    return {
        "headers": {"Authorization": f"Bearer {response.json()['access_token']}"},
        "id": uuid.UUID(me.json()["id"]),
    }


@pytest.fixture
async def buyer(client, stores):
    return await register(client, "buyer@example.com")


async def tier(client, account) -> str:
    return (await client.get(f"{API}/auth/me", headers=account["headers"])).json()["subscription_tier"]


async def apple_verify(client, account, jws=None, *, product_code="premium_monthly", transaction_id=None):
    return await client.post(
        f"{API}/billing/apple/verify",
        headers=account["headers"],
        json={"product_code": product_code, "signed_transaction": jws, "transaction_id": transaction_id},
    )


async def google_verify(client, account, token, *, product_code="premium_monthly"):
    return await client.post(
        f"{API}/billing/google/verify",
        headers=account["headers"],
        json={"product_code": product_code, "purchase_token": token},
    )


async def rows(session_factory, model, *where):
    async with session_factory() as session:
        return list(await session.scalars(select(model).where(*where)))


# ============================================================ store policy


def test_classification_matrix():
    classify = PaymentClassificationService()
    digital = PaymentClassification.DIGITAL_STORE
    live = PaymentClassification.LIVE_PERSON_TO_PERSON
    review = PaymentClassification.REVIEW_REQUIRED

    # Automated AI report, premium subscription, tarot interpretation.
    assert classify.classify_digital().value is digital
    assert classify.classify_digital(amount_minor=4999).value is digital
    # Live 1:1, not recorded.
    assert classify.classify_expert_session("voice", amount_minor=10000).value is live
    assert classify.classify_expert_session("video", amount_minor=10000).value is live
    # Fail closed.
    assert classify.classify_expert_session("written_report", amount_minor=10000).value is review
    assert classify.classify_expert_session("chat", amount_minor=10000).value is review
    assert classify.classify_expert_session("hologram", amount_minor=10000).value is review
    # One-to-few is not person-to-person on either store.
    assert classify.classify_expert_session("video", amount_minor=10000, participants=3).value is review
    # Free is free.
    assert classify.classify_expert_session("video", amount_minor=0).value is PaymentClassification.FREE


def test_recording_would_revoke_the_live_exemption():
    """Google's 1:1 exemption needs 'not available for replay'."""
    classify = PaymentClassificationService()
    result = classify.classify_expert_session("video", amount_minor=10000, replayable=True)
    assert result.value is PaymentClassification.REVIEW_REQUIRED
    assert result.basis == "replayable"


def test_b10_recording_constraint_is_what_keeps_sessions_live():
    from app.services.payments.classification import live_sessions_replayable

    # The B10 check constraint exists, so sessions are not replayable.
    assert live_sessions_replayable() is False


def test_router_never_sends_digital_goods_outside_a_store():
    router = PaymentRouter()
    digital = PaymentClassification.DIGITAL_STORE
    assert router.route(digital, ClientPlatform.IOS) is PaymentRail.APPLE_STORE
    assert router.route(digital, ClientPlatform.ANDROID) is PaymentRail.GOOGLE_PLAY
    assert router.route(digital, ClientPlatform.WEB) is PaymentRail.NONE
    # A storefront is not a licence for alternative billing.
    assert router.route(digital, ClientPlatform.IOS, storefront="NLD") is PaymentRail.APPLE_STORE
    live = PaymentClassification.LIVE_PERSON_TO_PERSON
    assert router.route(live, ClientPlatform.IOS) is PaymentRail.EXTERNAL_MARKETPLACE
    assert router.route(PaymentClassification.REVIEW_REQUIRED, ClientPlatform.IOS) is PaymentRail.NONE


def test_policy_matrix_is_dated():
    from app.services.payments.classification import POLICY_LAST_VERIFIED, POLICY_MATRIX

    assert POLICY_LAST_VERIFIED == "2026-09-24"
    assert any(row.review_required for row in POLICY_MATRIX)


# ================================================================== status


async def test_status_is_booleans_only(client, buyer):
    response = await client.get(f"{API}/billing/status", headers=buyer["headers"])
    assert response.json() == {
        "apple_configured": True,
        "google_configured": True,
        "external_marketplace_configured": True,
    }


async def test_without_credentials_everything_else_still_works(client, registered, monkeypatch):
    monkeypatch.setattr(settings, "store_provider", "real")
    monkeypatch.setattr(settings, "external_payment_provider", "disabled")
    payment_factory.set_payment_providers()
    try:
        status = await client.get(f"{API}/billing/status", headers=registered["headers"])
        assert status.json() == {
            "apple_configured": False,
            "google_configured": False,
            "external_marketplace_configured": False,
        }
        apple = await apple_verify(client, registered, "x.y.z")
        assert apple.status_code == 503
        assert apple.json()["error"]["code"] == "store_provider_not_configured"
        google = await google_verify(client, registered, "token-123456789")
        assert google.status_code == 503
        hook = await client.post(f"{API}/webhooks/apple/app-store", json={"signedPayload": "x"})
        assert hook.status_code == 503
        chart = await client.get(f"{API}/astrology/natal-chart/me", headers=registered["headers"])
        assert chart.status_code == 200
    finally:
        payment_factory.set_payment_providers()


def test_production_refuses_payment_fakes(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "cors_origins", "https://app.example")
    monkeypatch.setattr(settings, "jwt_secret", "x" * 40)
    monkeypatch.setattr(settings, "jwt_refresh_secret", "y" * 40)
    monkeypatch.setattr(settings, "store_provider", "fake")
    monkeypatch.setattr(settings, "external_payment_provider", "fake")
    with pytest.raises(RuntimeError) as error:
        settings.assert_production_ready()
    assert "STORE_PROVIDER=fake" in str(error.value)
    assert "EXTERNAL_PAYMENT_PROVIDER=fake" in str(error.value)


def test_unsafe_apple_environments_are_not_configurable():
    from app.services.payments.providers.apple import LibraryBackedAppleVerifier

    for environment in ("Xcode", "LocalTesting"):
        with pytest.raises(ValueError):
            LibraryBackedAppleVerifier(
                root_certificates=[b"x"], bundle_id="b", app_apple_id=1,
                environment=environment, accept_sandbox=False, online_checks=False,
            )


async def test_products_list_ids_and_no_prices(client, buyer):
    ios = await client.get(f"{API}/billing/products", headers=buyer["headers"], params={"platform": "ios"})
    codes = {item["code"]: item for item in ios.json()["items"]}
    # Legacy natal_report has an id in this configuration, but legacy
    # products are never sold in the stores.
    assert set(codes) == set(APPLE_IDS) - {"natal_report"}
    assert codes["premium_yearly"]["store_product_id"] == "com.astro.premium.yearly"
    assert "price" not in ios.text
    # Not configured for any store: not sold.
    assert "ai_pre_analysis" not in codes

    web = await client.get(f"{API}/billing/products", headers=buyer["headers"], params={"platform": "web"})
    assert web.json()["items"] == []


# =================================================================== Apple


async def test_a_verified_apple_subscription_grants_premium(client, buyer, stores, session_factory):
    apple = stores["apple"]
    jws = apple.transaction(product_id=APPLE_IDS["premium_monthly"], app_account_token=str(buyer["id"]))
    assert await tier(client, buyer) == "free"

    response = await apple_verify(client, buyer, jws)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "active"
    assert body["environment"] == "production"
    assert body["entitlements"]["premium"] is True
    assert await tier(client, buyer) == "premium"
    # Nothing secret comes back.
    assert jws not in response.text

    # The charge is platform revenue from the store - never an expert payable.
    entries = await rows(session_factory, LedgerEntry)
    accounts = {(entry.account_type, entry.direction, entry.amount_minor) for entry in entries}
    assert accounts == {("store_clearing", "debit", 9999), ("platform_revenue", "credit", 9999)}


async def test_verifying_twice_changes_nothing(client, buyer, stores, session_factory):
    jws = stores["apple"].transaction(product_id=APPLE_IDS["premium_monthly"])
    first = await apple_verify(client, buyer, jws)
    second = await apple_verify(client, buyer, jws)
    assert first.json()["purchase_id"] == second.json()["purchase_id"]
    assert len(await rows(session_factory, StorePurchase)) == 1
    assert len(await rows(session_factory, UserEntitlement)) == 1
    assert len(await rows(session_factory, PaymentTransaction)) == 1
    assert len(await rows(session_factory, LedgerEntry)) == 2


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"forge": True}, "store_verification_failed"),
        ({"bundle_id": "com.somebody.else"}, "store_verification_failed"),
        ({"environment": "Sandbox"}, "store_environment_rejected"),
    ],
)
async def test_bad_apple_transactions_are_refused(client, buyer, stores, session_factory, kwargs, code):
    jws = stores["apple"].transaction(product_id=APPLE_IDS["premium_monthly"], **kwargs)
    response = await apple_verify(client, buyer, jws)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert await rows(session_factory, StorePurchase) == []
    assert await tier(client, buyer) == "free"


async def test_the_store_product_decides_not_the_request(client, buyer, stores):
    """Buy the monthly, claim the yearly: refused."""
    jws = stores["apple"].transaction(product_id=APPLE_IDS["premium_monthly"])
    response = await apple_verify(client, buyer, jws, product_code="premium_yearly")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "product_mismatch"


async def test_an_unknown_store_product_is_refused(client, buyer, stores):
    jws = stores["apple"].transaction(product_id="com.astro.not.in.catalogue")
    response = await apple_verify(client, buyer, jws)
    assert response.json()["error"]["code"] == "unknown_store_product"


async def test_another_account_cannot_take_a_purchase(client, buyer, stores, session_factory):
    jws = stores["apple"].transaction(product_id=APPLE_IDS["premium_monthly"])
    assert (await apple_verify(client, buyer, jws)).status_code == 200

    thief = await register(client, "thief@example.com")
    response = await apple_verify(client, thief, jws)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "purchase_owned_by_another_account"
    assert await tier(client, thief) == "free"
    owners = {row.user_id for row in await rows(session_factory, StorePurchase)}
    assert owners == {buyer["id"]}


async def test_a_purchase_stamped_for_another_account_is_refused(client, buyer, stores):
    jws = stores["apple"].transaction(
        product_id=APPLE_IDS["premium_monthly"], app_account_token=str(uuid.uuid4())
    )
    response = await apple_verify(client, buyer, jws)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "purchase_account_mismatch"


async def test_the_server_api_is_preferred_when_configured(client, buyer, stores):
    apple = stores["apple"]
    apple.transaction(product_id=APPLE_IDS["premium_monthly"], transaction_id="2000000111")
    response = await apple_verify(client, buyer, None, transaction_id="2000000111")
    assert response.status_code == 200
    assert "get_transaction_info" in apple.calls

    apple.unavailable = True
    down = await apple_verify(client, buyer, None, transaction_id="2000000111")
    assert down.status_code == 503
    assert down.json()["error"]["code"] == "store_provider_unavailable"


async def test_an_apple_refund_revokes_access(client, buyer, stores, session_factory):
    apple = stores["apple"]
    jws = apple.transaction(product_id=APPLE_IDS["premium_monthly"], transaction_id="777",
                            app_account_token=str(buyer["id"]))
    await apple_verify(client, buyer, jws)
    assert await tier(client, buyer) == "premium"

    refunded = apple.transaction(product_id=APPLE_IDS["premium_monthly"], transaction_id="777", revoked=True)
    payload = apple.notification(notification_type="REFUND", signed_transaction=refunded)
    response = await client.post(f"{API}/webhooks/apple/app-store", json={"signedPayload": payload})
    assert response.json()["outcome"] == "applied"
    assert await tier(client, buyer) == "free"

    [purchase] = await rows(session_factory, StorePurchase)
    assert purchase.status == "revoked"
    assert purchase.refunded_at is not None
    types = sorted(t.type for t in await rows(session_factory, PaymentTransaction))
    assert types == ["charge", "refund"]
    async with session_factory() as session:
        ledger = LedgerService(session)
        assert await ledger.balance(__import__("app.domain.payments", fromlist=["LedgerAccount"]).LedgerAccount.PLATFORM_REVENUE, currency="TRY") == 0

    pushes = await rows(session_factory, NotificationOutbox, NotificationOutbox.event_type == "refund_processed")
    assert len(pushes) == 1
    assert pushes[0].payload["data"] == {"event": "refund_processed"}
    assert "9999" not in json.dumps(pushes[0].payload)


async def test_a_notification_is_applied_once(client, buyer, stores, session_factory):
    apple = stores["apple"]
    jws = apple.transaction(product_id=APPLE_IDS["premium_monthly"], app_account_token=str(buyer["id"]))
    payload = apple.notification(notification_type="SUBSCRIBED", subtype="INITIAL_BUY",
                                 signed_transaction=jws, notification_uuid="uuid-fixed-1")
    first = await client.post(f"{API}/webhooks/apple/app-store", json={"signedPayload": payload})
    second = await client.post(f"{API}/webhooks/apple/app-store", json={"signedPayload": payload})
    assert first.json()["outcome"] == "applied"
    assert second.json()["outcome"] == "duplicate"
    assert len(await rows(session_factory, StorePurchase)) == 1
    assert len(await rows(session_factory, PaymentTransaction)) == 1
    [event] = await rows(session_factory, PaymentProviderEvent)
    # A hash, not the payload.
    assert len(event.payload_sha256) == 64
    assert "signedPayload" not in repr(vars(event))


async def test_a_notification_racing_the_client_converges(client, buyer, stores, session_factory):
    apple = stores["apple"]
    jws = apple.transaction(product_id=APPLE_IDS["premium_monthly"], app_account_token=str(buyer["id"]))
    payload = apple.notification(notification_type="SUBSCRIBED", signed_transaction=jws)
    await client.post(f"{API}/webhooks/apple/app-store", json={"signedPayload": payload})
    await apple_verify(client, buyer, jws)
    assert len(await rows(session_factory, StorePurchase)) == 1
    assert len(await rows(session_factory, UserEntitlement)) == 1
    assert len(await rows(session_factory, LedgerEntry)) == 2


async def test_forged_and_foreign_notifications_are_refused(client, buyer, stores, session_factory):
    apple = stores["apple"]
    jws = apple.transaction(product_id=APPLE_IDS["premium_monthly"])
    forged = apple.notification(notification_type="SUBSCRIBED", signed_transaction=jws, forge=True)
    foreign = apple.notification(notification_type="SUBSCRIBED", signed_transaction=jws, bundle_id="com.other")
    for payload in (forged, foreign, "not-a-jws"):
        response = await client.post(f"{API}/webhooks/apple/app-store", json={"signedPayload": payload})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_provider_notification"
    missing = await client.post(f"{API}/webhooks/apple/app-store", json={})
    assert missing.status_code == 401
    assert await rows(session_factory, PaymentProviderEvent) == []


async def test_an_unassociated_notification_waits_for_the_client(client, buyer, stores):
    apple = stores["apple"]
    jws = apple.transaction(product_id=APPLE_IDS["premium_monthly"])  # no account token
    payload = apple.notification(notification_type="SUBSCRIBED", signed_transaction=jws)
    response = await client.post(f"{API}/webhooks/apple/app-store", json={"signedPayload": payload})
    assert response.json()["outcome"] == "unassociated"
    # The client's own verification attaches it.
    assert (await apple_verify(client, buyer, jws)).status_code == 200


async def test_cancelled_apple_subscription_keeps_access_until_expiry(client, buyer, stores):
    apple = stores["apple"]
    jws = apple.transaction(product_id=APPLE_IDS["premium_monthly"], transaction_id="555",
                            app_account_token=str(buyer["id"]))
    await apple_verify(client, buyer, jws)
    renewal = apple.renewal(original_transaction_id="555", product_id=APPLE_IDS["premium_monthly"], auto_renew=False)
    payload = apple.notification(notification_type="DID_CHANGE_RENEWAL_STATUS", subtype="AUTO_RENEW_DISABLED",
                                 signed_transaction=jws, signed_renewal=renewal)
    await client.post(f"{API}/webhooks/apple/app-store", json={"signedPayload": payload})
    entitlements = (await client.get(f"{API}/billing/entitlements", headers=buyer["headers"])).json()
    assert entitlements["items"][0]["status"] == "cancelled_pending_expiry"
    assert entitlements["premium"] is True


async def test_grace_period_follows_policy(client, buyer, stores, monkeypatch):
    apple = stores["apple"]
    jws = apple.transaction(product_id=APPLE_IDS["premium_monthly"], transaction_id="666",
                            expires_in=timedelta(days=-1), app_account_token=str(buyer["id"]))
    renewal = apple.renewal(original_transaction_id="666", product_id=APPLE_IDS["premium_monthly"],
                            in_billing_retry=True, grace_until=datetime.now(UTC) + timedelta(days=3))
    payload = apple.notification(notification_type="DID_FAIL_TO_RENEW", subtype="GRACE_PERIOD",
                                 signed_transaction=jws, signed_renewal=renewal)
    await client.post(f"{API}/webhooks/apple/app-store", json={"signedPayload": payload})
    summary = (await client.get(f"{API}/billing/entitlements", headers=buyer["headers"])).json()
    assert summary["items"][0]["status"] == "grace_period"
    assert summary["premium"] is True

    monkeypatch.setattr(settings, "premium_during_grace_period", False)
    summary = (await client.get(f"{API}/billing/entitlements", headers=buyer["headers"])).json()
    assert summary["premium"] is False


# ============================================================== consumables


@pytest.mark.usefixtures("legacy_products_sellable")
async def test_a_consumable_is_one_credit_used_once(client, buyer, stores, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "store_product_ids", product_ids(
        {"ai_pre_analysis": {"apple": "com.astro.preanalysis", "google": None}}))
    jws = stores["apple"].transaction(product_id="com.astro.preanalysis", type_="Consumable",
                                      expires_in=None, transaction_id="c-1")
    for _ in range(2):
        response = await apple_verify(client, buyer, jws, product_code="ai_pre_analysis")
        assert response.status_code == 200
    assert response.json()["entitlements"]["credits"] == {"pre_analysis_credit": 1}

    consume = {"entitlement_code": "pre_analysis_credit", "consumer_ref": "pre-analysis-1"}
    first = await client.post(f"{API}/billing/credits/consume", headers=buyer["headers"], json=consume)
    retry = await client.post(f"{API}/billing/credits/consume", headers=buyer["headers"], json=consume)
    assert first.status_code == retry.status_code == 200
    assert first.json()["entitlement_id"] == retry.json()["entitlement_id"]

    other = await client.post(f"{API}/billing/credits/consume", headers=buyer["headers"],
                              json={"entitlement_code": "pre_analysis_credit", "consumer_ref": "pre-analysis-2"})
    assert other.status_code == 402
    assert other.json()["error"]["code"] == "no_credit_available"


@pytest.mark.usefixtures("legacy_products_sellable")
async def test_report_credits_are_not_spent_by_the_generic_endpoint(client, buyer, stores):
    """They are spent by POST /ai/reports, with the job that delivers the report."""
    jws = stores["apple"].transaction(product_id=APPLE_IDS["natal_report"], type_="Consumable",
                                      expires_in=None, transaction_id="c-2")
    assert (await apple_verify(client, buyer, jws, product_code="natal_report")).status_code == 200

    response = await client.post(f"{API}/billing/credits/consume", headers=buyer["headers"],
                                 json={"entitlement_code": "natal_report_credit", "consumer_ref": "report-request-1"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "credit_reserved_for_reports"
    summary = (await client.get(f"{API}/billing/entitlements", headers=buyer["headers"])).json()
    assert summary["credits"] == {"natal_report_credit": 1}

    reserved = await client.post(f"{API}/billing/credits/consume", headers=buyer["headers"],
                                 json={"entitlement_code": "pre_analysis_credit", "consumer_ref": "ai_report:abcdefgh"})
    assert reserved.status_code == 422


async def test_restore_reconciles(client, buyer, stores):
    apple = stores["apple"]
    jws = apple.transaction(product_id=APPLE_IDS["premium_yearly"])
    response = await client.post(
        f"{API}/billing/reconcile",
        headers=buyer["headers"],
        json={"apple": [{"product_code": "premium_yearly", "signed_transaction": jws},
                        {"product_code": "premium_monthly", "signed_transaction": "garbage.x.y"}]},
    )
    body = response.json()
    assert body["verified"] == 1
    assert body["failed"][0]["code"] == "store_verification_failed"
    assert body["entitlements"]["premium"] is True


# ================================================================== Google


async def test_a_verified_google_subscription_is_acknowledged_after(client, buyer, stores, session_factory):
    google = stores["google"]
    google.add_subscription("tok-sub-1-00000000", product_id="premium_monthly", account=google_account_id(buyer["id"]))
    response = await google_verify(client, buyer, "tok-sub-1-00000000")
    assert response.status_code == 200, response.text
    assert response.json()["entitlements"]["premium"] is True
    assert google.acknowledged == [("premium_monthly", "tok-sub-1-00000000")]
    [purchase] = await rows(session_factory, StorePurchase)
    assert purchase.acknowledged_at is not None
    # The token is not stored - only its hash.
    assert purchase.purchase_token_hash and purchase.purchase_token_hash != "tok-sub-1-00000000"
    assert "tok-sub-1-00000000" not in repr(vars(purchase))
    # Google does not report a price: recorded, not posted.
    [charge] = await rows(session_factory, PaymentTransaction)
    assert charge.amount_minor is None
    assert await rows(session_factory, LedgerEntry) == []


@pytest.mark.usefixtures("legacy_products_sellable")
async def test_a_pending_google_purchase_grants_nothing(client, buyer, stores):
    google = stores["google"]
    google.add_product("tok-pending-00000000", product_id="report_natal", state="PENDING")
    response = await google_verify(client, buyer, "tok-pending-00000000", product_code="natal_report")
    assert response.json()["status"] == "pending"
    assert response.json()["entitlements"]["credits"] == {}
    assert google.acknowledged == [] and google.consumed == []


@pytest.mark.usefixtures("legacy_products_sellable")
async def test_a_google_consumable_is_consumed_after_crediting(client, buyer, stores):
    google = stores["google"]
    google.add_product("tok-report-00000000", product_id="report_natal")
    response = await google_verify(client, buyer, "tok-report-00000000", product_code="natal_report")
    assert response.json()["entitlements"]["credits"] == {"natal_report_credit": 1}
    assert google.consumed == [("report_natal", "tok-report-00000000")]


async def test_a_failed_acknowledgement_keeps_the_entitlement_and_retries(client, buyer, stores, session_factory):
    google = stores["google"]
    google.add_subscription("tok-ack-00000000", product_id="premium_monthly")
    google.fail_acknowledge = True
    response = await google_verify(client, buyer, "tok-ack-00000000")
    assert response.json()["entitlements"]["premium"] is True
    [purchase] = await rows(session_factory, StorePurchase)
    assert purchase.acknowledged_at is None

    google.fail_acknowledge = False
    await google_verify(client, buyer, "tok-ack-00000000")
    assert google.acknowledged == [("premium_monthly", "tok-ack-00000000")]


@pytest.mark.parametrize(
    ("state", "expires_in", "premium"),
    [
        ("SUBSCRIPTION_STATE_CANCELED", timedelta(days=5), True),
        ("SUBSCRIPTION_STATE_CANCELED", timedelta(days=-1), False),
        ("SUBSCRIPTION_STATE_EXPIRED", timedelta(days=-1), False),
        ("SUBSCRIPTION_STATE_ON_HOLD", timedelta(days=-1), False),
        ("SUBSCRIPTION_STATE_PAUSED", timedelta(days=5), False),
        ("SUBSCRIPTION_STATE_IN_GRACE_PERIOD", timedelta(days=-1), True),
    ],
)
async def test_google_states_map_to_access(client, buyer, stores, state, expires_in, premium):
    google = stores["google"]
    google.add_subscription("tok-s-00000000", product_id="premium_monthly")
    await google_verify(client, buyer, "tok-s-00000000")
    google.add_subscription("tok-s-00000000", product_id="premium_monthly", state=state, expires_in=expires_in,
                            acknowledged=True)
    await google_verify(client, buyer, "tok-s-00000000")
    summary = (await client.get(f"{API}/billing/entitlements", headers=buyer["headers"])).json()
    assert summary["premium"] is premium
    assert await tier(client, buyer) == ("premium" if premium else "free")


async def test_rtdn_fetches_the_truth(client, buyer, stores):
    """The notification says 'renewed'; the API says expired. The API wins."""
    google = stores["google"]
    google.add_subscription("tok-rtdn-00000000", product_id="premium_monthly")
    await google_verify(client, buyer, "tok-rtdn-00000000")
    google.add_subscription("tok-rtdn-00000000", product_id="premium_monthly",
                            state="SUBSCRIPTION_STATE_EXPIRED", expires_in=timedelta(days=-1), acknowledged=True)
    fetches_before = len(google.fetches)

    body = google.push_body({"subscriptionNotification": {"version": "1.0", "notificationType": 2,
                                                          "purchaseToken": "tok-rtdn-00000000"}}, message_id="m-1")
    response = await client.post(f"{API}/webhooks/google/play", content=body,
                                 headers={"Authorization": google.push_authorization()})
    assert response.json()["outcome"] == "applied"
    assert len(google.fetches) == fetches_before + 1
    assert await tier(client, buyer) == "free"

    replay = await client.post(f"{API}/webhooks/google/play", content=body,
                               headers={"Authorization": google.push_authorization()})
    assert replay.json()["outcome"] == "duplicate"
    assert len(google.fetches) == fetches_before + 1


@pytest.mark.parametrize(
    "kwargs",
    [{"forge": True}, {"audience": "https://elsewhere"}, {"email": "someone@evil.invalid"},
     {"email_verified": False}, {"issuer": "https://evil.invalid"}],
)
async def test_unauthenticated_rtdn_is_refused(client, buyer, stores, session_factory, kwargs):
    google = stores["google"]
    body = google.push_body({"testNotification": {"version": "1.0"}})
    response = await client.post(f"{API}/webhooks/google/play", content=body,
                                 headers={"Authorization": google.push_authorization(**kwargs)})
    assert response.status_code == 401
    assert await rows(session_factory, PaymentProviderEvent) == []


async def test_rtdn_for_another_package_is_refused(client, buyer, stores):
    google = stores["google"]
    body = json.loads(google.push_body({"testNotification": {}}))
    import base64

    inner = json.loads(base64.b64decode(body["message"]["data"]))
    inner["packageName"] = "com.somebody.else"
    body["message"]["data"] = base64.b64encode(json.dumps(inner).encode()).decode()
    response = await client.post(f"{API}/webhooks/google/play", content=json.dumps(body).encode(),
                                 headers={"Authorization": google.push_authorization()})
    assert response.status_code == 401


async def test_a_voided_purchase_is_revoked(client, buyer, stores):
    google = stores["google"]
    google.add_subscription("tok-void-00000000", product_id="premium_monthly")
    await google_verify(client, buyer, "tok-void-00000000")
    body = google.push_body({"voidedPurchaseNotification": {"purchaseToken": "tok-void-00000000", "orderId": "GPA.1",
                                                            "productType": 1, "refundType": 1}})
    await client.post(f"{API}/webhooks/google/play", content=body,
                      headers={"Authorization": google.push_authorization()})
    assert await tier(client, buyer) == "free"


async def test_google_ownership_and_product_are_checked(client, buyer, stores):
    google = stores["google"]
    google.add_subscription("tok-own-00000000", product_id="premium_monthly")
    await google_verify(client, buyer, "tok-own-00000000")
    thief = await register(client, "gthief@example.com")
    assert (await google_verify(client, thief, "tok-own-00000000")).json()["error"]["code"] == "purchase_owned_by_another_account"

    google.add_subscription("tok-mis-00000000", product_id="premium_monthly")
    mismatch = await google_verify(client, buyer, "tok-mis-00000000", product_code="premium_yearly")
    assert mismatch.json()["error"]["code"] == "product_mismatch"

    google.add_subscription("tok-acct-00000000", product_id="premium_monthly", account="someone-else")
    wrong = await google_verify(client, buyer, "tok-acct-00000000")
    assert wrong.json()["error"]["code"] == "purchase_account_mismatch"

    unknown = await google_verify(client, buyer, "tok-never-issued-00000000")
    assert unknown.json()["error"]["code"] == "store_verification_failed"


async def test_a_test_purchase_is_refused_in_production(client, buyer, stores, monkeypatch):
    stores["google"].add_subscription("tok-test-00000000", product_id="premium_monthly", test=True)
    monkeypatch.setattr(settings, "environment", "production")
    response = await google_verify(client, buyer, "tok-test-00000000")
    assert response.json()["error"]["code"] == "store_environment_rejected"


async def test_tokens_and_signed_payloads_are_never_logged(client, buyer, stores, monkeypatch):
    from app.api.v1 import billing as billing_routes
    from app.services.payments import purchases, store_notifications

    recorded: list = []

    class Recorder:
        def _record(self, event, *args, **fields):
            recorded.append((event, fields))

        info = warning = error = exception = debug = _record

    for module in (billing_routes, purchases, store_notifications):
        monkeypatch.setattr(module, "logger", Recorder())

    google = stores["google"]
    google.add_subscription("tok-secret-value-123-00000000", product_id="premium_monthly")
    await google_verify(client, buyer, "tok-secret-value-123-00000000")
    jws = stores["apple"].transaction(product_id=APPLE_IDS["premium_yearly"], app_account_token=str(buyer["id"]))
    await apple_verify(client, buyer, jws, product_code="premium_yearly")
    await client.post(f"{API}/webhooks/apple/app-store", json={"signedPayload": "forged.payload.here"})

    blob = repr(recorded)
    assert recorded
    assert "tok-secret-value-123-00000000" not in blob
    assert jws not in blob and jws.split(".")[1] not in blob
    assert "forged.payload.here" not in blob


# ========================================================= orders & rails


@pytest.fixture
def wide_open(monkeypatch):
    monkeypatch.setattr(settings, "appointment_minimum_notice_minutes", 0)
    monkeypatch.setattr(settings, "appointment_buffer_before_minutes", 0)
    monkeypatch.setattr(settings, "appointment_buffer_after_minutes", 0)


@pytest.fixture
async def market(client, stores, wide_open, session_factory):
    """A user and an expert with voice, video, chat and written offerings."""
    from app.services.catalog.service import CatalogService

    user = await register(client, "patron@example.com")
    expert = await register(client, "astrologer@example.com")
    async with session_factory() as session:
        await CatalogService(session).seed()
        await session.commit()
        definition = await session.scalar(
            select(ServiceDefinition).where(
                ServiceDefinition.supports_voice.is_(True),
                ServiceDefinition.supports_video.is_(True),
                ServiceDefinition.supports_chat.is_(True),
                ServiceDefinition.supports_appointment.is_(True),
            ).limit(1)
        )
        profile = Expert(
            user_id=expert["id"], display_name="Astrologer", languages=["tr"], specialties=["astrology"],
            experience_years=3, timezone="Europe/Istanbul", status=ExpertStatus.ACTIVE.value,
            verified=True, rating_average=0, rating_count=0,
        )
        session.add(profile)
        await session.flush()
        offerings = {}
        for delivery in (DeliveryType.VIDEO, DeliveryType.VOICE, DeliveryType.CHAT):
            row = ExpertService(
                expert_id=profile.id, service_definition_id=definition.id,
                title=f"{delivery.value}", delivery_type=delivery.value, duration_minutes=60,
                price_minor=999, currency="TRY", active=True,
            )
            session.add(row)
            await session.flush()
            offerings[delivery.value] = row.id
        for weekday in range(7):
            session.add(ExpertAvailability(
                expert_id=profile.id, weekday=weekday, start_local_time=time(0, 0),
                end_local_time=time(23, 0), timezone="Europe/Istanbul", active=True,
            ))
        await session.commit()
        return {"user": user, "expert": expert, "expert_id": profile.id, "offerings": offerings,
                "definition": definition, "slot": 0}


async def order_for(client, market, delivery="video") -> uuid.UUID:
    now = datetime.now(UTC)
    slots = await client.get(
        f"{API}/experts/{market['expert_id']}/slots",
        headers=market["user"]["headers"],
        params={"service_id": str(market["offerings"][delivery]), "from": now.isoformat(),
                "to": (now + timedelta(days=5)).isoformat()},
    )
    # A slot starting within minutes can begin while the test runs and read
    # as "awaiting_completion" instead of "scheduled": skip those.
    upcoming = [
        slot for slot in slots.json()["slots"]
        if datetime.fromisoformat(slot["starts_at_utc"].replace("Z", "+00:00"))
        > now + timedelta(minutes=10)
    ]
    starts = upcoming[market["slot"]]["starts_at_utc"]
    market["slot"] += 1
    response = await client.post(
        f"{API}/orders", headers=market["user"]["headers"],
        json={"expert_service_id": str(market["offerings"][delivery]), "starts_at_utc": starts},
    )
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


async def pay_externally(client, market, stores, order_id, *, amount=999, key="pay-key-0001"):
    started = await client.post(f"{API}/orders/{order_id}/payment", headers=market["user"]["headers"],
                                json={"method": "external", "idempotency_key": key})
    assert started.status_code == 200, started.text
    external = stores["external"]
    reference = started.json()["client_handoff"].rsplit("/", 1)[-1]
    body = external.event_body(event_type="payment_succeeded", external_reference=reference,
                               amount_minor=amount, currency="TRY", event_id=f"evt-{order_id}")
    response = await client.post(f"{API}/webhooks/payments/external", content=body,
                                 headers={SIGNATURE_HEADER: external.sign(body)})
    return started, response, reference


async def test_a_hybrid_order_is_two_lines_two_classifications(client, market, session_factory):
    order_id = await order_for(client, market)
    view = (await client.get(f"{API}/orders/{order_id}/payment", headers=market["user"]["headers"])).json()
    by_type = {line["item_type"]: line for line in view["lines"]}
    assert by_type["expert_session"]["payment_classification"] == "live_person_to_person"
    assert by_type["expert_session"]["provider_rail"] == "external_marketplace"
    if "ai_pre_analysis" in by_type:
        # Not sold through a store here, so not part of the order - and never
        # bundled into the external payment.
        assert by_type["ai_pre_analysis"]["payment_classification"] == "digital_store"
        assert by_type["ai_pre_analysis"]["line_status"] == "excluded"
    assert view["payable_externally"] is True


@pytest.mark.usefixtures("legacy_products_sellable")
async def test_a_hybrid_digital_line_needs_a_store_purchase(client, market, stores, monkeypatch):
    monkeypatch.setattr(settings, "store_product_ids", product_ids(
        {"ai_pre_analysis": {"apple": "com.astro.preanalysis", "google": "pre_analysis"}}))
    if market["definition"].fulfillment_modes and "hybrid" not in market["definition"].fulfillment_modes:
        pytest.skip("catalogue service is not hybrid")
    order_id = await order_for(client, market)
    view = (await client.get(f"{API}/orders/{order_id}/payment", headers=market["user"]["headers"])).json()
    classes = {group["classification"]: group for group in view["groups"]}
    assert classes["digital_store"]["rail"] == "store"
    assert classes["live_person_to_person"]["rail"] == "external_marketplace"

    # Paying the live part alone does not pay the order.
    _, event, _ = await pay_externally(client, market, stores, order_id)
    view = (await client.get(f"{API}/orders/{order_id}/payment", headers=market["user"]["headers"])).json()
    assert view["order_status"] == "pending_payment"

    # The digital part with a verified store credit completes it.
    jws = stores["apple"].transaction(product_id="com.astro.preanalysis", type_="Consumable", expires_in=None)
    await apple_verify(client, market["user"], jws, product_code="ai_pre_analysis")
    done = await client.post(f"{API}/orders/{order_id}/payment", headers=market["user"]["headers"],
                             json={"method": "store_credit", "idempotency_key": "credit-key-1"})
    assert done.json()["order"]["order_status"] == "confirmed"
    assert done.json()["order"]["payment_status"] == "paid"


async def test_review_required_services_cannot_be_paid(client, market):
    order_id = await order_for(client, market, delivery="chat")
    response = await client.post(f"{API}/orders/{order_id}/payment", headers=market["user"]["headers"],
                                 json={"method": "external", "idempotency_key": "chat-pay-1"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "payment_policy_review_required"


async def test_recording_turns_off_external_payment(client, market, monkeypatch):
    from app.services.payments import classification

    order_id = await order_for(client, market)
    monkeypatch.setattr(classification, "live_sessions_replayable", lambda: True)
    response = await client.post(f"{API}/orders/{order_id}/payment", headers=market["user"]["headers"],
                                 json={"method": "external", "idempotency_key": "rec-pay-1"})
    assert response.json()["error"]["code"] == "payment_policy_review_required"


async def test_external_payment_disabled_is_a_clean_503(client, market, monkeypatch):
    from app.services.payments.providers.external import DisabledExternalPaymentProvider

    payment_factory.set_payment_providers(
        apple=payment_factory.get_apple_provider(), google=payment_factory.get_google_provider(),
        external=DisabledExternalPaymentProvider(),
    )
    order_id = await order_for(client, market)
    response = await client.post(f"{API}/orders/{order_id}/payment", headers=market["user"]["headers"],
                                 json={"method": "external", "idempotency_key": "dis-pay-1"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "external_payment_provider_not_configured"


async def test_only_a_verified_provider_event_pays_an_order(client, market, stores, session_factory):
    order_id = await order_for(client, market)
    # There is no way to say "paid": unknown fields are refused, and nothing
    # else changes the state.
    fake = await client.post(f"{API}/orders/{order_id}/payment", headers=market["user"]["headers"],
                             json={"method": "external", "idempotency_key": "x" * 10, "paid": True})
    assert fake.status_code in (200, 422)
    async with session_factory() as session:
        assert (await session.get(ServiceOrder, order_id)).payment_status == "pending"

    external = stores["external"]
    forged = external.event_body(event_type="payment_succeeded", external_reference="fx_nothing",
                                 amount_minor=999, currency="TRY")
    bad = await client.post(f"{API}/webhooks/payments/external", content=forged,
                            headers={SIGNATURE_HEADER: "0" * 64})
    assert bad.status_code == 401

    _, paid, reference = await pay_externally(client, market, stores, order_id, key="real-key-001")
    assert paid.json()["outcome"] == "applied"
    async with session_factory() as session:
        order = await session.get(ServiceOrder, order_id)
        assert (order.status, order.payment_status) == ("confirmed", "paid")

    replay_body = external.event_body(event_type="payment_succeeded", external_reference=reference,
                                      amount_minor=999, currency="TRY", event_id=f"evt-{order_id}")
    replay = await client.post(f"{API}/webhooks/payments/external", content=replay_body,
                               headers={SIGNATURE_HEADER: external.sign(replay_body)})
    assert replay.json()["outcome"] == "duplicate"
    assert replay.status_code == 200
    assert len(await rows(session_factory, PaymentTransaction)) == 1


async def test_an_amount_mismatch_does_not_pay(client, market, stores, session_factory):
    order_id = await order_for(client, market)
    _, response, _ = await pay_externally(client, market, stores, order_id, amount=1, key="mismatch-01")
    assert response.json()["outcome"] == "amount_mismatch"
    async with session_factory() as session:
        assert (await session.get(ServiceOrder, order_id)).payment_status == "pending"


async def test_the_commission_split_survives_to_the_ledger(client, market, stores, session_factory):
    """999 minor at 2000 bp: platform 199, expert 800 - B8's rounding."""
    order_id = await order_for(client, market)
    await pay_externally(client, market, stores, order_id)
    entries = await rows(session_factory, LedgerEntry)
    totals = {(e.account_type, e.direction): e.amount_minor for e in entries}
    assert totals[("external_provider_clearing", "debit")] == 999
    fee = totals[("platform_revenue", "credit")]
    net = totals[("expert_payable_pending", "credit")]
    assert fee + net == 999
    async with session_factory() as session:
        order = await session.get(ServiceOrder, order_id)
        assert (fee, net) == (order.platform_fee_minor, order.expert_net_minor)
    assert sum(e.amount_minor for e in entries if e.direction == "debit") == sum(
        e.amount_minor for e in entries if e.direction == "credit"
    )


async def test_the_call_gate_follows_verified_payment(client, market, stores, monkeypatch):
    from app.services.calls import factory as call_factory
    from app.services.calls.fake_provider import FakeRealtimeCommunicationProvider

    monkeypatch.setattr(settings, "realtime_provider", "fake")
    call_factory.set_call_provider(FakeRealtimeCommunicationProvider())
    try:
        order_id = await order_for(client, market)
        call = {"order_id": str(order_id), "call_type": "video"}
        denied = await client.post(f"{API}/calls", headers=market["user"]["headers"], json=call)
        assert denied.status_code == 403
        assert denied.json()["error"]["details"]["reason"] in ("payment_required", "order_state_pending_payment")

        await pay_externally(client, market, stores, order_id, key="call-gate-1")
        allowed = await client.post(f"{API}/calls", headers=market["user"]["headers"], json=call)
        assert allowed.status_code == 201, allowed.text
    finally:
        call_factory.set_call_provider(None)


async def test_order_payment_is_owner_only(client, market, stores):
    order_id = await order_for(client, market)
    stranger = await register(client, "nosy-payer@example.com")
    for method, path, body in (
        ("get", f"/orders/{order_id}/payment", None),
        ("post", f"/orders/{order_id}/payment", {"method": "external", "idempotency_key": "steal-0001"}),
        ("post", f"/orders/{order_id}/refund-requests", {"reason": "goodwill", "idempotency_key": "steal-0002"}),
    ):
        kwargs = {"json": body} if body else {}
        response = await getattr(client, method)(f"{API}{path}", headers=stranger["headers"], **kwargs)
        assert response.status_code == 404, path


# ================================================================= refunds


async def test_cancelling_a_paid_order_owes_money_back(client, market, stores, session_factory):
    order_id = await order_for(client, market)
    await pay_externally(client, market, stores, order_id, key="cancel-key-1")
    await client.post(f"{API}/orders/{order_id}/cancel", headers=market["user"]["headers"], json={})
    async with session_factory() as session:
        order = await session.get(ServiceOrder, order_id)
        assert order.payment_status == "refund_pending"
    [request] = await rows(session_factory, RefundRequest)
    assert request.status == "manual_review"
    assert request.amount_minor == 999
    assert request.decision == RefundDecision.MANUAL_REVIEW.value


async def test_refund_amounts_are_bounded(client, market, stores):
    order_id = await order_for(client, market)
    await pay_externally(client, market, stores, order_id, key="bound-key-1")
    too_much = await client.post(f"{API}/orders/{order_id}/refund-requests", headers=market["user"]["headers"],
                                 json={"reason": "goodwill", "amount_minor": 1000, "idempotency_key": "bound-r-1"})
    assert too_much.json()["error"]["code"] == "refund_amount_invalid"
    zero = await client.post(f"{API}/orders/{order_id}/refund-requests", headers=market["user"]["headers"],
                             json={"reason": "goodwill", "amount_minor": 0, "idempotency_key": "bound-r-2"})
    assert zero.status_code == 422
    ok = await client.post(f"{API}/orders/{order_id}/refund-requests", headers=market["user"]["headers"],
                           json={"reason": "goodwill", "amount_minor": 500, "idempotency_key": "bound-r-3"})
    assert ok.status_code == 201
    # The pending request counts against what is left.
    more = await client.post(f"{API}/orders/{order_id}/refund-requests", headers=market["user"]["headers"],
                             json={"reason": "goodwill", "amount_minor": 500, "idempotency_key": "bound-r-4"})
    assert more.json()["error"]["code"] == "refund_amount_invalid"


async def test_unpaid_orders_have_nothing_to_refund(client, market):
    order_id = await order_for(client, market)
    response = await client.post(f"{API}/orders/{order_id}/refund-requests", headers=market["user"]["headers"],
                                 json={"reason": "goodwill", "idempotency_key": "nothing-1"})
    assert response.json()["error"]["code"] == "nothing_to_refund"


async def test_partial_refunds_reverse_the_split_exactly(client, market, stores, session_factory):
    from app.services.payments.refunds import RefundService

    order_id = await order_for(client, market)
    await pay_externally(client, market, stores, order_id, key="partial-key")
    ids = []
    for amount, key in ((333, "part-1-aaaa"), (666, "part-2-bbbb")):
        response = await client.post(f"{API}/orders/{order_id}/refund-requests", headers=market["user"]["headers"],
                                      json={"reason": "goodwill", "amount_minor": amount, "idempotency_key": key})
        ids.append(uuid.UUID(response.json()["id"]))
    async with session_factory() as session:
        for refund_id in ids:
            await RefundService(session).approve(refund_id, reviewer="admin-1", provider=stores["external"])
        await session.commit()

    async with session_factory() as session:
        ledger = LedgerService(session)
        from app.domain.payments import LedgerAccount

        assert await ledger.balance(LedgerAccount.PLATFORM_REVENUE, currency="TRY") == 0
        assert await ledger.balance(LedgerAccount.EXPERT_PAYABLE_PENDING, currency="TRY") == 0
        assert await ledger.balance(LedgerAccount.EXTERNAL_PROVIDER_CLEARING, currency="TRY") == 0
        order = await session.get(ServiceOrder, order_id)
        assert order.payment_status == "refunded"
        intent = await session.scalar(select(PaymentIntent))
        assert intent.refunded_minor == 999
    types = sorted(t.type for t in await rows(session_factory, PaymentTransaction))
    assert types == ["charge", "partial_refund", "refund"]
    pushes = await rows(session_factory, NotificationOutbox, NotificationOutbox.event_type == "refund_processed")
    assert all("amount" not in json.dumps(p.payload) for p in pushes)


async def test_an_approved_refund_cannot_be_approved_again(client, market, stores, session_factory):
    from app.services.payments.refunds import RefundNotReviewable, RefundService

    order_id = await order_for(client, market)
    await pay_externally(client, market, stores, order_id, key="twice-key-1")
    response = await client.post(f"{API}/orders/{order_id}/refund-requests", headers=market["user"]["headers"],
                                 json={"reason": "technical_failure", "idempotency_key": "twice-r-1"})
    refund_id = uuid.UUID(response.json()["id"])
    async with session_factory() as session:
        await RefundService(session).approve(refund_id, reviewer="admin", provider=stores["external"])
        await session.commit()
    async with session_factory() as session:
        with pytest.raises(RefundNotReviewable):
            await RefundService(session).approve(refund_id, reviewer="admin", provider=stores["external"])
    assert len(stores["external"].refunds) == 1


def test_the_refund_policy_advises_and_invents_nothing():
    from app.services.payments.refunds import RefundPolicy

    policy = RefundPolicy()
    technical = policy.evaluate(reason=RefundReason.TECHNICAL_FAILURE, paid=True,
                                call_end_reasons=["provider_error"], appointment_status="confirmed",
                                cancellation_actor=None)
    assert technical.decision is RefundDecision.MANUAL_REVIEW
    assert technical.basis == "technical_evidence:provider_error"
    no_show = policy.evaluate(reason=RefundReason.NO_SHOW, paid=True, call_end_reasons=["no_show"],
                              appointment_status="no_show", cancellation_actor="expert")
    assert no_show.decision is RefundDecision.MANUAL_REVIEW
    assert "expert" in no_show.basis
    assert policy.evaluate(reason=RefundReason.GOODWILL, paid=False, call_end_reasons=[],
                           appointment_status=None, cancellation_actor=None).decision is RefundDecision.NOT_ELIGIBLE
    assert policy.evaluate(reason=RefundReason.STORE_REVERSAL, paid=True, call_end_reasons=[],
                           appointment_status=None, cancellation_actor=None).decision is RefundDecision.AUTO


async def test_a_chargeback_is_recorded_and_reversed(client, market, stores, session_factory):
    order_id = await order_for(client, market)
    _, _, reference = await pay_externally(client, market, stores, order_id, key="cb-key-0001")
    external = stores["external"]
    body = external.event_body(event_type="chargeback", external_reference=reference,
                               amount_minor=999, currency="TRY", event_id="evt-cb-1")
    response = await client.post(f"{API}/webhooks/payments/external", content=body,
                                 headers={SIGNATURE_HEADER: external.sign(body)})
    assert response.json()["outcome"] == "applied"
    types = sorted(t.type for t in await rows(session_factory, PaymentTransaction))
    assert types == ["charge", "chargeback"]


# ============================================================== settlement


async def test_without_a_hold_decision_nothing_is_released(client, market, stores, session_factory):
    from app.services.marketplace.orders import OrderService

    order_id = await order_for(client, market)
    await pay_externally(client, market, stores, order_id, key="hold-key-01")
    async with session_factory() as session:
        await OrderService(session).complete(await session.get(ServiceOrder, order_id))
        await session.commit()
    earnings = (await client.get(f"{API}/expert/earnings", headers=market["expert"]["headers"])).json()
    assert earnings["settlement_hold_days"] is None
    [balance] = earnings["balances"]
    assert balance["pending_minor"] == 800 and balance["available_minor"] == 0


async def test_after_the_hold_funds_become_available_and_payouts_are_admin_only(
    client, market, stores, session_factory, monkeypatch
):
    from app.services.marketplace.orders import OrderService
    from app.services.payments.settlement import PayoutNotAllowed, SettlementService

    monkeypatch.setattr(settings, "expert_settlement_hold_days", 0)
    order_id = await order_for(client, market)
    await pay_externally(client, market, stores, order_id, key="release-k1")
    async with session_factory() as session:
        await OrderService(session).complete(await session.get(ServiceOrder, order_id))
        await session.commit()
    [balance] = (await client.get(f"{API}/expert/earnings", headers=market["expert"]["headers"])).json()["balances"]
    assert (balance["pending_minor"], balance["available_minor"]) == (0, 800)

    async with session_factory() as session:
        settlement = SettlementService(session)
        with pytest.raises(PayoutNotAllowed):
            await settlement.create_payout(market["expert_id"], amount_minor=801, currency="TRY", created_by="admin")
        payout = await settlement.create_payout(market["expert_id"], amount_minor=800, currency="TRY", created_by="admin")
        with pytest.raises(PayoutNotAllowed):
            await settlement.mark_paid(payout.id, external_reference="bank-1")  # not approved yet
        await settlement.approve(payout.id, admin="admin")
        await settlement.start_processing(payout.id, provider="manual")
        await settlement.mark_paid(payout.id, external_reference="bank-1")
        await session.commit()

    [balance] = (await client.get(f"{API}/expert/earnings", headers=market["expert"]["headers"])).json()["balances"]
    assert (balance["available_minor"], balance["paid_minor"]) == (0, 800)
    listed = (await client.get(f"{API}/expert/payouts", headers=market["expert"]["headers"])).json()
    assert [p["status"] for p in listed] == ["paid"]

    # A user without an expert profile has no payouts view.
    denied = await client.get(f"{API}/expert/payouts", headers=market["user"]["headers"])
    assert denied.status_code in (403, 404)


async def test_a_refund_after_release_can_leave_a_negative_balance(
    client, market, stores, session_factory, monkeypatch
):
    from app.services.marketplace.orders import OrderService
    from app.services.payments.refunds import RefundService

    monkeypatch.setattr(settings, "expert_settlement_hold_days", 0)
    order_id = await order_for(client, market)
    await pay_externally(client, market, stores, order_id, key="neg-key-001")
    async with session_factory() as session:
        await OrderService(session).complete(await session.get(ServiceOrder, order_id))
        await session.commit()
    await client.get(f"{API}/expert/earnings", headers=market["expert"]["headers"])  # releases
    async with session_factory() as session:
        from app.services.payments.settlement import SettlementService

        settlement = SettlementService(session)
        payout = await settlement.create_payout(market["expert_id"], amount_minor=800, currency="TRY", created_by="admin")
        for step in (settlement.approve(payout.id, admin="a"),):
            await step
        await settlement.start_processing(payout.id, provider="manual")
        await settlement.mark_paid(payout.id, external_reference="bank-2")
        await session.commit()
    response = await client.post(f"{API}/orders/{order_id}/refund-requests", headers=market["user"]["headers"],
                                 json={"reason": "goodwill", "idempotency_key": "neg-r-0001"})
    async with session_factory() as session:
        await RefundService(session).approve(uuid.UUID(response.json()["id"]), reviewer="a",
                                             provider=stores["external"])
        await session.commit()
    [balance] = (await client.get(f"{API}/expert/earnings", headers=market["expert"]["headers"])).json()["balances"]
    assert balance["available_minor"] == -800


# ================================================================== ledger


async def test_the_ledger_refuses_unbalanced_and_duplicate_journals(db_session):
    from app.domain.payments import LedgerAccount, LedgerDirection, TransactionType

    ledger = LedgerService(db_session)
    with pytest.raises(UnbalancedJournal):
        await ledger.post(journal_key="bad:1", entry_type=TransactionType.ADJUSTMENT, currency="TRY",
                          postings=[Posting(LedgerAccount.PLATFORM_REVENUE, LedgerDirection.CREDIT, 100)])
    good = [Posting(LedgerAccount.STORE_CLEARING, LedgerDirection.DEBIT, 100),
            Posting(LedgerAccount.PLATFORM_REVENUE, LedgerDirection.CREDIT, 100)]
    assert await ledger.post(journal_key="good:1", entry_type=TransactionType.ADJUSTMENT, currency="TRY",
                             postings=good) is True
    assert await ledger.post(journal_key="good:1", entry_type=TransactionType.ADJUSTMENT, currency="TRY",
                             postings=good) is False
    assert await ledger.journal_is_balanced("good:1")


def test_split_proportionally_adds_up():
    from app.services.payments.ledger import split_proportionally

    gross, net = 999, 800
    parts, refunded = [], 0
    for amount in (1, 332, 333, 333):
        parts.append(split_proportionally(amount=amount, already=refunded, gross=gross, share=net))
        refunded += amount
    assert sum(parts) == net


def test_apple_milliunits_convert_exactly():
    from app.domain.payments import milliunits_to_minor

    assert milliunits_to_minor(99_990, "TRY") == 9999
    assert milliunits_to_minor(1_000_000, "JPY") == 1000
    assert milliunits_to_minor(1_500, "KWD") == 1500


# ===================================================== tiers & capabilities


async def test_premium_quota_applies_only_when_configured(client, buyer, stores, monkeypatch):
    from app.api.v1 import ai as ai_routes
    from app.core.rate_limit import Quota
    from app.services.ai.factory import set_ai_provider
    from app.services.ai.fake_provider import FakeAIProvider

    jws = stores["apple"].transaction(product_id=APPLE_IDS["premium_monthly"])
    await apple_verify(client, buyer, jws)
    summary = (await client.get(f"{API}/billing/entitlements", headers=buyer["headers"])).json()
    # No premium number decided: premium gets the free one.
    assert summary["capabilities"]["ai_chat_rate_limit"] == settings.ai_chat_rate_limit

    limiter = ai_routes._chat_limit.dependency
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(limiter, "quota", Quota(limit=1, window_seconds=60))
    monkeypatch.setattr(limiter, "premium_quota", Quota(limit=3, window_seconds=60))
    monkeypatch.setattr(settings, "ai_provider", "fake")
    set_ai_provider(FakeAIProvider())
    try:
        codes = [
            (await client.post(f"{API}/ai/chat", headers=buyer["headers"], json={"message": "Merhaba"})).status_code
            for _ in range(4)
        ]
    finally:
        set_ai_provider(None)
    assert codes[:3] != [429, 429, 429] and codes[3] == 429
    assert codes.count(429) == 1
