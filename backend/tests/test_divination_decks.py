"""Deck integrity, spreads and the draw engine.

These tests are about the deck being *the deck*: 78 tarot cards, 24 runes in
three aettir, 65 Katina cards, every one of them mapped to an asset that
actually ships. A missing card or a card with no image is the kind of fault
that reaches a user as a blank rectangle in a paid reading, so it is checked
mechanically rather than trusted.

The draw engine is checked for the three promises it makes: no duplicates,
orientation that follows the item rather than the configuration, and a deal
that a question can never influence.
"""

from __future__ import annotations

import pathlib
from collections import Counter

import pytest

from app.core.config import settings
from app.domain.divination import Aett, Arcana, DeckType, Orientation, Suit
from app.services.divination.decks import get_deck, load_deck
from app.services.divination.decks.loader import (
    EXPECTED_COUNTS,
    DeckDataError,
)
from app.services.divination.engine import (
    DeckTooSmall,
    DrawEngine,
    UnknownSpreadError,
)
from app.services.divination.rng import (
    ScriptedRandomSource,
    SeededRandomSource,
    SystemRandomSource,
)
from app.services.divination.spreads import (
    REGISTRY,
    UnknownSpread,
    all_spread_versions,
    get_spread,
    spreads_for,
)

ASSET_ROOT = pathlib.Path(__file__).resolve().parents[2] / "assets"


@pytest.fixture(scope="module")
def tarot():
    return get_deck(DeckType.TAROT)


@pytest.fixture(scope="module")
def rune():
    return get_deck(DeckType.RUNE)


@pytest.fixture(scope="module")
def katina():
    return get_deck(DeckType.KATINA)


def engine(*args, **kwargs) -> DrawEngine:
    return DrawEngine(SeededRandomSource(*args or (11,), **kwargs))


# =============================================================== tarot deck


def test_tarot_has_seventy_eight_unique_cards(tarot):
    assert len(tarot.items) == 78
    assert len(tarot.item_ids) == 78


def test_tarot_arcana_split(tarot):
    majors = [item for item in tarot.items if item.arcana is Arcana.MAJOR]
    minors = [item for item in tarot.items if item.arcana is Arcana.MINOR]
    assert len(majors) == 22
    assert len(minors) == 56
    # The majors are numbered 0-21 with nothing missing or repeated.
    assert sorted(item.number for item in majors) == list(range(22))


def test_tarot_suits_are_fourteen_each(tarot):
    counts = Counter(
        item.suit for item in tarot.items if item.arcana is Arcana.MINOR
    )
    assert set(counts) == set(Suit)
    assert all(count == 14 for count in counts.values())

    for suit in Suit:
        numbers = sorted(
            item.number for item in tarot.items if item.suit is suit
        )
        assert numbers == list(range(1, 15)), suit


def test_tarot_court_ranks_are_complete(tarot):
    for suit in Suit:
        ranks = {
            item.rank
            for item in tarot.items
            if item.suit is suit and item.number and item.number > 10
        }
        assert ranks == {"Page", "Knight", "Queen", "King"}, suit


def test_tarot_ids_are_stable_and_descriptive(tarot):
    fool = next(item for item in tarot.items if item.number == 0)
    assert fool.item_id == "tarot:major:00:deli"
    assert fool.canonical_name == "The Fool"

    ace_of_cups = next(
        item
        for item in tarot.items
        if item.suit is Suit.CUPS and item.number == 1
    )
    assert ace_of_cups.item_id == "tarot:minor:cups:01"
    assert ace_of_cups.canonical_name == "Ace of Cups"


def test_every_tarot_card_is_reversible(tarot):
    assert all(item.reversible for item in tarot.items)


# ================================================================ rune deck


def test_rune_deck_is_twenty_four_canonical(rune):
    assert len(rune.items) == 24
    assert len(rune.item_ids) == 24


def test_blank_rune_is_optional_and_excluded_from_the_canonical_count(rune):
    """The blank rune is a 20th-century addition, not Elder Futhark."""
    assert len(rune.optional_items) == 1
    odin = rune.optional_items[0]
    assert odin.item_id not in rune.item_ids
    assert odin.content_status.value == "product_defined"
    assert len(rune.items) == EXPECTED_COUNTS[DeckType.RUNE]


def test_runes_are_eight_per_aett(rune):
    counts = Counter(item.aett for item in rune.items)
    assert set(counts) == set(Aett)
    assert all(count == 8 for count in counts.values())

    for aett in Aett:
        positions = sorted(
            item.aett_position for item in rune.items if item.aett is aett
        )
        assert positions == list(range(1, 9)), aett


def test_rune_symbols_and_transliterations_are_unique(rune):
    symbols = [item.symbol for item in rune.items]
    assert all(symbols)
    assert len(set(symbols)) == 24

    translits = [item.transliteration for item in rune.items]
    assert all(translits)
    assert len(set(translits)) == 24

    fehu = next(item for item in rune.items if item.canonical_name == "Fehu")
    assert fehu.symbol == "ᚠ"
    assert fehu.transliteration == "f"
    assert fehu.aett is Aett.FREYR
    assert fehu.aett_position == 1


def test_symmetrical_runes_cannot_be_reversed(rune):
    """A vertically symmetrical glyph has no reversed position to read."""
    symmetrical = {
        item.image_asset_key for item in rune.items if not item.reversible
    }
    assert symmetrical == {
        "gebo",
        "hagalaz",
        "isa",
        "jera",
        "eihwaz",
        "sowilo",
        "ingwaz",
        "dagaz",
    }

    for item in rune.items:
        if not item.reversible:
            for meaning in item.meanings.values():
                assert meaning.reversed_meaning == "", item.item_id


# ============================================================== katina deck


def test_katina_has_sixty_five_unique_cards(katina):
    assert len(katina.items) == 65
    assert len(katina.item_ids) == 65


def test_katina_has_no_reversals_anywhere(katina):
    """Katina has no reversal tradition, so none is invented."""
    assert katina.reversal_supported is False
    assert not any(item.reversible for item in katina.items)
    for item in katina.items:
        for meaning in item.meanings.values():
            assert meaning.reversed_meaning == "", item.item_id
            assert meaning.reversed_keywords == (), item.item_id


def test_katina_meanings_are_declared_product_defined(katina):
    """No documented tradition could be verified, and the data says so."""
    assert all(
        item.content_status.value == "product_defined" for item in katina.items
    )

    from app.services.divination.decks import deck_content_note

    note = deck_content_note(DeckType.KATINA).lower()
    assert "product-defined" in note
    assert "not traditional" in note


def test_katina_ids_are_stable(katina):
    assert all(item.item_id.startswith("katina:") for item in katina.items)
    numbers = sorted(item.number for item in katina.items)
    assert numbers == list(range(1, 66))


# ============================================================ asset mapping


@pytest.mark.parametrize(
    ("deck_type", "folder", "suffix", "expected"),
    [
        (DeckType.TAROT, "tarot/cards", ".webp", 78),
        (DeckType.RUNE, "rune/cards", ".webp", 24),
        (DeckType.KATINA, "katina/cards", ".webp", 65),
    ],
)
def test_every_card_maps_to_a_shipped_asset(
    deck_type: DeckType, folder: str, suffix: str, expected: int
):
    """A card with no image reaches the user as a blank rectangle."""
    deck = get_deck(deck_type)
    keys = {item.image_asset_key for item in deck.items}
    assert len(keys) == expected

    available = {path.stem for path in (ASSET_ROOT / folder).glob(f"*{suffix}")}
    missing = keys - available
    assert not missing, f"{deck_type.value} cards without an asset: {missing}"


def test_no_shipped_asset_is_orphaned():
    """Every production card asset belongs to a deck item."""
    for deck_type, folder in (
        (DeckType.TAROT, "tarot/cards"),
        (DeckType.RUNE, "rune/cards"),
        (DeckType.KATINA, "katina/cards"),
    ):
        deck = get_deck(deck_type)
        keys = {
            item.image_asset_key
            for item in deck.items + deck.optional_items
        }
        available = {path.stem for path in (ASSET_ROOT / folder).glob("*.webp")}
        orphans = available - keys
        assert not orphans, f"{deck_type.value} assets with no card: {orphans}"


def test_asset_keys_are_stems_not_paths():
    """The client resolves paths from its own manifest."""
    for deck_type in DeckType:
        for item in get_deck(deck_type).items:
            assert "/" not in item.image_asset_key
            assert "\\" not in item.image_asset_key
            assert not item.image_asset_key.endswith((".webp", ".png"))


def test_optional_rune_does_not_disturb_the_canonical_asset_check(rune):
    odin = rune.optional_items[0]
    assert odin.image_asset_key == "odin_runesi"
    assert (ASSET_ROOT / "rune/cards" / "odin_runesi.webp").exists()
    # The 24 stone assets are the canonical set, and match it exactly.
    stones = {path.stem for path in (ASSET_ROOT / "rune/stones").glob("*.png")}
    assert stones == {item.image_asset_key for item in rune.items}


# ========================================================= deck validation


def test_deck_validation_rejects_a_wrong_count(monkeypatch, tmp_path):
    import json

    from app.services.divination.decks import loader

    source = json.loads(
        (loader.DATA_DIR / "tarot_v1.json").read_text(encoding="utf-8")
    )
    source["items"] = source["items"][:70]
    broken = tmp_path / "tarot_broken.json"
    broken.write_text(json.dumps(source), encoding="utf-8")

    monkeypatch.setattr(loader, "DATA_DIR", tmp_path)
    with pytest.raises(DeckDataError, match="70 canonical items"):
        load_deck(DeckType.TAROT, "tarot_broken")


def test_deck_validation_rejects_a_reversed_meaning_on_a_fixed_item(
    monkeypatch, tmp_path
):
    """The failure this guards against would be shown to a user as tradition."""
    import json

    from app.services.divination.decks import loader

    source = json.loads(
        (loader.DATA_DIR / "rune_v1.json").read_text(encoding="utf-8")
    )
    isa = next(item for item in source["items"] if item["image_asset_key"] == "isa")
    isa["meanings"]["tr"]["reversed_meaning"] = "invented"
    broken = tmp_path / "rune_broken.json"
    broken.write_text(json.dumps(source), encoding="utf-8")

    monkeypatch.setattr(loader, "DATA_DIR", tmp_path)
    with pytest.raises(DeckDataError, match="not reversible"):
        load_deck(DeckType.RUNE, "rune_broken")


# ========================================================= spread registry


def test_every_spread_has_stable_versioned_positions():
    for deck_type, spreads in REGISTRY.items():
        for code, spread in spreads.items():
            assert spread.deck_type is deck_type
            assert spread.spread_code == code
            assert spread.spread_version.startswith(deck_type.value)
            assert spread.spread_version.endswith("_v1")

            indexes = [position.index for position in spread.positions]
            assert indexes == list(range(1, len(spread.positions) + 1))
            keys = [position.key for position in spread.positions]
            assert len(set(keys)) == len(keys)
            for position in spread.positions:
                assert position.interpretation_role
                assert position.titles.get("tr")


def test_spread_versions_are_unique():
    versions = all_spread_versions()
    assert len(set(versions.values())) == len(versions)


def test_required_spreads_exist():
    for code in (
        "single_card",
        "three_card",
        "past_present_future",
        "situation_action_outcome",
        "love_three_card",
        "career_three_card",
        "celtic_cross",
    ):
        get_spread(DeckType.TAROT, code)

    for code in (
        "single_rune",
        "three_rune",
        "past_present_future",
        "situation_challenge_advice",
        "five_rune_cross",
    ):
        get_spread(DeckType.RUNE, code)

    for code in (
        "single_card",
        "three_card",
        "relationship",
        "seven_card",
        "nine_card",
    ):
        get_spread(DeckType.KATINA, code)


def test_celtic_cross_is_ten_typed_positions():
    spread = get_spread(DeckType.TAROT, "celtic_cross")
    assert len(spread.positions) == 10
    assert [position.key for position in spread.positions] == [
        "significator",
        "crossing",
        "foundation",
        "recent_past",
        "conscious",
        "near_future",
        "self",
        "environment",
        "hopes_fears",
        "outcome",
    ]


def test_katina_spreads_do_not_claim_to_be_traditional():
    """No documented Katina layout could be verified, so none claims to be."""
    for spread in spreads_for(DeckType.KATINA):
        assert spread.origin.value == "product_defined", spread.spread_code
        assert spread.allow_reversed is False


def test_a_spread_belongs_to_exactly_one_deck():
    with pytest.raises(UnknownSpread):
        get_spread(DeckType.RUNE, "celtic_cross")
    with pytest.raises(UnknownSpread):
        get_spread(DeckType.TAROT, "five_rune_cross")
    with pytest.raises(UnknownSpread):
        get_spread(DeckType.KATINA, "celtic_cross")


# ============================================================ draw engine


def test_a_spread_never_deals_the_same_item_twice():
    for _ in range(25):
        draw = DrawEngine(SystemRandomSource()).draw(
            DeckType.TAROT, "celtic_cross"
        )
        assert len(draw.items) == 10
        assert len(set(draw.item_ids)) == 10


def test_every_spread_deals_its_own_position_count():
    dealer = engine()
    for deck_type in DeckType:
        for spread in spreads_for(deck_type):
            draw = dealer.draw(deck_type, spread.spread_code)
            assert len(draw.items) == spread.card_count
            assert len(set(draw.item_ids)) == spread.card_count
            assert [item.position.index for item in draw.items] == list(
                range(1, spread.card_count + 1)
            )
            assert [item.draw_order for item in draw.items] == list(
                range(1, spread.card_count + 1)
            )


def test_the_same_seed_deals_the_same_cards():
    first = DrawEngine(SeededRandomSource(99)).draw(DeckType.TAROT, "three_card")
    second = DrawEngine(SeededRandomSource(99)).draw(DeckType.TAROT, "three_card")

    assert first.item_ids == second.item_ids
    assert [item.orientation for item in first.items] == [
        item.orientation for item in second.items
    ]


def test_a_scripted_source_deals_exactly_what_a_test_asks_for():
    dealer = DrawEngine(
        ScriptedRandomSource(
            ["tarot:major:13:olum", "tarot:major:00:deli"],
            reversals=[True, False],
        )
    )
    draw = dealer.draw(DeckType.TAROT, "three_card")

    assert draw.items[0].item.item_id == "tarot:major:13:olum"
    assert draw.items[0].orientation is Orientation.REVERSED
    assert draw.items[1].item.item_id == "tarot:major:00:deli"
    assert draw.items[1].orientation is Orientation.UPRIGHT


def test_production_draws_use_the_system_csprng():
    """A predictable shuffle is indefensible in a product people pay for."""
    draw = DrawEngine(SystemRandomSource()).draw(DeckType.RUNE, "three_rune")
    assert draw.rng_source == "system_csprng"
    # And a seeded deal is always labelled as one.
    seeded = engine().draw(DeckType.RUNE, "three_rune")
    assert seeded.rng_source == "seeded_test_rng"


def test_reversals_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(settings, "divination_reversal_enabled", False)
    draw = DrawEngine(SeededRandomSource(3)).draw(DeckType.TAROT, "celtic_cross")
    assert draw.reversed_count == 0


def test_reversal_probability_is_honoured(monkeypatch):
    monkeypatch.setattr(settings, "divination_reversal_enabled", True)

    monkeypatch.setattr(settings, "divination_reversal_probability", 1.0)
    always = DrawEngine(SeededRandomSource(5)).draw(DeckType.TAROT, "celtic_cross")
    assert always.reversed_count == 10

    monkeypatch.setattr(settings, "divination_reversal_probability", 0.0)
    never = DrawEngine(SeededRandomSource(5)).draw(DeckType.TAROT, "celtic_cross")
    assert never.reversed_count == 0


def test_katina_is_never_dealt_reversed(monkeypatch):
    """Even with reversal forced on, a deck without the tradition stays upright."""
    monkeypatch.setattr(settings, "divination_reversal_enabled", True)
    monkeypatch.setattr(settings, "divination_reversal_probability", 1.0)

    draw = DrawEngine(SeededRandomSource(1)).draw(DeckType.KATINA, "nine_card")
    assert draw.reversed_count == 0
    assert all(item.orientation is Orientation.UPRIGHT for item in draw.items)


def test_symmetrical_runes_are_never_dealt_reversed(monkeypatch):
    monkeypatch.setattr(settings, "divination_reversal_enabled", True)
    monkeypatch.setattr(settings, "divination_reversal_probability", 1.0)

    for seed in range(30):
        draw = DrawEngine(SeededRandomSource(seed)).draw(
            DeckType.RUNE, "five_rune_cross"
        )
        for drawn in draw.items:
            if not drawn.item.reversible:
                assert drawn.orientation is Orientation.UPRIGHT, drawn.item.item_id


def test_the_blank_rune_is_only_dealt_when_asked_for():
    dealer = DrawEngine(SeededRandomSource(2))
    for _ in range(20):
        draw = dealer.draw(DeckType.RUNE, "five_rune_cross")
        assert all("optional" not in item.item.item_id for item in draw.items)

    pool = DrawEngine(
        ScriptedRandomSource(["rune:optional:odin"])
    ).draw(DeckType.RUNE, "single_rune", include_optional_items=True)
    assert pool.items[0].item.item_id == "rune:optional:odin"


def test_an_unknown_spread_is_a_stable_error():
    with pytest.raises(UnknownSpreadError) as error:
        engine().draw(DeckType.TAROT, "not_a_spread")
    assert error.value.code == "unknown_spread"
    assert error.value.status_code == 404


def test_a_spread_from_another_deck_is_refused():
    with pytest.raises(UnknownSpreadError):
        engine().draw(DeckType.RUNE, "celtic_cross")


def test_a_spread_cannot_ask_for_more_than_the_deck_holds(monkeypatch):
    from app.services.divination import spreads as registry
    from app.domain.divination import DivinationSpread, SpreadOrigin

    huge = DivinationSpread(
        deck_type=DeckType.RUNE,
        spread_code="impossible",
        spread_version="rune_impossible_v1",
        origin=SpreadOrigin.PRODUCT_DEFINED,
        names={"tr": "x", "en": "x"},
        positions=tuple(
            registry.position(index, f"p{index}", "x", "x", "role")
            for index in range(1, 40)
        ),
    )
    monkeypatch.setitem(REGISTRY[DeckType.RUNE], "impossible", huge)

    with pytest.raises(DeckTooSmall):
        engine().draw(DeckType.RUNE, "impossible")


def test_factor_ids_describe_position_item_and_orientation():
    draw = DrawEngine(
        ScriptedRandomSource(["tarot:major:16:kule"], reversals=[True])
    ).draw(DeckType.TAROT, "single_card")

    drawn = draw.items[0]
    assert drawn.factor_id == "draw:position:1:tarot:major:16:kule:reversed"
    assert drawn.is_reversed
