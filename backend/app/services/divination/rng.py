"""Randomness for draws.

Production uses `secrets.SystemRandom`, which draws from the operating
system's CSPRNG. Python's default `random.Random` is a Mersenne Twister:
fast, well distributed, and **fully predictable** once an observer has seen
enough output. For a product where a user pays for a reading, a deal that can
be predicted - or reproduced by anyone who learns the seed - is not a deal at
all. It is also the kind of thing that is indefensible after the fact, so it
is worth the nanoseconds.

Tests need the opposite: the same cards every run. So the source is an
injectable interface, and a seeded implementation exists for tests and for
reproducing a support complaint. Every reading records which source dealt it,
so a seeded draw can never be mistaken for a real one.
"""

from __future__ import annotations

import secrets
from typing import Protocol, Sequence, TypeVar

T = TypeVar("T")

SOURCE_SYSTEM = "system_csprng"
SOURCE_SEEDED = "seeded_test_rng"


class RandomSource(Protocol):
    """What a draw needs from randomness. Deliberately tiny."""

    name: str

    def sample(self, population: Sequence[T], count: int) -> list[T]:
        """`count` distinct members, in draw order."""

    def chance(self, probability: float) -> bool:
        """True with the given probability."""


class SystemRandomSource:
    """The production source: the OS CSPRNG."""

    name = SOURCE_SYSTEM

    def __init__(self) -> None:
        self._random = secrets.SystemRandom()

    def sample(self, population: Sequence[T], count: int) -> list[T]:
        if count > len(population):
            raise ValueError(
                f"cannot draw {count} items from a deck of {len(population)}"
            )
        return self._random.sample(list(population), count)

    def chance(self, probability: float) -> bool:
        if probability <= 0:
            return False
        if probability >= 1:
            return True
        return self._random.random() < probability


class SeededRandomSource:
    """Deterministic. Tests and reproduction only.

    Named so that it is obvious in a log, a reading row and a code review that
    this deal was not random. `assert_production_ready` refuses to let it be
    the default source in production.
    """

    name = SOURCE_SEEDED

    def __init__(self, seed: int = 0) -> None:
        import random

        self._random = random.Random(seed)

    def sample(self, population: Sequence[T], count: int) -> list[T]:
        if count > len(population):
            raise ValueError(
                f"cannot draw {count} items from a deck of {len(population)}"
            )
        return self._random.sample(list(population), count)

    def chance(self, probability: float) -> bool:
        if probability <= 0:
            return False
        if probability >= 1:
            return True
        return self._random.random() < probability


class ScriptedRandomSource:
    """Draws exactly what a test asks for.

    Useful when a test needs *a specific card* - "reversed Death in position
    three" - rather than merely a repeatable deal.
    """

    name = SOURCE_SEEDED

    def __init__(
        self, ids: Sequence[str], reversals: Sequence[bool] | None = None
    ) -> None:
        self._ids = list(ids)
        self._reversals = list(reversals or [])
        self._reversal_index = 0

    def sample(self, population: Sequence[T], count: int) -> list[T]:
        by_id = {getattr(item, "item_id", item): item for item in population}
        chosen = [by_id[item_id] for item_id in self._ids[:count]]
        if len(chosen) < count:
            remaining = [item for item in population if item not in chosen]
            chosen.extend(remaining[: count - len(chosen)])
        return chosen

    def chance(self, probability: float) -> bool:
        if self._reversal_index < len(self._reversals):
            value = self._reversals[self._reversal_index]
            self._reversal_index += 1
            return value
        return False


_source: RandomSource | None = None


def get_random_source() -> RandomSource:
    global _source
    if _source is None:
        _source = SystemRandomSource()
    return _source


def set_random_source(source: RandomSource | None) -> None:
    """Swap the source. Tests only; never request handling."""
    global _source
    _source = source
