# B12C integration verification — 2026-09-25

> B12C.2 addendum: the B12C/B12C.1 native-delivery limitations below describe the earlier phase, not the current code. PushKit/CallKit and Android data-only service code are now present; platform compilation and real delivery remain **NOT VERIFIED**. See `b12c2_native_call_verification.md`.

Latest B12C.2 host checks: `flutter analyze` 0 issues; `flutter test` 134 passed, 2 skipped. Android/iOS native tests were added but not run without their platform toolchains.

## Implemented on the Flutter side

- Typed B10 call repository, join-only ephemeral LiveKit grant, media/permission abstraction, audio/video controls, reconnect and duplicate-identity UI, incoming-call push routing, history and order entry point.
- B11 backend catalog and verification adapters; app-level store purchase listener; backend-authoritative entitlement controller; Premium, restore, digital and expert payment group UI. Store-localized price is the only displayed purchase price.
- Client-side paid-report orchestration uses a verified credit and report ID as the stable `consumer_ref`. This is **not** a backend-enforced paywall; see `b12c_backend_contract_issues.md`.
- Android microphone/camera/notification/billing permissions, iOS usage descriptions, Codemagic release-candidate workflows, no fake Firebase project files, no automatic publishing.

## Host checks

- Baseline: `flutter analyze` clean; `flutter test` 96 passed, 2 skipped.
- Final full-suite check: `flutter analyze` clean; `flutter test` **122 passed, 2 skipped**. `dart format --output=none --set-exit-if-changed` checked 30 changed Dart files with 0 changes.
- Targeted B12C fake tests cover call DTO/token redaction, audio/video/controls, denied permission, three authorization errors, reconnect, replacement, push routes, product mapping, localized price, purchase-with-inactive-entitlement locked, active/grace/expired states, pending, duplicate callback, restore, listener disposal, report-credit retry, hybrid/review groups, and 1.6×/2× Premium rendering.
- Host-only DTO timings: 50 call DTOs 8,352 µs; 20 products 576 µs; 100 entitlement DTOs 10,366 µs. These are local test-isolate measurements, **not** device frame times, networking or store latency.
- Host-only widget-harness measurements in the final full run: first audio-call screen at 2× text 993 ms; Premium screen at 1.6× 1,056 ms and 2× 91 ms. These include test harness/asset startup effects and are **not** device frame times.
- `flutter doctor -v`: Flutter 3.44.4/Dart 3.12.2; Android SDK missing. No Android release AAB. Windows host cannot build iOS.
- Local API `127.0.0.1:8000`: `GET /calls/status`, `/billing/status`, `/billing/products?platform=android`, `/billing/entitlements` all returned 401 without credentials. Routing/auth guard is reachable; configured provider/status/catalog/entitlement response bodies are **NOT VERIFIED**. No test account or backend data was created.
- Codemagic YAML parsed locally into two workflows; neither workflow was executed.
- Security text scan of `lib`, `android`, `ios`, `codemagic.yaml` and B12C fixture found no private key, OpenAI key, Firebase service account or native Firebase config file. Join/store proof values are redacted from custom `toString` and are never sent to persistence APIs by B12C code.
- Baseline and final SHA-256 of the sorted backend+assets file-hash manifest are identical: `CF7C3DFAED205F149BDDBC2A55034244A2DECA8F30B7EED18BF5AF18EFF14340`. Backend files modified by Codex: **0**; assets modified: **0**. No Git commit was created.

## Explicitly not verified

Physical-device LiveKit, TURN, Bluetooth, native incoming-call UI, Firebase/FCM, real Apple/Google purchases and restore, external PSP, production OpenAI, signed AAB/IPA, accessibility on devices and actual Codemagic signing. The high-severity paid-report backend contract issue prevents payment-enforced report release sign-off.
