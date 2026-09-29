# Katina Engine

65 cards. Deck version `katina_v1`.

## Read this section first

**Every meaning in this deck is product-defined. None of it is traditional,
and the data says so.**

Tarot has the Rider-Waite-Smith corpus. The Elder Futhark has the rune poems.
Katina has neither, at least not one that could be verified while building
this: there is no single documented methodology that a meaning could be
checked against. Several cards have transparent Turkish names whose sense
follows from the word — `kalp` (heart), `mektup` (letter), `yol` (road),
`mezar` (grave). Others are proper names whose Katina-specific meaning could
not be confirmed from any source: `adhamdeva`, `eprahhat`, `parsadra`,
`selcuksassa`, `tattaret`, `assyranta`, `gamhat`, `hesse`, `bedes`, `dastar`
and more.

So:

* Every item carries `content_status: "product_defined"`.
* Every spread carries `origin: "product_defined"`.
* The deck's `content_note` says it, and that note is returned by
  `GET /divination/decks` so the client can say it too.
* The AI context carries it as a warning, and `katina_interpretation_v1`
  instructs the model to present these as *this deck's* meanings and never as
  "the traditional meaning of this card".

Writing "traditionally, this card means…" about text we composed would be a
lie told with authority, and attributing an invented methodology to a culture
is worse than admitting we wrote it.

If a documented source is obtained later, the honest path is a `katina_v2`
with `content_status: "traditional"` on the cards it actually covers.
Existing readings keep pointing at `katina_v1` and keep saying what their
owners read.

## The deck

65 cards, ids `katina:01:adhamdeva` … `katina:65:zumrut`, numbered in
alphabetical order of the slug. The card **list** is not invented: it comes
from the audited production assets, which is the authoritative inventory of
this deck in the product.

Per card: Turkish display name, keywords, a core meaning, a love meaning, a
relationship meaning and a warning note. The English locale carries the name
only.

Field mapping in the data file, worth knowing when reading it: `love_meaning`
holds the love reading, `growth_meaning` holds the relationship reading and
`symbolism` holds the warning note — reusing the shared `ItemMeaning` shape
rather than forking a Katina-specific type.

## No reversals

Katina has no reversal tradition, so:

* `reversal_supported: false` on the deck
* `reversible: false` on every card
* every `reversed_meaning` and `reversed_keywords` empty
* every spread has `allow_reversed: false`

The engine never asks about orientation for this deck, so every card is
upright even with `DIVINATION_REVERSAL_PROBABILITY=1.0` — asserted in
`test_katina_is_never_dealt_reversed`. The deck loader refuses to load a
Katina file where any card claims to be reversible.

The AI context says so as a warning, and the prompt tells the model not to
mention orientation as though it were a choice the deal made.

## Spreads — all product-defined

| Code | Positions |
| --- | ---: |
| `single_card` | 1 |
| `three_card` | 3 (past, present, direction) |
| `relationship` | 5 (you, other person, bond, obstacle, direction) |
| `seven_card` | 7 (situation, past, present, hidden, support, obstacle, direction) |
| `nine_card` | 9 (self, home, feeling, past, present, hidden, obstacle, support, direction) |

None of these claims to be a traditional Katina layout, because no traditional
Katina layout could be verified. They are Astrofrekans layouts using the
Katina deck, and the API says `product_defined` on every one.

The `relationship` spread's second position, "the other person", carries the
same role text as its tarot counterpart: *read symbolically. This position
never states what that person is doing or feeling.*

Every `direction` position's role says it is a tendency, not a settled
outcome.

Version strings are `katina_{code}_v1`.

## Assets

65 cards ↔ 65 shipped assets in `assets/katina/cards/`, checked both ways.
`image_asset_key` is a stem (`zumrut`, `kiz_cocugu`); the client composes
`assets/katina/cards/{key}.webp` from its own manifest.

Card back: `katina_back`.

No image was generated or modified in this phase.

## Localisation

Turkish only. `locales: ["tr"]` on the deck, and the English locale carries
names without meanings. A request for `en` or `az` falls back to Turkish text
rather than returning empty strings.

This is the honest state: the meanings were written in Turkish for a Turkish
product, and machine-translating them into English would produce text that
reads like a translation of something authoritative when it is neither.

## Known limitations

- **All 65 meanings are product-defined**, as above. This is the deck's
  defining limitation and it is surfaced everywhere rather than hidden.
- **All 5 spreads are product-defined.**
- Turkish only.
- No card-combination rules, no positional heuristics, no distance or
  adjacency modelling. The interpreter sees the cards and their positions.
- Career meanings are not authored; the love and relationship meanings are.
- The card ordering (1–65) is alphabetical by slug and carries no meaning. If
  a traditional ordering exists, it is not reflected here.
