"""Deterministic whole-spread reading.

Before (and without) any AI interpretation, a spread already says something
as a whole: how many Major Arcana fell, which suit or aett dominates, how many
cards came reversed, and how the positions read in order. This module turns
those counts into fixed TR/EN sentences. The AI interpretation stays a
separate, optional deepening step.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from app.domain.divination import DeckType, DivinationItem, DivinationSpread

SYNTHESIS_VERSION = "spread_synthesis_v1"

Text = tuple[str, str]


def _pick(text: Text, locale: str) -> str:
    return text[1] if locale == "en" else text[0]


SUIT_THEMES: dict[str, Text] = {
    "wands": ("Değnekler ağırlıkta: tutku, girişim ve harekete geçme enerjisi öne çıkıyor.",
              "Wands dominate: passion, initiative and the urge to act come forward."),
    "cups": ("Kupalar ağırlıkta: duygular, ilişkiler ve iç dünya konunun merkezinde.",
             "Cups dominate: feelings, relationships and the inner world are central."),
    "swords": ("Kılıçlar ağırlıkta: düşünceler, kararlar ve iletişim belirleyici.",
               "Swords dominate: thoughts, decisions and communication are decisive."),
    "pentacles": ("Tılsımlar ağırlıkta: para, iş ve somut sonuçlar gündemde.",
                  "Pentacles dominate: money, work and tangible results are in focus."),
}

AETT_THEMES: dict[str, Text] = {
    "freyr": ("Freyr aett'i ağırlıkta: temel ihtiyaçlar, kaynaklar ve bereket teması.",
              "Freyr's aett dominates: basic needs, resources and abundance."),
    "heimdall": ("Heimdall aett'i ağırlıkta: kontrol dışındaki güçler ve sınanma teması.",
                 "Heimdall's aett dominates: forces beyond control and being tested."),
    "tyr": ("Tyr aett'i ağırlıkta: ilişkiler, adalet ve ruhsal gelişim teması.",
             "Tyr's aett dominates: relationships, justice and spiritual growth."),
}


@dataclass(slots=True)
class SpreadSynthesis:
    headline: str
    lines: list[str] = field(default_factory=list)
    flow: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    version: str = SYNTHESIS_VERSION


def synthesize(
    *,
    deck_type: DeckType,
    spread: DivinationSpread,
    rows: list[dict],
    items: dict[str, DivinationItem],
    locale: str,
) -> SpreadSynthesis:
    total = len(rows)
    reversed_count = sum(1 for row in rows if row["orientation"] == "reversed")
    lines: list[str] = []
    counts: dict[str, int] = {"cards": total, "reversed": reversed_count}

    if deck_type is DeckType.TAROT:
        majors = sum(
            1 for row in rows
            if items[row["item_id"]].arcana is not None
            and items[row["item_id"]].arcana.value == "major"
        )
        counts["major"] = majors
        if total > 1:
            if majors * 2 >= total:
                lines.append(_pick((
                    f"{total} kartın {majors} tanesi Büyük Arkana: konu gündelik değil, hayatının büyük temalarına dokunuyor.",
                    f"{majors} of {total} cards are Major Arcana: this touches the larger themes of your life, not daily details.",
                ), locale))
            elif majors == 0:
                lines.append(_pick((
                    "Hiç Büyük Arkana çıkmadı: konu günlük hayatın ve senin seçimlerinin alanında.",
                    "No Major Arcana fell: the matter lies within daily life and your own choices.",
                ), locale))
        suits = Counter(
            items[row["item_id"]].suit.value
            for row in rows
            if items[row["item_id"]].suit is not None
        )
        for suit, count in suits.items():
            counts[suit] = count
        if suits:
            suit, count = suits.most_common(1)[0]
            if count >= 2 and list(suits.values()).count(count) == 1:
                lines.append(_pick(SUIT_THEMES[suit], locale))

    elif deck_type is DeckType.RUNE:
        aetts = Counter(
            items[row["item_id"]].aett.value
            for row in rows
            if items[row["item_id"]].aett is not None
        )
        for aett, count in aetts.items():
            counts[aett] = count
        if total > 1 and aetts:
            aett, count = aetts.most_common(1)[0]
            if count >= 2 and list(aetts.values()).count(count) == 1:
                lines.append(_pick(AETT_THEMES[aett], locale))

    if total > 1 and spread.allow_reversed:
        if reversed_count == 0:
            lines.append(_pick((
                "Tüm kartlar düz geldi: enerji açık ve dışa dönük akıyor.",
                "Every card came upright: the energy flows openly and outward.",
            ), locale))
        elif reversed_count * 2 > total:
            lines.append(_pick((
                f"{reversed_count}/{total} kart ters: dışarıdan çok iç engellere, gecikmelere ve yeniden değerlendirmeye bakıyor.",
                f"{reversed_count}/{total} cards reversed: the reading points to inner blocks, delays and reassessment.",
            ), locale))

    flow = [
        f"{row['position_title']}: {row['display_name']}"
        + (_pick((" (ters)", " (reversed)"), locale) if row["orientation"] == "reversed" else "")
        + (f" — {row['keywords'][0]}" if row["keywords"] else "")
        for row in sorted(rows, key=lambda r: r["position_index"])
    ]

    if total == 1:
        row = rows[0]
        headline = _pick((
            f"Mesajın: {row['display_name']}" + (f" — {', '.join(row['keywords'][:2])}" if row["keywords"] else ""),
            f"Your message: {row['display_name']}" + (f" — {', '.join(row['keywords'][:2])}" if row["keywords"] else ""),
        ), locale)
    else:
        first = min(rows, key=lambda r: r["position_index"])
        last = max(rows, key=lambda r: r["position_index"])
        headline = _pick((
            f"{first['position_title']} konumundaki {first['display_name']} ile başlayan hikâye, "
            f"{last['position_title']} konumunda {last['display_name']} ile tamamlanıyor.",
            f"The story opens with {first['display_name']} as {first['position_title']} and closes "
            f"with {last['display_name']} as {last['position_title']}.",
        ), locale)

    return SpreadSynthesis(headline=headline, lines=lines, flow=flow, counts=counts)


def contextual_meaning(theme: str, row: dict) -> str:
    """The item's meaning for this spread's theme, falling back to general."""
    by_theme = {
        "love": row.get("love_meaning"),
        "relationship": row.get("love_meaning"),
        "career": row.get("career_meaning"),
        "money": row.get("career_meaning"),
        "spiritual": row.get("growth_meaning"),
    }
    return by_theme.get(theme) or row.get("meaning") or ""
