# OpenAI Setup and Operations

## The key lives in the backend environment. Only there.

`OPENAI_API_KEY` is read from the server environment by
`app/core/config.py` and used by `OpenAIProvider` alone.

It is never:

- shipped in the Flutter app or any client bundle,
- returned by any endpoint, including `/ai/status`,
- written to a log, a cost row, or an error message,
- committed — `.env` is git-ignored; `.env.example` carries an empty
  placeholder.

If a key is ever exposed, rotate it at the provider first, then update the
server environment. Nothing in the app needs redeploying.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `AI_PROVIDER` | `openai` | `openai` or `fake`. `fake` is a test double and is refused in production. |
| `OPENAI_API_KEY` | *(empty)* | Absent ⇒ AI features answer `ai_not_configured`. |
| `OPENAI_BASE_URL` | *(empty)* | Alternate endpoint / gateway. |
| `OPENAI_ORGANIZATION` | *(empty)* | Billing organisation. |
| `AI_MODEL_LOW_COST` | `gpt-5.6-luna` | Summaries, titles. |
| `AI_MODEL_STANDARD` | `gpt-5.6-terra` | Chat. |
| `AI_MODEL_PREMIUM` | `gpt-5.6-sol` | Reports. |
| `AI_MODEL_CHAT` / `AI_MODEL_REPORT` / `AI_MODEL_SUMMARY` | *(empty)* | Per-use-case override. |
| `AI_ALLOW_MODEL_FALLBACK` | `true` | Master switch for any downgrade. |
| `AI_ALLOW_FALLBACK_CHAT` | `true` | Chat may be served by a cheaper model. |
| `AI_ALLOW_FALLBACK_SUMMARY` | `true` | Summaries and titles may be. |
| `AI_ALLOW_FALLBACK_REPORT` | **`false`** | Reports may not, by default. See below. |
| `AI_REQUEST_TIMEOUT_SECONDS` | `90` | Buffered calls. |
| `AI_STREAM_TIMEOUT_SECONDS` | `180` | Streamed calls. |
| `AI_MAX_RETRIES` | `2` | Transient upstream failures only. |
| `AI_CHAT_CONTEXT_BUDGET` | `6000` | Context tokens for chat. |
| `AI_REPORT_CONTEXT_BUDGET` | `14000` | Context tokens for reports. |
| `AI_MAX_OUTPUT_TOKENS_CHAT` / `_REPORT` / `_SUMMARY` | `1200` / `4000` / `400` | Output caps. |
| `AI_CHAT_RATE_LIMIT` | `40/hour` | Per user. |
| `AI_REPORT_RATE_LIMIT` | `10/hour` | Per user. |
| `AI_STREAM_RATE_LIMIT` | `40/hour` | Per user. |
| `AI_REPORT_CACHE_TTL_SECONDS` | 30 days | Report pointer TTL. |
| `AI_GENERATION_LOCK_SECONDS` | `300` | Duplicate-generation lock. |
| `AI_JOB_LEASE_SECONDS` | `600` | How long a worker's claim survives. |
| `AI_JOB_MAX_ATTEMPTS` | `3` | Attempt ceiling per background job. |
| `AI_WORKER_POLL_SECONDS` | `2.0` | Worker idle poll interval. |
| `AI_WORKER_IDLE_LOG_SECONDS` | `300` | How often an idle worker logs queue depth. |
| `AI_LOG_PROMPTS` | `false` | Local debugging only. **Never enable in production.** |

Model names are configuration so a model can be swapped, overridden per use
case, or rolled back from the environment alone — no code change, no deploy.

### Why reports do not fall back

A chat answer from a cheaper model is still a useful answer, so falling back
beats failing while somebody is waiting. A premium report is different: the
user waited for it and may have paid for it, and quietly producing it with a
weaker model — then presenting it as the premium reading — is worse than
saying the service is busy. With `AI_ALLOW_FALLBACK_REPORT=false` (the
default) an unavailable premium model produces a stable error, and a
background job retries it rather than downgrading it.

Whenever a fallback *does* happen, `ai_generations` records
`model_requested`, `model_actual` and `fallback_reason`, so it is visible in
the data.

## Verifying against the real API

Everything in the test suite runs against `FakeAIProvider`, which proves our
own behaviour and nothing about OpenAI's. One script covers the rest:

```bash
python -m scripts.live_openai_smoke
```

Five small checks, all on synthetic data — one invented factor,
`test:sun:trine:jupiter`, and no name, birth date, place or coordinates
anywhere:

1. low-cost model, plain text through the Responses API
2. standard model, strict `json_schema` structured output, and whether the
   grounding held (did it cite only the id it was given?)
3. streaming, mapped into our `message_start` / `text_delta` /
   `message_complete` contract
4. one short premium call through the real report validator
5. an Azerbaijani generation, checking the language *switch* only

It costs four or five small calls, prints whether the API accepted the strict
schema, and never prints, logs or writes the key. Without `OPENAI_API_KEY` it
reports `SKIPPED` and exits 2 — not a failure, just an unverified path.

## Without a key

The application starts normally. `/health` and `/ready` stay green, migrations
run, and every non-AI endpoint works. `GET /ai/status` returns
`configured: false`, and the AI endpoints answer:

```json
{"error": {"code": "ai_not_configured",
           "message": "The interpretation service is not configured on this server."}}
```

with HTTP 503. This is deliberate: a missing key is a degraded feature, never
a broken backend. The report worker behaves the same way: it starts, logs
`ai_worker_idle_unconfigured` once, and consumes nothing, so a missing key
does not turn a queue into a pile of permanently failed reports.

`GET /ai/status` also reports *why*:

```json
{"configured": false, "provider": "openai",
 "models": {"low_cost": "…", "standard": "…", "premium": "…"},
 "fallback": {"chat": true, "summary": true, "report": false},
 "diagnostic": "OPENAI_API_KEY is not set on this server."}
```

The models a server *would* request are visible without a key, so a
configuration mistake can be spotted before one is installed. Nothing in that
response is derived from a credential.

`assert_production_ready()` refuses to start a production deployment with
`AI_PROVIDER=fake`.

## Which API is used

The **Responses API** (`client.responses.create`), with:

- `instructions` for the developer layer and `input` for the untrusted
  material,
- `text.format` = `json_schema` with `strict: true` for reports and chat
  answers,
- `store=false` — conversation state is ours, in Postgres, not the provider's,
- **no tools**: no web search, no code interpreter, no function calling,
- streaming via `response.output_text.delta`, adapted into our own event
  contract before it reaches a client.

Provider event names and error bodies never leave the backend.

## Error mapping

| Upstream | Our code | HTTP |
| --- | --- | --- |
| `APITimeoutError`, read timeout | `ai_timeout` | 504 |
| `RateLimitError`, 429 | `ai_rate_limited` | 429 |
| `AuthenticationError`, 401/403 | `ai_not_configured` | 503 |
| 400 mentioning context | `ai_context_too_large` | 422 |
| `BadRequestError`, other 400 | `ai_invalid_output` | 502 |
| anything else | `ai_provider_unavailable` | 502 |
| schema or grounding failure after one retry | `generation_failed` | 502 |
| our own per-user quota | `ai_rate_limited` + `Retry-After` | 429 |

Our quota and the provider's throttling deliberately share the `ai_rate_limited`
code: from a client's point of view the response is the same — back off and
retry — and `Retry-After` says how long. The `scope` in `details`
(`ai_chat`, `ai_stream`, `ai_report`) distinguishes them when someone needs to
know. Quotas are keyed by **user**, not by IP, so one heavy user cannot lock
out everyone behind the same carrier gateway.

The raw provider body is dropped: it can echo the request, and it is not
something a client should ever parse. A 401 also logs
`ai_authentication_failed`, which is the signal that a key expired or was
revoked.

Retries cover transient upstream conditions only, with exponential backoff and
jitter. A schema or prompt problem is retried exactly once with a correction,
never in a loop — that would burn tokens forever.

## Cost observability

Every call writes an `ai_generations` row: use case, provider, model requested
and actual, fallback reason, prompt and context versions, input/output/cached
tokens, latency, status, retry count, error code.

Deliberately absent: the prompt, the context, the answer, the key. The table
is meant to stay safe to read.

Useful queries:

```sql
-- spend shape by use case, last 7 days
SELECT use_case, model_actual, count(*), sum(total_tokens)
FROM ai_generations
WHERE created_at > now() - interval '7 days'
GROUP BY 1, 2 ORDER BY 4 DESC;

-- are we silently serving cheaper models?
SELECT fallback_reason, count(*) FROM ai_generations
WHERE model_actual <> model_requested GROUP BY 1;

-- failure shape
SELECT error_code, count(*) FROM ai_generations
WHERE status <> 'completed' GROUP BY 1 ORDER BY 2 DESC;
```

## Local development

```bash
# With a real key
echo "OPENAI_API_KEY=sk-..." >> backend/.env
docker compose up -d

# Without one - everything but AI works, AI answers ai_not_configured
docker compose up -d
```

Tests never call a real model. `FakeAIProvider` is deterministic, offline and
deliberately controllable (invalid JSON, invented factor id, timeout, rate
limit), which is what makes the grounding and safety tests meaningful. A test
run needs no key and costs nothing.

## Operational checklist

- [ ] `OPENAI_API_KEY` set in the server environment, not in any repo
- [ ] `AI_PROVIDER=openai` (never `fake`) in production
- [ ] `AI_LOG_PROMPTS=false`
- [ ] Rate limits appropriate to the plan
- [ ] Billing alerts set at the provider
- [ ] `AI_ALLOW_FALLBACK_REPORT=false` unless a downgrade is genuinely wanted
- [ ] `ai-worker` running (`docker compose up -d ai-worker`); scale as needed
- [ ] `ai_generations` monitored for `fallback_reason` and `error_code`
- [ ] `ai_report_jobs` monitored for backlog and `failed` rows
- [ ] `python -m scripts.live_openai_smoke` run once after installing a key
