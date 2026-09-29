"""User-pick draw sessions: shuffle face down, pick, reveal."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select, update

from app.db.models.divination import DivinationDrawSession, DivinationReading

API = "/api/v1/divination"


def _ref() -> str:
    return f"test-{uuid.uuid4().hex}"


async def _create(client, headers, *, ref=None, deck="tarot", spread="past_present_future", **extra):
    body = {
        "consumer_ref": ref or _ref(),
        "deck_type": deck,
        "spread_code": spread,
        "locale": "tr",
        **extra,
    }
    return await client.post(f"{API}/sessions", headers=headers, json=body)


async def _hidden(session_factory, session_id: str) -> dict:
    async with session_factory() as db:
        row = await db.get(DivinationDrawSession, uuid.UUID(session_id))
        return row.hidden_state


# ----------------------------------------------------------------- create


async def test_create_returns_only_public_state(client: httpx.AsyncClient, registered):
    response = await _create(client, registered["headers"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["deck_size"] == 78
    assert body["required_selections"] == 3
    assert [p["title"] for p in body["positions"]] == ["Geçmiş", "Şimdi", "Gidişat"]
    assert body["status"] == "open"
    text = response.text
    # No item ids, orientations or the hidden deck in the payload.
    for leak in ("hidden_state", "order", "orientation", "tarot:", "upright", "reversed"):
        assert leak not in text, leak

    got = await client.get(f"{API}/sessions/{body['session_id']}", headers=registered["headers"])
    assert got.status_code == 200
    for leak in ("hidden_state", "tarot:", "upright", "reversed"):
        assert leak not in got.text


async def test_same_consumer_ref_returns_same_session(client, registered, session_factory):
    ref = _ref()
    first = (await _create(client, registered["headers"], ref=ref)).json()
    second = (await _create(client, registered["headers"], ref=ref)).json()
    assert first["session_id"] == second["session_id"]
    async with session_factory() as db:
        count = await db.scalar(
            select(func.count()).select_from(DivinationDrawSession).where(DivinationDrawSession.consumer_ref == ref)
        )
    assert count == 1


async def test_same_ref_different_request_is_conflict(client, registered):
    ref = _ref()
    await _create(client, registered["headers"], ref=ref)
    for change in ({"spread": "single_card"}, {"deck": "rune", "spread": "three_rune"}):
        response = await _create(client, registered["headers"], ref=ref, **change)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "consumer_ref_conflict"
    other_question = await _create(client, registered["headers"], ref=ref, question="Başka soru")
    assert other_question.status_code == 409


async def test_rune_and_katina_sessions(client, registered):
    rune = (await _create(client, registered["headers"], deck="rune", spread="three_rune")).json()
    assert rune["deck_size"] == 24 and rune["required_selections"] == 3
    katina = (await _create(client, registered["headers"], deck="katina", spread="relationship")).json()
    assert katina["deck_size"] == 65 and katina["required_selections"] == 5


# ----------------------------------------------------------------- reveal


async def test_reveal_resolves_exactly_the_picked_slots_in_pick_order(
    client, registered, session_factory
):
    body = (await _create(client, registered["headers"])).json()
    hidden = await _hidden(session_factory, body["session_id"])
    picks = [51, 7, 24]  # deliberately unsorted
    response = await client.post(
        f"{API}/sessions/{body['session_id']}/reveal",
        headers=registered["headers"],
        json={"positions": picks},
    )
    assert response.status_code == 200, response.text
    items = sorted(response.json()["items"], key=lambda i: i["position_index"])
    assert [i["item_id"] for i in items] == [hidden["order"][p] for p in picks]
    assert [i["orientation"] for i in items] == [hidden["orientations"][p] for p in picks]
    assert [i["position_key"] for i in items] == ["past", "present", "future"]


async def test_reveal_requires_exact_count_and_distinct_picks(client, registered):
    sid = (await _create(client, registered["headers"])).json()["session_id"]
    url = f"{API}/sessions/{sid}/reveal"
    too_few = await client.post(url, headers=registered["headers"], json={"positions": [1, 2]})
    assert too_few.status_code == 422
    assert too_few.json()["error"]["code"] == "selection_count_mismatch"
    too_many = await client.post(url, headers=registered["headers"], json={"positions": [1, 2, 3, 4]})
    assert too_many.json()["error"]["code"] == "selection_count_mismatch"
    duplicate = await client.post(url, headers=registered["headers"], json={"positions": [5, 5, 6]})
    assert duplicate.json()["error"]["code"] == "duplicate_selection"
    outside = await client.post(url, headers=registered["headers"], json={"positions": [0, 1, 78]})
    assert outside.json()["error"]["code"] == "selection_out_of_range"
    # None of the rejected attempts consumed the session.
    ok = await client.post(url, headers=registered["headers"], json={"positions": [0, 1, 2]})
    assert ok.status_code == 200


async def test_retry_returns_same_reading_and_orientation(client, registered):
    sid = (await _create(client, registered["headers"])).json()["session_id"]
    url = f"{API}/sessions/{sid}/reveal"
    first = (await client.post(url, headers=registered["headers"], json={"positions": [3, 9, 11]})).json()
    for _ in range(3):
        again = (await client.post(url, headers=registered["headers"], json={"positions": [3, 9, 11]})).json()
        assert again["id"] == first["id"]
        assert [i["orientation"] for i in again["items"]] == [i["orientation"] for i in first["items"]]
        assert [i["item_id"] for i in again["items"]] == [i["item_id"] for i in first["items"]]


async def test_completed_session_rejects_different_picks(client, registered):
    sid = (await _create(client, registered["headers"])).json()["session_id"]
    url = f"{API}/sessions/{sid}/reveal"
    await client.post(url, headers=registered["headers"], json={"positions": [1, 2, 3]})
    response = await client.post(url, headers=registered["headers"], json={"positions": [4, 5, 6]})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "session_already_completed"
    session = (await client.get(f"{API}/sessions/{sid}", headers=registered["headers"])).json()
    assert session["status"] == "completed" and session["reading_id"]


async def test_other_users_session_is_invisible(client, registered):
    sid = (await _create(client, registered["headers"])).json()["session_id"]
    other = await client.post(
        "/api/v1/auth/register",
        json={"email": "intruder@example.com", "password": "Str0ngPassphrase!", "name": "Intruder"},
    )
    headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert (await client.get(f"{API}/sessions/{sid}", headers=headers)).status_code == 404
    reveal = await client.post(f"{API}/sessions/{sid}/reveal", headers=headers, json={"positions": [1, 2, 3]})
    assert reveal.status_code == 404


async def test_expired_session_cannot_be_revealed(client, registered, session_factory):
    sid = (await _create(client, registered["headers"])).json()["session_id"]
    async with session_factory() as db:
        await db.execute(
            update(DivinationDrawSession)
            .where(DivinationDrawSession.id == uuid.UUID(sid))
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await db.commit()
    response = await client.post(
        f"{API}/sessions/{sid}/reveal", headers=registered["headers"], json={"positions": [1, 2, 3]}
    )
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "divination_session_expired"
    state = (await client.get(f"{API}/sessions/{sid}", headers=registered["headers"])).json()
    assert state["status"] == "expired"


async def test_concurrent_reveals_create_one_reading(client, registered, session_factory):
    sid = (await _create(client, registered["headers"])).json()["session_id"]
    url = f"{API}/sessions/{sid}/reveal"
    responses = await asyncio.gather(
        *(client.post(url, headers=registered["headers"], json={"positions": [10, 20, 30]}) for _ in range(10))
    )
    ok = [r for r in responses if r.status_code == 200]
    assert ok, [r.text for r in responses]
    assert len({r.json()["id"] for r in ok}) == 1
    async with session_factory() as db:
        count = await db.scalar(
            select(func.count()).select_from(DivinationReading).where(
                DivinationReading.draw_session_id == uuid.UUID(sid)
            )
        )
    assert count == 1


async def test_server_never_replaces_the_users_picks(client, registered, session_factory):
    """Many sessions: the revealed cards always equal the hidden slots picked."""
    for _ in range(5):
        body = (await _create(client, registered["headers"], deck="katina", spread="three_card")).json()
        hidden = await _hidden(session_factory, body["session_id"])
        picks = [64, 0, 32]
        reading = (
            await client.post(
                f"{API}/sessions/{body['session_id']}/reveal",
                headers=registered["headers"],
                json={"positions": picks},
            )
        ).json()
        items = sorted(reading["items"], key=lambda i: i["position_index"])
        assert [i["item_id"] for i in items] == [hidden["order"][p] for p in picks]
        # Katina never reverses.
        assert all(i["orientation"] == "upright" for i in items)


async def test_legacy_auto_draw_still_works(client, registered):
    response = await client.post(
        f"{API}/readings",
        headers=registered["headers"],
        json={"deck_type": "tarot", "spread_code": "single_card", "locale": "tr"},
    )
    assert response.status_code == 201
    spec = (await client.get("/api/v1/openapi.json")).json()
    assert spec["paths"]["/api/v1/divination/readings"]["post"].get("deprecated") is True
