"""Loading decks from versioned data files.

**Why static files rather than database tables.** Card meanings are content,
not state: they are written once, reviewed, and then change rarely and
deliberately. Keeping them as versioned JSON in the repository means a change
is a diff somebody can read in a pull request, the same deck data ships with
the code that interprets it, and a deployment cannot end up with a deck the
running code has never seen. A database table would add a migration, a seeding
path and a drift risk for no benefit at this scale - 167 rows that nobody
edits at runtime.

What a reading stores is the `deck_version`, not the text. If `tarot_v1`
becomes `tarot_v2` with rewritten meanings, existing readings keep pointing at
v1 and keep saying what the user read.

Every file is validated on load: unique ids, populated asset keys, and the
canonical count the deck claims. A deck that fails validation raises at import
rather than dealing a broken card later.
"""

from __future__ import annotations

import json
import pathlib

from app.domain.divination import (
    Aett,
    Arcana,
    ContentStatus,
    DeckType,
    DivinationDeck,
    DivinationItem,
    ItemMeaning,
    Suit,
)

DATA_DIR = pathlib.Path(__file__).parent / "data"

# What each deck must contain. A mismatch is a broken deck, not a warning:
# 77 tarot cards is a bug, and dealing from it would be worse than failing.
EXPECTED_COUNTS = {
    DeckType.TAROT: 78,
    DeckType.RUNE: 24,
    DeckType.KATINA: 65,
}


class DeckDataError(RuntimeError):
    """A deck file is unusable. Raised at load time, never mid-draw."""


def _meaning(payload: dict) -> ItemMeaning:
    return ItemMeaning(
        display_name=payload["display_name"],
        keywords=tuple(payload.get("keywords", ())),
        reversed_keywords=tuple(payload.get("reversed_keywords", ())),
        upright_meaning=payload.get("upright_meaning", ""),
        reversed_meaning=payload.get("reversed_meaning", ""),
        love_meaning=payload.get("love_meaning", ""),
        career_meaning=payload.get("career_meaning", ""),
        growth_meaning=payload.get("growth_meaning", ""),
        symbolism=payload.get("symbolism", ""),
    )


def _item(payload: dict, deck_type: DeckType) -> DivinationItem:
    return DivinationItem(
        item_id=payload["item_id"],
        deck_type=deck_type,
        image_asset_key=payload["image_asset_key"],
        reversible=bool(payload["reversible"]),
        content_status=ContentStatus(payload["content_status"]),
        meanings={
            locale: _meaning(value)
            for locale, value in payload["meanings"].items()
        },
        arcana=Arcana(payload["arcana"]) if payload.get("arcana") else None,
        suit=Suit(payload["suit"]) if payload.get("suit") else None,
        number=payload.get("number"),
        rank=payload.get("rank"),
        symbol=payload.get("symbol"),
        transliteration=payload.get("transliteration"),
        aett=Aett(payload["aett"]) if payload.get("aett") else None,
        aett_position=payload.get("aett_position"),
        element=payload.get("element"),
        astrological_association=payload.get("astrological_association"),
        canonical_name=payload.get("canonical_name", ""),
    )


def _validate(deck: DivinationDeck) -> None:
    expected = EXPECTED_COUNTS[deck.deck_type]
    if len(deck.items) != expected:
        raise DeckDataError(
            f"{deck.deck_type.value} deck has {len(deck.items)} canonical "
            f"items, expected {expected}"
        )

    ids = [item.item_id for item in deck.items + deck.optional_items]
    if len(ids) != len(set(ids)):
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        raise DeckDataError(f"duplicate item ids: {duplicates}")

    for item in deck.items + deck.optional_items:
        if not item.image_asset_key:
            raise DeckDataError(f"{item.item_id} has no image asset key")
        if not item.meanings:
            raise DeckDataError(f"{item.item_id} has no meanings")
        # A reversed meaning on an item that cannot reverse is a data error
        # that would eventually be shown to a user as tradition.
        if not item.reversible:
            for locale, meaning in item.meanings.items():
                if meaning.reversed_meaning:
                    raise DeckDataError(
                        f"{item.item_id} is not reversible but carries a "
                        f"reversed meaning in {locale}"
                    )
        if not deck.reversal_supported and item.reversible:
            raise DeckDataError(
                f"{item.item_id} is reversible in a deck that does not "
                "support reversal"
            )


def load_deck(deck_type: DeckType, version: str | None = None) -> DivinationDeck:
    version = version or f"{deck_type.value}_v1"
    path = DATA_DIR / f"{version}.json"
    if not path.exists():
        raise DeckDataError(f"no deck data for {version}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload["deck_type"] != deck_type.value:
        raise DeckDataError(
            f"{path.name} declares deck type {payload['deck_type']}"
        )

    deck = DivinationDeck(
        deck_type=deck_type,
        deck_version=payload["deck_version"],
        items=tuple(_item(item, deck_type) for item in payload["items"]),
        optional_items=tuple(
            _item(item, deck_type) for item in payload.get("optional_items", [])
        ),
        locales=tuple(payload["locales"]),
        reversal_supported=bool(payload["reversal_supported"]),
        back_asset_key=payload["back_asset_key"],
    )
    _validate(deck)
    return deck


_cache: dict[tuple[DeckType, str], DivinationDeck] = {}


def get_deck(deck_type: DeckType, version: str | None = None) -> DivinationDeck:
    """Decks are immutable, so one load per version is enough."""
    key = (deck_type, version or f"{deck_type.value}_v1")
    if key not in _cache:
        _cache[key] = load_deck(deck_type, version)
    return _cache[key]


def all_decks() -> list[DivinationDeck]:
    return [get_deck(deck_type) for deck_type in DeckType]


def deck_content_note(deck_type: DeckType, version: str | None = None) -> str:
    version = version or f"{deck_type.value}_v1"
    payload = json.loads((DATA_DIR / f"{version}.json").read_text(encoding="utf-8"))
    return payload.get("content_note", "")
