"""Phase 2: account centre, notification centre, saved-person edits, search.

* Sessions: listed per device, "this device" marked, one can be signed out.
* Deleting an account needs the password (or the email when there is none)
  and is refused while an order, appointment or refund is open.
* The notification centre is the push outbox read back: only due,
  user-facing events, with a read state; never somebody else's.
* A saved person can be edited without touching a report already made.
* Expert search matches free text across all experts, not one page.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import update

from app.db.models.chat import NotificationOutbox
from app.db.models.compatibility import CompatibilityReport
from app.db.models.marketplace import Expert
from app.db.models.user import User
from app.domain.marketplace import ExpertStatus
from tests.test_payments import (  # noqa: F401 - fixtures
    API,
    market,
    order_for,
    pay_externally,
    register,
    stores,
    wide_open,
)

PASSWORD = "Str0ngPassphrase!"


async def login(client: httpx.AsyncClient, email: str, *, agent: str) -> dict:
    response = await client.post(
        f"{API}/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"User-Agent": agent, "X-Forwarded-For": "85.105.22.33"},
    )
    assert response.status_code == 200, response.text
    tokens = response.json()
    return {"headers": {"Authorization": f"Bearer {tokens['access_token']}"}, "tokens": tokens}


# ================================================================ sessions


async def test_sessions_are_listed_and_one_can_be_signed_out(client, registered):
    phone = await login(client, registered["email"], agent="Astrofrekans/1.0 (Android 15)")
    tablet = await login(client, registered["email"], agent="Astrofrekans/1.0 (iPad)")

    listed = (await client.get(f"{API}/auth/sessions", headers=phone["headers"])).json()
    # registration + two logins
    assert len(listed) == 3
    [current] = [row for row in listed if row["current"]]
    assert current["user_agent"].endswith("(Android 15)")
    assert current["ip_hint"] == "85.105.x.x"

    other = next(row for row in listed if row["user_agent"] and "iPad" in row["user_agent"])
    signed_out = await client.delete(f"{API}/auth/sessions/{other['id']}", headers=phone["headers"])
    assert signed_out.status_code == 200
    after = (await client.get(f"{API}/auth/sessions", headers=phone["headers"])).json()
    assert other["id"] not in {row["id"] for row in after}
    # That device can no longer refresh.
    refreshed = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tablet["tokens"]["refresh_token"]}
    )
    assert refreshed.status_code == 401


async def test_another_users_session_is_not_found(client, registered):
    stranger = await register(client, "stranger@example.com")
    mine = (await client.get(f"{API}/auth/sessions", headers=registered["headers"])).json()
    response = await client.delete(f"{API}/auth/sessions/{mine[0]['id']}", headers=stranger["headers"])
    assert response.status_code == 404
    unknown = await client.delete(f"{API}/auth/sessions/{uuid.uuid4()}", headers=registered["headers"])
    assert unknown.status_code == 404


async def test_change_password_needs_the_current_one(client, registered):
    wrong = await client.post(
        f"{API}/auth/change-password",
        headers=registered["headers"],
        json={"current_password": "not-it-at-all", "new_password": "BrandNewPassphrase9"},
    )
    assert wrong.status_code == 403
    assert wrong.json()["error"]["code"] == "current_password_incorrect"
    ok = await client.post(
        f"{API}/auth/change-password",
        headers=registered["headers"],
        json={"current_password": registered["password"], "new_password": "BrandNewPassphrase9"},
    )
    assert ok.status_code == 200
    new = await client.post(
        f"{API}/auth/login", json={"email": registered["email"], "password": "BrandNewPassphrase9"}
    )
    assert new.status_code == 200


# ============================================================== deletion


async def test_deletion_needs_the_password(client, registered):
    check = (await client.get(f"{API}/users/me/deletion-check", headers=registered["headers"])).json()
    assert check == {
        "allowed": True, "requires_password": True, "open_orders": 0,
        "live_appointments": 0, "open_refunds": 0, "expert_open_orders": 0,
    }
    missing = await client.post(f"{API}/users/me/delete", headers=registered["headers"], json={})
    # 403, not 401: the session is valid; only the confirmation failed.
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "current_password_incorrect"
    wrong = await client.post(
        f"{API}/users/me/delete", headers=registered["headers"], json={"password": "nope-nope-nope"}
    )
    assert wrong.status_code == 403
    # The old DELETE route follows the same rules.
    bare = await client.delete(f"{API}/users/me", headers=registered["headers"])
    assert bare.status_code == 403
    assert (await client.get(f"{API}/users/me", headers=registered["headers"])).status_code == 200

    done = await client.post(
        f"{API}/users/me/delete", headers=registered["headers"], json={"password": registered["password"]}
    )
    assert done.status_code == 200
    assert (await client.get(f"{API}/users/me", headers=registered["headers"])).status_code == 401
    relogin = await client.post(
        f"{API}/auth/login", json={"email": registered["email"], "password": registered["password"]}
    )
    assert relogin.status_code == 401


async def test_an_account_without_a_password_confirms_its_email(client, registered, session_factory):
    async with session_factory() as session:
        await session.execute(update(User).where(User.email == registered["email"]).values(password_hash=None))
        await session.commit()
    check = (await client.get(f"{API}/users/me/deletion-check", headers=registered["headers"])).json()
    assert check["requires_password"] is False
    wrong = await client.post(
        f"{API}/users/me/delete", headers=registered["headers"], json={"confirm_email": "other@example.com"}
    )
    assert wrong.json()["error"]["code"] == "deletion_confirmation_required"
    ok = await client.post(
        f"{API}/users/me/delete", headers=registered["headers"],
        json={"confirm_email": registered["email"].upper()},
    )
    assert ok.status_code == 200


async def test_open_services_block_deletion(client, market, stores, session_factory):
    order_id = await order_for(client, market)
    # Unpaid: abandoned, not open - but its appointment is still live.
    check = (await client.get(f"{API}/users/me/deletion-check", headers=market["user"]["headers"])).json()
    assert check["allowed"] is False and check["live_appointments"] == 1
    await pay_externally(client, market, stores, order_id, key="delete-block-1")
    blocked = await client.post(
        f"{API}/users/me/delete", headers=market["user"]["headers"], json={"password": PASSWORD}
    )
    assert blocked.status_code == 409
    details = blocked.json()["error"]["details"]
    assert details["open_orders"] == 1 and details["live_appointments"] == 1

    # The expert's side is blocked too while the order is open.
    expert_check = (await client.get(
        f"{API}/users/me/deletion-check", headers=market["expert"]["headers"]
    )).json()
    assert expert_check["expert_open_orders"] == 1

    # Cancelled with a refund under review: still blocked until it is decided.
    await client.post(f"{API}/orders/{order_id}/cancel", headers=market["user"]["headers"], json={})
    after_cancel = (await client.get(f"{API}/users/me/deletion-check", headers=market["user"]["headers"])).json()
    assert after_cancel["allowed"] is False
    assert after_cancel["open_refunds"] == 1 and after_cancel["live_appointments"] == 0
    # Counted once, as the refund - not also as an unfinished order.
    assert after_cancel["open_orders"] == 0


async def test_deleting_an_expert_account_takes_the_profile_out_of_search(client, market, session_factory):
    response = await client.post(
        f"{API}/users/me/delete", headers=market["expert"]["headers"], json={"password": PASSWORD}
    )
    assert response.status_code == 200
    async with session_factory() as session:
        expert = await session.get(Expert, market["expert_id"])
        assert expert.status == ExpertStatus.INACTIVE.value
    listed = (await client.get(f"{API}/experts", headers=market["user"]["headers"])).json()
    assert str(market["expert_id"]) not in {item["id"] for item in listed["items"]}


# =========================================================== notifications


async def test_the_inbox_is_the_outbox_read_back(client, market, session_factory):
    order_id = await order_for(client, market)
    headers = market["user"]["headers"]
    page = (await client.get(f"{API}/notifications", headers=headers)).json()
    # The booking notification is due; the reminders scheduled ahead are not.
    assert [item["event"] for item in page["items"]] == ["appointment_booked"]
    item = page["items"][0]
    assert item["category"] == "appointment" and item["read"] is False
    assert set(item["data"]) == {"appointment_id"}
    assert page["unread_count"] == 1

    marked = await client.patch(f"{API}/notifications/{item['id']}", headers=headers, json={"read": True})
    assert marked.json()["read"] is True
    assert (await client.get(f"{API}/notifications/unread-count", headers=headers)).json() == {"unread_count": 0}
    unmarked = await client.patch(f"{API}/notifications/{item['id']}", headers=headers, json={"read": False})
    assert unmarked.json()["read"] is False

    # Nobody else can read or mark it.
    stranger = await client.patch(
        f"{API}/notifications/{item['id']}", headers=market["expert"]["headers"], json={"read": True}
    )
    assert stranger.status_code == 404
    expert_page = (await client.get(f"{API}/notifications", headers=market["expert"]["headers"])).json()
    assert item["id"] not in {row["id"] for row in expert_page["items"]}

    # A due reminder appears; cancelling the appointment hides the ones it drops.
    appointment_id = uuid.UUID(item["data"]["appointment_id"])
    async with session_factory() as session:
        due = datetime.now(UTC) - timedelta(minutes=1)
        for key, status in (("delivered", "sent"), ("queued", "pending")):
            session.add(NotificationOutbox(
                event_type="appointment_reminder", user_id=market["user"]["id"],
                appointment_id=appointment_id, dedupe_key=f"reminder-test:{key}",
                payload={"data": {"event": "appointment_reminder",
                                  "appointment_id": str(appointment_id)}},
                status=status, scheduled_for=due,
            ))
        await session.commit()
    due_now = [row["event"] for row in (await client.get(f"{API}/notifications", headers=headers)).json()["items"]]
    assert due_now.count("appointment_reminder") == 2
    await client.post(f"{API}/orders/{order_id}/cancel", headers=headers, json={})
    events = [row["event"] for row in (await client.get(f"{API}/notifications", headers=headers)).json()["items"]]
    # The one already delivered stays; the one dropped by the cancellation
    # does not appear; the cancellation itself does.
    assert events.count("appointment_reminder") == 1
    assert "appointment_cancelled" in events

    everything = await client.post(f"{API}/notifications/read-all", headers=headers)
    assert everything.json() == {"unread_count": 0}
    only_unread = (await client.get(f"{API}/notifications?unread=true", headers=headers)).json()
    assert only_unread["items"] == []


async def test_call_signalling_and_categories(client, registered, session_factory):
    me = (await client.get(f"{API}/auth/me", headers=registered["headers"])).json()
    user_id = uuid.UUID(me["id"])
    async with session_factory() as session:
        for event, key in (
            ("incoming_call", "a"), ("call_answered", "b"), ("call_missed", "c"),
            ("refund_processed", "d"), ("ai_report_ready", "e"), ("new_chat_message", "f"),
        ):
            session.add(NotificationOutbox(
                event_type=event, user_id=user_id, dedupe_key=f"test:{key}",
                payload={"title": "t", "body": "b", "data": {"event": event, "order_id": "x", "text": "secret"}},
                status="sent",
            ))
        await session.commit()
    page = (await client.get(f"{API}/notifications", headers=registered["headers"])).json()
    got = {row["event"]: row["category"] for row in page["items"]}
    assert got == {
        "call_missed": "appointment", "refund_processed": "payment",
        "ai_report_ready": "astro_ai", "new_chat_message": "expert_message",
    }
    assert all(set(row["data"]) == {"order_id"} for row in page["items"])
    payments = (await client.get(f"{API}/notifications?category=payment", headers=registered["headers"])).json()
    assert [row["event"] for row in payments["items"]] == ["refund_processed"]
    bad = await client.get(f"{API}/notifications?category=nope", headers=registered["headers"])
    assert bad.status_code == 422


async def test_inbox_pages_with_a_cursor(client, registered, session_factory):
    me = (await client.get(f"{API}/auth/me", headers=registered["headers"])).json()
    async with session_factory() as session:
        base = datetime.now(UTC) - timedelta(hours=1)
        for index in range(5):
            row = NotificationOutbox(
                event_type="payment_succeeded", user_id=uuid.UUID(me["id"]), dedupe_key=f"page:{index}",
                payload={"data": {"event": "payment_succeeded"}}, status="sent",
            )
            session.add(row)
            await session.flush()
            row.created_at = base + timedelta(minutes=index)
        await session.commit()
    first = (await client.get(f"{API}/notifications?limit=2", headers=registered["headers"])).json()
    assert len(first["items"]) == 2 and first["next_before"]
    second = (await client.get(
        f"{API}/notifications", params={"limit": 2, "before": first["next_before"]},
        headers=registered["headers"],
    )).json()
    assert not {row["id"] for row in first["items"]} & {row["id"] for row in second["items"]}


# =========================================================== saved people


async def test_editing_a_saved_person_keeps_past_reports(client, registered, session_factory):
    person = (await client.post(
        f"{API}/saved-people", headers=registered["headers"],
        json={"name": "Deniz", "relation": "partner", "birth_date": "1994-08-21",
              "birth_time": "09:45:00", "birth_place": "London"},
    )).json()
    report = (await client.post(
        f"{API}/compatibility/synastry", headers=registered["headers"],
        json={"person_a": {"me": True}, "person_b": {"saved_person_id": person["id"]}},
    )).json()
    async with session_factory() as session:
        before = await session.get(CompatibilityReport, uuid.UUID(report["report_id"]))
        snapshot = (before.input_fingerprint, before.structured_result, before.person_b_label)

    edited = await client.patch(
        f"{API}/saved-people/{person['id']}", headers=registered["headers"],
        json={"name": "Deniz Y.", "birth_time": None, "birth_place": "Istanbul"},
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["name"] == "Deniz Y."
    assert body["birth_time"] is None and body["birth_time_known"] is False
    assert body["birth_date"] == "1994-08-21"
    assert body["timezone"] == "Europe/Istanbul"

    async with session_factory() as session:
        after = await session.get(CompatibilityReport, uuid.UUID(report["report_id"]))
        assert (after.input_fingerprint, after.structured_result, after.person_b_label) == snapshot

    again = (await client.post(
        f"{API}/compatibility/synastry", headers=registered["headers"],
        json={"person_a": {"me": True}, "person_b": {"saved_person_id": person["id"]}},
    )).json()
    assert again["report_id"] != report["report_id"]
    assert again["cached"] is False


async def test_saved_person_edits_are_owner_only_and_validated(client, registered):
    person = (await client.post(
        f"{API}/saved-people", headers=registered["headers"],
        json={"name": "Ada", "birth_date": "2000-01-01", "birth_place": "London"},
    )).json()
    stranger = await register(client, "nosy@example.com")
    assert (await client.patch(
        f"{API}/saved-people/{person['id']}", headers=stranger["headers"], json={"name": "X"}
    )).status_code == 404
    bad_zone = await client.patch(
        f"{API}/saved-people/{person['id']}", headers=registered["headers"], json={"timezone": "Mars/Base"}
    )
    assert bad_zone.status_code == 422
    set_time = (await client.patch(
        f"{API}/saved-people/{person['id']}", headers=registered["headers"], json={"birth_time": "07:30:00"}
    )).json()
    assert set_time["birth_time"] == "07:30:00" and set_time["birth_time_known"] is True
    assert set_time["birth_place"]  # untouched


# ================================================================= search


async def test_search_matches_free_text_across_every_expert(client, market, session_factory):
    async with session_factory() as session:
        for index in range(25):
            session.add(Expert(
                user_id=(await register(client, f"filler{index}@example.com"))["id"],
                display_name=f"Filler {index}", languages=["en"], specialties=["astrology"],
                experience_years=1, timezone="UTC", status=ExpertStatus.ACTIVE.value,
                verified=False, rating_average=5, rating_count=10,
            ))
        session.add(Expert(
            user_id=(await register(client, "ayse@example.com"))["id"],
            display_name="Ayşe Yıldız", headline="Kahve ve tarot", languages=["tr"],
            specialties=["tarot"], experience_years=4, timezone="Europe/Istanbul",
            status=ExpertStatus.ACTIVE.value, verified=True, rating_average=0, rating_count=0,
        ))
        await session.commit()
    headers = market["user"]["headers"]
    # Ayşe sorts last by rating: page one of the unfiltered list never has her.
    first_page = (await client.get(f"{API}/experts", params={"limit": 20}, headers=headers)).json()
    assert "Ayşe Yıldız" not in {item["display_name"] for item in first_page["items"]}

    for q in ("ayse", "AYŞE", "yıldız", "tarot"):
        found = (await client.get(f"{API}/experts", params={"q": q, "limit": 20}, headers=headers)).json()
        assert [item["display_name"] for item in found["items"]] == ["Ayşe Yıldız"], q
        assert found["total"] == 1

    by_specialty_name = (await client.get(
        f"{API}/experts", params={"q": "astroloji", "limit": 10}, headers=headers
    )).json()
    assert by_specialty_name["total"] == 26  # the market expert + 25 fillers
    second = (await client.get(
        f"{API}/experts", params={"q": "astroloji", "limit": 10, "offset": 20}, headers=headers
    )).json()
    assert len(second["items"]) == 6

    combined = (await client.get(
        f"{API}/experts", params={"q": "tarot", "language": "en"}, headers=headers
    )).json()
    assert combined["total"] == 0
    nothing = (await client.get(f"{API}/experts", params={"q": "zzz"}, headers=headers)).json()
    assert nothing == {**nothing, "items": [], "total": 0}
