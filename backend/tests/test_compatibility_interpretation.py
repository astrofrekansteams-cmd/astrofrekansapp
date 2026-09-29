"""Grounded AI readings of compatibility calculations.

The engine calculates; the model only reads what was calculated. These tests
pin the plumbing: one reading per calculation kind, each with its own prompt,
grounded in the stored calculation, cached, free, owner-only - and the
calculation never depends on the AI being available.
"""

from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.services.ai import factory
from app.services.ai.fake_provider import FakeAIProvider

API = "/api/v1"
PAYLOAD = {
    "person_a": {"me": True},
    "person_b": {
        "birth_date": "1994-08-21",
        "birth_time": "09:45:00",
        "latitude": 51.5072,
        "longitude": -0.1276,
        "timezone": "Europe/London",
        "label": "Deniz",
    },
}


@pytest.fixture
def ai(monkeypatch) -> FakeAIProvider:
    monkeypatch.setattr(settings, "ai_provider", "fake")
    provider = FakeAIProvider()
    factory.set_ai_provider(provider)
    yield provider
    factory.set_ai_provider(None)


async def _calculate(client, headers, kind: str, **extra) -> dict:
    response = await client.post(
        f"{API}/compatibility/{kind}", headers=headers, json={**PAYLOAD, **extra}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _interpret(client, headers, report_id: str, **body):
    return await client.post(
        f"{API}/compatibility/reports/{report_id}/interpretation",
        headers=headers,
        json={"background": False, **body},
    )


@pytest.mark.parametrize(
    ("kind", "prompt_version", "framing"),
    [
        ("synastry", "synastry_reading_v1", "how these two people affect each other"),
        ("composite", "composite_reading_v1", "the relationship itself as a third thing"),
        ("davison", "davison_reading_v1", "real chart for a real instant and place"),
    ],
)
async def test_each_kind_gets_its_own_grounded_reading(
    client: httpx.AsyncClient, registered, ai, kind, prompt_version, framing
):
    calculation = await _calculate(client, registered["headers"], kind)
    response = await _interpret(client, registered["headers"], calculation["report_id"])
    assert response.status_code == 200, response.text
    report = response.json()

    assert report["report_type"] == f"{kind}_reading"
    assert report["source_type"] == "compatibility_report"
    assert report["source_id"] == calculation["report_id"]
    assert report["prompt_version"] == prompt_version

    # Its own framing, and the shared grounding rules.
    instructions = ai.calls[-1].instructions
    assert framing in instructions
    assert "Never compute or name a planet" in instructions
    assert "never give a percentage" in instructions

    # Only calculated factors can be cited.
    context = ai.calls[-1].input[0]["content"]
    if kind == "synastry":
        calculated = {a["id"] for a in calculation["aspects"]} | {
            o["id"]
            for o in calculation["overlays_a_in_b"] + calculation["overlays_b_in_a"]
        } | {"synastry:scores"}
    else:
        chart = calculation["chart"]
        calculated = {f"{kind}:summary"} | {
            f"{kind}:planet:{p['planet']}" for p in chart["planets"]
        } | {
            f"{kind}:aspect:{a['first']}:{a['second']}:{a['aspect']}"
            for a in (calculation.get("aspects") or chart["aspects"])
        }
    cited = {fid for s in report["sections"] for fid in s["factor_ids"]}
    assert cited, "a grounded reading cites its factors"
    assert cited <= calculated
    for factor_id in cited:
        assert factor_id in context


async def test_the_reading_is_cached_per_calculation(
    client: httpx.AsyncClient, registered, ai
):
    calculation = await _calculate(client, registered["headers"], "composite")
    first = (await _interpret(client, registered["headers"], calculation["report_id"])).json()
    calls = len(ai.calls)

    again = await _interpret(client, registered["headers"], calculation["report_id"])
    assert again.status_code == 200
    assert again.json()["id"] == first["id"]
    assert again.json()["cached"] is True
    assert len(ai.calls) == calls  # no second model call

    # A background request for an existing reading answers with it directly
    # (200) instead of queueing a job that would only find the same snapshot.
    background = await _interpret(
        client, registered["headers"], calculation["report_id"], background=True
    )
    assert background.status_code == 200
    assert background.json()["id"] == first["id"]
    assert len(ai.calls) == calls

    fresh = await _interpret(
        client, registered["headers"], calculation["report_id"], refresh=True
    )
    assert fresh.json()["id"] != first["id"]


async def test_a_repeated_calculation_keeps_its_report_id(
    client: httpx.AsyncClient, registered, ai
):
    """A cache hit must still say which stored calculation it is, or the app
    could not ask for (or reuse) its reading."""
    first = await _calculate(client, registered["headers"], "synastry")
    second = await _calculate(client, registered["headers"], "synastry")
    assert second["cached"] is True
    assert second["report_id"] == first["report_id"]


async def test_background_answers_with_a_job(client: httpx.AsyncClient, registered, ai):
    calculation = await _calculate(client, registered["headers"], "davison")
    response = await _interpret(
        client, registered["headers"], calculation["report_id"], background=True
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["report_type"] == "davison_reading"
    status = await client.get(
        f"{API}/ai/report-jobs/{job['id']}", headers=registered["headers"]
    )
    assert status.status_code == 200


async def test_the_short_reading_is_free_even_where_the_long_report_is_paid(
    client: httpx.AsyncClient, registered, ai
):
    """The long synastry report needs a credit; the short reading does not
    replace or unlock it."""
    calculation = await _calculate(client, registered["headers"], "synastry")
    response = await _interpret(client, registered["headers"], calculation["report_id"])
    assert response.status_code == 200, response.text

    long_report = await client.post(
        f"{API}/ai/reports",
        headers=registered["headers"],
        json={"report_type": "synastry", "source_id": calculation["report_id"]},
    )
    assert long_report.status_code != 200


async def test_another_users_calculation_is_invisible(
    client: httpx.AsyncClient, registered, ai
):
    calculation = await _calculate(client, registered["headers"], "synastry")
    other = await client.post(
        f"{API}/auth/register",
        json={
            "email": "stranger@example.com",
            "password": "An0therStrongPass!",
            "name": "Stranger",
            "birth_date": "1988-11-02",
            "birth_time": "06:15:00",
            "birth_place": "Ankara",
        },
    )
    headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    response = await _interpret(client, headers, calculation["report_id"])
    assert response.status_code == 404


async def test_calculation_works_without_ai(
    client: httpx.AsyncClient, registered, monkeypatch
):
    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", None)
    factory.set_ai_provider(None)
    try:
        calculation = await _calculate(client, registered["headers"], "composite")
        assert calculation["chart"]["planets"]
        refused = await _interpret(client, registered["headers"], calculation["report_id"])
        assert refused.status_code == 503
        assert refused.json()["error"]["code"] == "ai_not_configured"
    finally:
        factory.set_ai_provider(None)
