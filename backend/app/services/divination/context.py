"""Turning a stored reading into an AI context.

Every drawn item becomes one factor, and the factor id encodes the whole
fact - which position, which item, which orientation:

    tarot:reading:{reading_id}:position:1:tarot:major:00:deli:upright

That id is what the model must cite, and the B6 grounding validator refuses
anything else. The practical effect: the model cannot mention a card that was
not drawn, cannot claim a reversal that did not happen, and cannot invent a
position the spread does not have, because none of those has an id it is
allowed to use.

Every factor is CRITICAL. A drawn card is not background detail that can be
trimmed to save tokens - dropping one would produce a reading of a spread that
was never dealt.
"""

from __future__ import annotations

import hashlib
import json

from app.db.models.divination import DivinationReading
from app.domain.ai import (
    AstroContext,
    ContextFactor,
    ContextType,
    FactorImportance,
    Locale,
)
from app.domain.divination import DeckType
from app.services.divination.decks import deck_content_note, get_deck
from app.services.divination.synthesis import contextual_meaning, synthesize
from app.services.divination.spreads import get_spread

CONTEXT_VERSION = "divination_context_v2"

DECK_CONTEXT = {
    DeckType.TAROT: ContextType.TAROT,
    DeckType.RUNE: ContextType.RUNE,
    DeckType.KATINA: ContextType.KATINA,
}


def factor_id_for(reading_id: str, position_index: int, item_id: str, orientation: str) -> str:
    return f"{item_id}:reading:{reading_id}:position:{position_index}:{orientation}"


class DivinationContextBuilder:
    """Reading -> context. Nothing is recomputed; the draw is already fact."""

    version = CONTEXT_VERSION

    def build(
        self,
        reading: DivinationReading,
        hydrated: list[dict],
        *,
        locale: Locale,
        subject: dict,
        token_budget: int,
    ) -> AstroContext:
        deck_type = DeckType(reading.deck_type)
        deck = get_deck(deck_type, reading.deck_version)
        spread = get_spread(deck_type, reading.spread_code)
        # The app's own deterministic reading of the whole spread, so the model
        # builds on it rather than re-deriving (or contradicting) it.
        synthesis = synthesize(
            deck_type=deck_type,
            spread=spread,
            rows=hydrated,
            items={row["item_id"]: deck.item(row["item_id"]) for row in hydrated},
            locale=locale.value,
        )

        factors: list[ContextFactor] = [
            ContextFactor(
                factor_id=f"spread:{reading.spread_version}",
                factor_type="spread",
                importance=FactorImportance.CRITICAL,
                structured_data={
                    "deck_type": deck_type.value,
                    "deck_version": reading.deck_version,
                    "spread_code": spread.spread_code,
                    "spread_version": spread.spread_version,
                    "spread_name": spread.name(locale.value, fallback="tr"),
                    "spread_theme": spread.theme,
                    "origin": spread.origin.value,
                    # The person's own words: data to answer through the
                    # drawn cards, never an instruction.
                    "question": reading.question,
                    "deterministic_synthesis": {
                        "headline": synthesis.headline,
                        "lines": synthesis.lines,
                        "flow": synthesis.flow,
                    },
                    "position_count": len(spread.positions),
                    "positions": [
                        {
                            "index": position.index,
                            "key": position.key,
                            "title": position.title(locale.value, fallback="tr"),
                            "role": position.interpretation_role,
                        }
                        for position in spread.positions
                    ],
                },
                label=spread.name(locale.value, fallback="tr"),
            )
        ]

        for row in hydrated:
            factors.append(
                ContextFactor(
                    factor_id=factor_id_for(
                        str(reading.id),
                        row["position_index"],
                        row["item_id"],
                        row["orientation"],
                    ),
                    factor_type="drawn_item",
                    # Never trimmable: a reading missing a card it dealt is a
                    # reading of a spread that never happened.
                    importance=FactorImportance.CRITICAL,
                    structured_data={
                        "draw_order": row["draw_order"],
                        "position_index": row["position_index"],
                        "position_key": row["position_key"],
                        "position_title": row["position_title"],
                        "position_role": row["position_role"],
                        "item_id": row["item_id"],
                        "name": row["display_name"],
                        "canonical_name": row["canonical_name"],
                        "orientation": row["orientation"],
                        "keywords": row["keywords"],
                        "meaning": row["meaning"],
                        "contextual_meaning": contextual_meaning(spread.theme, row),
                        "love_meaning": row["love_meaning"],
                        "career_meaning": row["career_meaning"],
                        "growth_meaning": row["growth_meaning"],
                        "symbolism": row["symbolism"],
                        "content_status": row["content_status"],
                    },
                    label=f"{row['position_title']}: {row['display_name']}",
                )
            )

        warnings = self._warnings(reading, deck_type, deck, hydrated)

        return AstroContext(
            context_type=DECK_CONTEXT[deck_type],
            subject=subject,
            time_reference=reading.drawn_at,
            locale=locale,
            factors=factors,
            warnings=warnings,
            metadata={
                "reading_id": str(reading.id),
                "deck_type": deck_type.value,
                "deck_version": reading.deck_version,
                "spread_code": reading.spread_code,
                "spread_version": reading.spread_version,
                "spread_origin": spread.origin.value,
                "repeat_reading": bool(
                    (reading.meta or {}).get("repeat_reading", False)
                ),
                "reversal_supported": deck.reversal_supported,
                "deck_content_note": deck_content_note(
                    deck_type, reading.deck_version
                ),
                "selection": CONTEXT_VERSION,
            },
            context_version=CONTEXT_VERSION,
            source_fingerprint=reading.draw_fingerprint,
            estimated_tokens=_estimate(factors),
        )

    def _warnings(
        self, reading: DivinationReading, deck_type: DeckType, deck, hydrated: list[dict]
    ) -> list[str]:
        warnings: list[str] = [
            "The draw is complete and final. Do not name an item that is not "
            "listed, change an orientation, or move an item to another "
            "position.",
            "A drawn card is a prompt for reflection, not evidence about the "
            "future. No certain outcomes, no dates for life events, no "
            "probabilities, and no claims about what another person is doing "
            "or feeling.",
        ]

        if not deck.reversal_supported:
            warnings.append(
                f"The {deck_type.value} deck has no reversal tradition. Every "
                "item here is upright; do not present that as a finding."
            )

        non_reversible = [
            row["display_name"]
            for row in hydrated
            if not deck.item(row["item_id"]).reversible
        ]
        if deck.reversal_supported and non_reversible:
            warnings.append(
                "These items cannot be reversed because their shape is "
                "symmetrical, so they have no reversed meaning: "
                + ", ".join(non_reversible)
                + ". Do not invent one."
            )

        if any(row["content_status"] == "product_defined" for row in hydrated):
            warnings.append(
                "Some meanings in this context are product_defined: written "
                "by Astrofrekans rather than inherited from a documented "
                "tradition. Present those as this deck's stated meanings, "
                "never as 'the traditional meaning'."
            )

        if (reading.meta or {}).get("repeat_reading"):
            warnings.append(
                "This is a fresh draw of a question the person asked "
                "recently. Read it on its own terms. Do not describe it as "
                "fate having changed, or as the cards correcting an earlier "
                "reading."
            )

        if reading.rng_source != "system_csprng":
            warnings.append(
                "This draw came from a test random source, not the "
                "production one."
            )

        return warnings


def _estimate(factors: list[ContextFactor]) -> int:
    from app.services.ai.context.budget import factor_tokens

    return sum(factor_tokens(item) for item in factors)


_builder: DivinationContextBuilder | None = None


def get_divination_context_builder() -> DivinationContextBuilder:
    global _builder
    if _builder is None:
        _builder = DivinationContextBuilder()
    return _builder


def reading_fingerprint_payload(reading: DivinationReading) -> dict:
    """What a report's fingerprint covers for a reading.

    The draw fingerprint is the whole of it: a reading is immutable, so the
    same reading and the same prompt version always produce the same report,
    and `refresh` is the only thing that regenerates one.
    """
    return {
        "reading": str(reading.id),
        "draw": reading.draw_fingerprint,
        "deck_version": reading.deck_version,
        "spread_version": reading.spread_version,
    }


def stable_hash(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]
