# Astro AI Architecture (B6)

## The rule the whole layer exists to enforce

**The engine computes. The AI explains.**

Every astrological fact — planetary longitudes, houses, aspects, orbs, exact
transit times, retrograde status, moon phases, dignities, receptions, horary
perfection, synastry aspects, composite and Davison midpoints, every score —
is produced by the B3–B5 engine, verified by its own regression fixtures, and
handed to the model as read-only data. The model's only job is to turn those
facts into language a person can use.

The model is never asked to calculate, never allowed to correct a calculation,
and never able to introduce an astrological factor of its own. This is not a
matter of asking nicely in a prompt: it is enforced mechanically by the
grounding validator (see below), which rejects any output citing a factor the
backend did not supply.

The model also has **no tools**. No web search, no shell, no database, no
function calling, no file access. The only material in scope for an answer is
the context the backend assembled.

## Layers

```
HTTP (app/api/v1/ai.py)
  │  authenticate → authorise the source → build context → generate
  ▼
ChatService / ReportService          (app/services/ai/{chat,reports}.py)
  │
  ├─ SourceResolver                  (sources.py)      ownership first
  ├─ AstroAIContextBuilder           (context/)        verified facts only
  ├─ ConversationService             (conversations.py) memory
  │
  ▼
GenerationService                    (generation.py)
  │  prompt (versioned) + context (data) + user text (untrusted, wrapped)
  │  → provider → schema validation → grounding check → cost row
  ▼
AIProvider (Protocol)                (provider.py)
  ├─ OpenAIProvider                  (openai_provider.py)  Responses API
  └─ FakeAIProvider                  (fake_provider.py)    tests only
```

Nothing above `provider.py` imports an SDK. That is what makes the OpenAI
implementation swappable, the test double honest, and a future Anthropic
provider a new file rather than a refactor.

## The request path, in order

1. **Authenticate.** Standard bearer token; every AI route requires a user.
2. **Authorise the source.** `SourceResolver` checks ownership of the horary
   question, compatibility report or birth profile **before** any data is
   assembled and long before anything is sent to a provider. A source id
   belonging to another user resolves to `404` — never a `403`, which would
   confirm the id exists.
3. **Route the intent.** `context/intent.py` is rule-first and deterministic
   (`intent_rules_v1`): the same question always routes the same way. An
   explicit `context_mode` from the client overrides it.
4. **Build the context.** `AstroAIContextBuilder` selects the relevant
   verified material and nothing else, fits it to a token budget, and records
   what it had to drop. See `ai_context_builder.md`.
5. **Assemble the call.** Instructions (safety rules + versioned task prompt),
   then the context as a delimited data block, then memory, then the person's
   own words last and clearly wrapped.
6. **Generate.** One controlled retry on unusable output, with the failure fed
   back as a correction. Never an endless loop.
7. **Validate.** Schema first, then grounding: every cited `factor_id` must be
   one the context supplied.
8. **Scan.** `safety.scan_output` is the backstop for claims the product must
   never make. A generation that trips it is not stored as a finished report.
9. **Record.** An `ai_generations` row holds what the call cost and how it was
   configured. It never holds the prompt, the context or the answer.

## Model routing

`router.py` maps a use case to a tier, and a tier to a model name from
configuration. Model names are never literals in service code.

| Use case | Tier | Setting |
| --- | --- | --- |
| `report` | premium | `AI_MODEL_PREMIUM`, override `AI_MODEL_REPORT` |
| `chat`, `interpretation` | standard | `AI_MODEL_STANDARD`, override `AI_MODEL_CHAT` |
| `summary`, `title`, `intent` | low cost | `AI_MODEL_LOW_COST`, override `AI_MODEL_SUMMARY` |

Fallback (premium → standard → low cost) is allowed but never silent: the
generation row records `model_requested`, `model_actual` and
`fallback_reason`, so a cheaper answer is visible in the data rather than
quietly shipped as if it were the premium one.

The policy is **per use case**, not one global switch:

| Use case | Fallback | Why |
| --- | --- | --- |
| chat, interpretation | allowed (`AI_ALLOW_FALLBACK_CHAT`) | A cheaper answer is still a useful answer while someone is waiting. |
| summary, title, intent | allowed (`AI_ALLOW_FALLBACK_SUMMARY`) | Memory does not need the good model. |
| **report** | **disabled by default** (`AI_ALLOW_FALLBACK_REPORT`) | A premium report is something the user waited for and may have paid for. Producing it with a weaker model and presenting it as the premium reading is worse than saying the service is busy. |

With report fallback off, an unavailable premium model produces a stable
error, and a background job retries it. `AI_ALLOW_MODEL_FALLBACK=false`
disables all of it.

## Structured output

Reports and chat answers both use the Responses API in strict JSON-schema
mode. The schemas are generated from Pydantic models in `schemas.py` and
tightened for strict mode: every property required,
`additionalProperties: false` everywhere, `$ref`/`$defs` inlined, optional
fields expressed as nullable.

`StructuredReport` sections carry `factor_ids` and a `general_summary` flag.
A section that makes a specific astrological claim must cite the factors it
rests on; a section that is general framing declares itself as such. Both are
checked — an uncited specific section is rejected exactly like an invented
citation.

## Grounding: the hallucination guard

```python
response factor ids ⊆ context factor ids
```

`validate_report` / `validate_chat` enforce this. A model that invents
`natal:aspect:moon:saturn:square` produces a hallucination *with a citation
attached*, which is worse than an uncited sentence, so it is rejected rather
than trimmed. The failure is fed back once as a correction naming the allowed
ids; a second failure fails the request with `generation_failed` and nothing
is written as a completed report.

On the streaming path there is no second chance, so `filter_known_factor_ids`
drops unknown ids rather than showing them to the user as sources.

## Background work

Reports can be generated inline or queued. A queued job is a row in
`ai_report_jobs`, and a separate process consumes it:

```
POST /ai/reports {"background": true}  ->  202 job
         |
         v
   ai_report_jobs (queued)
         |
   python -m app.workers.ai_report_worker
         |  SELECT ... FOR UPDATE SKIP LOCKED  (atomic claim + lease)
         v
   running -> completed (report_id) | failed | back to queued
```

Several workers can run at once; the claim is atomic and verified against real
Postgres. Full detail in `ai_worker.md`.

## Availability

A missing `OPENAI_API_KEY` is a degraded feature, never a broken backend. The
app boots, `/health` and `/ready` stay green, the rest of the API works, and
the AI endpoints answer `503 ai_not_configured`. The worker idles and leaves
the queue untouched. `GET /ai/status` tells the client whether to offer AI
features at all, which models this server would request, and — when AI is
off — why.

A startup diagnostic logs the same picture once at boot. It is a **local**
check: a boot that calls a third-party API is a boot that fails when that API
is having a bad morning, and it would fail after the load balancer has already
been told the process is coming up.

`assert_production_ready()` refuses to start a production deployment with the
fake provider selected.

## What is deliberately not here

- No astrological calculation in the AI layer, and no model-supplied fact.
- No tools, no retrieval, no browsing.
- No prompt, context, question text or answer in logs or in the cost table.
- No API key anywhere outside the backend environment.
- No horary verdict, and no compatibility score rendered as a probability.

## Related documents

- `ai_context_builder.md` — what goes into a context and why
- `ai_prompt_registry.md` — prompt versioning
- `ai_safety.md` — the safety rules and their mechanical checks
- `ai_reports.md` — snapshots, caching, refresh and jobs
- `ai_worker.md` — the queue consumer: claiming, leases, retries, shutdown
- `openai_setup.md` — configuration and operations
