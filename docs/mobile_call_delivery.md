# Mobile call delivery (B12C.1 hardening)

How an incoming call reaches a phone that is locked, backgrounded or asleep -
and how the ringing stops. Backend side only; the client work is listed at the
end.

Two rules sit above everything here:

* **An ordinary app notification is not a VoIP push.** Chat, bookings,
  payments keep the B9 FCM notification path, unchanged. Call lifecycle events
  have their own per-platform transports.
* **Push presentation is not call authorisation.** A push says "show a
  ringing screen for call X". It is not a join token, not a LiveKit token, not
  proof of payment. Answering always goes `GET /calls/{id}` →
  `POST /calls/{id}/join` → LiveKit, through B10's checks.

## Official behaviour this is built on (verified 2026-09-25)

| Source | What it says | Consequence here |
| --- | --- | --- |
| Apple, *Sending notification requests to APNs* | HTTP/2 + TLS 1.2; `POST /3/device/<token>`; `apns-push-type: voip` requires `apns-topic` = bundle id + `.voip`; `apns-expiration` 0 = "attempts to deliver the notification only once and doesn't store it"; VoIP payload ≤ 5 KB | `ApnsHttpProvider` |
| Apple, *Establishing a token-based connection* | ES256 JWT, `kid` header, `iss` team id, `iat`; refresh "no more than once every 20 minutes and no less than once every 60 minutes" | JWT cached 40 min |
| Apple, *Responding to VoIP notifications from PushKit* | iOS 13 SDK+: every VoIP push must be reported to CallKit; set `apns-expiration` to 0 or a few seconds; "don't send additional push notifications to cancel the call" - use the app's network connection and `reportCall(with:endedAt:reason:)` | VoIP carries `incoming_call` only |
| Apple, *Handling notification responses from APNs* | `BadDeviceToken` (400), `Unregistered` (410), `DeviceTokenNotForTopic` (400) are dead tokens; 429/5xx retry | credential disabled / retried |
| Firebase, *Message priority* | HIGH only for messages that result in something the user sees; FCM deprioritises apps whose HIGH messages do not; `onMessageReceived` gets "several seconds" | HIGH for ring/dismiss/missed; no network needed to present |
| Firebase, *Message lifespan* | TTL 0 = now or never; incoming video calls are the example use case | TTL = seconds left in the ring |
| Firebase, *Collapsible messages* | data messages are non-collapsible by default; collapse replaces only *undelivered* messages; max 4 keys per device; no ordering guarantee | `collapse_key=call:{id}` + `event_version` |
| Android 14 behaviour changes | `USE_FULL_SCREEN_INTENT` limited to calling/alarm apps; check `NotificationManager.canUseFullScreenIntent()` | client concern, listed below |

## Credentials

`push_devices` holds both kinds, kept apart by `credential_type`:

| `credential_type` | Registered with | Used for |
| --- | --- | --- |
| `fcm` | `POST /devices/push` (B9) | every ordinary notification; Android call events; iOS call fallback/background |
| `apns_voip` | `POST /devices/voip` | **only** `incoming_call` on iOS, via APNs `voip` |

An iPhone has one of each; they are different credentials and never
interchangeable - registering a VoIP token as FCM (or the reverse) is `422
invalid_push_token`. Ordinary notifications never select a VoIP token.

VoIP tokens: hex, stored lower-case, unique, owner-only, never returned or
logged (fingerprint only), moved - not duplicated - when another account
registers the same token (the B9 rule). `environment` (`production` for
TestFlight/App Store, `sandbox` for development builds) must equal the
server's `APNS_ENVIRONMENT`.

## Routing

`app/services/notifications/call_delivery.py` - one table, no provider-level
if/else:

| Event | Android FCM | iOS VoIP | iOS FCM | web |
| --- | --- | --- | --- | --- |
| `incoming_call` | data-only, HIGH, TTL = rest of the ring | APNs `voip` | alert - **only if the user has no VoIP token** | alert |
| `call_answered` | data-only, HIGH | - | background update | - |
| `call_cancelled` | data-only, HIGH | - | background update | - |
| `call_missed` | data-only, HIGH | - | alert ("Cevapsız … görüşme") | alert |

A user with an Android phone and an iPhone gets each device's transport; every
eligible device rings.

### Payload (every transport)

```json
{"event": "incoming_call", "call_id": "…", "call_type": "audio|video",
 "event_version": "7123456789012", "expires_at": "1790000000"}
```

`expires_at` only on `incoming_call`. Never a name, a service, an order, an
amount, a message, birth data, a question or a LiveKit token.

**Ordering.** FCM does not guarantee order. `event_version` = ring start (ms) ×
4 + rank (incoming 0, answered 1, cancelled 2, missed 3). Keep the highest
version per `call_id` and ignore anything lower: a late ring never resurrects a
call that ended, and a second ring of the same call outranks the first ring's
cancellation.

### APNs request

`POST https://api.push.apple.com/3/device/<token>` (sandbox host for
`sandbox`), headers `authorization: bearer <ES256 JWT>`, `apns-push-type:
voip`, `apns-topic: <APNS_BUNDLE_ID>.voip`, `apns-priority: 10`,
`apns-expiration: 0` (`APNS_VOIP_EXPIRATION_SECONDS`, never beyond the ring),
`apns-id: <delivery id>`.

### FCM data message (Android)

No `notification` block. `android.priority=high`, `android.ttl` = seconds
left until `expires_at` (B10's `CALL_RING_TIMEOUT_SECONDS` is the only clock),
`collapse_key=call:{id}` so a device offline for a whole call receives the
latest event rather than a stale ring then its cancellation. Collapse only
affects undelivered messages; delivered-event idempotency is the ledger below
and `event_version` on the device.

## Outbox

B9's outbox stays the single queue: same business transaction, same
`dedupe_key`, same `SKIP LOCKED` claim. What changed for call events:

* **Expiry.** `notification_outbox.expires_at` = ring start + ring timeout for
  `incoming_call`, `call_cancelled`, `call_answered` (nothing to dismiss after
  the ring). A row claimed after it is `skipped` with `skipped_expired` - never
  sent late, however long it sat in retries. `call_missed` has no expiry.
* **Per-device ledger.** `notification_deliveries` (unique `outbox_id +
  device_id`) is one **logical** delivery per device; `attempts` counts the
  physical sends it took. Statuses: `pending` → `sending` → `delivered` |
  `failed` | `skipped`.
* **Outcome.** any `pending` → row back to `pending` (bounded by
  `PUSH_OUTBOX_MAX_ATTEMPTS`, then the pending deliveries fail
  `max_attempts`; bounded by expiry first); anything delivered → `sent`; only
  `skipped provider_not_configured` → `skipped` (no APNs key / no Firebase:
  not a failure, not retried); nothing deliverable → `failed`.

## Delivery semantics: at least once

A call must not be lost because a worker died. So delivery is **at least
once**, and duplicates are the device's to suppress.

1. **Claim** - one transaction, committed: due deliveries (`pending`, or
   `sending` whose `lease_until` has passed) are locked `FOR UPDATE SKIP
   LOCKED` and set `sending`, `lease_until` = the outbox row's lease,
   `attempts + 1`, `last_attempt_at`.
2. **Send** - no database transaction is open during a provider call.
3. **Record** - the result is written only where `attempts` still equals
   this claim's attempt and the row is still `sending`; a worker whose lease
   lapsed cannot overwrite the one that took over (`attempts` is the fence).

Failure handling:

| Case | Result |
| --- | --- |
| provider accepted | `delivered`, never claimed again |
| 429, 5xx, network error, FCM transient | `pending`; the outbox row is retried; only undelivered devices are resent |
| worker dies before or during the send | stays `sending`; when the **call push lease** (15 s) lapses, B9's outbox recovery re-queues the row, the delivery's lease has lapsed with it, and the next worker claims the **same** delivery (`attempts` 2) - while the phone can still ring |
| provider hangs | cut off at `CALL_PUSH_SEND_TIMEOUT_SECONDS` (8 s) → `pending` `provider_timeout`, retried at once, inside the lease |
| worker dies after the provider accepted, before recording | as above: the device may get the same event twice |
| APNs `BadDeviceToken` / `Unregistered` / `DeviceTokenNotForTopic` | `failed`, credential disabled, not retried |
| FCM `UnregisteredError` / `SenderIdMismatchError` | `failed`, token disabled (B9), not retried |
| ring expired before the retry | `skipped` `skipped_expired`, never sent late |
| another worker's live lease | not claimed; the row is left to it |

### Call push timing

A ring lasts `CALL_RING_TIMEOUT_SECONDS` (60 s). B9's generic outbox lease is
`PUSH_OUTBOX_LEASE_SECONDS` (120 s) - fine for a chat message, useless for a
ring: a worker that died holding one would be taken over after the call was
missed. So call events (`incoming_call`, `call_answered`, `call_cancelled`,
`call_missed`) are claimed for `CALL_PUSH_LEASE_SECONDS` instead; ordinary
notifications keep B9's lease unchanged. `incoming_call` is the one that
matters; answered/cancelled only mean anything inside the same ring, and a
missed-call notice simply recovers sooner.

A short lease is only safe if a *live* worker can never outlast it. So every
call push provider operation is bounded on the wall clock by
`CALL_PUSH_SEND_TIMEOUT_SECONDS` (an `asyncio` timeout around the APNs request
and around the FCM batch - firebase-admin's own HTTP timeout is 120 s, and B9
relies on it, so it is not changed globally), and the operations run
concurrently, so a whole send takes about one timeout at most.

| Setting | Default | |
| --- | --- | --- |
| `APNS_TIMEOUT_SECONDS` | 8 | httpx per-phase timeout; ≤ send timeout |
| `CALL_PUSH_SEND_TIMEOUT_SECONDS` | 8 | hard bound on one provider operation |
| `CALL_PUSH_LEASE_SECONDS` | 15 | a call push claim |
| `CALL_RING_TIMEOUT_SECONDS` | 60 | B10's ring (the lifecycle clock) |

Checked when settings load; a violation refuses to boot rather than falling
back to a longer lease:

    APNS_TIMEOUT_SECONDS <= CALL_PUSH_SEND_TIMEOUT_SECONDS
    CALL_PUSH_SEND_TIMEOUT_SECONDS + 2 s <= CALL_PUSH_LEASE_SECONDS < CALL_RING_TIMEOUT_SECONDS

The 2 s margin covers the claim and record round trips. With the defaults a
worker that dies at t=0 is taken over at t≈15-17 s (lease plus one worker
poll), and the ring is still valid until t=60 s. `expires_at` stays the only
expiry: a delivery claimed after it is `skipped_expired`.

**Duplicate safety.** The duplicate is the same logical delivery: same
`call_id`, same `event_version`, same payload - and on iOS the same `apns-id`
(the delivery id, stable across retries). Apple documents `apns-id` as the
notification's identifier for error reporting; it does **not** document
deduplication on it, so the backend does not rely on it. The device does:

* Android: keep the highest `event_version` per `call_id`; an event equal to
  or lower than the one already handled creates no second UI.
* iOS: derive the CallKit UUID deterministically from `call_id`. A second VoIP
  push for a call already reported (or already ended) must still be reported
  to CallKit (PushKit requires it) and is ended at once / ignored by the app.
  **NOT VERIFIED on a device.**
* **Dead credentials.** APNs `Unregistered`/`BadDeviceToken`/
  `DeviceTokenNotForTopic` disable the VoIP device (`disabled_reason
  apns_<reason>`); FCM dead tokens keep B9's handling.

## Lifecycle (B10 is the clock)

B10 decides; the push layer has no timers of its own.

* Ring starts → `incoming_call` to the other party.
* Both present → `ACTIVE`: pending rings are withdrawn (B10) and
  `call_answered` goes to exactly the users that ring was sent to, so their
  other devices stop ringing. The device that answered ignores it.
* Caller leaves / cancels → `call_cancelled`.
* Ring timeout → `MISSED` → `call_missed`.
* B10's duplicate-identity rule is unchanged: a second device that answers
  replaces the first's media connection.

## iOS cancellation strategy

Apple: do not push again to cancel; tell the app over its own connection and
end the CallKit call with `reportCall(with:endedAt:reason:)`. So:

1. On the VoIP push: report to CallKit immediately (required), then
   `GET /calls/{id}`; if the call is no longer ringing, end the CallKit call at
   once with `.remoteEnded`.
2. While ringing, poll `GET /calls/{id}` (or keep a connection) and end the
   CallKit call when it is answered elsewhere, cancelled or missed.
3. End it locally at `expires_at` regardless.
4. `call_answered` / `call_cancelled` also go to the iPhone's FCM token as a
   background update - best effort, throttled by iOS, a hint only.
5. `call_missed` arrives as an ordinary FCM notification.

**NOT VERIFIED on a device.** No iOS build implements PushKit/CallKit yet.

## Android background contract

`FirebaseMessagingService.onMessageReceived` receives every call event in the
background (data-only). It must present or dismiss from the payload alone -
the handler window is a few seconds, too short for a network round trip. The
ringing notification uses a `CATEGORY_CALL` full-screen intent where
`canUseFullScreenIntent()` allows (Android 14+), otherwise a heads-up
notification. Answer → open the app → authenticated `GET /calls/{id}` →
`POST /calls/{id}/join`.

## Configuration

| Setting | Default | |
| --- | --- | --- |
| `APNS_PROVIDER` | `apns` | `fake` is a test double; refused in production |
| `APNS_TEAM_ID`, `APNS_KEY_ID` | - | from the Apple developer account |
| `APNS_PRIVATE_KEY` / `APNS_PRIVATE_KEY_PATH` | - | the `.p8` key; secret store, never git (`*.p8` is ignored) |
| `APNS_BUNDLE_ID` | - | topic is `<bundle>.voip` |
| `APNS_ENVIRONMENT` | `production` | the only environment this server delivers to |
| `APNS_VOIP_EXPIRATION_SECONDS` | `0` | Apple: 0 or a few seconds |
| `APNS_TIMEOUT_SECONDS` | `8` | ≤ `CALL_PUSH_SEND_TIMEOUT_SECONDS` (see Call push timing) |

Nothing is required to boot. The notification worker runs when **either**
transport is configured:

| Firebase | APNs | Worker |
| --- | --- | --- |
| yes | yes | claims everything |
| yes | no | claims everything; iOS VoIP targets `skipped provider_not_configured` |
| no | yes | claims **call events only**; iOS VoIP delivered, FCM targets skipped; ordinary notifications stay queued for Firebase |
| no | no | idle; the queue is untouched |

## Verification

* `tests/test_call_delivery.py`: Android data-only/HIGH/TTL/collapse,
  ordering, ordinary pushes unchanged, APNs request shape (fake and the real
  provider over `httpx.MockTransport`, JWT checked with the public key), iOS
  never VoIP for cancel/answered/missed, fallback, dead token, retry of only
  failed targets, not configured, expiry, multi-device once, privacy,
  registration ownership/rotation/interchangeability, production refusal.
* `tests/test_call_delivery_reliability.py`: worker dies before send /
  after the provider accepted → same delivery re-sent after the lease, same
  `apns-id` and `event_version`; live lease never claimed twice; transient FCM
  and APNs retries; expiry before retry; permanent failure not retried;
  worker startup matrix.
* `tests/test_call_delivery_fast_lease.py`: A claims at t=0 and dies, B
  cannot claim at t=10, claims at t=16, delivers (`attempts` 2, ring still
  valid); lease lapsing after the ring → `skipped_expired`; a worker inside
  a provider call keeps its claim; a hung provider is cut off inside the
  lease; generic notifications keep B9's lease; unsafe timings refused.
* `scripts/call_push_concurrency_check.py` (real Postgres): concurrent
  enqueue → one row; 8 workers → every device once per event; two workers on
  one row → once per device; worker A claims and dies, B takes over → one
  row, `attempts=2`, delivered; six workers recovering one stale delivery →
  exactly one claim per lapse; short call lease on the wall clock (ring 10 s,
  lease 3 s) → recovered after ~3.05 s and delivered while still ringing.
* **Live APNs and live FCM: NOT VERIFIED** (no credentials, no device build).
