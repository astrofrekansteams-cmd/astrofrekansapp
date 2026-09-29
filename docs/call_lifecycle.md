# Call lifecycle

## States

```
            create (before window)          create (window open)
                    │                               │
                    ▼                               ▼
               SCHEDULED ──── first join ───► WAITING ◄─────────────┐
                    │                          │   │                │ lone party left,
                    │                 one in   │   │ both in         │ grace passed
                    │                 the room ▼   │                │
                    │                      RINGING ─┘────────────────┘
                    │                          │   │
                    │                     both │   │ ring timeout
                    │                      in  ▼   ▼
                    │                    ACTIVE    MISSED
                    │                      │
                    ▼                      ▼
    CANCELLED / ENDED(no_show)           ENDED
              FAILED (room could not be created)
```

The table lives in `app/domain/calls.py` (`TRANSITIONS`). Every change goes
through `CallService._transition`, which refuses anything not listed. No route
assigns a status.

`ENDED`, `MISSED`, `CANCELLED` and `FAILED` are terminal. A terminal call never
becomes live again; another attempt is a new session with its own audit trail.

## What drives it

* **People** — create, join, end.
* **The provider** — `participant_joined`, `participant_left`,
  `participant_connection_aborted`, `room_finished`.
* **The clock** — ring timeout, reconnect grace, the window closing, the hard
  ceiling. Evaluated on every read, every webhook and by the call worker.

## Definitions

**RINGING** — exactly one party is in the room. The other is sent
`incoming_call`.

**ACTIVE** — both parties in the room at the same time, as reported by
LiveKit. `started_at` is that moment. Issuing tokens to both is not ACTIVE; a
client saying "we started" is not ACTIVE.

**MISSED** — it rang for `CALL_RING_TIMEOUT_SECONDS` (60) and the other party
never joined. They get `call_missed`; the caller does not.

**Caller gave up** — the lone party left while ringing and did not return within
the grace: back to WAITING (the call can ring again inside its window), and the
rung party gets `call_cancelled`.

**NO_SHOW** — nobody joined before the window closed: ENDED with
`end_reason=no_show`, no `started_at`, no duration.

**Ended by hand** — `POST /calls/{id}/end` by either party. ACTIVE → ENDED;
anything earlier → CANCELLED (and `call_cancelled` if it was ringing). The
other party cannot be "kicked": this is a 1:1 consultation with no moderation
role.

## Disconnect is not end

WebRTC drops happen. A participant who leaves is not gone until
`CALL_RECONNECT_GRACE_SECONDS` (45) pass without them returning. Then:

| How they left | `end_reason` | `ended_by` |
|---|---|---|
| `CLIENT_INITIATED` (hung up, closed the app) | `user_ended` / `expert_ended` | that role |
| anything else (network, timeout) | `network_disconnect` | — |
| `DUPLICATE_IDENTITY` | *not a leave* — a newer connection replaced them | — |

`ended_at` is **when they left**, not when the grace ran out. The grace is not
billed as consultation time.

### Absence is confirmed with the provider

Decisions made from somebody's absence — MISSED, ENDED by a drop, the caller
giving up — ask LiveKit who is actually in the room first. Webhooks can arrive
late: a `participant_joined` delivered after a backlog would otherwise start a
ring timeout that already expired and mark a call MISSED while both people are
talking. There is a test for exactly that.

## Duration

```
duration_seconds = max(0, ended_at − started_at)
```

Server-side timestamps only, from provider events; never a client timer.
Reconnections inside the grace count as call time (the call never stopped
being the consultation). Webhook timestamps are whole seconds, so durations
are accurate to a second. A call that never became ACTIVE has no duration.

## Limits

| Setting | Default | Effect |
|---|---|---|
| `CALL_JOIN_EARLY_SECONDS` | 600 | window opens before the start |
| `CALL_JOIN_LATE_SECONDS` | 900 | window closes after the **end**; live calls stop then (`timeout`) |
| `CALL_RING_TIMEOUT_SECONDS` | 60 | RINGING → MISSED |
| `CALL_RECONNECT_GRACE_SECONDS` | 45 | a drop becomes an end |
| `CALL_MAX_DURATION_SECONDS` | 10800 | hard ceiling from `started_at`, whatever the appointment says |
| `CALL_ROOM_EMPTY_TIMEOUT_SECONDS` | 300 | LiveKit's own backstop for empty rooms |
| `CALL_TOKEN_TTL_SECONDS` | 600 | join authorisation only |

No room is left open indefinitely: the window, the hard ceiling, the worker and
LiveKit's empty timeout each close it.

## Provider failure

* **Room creation fails at create** → the session is FAILED with
  `provider_error_code`, the API answers `503 call_provider_unavailable` with the
  failed `call_id`, and the order and appointment are untouched. Opening the call
  again is a new attempt (the failed one no longer blocks the live-call index).
* **Room creation fails at join** (a scheduled call whose window just opened) →
  `503`, the session is left as it was. Retry the join.
* **Token issuance** needs no network once the room exists, so a LiveKit API
  outage does not stop reconnects to an existing room.
* A provider outage never changes the order's or the appointment's status. A
  call failure is a call failure, recorded with its reason.

## The worker

```bash
python -m app.workers.call_worker
```

Sweeps live calls every `CALL_WORKER_POLL_SECONDS`: applies the clock, and
reconciles against LiveKit any live call not looked at for
`CALL_RECONCILE_INTERVAL_SECONDS`. Calls are claimed with `FOR UPDATE SKIP
LOCKED`, so several workers can run. Without LiveKit credentials it idles. In
compose it is `call-worker`, with the inherited HTTP healthcheck disabled (a
worker serves no HTTP).

## Recording

None. No Egress dependency, no egress in `CreateRoom`, no `roomRecord` grant,
and `call_sessions.recording_enabled` is held at false by a check constraint —
turning recording on is a migration and a decision about consent, retention and
jurisdiction, not a flag. No transcription, no voice AI, no face analysis, no
biometric processing, no media through FastAPI.

## Not stored

Camera and microphone state, mute events, track lists, quality statistics.
Coarse participant state (invited / joining / joined / left / disconnected) is
enough for authorisation and audit.
