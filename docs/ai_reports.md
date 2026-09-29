# AI Reports: snapshots, caching and jobs

## A report is a snapshot

A report is frozen at the moment it was produced. It keeps its text, its
`prompt_version`, its `context_version`, its `engine_version` and the model
that wrote it. That is what makes a report safe to pay for, to show to an
expert, and to come back to a year later.

## The fingerprint

`report_fingerprint` is a SHA-256 over:

```
report_type
source_type, source_id
source_fingerprint      (the context's own hash of its inputs)
context_version         (context_selection_v1)
engine_version          (B3-B5 engine)
prompt_version
locale
extra                   (e.g. transit range)
```

Change any of them and the next request produces a **new** report. The old one
is untouched.

The fingerprint is deliberately **not unique** in the database: it identifies
the inputs, not a row. An explicit `refresh=true` writes another report from
the same inputs rather than overwriting the reading the user already has.
Lookups take the newest completed row for a fingerprint.

## Caching

1. `ai:report:{fingerprint}` in Redis points at a report id (TTL 30 days).
2. On a miss, the newest completed row with that fingerprint is used.
3. Only on a miss in both does a generation run.

A cache hit costs nothing: no provider call, no tokens. The response carries
`cached: true` so the client can say so.

`refresh=true` skips the lookup and generates again. The previous report stays
readable at its own id.

## The duplicate lock

Before an expensive generation, `ai:lock:{user}:{fingerprint}` is taken. A
second request for the same report while the first is running returns the
existing report if there is one, or `generation_in_progress` if there is not.
The lock is best effort: if the cache is unavailable the request proceeds,
because a duplicate report is cheaper than a broken feature.

## Lifecycle of a row

```
pending → generating → completed
                     ↘ failed (error_code)
```

A failed generation leaves an inspectable `failed` row with an error code —
`generation_failed`, `ai_timeout`, `safety_violation` — rather than
disappearing. Failed rows are never returned as readings and never satisfy a
cache lookup.

## Sources and authorisation

| Report type | Source | Requires `source_id` |
| --- | --- | --- |
| `natal` | primary birth profile | no |
| `transit` | birth profile + B4 scan | no |
| `daily`, `weekly`, `monthly`, `yearly` | birth profile + forecast | no |
| `horary` | horary question | **yes** |
| `synastry`, `composite`, `davison` | compatibility report | **yes** |

Ownership is checked first, and the report type must match the source kind —
asking for a `composite` report over a `synastry` source is a `404`, not a
silent reinterpretation. A source id belonging to another user is a `404`, so
id guessing cannot even confirm that the row exists. No provider call happens
before this check passes.

Without a birth profile, a natal or forecast report answers `422
birth_profile_missing` rather than inventing a chart.

## Background jobs

Long premium reports can be queued:

```
POST /ai/reports        {"report_type": "yearly", "background": true}  → 202 job
POST /ai/report-jobs    {"report_type": "yearly"}                      → 202 job
GET  /ai/report-jobs/{id}                                              → status
POST /ai/report-jobs/{id}/cancel                                       → cancelled
```

A 202 returns the **job**, not an error envelope: a queued job is a success
with a different shape.

### Payment

`natal`, `synastry` and `yearly` are sold as store credits (unless
`PAID_REPORTS_INCLUDED_IN_PREMIUM` and a verified premium entitlement say
otherwise). Every report route - sync, background, `/ai/report-jobs`, the
divination interpretation - goes through `ReportService.request`, which asks
`ReportAccessPolicy` first. For a credit-paid report it reserves the credit and
writes the job (`payment_basis="credit"`, `consumer_ref`, `entitlement_id`) in
the request's transaction; `run_job` checks the reservation is still held,
generates, and consumes the credit in the commit that completes the report. A
synchronous paid report is a job claimed inline with a lease, so if the request
dies a worker finishes it. Jobs queued before enforcement (`payment_basis`
NULL) are judged by the policy when they run. Contract and error codes:
`api_contracts.md` → "Paid reports".

Job state lives in Postgres (`ai_report_jobs`), so a crash or a disconnect
leaves an inspectable row rather than a silently lost request. `enqueue`
resolves and authorises the source *before* recording the job, so an
unauthorised job never reaches the queue. `run_job` records the attempt count
and the error code, and is safe to call from a worker or inline.

```
queued ──claim──► running ──success──► completed (report_id)
   ▲                 │
   │                 ├─transient failure, attempts left──► queued
   │                 ├─permanent failure──────────────────► failed
   │                 └─lease expired───► queued | failed (worker_lost)
   │
   └── cancelled (never runs)
```

Rules that matter:

* **A cancelled job never runs.** `run_job` skips anything already
  `completed`, `cancelled` or `failed`.
* **Re-running a completed job produces no second report.** It returns
  unchanged, and the report cache would return the same snapshot anyway.
* **Transient failures retry, permanent ones do not.** A timeout or a rate
  limit goes back to `queued` while attempts remain. A schema, grounding or
  safety failure goes straight to `failed` — the inputs have not changed, so
  retrying only spends money.
* **A dead worker's job is recovered, not lost.** Claims carry a lease; once
  it expires the job is requeued, or failed with `worker_lost` at the attempt
  ceiling.

The consumer is a separate process (`python -m app.workers.ai_report_worker`).
Claiming uses `SELECT ... FOR UPDATE SKIP LOCKED`, so several workers can run
without ever generating the same report twice. See `ai_worker.md`.

## Report shape

```json
{
  "id": "…", "report_type": "natal", "status": "completed",
  "title": "…", "summary": "…",
  "sections": [
    {"key": "overview", "title": "…", "body": "…",
     "factor_ids": ["natal:planet:sun"], "general_summary": false}
  ],
  "warnings": ["…"],
  "interpretation_scope": "Astrological interpretation for reflection, not a prediction.",
  "safety_note": null,
  "prompt_version": "natal_report_v1",
  "context_version": "context_selection_v1",
  "engine_version": "…",
  "provider": "openai", "model": "…",
  "cached": false
}
```

`factor_ids` are the app's own ids, so a section can be linked back to the
transit or aspect card that produced it. `warnings` come from the context —
birth time unknown, void-of-course Moon, ambiguous midpoints, horary
`not_implemented`, compatibility score semantics — and are carried through to
the client rather than left inside the prompt.

## Deleting

Reports are soft-deleted (`deleted_at`). A soft-deleted report is invisible to
reads and to cache lookups.
