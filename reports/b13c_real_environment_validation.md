# B13C real-environment validation — 2026-09-25

**Release recommendation: NOT READY FOR SUBMISSION.** B13C is an evidence-gathering phase, not a feature phase. Statuses below are based on this host and accessible project files at 2026-09-25 04:43 UTC; an account not accessible here is not asserted nonexistent. No backend business logic, Flutter/native source, assets, credentials or signing material was changed. No store submission or Git commit.

## Prerequisite inventory

`AVAILABLE` means directly observed. `MISSING` means absent from the inspected host/repo/environment. `PARTIAL` means a source configuration exists but remote account or operative capability is not verifiable. Secret values were never printed.

| Group | Prerequisite | State | Evidence / limitation |
| --- | --- | --- | --- |
| Android | SDK and adb | MISSING | `flutter doctor -v` cannot locate SDK; controlled SDK paths and `ANDROID_HOME`/`ANDROID_SDK_ROOT` absent; `adb` unavailable |
| Android | Java 21 | MISSING | Java 17.0.20.1 at `C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot`; checked Java/Adoptium/user JDK locations, no 21; no system change |
| Android | Physical device | MISSING | Flutter lists Windows, Chrome, Edge only |
| Android | Release/upload keystore | MISSING | No repo keystore and `CM_KEYSTORE_*` variables unset; remote Codemagic identity unverified |
| Android | Play Console app and license tester | PARTIAL | Package ID source is `com.astrofrekans.astrofrekans`; no Play Console/account/tester access or evidence |
| Android | `google-services.json` | MISSING | `android/app/google-services.json` absent |
| iOS | Codemagic/macOS access | PARTIAL | `codemagic.yaml` defines iOS workflow, but no Codemagic CLI/account run or macOS/Xcode access supplied |
| iOS | Apple team, certificate and profile | MISSING | No signing input or signed build on this host; remote account state unverified |
| iOS | App Store Connect app and sandbox tester | PARTIAL | Bundle ID source is `com.astrofrekans.astrofrekans`; no App Store Connect/account/tester evidence |
| iOS | `GoogleService-Info.plist` | MISSING | `ios/Runner/GoogleService-Info.plist` absent |
| iOS | Push Notifications/PushKit provisioning | PARTIAL | `Info.plist` declares `voip` and `remote-notification`; no verified Push Notifications entitlement, signed profile or device capability |
| iOS | Physical iPhone | MISSING | No iPhone connected/available to this Windows host |
| Backend | Local API/PostgreSQL/Redis | AVAILABLE locally | Existing Compose containers healthy; `GET /health` and `/ready` returned 200. This is not production readiness |
| Backend | Firebase project/service account, RTDB URL, Storage bucket | MISSING | Corresponding host variables unset and backend `.env` keys not present; `backend/secrets` absent |
| Backend | OpenAI API key | MISSING | Host variable unset; backend `.env` key empty |
| Backend | LiveKit URL/API key/secret/webhook | MISSING | Host variables and backend `.env` keys absent |
| Backend | APNs Team ID, Key ID and `.p8` | MISSING | Host variables/backend `.env` keys absent; no supplied key |
| Backend | App Store Server API credentials | MISSING | No accessible key/issuer/certificate configuration; account state unverified |
| Backend | Google Play service account/PubSub | MISSING | No accessible service account or PubSub configuration; account state unverified |
| Deploy | Production API URL and CORS | MISSING | `API_BASE_URL` unset; backend `.env` `CORS_ORIGINS` empty. No wildcard was introduced |

The prior B13A report's **811 passed / 0 failed** backend suite is historical source-of-truth evidence, **not a B13C rerun**. `backend/.env` was read only for key presence/emptiness and remains Git-ignored.

## Execution matrix

| Test/gate | B13C status | Evidence / reason |
| --- | --- | --- |
| Flutter static analysis | PASS | `flutter analyze` → no issues |
| Flutter host tests | PASS | `flutter test --reporter compact` → 141 passed, 2 skipped |
| Local backend liveness | PASS (local only) | `/health` 200, `/ready` 200; no external service E2E implied |
| Firebase Emulator Firestore, RTDB and Storage rules | BLOCKED | Java 21 absent; Firebase CLI 15.22.4 installed. No emulator harness/run claimed; B9 presence schema untouched |
| Firebase initialization/Auth ID token→FastAPI, Firestore backend POST/listener, RTDB presence ACL, Storage upload/finalize, FCM registration | BLOCKED | Client native configs and backend Firebase credentials absent |
| Android debug APK/Kotlin compile/Gradle `testDebugUnitTest` | BLOCKED | SDK/adb absent. `NativeCallDelivery.kt`, `AstroCallMessagingService.kt`, `MainActivity.kt`, `IncomingCallActivity.kt` not natively compiled in B13C |
| Android merged-manifest one `MESSAGING_EVENT` service | BLOCKED | Source removes FlutterFire service and declares custom service, but merged manifest requires Android build tooling |
| Android signed production AAB | BLOCKED | SDK, Firebase config, signing and production URL absent; no AAB/file size/build number |
| Android Firebase/FCM call ordering/full-screen/media/TURN/Bluetooth/reconnect/performance/TalkBack | BLOCKED | Physical Android, real Firebase/LiveKit and signed/device build absent; prior fake tests are not device proof |
| iOS Codemagic stages, Swift compile, RunnerTests, archive/sign/IPA | BLOCKED | No remote Codemagic run/macOS/signing/Firebase plist; YAML existence is not build evidence |
| PushKit token→backend→APNs→CallKit, duplicate, answer/decline, media/Bluetooth | BLOCKED | Signed iPhone, APNs credentials and LiveKit absent |
| Live OpenAI backend smoke then Flutter chat/stream/report/job | BLOCKED | OpenAI key absent; live smoke was not run with a fabricated key |
| Apple sandbox products/purchase/verify/restore/refund and real paid report | BLOCKED | App Store Connect setup, IPA, backend credentials and OpenAI absent |
| Google test-track products/purchase/pending/verify/restore/refund and real paid report | BLOCKED | Signed AAB, Play access/tester, backend credentials and OpenAI absent |
| Real-device performance/accessibility and release runtime logs | BLOCKED | No release build or physical device; source scan is not runtime log proof |
| Store Privacy / Play Data Safety final submission answers | BLOCKED | Live processors/regions/retention and product/legal decisions unconfirmed; source inventory in `b13c_store_validation.md` |

No executed native or live-service test failed; **`FAILED: 0` does not mean those groups passed**. `NOT RUN` means no test was attempted; `BLOCKED` additionally names a missing prerequisite. Physical scenarios and exact device fields are in `device_test_matrix.md`.

## Release gate audit

| Gate | Result | Evidence boundary |
| --- | --- | --- |
| SEC | PARTIAL | Targeted mobile key-pattern scan: 0 candidate files; mobile `print`/`debugPrint`/`NSLog`/Android `Log` call-site scan: 0 files; `backend/.env` ignored. Runtime token/PII logs and production HTTPS still unverified |
| DB | PARTIAL | Local PostgreSQL/Redis/API healthy per Compose and `/ready`; production DB, backups/restore and retention unverified |
| CODE | PASS host / BLOCKED native | Flutter analyze/test pass; Kotlin/Swift builds and native tests not executed |
| DEP | PARTIAL | `pubspec.lock` exists; Git has no baseline commit, so lockfile is not committed; native SDK/signing unavailable |
| AI | BLOCKED | OpenAI key absent; no live smoke or privacy-processing verification |
| DEPLOY | BLOCKED | Production HTTPS URL/CORS, Firebase, signing and stores not provisioned; local health is insufficient |
| FE | BLOCKED | No device performance, TalkBack, VoiceOver or scaled-text runs |
| OBS | BLOCKED | No release runtime/crash-log capture; no mobile crash-SDK reference found in scanned source |

Manual confirmations still required: production TLS/CORS, database backup/restore, staging/rollback, alerts/error rates/log retention, Apple/Google accounts and store policies. They are **not** inferred from source scans.

## Decision

**LIVE VERIFIED in B13C:** local API `/health` and `/ready` only. **PARTIALLY VERIFIED:** static native/Codemagic configuration and source-level security inventory. **BLOCKED:** every native, device, Firebase, APNs, LiveKit, OpenAI and store E2E gate. **NOT RUN:** corresponding actions because prerequisites were absent. **OPEN P0:** Firebase/config/rules, Android+iOS builds and signed artifacts, production URL/CORS, LiveKit/OpenAI, Apple+Google billing and real paid report. **OPEN P1:** physical push/call/media, performance/accessibility, runtime log and store metadata/privacy evidence. Next action is operator provision of the exact prerequisites in `mobile_release_blockers.md`; do not submit or proceed to a new feature phase.

Backend modified: **0**. Assets modified: **0**. Store submission: **NOT PERFORMED**. Git commit: **no**.
