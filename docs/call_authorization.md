# Call authorisation

All of it lives in `app/services/calls/policy.py`, as functions of loaded rows,
so creating a call, joining it and every token reissue ask exactly the same
question in exactly the same order:

```
caller → membership → order → expert → offering → payment
       → channel → appointment → window → call state → token
```

Nothing reaches LiveKit until every step has passed. LiveKit enforces the grants
it is handed; it never decides who deserves them.

## Membership

The caller must be the order's user, or the account behind the order's expert
(`expert.user_id`). An expert **profile id is not a credential** — another
expert, or anybody who knows an id, gets `404`. Never `403`: a guess must not
confirm that an order or call exists.

Either party may open the call. Whoever opens second gets the same session
(`200`), never a second room.

## The order

| Check | Refusal (`403 call_not_allowed`, `details.reason`) |
|---|---|
| order exists, not deleted | `order_unavailable` |
| has an expert and an offering | `order_has_no_expert` |
| fulfilment is `expert` or `hybrid` | `order_is_automated` |
| status in `paid, confirmed, awaiting_expert, in_progress` | `order_state_<status>` |
| expert is the order's expert | `expert_mismatch` |
| expert not suspended / inactive | `expert_suspended` / `expert_unavailable` |
| offering belongs to the order's expert | `offering_mismatch` |
| both accounts active and not deleted | `participant_unavailable` |

`pending_payment` is not callable: a call before payment is a free consultation.

## Payment invariant

A **priced** order must be `payment_status = paid`. `not_required` counts only
when the order is **actually free** (`total_minor = 0`) — a priced order
carrying `not_required` is a data error, and treating it as permission would be
a free consultation by accident.

No payment provider exists yet, so nothing in production marks a priced order
PAID. Until B11, priced consultations cannot be joined — the correct failure.
Tests and scripts create PAID orders directly as fixtures; no endpoint does.

## Channel: voice vs video

| Call | Allowed when |
|---|---|
| `audio` | catalogue `supports_voice`, and the order was sold as `voice` **or** `video` (a downgrade the customer may choose) |
| `video` | catalogue `supports_video`, and the order was sold as `video` (video on a voice order is an upgrade nobody paid for) |

A chat or written-report order has no call: `422 call_type_not_supported`.
The order's snapshot of the channel counts, not the offering's current
settings.

### What the token may publish

| Call | `canPublishSources` | Data channel | Admin grants |
|---|---|---|---|
| audio | `["microphone"]` | no | none |
| video | `["camera", "microphone"]` | no | none |

`canPublishSources` is enforced by the LiveKit server — verified against a real
server: an audio token's camera publish is never acknowledged and no camera
track appears. The client UI is not the security boundary. Screen sharing is in
neither list.

## Appointment

Every voice/video service in today's catalogue has `supports_appointment`, so a
call needs the order's appointment, in `pending` or `confirmed`
(`appointment_required`, `appointment_<status>`). An `appointment_id` in the
request must be the order's (`appointment_mismatch`). No rule is invented for
appointment-less services; if one appears, its window is creation → the hard
duration ceiling.

## The window

```
opens  = start − CALL_JOIN_EARLY_SECONDS   (600)
closes = end   + CALL_JOIN_LATE_SECONDS    (900)
```

For 14:00–14:45: joinable from 13:50 to 15:00. **Late is measured from the
end**, not the start, so somebody who drops at 14:30 can get a fresh token and
rejoin. Before: `409 call_too_early` with `opens_at`. After: `409
call_window_closed`.

Creating a call before the window is allowed and yields a `scheduled` session
with no room. The window closing ends whatever is still live.

## Tokens

* Minted by the backend; the API secret never leaves the server.
* TTL `CALL_TOKEN_TTL_SECONDS` (600), and never past the window's close.
* Room-exact, identity-exact, no name, no metadata.
* Returned only by `POST /calls/{id}/join`, with `Cache-Control: no-store`.
* Never logged — not the token, not its signature. The logger's redaction list
  also covers `join_token`, `participant_token`, `api_secret`,
  `livekit_api_secret`.
* **Token lifetime is not call duration.** LiveKit checks expiry only on the
  initial connection and refreshes a connected client's token itself.

### Reissue

`POST /calls/{id}/join` again, as often as needed (rate-limited): a token that
expired before connecting, an app restart, a new device. Every reissue repeats
the whole chain — a refunded order, a cancelled appointment, a suspended expert
or a closed window refuses a reissue exactly as it would a first request.

### Replay and devices

A token names one identity in one room for ten minutes. A stolen token lets the
thief replace the legitimate participant — LiveKit allows one connection per
identity and the newer one wins (`DUPLICATE_IDENTITY`). That is why the TTL is
short and the response is `no-store`.

Product policy: **one active presence per participant**. Switching device is
reconnecting with a fresh token as the same identity; the old connection is
dropped and the call continues. Verified against a real server.

## Suspension and account status

* **Expert suspended** → no new calls or tokens (`expert_suspended`), and every
  live call of theirs is stopped immediately — including one in progress
  (`end_reason = expert_suspended`). Suspension is a safety action; leaving a
  user in a room with somebody the platform just suspended is the wrong side to
  err on.
* **Account disabled or deleted** → no token for that account, and the other
  party gets `participant_unavailable`. Webhooks still close any call.

## Cancellation

| Event | Call not yet active | Call active |
|---|---|---|
| order cancelled | `cancelled`, `order_cancelled` | `ended`, `order_cancelled` |
| appointment cancelled | `cancelled`, `appointment_cancelled` | `ended`, `appointment_cancelled` |
| order refunded | tokens refused (`order_state_refunded`) | — |

Ending a call **never** completes the appointment or the order: a dropped call
is not a finished consultation. Completion stays a separate business action.

Refunds are not decided here. `end_reason` and `ended_by` are stored for the
refund policy that B11 will need.

## Rate limits

| Scope | Default | Key |
|---|---|---|
| `call_create` | 20/hour | user |
| `call_join_token` | 60/hour | user |
| `call_end` | 30/hour | user |
| `livekit_webhook` | 600/minute | IP — the signature is the real protection |

## Errors

| Code | Status |
|---|---|
| `call_provider_not_configured` | 503 |
| `call_provider_unavailable` | 503 |
| `call_token_failed` | 503 |
| `call_not_found` | 404 |
| `call_not_allowed` | 403 |
| `call_too_early` | 409 |
| `call_window_closed` | 409 |
| `call_already_ended` | 409 |
| `call_type_not_supported` | 422 |
| `call_participant_limit` | 409 |
| `invalid_webhook` | 401 |

`call_participant_limit` is reserved: non-members cannot reach a call at all
(404), and a third identity in a room is handled by the webhook path, not the
API.
