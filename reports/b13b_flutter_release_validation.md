# B13B Flutter / device / store validation — 2026-09-25

**Release recommendation: NOT READY FOR SUBMISSION.** This is a host-side Flutter contract and release-gate audit, not a native build, physical-device test, store sandbox run or deployment sign-off. No store submission or Git commit was made. Backend source and assets modified: **0 / 0**. B13A backend state (`b13a_production_services.md`, `b13a_live_service_matrix.md`, `b13a_backend_release_blockers.md`) is the backend source of truth; the earlier 811/0 backend result was **not rerun** here.

## Baseline and final host checks

| Check | B13B baseline | Final | Boundary |
| --- | --- | --- | --- |
| `git status --short --branch` | `master`, no commits, repository untracked | Same | No baseline commit/diff available; manual change manifest |
| `flutter --version` / `dart --version` | Flutter 3.44.4 / Dart 3.12.2 | Same | Windows 11 host |
| `flutter doctor -v` | Android SDK absent; Windows/Chrome/Edge only; no physical phone | Same | No Android compile; Windows cannot run Xcode |
| `flutter analyze` | No issues | No issues | Dart/Flutter static analysis only |
| `flutter test` | 134 passed, 2 skipped | **141 passed, 2 skipped** | Host fake/contract/widget tests, not Firebase/store/native/device |
| Changed-Dart `dart format --output=none --set-exit-if-changed` | — | 8 files checked, 0 changes | No repo-wide formatter |
| `codemagic.yaml` syntax | — | Python YAML parser: both workflows load | No Codemagic remote run |

## Flutter contract and release hardening

- B13A paid reports now use `POST /ai/reports` with a random opaque, secure-store-persisted `consumer_ref` scoped to user/report/source/locale. No Flutter `POST /billing/credits/consume` follows report creation. A network failure or 202 replays the same reference, including if the backend already reserved the last credit; 200 clears it, while `409 report_credit_conflict` / `report_credit_unavailable` clear it for a fresh attempt. 200 opens the report and 202 opens existing job polling. 402/409 have typed UI messages. Backend duplicate protection itself is B13A's responsibility, not live-retested here.
- Generic report-job UI no longer offers the paid natal/yearly types without a `consumer_ref`; the backend still enforces the gate. Sinastry requires a source and remains visibly unavailable in this UI until source selection is connected; no fake paid flow.
- B13A's optional `PAID_REPORTS_INCLUDED_IN_PREMIUM=true` is **not** part of this release candidate: Flutter currently requires a report credit in this section. Leave the backend flag at its default `false`; if product enables it, align Flutter to `entitlements.capabilities.premium_reports` and test the no-credit path first. This conditional gap is tracked in `mobile_release_blockers.md`.
- Apple and Google fake purchased callbacks with inactive backend entitlement remain FREE/LOCKED. Active backend entitlement unlocks in host tests. Store sandbox/device proof is absent.
- `AppEnvironment.validate` rejects mock source in production or any release build; production API mode requires HTTPS and rejects loopback. Both Codemagic release workflows explicitly pass `APP_DATA_SOURCE=api`, production environment, selected `AUTH_MODE`, HTTPS `API_BASE_URL` and disabled debug tools. A real URL and backend `CORS_ORIGINS` are still missing.
- Codemagic workflows now gate on Flutter analyze/test plus Android `:app:testDebugUnitTest` and iOS `Runner` XCTest on an available simulator, then sign/build AAB/IPA. They require real Firebase config and signing material and have no auto-submit step. YAML parsing is **not** a remote build or native test result.
- Android manifest source has a `tools:node="remove"` entry for FlutterFire's original messaging service and registers `AstroCallMessagingService` as the intended sole `MESSAGING_EVENT` service. The merged manifest was **not generated** because Android SDK is absent; duplicate-service absence in the final build is **NOT VERIFIED**.

## Platform and service status

| Area | Status | Evidence / missing requirement |
| --- | --- | --- |
| Firebase Android/iOS configs | NOT VERIFIED | `android/app/google-services.json`, `ios/Runner/GoogleService-Info.plist`, `lib/firebase_options.dart` absent; no fake file generated |
| Firebase initialization, Auth/ID token→FastAPI, Firestore chat/listener/direct-write denial, RTDB partner/unrelated ACL, Storage intent/upload/finalize | NOT VERIFIED | No project/client config or backend credentials. B9 `presenceVisibility/{targetUid}/{readerUid}/{conversationId}` and ACTIVE/READ_ONLY allow, SUSPENDED/CLOSED deny remain unchanged; Flutter does not compute presence ACL |
| Firebase emulator Firestore/RTDB/Storage rules | NOT VERIFIED | Firebase CLI 15.22.4; only Java 17.0.20 found in controlled locations. Java 21/harness not available; system Java not changed |
| Android SDK/debug APK/Kotlin compile/native JUnit | NOT VERIFIED | SDK paths and `ANDROID_HOME`/`ANDROID_SDK_ROOT` absent; no `flutter build apk --debug` or Gradle task run |
| Android signing/release AAB | NOT VERIFIED | Keystore/signing inputs absent; `build/app/outputs/bundle/release` absent |
| iOS Codemagic/native Swift compile/RunnerTests/signing/IPA | NOT VERIFIED | Windows host, no macOS run or Apple signing/profile; `build/ios/ipa` absent. YAML syntax only is PARTIAL config validation |
| FCM Android foreground/background/killed, call incoming/cancel/missed, version and full-screen policy | NOT VERIFIED | Firebase/server credentials and physical Android absent; existing Dart fake tests do not prove data-only HIGH delivery or OS behavior |
| APNs VoIP token/backend registration/PushKit/CallKit duplicate/answer/decline/audio | NOT VERIFIED | B13A APNs unconfigured; no signed iPhone or Swift compile/device run |
| LiveKit Android/iPhone, TURN, reconnect, duplicate identity, Bluetooth | NOT VERIFIED | B13A production/staging LiveKit unconfigured; no physical device/network matrix |
| OpenAI chat/stream/reports/paid report | NOT VERIFIED live | B13A key absent; Flutter report wire contract covered by fake tests only |
| Apple Store products/sandbox verification/entitlement/restore/refund | NOT VERIFIED live | App Store Connect, sandbox users, backend credentials, signed IPA absent; host Premium lock regression PASSED |
| Google Play products/test purchase/backend verification/pending/restore/refund | NOT VERIFIED live | Play Console/service account/license testers/signed AAB absent; host Premium lock/pending regression PASSED |
| Paid report real credit and duplicate-charge behavior | NOT VERIFIED live | 200/202/402/409 and stable retry host tests PASSED; no real credit, OpenAI or store run |
| External expert payment | NOT CONFIGURED | B13A PSP disabled; no implementation or fake paid completion added. REVIEW_REQUIRED must remain blocked |
| Real-device performance / TalkBack / VoiceOver / larger text | NOT RUN | No devices/builds. Host DTO benchmark is not device frame/launch latency; matrix in `device_test_matrix.md` |

## Security, privacy, listing and artifacts

- Targeted source scan (`lib`, Android/iOS native, Firebase rules, Codemagic) found **0 candidate mobile secret files** for private keys/OpenAI/AWS/service-account/LiveKit patterns; `print`/`debugPrint`/`NSLog`/Android `Log` call-site scan found **0 mobile source files**. This is a pattern/source audit, **not** a runtime crash/log capture or proof of no sensitive telemetry. Production ID/FCM/VoIP/LiveKit tokens, purchase proofs/JWS, birth/chat data must be checked on real release builds and any crash SDK before sign-off. Mobile Firebase client configuration is not a server secret.
- Privacy/data-flow inventory for store disclosures (observed from mobile adapters and backend contracts; retention/sharing policy still needs product/legal review):

| Data | Mobile → backend/service | Disclosure/verification gap |
| --- | --- | --- |
| Birth date/time/place, coordinates, saved-person chart data | HTTPS FastAPI profile/astrology; secure local profile cache; backend PostgreSQL | Retention, deletion/export, AI context use and third-party processing decision |
| Horary questions and AI prompts/report context | HTTPS FastAPI horary/AI; B13A OpenAI provider when configured | Sensitive free text; OpenAI processor and retention disclosures, live flow not configured |
| Expert chat text and conversation identifiers | HTTPS FastAPI message POST; Firestore server projection/listener | Firestore access/rules, moderation/retention and participant notice |
| Chat images/attachments | Backend intent/finalize; Firebase Storage authorized object path; Firestore message metadata | Bucket region, MIME/size enforcement, deletion/retention, no permanent public URL live proof |
| Call metadata, participant IDs, media | FastAPI call lifecycle; LiveKit media/TURN when configured | Provider/region/recording policy, network/metadata retention |
| FCM and VoIP device tokens | Firebase/PushKit → FastAPI device registration; backend FCM/APNs | Token rotation/logout/deletion and push consent disclosures |
| Apple JWS/transaction and Google purchase token/product ID | StoreKit/Play → FastAPI verification → Apple/Google server APIs | Purchase/account linkage, refunds/revocations, sandbox proof |
| Paid-report `consumer_ref` | Secure device storage → FastAPI report endpoint | Opaque attempt ID, scoped per user; retry retention/cleanup review |

- Store listing gaps: real screenshots, privacy policy URL, support URL, App Store privacy answers, Play Data safety form, age rating, review notes/test access, subscription names/descriptions/pricing/terms, product metadata and final bundle/package ownership. None were fabricated or submitted.
- No debug APK, signed AAB or IPA artifact exists at the checked output paths; release size, artifact filename/path and build number are **N/A**. Prior debug size figures are not release-size evidence.

## Release gate summary

Ship-gate categories: **SEC PARTIAL** (source scans/guards, runtime logs unknown); **DB PARTIAL** (B13A local backend only, production not provisioned); **CODE PASS host / OPEN native**; **DEP PARTIAL** (Flutter dependencies resolve; native SDK/signing missing); **AI OPEN**; **DEPLOY OPEN** (HTTPS/CORS/credentials); **FE OPEN device** (performance/accessibility); **OBS OPEN** (release crash/alerting not exercised).

**LIVE VERIFIED in B13B:** none. **PARTIALLY VERIFIED:** Flutter contract, fail-closed Premium and release configuration on host; Codemagic YAML syntax. **NOT VERIFIED:** all physical-device, native compile, Firebase/APNs/LiveKit/OpenAI/store services and release artifacts. Open blockers/owners are in `mobile_release_blockers.md`. Next work is a specifically scoped B13C only after operator-provided credentials, signing/build access and devices; no automatic B14 or submission.
