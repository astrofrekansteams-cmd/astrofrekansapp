# Backend Architecture

Astrofrekans is a mobile-first product: the Flutter app is a **client**, and
everything that must be correct, private or paid for lives here.

---

## 1. Layers

```
app/
  api/            HTTP only: routing, status codes, dependency wiring
    v1/           versioned routers (auth, users, astrology, health)
    deps.py       session, current user, premium gate, engine handle
  services/       use cases; the only place business rules live
    astrology/    engine, houses, aspects, transits, calendar, returns,
                  scoring, horoscope, dignities, horary, synastry,
                  composite, caching
    forecast/     forecast service, caching and API mapping
    horary/       question store, chart casting, analysis snapshots
    compatibility/ person resolution, report snapshots, caching
    auth/         registration, login, token rotation, password reset
    users/        profile, birth profiles, saved people
    geocoding/    provider protocol + mock and Nominatim implementations
    timezone/     coordinates -> IANA zone -> UTC, DST aware
  repositories/   all database queries; services never write SQL inline
  db/             engine, session factory, ORM models, portable column types
  domain/         pure dataclasses and enums - no framework imports
  core/           config, security, logging, errors, cache, rate limiting
```

Dependencies point inwards: `api → services → repositories → db`, with
`domain` at the centre depending on nothing. A service can be unit tested
without HTTP, and the engine without a database.

## 2. Request lifecycle

1. Middleware assigns a `request_id` (honouring an inbound `X-Request-Id`) and
   binds it to the logging context.
2. The route's dependencies run: rate limit, database session, `get_current_user`
   (decodes the access token, loads the user, binds the **user id** - never the
   email - to logs).
3. The handler calls a service. Services own the transaction boundary: the
   route commits once, at the end.
4. Any `AppError` becomes `{"error": {code, message, details}}` with its status
   code; anything unexpected becomes a generic 500 and a logged stack trace.
5. The completion log records method, path, status and latency. Query strings
   are never logged - they can contain place names.

## 3. Data model

UUID primary keys everywhere, `created_at` / `updated_at` on every table,
`deleted_at` where history matters (users, birth profiles, saved people).

| Table | Holds |
| --- | --- |
| `users` | credentials, provider, activity flags |
| `user_profiles` | display name, avatar, language, home timezone |
| `birth_profiles` | the user's own birth data; exactly one `is_primary` |
| `saved_people` | partner/friend/family charts for synastry and AI context |
| `refresh_tokens` | hashed tokens, session family, rotation chain |
| `password_reset_tokens` | hashed, single use |
| `subscriptions` | tier and entitlement window, written only after server-side receipt verification |
| `charts` | durable cache for charts of every kind (natal, horary, returns), keyed by input hash |
| `service_definitions` | the catalogue of everything the platform can deliver, and in which fulfillment modes |
| `forecast_snapshots` | durable cache for the expensive forecasts (monthly, annual); also what an expert reads in a hybrid consultation |
| `cosmic_events` | global sky events, cached once for everyone |
| `horary_questions` | a question with the instant and place it was asked - the chart itself |
| `horary_analyses` | the structured analysis of a question, snapshotted with its rule versions |
| `compatibility_reports` | synastry / composite / Davison results, frozen at the moment they were run |

Later phases add `ai_conversations`, `ai_messages`, `tarot_readings`,
`rune_readings`, `katina_readings`, `transit_cache`, `service_orders`,
`experts`, `expert_services`, `expert_availability`, `appointments`,
`reviews`, `favorites`, `conversations`, `conversation_messages`,
`media_attachments`, `call_sessions`, `payments`, `expert_payouts`,
`notification_preferences`.

The platform is not only automated: every service can be delivered by the
engine, by a real astrologer, or as a hybrid of both. That distinction and the
marketplace design it implies are specified in
[`platform_architecture.md`](platform_architecture.md).

Timestamps use a `UtcDateTime` column type that guarantees timezone-aware UTC
in Python on both Postgres and SQLite, so comparisons cannot mix naive and
aware values.

## 4. Authentication

* **Argon2id** password hashing (argon2-cffi defaults), with transparent
  rehashing when parameters change. Plaintext passwords are never stored,
  logged or returned.
* **Access token**: JWT, 15 minutes, signed with `JWT_SECRET`.
* **Refresh token**: JWT with a separate secret and a random nonce, 30 days,
  stored only as a SHA-256 digest, **rotated on every use**.
* **Reuse detection**: presenting an already-rotated refresh token revokes the
  entire session family immediately (and commits that revocation before
  raising, so the attacker's and the victim's tokens both die).
* Changing or resetting a password revokes every session.
* `forgot-password` answers identically for known and unknown addresses, and
  the token never travels in the response body.

Social sign-in (Google, Apple) arrived in B9 through Firebase Auth rather than
a hand-rolled OAuth flow. `AUTH_MODE=hybrid` accepts **both** the JWTs above and
a Firebase ID token as the bearer token, so existing accounts keep working
unchanged and no backend JWT is minted for a Firebase session - wrapping one
token in another would mean two lifetimes and two revocation stories.

`users.firebase_uid` (nullable, unique) maps a verified credential to a local
account. Postgres still owns the account; Firebase owns the credential. Adopting
an existing account because a token carries a matching email address is off by
default, because it is an account-takeover primitive: the safe path is to sign in
and link from inside the session. See
[`firebase_auth.md`](firebase_auth.md).

## 5. Caching and rate limiting

Redis, with an in-process fallback so a Redis outage degrades rather than
fails. Cached: natal charts (30 days), moon phase (1 hour), geocoding results
(30 days), transits (6 h - 14 d by range), daily frequency (6 h), horoscopes,
cosmic calendar (30 days) and forecasts. Every forecast key carries the chart
fingerprint plus the engine, orb-policy and scoring versions, so new birth data
or a changed weight retires the affected entries without an invalidation sweep
(see [`transit_engine.md`](transit_engine.md)). Rate limits are fixed windows keyed by user id when authenticated
and by proxy-aware IP otherwise: login 10/min, register 5/min, refresh 60/h,
password reset 5-10/h, geocode 60/h.

## 6. Configuration and secrets

All settings come from the environment through `pydantic-settings`.
`assert_production_ready()` refuses to boot a production instance with
development JWT secrets, `DEBUG=true`, an empty CORS list, a plaintext
`ws://` LiveKit URL, or a test double in place of a real provider
(`AI_PROVIDER=fake`, `FIREBASE_PROVIDER=fake`, `REALTIME_PROVIDER=fake`). `.env`
is git-ignored, along with anything service-account-shaped; API keys for AI
providers and the Firebase service account live only in the server environment,
so a decompiled APK contains nothing worth stealing.

A missing credential is a degraded feature set, never a broken backend. Without
an OpenAI key the AI routes answer `ai_not_configured`; without a Firebase
service account chat, presence, attachments and push answer
`firebase_not_configured` (503) and everything else is unaffected. Both say so at
boot, and `GET /auth/capabilities` says so to the client.

## 7. Logging

`structlog`, JSON outside local development, with `request_id` and `user_id`
bound per request. A redaction processor drops passwords, tokens, emails,
birth details and AI message content by key name - an astrology app holds
unusually sensitive personal data, and a log aggregator is not the place for
it.

## 8. Errors

One envelope, always:

```json
{"error": {"code": "birth_profile_missing", "message": "…", "details": {}}}
```

Codes are stable strings the client can branch on. Validation failures list
the offending fields in `details.fields`. Internal errors never leak stack
traces or SQL.

## 9. Deployment

`docker compose` runs `postgres`, `redis`, `api` and three optional workers:
`ai-worker` (`python -m app.workers.ai_report_worker`),
`notification-worker` (`python -m app.workers.notification_worker`) and
`call-worker` (`python -m app.workers.call_worker`). All are optional in the
same way - without them the queued work waits and nothing else
breaks - and both scale horizontally, because each claims rows with
`SELECT ... FOR UPDATE SKIP LOCKED` rather than polling for whatever it can see.

The API image is multi-stage-friendly, runs as a non-root user, bakes in the
ephemeris kernel, applies migrations on start and exposes a `curl`-based
healthcheck. Migrations belong to one process, and that process is the API.
`/health` is the liveness probe; `/ready` checks database, cache and ephemeris
and returns 503 when the service cannot actually serve.

## 10. Phase map

See [`platform_architecture.md`](platform_architecture.md) for the full phase
table. B1-B10 are done: the astrology and horary engines, compatibility,
Astro AI, divination, the expert marketplace, the Firebase layer (auth, chat,
presence, attachments, push) and LiveKit voice and video calls. B11 (payments,
store billing, marketplace settlement) is next.

Phase documents worth reading alongside this one:
[`ai_architecture.md`](ai_architecture.md),
[`divination_architecture.md`](divination_architecture.md),
[`marketplace_architecture.md`](marketplace_architecture.md),
[`firebase_backend.md`](firebase_backend.md),
[`chat_architecture.md`](chat_architecture.md),
[`presence.md`](presence.md),
[`media_attachments.md`](media_attachments.md),
[`push_notifications.md`](push_notifications.md),
[`call_architecture.md`](call_architecture.md),
[`livekit_webhooks.md`](livekit_webhooks.md).
