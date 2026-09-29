"""Paid AI reports: no verified credit (or included premium), no report.

The properties worth breaking a build over:

* **The API is the boundary, not Flutter.** A direct `POST /ai/reports` for a
  paid type without a credit creates no job, no report and no model call.
* **One reference, one payment.** The same `consumer_ref` replays the same
  job/report and never uses a second credit.
* **Credit and delivery move together.** The credit is reserved with the job
  and consumed in the commit that completes the report; a failed generation
  keeps the reservation for the retry; a refunded credit delivers nothing.
* **Neither the cache nor `refresh` is a way around payment.**
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.db.models.ai import AIReport, AIReportJob
from app.db.models.payments import UserEntitlement
from app.db.models.user import User
from app.domain.ai import JobStatus, Locale, ReportStatus, ReportType
from app.services.ai import factory, report_access
from app.services.ai.fake_provider import FakeAIProvider
from app.services.ai.queue import claim_next_job
from app.services.payments import factory as payment_factory
from app.services.payments.providers.external import FakeExternalMarketplacePaymentProvider
from app.services.payments.providers.fakes import (
    FAKE_PACKAGE,
    FakeAppleStoreProvider,
    FakeGooglePlayProvider,
)
from app.workers.ai_report_worker import AIReportWorker


# Every test here pays for a report with a store-bought credit - the legacy
# path, kept covered although the stores no longer sell it.
pytestmark = pytest.mark.usefixtures("legacy_products_sellable")

API = "/api/v1"

APPLE_IDS = {
    "premium_monthly": "com.astro.premium.monthly",
    "natal_report": "com.astro.report.natal",
    "synastry_report": "com.astro.report.synastry",
    "annual_forecast_report": "com.astro.report.annual",
}


# ================================================================ fixtures


@pytest.fixture
def ai(monkeypatch) -> FakeAIProvider:
    monkeypatch.setattr(settings, "ai_provider", "fake")
    provider = FakeAIProvider()
    factory.set_ai_provider(provider)
    yield provider
    factory.set_ai_provider(None)


@pytest.fixture
def apple(monkeypatch) -> FakeAppleStoreProvider:
    monkeypatch.setattr(settings, "store_provider", "fake")
    monkeypatch.setattr(settings, "google_play_package_name", FAKE_PACKAGE)
    monkeypatch.setattr(
        settings,
        "store_product_ids",
        json.dumps({code: {"apple": ref} for code, ref in APPLE_IDS.items()}),
    )
    provider = FakeAppleStoreProvider()
    payment_factory.set_payment_providers(
        apple=provider,
        google=FakeGooglePlayProvider(),
        external=FakeExternalMarketplacePaymentProvider(),
    )
    yield provider
    payment_factory.set_payment_providers()


async def account(client: httpx.AsyncClient, email: str = "payer@example.com") -> dict:
    response = await client.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "Str0ngPassphrase!",
            "name": "Payer",
            "birth_date": "1991-03-03",
            "birth_time": "08:15:00",
            "birth_place": "Istanbul",
        },
    )
    assert response.status_code == 201, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    me = (await client.get(f"{API}/auth/me", headers=headers)).json()
    return {"headers": headers, "id": uuid.UUID(me["id"])}


@pytest.fixture
async def payer(client, apple, ai) -> dict:
    return await account(client)


async def buy(client, apple, who, product="natal_report", *, transaction_id=None) -> str:
    """A consumable bought through the store and verified by the backend."""
    transaction_id = transaction_id or uuid.uuid4().hex[:12]
    jws = apple.transaction(
        product_id=APPLE_IDS[product],
        type_="Consumable",
        expires_in=None,
        transaction_id=transaction_id,
        app_account_token=str(who["id"]),
    )
    response = await client.post(
        f"{API}/billing/apple/verify",
        headers=who["headers"],
        json={"product_code": product, "signed_transaction": jws},
    )
    assert response.status_code == 200, response.text
    return transaction_id


async def subscribe(client, apple, who, *, expires_in=timedelta(days=30)) -> None:
    jws = apple.transaction(
        product_id=APPLE_IDS["premium_monthly"],
        expires_in=expires_in,
        app_account_token=str(who["id"]),
    )
    response = await client.post(
        f"{API}/billing/apple/verify",
        headers=who["headers"],
        json={"product_code": "premium_monthly", "signed_transaction": jws},
    )
    assert response.status_code == 200, response.text


async def report(client, who, report_type="natal", **extra) -> httpx.Response:
    return await client.post(
        f"{API}/ai/reports",
        headers=who["headers"],
        json={"report_type": report_type, **extra},
    )


async def credits(client, who) -> dict:
    summary = await client.get(f"{API}/billing/entitlements", headers=who["headers"])
    return summary.json()["credits"]


async def count(session_factory, model, *where) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(model).where(*where))


async def entitlement_rows(session_factory, user_id) -> list[UserEntitlement]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(UserEntitlement)
                .where(UserEntitlement.user_id == user_id)
                .order_by(UserEntitlement.created_at)
            )
        )


async def run_worker(session_factory) -> AIReportJob | None:
    async with session_factory() as session:
        job = await claim_next_job(session, worker_id="test-worker")
        if job is None:
            return None
        return await AIReportWorker(worker_id="test-worker").process(session, job)


def generations(ai: FakeAIProvider) -> int:
    return len(ai.calls)


# ============================================================ the policy


def test_the_price_list_names_real_catalogue_products():
    from app.services.payments.catalog import CATALOG

    codes = {definition.code for definition in CATALOG}
    assert set(report_access.PAID_REPORT_PRODUCTS.values()) <= codes
    assert report_access.report_entitlement_codes() == {
        "natal_report_credit",
        "synastry_report_credit",
        "annual_forecast_credit",
    }


async def test_a_free_report_needs_nothing(client, payer, ai, session_factory):
    response = await report(client, payer, "daily")
    assert response.status_code == 200, response.text
    assert await count(session_factory, AIReportJob) == 0
    assert await entitlement_rows(session_factory, payer["id"]) == []


# =================================================== the direct API bypass


async def test_a_direct_request_without_a_credit_gets_nothing(
    client, payer, ai, session_factory
):
    """The most important regression: Flutter gating is not the boundary."""
    missing_ref = await report(client, payer, "natal")
    assert missing_ref.status_code == 422
    assert missing_ref.json()["error"]["code"] == "report_consumer_ref_required"

    for body in (
        {"consumer_ref": "attempt-0001"},
        {"consumer_ref": "attempt-0002", "background": True},
        {"consumer_ref": "attempt-0003", "refresh": True},
    ):
        response = await report(client, payer, "natal", **body)
        assert response.status_code == 402, response.text
        error = response.json()["error"]
        assert error["code"] == "report_payment_required"
        assert error["details"] == {
            "product_code": "natal_report",
            "entitlement_code": "natal_report_credit",
        }

    queued = await client.post(
        f"{API}/ai/report-jobs",
        headers=payer["headers"],
        json={"report_type": "yearly", "consumer_ref": "attempt-0004"},
    )
    assert queued.status_code == 402

    assert await count(session_factory, AIReportJob) == 0
    assert await count(session_factory, AIReport) == 0
    assert generations(ai) == 0


async def test_a_client_cannot_claim_premium(client, payer, ai, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "paid_reports_included_in_premium", True)
    response = await client.post(
        f"{API}/ai/reports",
        headers=payer["headers"],
        json={"report_type": "natal", "consumer_ref": "attempt-0001", "is_premium": True, "paid": True},
    )
    assert response.status_code in (402, 422)
    assert await count(session_factory, AIReport) == 0


# ============================================================ paying once


async def test_a_verified_credit_pays_for_exactly_one_report(
    client, apple, payer, ai, session_factory
):
    await buy(client, apple, payer)
    assert await credits(client, payer) == {"natal_report_credit": 1}

    response = await report(client, payer, "natal", consumer_ref="natal-try-001")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["cached"] is False

    [credit] = await entitlement_rows(session_factory, payer["id"])
    assert credit.status == "consumed"
    assert credit.consumed_ref == "ai_report:natal-try-001"
    async with session_factory() as session:
        job = await session.scalar(select(AIReportJob))
        stored = await session.get(AIReport, uuid.UUID(body["id"]))
    assert job.status == JobStatus.COMPLETED.value
    assert job.payment_basis == "credit"
    assert job.entitlement_id == credit.id
    assert job.report_id == stored.id
    assert stored.entitlement_id == credit.id
    assert await credits(client, payer) == {}
    assert generations(ai) == 1


async def test_the_same_reference_replays_and_never_charges_twice(
    client, apple, payer, ai, session_factory
):
    await buy(client, apple, payer)
    await buy(client, apple, payer)
    first = await report(client, payer, "natal", consumer_ref="natal-try-001")
    assert first.status_code == 200
    calls = generations(ai)

    for background in (False, True):
        again = await report(client, payer, "natal", consumer_ref="natal-try-001", background=background)
        assert again.status_code == 200, again.text
        assert again.json()["id"] == first.json()["id"]
        assert again.json()["cached"] is True
    queued = await client.post(
        f"{API}/ai/report-jobs",
        headers=payer["headers"],
        json={"report_type": "natal", "consumer_ref": "natal-try-001"},
    )
    assert queued.status_code == 200
    assert queued.json()["id"] == first.json()["id"]

    assert generations(ai) == calls
    assert await count(session_factory, AIReportJob) == 1
    assert await credits(client, payer) == {"natal_report_credit": 1}


async def test_a_reference_is_bound_to_its_request(client, apple, payer, ai, session_factory):
    await buy(client, apple, payer)
    await buy(client, apple, payer, "annual_forecast_report")
    assert (await report(client, payer, "natal", consumer_ref="natal-try-001")).status_code == 200

    reused = await report(client, payer, "yearly", consumer_ref="natal-try-001")
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "report_credit_conflict"
    assert await credits(client, payer) == {"annual_forecast_credit": 1}


# ======================================================= sync, background


async def test_background_uses_the_same_gate_and_pays_on_delivery(
    client, apple, payer, ai, session_factory
):
    await buy(client, apple, payer)
    response = await report(client, payer, "natal", consumer_ref="natal-bg-0001", background=True)
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "queued"

    [credit] = await entitlement_rows(session_factory, payer["id"])
    assert credit.status == "reserved"
    assert await credits(client, payer) == {}  # held, not available twice
    assert generations(ai) == 0

    job = await run_worker(session_factory)
    assert job.status == JobStatus.COMPLETED.value
    [credit] = await entitlement_rows(session_factory, payer["id"])
    assert credit.status == "consumed"
    async with session_factory() as session:
        stored = await session.get(AIReport, job.report_id)
    assert stored.status == ReportStatus.COMPLETED.value
    assert stored.entitlement_id == credit.id

    polled = await client.get(f"{API}/ai/report-jobs/{job.id}", headers=payer["headers"])
    assert polled.json()["report_id"] == str(stored.id)


async def test_a_legacy_unpaid_job_is_refused_by_the_worker(
    client, payer, ai, session_factory
):
    """Queued before enforcement (no payment basis): judged again when it runs."""
    async with session_factory() as session:
        session.add(
            AIReportJob(
                user_id=payer["id"],
                report_type="natal",
                source_type="birth_profile",
                locale="tr",
                status=JobStatus.QUEUED.value,
                input_fingerprint="0" * 64,
                max_attempts=3,
            )
        )
        await session.commit()

    job = await run_worker(session_factory)
    assert job.status == JobStatus.FAILED.value
    assert job.error_code == "report_payment_required"
    assert job.report_id is None
    assert await count(session_factory, AIReport) == 0
    assert generations(ai) == 0


# ======================================================= failure, retry


async def test_a_failed_generation_keeps_the_credit_for_the_retry(
    client, apple, payer, ai, session_factory
):
    await buy(client, apple, payer)
    ai.invalid_json_times = 50  # fails validation every time: a permanent failure

    failed = await report(client, payer, "natal", consumer_ref="natal-fail-01")
    assert failed.status_code == 502, failed.text
    job_id = failed.json()["error"]["details"]["job_id"]
    [credit] = await entitlement_rows(session_factory, payer["id"])
    assert credit.status == "reserved"  # not consumed, not lost
    assert await count(session_factory, AIReport, AIReport.status == "completed") == 0

    ai.invalid_json_times = 0
    retry = await report(client, payer, "natal", consumer_ref="natal-fail-01")
    assert retry.status_code == 200, retry.text

    [credit] = await entitlement_rows(session_factory, payer["id"])
    assert credit.status == "consumed"
    async with session_factory() as session:
        jobs = list(await session.scalars(select(AIReportJob)))
    assert [str(job.id) for job in jobs] == [job_id]
    assert jobs[0].status == JobStatus.COMPLETED.value


async def test_a_transient_failure_answers_with_the_job_and_a_worker_finishes(
    client, apple, payer, ai, session_factory
):
    from app.services.ai.provider import AITimeout

    await buy(client, apple, payer)
    ai.raise_next(AITimeout())

    response = await report(client, payer, "natal", consumer_ref="natal-slow-01")
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "queued"
    assert (await entitlement_rows(session_factory, payer["id"]))[0].status == "reserved"

    job = await run_worker(session_factory)
    assert job.status == JobStatus.COMPLETED.value
    assert (await entitlement_rows(session_factory, payer["id"]))[0].status == "consumed"


async def test_a_died_inline_request_is_finished_by_a_worker(
    client, apple, payer, ai, session_factory
):
    """The inline claim has a lease; when it lapses the worker delivers."""
    from app.services.ai.queue import recover_stale_jobs

    await buy(client, apple, payer)
    async with session_factory() as session:
        from app.services.ai.factory import build_report_service

        user = await session.get(User, payer["id"])
        outcome = await build_report_service(session).request(
            user,
            report_type=ReportType.NATAL,
            source_id=None,
            locale=Locale.TR,
            consumer_ref="natal-crash-1",
        )
        assert outcome.run_inline
        # The request commits its reservation and then dies before running.
        outcome.job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

    async with session_factory() as session:
        assert await recover_stale_jobs(session) == 1
    job = await run_worker(session_factory)
    assert job.status == JobStatus.COMPLETED.value
    assert (await entitlement_rows(session_factory, payer["id"]))[0].status == "consumed"


# ============================================================ cache, refresh


async def test_a_paid_snapshot_is_not_charged_again(client, apple, payer, ai, session_factory):
    await buy(client, apple, payer)
    first = await report(client, payer, "natal", consumer_ref="natal-try-001")
    calls = generations(ai)

    # No credit left, a new reference, same inputs: the snapshot is theirs.
    again = await report(client, payer, "natal", consumer_ref="natal-try-002")
    assert again.status_code == 200, again.text
    assert again.json()["id"] == first.json()["id"]
    assert again.json()["cached"] is True
    assert generations(ai) == calls
    assert await count(session_factory, AIReportJob) == 1


async def test_an_unpaid_cached_report_does_not_bypass_payment(
    client, apple, payer, ai, session_factory, monkeypatch
):
    """A snapshot made while natal was free is not a free pass now."""
    with monkeypatch.context() as free:
        free.setattr(report_access, "PAID_REPORT_PRODUCTS", {})
        legacy = await report(client, payer, "natal")
        assert legacy.status_code == 200
    calls = generations(ai)

    refused = await report(client, payer, "natal", consumer_ref="natal-try-001")
    assert refused.status_code == 402

    await buy(client, apple, payer)
    paid = await report(client, payer, "natal", consumer_ref="natal-try-002")
    assert paid.status_code == 200
    # Delivered from the existing snapshot - paid for, not regenerated.
    assert paid.json()["id"] == legacy.json()["id"]
    assert generations(ai) == calls
    assert (await entitlement_rows(session_factory, payer["id"]))[0].status == "consumed"


async def test_refresh_is_a_new_paid_delivery(client, apple, payer, ai, session_factory):
    await buy(client, apple, payer)
    first = await report(client, payer, "natal", consumer_ref="natal-try-001")

    refused = await report(client, payer, "natal", consumer_ref="natal-try-002", refresh=True)
    assert refused.status_code == 402

    await buy(client, apple, payer)
    fresh = await report(client, payer, "natal", consumer_ref="natal-try-003", refresh=True)
    assert fresh.status_code == 200
    assert fresh.json()["id"] != first.json()["id"]
    assert [row.status for row in await entitlement_rows(session_factory, payer["id"])] == [
        "consumed",
        "consumed",
    ]


# ================================================================ premium


async def test_premium_includes_paid_reports_only_when_the_product_says_so(
    client, apple, payer, ai, session_factory, monkeypatch
):
    await subscribe(client, apple, payer)

    # Default: no product decision, so premium does not include them.
    summary = (await client.get(f"{API}/billing/entitlements", headers=payer["headers"])).json()
    assert summary["premium"] is True
    assert summary["capabilities"]["premium_reports"] is False
    assert (await report(client, payer, "natal", consumer_ref="natal-try-001")).status_code == 402

    monkeypatch.setattr(settings, "paid_reports_included_in_premium", True)
    summary = (await client.get(f"{API}/billing/entitlements", headers=payer["headers"])).json()
    assert summary["capabilities"]["premium_reports"] is True
    included = await report(client, payer, "natal")
    assert included.status_code == 200, included.text
    refreshed = await report(client, payer, "natal", refresh=True)
    assert refreshed.status_code == 200
    assert await count(session_factory, AIReportJob) == 0
    # No credit was involved (the only entitlement is the subscription).
    assert [row.kind for row in await entitlement_rows(session_factory, payer["id"])] == [
        "subscription"
    ]


async def test_an_expired_subscription_includes_nothing(
    client, apple, payer, ai, monkeypatch
):
    monkeypatch.setattr(settings, "paid_reports_included_in_premium", True)
    await subscribe(client, apple, payer, expires_in=timedelta(days=-1))
    response = await report(client, payer, "natal", consumer_ref="natal-try-001")
    assert response.status_code == 402


@pytest.mark.parametrize("grace_keeps_premium", [True, False])
async def test_the_grace_period_follows_the_premium_policy(
    client, payer, ai, session_factory, monkeypatch, grace_keeps_premium
):
    monkeypatch.setattr(settings, "paid_reports_included_in_premium", True)
    monkeypatch.setattr(settings, "premium_during_grace_period", grace_keeps_premium)
    async with session_factory() as session:
        session.add(
            UserEntitlement(
                user_id=payer["id"],
                entitlement_code="premium",
                kind="subscription",
                source="grant",
                unit_index=0,
                environment="production",
                status="grace_period",
                expires_at=datetime.now(UTC) - timedelta(hours=1),
                grace_until=datetime.now(UTC) + timedelta(days=3),
            )
        )
        await session.commit()

    response = await report(client, payer, "natal", consumer_ref="natal-try-001")
    assert response.status_code == (200 if grace_keeps_premium else 402)


async def test_a_premium_job_whose_premium_lapsed_is_not_delivered(
    client, payer, ai, session_factory, monkeypatch
):
    monkeypatch.setattr(settings, "paid_reports_included_in_premium", True)
    async with session_factory() as session:
        grant = UserEntitlement(
            user_id=payer["id"],
            entitlement_code="premium",
            kind="subscription",
            source="grant",
            unit_index=0,
            environment="production",
            status="active",
            expires_at=datetime.now(UTC) + timedelta(days=3),
        )
        session.add(grant)
        await session.commit()
        grant_id = grant.id

    queued = await report(client, payer, "natal", background=True)
    assert queued.status_code == 202

    async with session_factory() as session:
        (await session.get(UserEntitlement, grant_id)).status = "expired"
        await session.commit()
    job = await run_worker(session_factory)
    assert job.status == JobStatus.FAILED.value
    assert job.error_code == "report_payment_required"
    assert generations(ai) == 0


# =============================================================== refunds


async def test_a_refunded_credit_delivers_nothing(client, apple, payer, ai, session_factory):
    transaction_id = await buy(client, apple, payer)
    queued = await report(client, payer, "natal", consumer_ref="natal-refund-1", background=True)
    assert queued.status_code == 202

    refunded = apple.transaction(
        product_id=APPLE_IDS["natal_report"],
        type_="Consumable",
        expires_in=None,
        transaction_id=transaction_id,
        revoked=True,
    )
    hook = await client.post(
        f"{API}/webhooks/apple/app-store",
        json={"signedPayload": apple.notification(notification_type="REFUND", signed_transaction=refunded)},
    )
    assert hook.json()["outcome"] == "applied"
    assert (await entitlement_rows(session_factory, payer["id"]))[0].status == "revoked"

    job = await run_worker(session_factory)
    assert job.status == JobStatus.FAILED.value
    assert job.error_code == "report_credit_unavailable"
    assert generations(ai) == 0
    assert await count(session_factory, AIReport) == 0

    replay = await report(client, payer, "natal", consumer_ref="natal-refund-1")
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "report_credit_unavailable"


async def test_a_refund_during_generation_withholds_the_report(
    client, apple, payer, ai, session_factory, monkeypatch
):
    """Revoked after the gate, before delivery: generated, never delivered."""
    await buy(client, apple, payer)
    queued = await report(client, payer, "natal", consumer_ref="natal-race-01", background=True)
    assert queued.status_code == 202

    real_generate = FakeAIProvider.generate_structured

    async def generate_then_refund(self, request):
        result = await real_generate(self, request)
        async with session_factory() as other:
            row = await other.scalar(select(UserEntitlement).where(UserEntitlement.user_id == payer["id"]))
            row.status = "revoked"
            await other.commit()
        return result

    monkeypatch.setattr(FakeAIProvider, "generate_structured", generate_then_refund)

    job = await run_worker(session_factory)
    assert job.status == JobStatus.FAILED.value
    assert job.error_code == "report_credit_unavailable"
    async with session_factory() as session:
        rows = list(await session.scalars(select(AIReport)))
    assert len(rows) == 1
    assert rows[0].status == ReportStatus.FAILED.value
    assert rows[0].summary is None and rows[0].sections is None


# =================================================== ownership and IDOR


async def test_a_source_the_caller_does_not_own_is_refused_before_payment(
    client, apple, payer, ai, session_factory
):
    owner = await account(client, "owner@example.com")
    person = await client.post(
        f"{API}/saved-people",
        headers=owner["headers"],
        json={"name": "Deniz", "relation": "partner", "birth_date": "1994-08-21",
              "birth_time": "09:45:00", "birth_place": "London"},
    )
    synastry = await client.post(
        f"{API}/compatibility/synastry",
        headers=owner["headers"],
        json={"person_a": {"me": True}, "person_b": {"saved_person_id": person.json()["id"]}},
    )
    assert synastry.status_code == 200, synastry.text

    await buy(client, apple, payer, "synastry_report")
    stolen = await report(
        client, payer, "synastry", source_id=synastry.json()["report_id"], consumer_ref="syn-steal-01"
    )
    assert stolen.status_code == 404
    assert await credits(client, payer) == {"synastry_report_credit": 1}
    assert await count(session_factory, AIReportJob) == 0


async def test_a_reference_is_scoped_to_its_account(client, apple, payer, ai, session_factory):
    await buy(client, apple, payer)
    mine = await report(client, payer, "natal", consumer_ref="shared-ref-01")
    assert mine.status_code == 200

    other = await account(client, "other@example.com")
    theirs = await report(client, other, "natal", consumer_ref="shared-ref-01")
    assert theirs.status_code == 402  # not my report, not my credit

    async with session_factory() as session:
        job = await session.scalar(select(AIReportJob))
    peek = await client.get(f"{API}/ai/report-jobs/{job.id}", headers=other["headers"])
    assert peek.status_code == 404
    read = await client.get(f"{API}/ai/reports/{mine.json()['id']}", headers=other["headers"])
    assert read.status_code == 404


# ================================================================ logging


async def test_logs_carry_a_reference_fingerprint_not_the_reference(
    client, apple, payer, ai, monkeypatch
):
    from app.services.ai import reports as reports_module

    recorded: list = []

    class Recorder:
        def _record(self, event, *args, **fields):
            recorded.append((event, fields))

        info = warning = error = exception = debug = _record

    monkeypatch.setattr(reports_module, "logger", Recorder())
    await buy(client, apple, payer)
    assert (await report(client, payer, "natal", consumer_ref="secret-ref-000")).status_code == 200

    [(_, access)] = [item for item in recorded if item[0] == "ai_report_access"]
    assert access["outcome"] == "credit"
    assert access["product_code"] == "natal_report"
    assert access["consumer_ref_fingerprint"] and len(access["consumer_ref_fingerprint"]) == 12
    assert "secret-ref-000" not in repr(recorded)
