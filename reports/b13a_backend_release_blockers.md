# B13A backend release blockers

Date: 2026-09-25. Backend code is not blocking: the full suite passes and the
degraded (unconfigured) deployment behaves as designed. What blocks a
production release is **configuration and credentials that do not exist in
this environment**, and live verification that therefore could not happen.

## P0 - release cannot ship without these

| # | Blocker | Why | What closes it |
| --- | --- | --- | --- |
| 1 | No Firebase project credentials | Auth (Firebase ID tokens), chat, presence, attachments and all push depend on it; today they answer `firebase_not_configured` | `FIREBASE_PROJECT_ID`, `FIREBASE_CREDENTIALS_JSON` (secret store), `FIREBASE_STORAGE_BUCKET`, `FIREBASE_DATABASE_URL`; deploy `firebase/*.rules`; then live Auth/Firestore/RTDB/Storage/FCM checks |
| 2 | Firebase rules never executed | `firestore.rules`, `database.rules.json`, `storage.rules` are unit-reasoned only; the emulator refuses to start on Java 17 | Install JDK 21 (operator decision; not changed here), add an emulator rules suite, run it |
| 3 | No LiveKit production/staging | Voice/video calls unavailable (`calls not configured`) | `LIVEKIT_URL` (wss://), `LIVEKIT_API_URL`, API key/secret, webhook key; server-side smoke (room, token, join, webhooks, leave, finish); TURN reachability |
| 4 | No OpenAI key | Astro AI chat and every report answer `ai_not_configured`; paid reports cannot be delivered | `OPENAI_API_KEY` (secret store); run `scripts/live_openai_smoke.py` (Luna, Terra structured + stream, Sol, AZ) |
| 5 | No store credentials | No purchase, subscription or credit can be verified; paid features unreachable | Apple: bundle id, App Apple ID, issuer/key id/.p8, root certificates → Server API + Notifications V2 in sandbox. Google: package, service account, Pub/Sub push audience/account → Developer API + RTDN. Then real sandbox/license-test purchases |
| 6 | `CORS_ORIGINS` empty | `assert_production_ready` refuses to boot in production | Set the allowed origins |
| 7a | **Firebase project on Spark plan - Storage BLOCKED** (operator decision, B13C setup, 2026-09-25) | Cloud Storage for Firebase requires the Blaze plan (in effect since 2026-02-03, per Firebase's official FAQ). Chat attachments (intent → upload → finalize) cannot work; the backend answers `firebase_not_configured` for them | Upgrade the project to Blaze before release, create the default bucket (`<project-id>.firebasestorage.app`), set `FIREBASE_STORAGE_BUCKET`, deploy `storage.rules`, run the live attachment checks |
| 7c | ~~Android Google sign-in: no SHA fingerprint~~ **CLOSED 2026-09-25** | Debug SHA-1/SHA-256 (from `gradlew :app:signingReport`) registered; refreshed `google-services.json` has an Android OAuth client (type 1) bound to the debug SHA-1 | Release / Play App Signing SHAs still to add at the signing stage |
| 7d | ~~Firebase CLI on the wrong account~~ **CLOSED 2026-09-25** | `astrofrekans-staging` visible; `firebase/.firebaserc` has only `staging` (no default, no production) | - |
| 3a | **LiveKit webhooks not live** (B13C step 4, 2026-09-25) | LiveKit Cloud staging is configured and live-tested server-side, but webhooks need a publicly reachable HTTPS backend; the backend runs on localhost. Without webhooks the call lifecycle (RINGING/ACTIVE/ENDED from joins and leaves) and the intruder-removal defence are not driven in staging | Deploy the backend behind public HTTPS; add `https://<host>/api/v1/webhooks/livekit` in LiveKit Cloud → Settings → Webhooks with the backend's API key as the signing key; verify a signed event end to end |
| 3b | **LiveKit Cloud did not enforce `max_participants=2`** (observed 2026-09-25) | A third, separately minted token joined a room created with `max_participants=2` (server reported max 2, counted 3). The backend's contract still holds: it mints tokens only for the call's two members (fixed opaque identities), and an unknown identity is removed via webhook (`intruder`) - removal verified live on Cloud. But that removal needs blocker 3a | Close 3a; optionally ask LiveKit support whether `max_participants` applies to tokens issued before the limit was reached |
| 5b | **Apple commercial agreements deferred** (operator decision, B13C step 5, 2026-09-26) | Paid Apps Agreement = NEW / NOT ACTIVE; Tax = NOT COMPLETED; Banking = NOT COMPLETED (legal entity update required first); EU DSA trader status = NOT COMPLETED (Apple requires a declaration even without EU distribution). No subscription or paid-report credit can be sold, and StoreKit sandbox purchase tests depend on it | Before release: update legal entity info → accept Paid Apps Agreement → tax → banking → Active; declare DSA trader status (operator decision; as a trader, an individual's address/phone/email are shown on the EU storefront) |
| 5a | **Sign in with Apple not ready** (B13C step 5, 2026-09-25) | The Flutter app ships an Apple sign-in button (`AppleAuthProvider`) and Google sign-in is enabled. App Store Review Guideline 4.8 requires an equivalent privacy-preserving login (Sign in with Apple qualifies) when a third-party login such as Google is offered. The Apple provider is not enabled in Firebase, the capability is not on the App ID, and the flow was never verified end to end | Before App Store submission: enable the Sign In with Apple capability on `com.astrofrekans.astrofrekans`, configure the Apple provider in Firebase (Services ID / key as Firebase requires), add the entitlement at signing, verify on a device - or remove Google sign-in on iOS |
| 7b | ~~`firebase/database.rules.json` does not load~~ **CLOSED 2026-09-25** | Comment keys removed programmatically (rules semantics hash unchanged); emulator loads it; 16/16 emulator rules tests; deployed to staging and read back identical | - |

## P1 - required for the call experience on devices

| # | Blocker | Impact | What closes it |
| --- | --- | --- | --- |
| 7 | ~~No APNs VoIP credentials~~ **CONFIGURED 2026-09-26** (B13C step 6) | Token key AYGBJ7SNHN (Sandbox & Production, Team Scoped) in backend/secrets; APNs provider auth accepted live (400 BadDeviceToken to a made-up token, production and sandbox, host and notification-worker) | Remaining: real VoIP delivery + CallKit on a signed iPhone build (B13C device phase); upload the same key to Firebase Cloud Messaging for ordinary iOS notifications |
| 8 | No live FCM / device validation | Android data-only HIGH call pushes, TTL and collapse unverified on a device | Firebase (1) + Android test device - B13B |

## P2 - product decisions pending (not bugs)

* External expert payment provider not chosen (`EXTERNAL_PAYMENT_PROVIDER=disabled`); priced live consultations cannot be paid.
* `PAID_REPORTS_INCLUDED_IN_PREMIUM` (default `false`), `EXPERT_SETTLEMENT_HOLD_DAYS` (unset), premium AI quotas (unset).

## Closed in this phase

* `.gitignore`: a root `.env`, `.env.*` variants, `backend/secrets/`, `*.pem` and `*.key` were not ignored. Added (template `.env.example` still committed). No secret was present.
* Docker images were ~27-34 h old (pre paid-report and call-delivery hardening); rebuilt and smoke-tested against current code.

## Not blockers

* Production readiness check refuses fakes (AI, Firebase, realtime, store, APNs, external payment) - verified by tests.
* Call push timing invariant holds with production defaults: send timeout 8 s < lease 15 s < ring 60 s; generic push lease 120 s unchanged.
