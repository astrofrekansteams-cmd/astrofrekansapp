"""Benchmark the draw path.

Provider latency is the provider's. What is ours is everything before it:
loading the deck, shuffling with the OS CSPRNG, assigning positions, resolving
meanings and building the AI context. This measures that, with no model
involved at all.

Run:  python -m scripts.benchmark_divination
"""

from __future__ import annotations

import statistics
import time

from app.domain.divination import DeckType
from app.services.divination.decks import get_deck
from app.services.divination.engine import DrawEngine
from app.services.divination.rng import SystemRandomSource

CASES = [
    (DeckType.TAROT, "single_card"),
    (DeckType.TAROT, "three_card"),
    (DeckType.TAROT, "celtic_cross"),
    (DeckType.RUNE, "five_rune_cross"),
    (DeckType.KATINA, "nine_card"),
]


def timed(func, repeat: int = 200) -> tuple[float, float]:
    samples = []
    for _ in range(repeat):
        started = time.perf_counter()
        func()
        samples.append((time.perf_counter() - started) * 1000)
    return (
        round(statistics.median(samples), 4),
        round(sorted(samples)[int(len(samples) * 0.95) - 1], 4),
    )


def main() -> None:
    # Warm the deck cache so the numbers measure dealing, not file IO.
    for deck_type in DeckType:
        get_deck(deck_type)

    engine = DrawEngine(SystemRandomSource())

    print(f"{'draw':34} {'cards':>6} {'median ms':>10} {'p95 ms':>9}")
    print("-" * 64)
    for deck_type, spread_code in CASES:
        median, p95 = timed(lambda d=deck_type, s=spread_code: engine.draw(d, s))
        count = len(engine.draw(deck_type, spread_code).items)
        print(f"{deck_type.value + ' ' + spread_code:34} {count:>6} {median:>10} {p95:>9}")

    print()
    cold_start, _ = timed(lambda: get_deck(DeckType.TAROT), repeat=1000)
    print(f"cached deck lookup:            {cold_start} ms")

    from app.services.divination.decks.loader import load_deck

    fresh, _ = timed(lambda: load_deck(DeckType.TAROT), repeat=20)
    print(f"deck load from disk + validate: {fresh} ms (once per process)")

    print()
    print("Deck sizes:")
    for deck_type in DeckType:
        deck = get_deck(deck_type)
        print(
            f"  {deck_type.value:8} {len(deck.items):3} items "
            f"(+{len(deck.optional_items)} optional)  {deck.deck_version}"
        )


if __name__ == "__main__":
    main()
