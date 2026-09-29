# B13A production services validation

Date: 2026-09-25. Scope: connect and validate real production services, close
release blockers with evidence. No feature work, no Flutter change.

**Headline:** the backend is release-ready as code; the environment is not.
No production/staging credentials for Firebase, APNs, LiveKit, OpenAI, App
Store Connect, Google Play or a PSP exist here, and none were created. Every
live service is therefore **NOT VERIFIED**; what could be proven locally was.
See [b13a_live_service_matrix.md](b13a_live_service_matrix.md) and
[b13a_backend_release_blockers.md](b13a_backend_release_blockers.md).

## Baseline

| Check | Result |
| --- | --- |
| git | branch `master`, **no commits**, 0 tracked files, 31 untracked top-level entries |
| alembic | current = head = `0014_call_delivery_lease`; `alembic check`: no new upgrade operations |
| pytest | **811 passed, 0 failed, 0 skipped** (13 min) |
| docker compose | `config -q` OK; services postgres, redis, api, notification-worker, ai-worker, call-worker |

The running containers were 27-34 hours old - built before the paid-report
and call-delivery hardening. Images were rebuilt from current code and the
backend services restarted (Postgres/Redis data untouched).

## Configuration audit (presence only, never values)

Configured: `ENVIRONMENT` (local), `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`,
`JWT_REFRESH_SECRET`, `AI_PROVIDER` (openai).

Not configured: every Firebase key, every APNs key, every LiveKit key,
`OPENAI_API_KEY` (empty), every Apple and Google store key,
`EXTERNAL_PAYMENT_PROVIDER` (default `disabled`), `STORE_PRODUCT_IDS`.

Production-readiness dry run (`Settings(environment="production")`): refused
with `CORS_ORIGINS must list the allowed origins` (host `.env` additionally
`DEBUG must be false`). It correctly does not demand optional providers -
their absence is a degraded mode, which is exactly why they are listed as
release blockers instead.

### Required production environment

| Group | Variables | State |
| --- | --- | --- |
| Core | `ENVIRONMENT=production`, `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `JWT_REFRESH_SECRET`, `CORS_ORIGINS`, `DEBUG=false` | DB/Redis/JWT set (local); **CORS missing** |
| Firebase | `FIREBASE_PROJECT_ID`, `FIREBASE_CREDENTIALS_JSON` or `_PATH`, `FIREBASE_STORAGE_BUCKET`, `FIREBASE_DATABASE_URL`, `AUTH_MODE` | **missing** |
| LiveKit | `REALTIME_PROVIDER=livekit`, `LIVEKIT_URL` (wss://), `LIVEKIT_API_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, webhook key | **missing** |
| Call timing | `CALL_RING_TIMEOUT_SECONDS` 60, `CALL_PUSH_LEASE_SECONDS` 15, `CALL_PUSH_SEND_TIMEOUT_SECONDS` 8, `APNS_TIMEOUT_SECONDS` 8 | defaults valid |
| APNs VoIP | `APNS_TEAM_ID`, `APNS_KEY_ID`, `APNS_PRIVATE_KEY` or `_PATH`, `APNS_BUNDLE_ID`, `APNS_ENVIRONMENT` | **missing** |
| OpenAI | `AI_PROVIDER=openai`, `OPENAI_API_KEY` | **key missing** |
| Apple | `APPLE_BUNDLE_ID`, `APPLE_APP_APPLE_ID`, `APPLE_ISSUER_ID`, `APPLE_KEY_ID`, `APPLE_PRIVATE_KEY` or `_PATH`, `APPLE_ROOT_CERTIFICATES_PATH`, `APPLE_ENVIRONMENT` | **missing** |
| Google Play | `GOOGLE_PLAY_PACKAGE_NAME`, `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` or `_PATH`, `GOOGLE_PUBSUB_PUSH_AUDIENCE`, `GOOGLE_PUBSUB_PUSH_SERVICE_ACCOUNT` | **missing** |
| Store catalogue | `STORE_PRODUCT_IDS` | **missing** |
| External payment | `EXTERNAL_PAYMENT_PROVIDER` | `disabled` (no provider chosen) |
| Product decisions | `PAID_REPORTS_INCLUDED_IN_PREMIUM`, `EXPERT_SETTLEMENT_HOLD_DAYS`, premium AI quotas | defaults (fail closed / unset) |

## Services

**Firebase (Auth, Firestore, RTDB, Storage, FCM)** - not configured; NOT
VERIFIED live. Endpoints answer `firebase_not_configured` and the smoke
confirms the rest of the API is unaffected. Token handling (valid, expired
vs revoked, new account, linked account, link-required, unverified email,
no raw token logged) is covered by `tests/test_firebase_auth.py` with the
fake provider - not a live proof.

**Firebase Emulator** - CLI 15.22.4 present; Java 17.0.20 installed. The
emulator refuses: "firebase-tools no longer supports Java version before 21".
JDK was not installed (system change left to the operator). No rules test
suite exists yet. **Blocker.**

**Presence** - frozen schema `presenceVisibility/{targetUid}/{readerUid}/{conversationId}`
and policy (ACTIVE/READ_ONLY allowed, SUSPENDED/CLOSED denied) unchanged.
`python -m scripts.rebuild_presence_visibility --dry-run` on host and inside
the API container: `{"error": "firebase_not_configured"}`, exit 2 - the
controlled refusal. No rebuild, no prune (no Firebase, no production data).

**APNs VoIP** - not configured (`apns_configured=false`); no live send. The
HTTP/2 provider is covered only by a `httpx.MockTransport` test that checks
headers, topic, host and the ES256 JWT. NOT VERIFIED.

**Call delivery reliability** - production defaults hold the invariant: send
timeout 8 s < call lease 15 s < ring 60 s (APNs httpx timeout 8 s; generic
push lease 120 s unchanged), read from the rebuilt container. Enforced at
startup. At-least-once with `call_id` + `event_version` client dedupe - not
redesigned.

**LiveKit** - no production/staging server; NOT VERIFIED. The only live
evidence remains B10's local LiveKit 1.13.7 E2E (25/25). It was not re-run:
it needs the API reconfigured against a local LiveKit, and a local server is
not what this phase validates. `smoke_calls` PASS (not-configured path). TURN:
not configured.

**OpenAI** - `OPENAI_API_KEY` empty. `scripts/live_openai_smoke.py` →
"SKIPPED: OPENAI_API_KEY is not set". Luna, Terra (structured, streaming),
Sol, AZ: NOT VERIFIED. `smoke_ai` PASS on the not-configured path.

**Paid reports** - security not redesigned. Bypass closed (unit tests and the
real-Postgres concurrency check from the enforcement phase; still in the
811). Live generation NOT VERIFIED (no key); no real store credit.

**Apple / Google** - not configured; Server API, Notifications V2, sandbox
transaction, Developer API, RTDN, license-test purchase: NOT VERIFIED.
`smoke_billing` PASS (booleans false, verify/webhooks 503, entitlements
readable).

**External expert payment** - `disabled`, no provider chosen: NOT CONFIGURED.
The fake is refused in production.

## Workers

Rebuilt and started: `ai-worker`, `notification-worker`, `call-worker` all
`running`, 0 restarts, each logging `*_idle_unconfigured` - the controlled
degraded state, queue untouched. Lease recovery on crash/restart is covered by
the suite (`test_graceful_shutdown_requeues_the_job_in_hand`, call delivery
reliability and fast-lease tests, Postgres scripts in earlier phases).
Configured-branch consumption: NOT VERIFIED (no providers).

## Docker smoke (rebuilt images, not-configured branch)

| Script | Result |
| --- | --- |
| `smoke_ai.sh` | SMOKE OK (configured=false) |
| `smoke_worker.sh` | WORKER SMOKE OK (unconfigured) |
| `smoke_chat.sh` | PASS |
| `smoke_calls.sh` | PASS |
| `smoke_billing.sh` | PASS |
| `smoke_marketplace.sh` | MARKETPLACE SMOKE OK |
| `smoke_divination.sh` | stops at interpretation with `ai_not_configured` - expected: this script requires a configured AI provider; the draw steps ran |

The first run of several smokes back to back hit `429 rate_limited`
(`register` 5/minute per IP) - the limiter working; re-run spaced 65 s apart.

## Secrets audit

* Tracked files: **0** (no commits).
* Committable (non-ignored) files scanned for OpenAI-style keys, PEM private
  keys, service-account JSON, filled secret env lines, `.p8`/`AuthKey_`/
  service-account file names: **none present**. One false positive
  (`docs/livekit_backend.md` shows an empty `LIVEKIT_API_SECRET=` placeholder).
* `backend/.env` ignored. Gaps found and closed in `.gitignore`: root `.env`,
  `**/.env.*` (template `.env.example` kept), `backend/secrets/`, `**/*.pem`,
  `**/*.key`. Committable file count unchanged (1293) - nothing legitimate
  was excluded.
* OpenAI key, Firebase Admin JSON, APNs .p8, Apple key, Google service
  account, LiveKit secret, PSP secret: **not present** in the working tree.

## Database

Head `0014_call_delivery_lease`, all migrations 0001-0014 applied on the dev
database; `alembic check` clean. No production/staging database exists; no
downgrade was run anywhere.

## Security regression (all in the 811)

| Property | Evidence |
| --- | --- |
| Paid-report direct bypass closed | `test_a_direct_request_without_a_credit_gets_nothing`, `test_an_unpaid_cached_report_does_not_bypass_payment`, `test_a_client_cannot_claim_premium` |
| Firebase auth | `test_expired_and_revoked_tokens_are_distinguished`, `test_an_invalid_token_says_nothing_about_why`, `test_an_unverified_email_never_links_even_when_enabled`, `test_linking_from_inside_a_session_is_the_safe_path` |
| Conversation IDOR | `test_a_stranger_cannot_reach_the_conversation`, `test_another_expert_is_not_a_member`, `test_another_users_conversation_is_not_found` |
| Attachment IDOR | `test_an_attachment_cannot_be_replayed_into_another_conversation`, `test_another_member_cannot_finalise_your_upload` |
| Call IDOR / LiveKit token | `test_a_stranger_cannot_open_a_call_on_someone_elses_order`, `test_a_video_token_is_least_privilege`, `test_the_token_is_short_lived_and_not_cached`, `test_production_refuses_plaintext_livekit` |
| Purchase ownership | `test_another_account_cannot_take_a_purchase`, `test_a_purchase_stamped_for_another_account_is_refused`, `test_google_ownership_and_product_are_checked` |
| consumer_ref ownership | `test_a_reference_is_scoped_to_its_account`, `test_a_source_the_caller_does_not_own_is_refused_before_payment` |
| Push token privacy | `test_a_push_token_is_never_logged`, `test_another_user_cannot_delete_your_device` |
| VoIP token privacy | `test_voip_registration_is_owned_and_never_echoed`, `test_voip_and_fcm_tokens_are_never_interchangeable` |

These are regression proofs with fakes, not live-service proofs.

## Changes made in this phase

* `.gitignore`: env files, secrets directory, PEM/key files (above).
* Docker images rebuilt; backend services restarted.
* Reports: this file, the matrix, the blockers.
* No backend source, migration or Flutter file changed.
