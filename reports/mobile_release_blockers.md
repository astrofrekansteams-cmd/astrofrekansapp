# Mobile release blockers (B13C current)

## B13C current release blockers — 2026-09-25

This section supersedes the B13B/B12C historical sections below. Current recommendation: **NOT READY FOR SUBMISSION**. `OPEN` means the B13C physical/native/store evidence is missing; `PARTIAL` means source/host proof only; `CLOSED` is limited to the explicitly named host gate. Full evidence: `b13c_real_environment_validation.md` and `b13c_store_validation.md`.

| Priority | Gate/blocker | Status | Owner / evidence required |
| --- | --- | --- | --- |
| P0 | Firebase mobile configs, backend project/service account, RTDB URL, bucket and live Auth/Firestore/RTDB/Storage/FCM | OPEN | Project/operator: real files and server secrets outside Git, deploy rules, signed-device E2E; no fake IDs |
| P0 | Java 21 and real Firebase rules emulator run | OPEN | Environment/operator: controlled JDK21 path, Firestore/RTDB/Storage harness/results; no system Java was changed |
| P0 | Android SDK/native Kotlin compile/JUnit, signed AAB | OPEN | Android build/operator: SDK, Gradle/JDK/licenses, upload keystore, real Firebase config, production HTTPS URL, build/test logs and AAB path/size/build number |
| P0 | iOS Codemagic Swift compile/RunnerTests, Apple signing, signed IPA | OPEN | iOS build/operator: Codemagic/macOS account run, Team ID/cert/profile, Push capability, real plist, stage logs and IPA path/size/build number |
| P0 | Production HTTPS API URL, scoped CORS and production environment | OPEN | Deployment/operator: real `API_BASE_URL`, non-wildcard `CORS_ORIGINS`, production services/health/backup/rollback evidence |
| P0 | OpenAI + LiveKit/TURN + Apple/Google backend store credentials | OPEN | Backend service/operator: provision secrets outside repo, pass live smoke before Flutter device E2E |
| P0 | Apple sandbox, Google internal/test-track and real paid-report credit E2E | OPEN | Store/mobile QA: accounts, SKUs/testers, signed builds, purchases/verification/restore/refund and stable-ref one-credit evidence |
| P1 | APNs VoIP + Android data-only FCM delivery, ordering, OS full-screen/CallKit | OPEN | Platform QA: APNs `.p8`/IDs and signed iPhone; FCM config and Android 14+ device; background/killed/duplicate/answer/decline logs |
| P1 | LiveKit physical Android+iPhone media, TURN, Bluetooth, reconnect and duplicate identity | OPEN | Realtime/mobile QA: configured service, two devices and carrier/NAT test networks |
| P1 | Real-device performance, TalkBack/VoiceOver and runtime sensitive-log audit | OPEN | Mobile QA: device/build-specific timings, accessibility results, logcat/Xcode/crash SDK evidence |
| P1 | Store screenshots, privacy/support URLs, rating, review notes, product/terms and privacy answers | OPEN | Product/legal/store operator: factual listing assets and confirmed data processing/retention matrix |
| Conditional | Premium-included reports flag and external expert PSP | OPEN (product decision) | Keep default paid-report flag `false` and PSP `disabled` until separate product/contract alignment; no fake payment path |
| Host | Flutter analyze/test and local API liveness | CLOSED (host only) | B13C: analyze clean, 141 passed/2 skipped, `/health` and `/ready` 200; does not close native/live blockers |
| Host | Source-level secret/log scan and Codemagic YAML | PARTIAL | No candidate mobile keys or explicit logging calls; runtime release logs and actual Codemagic execution still OPEN |

## B13B authoritative status — 2026-09-25

This table supersedes historical B12C wording below. `CLOSED` means a host code/contract gate only; it never implies live service, native compile or store approval. No store submission was performed.

| Blocker / gate | Status | Owner and closure evidence |
| --- | --- | --- |
| Flutter paid-report B13A contract and stable retry, no client credit consume | CLOSED (host) | Codex: Flutter contract tests for 200/202/402/409 and network retry; live credit purchase/delivery remains OPEN |
| Store callback alone unlocking Premium | CLOSED (host) | Codex: fake Apple/Google purchased callback + inactive backend remains locked; active backend unlocks; device sandbox still OPEN |
| Release mock/API URL guard | CLOSED (host) | Codex: production/release mock rejected, HTTPS/loopback validation, Codemagic uses `APP_DATA_SOURCE=api`; real URL/operator CORS still OPEN |
| Firebase project + Android/iOS client configs and backend credentials | OPEN | Owner: project/operator. Supply real native configs and backend service account/project/bucket/database URL; then signed builds and Auth/Firestore/RTDB/Storage/FCM E2E |
| Firebase rules emulator | OPEN | Owner: environment/operator. Install Java 21 in a controlled path, create/run Firestore/RTDB/Storage rules harness; no system Java change by Codex |
| Android SDK, physical device and native Kotlin compile/JUnit | OPEN | Owner: build/operator. Provide SDK or Codemagic run, execute `flutter build apk --debug` and `:app:testDebugUnitTest`, attach task output and device model/OS/build |
| Android release signing/AAB and Play test track | OPEN | Owner: Android release/operator. Real keystore, Firebase config, SDK, Play app/products/testers and successful signed AAB/track evidence |
| iOS macOS/Codemagic compile, XCTest, signing and IPA | OPEN | Owner: iOS release/operator. Real Apple team/cert/profile, Firebase plist, Codemagic run logs + RunnerTests + signed IPA; local YAML syntax is only PARTIAL |
| PushKit/APNs VoIP and FCM device delivery | OPEN | Owner: backend/platform/operator. APNs `.p8`/IDs and signed iPhone, FCM backend credentials and physical Android; foreground/background/killed/cancel/missed/duplicate evidence |
| LiveKit/TURN and mobile media | OPEN | Owner: infrastructure/QA. Staging/production credentials, TURN and physical Android/iPhone call, reconnect, duplicate identity, Bluetooth evidence |
| OpenAI live chat/stream/report | OPEN | Owner: backend/operator. Server key and backend live smoke first, then Flutter device E2E including paid report |
| Apple Store and Google Play billing E2E | OPEN | Owner: store/operator/QA. Real product IDs and server credentials; sandbox/test-track purchase, backend verification, locked-on-failure, restore, pending, refund/revoke |
| External expert payment provider | OPEN (product decision) | Owner: product/operator. Provider remains disabled; priced expert checkout must remain unavailable; review-required payment remains blocked |
| `PAID_REPORTS_INCLUDED_IN_PREMIUM` product flag | OPEN (conditional) | Owner: product/operator. Keep B13A default `false` for this candidate; if enabling `true`, Flutter paid section must expose the backend-reported `capabilities.premium_reports` path without requiring a credit, with tests |
| Production API/CORS, production infrastructure and monitoring | OPEN | Owner: deployment/operator. HTTPS non-loopback API URL, bounded `CORS_ORIGINS`, production DB/Redis, crash/alerting evidence; no wildcard CORS |
| Store listing and privacy disclosures | OPEN | Owner: product/legal/store operator. Screenshots, privacy/data-safety, age rating, support/privacy URLs, review notes and subscription metadata based on real data inventory |
| Real-device performance and accessibility | OPEN | Owner: mobile QA. Populate `device_test_matrix.md` with model, OS, build, environment, actual timestamp and evidence; no physical rows run in B13B |

Current release recommendation: **NOT READY FOR SUBMISSION**. Detailed evidence and data inventory: `b13b_flutter_release_validation.md`.

> B12C.2 update (2026-09-25): backend call-delivery contract is frozen and native PushKit/CallKit plus Android data-only receiver code has been added. The B12C.1 paragraph below saying those paths are unimplemented is historical. Native build/device validation remains blocked; see `b12c2_native_call_verification.md`.

This is not a release sign-off. Resolve each item with evidence before store submission.

| Area | Current state / required evidence |
| --- | --- |
| Firebase Auth, Firestore, RTDB, Storage | No real Firebase native project files or real-project end-to-end validation. Provide actual Android/iOS configs and exercise auth, chat, presence, media. B9 presence policy unchanged. |
| FCM | Native config and physical-device foreground/background/cold-start delivery not verified. Notification permission and revoked-permission behavior need device checks. |
| OpenAI | No production API key/provider E2E; Astro AI/report generation remains not verified. |
| App Store Connect | App record, matching bundle ID, contracts, subscription/report SKUs, sandbox users, signing certificate/profile and review metadata not verified. |
| Play Console | App record, package ID, subscription/report SKUs, license testers, upload key, Play Billing production access not verified. |
| Store purchase and restore | StoreKit/Play purchase, pending, cancel, duplicate callback, account mapping, refund/revocation and reinstall restore require real sandbox/test-track runs. Backend-paid report enforcement gap is HIGH. |
| External expert payment | External provider credentials/configuration and checkout handoff/webhook lifecycle not verified. `REVIEW_REQUIRED` remains blocked. |
| Android SDK | Missing on this Windows host; no AAB build was possible here. CI signing identity also absent. |
| iOS signing/build | Windows cannot build iOS. Codemagic workflow syntax parsed locally, but signing profiles, Pods, IPA output and App Store validation were not run. |
| Physical Android | Audio/video, camera switch, mute, speaker/Bluetooth, network drop/reconnect, rotation, background, FCM incoming UI and 1.6×/2× text need device testing. |
| Physical iPhone | Same call/store checks plus notification behavior, StoreKit sandbox, real PushKit/CallKit delivery and background-mode review. |
| LiveKit/TURN | Real client connection, mobile network/NAT traversal, TURN, 45-second grace and duplicate-identity replacement need physical-device validation. |
| Incoming-call native UI | B12C.2 code now includes Android data-only service and iOS PushKit/CallKit bridge; neither native build nor physical background/killed-state delivery is verified. Do not claim ringing in those states yet. |
| Release config | Production API URL, real Firebase config, Android keystore, iOS certificates/profiles and app ownership must be provisioned. No automatic store upload configured. |

The user has not authorized store submission. Next phase is device validation and production launch readiness, not automatic publishing.

## B12C.2 native validation gate

- Android SDK and real Firebase config are absent, so the new Kotlin service/JUnit tests have not run or compiled on this host. Validate merged manifest, data-only delivery, notification permission denial, Android 14 full-screen eligibility and heads-up on a physical device.
- Windows has no Xcode. Build the Swift target/XCTest on macOS with the actual Apple Push Notifications/VoIP capability and signing profile; provide APNs VoIP credentials matching the backend environment. Verify `reportNewIncomingCall`/PushKit completion, process restart, duplicate/expired push and audio handoff on a physical iPhone.
- Real Firebase, APNs, LiveKit/TURN, store and payment validation above remain release blockers. Do not treat Flutter tests as native-delivery proof.

## B12C.1 incoming-call boundary

### Implemented but not device verified

- `IncomingCallPresentationService` separates Android, iOS/in-app and fake presentation. Foreground `incoming_call` is displayed only after authenticated `GET /calls/{id}` confirms a waiting/ringing call. Duplicate IDs are coalesced; a cancelled/missed event wins over an in-flight GET.
- Android native high-importance `astrofrekans_calls` channel uses generic "Astrofrekans / Gelen görüşme" text, private lock-screen visibility, and Open/Answer/Decline actions. On Android 14+ it checks `canUseFullScreenIntent()` before attaching a full-screen intent; otherwise the OS may show heads-up. The full-screen target is a non-exported generic native `IncomingCallActivity`, not the private Flutter app screen. The app never starts an activity directly from a background service. `POST_NOTIFICATIONS` and disabled notification/channel states fall back to the authenticated in-app screen. Native action intents are nonce-checked before they are accepted from the exported launch activity. No phone-call foreground service or self-managed `ConnectionService` was declared because this implementation does not use either; do not add their permissions speculatively.
- Native action and notification cold-start extras are passed to Flutter once; both action handling and `CallController.join()` refresh the server session. `/join` remains the only LiveKit token source. Answer hands off to the existing Flutter call screen, whose explicit answer path connects LiveKit. Decline uses the verified B10 `/end` semantics (ringing/waiting becomes `cancelled`); failure never writes a local fake decline. Cancellation/miss dismisses the local notification while Flutter is running/receiving the event.
- Existing FCM initial/opened route supports a notification tap after cold start and prompts authentication before navigation. Physical-device delivery, Android notification action launch/permission behavior, lock-screen rendering, media handoff, and process-recreation timing are **NOT VERIFIED**.

### Not implemented due to missing server/platform credential or delivery contract

The exact B9 delivery gaps are tracked separately in `reports/b12c1_native_call_contract_issues.md`.

- iOS CallKit/PushKit is **not implemented**. LiveKit consultation is a real VoIP use case, so PushKit + CallKit is an appropriate *future* strategy, but B9 currently registers only ordinary FCM tokens and sends normal FCM/APNs notification payloads. It has no VoIP token registration, APNs VoIP delivery, entitlement/provisioning, or device validation. A normal FCM notification must not be misrepresented as a VoIP push. Current iOS behavior remains ordinary notification → authenticated in-app call screen. No fake token, entitlement or `UIBackgroundModes` entry was added.
- Android backend push is `notification + data` (`FirebasePushProviderImpl.send_multicast`). Firebase handles that payload in the system tray when the app is backgrounded; the Flutter foreground listener is not a reliable background receiver for it. Therefore the new high-importance native call notification, action buttons, and cancellation dismissal are **foreground only**. A B9 server delivery design for call-specific data-only/background handling (and cancellation) is required before claiming background/locked/killed Android native ringing. Backend was read-only in this phase.
- Full-screen eligibility depends on Android 14+ OS/Play policy, user grant and physical-device behavior. The manifest permission alone is not proof of eligibility. If denied, heads-up notification is the fallback. There is no Android foreground service and no exemption from background execution limits.

Official basis: [Apple PushKit/CallKit](https://developer.apple.com/documentation/pushkit/responding-to-voip-notifications-from-pushkit), [Firebase Flutter message handling](https://firebase.google.com/docs/cloud-messaging/flutter/receive-messages), [Firebase Android notification/data background behavior](https://firebase.google.com/docs/cloud-messaging/android/receive-messages), [Android 14 full-screen limits](https://developer.android.com/about/versions/14/behavior-changes-14).

Host verification: `flutter analyze` clean; `flutter test` 129 passed, 2 skipped; changed Dart files pass `dart format --output=none --set-exit-if-changed`. `flutter doctor -v` reports no Android SDK, so Kotlin/Android build and physical notification behavior were **not compiled or verified**. iOS cannot be built on this Windows host.
