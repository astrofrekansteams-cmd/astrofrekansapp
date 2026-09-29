"""Spending AstroCoins on what a plan does not include.

The properties worth breaking a build over:

* **The price is the server's.** Every spend item comes from the catalogue;
  a gated route names the item that unlocks it.
* **One press, one charge.** The same reference never charges twice.
* **A failure costs nothing.** Work that fails before it answers is never
  charged; an AI job that ends without a report gives the coins back.
* **The AI is grounded.** A deep reading sends the drawn cards, their
  positions, the question and the deterministic synthesis - nothing else.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models.ai import AIReportJob
from app.db.models.chat import NotificationOutbox
from app.db.models.coins import CoinTransaction
from app.db.models.marketplace import Expert, ExpertAvailability, ExpertAvailabilityException
from app.db.models.user import User
from app.domain.ai import JobStatus
from app.domain.chat import OutboxStatus, PushEvent
from app.domain.marketplace import ExpertStatus
from app.services.ai import factory
from app.services.ai.fake_provider import FakeAIProvider
from app.services.coins.catalog import SPEND_ITEMS, comparison
from app.services.firebase import factory as firebase_factory
from app.services.notifications.outbox import OutboxService
from app.services.notifications.sender import NotificationSender

API = "/api/v1"


@pytest.fixture
def gating(monkeypatch):
    monkeypatch.setattr(settings, "premium_gating_enabled", True)


@pytest.fixture
def ai(monkeypatch) -> FakeAIProvider:
    monkeypatch.setattr(settings, "ai_provider", "fake")
    provider = FakeAIProvider()
    factory.set_ai_provider(provider)
    yield provider
    factory.set_ai_provider(None)


@pytest.fixture
def firebase(monkeypatch):
    monkeypatch.setattr(settings, "firebase_provider", "fake")
    monkeypatch.setattr(settings, "firebase_project_id", "astrofrekans-test")
    providers = firebase_factory.fake_providers()
    firebase_factory.set_firebase(providers)
    yield providers
    firebase_factory.set_firebase(None)


async def _user_id(client, account) -> uuid.UUID:
    return uuid.UUID((await client.get(f"{API}/auth/me", headers=account["headers"])).json()["id"])


async def _give_coins(session_factory, user_id: uuid.UUID, amount: int) -> None:
    from app.services.coins.service import CoinService

    async with session_factory() as session:
        await CoinService(session)._apply(
            user_id, amount, kind="ad_reward", reason="test", key=f"test:{uuid.uuid4().hex}"
        )
        await session.commit()


async def _balance(client, account) -> int:
    body = (await client.get(f"{API}/coins/wallet", headers=account["headers"])).json()
    return body["balance"]


async def _spends(session_factory) -> list[CoinTransaction]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(CoinTransaction).where(CoinTransaction.kind == "spend")
            )
        )


def _coins(ref: str) -> dict[str, str]:
    return {"X-Coin-Consumer-Ref": ref}


# ------------------------------------------------------------------ catalogue


async def test_every_spend_is_live_and_the_plans_compare(client, registered):
    body = (await client.get(f"{API}/coins/catalog", headers=registered["headers"])).json()
    items = {item["code"]: item for item in body["spend_items"]}
    assert set(items) == {item.code for item in SPEND_ITEMS}
    assert all(item["available"] for item in items.values())
    assert items["ai_deep_reading"]["price"] == 40
    assert items["special_analysis"]["price"] == 60
    assert items["single_premium_content"]["price"] == 30

    rows = {row["key"]: row for row in body["comparison"]}
    assert rows == {row["key"]: row for row in comparison()}
    for row in rows.values():
        assert set(row["cells"]) == {"free", "premium", "cosmic_plus"}
        assert set(row["cells"].values()) <= {"included", "coins", "none"}
        if "coins" in row["cells"].values():
            assert row["coin_item"] in items
    assert rows["ai_deep_reading"]["cells"]["cosmic_plus"] == "included"
    assert rows["monthly_coins"]["values"]["cosmic_plus"] == settings.monthly_coins_cosmic_plus


# ----------------------------------------------------- one gated route, paid


async def test_a_gated_route_names_its_coin_price(client, registered, gating):
    refused = await client.get(f"{API}/forecasts/monthly", headers=registered["headers"])
    assert refused.status_code == 403
    assert refused.json()["error"]["details"]["coin_item"] == "single_premium_content"


async def test_a_monthly_forecast_paid_with_coins_is_charged_once(
    client, registered, gating, session_factory
):
    headers = registered["headers"]
    broke = await client.get(
        f"{API}/forecasts/monthly", headers={**headers, **_coins("monthly-0001")}
    )
    assert broke.status_code == 402
    assert broke.json()["error"]["details"] == {
        "balance": 0,
        "required": 30,
        "item": "single_premium_content",
    }

    await _give_coins(session_factory, await _user_id(client, registered), 50)
    paid = await client.get(
        f"{API}/forecasts/monthly", headers={**headers, **_coins("monthly-0002")}
    )
    assert paid.status_code == 200, paid.text
    assert await _balance(client, registered) == 20

    retry = await client.get(
        f"{API}/forecasts/monthly", headers={**headers, **_coins("monthly-0002")}
    )
    assert retry.status_code == 200
    assert await _balance(client, registered) == 20
    [spend] = await _spends(session_factory)
    assert spend.amount == -30
    assert spend.idempotency_key == "spend:feature:monthly_forecast:monthly-0002"


async def test_a_failing_request_is_not_charged(client, registered, gating, session_factory):
    await _give_coins(session_factory, await _user_id(client, registered), 50)
    failed = await client.get(
        f"{API}/astrology/solar-return",
        headers={**registered["headers"], **_coins("solar-0001")},
        params={"latitude": 41.0},
    )
    assert failed.status_code == 422
    assert await _balance(client, registered) == 50
    assert await _spends(session_factory) == []


async def test_a_bad_reference_is_refused(client, registered, gating):
    response = await client.get(
        f"{API}/forecasts/monthly", headers={**registered["headers"], **_coins("no spaces!")}
    )
    assert response.status_code == 422


async def test_an_included_feature_is_never_charged(client, registered, session_factory):
    """Gating off (every plan includes everything): the header is ignored."""
    await _give_coins(session_factory, await _user_id(client, registered), 50)
    response = await client.get(
        f"{API}/forecasts/monthly",
        headers={**registered["headers"], **_coins("monthly-free-01")},
    )
    assert response.status_code == 200
    assert await _balance(client, registered) == 50


# ------------------------------------------------------- AI deep reading


async def _reading(client, registered, question: str | None = "Bu ay işim nasıl gider?") -> dict:
    body = {"deck_type": "tarot", "spread_code": "three_card"}
    if question:
        body["question"] = question
    response = await client.post(
        f"{API}/divination/readings", headers=registered["headers"], json=body
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _interpret(client, registered, reading_id: str, **body) -> httpx.Response:
    return await client.post(
        f"{API}/divination/readings/{reading_id}/interpret",
        headers=registered["headers"],
        json=body,
    )


async def test_a_deep_reading_needs_a_reference_and_coins(
    client, registered, gating, ai, session_factory
):
    reading = await _reading(client, registered)

    missing = await _interpret(client, registered, reading["id"])
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "report_consumer_ref_required"

    broke = await _interpret(client, registered, reading["id"], consumer_ref="deep-0001")
    assert broke.status_code == 402
    assert broke.json()["error"]["code"] == "insufficient_coins"
    assert ai.calls == []

    await _give_coins(session_factory, await _user_id(client, registered), 100)
    paid = await _interpret(client, registered, reading["id"], consumer_ref="deep-0002")
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "completed"
    assert await _balance(client, registered) == 60

    retry = await _interpret(client, registered, reading["id"], consumer_ref="deep-0002")
    assert retry.status_code == 200
    assert retry.json()["id"] == paid.json()["id"]
    assert await _balance(client, registered) == 60
    assert len(await _spends(session_factory)) == 1

    # A reading already interpreted is returned, not sold again.
    again = await _interpret(client, registered, reading["id"], consumer_ref="deep-0003")
    assert again.status_code == 200
    assert again.json()["id"] == paid.json()["id"]
    assert await _balance(client, registered) == 60
    # ...even without a reference: owning it needs no purchase.
    owned = await _interpret(client, registered, reading["id"])
    assert owned.status_code == 200
    assert owned.json()["id"] == paid.json()["id"]
    assert await _balance(client, registered) == 60


async def test_a_deep_reading_is_grounded_in_the_draw(
    client, registered, gating, ai, session_factory
):
    await _give_coins(session_factory, await _user_id(client, registered), 40)
    reading = await _reading(client, registered, "Yeni işe geçmeli miyim?")
    response = await _interpret(client, registered, reading["id"], consumer_ref="deep-ground-1")
    assert response.status_code == 200, response.text

    context = ai.calls[-1].input[0]["content"]
    assert "Yeni işe geçmeli miyim?" in context
    assert "deterministic_synthesis" in context
    for row in reading["items"]:
        assert row["item_id"] in context
        assert row["position_key"] in context


async def test_a_failed_deep_reading_gives_the_coins_back(
    client, registered, gating, ai, session_factory
):
    await _give_coins(session_factory, await _user_id(client, registered), 40)
    reading = await _reading(client, registered)
    ai.invalid_json_times = 50  # a permanent failure

    failed = await _interpret(client, registered, reading["id"], consumer_ref="deep-fail-01")
    assert failed.status_code == 502, failed.text
    assert await _balance(client, registered) == 40

    async with session_factory() as session:
        [job] = list(await session.scalars(select(AIReportJob)))
        kinds = sorted(
            row.kind for row in await session.scalars(select(CoinTransaction))
        )
    assert job.status == JobStatus.FAILED.value
    # The ledger keeps both sides: the spend and its refund.
    assert kinds == ["ad_reward", "refund", "spend"]

    # A new press is a new charge, and it delivers.
    ai.invalid_json_times = 0
    ok = await _interpret(client, registered, reading["id"], consumer_ref="deep-fail-02")
    assert ok.status_code == 200, ok.text
    assert await _balance(client, registered) == 0


async def test_a_cancelled_deep_reading_gives_the_coins_back(
    client, registered, gating, ai, session_factory
):
    await _give_coins(session_factory, await _user_id(client, registered), 40)
    reading = await _reading(client, registered)
    queued = await _interpret(
        client, registered, reading["id"], consumer_ref="deep-bg-0001", background=True
    )
    assert queued.status_code == 202, queued.text
    assert await _balance(client, registered) == 0

    # A second press while it is still generating joins the same job.
    joined = await _interpret(
        client, registered, reading["id"], consumer_ref="deep-bg-0002", background=True
    )
    assert joined.status_code == 202, joined.text
    assert joined.json()["id"] == queued.json()["id"]
    assert len(await _spends(session_factory)) == 1

    job_id = queued.json()["id"]
    cancelled = await client.post(
        f"{API}/ai/report-jobs/{job_id}/cancel", headers=registered["headers"]
    )
    assert cancelled.status_code == 200, cancelled.text
    assert await _balance(client, registered) == 40


# --------------------------------------------------- special analysis


async def test_a_paid_report_can_be_bought_with_coins(
    client, registered, gating, ai, session_factory
):
    headers = registered["headers"]
    body = {"report_type": "natal", "consumer_ref": "natal-coins-01"}
    unpaid = await client.post(f"{API}/ai/reports", headers=headers, json=body)
    assert unpaid.status_code == 402
    assert unpaid.json()["error"]["code"] == "report_payment_required"

    broke = await client.post(
        f"{API}/ai/reports", headers=headers, json={**body, "pay_with_coins": True}
    )
    assert broke.status_code == 402
    assert broke.json()["error"]["code"] == "insufficient_coins"

    await _give_coins(session_factory, await _user_id(client, registered), 70)
    paid = await client.post(
        f"{API}/ai/reports", headers=headers, json={**body, "pay_with_coins": True}
    )
    assert paid.status_code == 200, paid.text
    assert await _balance(client, registered) == 10
    [spend] = await _spends(session_factory)
    assert spend.amount == -60


# ------------------------------------------------ notification preferences


async def _queue(session_factory, user_id, event: PushEvent) -> uuid.UUID:
    async with session_factory() as session:
        row = await OutboxService(session).enqueue(
            event=event, user_id=user_id, dedupe_key=f"test:{uuid.uuid4().hex}"
        )
        await session.commit()
        return row.id


async def _deliver(session_factory, firebase, row_id):
    async with session_factory() as session:
        row = await session.get(NotificationOutbox, row_id)
        outcome = await NotificationSender(session, firebase).deliver(row)
        await session.commit()
        await session.refresh(row)
        return outcome, row.status


async def test_a_switched_off_notification_is_not_sent(
    client, registered, firebase, session_factory
):
    headers = registered["headers"]
    await client.post(
        f"{API}/devices/push", headers=headers, json={"token": "t" * 40, "platform": "android"}
    )
    user_id = await _user_id(client, registered)
    patched = await client.patch(
        f"{API}/users/me",
        headers=headers,
        json={"notification_prefs": {"ai_reports": False, "promotions": False}},
    )
    assert patched.status_code == 200, patched.text

    for event in (PushEvent.AI_REPORT_READY, PushEvent.PROMOTION):
        outcome, status = await _deliver(
            session_factory, firebase, await _queue(session_factory, user_id, event)
        )
        assert outcome.skipped_reason == "user_preference_off"
        assert status == OutboxStatus.SKIPPED.value
    assert firebase.push.all_tokens == []

    # What the user left on still goes out.
    outcome, _ = await _deliver(
        session_factory, firebase, await _queue(session_factory, user_id, PushEvent.DAILY_CONTENT)
    )
    assert outcome.delivered == 1

    # A transactional notice is never optional.
    outcome, _ = await _deliver(
        session_factory, firebase, await _queue(session_factory, user_id, PushEvent.PAYMENT_SUCCEEDED)
    )
    assert outcome.skipped_reason != "user_preference_off"


async def test_new_preferences_default_on(client, registered):
    me = (await client.get(f"{API}/users/me", headers=registered["headers"])).json()
    assert me["notification_prefs"]["ai_reports"] is True
    assert me["notification_prefs"]["expert_messages"] is True
    assert me["notification_prefs"]["promotions"] is False


# ------------------------------------------------------ available today


async def _expert(session_factory, email: str, weekdays, *, blocked=False) -> uuid.UUID:
    async with session_factory() as session:
        user = User(email=email, password_hash="x")
        session.add(user)
        await session.flush()
        row = Expert(
            user_id=user.id,
            display_name=email.split("@")[0],
            headline="Astrology",
            bio="Bio",
            languages=["tr"],
            specialties=["astrology"],
            experience_years=5,
            timezone="UTC",
            status=ExpertStatus.ACTIVE.value,
            verified=True,
            rating_average=0,
            rating_count=0,
        )
        session.add(row)
        await session.flush()
        for weekday in weekdays:
            session.add(
                ExpertAvailability(
                    expert_id=row.id,
                    weekday=weekday,
                    start_local_time=time(9, 0),
                    end_local_time=time(17, 0),
                    timezone="UTC",
                    active=True,
                )
            )
        if blocked:
            now = datetime.now(UTC)
            session.add(
                ExpertAvailabilityException(
                    expert_id=row.id,
                    exception_type="vacation",
                    starts_at_utc=now - timedelta(hours=1),
                    ends_at_utc=now + timedelta(days=2),
                )
            )
        await session.commit()
        return row.id


async def test_the_available_today_filter(client, registered, session_factory):
    today = datetime.now(UTC).weekday()
    open_id = await _expert(session_factory, "open@example.com", [today])
    await _expert(session_factory, "closed@example.com", [(today + 1) % 7])
    await _expert(session_factory, "away@example.com", [today], blocked=True)

    everyone = await client.get(f"{API}/experts", headers=registered["headers"])
    assert everyone.json()["total"] == 3

    today_only = await client.get(
        f"{API}/experts", headers=registered["headers"], params={"available_today": True}
    )
    assert today_only.status_code == 200, today_only.text
    assert [row["id"] for row in today_only.json()["items"]] == [str(open_id)]
