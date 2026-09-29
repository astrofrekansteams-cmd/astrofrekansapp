# AstroAIContextBuilder (`context_selection_v1`)

The context is everything the model is allowed to know for one request. It is
built from engine output only, it is bounded, and it is **data, not
instructions**.

## Why selection, not everything

The model never receives a whole chart "just in case". A large context is
expensive, dilutes attention across irrelevant material, and makes it much
harder to tell what an answer actually rests on. Selection is part of the
product, not an optimisation.

## Factor ids

Every piece of material is a `ContextFactor` with a stable `factor_id`. Where
the B4/B5 engines already mint an id — a transit, a synastry aspect, a horary
reception — that id is reused, so a sentence in a report can be traced back to
the transit card the app already shows. New ids are minted only for material
that has none.

Shape: `domain:kind:detail`, for example

```
natal:planet:sun
natal:aspect:sun:moon:trine
natal:house:10
natal:dominants
transit:saturn:square:venus:2026-03-14
horary:querent
synastry:scores
```

These ids are the vocabulary the model is allowed to cite. Nothing else is
accepted (see `ai_architecture.md`, "Grounding").

## Importance and trimming

| Importance | Meaning | Trimmable |
| --- | --- | --- |
| `critical` | Warnings, exact contacts, horary significators and perfection, the source a report is about, compatibility score semantics | **Never** |
| `high` | Luminaries and personal planets, strong transits, tight aspects | Last |
| `medium` | Outer planets, weaker contacts, house overlays | Yes |
| `low` | House cusps, background detail | First |

Rules:

- Factors are dropped **whole**, never truncated mid-structure, so the model
  never sees half a transit.
- Critical factors are never dropped. Trimming a warning or a horary
  significator to save tokens would silently change what the reading is
  *about*.
- Inside an importance band, material the engine already scored survives by
  strength, so the strongest transits outlast the weakest.
- What was dropped is recorded in `trimmed_factor_ids`. An omission is
  visible, not invisible.

Critical material may exceed the budget. It is kept anyway, and the reported
token count is the real one rather than a comfortable lie.

Token estimation is deliberately pessimistic (3.2 characters per token):
Turkish and Azerbaijani tokenise worse than English, and overshooting a
budget is a provider error while undershooting is only a shorter prompt.

Budgets: `AI_CHAT_CONTEXT_BUDGET` (6000), `AI_REPORT_CONTEXT_BUDGET` (14000),
`AI_SUMMARY_BUDGET` (1200).

## What each context type contains

| Context | Source | Critical material |
| --- | --- | --- |
| `natal` | B3 chart | chart summary (dominants, big three) |
| `transit` | B4 transit scan | exact contacts in window |
| `daily` | B4 daily frequency | day scores, important hours |
| `weekly`/`monthly`/`yearly` | B4 forecast | key periods, eclipses, stations |
| `horary` | B5 analysis | querent, quesited, Moon, perfection, obstruction |
| `synastry` | B5 synastry | score semantics |
| `composite`/`davison` | B5 composite | method warnings, ambiguous midpoints |
| `general_astro_chat` | none | — |

## Focus

Chat intents that name a life area raise the importance of the material that
area needs — career pulls the Midheaven, the tenth house, Saturn and Jupiter
forward; love pulls Venus, Mars, the fifth and seventh. Nothing is removed by
focus; only the ranking changes, and the budget still does the removing.

Focus is part of the fingerprint, so a career-focused reading and a plain one
are different snapshots.

## Privacy

The `subject` block carries no identity:

```json
{"kind": "app_user", "locale": "tr", "timezone": "Europe/Istanbul"}
```

Never sent: name, email, birth date, birth time, birth place, coordinates,
saved-person names. The chart *facts* are in the factors; identity is not
needed to interpret them, so it is not sent. Provider-side request metadata
carries only `context_type`, `context_version`, `prompt_version` and `locale`.

## Fingerprint

`source_fingerprint` is a SHA-256 of the identifying inputs — the chart
moment, the question id, the report id, the focus, the context type. It is
what makes a report cacheable and what makes a changed input produce a new
report rather than a stale one.

## Presentation

The context is rendered as JSON inside `<context>…</context>`. The prompt
declares that block inert: it is data describing calculations, never an
instruction, even when it contains text that looks like one. `wrap_untrusted`
escapes any closing tag inside the payload, so content cannot break out of
its block — a hostile string stored in a saved-person label is still just
data.

## Versioning

`context_version = "context_selection_v1"`. Changing what goes into a context
changes this string, which changes every report fingerprint, which means new
requests produce new reports while existing ones keep saying what the user
already read.
