"""Token budgeting for the context.

Rules:

* Nothing is truncated mid-structure. Factors are dropped whole, lowest
  importance first, so the model never sees half a transit.
* **Critical factors are never dropped**: warnings, exact contacts, horary
  significators and perfection, the source a report is about. Trimming one of
  those to save tokens would silently change what the reading is about.
* What was dropped is recorded on the context, so the omission is visible
  rather than invisible.
"""

from __future__ import annotations

import json

from app.domain.ai import ContextFactor, FactorImportance

# Rough characters-per-token. Deliberately pessimistic: Turkish and
# Azerbaijani tokenise worse than English, and overshooting the budget is a
# 400 from the provider while undershooting is only a slightly shorter prompt.
CHARS_PER_TOKEN = 3.2


def estimate_tokens(value: object) -> int:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
    return int(len(text) / CHARS_PER_TOKEN) + 1


def factor_tokens(factor: ContextFactor) -> int:
    return estimate_tokens(
        {
            "factor_id": factor.factor_id,
            "factor_type": factor.factor_type,
            "importance": factor.importance.value,
            "label": factor.label,
            "data": factor.structured_data,
        }
    )


def trim_factors(
    factors: list[ContextFactor], budget: int
) -> tuple[list[ContextFactor], list[str], int]:
    """Fit factors into ``budget`` tokens.

    Returns ``(kept, dropped_ids, tokens_used)``. Ordering inside an
    importance band is preserved, so the builder's own ranking still decides
    what goes first.
    """
    critical = [item for item in factors if item.is_critical]
    optional = [item for item in factors if not item.is_critical]

    kept: list[ContextFactor] = list(critical)
    used = sum(factor_tokens(item) for item in kept)

    # Critical material can exceed the budget; it is kept anyway, and the
    # caller sees the real token count rather than a comfortable lie.
    ranked = sorted(
        optional,
        key=lambda item: (item.importance.rank, -_weight(item)),
    )

    dropped: list[str] = []
    for factor in ranked:
        cost = factor_tokens(factor)
        if used + cost <= budget:
            kept.append(factor)
            used += cost
        else:
            dropped.append(factor.factor_id)

    order = {factor.factor_id: index for index, factor in enumerate(factors)}
    kept.sort(key=lambda item: order.get(item.factor_id, 0))
    return kept, dropped, used


def _weight(factor: ContextFactor) -> float:
    """Secondary ordering inside an importance band.

    Anything the engine already scored (transits, themes, personal events)
    carries a strength; stronger material survives a tight budget.
    """
    data = factor.structured_data
    for key in ("strength", "score", "weight", "importance_score"):
        value = data.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def budget_report() -> dict:
    from app.core.config import settings

    return {
        "chat_context_budget": settings.ai_chat_context_budget,
        "report_context_budget": settings.ai_report_context_budget,
        "summary_budget": settings.ai_summary_budget,
        "chars_per_token": CHARS_PER_TOKEN,
    }


CRITICAL = FactorImportance.CRITICAL
HIGH = FactorImportance.HIGH
MEDIUM = FactorImportance.MEDIUM
LOW = FactorImportance.LOW
