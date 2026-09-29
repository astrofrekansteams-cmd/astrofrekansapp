# B6 — Astro AI performance

Measured 2026-09-23 on the development machine (Windows 11, Python 3.13,
SQLite for the endpoint figures, Skyfield + DE421 for the ephemeris).

**What is measured and what is not.** Provider latency is the provider's: it
varies with model, load and prompt length, and there is nothing in this
codebase to optimise about it. Everything *around* the call is ours —
authorising a source, running the engine, selecting and budgeting the context,
rendering it, validating and grounding the result, writing the cost row — and
that is what these numbers cover. `FakeAIProvider` stands in for the model, so
the figures are stable and the run costs nothing.

## Per-step cost

`python -m scripts.benchmark_ai`

| Step | median | p95 |
| --- | ---: | ---: |
| Natal chart (B3 engine) | 86.22 ms | 142.30 ms |
| Natal context: select + budget | 1.73 ms | 2.49 ms |
| Render context to the `<context>` block | 0.19 ms | 0.27 ms |
| Intent routing (`intent_rules_v1`) | 0.02 ms | 0.04 ms |
| Instruction assembly (safety + task prompt) | <0.01 ms | 0.01 ms |
| Schema validation + factor grounding | 0.01 ms | 0.02 ms |
| **Whole AI layer per report, excluding the model** | **0.73 ms** | — |

The AI layer costs well under a millisecond. Everything expensive in an AI
request is either the astrology engine (~86 ms for a natal chart, cached
afterwards) or the provider itself.

Intent routing deserves its own line: 0.02 ms because it is rules, not a
model. Routing every chat turn through a cheap model instead would have added
a network round trip and a bill to every question, for a decision that is
deterministic anyway.

## Context size

Natal, Turkish, report budget:

| Measure | Value |
| --- | ---: |
| Factors kept | 39 |
| Factors trimmed | 0 |
| Estimated context tokens | 2 725 |
| Rendered characters | 10 953 |
| Rendered tokens (est.) | 3 423 |
| Instruction layer tokens (est.) | 1 664 |
| **Input tokens per natal report (est.)** | **~5 100** |

Token estimation is deliberately pessimistic (3.2 characters per token):
Turkish and Azerbaijani tokenise worse than English, and overshooting a budget
is a provider error while undershooting is only a shorter prompt.

## Budget behaviour under pressure

| Budget | Factors kept | Trimmed | Tokens used |
| ---: | ---: | ---: | ---: |
| 1 000 | 13 | 26 | 961 |
| 3 000 | 39 | 0 | 2 725 |
| 6 000 | 39 | 0 | 2 725 |
| 14 000 | 39 | 0 | 2 725 |

At 1 000 tokens the builder drops 26 low-importance factors — house cusps and
background detail — and keeps the chart summary, the luminaries and the
strongest aspects. Critical factors are never trimmed, and what was dropped is
reported in `trimmed_factor_ids` rather than silently omitted.

The configured report budget (14 000) is comfortable for a natal chart and is
sized for the larger contexts: an annual forecast carries key periods,
eclipses, retrogrades and house activations.

## Endpoint latency

Collected from the API test run (23 report generations, 12 chat turns, 2
streams). SQLite and an in-memory cache, so database time is optimistic;
provider time is the fake provider's ~1 ms.

| Endpoint | n | median | max |
| --- | ---: | ---: | ---: |
| `GET /ai/status` | 3 | 111.5 ms | 166.9 ms |
| `POST /ai/conversations` | 2 | 112.5 ms | 155.6 ms |
| `GET /ai/conversations` | 5 | 10.8 ms | 28.2 ms |
| `GET /ai/conversations/{id}/messages` | 4 | 26.2 ms | 31.3 ms |
| `POST /ai/chat` | 12 | 179.4 ms | 3 068.9 ms |
| `POST /ai/chat/stream` | 2 | 177.2 ms | 205.8 ms |
| `POST /ai/reports` | 23 | 92.1 ms | 2 231.5 ms |
| `GET /ai/reports/{id}` | 3 | 22.5 ms | 28.1 ms |
| `POST /ai/report-jobs` | 1 | 293.8 ms | 293.8 ms |

The medians are the interesting number; the maxima are the first request for a
given forecast, where the B4 engine computes a month of transits before any
interpretation can begin. Once the forecast is cached, the same request falls
back to the median. A `cached: true` report returns in ~20 ms and makes **no
provider call at all**.

The first `/ai/status` call pays for module import; afterwards it is trivial.

## Cost per generation (estimates)

With the pessimistic estimator and the measured context sizes:

| Use case | Input tokens | Output cap | Tier |
| --- | ---: | ---: | --- |
| Chat turn | ~3 000–4 000 | 1 200 | standard |
| Natal report | ~5 100 | 4 000 | premium |
| Annual forecast | up to ~15 700 | 4 000 | premium |
| Conversation summary | ~1 700 | 400 | low cost |

Three things keep this bill down and are worth naming:

1. **Report caching.** A repeated request with the same source, engine,
   context and prompt versions returns the stored snapshot and calls nothing.
2. **Context selection.** The model never receives a whole chart "just in
   case"; selection is a product decision that happens to also be the largest
   cost lever.
3. **Tiering.** Summaries and titles never touch the premium model, and a
   fallback to a cheaper model is recorded in `ai_generations` rather than
   shipped silently as if it were the premium answer.

## Observability

Every call writes an `ai_generations` row: use case, provider, model requested
and actual, fallback reason, prompt and context versions, input/output/cached
tokens, latency, status, retry count, error code. Deliberately absent: the
prompt, the context, the answer, the key.

```sql
SELECT use_case, model_actual, count(*), sum(total_tokens)
FROM ai_generations
WHERE created_at > now() - interval '7 days'
GROUP BY 1, 2 ORDER BY 4 DESC;
```

## Honest limitations

- These figures exclude real provider latency, which will dominate a user's
  experience of a report. Expect seconds, not milliseconds, and treat the
  background job path as the answer for long reports.
- Endpoint timings use SQLite and an in-memory cache. Postgres and Redis will
  add network time to every query; the shape will hold, the absolute numbers
  will not.
- Token counts are estimates from a character heuristic, not a tokeniser. The
  provider's reported `input_tokens` in `ai_generations` is the number to
  trust once real traffic exists; the estimator only has to be conservative
  enough not to overrun a budget.
- One machine, one chart, no concurrency. Nothing here says how the layer
  behaves under parallel load.
