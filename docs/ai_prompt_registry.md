# Prompt Registry

Prompts are versioned artefacts, not strings scattered through services.

## Why versioning matters here

Every generation records the `prompt_version` it used. Changing a prompt
therefore produces *new* output going forward and never silently rewrites a
report a user has already read — the version is part of the report
fingerprint, so an edited prompt yields a new snapshot rather than a changed
one.

## The registry

`app/services/ai/prompts.py`. One `Prompt` per use case: `name`, `version`,
`task`.

| Name | Version | Used for |
| --- | --- | --- |
| `astro_chat` | `astro_chat_v1` | conversational answers |
| `natal_report` | `natal_report_v1` | natal reading |
| `transit_interpretation` | `transit_interpretation_v1` | transit report |
| `daily_interpretation` | `daily_interpretation_v1` | daily horoscope |
| `weekly_interpretation` | `weekly_interpretation_v1` | weekly horoscope |
| `monthly_forecast` | `monthly_forecast_v1` | monthly forecast |
| `annual_forecast` | `annual_forecast_v1` | annual forecast |
| `horary_interpretation` | `horary_interpretation_v1` | horary reading |
| `synastry_report` | `synastry_report_v1` | synastry reading |
| `composite_report` | `composite_report_v1` | composite reading |
| `davison_report` | `davison_report_v1` | Davison reading |
| `conversation_summary` | `conversation_summary_v1` | rolling chat memory |
| `conversation_title` | `conversation_title_v1` | thread title |

`GET /ai/status` returns the whole map, so a client can tell which prompt
produced a stored report.

## Structure of a call's instruction layer

`Prompt.instructions(locale)` composes, in order:

1. Role line
2. `INSTRUCTION_HIERARCHY` — what may and may not change the rules
3. `ENGINE_BOUNDARY` — what the model may not calculate
4. `FACTOR_GROUNDING` — cite `factor_id`s, never invent one
5. `UNCERTAINTY` — how to speak about the future
6. `DOMAIN_LIMITS` — health, money, law
7. `RELATIONSHIP_LIMITS` — other people
8. `COMPATIBILITY_SEMANTICS` — a score is an index
9. `STYLE`
10. `language_rule(...)` — the output language
11. The prompt's own `TASK` block

The shared blocks live in `safety.py` and are identical across every prompt,
so a safety rule is written once and cannot drift between use cases.

## Language

The output language is a **parameter**, not a separate prompt. Three
translated copies of every prompt would drift apart within a month; one prompt
with a language rule cannot. Supported: Turkish, Azerbaijani, English.

The locale reaches both layers: the language rule in the instructions and the
`locale` field in provider metadata.

## Task prompts worth reading closely

**`horary_interpretation_v1`** states the judgement rule explicitly: describe
the traditional indications as supportive, challenging, mixed or unclear, and
stop there. No verdict, no probability, no date for an outcome. It also
instructs the model not to mention techniques listed under `not_implemented`
as present or absent — the engine did not examine them, so nothing may be
concluded from them.

**`synastry_report_v1`** requires the overall score to be explained as an
astrological factor index and forbids converting it into a chance, a
percentage of success, or advice about whether to stay together.

**`conversation_summary_v1`** records what the person asked about and how they
like to be spoken to, and explicitly must **not** record astrological facts,
placements or dates. Those always come fresh from the engine; a remembered
"my Venus is in Aries" must never become a fact.

**`composite_report_v1`** requires the model to say once, plainly, that a
composite is a chart of midpoints and not a moment that existed in the sky.

## Changing a prompt

1. Add a new `Prompt` with `..._v2`, or bump the version on the existing one.
2. Leave stored reports alone. They keep their `prompt_version` and their
   text.
3. Expect new fingerprints: the next request for the same source produces a
   new report.
4. Update the prompt-version assertions in `tests/test_ai_core.py`.

Never edit a prompt's text without changing its version. That is the one
change that would make a stored report's recorded provenance a lie.
