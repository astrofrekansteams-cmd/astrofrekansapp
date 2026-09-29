# Voice and video calls

## The flow

```
Flutter
  │  POST /calls               ← open the call for an order (either party)
  │  POST /calls/{id}/join     ← full re-authorisation, then a 10-minute token
  ▼
FastAPI ── authorise ──► Postgres (call_sessions, call_participants)
  │                         ▲
  │ CreateRoom              │ webhooks: participant_joined / left, room_finished
  ▼                         │
LiveKit ◄──── WebRTC audio/video ────► Flutter (livekit_client)
  │
  └─► FCM (via the B9 outbox): incoming_call / call_missed / call_cancelled
```

| Layer | Owns |
|---|---|
| FastAPI | every authorisation decision, token minting |
| Postgres | call lifecycle, participants, provider-event audit |
| LiveKit | the room and the media — nothing else |
| Firebase (B9) | incoming-call push through the existing outbox |

## Principles

* **A call exists because a paid, scheduled order does.** Nobody opens a call
  with an arbitrary expert id. See [call_authorization.md](call_authorization.md).
* **Nothing reaches LiveKit before every business check passes** — on every
  token, including reissues.
* **Only provider events make a call ACTIVE.** A client cannot declare a call
  started; `started_at` is the first moment LiveKit reported both parties in the
  room.
* **One live call per order** — a partial unique index, not an
  application-level SELECT.
* **Least privilege.** No data channel, no room administration, only the track
  sources the call type allows.
* **No PII at the provider.** Room `call_<random>`, identities `p_<random>`, no
  names, no metadata.
* **No recording, no transcription, no media through FastAPI.**

## Tables

**`call_sessions`** — one attempt at a live consultation. `order_id`,
`appointment_id`, `conversation_id`, both accounts (`user_id`,
`expert_user_id`), `call_type`, `status`, provider room name, the appointment
window snapshotted, `ringing_at` / `started_at` / `ended_at`, `end_reason`,
`ended_by`, `duration_seconds`, `recording_enabled` (held at false by a check
constraint).

**`call_participants`** — the two people, created with the session. Opaque
`provider_identity`, status (`invited → joining → joined → left | disconnected`),
join/leave timestamps, connection count, token issue count. The set of people
allowed in the room is fixed before anybody joins.

**`call_provider_events`** — webhooks already seen: provider event id (unique),
type, opaque room and identity, timestamps, SHA-256 of the body, outcome. **Not
the raw payload** — it carries names and metadata.

### The B8/B9 reserved pointers

`service_orders.call_session_id`, `appointments.call_session_id` and
`expert_conversations.call_session_id` are **left unwritten**. The source of
truth is `call_sessions.order_id / appointment_id / conversation_id`: one order
or conversation can have several calls over time (a failed attempt, a retry
after a drop past the grace), and a single pointer on the parent could hold
only one of them. Writing both would give two answers to "which calls belong to
this order". Dropping the reserved columns is a later, separate migration.

## Text chat stays in B9

Calls do not carry messages. The LiveKit data channel is disabled in every
token, so there is no second, unaudited chat. The Firestore conversation stays
open during a call. B9 **presence** (app online) and LiveKit **room presence**
(in the call) are different things and are never mixed — being online is not
being in a call.

## Push

Reuses the B9 outbox and FCM provider. New events: `incoming_call`,
`call_cancelled`, `call_missed`. Payload:

```json
{"title": "Astrofrekans", "body": "Gelen görüntülü görüşme",
 "data": {"event": "incoming_call", "call_id": "…", "call_type": "video"}}
```

No service, no topic, no order, no other person's name — a lock screen is public.
Never sent to the person who caused it. Dedupe key per ringing episode
(`incoming_call:{call}:{recipient}:{ring started}`), so a retried webhook does
not ring twice but a caller who hangs up and calls again does ring again.
Pending rings are withdrawn (`skipped`) the moment the call is answered, missed
or cancelled — an incoming-call notification delivered late makes a phone ring
for nothing.

### Mobile call UI is the Flutter phase

iOS CallKit + PushKit (VoIP push) and Android ConnectionService / full-screen
intent notifications are client concerns. The backend does not imitate them.
Known requirement for that phase: FCM data messages are not VoIP pushes — iOS
background incoming-call UI needs PushKit via APNs, which is a new push channel,
not a change to this one.

## What has been verified

| Where | What |
|---|---|
| unit/API tests (fake provider, SQLite) | 72 tests: authorisation matrix, windows, tokens, lifecycle, webhooks, reconciliation, push, privacy, rate limits |
| real Postgres 17 | 10 concurrent creates → 1 session; the same webhook ×8 → applied once; 10 concurrent joins → 1 session, 1 identity, 10 tokens counted |
| migration | `0010` upgrade → `alembic check` clean → downgrade → upgrade, on a throwaway database |
| **real LiveKit 1.13.7 (local)** | 25/25: tokens accepted; server-reported permissions (no data, only allowed sources); audio token cannot publish a camera; signed webhooks drive RINGING → ACTIVE → ENDED; DUPLICATE_IDENTITY replacement keeps the call active; deleted room cannot be reopened by a leftover token |
| Docker smoke | both branches: without LiveKit (controlled 503s, rest of product 200) and with it (forged webhooks 401, unknown call 404) |

Not verified: LiveKit Cloud, real mobile clients, real media quality, TURN.

## Telemetry, later

Packet loss, jitter, RTT and reconnect counts are available to the client SDK.
A future `POST /calls/{id}/quality` could accept aggregated numbers per call for
support and refund decisions. Not built: no per-packet streaming, and nothing
that identifies a device or a network.
