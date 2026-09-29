# Tarot Engine

78 cards, Rider-Waite-Smith structure and meanings. Deck version `tarot_v1`.

## The deck

| | Count | Ids |
| --- | ---: | --- |
| Major Arcana | 22 | `tarot:major:00:deli` … `tarot:major:21:dunya` |
| Wands | 14 | `tarot:minor:wands:01` … `:14` |
| Cups | 14 | `tarot:minor:cups:01` … `:14` |
| Swords | 14 | `tarot:minor:swords:01` … `:14` |
| Pentacles | 14 | `tarot:minor:pentacles:01` … `:14` |
| **Total** | **78** | |

Minor numbering runs 1–14: Ace through Ten, then Page (11), Knight (12),
Queen (13), King (14). Keeping the court cards in the same number space as the
pips means "the fifth card of Cups" and "the Queen of Cups" are the same kind
of lookup.

Ids are stable for the life of the product. A stored reading points at an id,
so changing one would silently rewrite somebody's past reading. Display names
are localised and may be rewritten freely.

## Structure per card

```json
{
  "item_id": "tarot:major:16:kule",
  "image_asset_key": "kule",
  "canonical_name": "The Tower",
  "arcana": "major", "suit": null, "number": 16, "rank": null,
  "element": "fire", "astrological_association": "Mars",
  "reversible": true,
  "content_status": "traditional",
  "meanings": {
    "tr": {
      "display_name": "Kule",
      "keywords": ["ani değişim", "yıkılış", "gerçeğin açığa çıkması", "sarsıntı"],
      "reversed_keywords": ["ertelenen çöküş", "kaçınma", "yavaş yıkım"],
      "upright_meaning": "…", "reversed_meaning": "…",
      "love_meaning": "…", "career_meaning": "…", "growth_meaning": "…",
      "symbolism": "…"
    },
    "en": { "…": "canonical name, keywords, one-line meanings" }
  }
}
```

Every major carries an element and an astrological association; minors carry
their suit's element. The 22 majors have full Turkish text across all six
meaning fields. The 56 minors carry Turkish keywords, upright and reversed
meanings and a symbolism line composed from suit and rank; the domain fields
(love, career, growth) are empty for minors and the interpreter works from the
core meaning and the position instead.

## Spreads

| Code | Positions | Origin |
| --- | ---: | --- |
| `single_card` | 1 | traditional |
| `three_card` | 3 | traditional |
| `past_present_future` | 3 | traditional |
| `situation_action_outcome` | 3 | traditional |
| `love_three_card` | 3 | **product-defined** |
| `career_three_card` | 3 | **product-defined** |
| `celtic_cross` | 10 | traditional |

Version strings are `tarot_{code}_v1`. A stored reading keeps its
`spread_version`, so redesigning a layout into `_v2` leaves existing readings
describing the layout they were actually dealt in.

### Celtic Cross

Ten typed positions, in the standard order:

1. `significator` — the heart of the matter as it stands
2. `crossing` — what complicates it, for better or worse
3. `foundation` — the root of the situation
4. `recent_past` — what is passing out of it
5. `conscious` — what the querent is aware of aiming at
6. `near_future` — what is coming in, as a tendency
7. `self` — how the querent is positioned
8. `environment` — the people and circumstances around it
9. `hopes_fears` — what they hope for and fear, often the same thing
10. `outcome` — where the whole reading tends

Each position carries an `interpretation_role` that travels into the AI
context. That is the difference between "the third card is Death" and "the
root of this situation is Death" — the relationship between card and slot is
the reading, and it is data rather than something the model has to infer.

The `outcome` and `near_future` roles say explicitly that they are tendencies,
not settled events. A spread that names a position "outcome" invites a
prediction; the role text is where that invitation is declined.

### The love spread's second position

`love_three_card` position 2 is "the other person", and its role text says:
*read symbolically. This position never states what that person is doing or
feeling.* A chart or a card cannot know that, and this is the position where a
reading is most likely to claim otherwise.

## Reversals

All 78 cards are reversible. Orientation is decided by the engine at
`DIVINATION_REVERSAL_PROBABILITY` (default 0.3), and the model is never asked
to pick one.

* `DIVINATION_REVERSAL_ENABLED=false` → every card upright.
* `DIVINATION_REVERSAL_PROBABILITY=1.0` → every reversible card reversed
  (useful in tests; a 10-card Celtic Cross comes back with `reversed_count`
  of exactly 10).

Reversed keywords are separate from upright ones, and the hydrated reading
returns whichever set matches the orientation the card actually landed in.

## Assets

`image_asset_key` is a **stem**, not a path: `kule`, `kupa_asi`,
`tilsim_kralicesi`. The client composes `assets/tarot/cards/{key}.webp` from
its own manifest. The backend returning a filesystem path would tie the API to
one client's bundling.

78 cards ↔ 78 shipped assets, checked both ways by
`test_every_card_maps_to_a_shipped_asset` and `test_no_shipped_asset_is_orphaned`.
No image was generated or modified in this phase; the deck was built against
the audited production assets.

Card back: `tarot_back`.

## Turkish naming

The asset slugs are Turkish, and the deck was mapped to them through an
explicit canonical table rather than by parsing filenames. Worth knowing when
reading the data:

| Turkish | English | | Turkish | English |
| --- | --- | --- | --- | --- |
| `degnek` | Wands | | `prens` | Page |
| `kupa` | Cups | | `sovalye` | Knight |
| `kilic` | Swords | | `kralice` | Queen |
| `tilsim` | Pentacles | | `kral` | King |
| `deli` | The Fool | | `denge` | Temperance |
| `ermis` | The Hermit | | `kader_carki` | Wheel of Fortune |

## Known limitations

- Minor arcana domain meanings (love, career, growth) are empty. The
  interpreter uses the core meaning plus the position, which reads well but is
  less specific than the majors.
- English carries canonical names, keywords and a one-line meaning per card,
  not the full text. Turkish is the production locale.
- Azerbaijani is not authored.
- Elemental dignities, card-combination rules and suit-majority heuristics are
  not modelled. The interpreter sees the cards and their positions and is
  asked to read the spread as a whole, but the engine computes no such
  relationships — and nothing claims it does.
