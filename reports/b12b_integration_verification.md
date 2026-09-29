# B12B integration verification

## Outcome

Flutter B12B marketplace, order/consent/review, expert-workspace and chat/FCM foundations are implemented without backend or asset edits. This is **not** a real-Firebase or mobile-device release sign-off. B12C was not started.

## Local checks

- Baseline before B12B: `flutter analyze` clean; `flutter test` 73 pass, 1 design-preview skip.
- Final `flutter analyze`: clean. Final `flutter test`: **96 passed, 2 skipped** (opt-in live smoke and design preview). Opt-in B12B live smoke also passed separately.
- `dart format --output=none --set-exit-if-changed` on changed Dart files: 0 changes.
- Backend source digest over 267 files stayed `A2423C438442A8A4FD68A058FD4DAEB5AE2BC81E9B9A3B9A15903614B1390568` from before to after this phase: **backend files modified by Codex: 0**.
- Asset path/size/UTC-mtime digest over 537 files stayed `6588F2685F1442E0F323F85AE7342200C482A0AD720A7A1838CFABB86F18992A`: **assets modified by Codex: 0**. No image generation was performed.
- No commit was created. Repository still lacks a baseline commit, so the changed-file manifest is the audit record.

## Contract and behavior coverage

- Typed DTO fixtures cover experts, services, slots, orders, appointments, consent, review, favorites, conversation, messages, attachment, device and availability; unknown order states do not crash.
- Repository tests verify filter parameters, page-only text search, stable order idempotency key, complete-set consent `PUT`, backend-only message `POST` with client id, and review create/update/delete paths.
- Controller tests verify history/realtime dedupe, pagination, listener disposal, read-only/closed send denial, sender-only delete, same-id retry with cooldown, attachment MIME rejection, finalize-before-message and failed-finalize no-send.
- Push tests verify no launch-time permission request, explicit opt-in, token refresh, backend device unregister/logout and allowlisted generic routes. No private message text is used in notification routing.
- Widget tests render marketplace results and verify page-only search and 1.6x text on a 320px viewport without overflow.
- Firestore client adapter has a read listener only; all message writes use FastAPI. RTDB writes are restricted to the signed-in user's presence and typing path. Storage uploads require backend intent and ready finalization. Image display uses authorized Storage bytes, not a public URL.

## Live loopback smoke

`B12B_LIVE=1 flutter test test/core/b12b_live_smoke_test.dart` passed on the local `http://127.0.0.1:8000` API. Each run created a random synthetic user, then soft-deleted it. The final passing run observed: 2 experts; 1 service and 1 review on the selected expert; 219 generated slots; public detail; favorites add/list/remove; empty initial order/appointment lists; chat policy; a priced order remaining `pendingPayment` with `payment=pending`; consent grant and complete-set revoke; and order cancellation. No paid state was faked. The backend reported `firebase_configured=false`, and the conversation endpoint returned controlled `firebase_not_configured` / HTTP 503. A completed-order review mutation and a confirmed appointment path were **not** created in live smoke.

## Firebase and device limits

- No `firebase_options.dart`, `google-services.json` or `GoogleService-Info.plist` was fabricated; no real Firebase project or credentials were configured. Real Firestore listener, RTDB presence/typing, Storage upload/display, FCM delivery and Firebase ID-token mapping are **NOT VERIFIED** end-to-end.
- Firebase CLI 15.22.4 and repo emulator rules exist, but emulator startup failed before rules loaded: CLI requires Java 21+, host has OpenJDK 17. Emulator adapter/rules tests are **NOT VERIFIED**.
- Backend presence projection and RTDB rule path disagree; see `b12b_backend_contract_issues.md`. Partner presence may be denied until the separately owned backend/rules fix.
- `flutter doctor -v`: Android SDK absent, so no Android build/device install. iOS build was not attempted on Windows. Native Firebase configuration, background push delivery, notification permission behavior and deep-link restoration need device tests.

## Performance scope

Synthetic host-side Flutter-test measurements, **not device frame times or remote latency**: 20-expert DTO parse 15.8 ms; expert DTO 0.7 ms; 240 slots spanning 30 days 15.2 ms; 50-message DTO parse 5.4 ms; one-message map append 1.0 ms; 8 MiB local byte copy 6.4 ms. A 20-result marketplace widget test took 1.3–2.8 s wall time across runs, including test harness setup, asset loading and an explicit 500 ms animation pump. Expert-detail frame, 50-message actual chat frame and network/Firebase first meaningful paint remain **NOT VERIFIED** on a device.

## Known limitations / next gate

- Search is explicitly limited to the loaded page because the backend has no full-text parameter. Expert appointment detail is derived from the authorized list; no expert detail endpoint exists.
- Turkish and English B12B copy is present. Azerbaijani currently falls back to Turkish and needs product localization review.
- True Firebase E2E, the presence projection/rule correction, Android/iOS builds, permission/background notification checks and device-level accessibility/performance remain release gates.
- B12C (LiveKit calls, StoreKit/Play Billing, entitlements, release integration) was **not** started.
