# B13A live service matrix

Date: 2026-09-25. Evidence is what was run in this phase; nothing is marked
live-tested on the strength of a fake provider or a mock.

**No production or staging credentials exist in this environment** (no
Firebase service account, no APNs key, no production LiveKit, empty
`OPENAI_API_KEY`, no App Store Connect key, no Play Console service account,
no external PSP). None were created or invented.

| SERVICE | CONFIGURED | LIVE TESTED | RESULT | BLOCKER |
| --- | --- | --- | --- | --- |
| PostgreSQL 17 (local Docker) | yes | yes (local) | `/ready` database ok; alembic head `0014_call_delivery_lease`; `alembic check` no drift | production DB not provisioned |
| Redis 8 (local Docker) | yes | yes (local) | `/ready` cache ok | production Redis not provisioned |
| Backend API (Docker, rebuilt from current code) | yes | yes (local) | `/health` 200, `/ready` 200; smokes: ai, worker, chat, calls, billing, marketplace PASS | - |
| ai-worker | yes | yes (local) | starts; `ai_worker_idle_unconfigured`, 0 restarts | OpenAI key |
| notification-worker | yes | yes (local) | starts; `notification_worker_idle_unconfigured` (neither Firebase nor APNs) | Firebase / APNs credentials |
| call-worker | yes | yes (local) | starts; `call_worker_idle_unconfigured` | LiveKit credentials |
| Firebase Admin / Auth | no | no | endpoints answer `firebase_not_configured`; unit tests cover valid/expired/revoked/new/linked/link-required with the fake | **service account + project** |
| Firestore | no | no | rules file present; not deployed/tested live | service account; emulator needs Java 21 |
| Realtime Database (presence) | no | no | frozen schema unchanged; backfill command exits 2 `firebase_not_configured` (host and container) | service account + `FIREBASE_DATABASE_URL`; emulator needs Java 21 |
| Firebase Storage | no | no | not tested live | service account + bucket |
| FCM | no | no | provider acceptance not tested (no credentials); call contract covered by unit tests | service account + Android test device |
| Firebase Emulator (rules tests) | CLI 15.22.4 present | no | refused: "firebase-tools no longer supports Java version before 21" (Java 17.0.20 installed) | **Java 21** (not installed - system change not made) |
| APNs PushKit VoIP | no | no | `apns_configured=false`; real HTTP/2 provider covered by `httpx.MockTransport` + JWT test only | **.p8 key, Team ID, Key ID, bundle id, signed iOS build** |
| LiveKit (production/staging) | no | no | `/calls/status` not configured; B10 local LiveKit 1.13.7 E2E (25/25) remains the only live evidence | **LiveKit URL/keys, webhook, TURN** |
| OpenAI | no (key empty) | no | `scripts/live_openai_smoke.py` → "SKIPPED: OPENAI_API_KEY is not set" | **OpenAI key** |
| Paid reports | yes (logic) | local only | bypass closed (unit + real Postgres concurrency, earlier phase); smoke: natal without credit → 402 on configured path only | OpenAI key for live generation; real store credit |
| App Store Server API / Notifications V2 | no | no | `billing/status` apple false; library path covered with a throwaway root | **App Store Connect key, issuer, root certs** |
| Google Play Developer API / RTDN | no | no | `billing/status` google false | **Play service account, Pub/Sub push** |
| External expert payment (PSP) | no (`disabled`) | no | NOT CONFIGURED by design (no provider chosen); fake refused in production | provider decision |
| Secrets in repository | - | yes | 0 tracked files (no commits); committable-file scan: no keys, private keys or service accounts; `.gitignore` gaps closed | - |
