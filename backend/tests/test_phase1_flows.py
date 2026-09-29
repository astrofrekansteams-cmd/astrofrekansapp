"""Phase 1 critical user flows.

* One cancellation path: user and expert, order and appointment, all reach
  the same financial outcome - one refund review for a paid order, none for an
  unpaid one - and repeating a cancel never opens a second refund.
* Completion is reachable: a live session after it began, a written analysis
  by its delivery. It opens the review and lets settlement run its rules.
* The order read model says what happened (`lifecycle`, `actions`, `refund`,
  `timeline`) so a client never has to guess after a payment.
* A slot is booked on the day the person was looking at.
* Password reset: one generic answer, a single-use expiring link, and an honest
  503 when no mail provider exists.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.core.config import settings
from app.db.models.marketplace import Appointment, ExpertService
from app.db.models.payments import PaymentIntent, RefundRequest
from app.db.models.user import User
from app.domain.marketplace import DeliveryType
from app.services.mail import mailer as mail_module
from tests.test_payments import (  # noqa: F401 - fixtures
    API,
    SIGNATURE_HEADER,
    market,
    order_for,
    pay_externally,
    register,
    rows,
    stores,
    wide_open,
)


async def get_order(client, market, order_id, *, expert=False):
    prefix = "/expert" if expert else ""
    who = "expert" if expert else "user"
    response = await client.get(f"{API}{prefix}/orders/{order_id}", headers=market[who]["headers"])
    assert response.status_code == 200, response.text
    return response.json()


async def paid_order(client, market, stores, key):
    order_id = await order_for(client, market)
    _, paid, _ = await pay_externally(client, market, stores, order_id, key=key)
    assert paid.status_code == 200, paid.text
    return order_id


async def start_in_past(session_factory, order_id, *, hours=2):
    """Move the session's start behind us, as time passing would."""
    async with session_factory() as session:
        starts = datetime.now(UTC) - timedelta(hours=hours)
        await session.execute(
            update(Appointment)
            .where(Appointment.service_order_id == order_id)
            .values(starts_at_utc=starts, ends_at_utc=starts + timedelta(hours=1))
        )
        await session.commit()


async def refund_rows(session_factory, order_id):
    return await rows(session_factory, RefundRequest, RefundRequest.order_id == order_id)


# ============================================================ cancellation


@pytest.mark.parametrize("actor", ["user", "expert"])
async def test_appointment_cancel_opens_the_same_refund_as_order_cancel(
    client, market, stores, session_factory, actor
):
    order_id = await paid_order(client, market, stores, key=f"appt-{actor}-key")
    before = await get_order(client, market, order_id)
    assert before["lifecycle"] == "scheduled"
    assert before["cancellation"] == {
        "allowed": True, "refund_outcome": "refund_review",
        "refundable_minor": 999, "currency": "TRY",
    }

    prefix = "/expert" if actor == "expert" else ""
    response = await client.post(
        f"{API}{prefix}/appointments/{before['appointment']['id']}/cancel",
        headers=market[actor]["headers"], json={"reason": "Cannot make it"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"

    after = await get_order(client, market, order_id)
    assert after["status"] == "cancelled"
    assert after["payment_status"] == "refund_pending"
    assert after["cancellation_actor"] == actor
    assert after["appointment"]["status"] == "cancelled"
    assert after["lifecycle"] == "refund_review"
    assert after["refund"]["status"] == "manual_review"
    assert after["refund"]["amount_minor"] == 999
    assert after["refund"]["reason"] == f"{actor}_cancellation"
    assert after["actions"]["can_cancel"] is False
    events = [item["event"] for item in after["timeline"]]
    assert {"created", "paid", "cancelled", "refund_requested"} <= set(events)

    [refund] = await refund_rows(session_factory, order_id)
    assert refund.idempotency_key == f"cancel:{order_id}"


async def test_duplicate_cancels_never_open_a_second_refund(client, market, stores, session_factory):
    order_id = await paid_order(client, market, stores, key="dup-cancel-key")
    view = await get_order(client, market, order_id)
    headers = market["user"]["headers"]

    first = await client.post(f"{API}/orders/{order_id}/cancel", headers=headers, json={})
    again = await client.post(f"{API}/orders/{order_id}/cancel", headers=headers, json={})
    via_appointment = await client.post(
        f"{API}/appointments/{view['appointment']['id']}/cancel", headers=headers, json={}
    )
    via_expert = await client.post(
        f"{API}/expert/appointments/{view['appointment']['id']}/cancel",
        headers=market["expert"]["headers"], json={},
    )
    assert [r.status_code for r in (first, again, via_appointment, via_expert)] == [200] * 4
    assert again.json()["cancelled_at"] == first.json()["cancelled_at"]
    # The first actor stays on record; a replay does not rewrite it.
    assert (await get_order(client, market, order_id))["cancellation_actor"] == "user"
    assert len(await refund_rows(session_factory, order_id)) == 1


async def test_unpaid_order_cancel_owes_nothing_and_closes_the_checkout(
    client, market, stores, session_factory
):
    order_id = await order_for(client, market)
    started = await client.post(
        f"{API}/orders/{order_id}/payment", headers=market["user"]["headers"],
        json={"method": "external", "idempotency_key": "open-checkout-1"},
    )
    assert started.status_code == 200
    preview = (await get_order(client, market, order_id))["cancellation"]
    assert preview["refund_outcome"] == "not_paid"

    response = await client.post(f"{API}/orders/{order_id}/cancel", headers=market["user"]["headers"], json={})
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["payment_status"] == "pending"
    assert body["lifecycle"] == "cancelled"
    assert body["refund"] is None
    assert await refund_rows(session_factory, order_id) == []
    [intent] = await rows(session_factory, PaymentIntent, PaymentIntent.order_id == order_id)
    assert intent.status == "cancelled"


async def test_money_arriving_after_cancellation_is_owed_back(client, market, stores, session_factory):
    order_id = await order_for(client, market)
    started = await client.post(
        f"{API}/orders/{order_id}/payment", headers=market["user"]["headers"],
        json={"method": "external", "idempotency_key": "late-pay-key1"},
    )
    reference = started.json()["client_handoff"].rsplit("/", 1)[-1]
    await client.post(f"{API}/orders/{order_id}/cancel", headers=market["user"]["headers"], json={})

    external = stores["external"]
    body = external.event_body(event_type="payment_succeeded", external_reference=reference,
                               amount_minor=999, currency="TRY", event_id="evt-late-1")
    response = await client.post(f"{API}/webhooks/payments/external", content=body,
                                 headers={SIGNATURE_HEADER: external.sign(body)})
    assert response.json()["outcome"] == "applied"

    after = await get_order(client, market, order_id)
    assert after["status"] == "cancelled"
    assert after["payment_status"] == "refund_pending"
    assert after["lifecycle"] == "refund_review"
    assert len(await refund_rows(session_factory, order_id)) == 1


async def test_cancel_when_a_refund_already_covers_the_payment(client, market, stores, session_factory):
    order_id = await paid_order(client, market, stores, key="covered-key-1")
    asked = await client.post(
        f"{API}/orders/{order_id}/refund-requests", headers=market["user"]["headers"],
        json={"reason": "goodwill", "idempotency_key": "covered-r-1"},
    )
    assert asked.status_code == 201

    response = await client.post(f"{API}/orders/{order_id}/cancel", headers=market["user"]["headers"], json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["payment_status"] == "refund_pending"
    assert body["refund"]["id"] == asked.json()["id"]
    assert len(await refund_rows(session_factory, order_id)) == 1


async def test_cancel_after_a_partial_refund_request_asks_for_the_rest(client, market, stores, session_factory):
    order_id = await paid_order(client, market, stores, key="part-cover-k1")
    await client.post(
        f"{API}/orders/{order_id}/refund-requests", headers=market["user"]["headers"],
        json={"reason": "goodwill", "amount_minor": 400, "idempotency_key": "part-cover-r1"},
    )
    await client.post(f"{API}/orders/{order_id}/cancel", headers=market["user"]["headers"], json={})
    amounts = sorted(r.amount_minor for r in await refund_rows(session_factory, order_id))
    assert amounts == [400, 599]


async def test_a_denied_refund_stops_saying_pending(client, market, stores, session_factory):
    from app.services.payments.refunds import RefundService

    order_id = await paid_order(client, market, stores, key="deny-key-001")
    await client.post(f"{API}/orders/{order_id}/cancel", headers=market["user"]["headers"], json={})
    [refund] = await refund_rows(session_factory, order_id)
    async with session_factory() as session:
        await RefundService(session).deny(refund.id, reviewer="admin")
        await session.commit()
    after = await get_order(client, market, order_id)
    assert after["payment_status"] == "paid"
    assert after["refund"]["status"] == "denied"
    assert after["lifecycle"] == "cancelled"
    assert "refund_denied" in [item["event"] for item in after["timeline"]]


async def test_an_approved_refund_reads_refunded(client, market, stores, session_factory):
    from app.services.payments.refunds import RefundService

    order_id = await paid_order(client, market, stores, key="approve-k-01")
    await client.post(f"{API}/orders/{order_id}/cancel", headers=market["user"]["headers"], json={})
    [refund] = await refund_rows(session_factory, order_id)
    async with session_factory() as session:
        await RefundService(session).approve(refund.id, reviewer="admin", provider=stores["external"])
        await session.commit()
    after = await get_order(client, market, order_id)
    assert after["payment_status"] == "refunded"
    assert after["lifecycle"] == "refunded"
    assert after["refund"]["status"] == "refunded"
    listed = (await client.get(f"{API}/orders", headers=market["user"]["headers"])).json()
    assert [o["lifecycle"] for o in listed if o["id"] == str(order_id)] == ["refunded"]


# ============================================================== completion


async def test_a_live_session_completes_only_after_it_began(client, market, stores, session_factory):
    order_id = await paid_order(client, market, stores, key="complete-k-01")
    early = await get_order(client, market, order_id)
    assert early["actions"]["can_complete"] is False
    assert early["completion_block"] == "session_not_started"
    refused = await client.post(f"{API}/orders/{order_id}/complete", headers=market["user"]["headers"])
    assert refused.status_code == 409
    assert refused.json()["error"]["details"]["reason"] == "session_not_started"

    await start_in_past(session_factory, order_id)
    due = await get_order(client, market, order_id)
    assert due["lifecycle"] == "awaiting_completion"
    assert due["actions"]["can_complete"] is True
    assert due["actions"]["review_eligible"] is False

    done = await client.post(f"{API}/orders/{order_id}/complete", headers=market["user"]["headers"])
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "completed"
    assert body["lifecycle"] == "completed"
    assert body["appointment"]["status"] == "completed"
    assert body["actions"]["review_eligible"] is True
    assert body["actions"]["can_cancel"] is False
    assert "completed" in [item["event"] for item in body["timeline"]]

    # A retry is harmless; the review is now allowed.
    again = await client.post(f"{API}/orders/{order_id}/complete", headers=market["user"]["headers"])
    assert again.status_code == 200
    review = await client.post(f"{API}/orders/{order_id}/review", headers=market["user"]["headers"],
                               json={"rating": 5})
    assert review.status_code == 201


async def test_the_expert_can_complete_and_settlement_follows_the_hold(
    client, market, stores, session_factory, monkeypatch
):
    monkeypatch.setattr(settings, "expert_settlement_hold_days", 0)
    order_id = await paid_order(client, market, stores, key="expert-done-1")
    await start_in_past(session_factory, order_id)
    expert_view = await get_order(client, market, order_id, expert=True)
    assert expert_view["actions"]["can_complete"] is True
    assert expert_view["actions"]["review_eligible"] is False

    done = await client.post(f"{API}/expert/orders/{order_id}/complete", headers=market["expert"]["headers"])
    assert done.status_code == 200, done.text
    [balance] = (await client.get(f"{API}/expert/earnings", headers=market["expert"]["headers"])).json()["balances"]
    assert (balance["pending_minor"], balance["available_minor"]) == (0, 800)


async def test_completion_without_a_hold_decision_releases_nothing(client, market, stores, session_factory):
    order_id = await paid_order(client, market, stores, key="no-hold-key1")
    await start_in_past(session_factory, order_id)
    await client.post(f"{API}/orders/{order_id}/complete", headers=market["user"]["headers"])
    [balance] = (await client.get(f"{API}/expert/earnings", headers=market["expert"]["headers"])).json()["balances"]
    assert (balance["pending_minor"], balance["available_minor"]) == (800, 0)


async def test_unpaid_or_cancelled_orders_cannot_be_completed(client, market, stores, session_factory):
    unpaid = await order_for(client, market)
    await start_in_past(session_factory, unpaid)
    response = await client.post(f"{API}/orders/{unpaid}/complete", headers=market["user"]["headers"])
    assert response.json()["error"]["details"]["reason"] == "payment_pending"

    cancelled = await paid_order(client, market, stores, key="cancel-then-1")
    await client.post(f"{API}/orders/{cancelled}/cancel", headers=market["user"]["headers"], json={})
    await start_in_past(session_factory, cancelled)
    response = await client.post(f"{API}/orders/{cancelled}/complete", headers=market["user"]["headers"])
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "order_cancelled"


async def test_a_written_analysis_is_completed_by_its_delivery(client, market, session_factory):
    async with session_factory() as session:
        written = ExpertService(
            expert_id=market["expert_id"], service_definition_id=market["definition"].id,
            title="Written", delivery_type=DeliveryType.WRITTEN_REPORT.value, duration_minutes=60,
            price_minor=0, currency="TRY", active=True,
        )
        session.add(written)
        await session.commit()
        market["offerings"]["written_report"] = written.id
    order_id = await order_for(client, market, delivery="written_report")
    view = await get_order(client, market, order_id, expert=True)
    assert view["lifecycle"] == "scheduled"
    assert view["actions"]["can_deliver"] is True
    assert view["actions"]["can_complete"] is False

    # A live-session completion is not how a written analysis ends.
    live = await client.post(f"{API}/orders/{order_id}/complete", headers=market["user"]["headers"])
    assert live.json()["error"]["details"]["reason"] == "written_needs_delivery"
    # The user cannot deliver; only the expert's route exists.
    stranger = await client.post(f"{API}/expert/orders/{order_id}/deliver",
                                 headers=market["user"]["headers"], json={"note": "x"})
    assert stranger.status_code in (403, 404)
    empty = await client.post(f"{API}/expert/orders/{order_id}/deliver",
                              headers=market["expert"]["headers"], json={"note": ""})
    assert empty.status_code == 422

    delivered = await client.post(f"{API}/expert/orders/{order_id}/deliver",
                                  headers=market["expert"]["headers"],
                                  json={"note": "Güneşin 10. evde; kariyer vurgusu."})
    assert delivered.status_code == 200, delivered.text
    user_view = await get_order(client, market, order_id)
    assert user_view["status"] == "completed"
    assert user_view["delivery"]["note"] == "Güneşin 10. evde; kariyer vurgusu."
    assert user_view["actions"]["review_eligible"] is True
    assert {"delivered", "completed"} <= {item["event"] for item in user_view["timeline"]}


# ======================================================= payment refresh


async def test_after_payment_every_read_agrees(client, market, stores):
    order_id = await order_for(client, market)
    before = await get_order(client, market, order_id)
    assert before["lifecycle"] == "pending"
    assert before["payment_status"] == "pending"

    await pay_externally(client, market, stores, order_id, key="refresh-key-1")
    order = await get_order(client, market, order_id)
    payment = (await client.get(f"{API}/orders/{order_id}/payment", headers=market["user"]["headers"])).json()
    appointment = (await client.get(
        f"{API}/appointments/{order['appointment']['id']}", headers=market["user"]["headers"]
    )).json()
    listed = (await client.get(f"{API}/orders", headers=market["user"]["headers"])).json()

    assert order["status"] == "confirmed"
    assert order["payment_status"] == "paid"
    assert order["lifecycle"] == "scheduled"
    assert appointment["status"] == "confirmed"
    assert all(group["status"] in ("satisfied", "not_required") for group in payment["groups"])
    assert [o["lifecycle"] for o in listed if o["id"] == str(order_id)] == ["scheduled"]


# ============================================================ stale slot


async def test_a_slot_on_another_day_than_selected_is_refused(client, market):
    now = datetime.now(UTC)
    slots = (await client.get(
        f"{API}/experts/{market['expert_id']}/slots", headers=market["user"]["headers"],
        params={"service_id": str(market["offerings"]["video"]), "from": now.isoformat(),
                "to": (now + timedelta(days=5)).isoformat()},
    )).json()["slots"]
    starts = datetime.fromisoformat(slots[0]["starts_at_utc"].replace("Z", "+00:00"))
    offset = 180
    shown_day = (starts + timedelta(minutes=offset)).date()
    base = {"expert_service_id": str(market["offerings"]["video"]),
            "starts_at_utc": slots[0]["starts_at_utc"], "selected_utc_offset_minutes": offset}

    wrong = await client.post(f"{API}/orders", headers=market["user"]["headers"],
                              json={**base, "selected_local_date": (shown_day + timedelta(days=1)).isoformat()})
    assert wrong.status_code == 422
    assert wrong.json()["error"]["code"] == "slot_date_mismatch"
    assert await rows_count(client, market) == 0

    right = await client.post(f"{API}/orders", headers=market["user"]["headers"],
                              json={**base, "selected_local_date": shown_day.isoformat()})
    assert right.status_code == 201, right.text


async def rows_count(client, market) -> int:
    return len((await client.get(f"{API}/orders", headers=market["user"]["headers"])).json())


# ========================================================= password reset


@pytest.fixture
def outbox():
    memory = mail_module.MemoryMailer()
    mail_module.set_mailer(memory)
    yield memory.outbox
    mail_module.set_mailer(None)


def token_from(message) -> str:
    link = next(line for line in message.text.splitlines() if "token=" in line)
    from urllib.parse import parse_qs, urlsplit, unquote

    parsed = urlsplit(link.strip())
    return unquote(parse_qs(parsed.fragment or parsed.query)["token"][0])


async def test_reset_link_is_mailed_single_use_and_checkable(client, registered, outbox):
    response = await client.post(f"{API}/auth/forgot-password", json={"email": registered["email"]})
    assert response.status_code == 200
    assert response.json()["message"] == "If the account is eligible, a reset link has been sent."
    [message] = outbox
    assert message.to == registered["email"]
    assert f"{settings.password_reset_url_base}#token=" in message.text
    assert message.html and message.kind == "password_reset"
    token = token_from(message)
    assert token not in response.text

    check = await client.post(f"{API}/auth/reset-password/check", json={"token": token})
    assert check.status_code == 200 and check.json()["valid"] is True

    reset = await client.post(f"{API}/auth/reset-password",
                              json={"token": token, "new_password": "BrandNewPassphrase9"})
    assert reset.status_code == 200
    used = await client.post(f"{API}/auth/reset-password/check", json={"token": token})
    assert used.status_code == 401
    assert used.json()["error"]["code"] == "token_used"
    login = await client.post(f"{API}/auth/login",
                              json={"email": registered["email"], "password": "BrandNewPassphrase9"})
    assert login.status_code == 200


async def test_unknown_or_ineligible_addresses_get_the_same_answer_and_no_mail(
    client, registered, outbox, session_factory
):
    unknown = await client.post(f"{API}/auth/forgot-password", json={"email": "ghost@example.com"})
    async with session_factory() as session:
        await session.execute(update(User).where(User.email == registered["email"]).values(password_hash=None))
        await session.commit()
    firebase_only = await client.post(f"{API}/auth/forgot-password", json={"email": registered["email"]})
    assert unknown.status_code == firebase_only.status_code == 200
    assert unknown.json() == firebase_only.json()
    assert outbox == []


async def test_asking_again_retires_the_earlier_link(client, registered, outbox):
    for _ in range(2):
        await client.post(f"{API}/auth/forgot-password", json={"email": registered["email"]})
    first, second = (token_from(m) for m in outbox)
    old = await client.post(f"{API}/auth/reset-password/check", json={"token": first})
    assert old.json()["error"]["code"] == "token_used"
    new = await client.post(f"{API}/auth/reset-password/check", json={"token": second})
    assert new.status_code == 200


async def test_an_expired_link_says_so(client, registered, outbox, monkeypatch):
    monkeypatch.setattr(settings, "password_reset_ttl_minutes", -1)
    await client.post(f"{API}/auth/forgot-password", json={"email": registered["email"]})
    token = token_from(outbox[0])
    check = await client.post(f"{API}/auth/reset-password/check", json={"token": token})
    assert check.status_code == 401
    assert check.json()["error"]["code"] == "token_expired"
    reset = await client.post(f"{API}/auth/reset-password",
                              json={"token": token, "new_password": "BrandNewPassphrase9"})
    assert reset.json()["error"]["code"] == "token_expired"


async def test_without_a_mail_provider_reset_is_unavailable_for_everyone(client, registered):
    mail_module.set_mailer(mail_module.DisabledMailer())
    try:
        known = await client.post(f"{API}/auth/forgot-password", json={"email": registered["email"]})
        unknown = await client.post(f"{API}/auth/forgot-password", json={"email": "ghost@example.com"})
        capabilities = (await client.get(f"{API}/auth/capabilities")).json()
    finally:
        mail_module.set_mailer(None)
    assert known.status_code == unknown.status_code == 503
    assert known.json()["error"]["code"] == "password_reset_unavailable"
    assert known.json() == unknown.json()
    assert capabilities["password_reset_email"] is False


def test_production_refuses_development_mailers(monkeypatch):
    for provider in ("log", "memory"):
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "mail_provider", provider)
        with pytest.raises(RuntimeError, match="MAIL_PROVIDER"):
            settings.assert_production_ready()


async def test_smtp_without_a_host_is_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", None)
    monkeypatch.setattr(settings, "mail_from", "noreply@example.com")
    smtp = mail_module.SmtpMailer()
    assert smtp.configured is False
    with pytest.raises(mail_module.MailNotConfigured):
        await smtp.send(mail_module.MailMessage(to="a@example.com", subject="s", text="t"))
