# LiveKit webhooks

`POST /api/v1/webhooks/livekit`

LiveKit is the only source of "who is in the room". Its webhooks are how the
backend learns it — so the endpoint is the most attractive thing in B10 to
forge, and it is treated that way.

## Verification

LiveKit signs every webhook: the `Authorization` header is a JWT issued by our
API key, whose `sha256` claim is the base64 SHA-256 of the **exact body**.
`livekit.api.WebhookReceiver` checks the signature, the issuer and the hash.

* The endpoint reads the **raw bytes** (`await request.body()`). Parsed JSON
  re-serialised would not hash to what was signed.
* No header, a garbage header, a token signed with the wrong secret, a genuine
  signature over a modified body, an expired token — all the same
  `401 invalid_webhook`. Saying which check failed would help only a forger.
* A rejection is logged as `livekit_webhook_rejected` with whether a header was
  present and the body length. Neither the header nor the body is logged: both
  are attacker-supplied, and the header may be a real token.
* Without LiveKit configured the endpoint answers `503`.
* Rate-limited per IP (`LIVEKIT_WEBHOOK_RATE_LIMIT`, 600/minute) — not per user,
  because LiveKit is not a user. The signature is the protection; the limit only
  bounds the cost of checking signatures on garbage.

Tested with the real verifier: missing, garbage, wrong key, modified body. And
end-to-end: a real LiveKit 1.13.7 delivered 60 webhooks, every one accepted.

## Events

Documented names, verified against LiveKit's docs:

| Event | Effect |
|---|---|
| `participant_joined` | participant → JOINED; one in room → RINGING, both → ACTIVE |
| `participant_left` | participant → LEFT (`CLIENT_INITIATED`) or DISCONNECTED; the grace decides what it means |
| `participant_connection_aborted` | as `participant_left` |
| `room_finished` | everybody present → DISCONNECTED; the room is re-provisioned on the next join if the call is still live |
| `room_started`, `track_published`, `track_unpublished`, others | recorded, no effect |

`DUPLICATE_IDENTITY` on a leave means the same person connected again and
LiveKit replaced the old connection. It is **not** a leave (`outcome=replaced`).

## Idempotency

The event id is recorded **first**, in a savepoint, under
`uq_call_provider_events_event (provider, event_id)`. A retried webhook finds its
id taken and changes nothing (`outcome=duplicate`). Proven on Postgres: the same
event delivered 8× concurrently → applied once, `connection_count = 1`.

## Ordering

LiveKit sequences deliveries, but delivery is not guaranteed. Each participant
keeps `last_event_at` — the provider timestamp of the newest event applied to
them. An older event arriving later is history (`outcome=stale`) and cannot move
the participant backwards.

## Matching

Participants are matched by **opaque identity** within the room's call. Nothing
in the webhook — display name, metadata — informs a business decision, and none
of it is stored.

| Situation | Outcome |
|---|---|
| room not ours (another environment on the same project, a forgotten room) | `unknown_room`, recorded, ignored |
| identity not one of the two participants | `intruder`: `call_intruder_detected` logged with a fingerprint of the identity (not the identity), `RemoveParticipant` called |
| a participant joins a call that already ended (a leftover token) | `late_join_removed`: removed, and the room deleted again |

An intruder needs a token we did not issue, i.e. our API secret. So it is either
a leaked secret or a bug, and in both cases they are removed.

## What is stored

`call_provider_events`: provider, event id, event type, the call it belongs to,
the opaque room and identity, the provider's timestamp, when we received and
processed it, a SHA-256 of the body, and the outcome. **Not the payload** — it
carries participant names, metadata and track details.

## Reconciliation

Webhooks are not guaranteed. `CallService.reconcile(call)` asks LiveKit
(`ListParticipants`) who is actually in the room and repairs our view: present
but not recorded → JOINED; recorded but absent → DISCONNECTED; present but not
one of the two → removed. The call worker reconciles every live call not looked
at for `CALL_RECONCILE_INTERVAL_SECONDS`, and every absence-based terminal
decision (MISSED, ended by a drop) reconciles first. A provider outage during
reconciliation changes nothing (`provider_unavailable`).

## Server configuration

```yaml
webhook:
  api_key: <LIVEKIT_API_KEY>
  urls:
    - https://api.example/api/v1/webhooks/livekit
room:
  auto_create: false
```

The key must be the same pair the backend holds. `auto_create: false` makes
"a room exists only because the backend created it" true at the server.
