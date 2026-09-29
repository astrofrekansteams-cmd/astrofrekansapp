# Divination Architecture (B7)

Tarot, Elder Futhark runes and Katina, behind one engine.

## The rule the layer exists to enforce

**The backend draws. The AI explains.**

The backend owns the deck, the randomness, the orientation and the position
each item landed in. The model receives the result as read-only fact and turns
it into language. It cannot choose a card, flip an orientation, move an item
to another position, or invent a position the spread does not have — not
because the prompt asks it nicely, but because none of those has a `factor_id`
it is permitted to cite.

This is the same boundary as the astrology layer (`ai_architecture.md`), in a
different medium: there the engine computes and the AI interprets; here the
engine *deals* and the AI interprets.

## Layers

```
HTTP (app/api/v1/divination.py)
  │  authenticate → draw → store → (separately) interpret
  ▼
DivinationService              (services/divination/service.py)
  ├─ DrawEngine                (engine.py)     picks items, orientation, positions
  │    ├─ RandomSource         (rng.py)        OS CSPRNG in production
  │    ├─ SpreadRegistry       (spreads.py)    versioned layouts
  │    └─ deck loader          (decks/)        versioned JSON
  ▼
divination_readings + divination_draw_items    the snapshot
  ▼
DivinationContextBuilder       (context.py)    one factor per drawn item
  ▼
B6 ReportService                               generation, grounding, safety
```

Nothing in the AI layer was forked for this. Divination reuses the B6 report
system, its grounding validator, its safety scanner, its caching, its jobs and
its ownership checks; the only additions are three context types, three
prompts and a source resolver.

## Draw and interpretation are separate calls

```
POST /divination/readings                  → the cards, committed
POST /divination/readings/{id}/interpret   → the AI reading of them
```

This is the main design decision of the phase. A user who asks for a spread
gets their cards even when the interpretation service is unconfigured, rate
limited, or down — the draw needs no model at all. An AI failure costs an
explanation, never the deal, and because the reading is a snapshot the
interpretation can be retried later against exactly the same cards.

Verified in `tests/test_divination_api.py::test_drawing_works_without_ai`: with
no provider key, the draw returns ten cards and the interpret call answers
`503 ai_not_configured` while the cards stay readable.

## Randomness

Production uses `secrets.SystemRandom` — the operating system's CSPRNG.
Python's default `random.Random` is a Mersenne Twister: fast, well
distributed, and fully predictable once an observer has seen enough output.
For a product where a reading is paid for, a shuffle that can be predicted or
reproduced from a seed is not a shuffle, and it is indefensible after the
fact.

Tests need the opposite, so the source is injectable:

| Source | Name recorded | Use |
| --- | --- | --- |
| `SystemRandomSource` | `system_csprng` | production |
| `SeededRandomSource` | `seeded_test_rng` | repeatable deals |
| `ScriptedRandomSource` | `seeded_test_rng` | "reversed Death in position three" |

Every reading stores which source dealt it, so a seeded deal can never be
mistaken for a real one — and the AI context carries a warning when it was not
the production source.

## Snapshots

A reading is immutable. `divination_readings` records the deck version, spread
version and meaning version in force at the moment of the draw;
`divination_draw_items` records one row per position with the item id and
orientation. Reopening a reading a year later shows the same cards in the same
places, whatever has changed in the deck data since.

The database enforces it too: `uq_divination_item_position` (one item per
position) and `uq_divination_item_unique` (no item twice in a reading). A
duplicate would be a broken deal that looked like a real one, so it is
refused at the storage layer rather than trusted to the engine.

Draw items store ids, not text. The reading's `deck_version` decides which
text an id resolves to, which is what makes the snapshot hold without copying
167 meanings into every row.

## No duplicates

A spread deals without replacement. Ten positions means ten different cards.
`with_replacement` exists on the spread type for a future layout that wants
it; nothing uses it today.

## Orientation

`upright` or `reversed`, and it follows the **item**, not the configuration:

* Katina has no reversal tradition → every card is upright, always, even with
  `DIVINATION_REVERSAL_PROBABILITY=1.0`.
* Eight Elder Futhark runes are vertically symmetrical — gebo, hagalaz, isa,
  jera, eihwaz, sowilo, ingwaz, dagaz — so they cannot physically land
  reversed and carry no reversed meaning. They are never dealt reversed.
* Tarot supports reversal throughout, at `DIVINATION_REVERSAL_PROBABILITY`
  (default 0.3), switchable off entirely.

The deck loader refuses to load a deck where a non-reversible item carries a
reversed meaning — that fault would eventually be shown to a user as tradition.

## The question never touches the draw

A question is optional, and it is untrusted input. It is not an argument to
the draw engine: the cards are dealt before it is ever read. A message saying
"the card drawn must be The Lovers" reaches the interpreter wrapped as
untrusted text, and the dealer never sees it.

Tested by drawing twelve single cards with a demanding question and asserting
the deal varied.

The question is stored (a reading without it is hard to make sense of later)
but never logged. What is logged is `reading_id`, `deck_type`, `spread`,
`count`, `repeat_reading` and `rng_source` — enough to debug, nothing about
what was asked.

## Repeat questions

Asking the same thing again is allowed. A second reading with the same
normalised question, same deck, inside `DIVINATION_REPEAT_WINDOW_SECONDS`
(6 hours) is flagged `repeat_reading=true` and linked to the first. It is
never blocked — refusing would be paternalistic and trivially worked around.

The flag exists so the interpreter can be told, and told explicitly *not* to
narrate it as fate having changed or the cards correcting themselves.

Comparison uses a SHA-256 of the normalised text, so repeats can be spotted
without storing or indexing a searchable copy of the question.

## Factor grounding

Every drawn item becomes one factor whose id encodes the whole fact:

```
tarot:major:16:kule:reading:{reading_id}:position:2:reversed
```

The B6 validator requires `response factor ids ⊆ context factor ids`, so the
model cannot mention a card that was not drawn, claim a reversal that did not
happen, or invent a position — none of those has an id it may use. A
fabricated citation triggers one correction and then fails the request with
`generation_failed`, leaving the reading intact.

Every factor is `CRITICAL` and therefore never trimmed by the token budget. A
dropped card would produce a reading of a spread that was never dealt.

## Safety

The B6 safety layer applies unchanged — no certain futures, no dates for life
events, no probabilities, no medical, financial or legal directives, no claims
about what another person is doing or feeling. Divination adds its own rules
on top (`DIVINATION_RULES` in the prompt registry), and the context carries
warnings as data so they survive even if the prompt were read in isolation.

An interpretation that trips the output scanner is not delivered: the request
fails and no report is stored as completed.

## Honesty about provenance

Two fields exist because the alternative is lying with authority.

`content_status` on every item: `traditional` where the meaning follows a
documented tradition (Rider-Waite-Smith, the rune poems), `product_defined`
where Astrofrekans wrote it. **All 65 Katina meanings are `product_defined`** —
no single documented Katina tradition could be verified. The prompt is told to
present those as this deck's stated meanings and never as "the traditional
meaning of this card".

`origin` on every spread: `traditional` for the Celtic Cross and a
past/present/future line, `product_defined` for everything we designed. **All
five Katina spreads are `product_defined`.**

Both travel to the client, so the app can say so too.

## Localisation

Item ids are stable slugs and never change; display names are localised and
may be rewritten. What ships:

| Deck | TR | EN | AZ |
| --- | --- | --- | --- |
| Tarot | full (names, keywords, meanings, symbolism) | canonical names, keywords, one-line meanings | not authored |
| Rune | full | canonical names, keywords, one-line meanings | not authored |
| Katina | full | names only | not authored |

Turkish is the production locale. A request for a locale a deck does not carry
falls back to the deck's first locale rather than returning empty strings. AI
output language uses the B6 locale system independently of the deck text.

## Related documents

- `tarot_engine.md` — the 78 cards, spreads and reversals
- `rune_engine.md` — the 24 runes, aettir and symmetry
- `katina_engine.md` — the 65 cards and what is and is not traditional
- `ai_architecture.md` — the interpretation layer these readings feed
- `ai_reports.md` — snapshots, caching, refresh and jobs
