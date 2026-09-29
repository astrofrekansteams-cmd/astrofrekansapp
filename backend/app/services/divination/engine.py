"""The draw engine.

This is the whole of the "backend draws, AI explains" boundary in one file.
It picks the items, decides orientation, and assigns positions. Nothing that
happens later - not the question text, not the model, not a retry - can change
what came out.

Three rules it enforces without exception:

* **No duplicates.** A spread deals without replacement by default, so a
  ten-card Celtic Cross is ten different cards. Anything else is a shuffling
  bug pretending to be fate.
* **Orientation follows the item, not convenience.** A Katina card has no
  reversed tradition and a symmetrical rune cannot physically land reversed,
  so neither is ever dealt reversed - regardless of configuration.
* **The question never touches the draw.** It is not an input here. A message
  reading "make the card The Lovers" reaches the interpreter as untrusted
  text and the dealer never sees it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import settings
from app.core.exceptions import AppError
from app.domain.divination import (
    DeckType,
    DivinationDeck,
    DivinationDraw,
    DivinationSpread,
    DrawnItem,
    Orientation,
)
from app.services.divination.decks import get_deck
from app.services.divination.rng import RandomSource, get_random_source
from app.services.divination.spreads import UnknownSpread, get_spread


class DivinationError(AppError):
    status_code = 422
    code = "divination_error"
    message = "This reading could not be produced."


class UnknownSpreadError(DivinationError):
    status_code = 404
    code = "unknown_spread"
    message = "That spread does not exist for this deck."


class SpreadDeckMismatch(DivinationError):
    code = "spread_deck_mismatch"
    message = "That spread belongs to a different deck."


class DeckTooSmall(DivinationError):
    code = "deck_too_small"
    message = "This spread needs more cards than the deck contains."


def reversal_probability(deck: DivinationDeck) -> float:
    """How often a reversible item lands reversed.

    Configuration, not a constant, so it can be tuned or switched off without
    a deploy - and so a test can pin it to 0 or 1 and get a deterministic
    orientation.
    """
    if not deck.reversal_supported:
        return 0.0
    if not settings.divination_reversal_enabled:
        return 0.0
    return max(0.0, min(1.0, settings.divination_reversal_probability))


class DrawEngine:
    def __init__(self, random_source: RandomSource | None = None) -> None:
        self._random = random_source or get_random_source()

    def resolve_spread(
        self, deck_type: DeckType, spread_code: str
    ) -> DivinationSpread:
        try:
            spread = get_spread(deck_type, spread_code)
        except UnknownSpread as exc:
            raise UnknownSpreadError(
                f"'{spread_code}' is not a spread for the "
                f"{deck_type.value} deck.",
                details={"deck_type": deck_type.value, "spread": spread_code},
            ) from exc

        if spread.deck_type is not deck_type:  # pragma: no cover - registry guard
            raise SpreadDeckMismatch()
        return spread

    def draw(
        self,
        deck_type: DeckType,
        spread_code: str,
        *,
        include_optional_items: bool = False,
        deck_version: str | None = None,
    ) -> DivinationDraw:
        deck = get_deck(deck_type, deck_version)
        spread = self.resolve_spread(deck_type, spread_code)

        pool = list(deck.items)
        if include_optional_items:
            # The blank Odin rune joins the pool only when asked for. It is
            # not part of the canonical 24 and must never change that count.
            pool.extend(deck.optional_items)

        if spread.card_count > len(pool):
            raise DeckTooSmall(
                f"{spread.spread_code} needs {spread.card_count} items but "
                f"the deck has {len(pool)}.",
                details={
                    "required": spread.card_count,
                    "available": len(pool),
                },
            )

        if spread.with_replacement:  # pragma: no cover - no spread uses it yet
            chosen = [
                self._random.sample(pool, 1)[0] for _ in range(spread.card_count)
            ]
        else:
            chosen = self._random.sample(pool, spread.card_count)

        probability = reversal_probability(deck) if spread.allow_reversed else 0.0

        drawn: list[DrawnItem] = []
        for order, (item, position) in enumerate(
            zip(chosen, spread.positions, strict=True), start=1
        ):
            # An item that cannot be reversed is never asked about, so a
            # configured probability cannot produce an impossible orientation.
            reversed_ = item.reversible and self._random.chance(probability)
            drawn.append(
                DrawnItem(
                    draw_order=order,
                    position=position,
                    item=item,
                    orientation=(
                        Orientation.REVERSED if reversed_ else Orientation.UPRIGHT
                    ),
                )
            )

        return DivinationDraw(
            deck_type=deck_type,
            deck_version=deck.deck_version,
            spread=spread,
            items=tuple(drawn),
            drawn_at=datetime.now(UTC),
            rng_source=self._random.name,
        )

    # --------------------------------------------------------- user pick

    def shuffle(
        self,
        deck_type: DeckType,
        spread_code: str,
        *,
        include_optional_items: bool = False,
        deck_version: str | None = None,
    ) -> "ShuffledDeck":
        """Shuffle the whole deck face down, once, for a user-pick session.

        Every face-down slot's orientation is fixed here too, so revealing the
        same picks again can never flip a card: the reveal only looks up what
        this shuffle already decided.
        """
        deck = get_deck(deck_type, deck_version)
        spread = self.resolve_spread(deck_type, spread_code)
        pool = list(deck.items)
        if include_optional_items:
            pool.extend(deck.optional_items)
        if spread.card_count > len(pool):
            raise DeckTooSmall(
                details={"required": spread.card_count, "available": len(pool)},
            )
        order = self._random.sample(pool, len(pool))
        probability = reversal_probability(deck) if spread.allow_reversed else 0.0
        orientations = tuple(
            Orientation.REVERSED
            if item.reversible and self._random.chance(probability)
            else Orientation.UPRIGHT
            for item in order
        )
        return ShuffledDeck(
            deck_type=deck_type,
            deck_version=deck.deck_version,
            spread=spread,
            item_ids=tuple(item.item_id for item in order),
            orientations=orientations,
            rng_source=self._random.name,
        )

    def resolve_picks(
        self, shuffled: "ShuffledDeck", positions: list[int]
    ) -> DivinationDraw:
        """Turn the user's picks into a draw, in the order they were picked.

        The i-th pick fills the spread's i-th position. Nothing is sorted and
        nothing is re-randomised.
        """
        deck = get_deck(shuffled.deck_type, shuffled.deck_version)
        drawn = [
            DrawnItem(
                draw_order=order,
                position=position,
                item=deck.item(shuffled.item_ids[slot]),
                orientation=shuffled.orientations[slot],
            )
            for order, (slot, position) in enumerate(
                zip(positions, shuffled.spread.positions, strict=True), start=1
            )
        ]
        return DivinationDraw(
            deck_type=shuffled.deck_type,
            deck_version=shuffled.deck_version,
            spread=shuffled.spread,
            items=tuple(drawn),
            drawn_at=datetime.now(UTC),
            rng_source=shuffled.rng_source,
        )


@dataclass(frozen=True, slots=True)
class ShuffledDeck:
    """A face-down deck: slot i holds item_ids[i] with orientations[i]."""

    deck_type: DeckType
    deck_version: str
    spread: DivinationSpread
    item_ids: tuple[str, ...]
    orientations: tuple[Orientation, ...]
    rng_source: str

    @property
    def size(self) -> int:
        return len(self.item_ids)

    def to_hidden_state(self) -> dict:
        return {
            "order": list(self.item_ids),
            "orientations": [o.value for o in self.orientations],
        }

    @classmethod
    def from_hidden_state(
        cls,
        *,
        deck_type: DeckType,
        deck_version: str,
        spread: DivinationSpread,
        state: dict,
        rng_source: str,
    ) -> "ShuffledDeck":
        return cls(
            deck_type=deck_type,
            deck_version=deck_version,
            spread=spread,
            item_ids=tuple(state["order"]),
            orientations=tuple(Orientation(o) for o in state["orientations"]),
            rng_source=rng_source,
        )


def get_draw_engine(random_source: RandomSource | None = None) -> DrawEngine:
    return DrawEngine(random_source)
