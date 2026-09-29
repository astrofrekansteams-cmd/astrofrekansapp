"""Intent routing for Astro AI chat.

Rule-first and deterministic: the same question always routes the same way,
which is testable and free. A model is only consulted when the rules find
nothing, and even then it may only pick a label - it never touches the user's
astrological data, and its answer is cached.

``intent_rules_v1``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.domain.ai import ContextType, Intent

INTENT_RULES_VERSION = "intent_rules_v1"

# Keywords per intent, in the three product languages. Matching is
# accent-folded, so "ilişki" also matches "iliski" as users often type.
KEYWORDS: dict[Intent, tuple[str, ...]] = {
    Intent.TODAY: (
        "bugun", "bugunku", "gunluk", "bu gun",
        "bugun", "gunun", "bu gunku",
        "today", "todays", "daily", "this day",
    ),
    Intent.WEEK: (
        "bu hafta", "haftalik", "haftaya", "hafta",
        "this week", "weekly", "week ahead",
    ),
    Intent.MONTH: (
        "bu ay", "aylik", "ay icinde", "onumuzdeki ay",
        "bu ay", "ayliq",
        "this month", "monthly", "month ahead",
    ),
    Intent.YEAR: (
        "bu yil", "yillik", "gelecek yil", "seneye",
        "bu il", "illik",
        "this year", "yearly", "annual", "year ahead",
    ),
    Intent.TRANSIT: (
        "transit", "transitler", "gecis", "gecisler",
        "retro", "retrograd", "tutulma",
        "eclipse", "retrograde", "station",
    ),
    Intent.LOVE: (
        "ask", "asik", "sevgili", "romantik", "flort",
        "eshq", "sevgi",
        "love", "romance", "dating", "crush",
    ),
    Intent.RELATIONSHIP: (
        "iliski", "partner", "es", "evlilik", "ayrilik", "bosanma",
        "munasibet", "evlenmek",
        "relationship", "marriage", "partner", "breakup", "divorce",
    ),
    Intent.COMPATIBILITY: (
        "uyum", "sinastri", "uyumlu muyuz", "birlikte", "kompozit",
        "uygunluq", "sinastriya",
        "compatibility", "synastry", "composite", "davison", "match",
    ),
    Intent.CAREER: (
        "kariyer", "is", "meslek", "terfi", "patron", "sirket", "isim",
        "karyera", "is yeri",
        "career", "job", "work", "promotion", "business", "boss",
    ),
    Intent.MONEY: (
        "para", "maas", "finans", "borc", "kazanc", "butce", "yatirim",
        "pul", "maas",
        "money", "salary", "finance", "debt", "income", "budget",
    ),
    Intent.NATAL: (
        "dogum haritam", "natal", "haritam", "yukselen", "burcum",
        "dogum xeritesi",
        "natal", "birth chart", "my chart", "rising", "ascendant",
    ),
    Intent.HORARY_REFERENCE: (
        "horary", "soru haritasi", "sorumun haritasi",
        "horary chart", "my question chart",
    ),
}

# Which context each intent needs.
INTENT_CONTEXT: dict[Intent, ContextType] = {
    Intent.GENERAL: ContextType.GENERAL_ASTRO_CHAT,
    Intent.NATAL: ContextType.NATAL,
    Intent.LOVE: ContextType.NATAL,
    Intent.RELATIONSHIP: ContextType.NATAL,
    Intent.CAREER: ContextType.MONTHLY,
    Intent.MONEY: ContextType.MONTHLY,
    Intent.TRANSIT: ContextType.TRANSIT,
    Intent.TODAY: ContextType.DAILY,
    Intent.WEEK: ContextType.WEEKLY,
    Intent.MONTH: ContextType.MONTHLY,
    Intent.YEAR: ContextType.YEARLY,
    Intent.COMPATIBILITY: ContextType.SYNASTRY,
    Intent.HORARY_REFERENCE: ContextType.HORARY,
}

# When several intents match, the more specific time frame wins over the more
# general life area: "career this month" is a monthly question about career.
PRIORITY: tuple[Intent, ...] = (
    Intent.HORARY_REFERENCE,
    Intent.COMPATIBILITY,
    Intent.TODAY,
    Intent.WEEK,
    Intent.MONTH,
    Intent.YEAR,
    Intent.TRANSIT,
    Intent.NATAL,
    Intent.LOVE,
    Intent.RELATIONSHIP,
    Intent.CAREER,
    Intent.MONEY,
)


@dataclass(slots=True, frozen=True)
class IntentResult:
    intent: Intent
    context_type: ContextType
    matched: list[Intent]
    confidence: float
    source: str = "rules"
    rules_version: str = INTENT_RULES_VERSION


def fold(text: str) -> str:
    """Lowercase and strip accents so Turkish typing variants still match."""
    lowered = text.casefold().replace("ı", "i").replace("İ", "i")
    decomposed = unicodedata.normalize("NFKD", lowered)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped)


def classify(message: str, *, explicit: ContextType | None = None) -> IntentResult:
    """Route a message. Deterministic, and never reads the user's chart."""
    if explicit is not None:
        intent = next(
            (key for key, value in INTENT_CONTEXT.items() if value is explicit),
            Intent.GENERAL,
        )
        return IntentResult(
            intent=intent,
            context_type=explicit,
            matched=[intent],
            confidence=1.0,
            source="explicit",
        )

    folded = fold(message)
    matched = [
        intent
        for intent, words in KEYWORDS.items()
        if any(word in folded for word in words)
    ]

    if not matched:
        return IntentResult(
            intent=Intent.GENERAL,
            context_type=ContextType.GENERAL_ASTRO_CHAT,
            matched=[],
            confidence=0.3,
        )

    chosen = next((item for item in PRIORITY if item in matched), matched[0])
    # Several signals agreeing is not more certain than one clear signal; a
    # single unambiguous match is the strongest case.
    confidence = 0.9 if len(matched) == 1 else 0.75
    return IntentResult(
        intent=chosen,
        context_type=INTENT_CONTEXT[chosen],
        matched=matched,
        confidence=confidence,
    )
