# LiveKit in the backend

> **FastAPI decides who may join. LiveKit carries the media.**

No audio or video ever passes through FastAPI. The backend authorises, mints a
short-lived join token, and listens to LiveKit's webhooks to learn who is
actually in the room. Postgres holds the call's lifecycle and audit trail;
LiveKit holds the room.

## SDK

`livekit-api==1.2.1` (with `livekit-protocol` 1.1.27), verified by reading the
installed source rather than recalling the API. The facts that shaped the
implementation:

| Fact (from the SDK source) | Consequence |
|---|---|
| `AccessToken` defaults to a **6 hour** TTL | every token sets its own, 10 minutes by default |
| `VideoGrants.can_publish_data` defaults to **True** | set to False explicitly — no chat over the data channel |
| `can_publish_sources` supersedes `can_publish`; values `camera`, `microphone`, `screen_share`, `screen_share_audio` | audio calls get `["microphone"]` and genuinely cannot publish a camera |
| token expiry is checked on the **initial connection only**; LiveKit refreshes tokens for connected clients | token TTL is join authorisation, not call duration |
| a second connection with the same identity replaces the first (`DUPLICATE_IDENTITY`) | one identity = one presence; a device switch is not a hang-up |
| webhooks carry a JWT from our API key whose `sha256` claim is the body's digest | verification needs the raw body, byte for byte |
| the server API client converts `ws(s)://` to `http(s)://` | one `LIVEKIT_URL`; `LIVEKIT_API_URL` only when the backend reaches LiveKit by another address |
| `RoomService` errors are `ServerError` (with a twirp code) or `aiohttp.ClientError` | both become `call_provider_unavailable`; the provider's message never leaves the adapter |

## The provider seam

`RealtimeCommunicationProvider` in `app/services/calls/provider.py`:

```
create_room · delete_room · get_room · list_participants · remove_participant
create_participant_token · parse_webhook · close
```

Nothing outside `app/services/calls/` imports a LiveKit type. Routes and the
lifecycle speak in small dataclasses (`RoomSpec`, `TokenRequest`, `JoinToken`,
`ProviderWebhookEvent`...), so an Agora or Twilio implementation is a new class,
not a rewrite of the call domain.

`FakeRealtimeCommunicationProvider` simulates rooms in memory — but mints tokens
and verifies webhook signatures with **LiveKit's real SDK code** and a test key
pair. So the tests that inspect grants inspect real LiveKit JWTs, and the tests
that forge webhooks attack LiveKit's real verifier.

## Configuration

```
LIVEKIT_URL=            # what clients connect to (wss:// in production)
LIVEKIT_API_URL=        # optional: where the backend reaches the server API
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=     # signs tokens, verifies webhooks. Never logged, never returned.
REALTIME_PROVIDER=livekit
```

Plus the call tunables — see [call_lifecycle.md](call_lifecycle.md).

**Without credentials the backend boots.** `/health` and `/ready` stay green,
everything else works, and call routes answer `503 call_provider_not_configured`.
The boot diagnostic names the missing variables by *name*. `GET /calls/status`
returns only `{"configured", "provider"}` — never a URL, key or secret.

`assert_production_ready` refuses `REALTIME_PROVIDER=fake` and a non-`wss://`
`LIVEKIT_URL`.

## Rooms

* Name: `call_<24 random hex>`. Not derived from anybody, any order or any
  service.
* `max_participants=2`, no metadata, no egress.
* Created when the call's window is open; re-created on the next join if
  LiveKit closed it (empty timeout) while the call is still live.
* Deleted when the call reaches a terminal state.

Recommended server setting: **`room.auto_create: false`**. LiveKit otherwise
creates a room when somebody joins it — so a leftover token, still inside its
TTL, could bring back a room we deleted. With it off, a room exists only
because the backend created it. The backend also defends without it: a join
into a finished call is removed and the room deleted again.

## Local end-to-end

```bash
docker compose --profile livekit up -d livekit
```

`livekit/livekit-server:v1.13.7`, not in the default stack. Its key pair comes
from your `.env` (`LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`) through
`LIVEKIT_CONFIG` — nothing is committed — and it signs webhooks to
`http://api:8000/api/v1/webhooks/livekit` with the same pair. Then:

```bash
python -m scripts.e2e_livekit_prepare setup > e2e.json   # backend venv
.e2e/Scripts/python scripts/e2e_livekit.py e2e.json      # a venv with `pip install livekit`
python -m scripts.e2e_livekit_prepare cleanup
```

The driver checks 25 things against the real server; see
[call_architecture.md](call_architecture.md#what-has-been-verified).

## Related

* [call_architecture.md](call_architecture.md) — the shape of the whole thing
* [call_authorization.md](call_authorization.md) — who may join, when
* [call_lifecycle.md](call_lifecycle.md) — the state machine and the clock
* [livekit_webhooks.md](livekit_webhooks.md) — verification, idempotency, reconciliation
