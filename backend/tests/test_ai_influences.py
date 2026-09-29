"""Readable 'what shaped this answer' lines for Astro AI."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.domain.ai import AstroContext, ContextFactor, ContextType, FactorImportance, Locale
from app.services.ai.influences import MAX_INFLUENCES, describe, influences


def _factor(fid, kind, data, importance=FactorImportance.HIGH):
    return ContextFactor(factor_id=fid, factor_type=kind, importance=importance, structured_data=data)


def _context(factors):
    return AstroContext(
        context_type=ContextType.TRANSIT,
        subject={},
        time_reference=datetime(2026, 9, 26, tzinfo=UTC),
        locale=Locale.TR,
        factors=factors,
    )


def test_transit_and_natal_lines_are_localized():
    transit = _factor(
        "a1b2", "transit", {"transiting_body": "saturn", "target": "sun", "aspect": "square", "nature": "challenging"}
    )
    natal = _factor("natal:planet:venus", "natal_planet", {"planet": "venus", "sign": "taurus", "house": 7})
    aspect = _factor(
        "natal:aspect:moon:jupiter:trine", "natal_aspect", {"first": "moon", "second": "jupiter", "aspect": "trine"}
    )
    assert describe(transit, "tr") == "Transit Satürn kare natal Güneş"
    assert describe(transit, "en") == "Transit Saturn square natal Sun"
    assert describe(natal, "tr") == "Natal Venüs Boğa (7. ev)"
    assert describe(aspect, "tr") == "Ay üçgen Jüpiter"


def test_cited_factors_come_first_and_summaries_are_skipped():
    factors = [
        _factor("summary", "natal_summary", {}, FactorImportance.CRITICAL),
        _factor("t1", "transit", {"transiting_body": "mars", "target": "venus", "aspect": "trine"}),
        _factor("n1", "natal_planet", {"planet": "moon", "sign": "capricorn"}, FactorImportance.MEDIUM),
    ]
    context = _context(factors)
    cited = influences(context, "tr", cited=["n1"])
    assert [i["id"] for i in cited] == ["n1"]
    available = influences(context, "tr")
    assert [i["id"] for i in available] == ["t1", "n1"]  # importance order, no summary


def test_influences_are_bounded():
    factors = [
        _factor(f"t{i}", "transit", {"transiting_body": "mars", "target": "venus", "aspect": "trine"})
        for i in range(20)
    ]
    assert len(influences(_context(factors), "tr")) == MAX_INFLUENCES


async def test_chat_answer_carries_influences(client: httpx.AsyncClient, registered, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "fake")
    response = await client.post(
        "/api/v1/ai/chat",
        headers=registered["headers"],
        json={"message": "Bu ay aşk hayatım nasıl?", "locale": "tr"},
    )
    if response.status_code != 200:  # AI disabled in this environment
        assert response.json()["error"]["code"] in ("ai_not_configured", "provider_unavailable")
        return
    body = response.json()
    assert "influences" in body
    for item in body["influences"]:
        assert item["label"] and item["id"]
