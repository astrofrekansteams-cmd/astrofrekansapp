# Push notifications

## The outbox, and why

Push is **not** on the critical path of a business transaction. A request writes
a row; a worker delivers it.

Two properties, both worth more than the indirection costs:

* **The business transaction stays atomic.** The outbox row is written in the
  same transaction as the message or the booking. There is no state where the
  thing happened and nothing will ever be sent, and none where a notification
  promises something that rolled back.
* **One event, one notification.** `dedupe_key` is a unique constraint, so a
  retried request, a replayed webhook and a worker that restarts mid-flight all
  converge on one row.

FCM being down must not roll back an order somebody paid for.

### Enqueuing uses a savepoint, not the transaction

`enqueue` checks for an existing row first - that handles the ordinary retry
cheaply - and wraps the insert in `begin_nested()` for the race the check cannot
cover: two connections that both look, both see nothing, and both insert.

The savepoint matters. `session.rollback()` there would discard the *caller's*
work: booking notifies two people, and a dedupe on the second would have rolled
back the appointment. It would also expire every object the caller still holds,
which is how a deduped chat notification used to turn into a `500`.

## What a payload may contain

A lock screen is a public surface. Somebody else can read it while the phone is
on a table.

So a payload carries an id and a generic Turkish line. Never a message body,
never birth data, never a horary question, never an amount, never a name.

```json
{
  "title": "Astrofrekans",
  "body": "Yeni mesajınız var.",
  "data": {"event": "new_chat_message", "conversation_id": "…"}
}
```

The app fetches the detail after the user opens it, by which point they have
authenticated. `test_a_message_queues_a_notification_for_the_other_party` asserts
the message text is absent from the stored payload.

`data` is ids only, for the client to route on. The client re-renders the
notification in the user's own locale once it has their session; the generic
title is what shows if it does not.

## Events

| Event | Dedupe key |
|---|---|
| `new_chat_message` | `chat:{message_id}:{recipient}` |
| `appointment_booked` | `appointment_booked:{appointment_id}:{side}` |
| `appointment_cancelled` | `appointment_cancelled:{appointment_id}:{recipient}` |
| `appointment_reminder` | `reminder:{appointment_id}:{offset_seconds}` |
| `order_status_changed` | caller-supplied |
| `incoming_call` (B10) | `incoming_call:{call_id}:{recipient}:{ring started}` |
| `call_cancelled` (B10) | `call_cancelled:{call_id}:{recipient}[:{ring started}]` |
| `call_missed` (B10) | `call_missed:{call_id}:{recipient}` |
| `call_answered` (B12C.1) | `call_answered:{call_id}:{recipient}:{ring started}` |

Call notifications carry `call_id`, `call_type`, `event_version` and (for a
ring) `expires_at` - never a name, a service or a topic. Pending
`incoming_call` rows are withdrawn (`skipped`) the moment the call is answered,
missed or cancelled. See `call_architecture.md`.

**Call events do not take the notification path below.** Since B12C.1 they go
per device over call-specific transports - data-only HIGH FCM on Android,
APNs PushKit VoIP (`incoming_call` only) on iOS - with an expiry
(`skipped_expired`) and a per-device delivery ledger. An ordinary app
notification is not a VoIP push, and a push is never call authorisation. See
[mobile_call_delivery.md](mobile_call_delivery.md).

## Reminders need no scheduler

Each offset - 24 hours, 1 hour, 15 minutes - becomes one outbox row with
`scheduled_for` set. The worker's "what is due" query **is** the scheduler:

```sql
WHERE status = 'pending' AND (scheduled_for IS NULL OR scheduled_for <= now())
```

Offsets already in the past are skipped rather than fired late. "Your appointment
is in 24 hours" delivered an hour beforehand is worse than nothing.

Cancelling an appointment marks its pending reminders `skipped`. A reminder for
something that is not happening is worse than no reminder.

## Claiming

`SELECT ... FOR UPDATE SKIP LOCKED`, one row per claim. The standard way to hand
one row to exactly one worker; without it two workers read the same pending row
and the user's phone buzzes twice.

A claim sets `sending`, stamps `worker_id`, takes a lease and increments
`attempts`. `recover_stale()` returns rows whose lease expired - a `sending` row
with an expired lease has no live owner - to `pending` if attempts remain and to
`failed` if not. A notification that keeps killing its worker should stop being
tried.

SQLite has no `SKIP LOCKED`, so the unit tests prove the state machine only.
`scripts/chat_concurrency_check.py` proves the locking against real Postgres:
many workers, many rows, every row claimed exactly once.

## Delivery

`send_each_for_multicast` - `send_multicast` and `send_all` were removed in
firebase-admin 7.x. Per-token outcomes are what token retirement needs anyway.

Three outcomes, and the distinction between them is the part that is easy to get
wrong:

**Sent.** At least one token accepted it.

**Skipped.** No enabled devices. A user with notifications off has nothing to
deliver to; marking that `failed` would fill the failure metric with people
exercising a preference.

**Failed.** Retryable if something transient happened, terminal if every token
was simply dead - retrying a dead token never succeeds.

### A dead token is retired, not retried

`UnregisteredError` and `SenderIdMismatchError` mean the app was uninstalled or
the token rotated. Those tokens are disabled with
`disabled_reason="unregistered"`. Left alone they fail on every future
notification and the outbox never clears.

### Collapsing

Several messages in one conversation share `collapse_key=conversation:{id}`, so
they become one badge rather than a stack of identical lines.

## Devices

An FCM token is an addressable secret: whoever holds it can send notifications to
that device. So:

* **Unique across the table.** Registering a token that belongs to another
  account **moves** it. A shared handset is a real thing, and leaving the token
  on the previous account would send that person's notifications to whoever is
  holding the phone now.
* **Never returned.** `GET /devices/push` returns `token_fingerprint`, a hash
  prefix. Echoing every token back would turn a device list into a way to harvest
  them.
* **Never logged.** Only `mask_token()` output, which is enough to match a
  support report to a row and useless to anybody who intercepts a log line.
* **Raw device identifiers are not stored.** `device_id` is hashed. A hash
  recognises a re-registration from the same handset; it cannot be correlated
  back to a physical device by anybody reading the table.
* **Deletion is a real delete**, not a flag. A token nobody should use is a token
  nobody should be able to read out of the database either.
* **Another account's device is a `404`.**

Minimum token length is 32 characters.

## The worker

```bash
python -m app.workers.notification_worker
```

Same shape as the AI report worker: recover, claim, deliver, repeat. Scale it
with `docker compose up -d --scale notification-worker=3`.

Without Firebase credentials it starts, says so once, and consumes nothing.
Draining the queue only to fail every row would turn a missing service account
into a pile of permanently failed notifications; leaving them pending means they
go out as soon as the credential arrives.

`SIGTERM` finishes the notification in hand and stops. `stop_grace_period: 30s`.

## Settings

| Setting | Default |
|---|---|
| `PUSH_OUTBOX_MAX_ATTEMPTS` | 5 |
| `PUSH_OUTBOX_LEASE_SECONDS` | 120 |
| `PUSH_WORKER_POLL_SECONDS` | 2.0 |
| `PUSH_WORKER_IDLE_LOG_SECONDS` | 300 |
| `PUSH_NOTIFY_SENDER_OTHER_DEVICES` | false |
| `DEVICE_REGISTER_RATE_LIMIT` | 30/hour |

A sender's own other devices are not notified by default. Somebody who just typed
a message does not need their tablet to buzz about it, and the cross-device sync a
client wants is a Firestore listener's job.

## Endpoints

| Method | Path |
|---|---|
| `POST` | `/api/v1/devices/push` |
| `GET` | `/api/v1/devices/push` |
| `DELETE` | `/api/v1/devices/push/{id}` |

## In-app notification centre (Phase 2)

The notification centre reads the same `notification_outbox` rows that push
delivers - one event stream, so push and the inbox can never disagree and
nothing is created for the inbox alone. Migration `0017` adds `read_at` and an
`(user_id, created_at)` index.

Shown: only user-facing events, grouped into categories -
`astro_ai` (ai_report_ready), `appointment` (booked, cancelled, reminder,
order status, missed call), `expert_message` (new chat message), `payment`
(payment, refund, subscription), `system` (daily content), `promotion`. Call
signalling (incoming, answered, cancelled) is never listed. A reminder shows
only once due; one dropped because its appointment was cancelled is hidden.
Push delivery status does not matter: a row skipped for lack of a device is
still in the inbox. `data` carries ids only; the app writes the text.

| Endpoint | |
| --- | --- |
| `GET /notifications?limit&before&category&unread` | newest first, cursor `next_before`, with `unread_count` |
| `GET /notifications/unread-count` | the bell |
| `PATCH /notifications/{id}` `{read}` | read / unread; another user's is 404 |
| `POST /notifications/read-all` | |
