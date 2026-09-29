# B12C.2 native call bridge verification — 2026-09-25

Status: **code ready for native build and device validation; not release-verified**.

## Implemented

| Area | Result |
| --- | --- |
| iOS delivery | PushKit `.voIP` registry starts in `AppDelegate`, reports every VoIP push to CallKit before PushKit completion, including expired/duplicate deliveries. CallKit uses the backend `call_id` UUID deterministically. The highest event version persists in `UserDefaults`; active minimal call metadata and pending actions survive process restart. Duplicate/older events do not create a second UUID. Expired/terminal calls end locally. |
| iOS token lifecycle | PushKit hex token remains in memory, authenticated `/devices/voip` registration stores only returned device ID securely, rotation removes the old ID, invalidation and logout attempt unregister. No token is logged or put in analytics. |
| iOS answer/decline | CallKit actions persist minimal pending data. Flutter consumes once after auth, GETs the call; answer enters existing call screen, which GETs again, POSTs `/join`, then uses the existing `LiveKitCallMediaService`. Decline/end POST `/end`; API failures surface a typed generic message. CallKit audio activation/deactivation controls LiveKit's external-call-system mode and engine availability. |
| iOS reconciliation | Native expiry timer plus up to six authenticated GET checks, 10 seconds apart, while ringing. Terminal/active server status stops polling and reconciles CallKit. Push remains a hint, not authorization. |
| Android delivery | A single `FirebaseMessagingService` handles data-only call events without a network request. Highest event version, expiry, minimal pending action and action nonce persist in private `SharedPreferences`. Stable call-ID-derived notification IDs; generic high-importance `CATEGORY_CALL` private notification with answer/decline. Terminal events dismiss. |
| Android full-screen | On Android 14+, full-screen intent is attached only when `canUseFullScreenIntent()` permits it. Otherwise high-importance notification remains for system heads-up behavior. Notification/channel permission denial means presentation is unavailable; real OS fallback behavior needs device testing. |
| Cold start/logout | Native actions persist until Flutter/auth is ready; stale/expired/version-superseded actions are dropped and valid actions consumed once. Logout dispatches native pending-action clear, attempts VoIP unregister, and retains existing FCM cleanup. |

## Host evidence

- Flutter targeted call/VoIP tests: 21 passed after handoff correction (B12C.1, B12C.2, B12C call/widget files). An additional B12C.1 end/expiry test was then included in the passing full suite.
- `flutter analyze`: no issues. Full `flutter test`: **134 passed, 2 skipped**. The first full run exposed a test-harness logout stall on the missing native method channel; native pending-action clearing is now dispatched without holding logout open. The second full run passed.
- Android JUnit `NativeCallDeliveryTest` covers data-only event parsing, duplicate/older/newer policy, expiry, stable ID and full-screen gate. **Not executed:** Android SDK absent on this Windows host.
- iOS XCTest `RunnerTests` covers deterministic UUID, version and expiry policy. **Not executed:** Xcode/iOS toolchain unavailable on Windows.
- Native code and manifest/project inclusion inspected statically. This is not proof of platform compilation or PushKit/FCM delivery.
- No backend or assets source files changed; no Git commit.

## Device and account blockers

Real Firebase Android/iOS project config, APNs VoIP key/certificate, matching Apple Push Notifications/VoIP signing capability and provisioning profile, physical iPhone and Android devices, Android SDK, macOS/Xcode build, LiveKit/TURN test service and authenticated end-to-end call accounts are required. Check Play full-screen intent eligibility and iOS PushKit policy on physical signed builds. A real token may receive `voip_environment_mismatch` unless the backend APNs environment matches the build (`sandbox` for development, `production` for TestFlight/App Store).

If `/devices/voip/{id}` is unreachable during logout, the app still clears its local session and device ID; server-side credential removal cannot be confirmed until a real authenticated cleanup succeeds. This is a device/security validation item, not a claimed successful unregister.

## Not verified

Actual APNs/FCM receipt in foreground/background/killed states; OS display of duplicate/expired pushes; CallKit answer/audio and cancellation across process death; heads-up/full-screen behavior and notification-permission denial; Bluetooth/media routing; backend side effects and token unregister on real devices; Kotlin/Swift compilation; signed AAB/IPA. No fake Firebase or Apple credentials were created.
