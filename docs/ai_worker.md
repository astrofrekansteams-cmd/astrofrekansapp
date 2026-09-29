# AI Report Worker

```
python -m app.workers.ai_report_worker
```

One process, one loop: recover jobs whose worker died, claim the oldest queued
job, run it, repeat.

## Why a separate process

A premium report can take tens of seconds. Work attached to a web process —
FastAPI's `BackgroundTasks` — dies with a deploy, a restart or a crashed
request, and competes with request handling for the same event loop. Neither
is acceptable for something a user waited for and may have paid for. A worker
is scaled, restarted and watched on its own.

The API never generates a background report itself. It writes a job row and
returns `202` with it; the worker does the rest.

## Where the queue lives, and why it is Postgres

The queue is the `ai_report_jobs` table. Not Redis, because the job **is** the
row: its state, attempt count, error code, owner and resulting report are all
things a support engineer needs to read a week later. Putting the work item in
one store and its record in another means the two can disagree, and the
version a user asks about is always the row.

Redis still holds the short-lived duplicate-generation lock, which is a
different problem — stopping one user firing the same expensive generation
twice within minutes.

## Claiming: `SELECT ... FOR UPDATE SKIP LOCKED`

```sql
SELECT * FROM ai_report_jobs
 WHERE status = 'queued'
 ORDER BY created_at
 LIMIT 1
   FOR UPDATE SKIP LOCKED;
```

The standard way to hand one row to exactly one consumer: no lock table, and
workers do not queue behind each other. Two workers polling at the same
instant each get a different job, or one gets a job and the other gets
nothing. The select, the transition to `running` and the lease write all
happen in one transaction, so a job is either fully claimed or untouched.

Ordering is oldest-first. A queue that reorders itself is a queue that starves
somebody.

**Verified, not assumed.** `python -m scripts.worker_concurrency_check` runs
this against real Postgres with 8 concurrent workers and 12 jobs and asserts
every job was claimed exactly once. Last run: 12/12, no duplicates, spread
over 8 workers.

SQLite (the test database) has no `SKIP LOCKED` and no concurrent writers, so
the query runs there without the locking clause. That is safe — SQLite
serialises writers anyway — but it means the unit tests prove the *state
machine*, not the locking. The concurrency script is what proves the locking.

## Leases: surviving a dead worker

A claim writes `worker_id` and `lease_expires_at` (`AI_JOB_LEASE_SECONDS`,
default 600). If a worker dies mid-generation, nothing can mark its job
failed — the process that would have done so is gone — so the row would sit in
`running` forever.

Every loop begins with `recover_stale_jobs`:

- `running`, lease expired, attempts left → back to `queued`
- `running`, lease expired, no attempts left → `failed`, `error_code = "worker_lost"`

A job that has repeatedly killed its worker stops being retried. A job with a
*live* lease is never touched, so recovery cannot steal work from a healthy
worker.

The lease must outlast the slowest generation. 600 seconds is deliberately
generous against a ~60-second premium report: the cost of a lease that is too
short (two workers generating the same report) is much worse than one that is
too long (a dead worker's job waits a few extra minutes).

## Retries

`ReportService._fail_job` decides:

| Failure | Behaviour |
| --- | --- |
| `ai_timeout`, `ai_rate_limited`, `ai_provider_unavailable` | back to `queued` while `attempt < max_attempts` |
| `generation_failed` (schema, grounding, safety) | `failed` immediately |
| `ai_invalid_output` after the in-call retry | `failed` |
| worker died | `queued` via lease expiry, or `failed` at the attempt ceiling |

A timeout is the provider having a bad minute and is worth another attempt.
Output that failed schema validation, factor grounding or the safety scan will
fail the same way next time — the inputs have not changed — so retrying it
only spends money.

`AI_JOB_MAX_ATTEMPTS` (default 3) is recorded per job at enqueue time, so
changing the setting does not rewrite the ceiling for work already queued.

## State machine

```
queued ──claim──► running ──success──► completed (report_id)
   ▲                 │
   │                 ├─transient failure, attempts left──► queued
   │                 ├─permanent failure──────────────────► failed
   │                 └─lease expired───► queued | failed (worker_lost)
   │
   └── cancelled (never runs; a cancelled job is skipped, not executed)
```

`run_job` refuses to touch a job that is `completed`, `cancelled` or `failed`.
Re-running a completed job returns it unchanged and produces **no second
report** — and even if it did generate, the report cache would return the same
snapshot.

## Without a provider key

The worker starts, logs `ai_worker_idle_unconfigured` **once**, and consumes
nothing. Draining the queue only to fail every job would turn a missing key
into a pile of permanently failed reports; leaving the work queued means it
runs as soon as the key is there.

The API behaves the same way from the other side: `/ai/reports` and
`/ai/report-jobs` answer `503 ai_not_configured`, so nothing is accepted that
nobody can do.

## Shutdown

`SIGINT` / `SIGTERM` set a stop flag. The worker finishes the job in hand — it
does not abandon a generation the user is waiting for — then releases its
claim and exits. If it was mid-job, `release_claim(requeue=True)` puts the job
straight back in the queue rather than waiting out its lease.

Compose sets `stop_grace_period: 90s` for that reason. A shorter grace period
means `SIGKILL` mid-generation, which is survivable (the lease recovers it)
but wasteful.

## Failure containment

Nothing in one job may stop the loop:

- `process()` never raises. A crash is logged and the claim is left to expire.
- A claim failure (a database blip) is logged and the loop sleeps and retries.
- A job whose user has been deleted fails with `user_missing` rather than
  raising.

## Running it

```bash
# Local
python -m app.workers.ai_report_worker

# Docker
docker compose up -d ai-worker
docker compose up -d --scale ai-worker=3 ai-worker   # several is safe
docker compose logs -f ai-worker
```

The compose service has no ports — a worker serves nobody — and
`restart: unless-stopped`.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `AI_JOB_LEASE_SECONDS` | 600 | How long a claim survives without renewal |
| `AI_JOB_MAX_ATTEMPTS` | 3 | Attempt ceiling per job |
| `AI_WORKER_POLL_SECONDS` | 2.0 | Idle poll interval |
| `AI_WORKER_IDLE_LOG_SECONDS` | 300 | How often an idle worker reports queue depth |

## What to watch

| Log event | Meaning |
| --- | --- |
| `ai_worker_started` | worker id, poll interval, lease length |
| `ai_worker_idle` | queue depth, every 5 minutes while idle |
| `ai_worker_idle_unconfigured` | no key; nothing is being consumed |
| `ai_job_started` / `ai_job_completed` | normal work |
| `ai_job_retry` | transient failure, going back to the queue |
| `ai_job_failed` | gave up, with the error code |
| `ai_jobs_recovered` | a worker died and its jobs were released |
| `ai_job_crashed` | a bug; the claim will expire |

Useful queries:

```sql
-- backlog
SELECT status, count(*) FROM ai_report_jobs GROUP BY 1;

-- jobs stuck with a dead owner
SELECT id, worker_id, attempt, lease_expires_at FROM ai_report_jobs
WHERE status = 'running' AND lease_expires_at < now();

-- why jobs fail
SELECT error_code, count(*) FROM ai_report_jobs
WHERE status = 'failed' GROUP BY 1 ORDER BY 2 DESC;
```

## Limits worth knowing

- Polling, not `LISTEN/NOTIFY`. A job waits up to `AI_WORKER_POLL_SECONDS`
  before being picked up. For work measured in tens of seconds, two seconds of
  latency is not worth the extra moving part.
- No priority. Oldest first, always. A premium report does not overtake a
  daily one.
- No scheduled or recurring jobs. Everything in the queue was asked for by a
  user.
