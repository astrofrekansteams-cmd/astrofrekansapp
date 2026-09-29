# Elder Futhark Rune Engine

24 runes in three aettir. Deck version `rune_v1`.

## The deck

| Aett | Runes | Ids |
| --- | --- | --- |
| Freyr's aett | Fehu, Uruz, Thurisaz, Ansuz, Raidho, Kenaz, Gebo, Wunjo | `rune:freyr:01:fehu` … `:08:wunjo` |
| Heimdall's aett | Hagalaz, Nauthiz, Isa, Jera, Eihwaz, Perthro, Algiz, Sowilo | `rune:heimdall:01:hagalaz` … `:08:sowilo` |
| Tyr's aett | Tiwaz, Berkano, Ehwaz, Mannaz, Laguz, Ingwaz, Dagaz, Othala | `rune:tyr:01:tiwaz` … `:08:othala` |

Eight per aett, in the traditional order. The id carries the aett and the
position within it, so the row order is readable from the id alone.

Each rune carries its glyph (`ᚠ`), its transliteration (`f`), keywords, an
upright meaning, a symbolism note, and a reversed meaning where one is
possible. Symbols and transliterations are unique across the deck, which the
tests assert rather than assume.

## The blank rune is not part of the deck

`odin_runesi` exists as an **optional item**, outside the canonical 24:

```json
"optional_items": [{"item_id": "rune:optional:odin", "content_status": "product_defined"}]
```

The blank rune is a 20th-century addition, not part of the historical Elder
Futhark. It is excluded from the canonical count, never dealt unless
`include_optional_items` is explicitly requested, and its own meaning text
says what it is. Including it silently would misrepresent the tradition the
rest of the deck is drawn from.

`DIVINATION_INCLUDE_BLANK_RUNE` exists as a server-side default; the request
flag is what actually decides per draw. The canonical-count test
(`test_blank_rune_is_optional_and_excluded_from_the_canonical_count`) fails if
it ever enters the 24.

## Reversals follow shape, not convenience

Eight runes are vertically symmetrical. Turned around, the glyph is the same
glyph — there is no reversed position to read:

**gebo (ᚷ), hagalaz (ᚺ), isa (ᛁ), jera (ᛃ), eihwaz (ᛇ), sowilo (ᛋ),
ingwaz (ᛜ), dagaz (ᛞ)**

These are marked `reversible: false` and carry an empty `reversed_meaning`.
The engine never asks about their orientation, so they cannot be dealt
reversed even with `DIVINATION_REVERSAL_PROBABILITY=1.0` — asserted over 30
seeds in `test_symmetrical_runes_are_never_dealt_reversed`.

The deck loader refuses to load a file where one of them carries a reversed
meaning. Filling that field to make the data uniform would be inventing
tradition and then showing it to a user as inherited.

The AI context lists the non-reversible runes in a drawn spread by name, and
the prompt says: never invent a reversed meaning for one, and never describe
it as "not reversed" as though that were a finding.

The remaining 16 runes reverse normally, at the configured probability.

## Spreads

| Code | Positions | Origin |
| --- | ---: | --- |
| `single_rune` | 1 | traditional |
| `three_rune` | 3 | traditional |
| `past_present_future` | 3 | traditional |
| `situation_challenge_advice` | 3 | traditional |
| `five_rune_cross` | 5 | traditional |

`five_rune_cross`: overview, challenge, past influence, advice, direction.

Each position carries an `interpretation_role`, and the `direction` role says
plainly that it is a tendency rather than a fixed outcome.

Version strings are `rune_{code}_v1`.

## Assets

Two sets ship, and they are not interchangeable:

* `assets/rune/cards/` — 25 files: the canonical 24 plus `odin_runesi`
* `assets/rune/stones/` — 24 files: exactly the canonical set

`image_asset_key` is a stem (`algiz`, `fehu`); the client picks card or stone
presentation from its own manifest and composes the path. The tests assert the
stone set matches the canonical 24 exactly — that equality is a useful
independent check that the blank rune has not leaked into the deck.

Backs: `rune_back` (cards), `runetas_back` (stones).

No image was generated or modified in this phase.

## Known limitations

- Turkish is the production locale. English carries canonical names, keywords
  and a one-line meaning; Azerbaijani is not authored.
- Domain meanings (love, career, growth) are not authored for runes. The
  interpreter works from the core meaning and the position.
- No rune-relationship modelling: no bindrunes, no aett-majority heuristics,
  no numerical correspondences. The interpreter is told which aettir appear
  and asked to read the cast as a whole, but the engine computes nothing about
  their interaction and nothing claims it does.
- Rune poem sources are not cited per rune. The meanings follow the common
  published reading of the Old English, Norwegian and Icelandic poems, and are
  marked `traditional` on that basis; they are not a scholarly edition.
