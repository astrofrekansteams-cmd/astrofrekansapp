"""Divination domain types: decks, spreads, draws and readings.

The boundary this module encodes is the same one as the astrology layer, in a
different medium: **the backend draws, the AI explains.**

A draw is a physical event. The backend owns the deck, the randomness, the
orientation and the position each item landed in; the model receives the
result as read-only fact and turns it into language. Nothing here lets a model
choose a card, flip an orientation, or invent a position - and nothing lets a
user's question do so either.

A reading is a **snapshot**. Once the cards are down they are down: reopening
a reading a year later shows the same cards in the same places, whatever has
changed in the deck data, the prompts or the model since.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class DeckType(StrEnum):
    TAROT = "tarot"
    RUNE = "rune"
    KATINA = "katina"


class Orientation(StrEnum):
    """How an item landed.

    Not every deck has a meaningful reversal. A Katina card has no reversed
    tradition, and several runes are vertically symmetrical, so they cannot be
    reversed at all. Those decks and items are `UPRIGHT` always - inventing a
    reversal to fill a field would be inventing tradition.
    """

    UPRIGHT = "upright"
    REVERSED = "reversed"


class Arcana(StrEnum):
    MAJOR = "major"
    MINOR = "minor"


class Suit(StrEnum):
    WANDS = "wands"
    CUPS = "cups"
    SWORDS = "swords"
    PENTACLES = "pentacles"


class Aett(StrEnum):
    """The three groups of eight in the Elder Futhark."""

    FREYR = "freyr"      # Freyr's aett: fehu .. wunjo
    HEIMDALL = "heimdall"  # Hagal's aett: hagalaz .. sowilo
    TYR = "tyr"          # Tyr's aett: tiwaz .. othala


class ContentStatus(StrEnum):
    """How much the written meaning can be trusted as tradition.

    `TRADITIONAL` - the meaning follows a documented, widely published
    tradition (Rider-Waite-Smith for tarot, the rune poems for Elder Futhark).

    `PRODUCT_DEFINED` - Astrofrekans wrote it. Used where no single documented
    tradition exists, which is much of the Katina deck. Saying "traditionally
    this card means..." about something we made up would be a lie told with
    authority, so the data says which is which and the prompt is told.
    """

    TRADITIONAL = "traditional"
    PRODUCT_DEFINED = "product_defined"


class SpreadOrigin(StrEnum):
    """Where a spread comes from. Same honesty rule as ContentStatus."""

    TRADITIONAL = "traditional"
    PRODUCT_DEFINED = "product_defined"


class ReadingStatus(StrEnum):
    DRAWN = "drawn"
    INTERPRETED = "interpreted"


# ------------------------------------------------------------------ items


@dataclass(slots=True, frozen=True)
class ItemMeaning:
    """One locale's worth of text for one item."""

    display_name: str
    keywords: tuple[str, ...] = ()
    reversed_keywords: tuple[str, ...] = ()
    upright_meaning: str = ""
    reversed_meaning: str = ""
    love_meaning: str = ""
    career_meaning: str = ""
    growth_meaning: str = ""
    symbolism: str = ""


@dataclass(slots=True, frozen=True)
class DivinationItem:
    """One card or rune.

    `item_id` is stable for the life of the product. Display names are
    localised and may be rewritten; the id is what a stored reading points at,
    so changing one would silently rewrite somebody's past reading.
    """

    item_id: str
    deck_type: DeckType
    image_asset_key: str
    reversible: bool
    content_status: ContentStatus
    meanings: dict[str, ItemMeaning] = field(default_factory=dict)

    # Tarot
    arcana: Arcana | None = None
    suit: Suit | None = None
    number: int | None = None
    rank: str | None = None

    # Rune
    symbol: str | None = None
    transliteration: str | None = None
    aett: Aett | None = None
    aett_position: int | None = None

    # Shared, optional
    element: str | None = None
    astrological_association: str | None = None
    canonical_name: str = ""

    def meaning(self, locale: str, *, fallback: str = "tr") -> ItemMeaning:
        return self.meanings.get(locale) or self.meanings[fallback]

    @property
    def is_major(self) -> bool:
        return self.arcana is Arcana.MAJOR


@dataclass(slots=True, frozen=True)
class DivinationDeck:
    deck_type: DeckType
    deck_version: str
    items: tuple[DivinationItem, ...]
    locales: tuple[str, ...]
    reversal_supported: bool
    back_asset_key: str
    # Items outside the canonical set - the blank Odin rune, for instance -
    # which are only dealt when explicitly enabled.
    optional_items: tuple[DivinationItem, ...] = ()

    def __len__(self) -> int:
        return len(self.items)

    def item(self, item_id: str) -> DivinationItem:
        for candidate in self.items + self.optional_items:
            if candidate.item_id == item_id:
                return candidate
        raise KeyError(item_id)

    @property
    def item_ids(self) -> set[str]:
        return {item.item_id for item in self.items}


# ----------------------------------------------------------------- spreads


@dataclass(slots=True, frozen=True)
class SpreadPosition:
    """One slot in a spread.

    `key` is stable and machine-readable; `title` is what a person reads.
    `interpretation_role` tells the model what the slot *is for*, which is the
    difference between "the third card is Death" and "what you are moving
    towards is Death".
    """

    index: int
    key: str
    titles: dict[str, str]
    interpretation_role: str
    descriptions: dict[str, str] = field(default_factory=dict)

    def title(self, locale: str, *, fallback: str = "tr") -> str:
        return self.titles.get(locale) or self.titles[fallback]

    def description(self, locale: str, *, fallback: str = "tr") -> str:
        return self.descriptions.get(locale) or self.descriptions.get(fallback, "")


@dataclass(slots=True, frozen=True)
class DivinationSpread:
    deck_type: DeckType
    spread_code: str
    spread_version: str
    origin: SpreadOrigin
    positions: tuple[SpreadPosition, ...]
    names: dict[str, str]
    allow_reversed: bool = True
    with_replacement: bool = False
    # Which meaning layer fits this spread: general, love, relationship,
    # career, money or spiritual. Display only; the draw ignores it.
    theme: str = "general"

    def __len__(self) -> int:
        return len(self.positions)

    def name(self, locale: str, *, fallback: str = "tr") -> str:
        return self.names.get(locale) or self.names[fallback]

    @property
    def card_count(self) -> int:
        return len(self.positions)


# ------------------------------------------------------------------ draws


@dataclass(slots=True, frozen=True)
class DrawnItem:
    """One item, where it landed, and how.

    This is the unit the AI is allowed to talk about, and the unit a
    `factor_id` points at.
    """

    draw_order: int
    position: SpreadPosition
    item: DivinationItem
    orientation: Orientation

    @property
    def factor_id(self) -> str:
        return (
            f"draw:position:{self.position.index}:"
            f"{self.item.item_id}:{self.orientation.value}"
        )

    @property
    def is_reversed(self) -> bool:
        return self.orientation is Orientation.REVERSED


@dataclass(slots=True, frozen=True)
class DivinationDraw:
    """The result of one shuffle and deal. Immutable by construction."""

    deck_type: DeckType
    deck_version: str
    spread: DivinationSpread
    items: tuple[DrawnItem, ...]
    drawn_at: datetime
    rng_source: str

    def __len__(self) -> int:
        return len(self.items)

    @property
    def item_ids(self) -> list[str]:
        return [drawn.item.item_id for drawn in self.items]

    @property
    def reversed_count(self) -> int:
        return sum(1 for drawn in self.items if drawn.is_reversed)
