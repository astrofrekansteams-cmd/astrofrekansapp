"""Divination API contracts.

`image_asset_key` is a **stem**, not a path: the client composes
`assets/tarot/cards/{key}.webp` from its own manifest. The backend has no
business knowing how the app bundles its files, and returning a filesystem
path would tie the API to one client's layout.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.domain.ai import Locale
from app.domain.divination import DeckType, Orientation, SpreadOrigin
from app.schemas.common import APIModel


class SpreadPositionResponse(APIModel):
    index: int
    key: str
    title: str
    role: str = Field(
        description=(
            "What this slot is for. The difference between 'the third card is "
            "Death' and 'what you are moving towards is Death'."
        )
    )
    description: str | None = None


class SpreadResponse(APIModel):
    deck_type: DeckType
    spread_code: str
    spread_version: str
    name: str
    origin: SpreadOrigin = Field(
        description=(
            "`traditional` for a documented layout, `product_defined` for one "
            "Astrofrekans designed. Never guessed."
        )
    )
    card_count: int
    allow_reversed: bool
    theme: str = "general"
    positions: list[SpreadPositionResponse]


class DeckResponse(APIModel):
    deck_type: DeckType
    deck_version: str
    item_count: int
    optional_item_count: int
    reversal_supported: bool
    locales: list[str]
    back_asset_key: str
    content_note: str
    spread_codes: list[str]


class DeckItemResponse(APIModel):
    item_id: str
    display_name: str
    canonical_name: str
    image_asset_key: str
    keywords: list[str] = Field(default_factory=list)
    reversible: bool
    content_status: str

    arcana: str | None = None
    suit: str | None = None
    number: int | None = None
    rank: str | None = None
    symbol: str | None = None
    transliteration: str | None = None
    aett: str | None = None
    element: str | None = None


class ReadingCreateRequest(APIModel):
    deck_type: DeckType
    spread_code: str
    locale: Locale | None = None
    question: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Optional, and untrusted. It is never allowed to influence the "
            "draw: the cards are dealt before it is read."
        ),
    )
    include_optional_items: bool = Field(
        default=False,
        description=(
            "Rune deck only: include the blank 'Odin' rune, a 20th-century "
            "addition that is not part of the canonical 24."
        ),
    )


class DrawSessionCreateRequest(APIModel):
    consumer_ref: str = Field(
        min_length=8,
        max_length=80,
        pattern=r"^[A-Za-z0-9._:-]+$",
        description=(
            "Stable client reference for this shuffle. Retrying with the same "
            "ref returns the same session; the same ref with a different "
            "request is a 409."
        ),
    )
    deck_type: DeckType
    spread_code: str
    locale: Locale | None = None
    question: str | None = Field(default=None, max_length=500)
    include_optional_items: bool = False
    pay_with_coins: bool = Field(
        default=False,
        description=(
            "Pay with AstroCoins for what the plan does not cover (a spread "
            "outside the plan, a draw beyond today's allowance)."
        ),
    )


class DrawAllowanceResponse(APIModel):
    tier: str
    enforced: bool
    daily_limit: int
    used_today: int
    remaining: int
    extra_draw_price: int
    advanced_spread_price: int


class DrawSessionResponse(APIModel):
    """What the client may know about a face-down deck: its size and the
    spread - never which item or orientation sits in any slot."""

    session_id: uuid.UUID
    deck_type: DeckType
    deck_size: int
    spread_code: str
    spread_name: str
    required_selections: int
    positions: list[SpreadPositionResponse]
    expires_at: datetime
    status: str
    reading_id: uuid.UUID | None = None
    coins_spent: int = 0


class DrawSessionRevealRequest(APIModel):
    positions: list[int] = Field(
        min_length=1,
        max_length=20,
        description=(
            "Face-down slots in the order the user picked them; the i-th pick "
            "fills the spread's i-th position. Not sorted by the server."
        ),
    )


class DrawnItemResponse(APIModel):
    draw_order: int
    position_index: int
    position_key: str
    position_title: str
    position_role: str
    position_description: str = ""

    item_id: str
    display_name: str
    canonical_name: str
    orientation: Orientation
    image_asset_key: str

    keywords: list[str] = Field(default_factory=list)
    meaning: str = ""
    love_meaning: str = ""
    career_meaning: str = ""
    growth_meaning: str = ""
    symbolism: str = ""
    contextual_meaning: str = Field(
        default="",
        description="The meaning layer matching the spread theme (love, career, growth), else the general one.",
    )
    shadow_meaning: str = Field(
        default="",
        description="The reversed/shadow side of the item, shown alongside an upright draw.",
    )
    content_status: str = Field(
        description=(
            "`traditional` where the meaning follows a documented tradition, "
            "`product_defined` where Astrofrekans wrote it."
        )
    )


class SynthesisResponse(APIModel):
    headline: str
    lines: list[str]
    flow: list[str]
    counts: dict[str, int]
    version: str


class ReadingResponse(APIModel):
    id: uuid.UUID
    deck_type: DeckType
    deck_version: str
    spread_code: str
    spread_version: str
    spread_name: str
    locale: Locale

    question: str | None = None
    repeat_reading: bool = Field(
        default=False,
        description=(
            "The same question, same deck, asked again recently. Recorded, "
            "never blocked."
        ),
    )
    repeat_of_id: uuid.UUID | None = None

    rng_source: str
    drawn_at: datetime
    status: str
    items: list[DrawnItemResponse]
    spread_theme: str = "general"
    synthesis: SynthesisResponse | None = None

    has_interpretation: bool = False
    created_at: datetime


class ReadingSummary(APIModel):
    id: uuid.UUID
    deck_type: DeckType
    spread_code: str
    spread_name: str
    locale: Locale
    question: str | None = None
    item_count: int
    drawn_at: datetime
    has_interpretation: bool = False
    created_at: datetime


class InterpretRequest(APIModel):
    locale: Locale | None = None
    refresh: bool = Field(
        default=False,
        description=(
            "Generate a new interpretation. The draw never changes - only the "
            "reading of it."
        ),
    )
    background: bool = False
    consumer_ref: str | None = Field(
        default=None,
        min_length=8,
        max_length=100,
        pattern=r"^[A-Za-z0-9._:-]+$",
        description=(
            "Required when the plan does not include AI deep readings: the "
            "AstroCoin charge for this press, reused on every retry of it."
        ),
    )
