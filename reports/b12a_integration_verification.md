# B12A integration verification

## Local checks

- `flutter analyze`: no issues.
- `flutter test`: 73 passed, 1 design-preview test skipped intentionally.
- `dart format --output=none --set-exit-if-changed` on changed Dart files: 0 changes.
- API/mock provider selection and local JWT/Firebase/hybrid adapter selection covered by tests.
- Concurrent 401 tests exercise ten requests, single JWT/backend or Firebase SDK refresh, retry and failed-session cleanup.
- Backend source and assets were not changed; no commit was created.

## Live backend smoke

Local development API was exercised with a disposable account, which was soft-deleted after validation. The run covered registration/login, birth profile, saved people create/list/delete, natal, transits, daily frequency, personal calendar, horary, synastry, composite, Davison, three deck draws, AI status/conversation metadata and public expert listing. Sanitized contract samples are in `test/fixtures/live_b5_b11_contract_samples.json`.

Representative remote HTTP durations (milliseconds): natal 32, transits 31, daily 28, personal calendar 654, horary analysis 704, synastry 41, composite 46, Davison 41, Tarot 59, Rune 39, Katina 51. These are local backend requests from a Dart smoke harness, **not Flutter device cold-launch or first-frame timings**; full samples are in `reports/b12a_live_timings.json`.

## Configuration and verification limits

- Firebase native project settings/credentials are absent. Firebase SDK login, Google/Apple provider setup, token verification and device logout are not end-to-end verified. Selecting Firebase without native config gives a controlled configuration error; local JWT remains usable.
- Local backend reports AI provider not configured. Controlled unavailable behavior and DTO/SSE/poll parser tests passed, but no real model stream or report generation was possible.
- `flutter doctor -v` reports no Android SDK. Release Android App Bundle was **not built**. iOS build was **not verified** on Windows.
- Device cold launch, home first meaningful data, natal-screen load and transit-screen load were **not measured**; remote HTTP timings must not be presented as substitutes.
- Saved-person update has no backend route; see `reports/b12a_backend_contract_issues.md`. Read-by-ID uses the authenticated list as a compatibility fallback.
- TR and EN new copy is present. AZ UI is not production ready.
- B12B/B12C marketplace, chat, LiveKit, billing and FCM UI remain out of scope.
