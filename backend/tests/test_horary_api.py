"""Horary API: ownership, the question-is-the-chart rule, and caching."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

API = "/api/v1"

ISTANBUL = {"latitude": 41.0082, "longitude": 28.9784, "location_name": "Istanbul"}


async def _ask(
    client: httpx.AsyncClient, registered, **overrides
) -> httpx.Response:
    payload = {
        "question": "Will the contract be signed?",
        "category": "career",
        **ISTANBUL,
        **overrides,
    }
    return await client.post(
        f"{API}/horary/questions", headers=registered["headers"], json=payload
    )


async def test_question_lifecycle(client: httpx.AsyncClient, registered):
    created = await _ask(client, registered)
    assert created.status_code == 201
    question = created.json()

    assert question["status"] == "created"
    assert question["timezone"] == "Europe/Istanbul"  # derived from coordinates
    assert question["duplicate_suspected"] is False
    assert question["chart_id"] is None

    calculated = await client.post(
        f"{API}/horary/questions/{question['id']}/calculate",
        headers=registered["headers"],
    )
    assert calculated.status_code == 200
    assert calculated.json()["status"] == "calculated"
    assert calculated.json()["chart_id"]

    analysis = await client.get(
        f"{API}/horary/questions/{question['id']}/analysis",
        headers=registered["headers"],
    )
    assert analysis.status_code == 200
    body = analysis.json()

    assert body["querent_house"] == 1
    assert body["quesited_house"] == 10  # career
    assert body["querent"]["planet"] not in ("uranus", "neptune", "pluto")
    assert body["co_significator"]["planet"] == "moon"
    assert body["moon"]["void_definition"] == "traditional_sign_based_v1"
    assert body["house_rulers"]
    assert body["source_factors"]
    assert body["not_implemented"]
    assert body["rules_version"] == "horary_rules_v1"
    assert body["dignity_version"] == "dignity_rules_v1"


async def test_analysis_response_contains_no_verdict(
    client: httpx.AsyncClient, registered
):
    created = await _ask(client, registered, question="Will we marry?")
    response = await client.get(
        f"{API}/horary/questions/{created.json()['id']}/analysis",
        headers=registered["headers"],
    )
    payload = response.text.lower()
    for forbidden in ('"answer"', '"verdict"', '"yes"', '"no"'):
        assert forbidden not in payload


async def test_analysis_is_cached_and_refreshable(
    client: httpx.AsyncClient, registered
):
    created = await _ask(client, registered, question="Is the job offer real?")
    question_id = created.json()["id"]

    first = await client.get(
        f"{API}/horary/questions/{question_id}/analysis",
        headers=registered["headers"],
    )
    second = await client.get(
        f"{API}/horary/questions/{question_id}/analysis",
        headers=registered["headers"],
    )
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert first.json()["querent"]["planet"] == second.json()["querent"]["planet"]

    refreshed = await client.get(
        f"{API}/horary/questions/{question_id}/analysis",
        headers=registered["headers"],
        params={"refresh": "true"},
    )
    assert refreshed.json()["cached"] is False


async def test_house_override_is_honoured(client: httpx.AsyncClient, registered):
    created = await _ask(
        client, registered, question="Where is my lost ring?", category="lost_object",
        house_override=4,
    )
    analysis = await client.get(
        f"{API}/horary/questions/{created.json()['id']}/analysis",
        headers=registered["headers"],
    )
    assert analysis.json()["quesited_house"] == 4


async def test_birth_profile_changes_do_not_touch_a_horary_chart(
    client: httpx.AsyncClient, registered
):
    """The question's moment is the chart. Nothing about the querent's birth
    data may change it."""
    created = await _ask(client, registered, question="Will the deal close?")
    question_id = created.json()["id"]

    before = await client.get(
        f"{API}/horary/questions/{question_id}/analysis",
        headers=registered["headers"],
        params={"refresh": "true"},
    )

    await client.put(
        f"{API}/birth-profiles/me",
        headers=registered["headers"],
        json={
            "birth_date": "1979-03-09",
            "birth_time": "22:10:00",
            "birth_place": "Tokyo",
        },
    )

    after = await client.get(
        f"{API}/horary/questions/{question_id}/analysis",
        headers=registered["headers"],
        params={"refresh": "true"},
    )

    assert after.json()["querent"]["planet"] == before.json()["querent"]["planet"]
    assert after.json()["asked_at_utc"] == before.json()["asked_at_utc"]
    assert after.json()["moon"]["degree"] == before.json()["moon"]["degree"]


async def test_two_questions_minutes_apart_get_different_charts(
    client: httpx.AsyncClient, registered
):
    earlier = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)
    first = await _ask(
        client, registered, question="Question one?", asked_at=earlier.isoformat()
    )
    second = await _ask(
        client,
        registered,
        question="Question two?",
        asked_at=(earlier + timedelta(hours=3)).isoformat(),
    )

    analyses = []
    for created in (first, second):
        response = await client.get(
            f"{API}/horary/questions/{created.json()['id']}/analysis",
            headers=registered["headers"],
        )
        analyses.append(response.json())

    assert analyses[0]["asked_at_utc"] != analyses[1]["asked_at_utc"]
    assert (
        analyses[0]["querent"]["planet"] != analyses[1]["querent"]["planet"]
        or analyses[0]["moon"]["degree"] != analyses[1]["moon"]["degree"]
    )


async def test_repeat_question_is_flagged_not_blocked(
    client: httpx.AsyncClient, registered
):
    first = await _ask(client, registered, question="Will they call me back?")
    assert first.json()["duplicate_suspected"] is False

    # Same question again: allowed, and flagged.
    second = await _ask(client, registered, question="will they call me back")
    assert second.status_code == 201
    assert second.json()["duplicate_suspected"] is True

    analysis = await client.get(
        f"{API}/horary/questions/{second.json()['id']}/analysis",
        headers=registered["headers"],
    )
    codes = {item["code"] for item in analysis.json()["warnings"]}
    assert "question_repeat_suspected" in codes


async def test_location_is_required(client: httpx.AsyncClient, registered):
    response = await client.post(
        f"{API}/horary/questions",
        headers=registered["headers"],
        json={"question": "Will it rain?", "category": "general"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_questions_are_private(client: httpx.AsyncClient, registered):
    created = await _ask(client, registered, question="My private question?")
    question_id = created.json()["id"]

    other = await client.post(
        f"{API}/auth/register",
        json={
            "email": "stranger@example.com",
            "password": "Str0ngPassphrase!",
            "name": "Stranger",
        },
    )
    headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    for path in (
        f"horary/questions/{question_id}",
        f"horary/questions/{question_id}/analysis",
    ):
        response = await client.get(f"{API}/{path}", headers=headers)
        assert response.status_code == 404

    listing = await client.get(f"{API}/horary/questions", headers=headers)
    assert listing.json() == []


async def test_horary_requires_auth(client: httpx.AsyncClient):
    assert (await client.get(f"{API}/horary/questions")).status_code == 401
    assert (
        await client.post(f"{API}/horary/questions", json={"question": "x?"})
    ).status_code == 401
