# B13B/B13C physical-device validation matrix

## B13C current audit — 2026-09-25 04:43 UTC

No physical Android or iPhone, native build, Firebase project config, APNs, LiveKit or store sandbox was available to this session. In this table, `—` for device/OS/build means **no device/build exists**, not that metadata was omitted from a successful run. The timestamp is the environment audit, not a fabricated test execution time. Every listed physical test is **BLOCKED** by the named prerequisite; none is PASS or FAIL.

| Test | Device | OS | Build | Environment | Audit timestamp UTC | Result | Evidence/blocker |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Firebase init, email/password, ID token→FastAPI | Android — | — | — | Firebase absent | 2026-09-25 04:43 | BLOCKED | No SDK/device/native config/server credentials |
| Chat backend POST, Firestore listener/pagination, client write denied | Android — | — | — | Firebase absent | 2026-09-25 04:43 | BLOCKED | No project/device |
| Partner presence ACTIVE/READ_ONLY allow, stranger/SUSPENDED/CLOSED deny | Android — | — | — | Firebase absent | 2026-09-25 04:43 | BLOCKED | No RTDB project/device; B9 schema unchanged |
| Image intent/upload/finalize; invalid MIME/size and public URL denial | Android — | — | — | Firebase absent | 2026-09-25 04:43 | BLOCKED | No Storage project/device |
| FCM foreground/background/locked/killed; incoming/answered/cancelled/missed | Android — | — | — | FCM absent | 2026-09-25 04:43 | BLOCKED | No real config/server credentials/device |
| v10 one ring, duplicate v10/v9 ignored, cancel v11 dismiss, late v10 ignored | Android — | — | — | FCM absent | 2026-09-25 04:43 | BLOCKED | No native compile/integration harness/device |
| Android 14+ full-screen allowed vs heads-up denied | Android — | — | — | No device | 2026-09-25 04:43 | BLOCKED | No OS behavior evidence |
| Notification/mic/camera grant-deny; audio-only avoids camera | Android — | — | — | No device | 2026-09-25 04:43 | BLOCKED | No physical permission flow |
| Audio/video/mute/camera switch/speaker/earpiece/Bluetooth | Android — | — | — | LiveKit absent | 2026-09-25 04:43 | BLOCKED | No LiveKit/device |
| Wi-Fi→mobile, short/long disconnect, duplicate identity, TURN/NAT | Android — | — | — | LiveKit absent | 2026-09-25 04:43 | BLOCKED | Requires configured service and two/network-varied devices |
| Play products, purchase/pending/verify/unlock/restore/refund | Android — | — | — | Play absent | 2026-09-25 04:43 | BLOCKED | No AAB/track/tester/server credentials |
| Cold launch/home/natal/transit/marketplace/50-chat/video timing | Android — | — | — | No build | 2026-09-25 04:43 | BLOCKED | No device profiler/build |
| TalkBack critical flows and 1.6×/2× text | Android — | — | — | No build | 2026-09-25 04:43 | BLOCKED | No physical accessibility run |
| Firebase init/Auth/chat/presence/Storage | iPhone — | — | — | Firebase absent | 2026-09-25 04:43 | BLOCKED | No plist/signed device/server credentials |
| FCM foreground/background/killed and notification permission | iPhone — | — | — | APNs/Firebase absent | 2026-09-25 04:43 | BLOCKED | No signed iPhone |
| PKPushRegistry token→backend registration→APNs VoIP→CallKit UI | iPhone — | — | — | APNs absent | 2026-09-25 04:43 | BLOCKED | No .p8/profile/signed iPhone |
| Duplicate same call/version, expiry and terminal cancellation | iPhone — | — | — | APNs absent | 2026-09-25 04:43 | BLOCKED | Swift XCTest/device delivery not executed |
| CallKit answer GET→join→LiveKit; decline POST /end | iPhone — | — | — | APNs/LiveKit absent | 2026-09-25 04:43 | BLOCKED | No signed iPhone/server services |
| CallKit audio, mute, speaker/earpiece/Bluetooth, background | iPhone — | — | — | LiveKit absent | 2026-09-25 04:43 | BLOCKED | No device/media service |
| Video/camera switch, reconnect, duplicate identity, TURN | iPhone — | — | — | LiveKit absent | 2026-09-25 04:43 | BLOCKED | No device/media service |
| StoreKit products/purchase/verify/unlock/restore/refund | iPhone — | — | — | Apple Store absent | 2026-09-25 04:43 | BLOCKED | No IPA/sandbox tester/server credentials |
| Paid credit→report/job→same `consumer_ref` retry | Android/iPhone — | — | — | Stores/OpenAI absent | 2026-09-25 04:43 | BLOCKED | Host contract tests are not real credit proof |
| Cold launch/home/natal/transit/marketplace/50-chat/video timing | iPhone — | — | — | No IPA | 2026-09-25 04:43 | BLOCKED | No physical profiler/build |
| VoiceOver critical flows and Dynamic Type | iPhone — | — | — | No IPA | 2026-09-25 04:43 | BLOCKED | No physical accessibility run |

Host-only `flutter analyze` and `flutter test` passed separately; see `b13c_real_environment_validation.md`. The B13B historical matrix below remains unchanged.

Audit date: 2026-09-25. **No physical Android or iPhone was connected.** `flutter doctor -v` listed Windows, Chrome and Edge only; Android SDK and iOS/macOS build access were absent. The date below is the audit date, **not a claimed test-execution timestamp**. No native build number or store environment exists. Every unexecuted scenario is `NOT RUN`, never PASS.

| Scenario | Device | OS | Build number | Environment | Audit date | Result | Evidence / prerequisite |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Firebase initialize, Auth email/password → FastAPI account | Android physical — | — | — | Firebase unconfigured | 2026-09-25 | NOT RUN | No `google-services.json` or server Firebase credentials |
| Firestore conversation/open, backend POST, listener, pagination; direct write denied | Android physical — | — | — | Firebase unconfigured | 2026-09-25 | NOT RUN | Firebase project/rules and device required |
| RTDB partner presence ACTIVE/READ_ONLY allowed, SUSPENDED/CLOSED and unrelated denied | Android physical — | — | — | Firebase unconfigured | 2026-09-25 | NOT RUN | B9 schema frozen; real-project rules/device required |
| Storage intent/upload/finalize/image; invalid MIME/size denied, no public URL | Android physical — | — | — | Firebase unconfigured | 2026-09-25 | NOT RUN | Firebase project/backend required |
| FCM foreground/background/locked/killed and cold-start navigation | Android physical — | — | — | FCM unconfigured | 2026-09-25 | NOT RUN | Real config, server credentials, device required |
| Data-only HIGH incoming/answered/cancelled/missed and reconciliation | Android physical — | — | — | FCM unconfigured | 2026-09-25 | NOT RUN | `AstroCallMessagingService` not natively compiled here |
| v10 duplicate, v9 old, v11 cancel, late v10 ignored | Android physical — | — | — | FCM unconfigured | 2026-09-25 | NOT RUN | Kotlin JUnit not executed; device integration absent |
| Full-screen allowed versus denied heads-up on Android 14+ | Android physical — | — | — | No device | 2026-09-25 | NOT RUN | Manifest permission is not OS eligibility evidence |
| Notification, mic and camera grant/deny; audio-only does not ask camera | Android physical — | — | — | No device | 2026-09-25 | NOT RUN | Physical permission flow required |
| Native answer/decline after cold start; authenticated GET then join/end | Android physical — | — | — | No device | 2026-09-25 | NOT RUN | Native compile and backend/mobile E2E required |
| Call audio/video, mute, camera switch, speaker/earpiece/Bluetooth | Android physical — | — | — | LiveKit unconfigured | 2026-09-25 | NOT RUN | Production/staging LiveKit + device required |
| Wi-Fi→mobile, <45s and >45s loss, duplicate identity, TURN/NAT | Android physical — | — | — | LiveKit unconfigured | 2026-09-25 | NOT RUN | Carrier/restricted networks and two devices required |
| Play product discovery, purchase, backend verify and Premium unlock | Android physical — | — | — | Play unconfigured | 2026-09-25 | NOT RUN | Signed internal/test track + license tester required |
| Play pending, cancel/fail, restore after reinstall, refund/revoke | Android physical — | — | — | Play unconfigured | 2026-09-25 | NOT RUN | Play Console/store backend credentials required |
| Paid credit purchase, stable `consumer_ref`, retry, no duplicate charge | Android physical — | — | — | Play/OpenAI unconfigured | 2026-09-25 | NOT RUN | Contract unit tests only; real store and AI required |
| Cold launch, home, natal, transit, marketplace, 50-message chat, video UI timings | Android physical — | — | — | No release build | 2026-09-25 | NOT RUN | Device profiler and instrumented build required |
| TalkBack login/marketplace/chat/call/purchase, 1.6×/2× text | Android physical — | — | — | No release build | 2026-09-25 | NOT RUN | Physical accessibility review required |
| Firebase initialize, Auth email/password → FastAPI account | iPhone physical — | — | — | Firebase unconfigured | 2026-09-25 | NOT RUN | No `GoogleService-Info.plist` or server credentials |
| Firestore chat, RTDB presence ACL, Storage upload/finalize | iPhone physical — | — | — | Firebase unconfigured | 2026-09-25 | NOT RUN | Real signed app, Firebase project, backend required |
| FCM foreground/background/killed and notification permission | iPhone physical — | — | — | APNs/Firebase unconfigured | 2026-09-25 | NOT RUN | Signed device build and APNs setup required |
| PushKit token register/rotate/invalidate/logout | iPhone physical — | — | — | APNs VoIP unconfigured | 2026-09-25 | NOT RUN | Signed entitlement and backend APNs credentials required |
| VoIP incoming → prompt CallKit report/completion; OS call screen | iPhone physical — | — | — | APNs VoIP unconfigured | 2026-09-25 | NOT RUN | `VoipCallBridge.swift` not compiled here |
| Duplicate/version/expiry, terminal cancel/miss, stable CallKit UUID | iPhone physical — | — | — | APNs VoIP unconfigured | 2026-09-25 | NOT RUN | RunnerTests not executed; device delivery required |
| CallKit answer GET→join→LiveKit; decline POST /end; logout cleanup | iPhone physical — | — | — | APNs/LiveKit unconfigured | 2026-09-25 | NOT RUN | Signed app and server E2E required |
| CallKit audio activation, mute, speaker/earpiece/Bluetooth, background | iPhone physical — | — | — | LiveKit unconfigured | 2026-09-25 | NOT RUN | Physical iPhone required |
| Video, camera permissions/switch/rotation, network loss and duplicate identity | iPhone physical — | — | — | LiveKit unconfigured | 2026-09-25 | NOT RUN | LiveKit/TURN and two devices required |
| StoreKit product discovery, sandbox purchase, backend verify/unlock | iPhone physical — | — | — | Apple Store unconfigured | 2026-09-25 | NOT RUN | App Store Connect, signing, sandbox user required |
| StoreKit pending/cancel/fail, restore, refund/revoke | iPhone physical — | — | — | Apple Store unconfigured | 2026-09-25 | NOT RUN | Signed app and Apple server credentials required |
| Purchase callback succeeds while backend inactive: remains locked | iPhone physical — | — | — | Apple Store unconfigured | 2026-09-25 | NOT RUN | Host fake regression passes; sandbox/device not run |
| Paid credit purchase, report/job, stable `consumer_ref` retry | iPhone physical — | — | — | Apple/OpenAI unconfigured | 2026-09-25 | NOT RUN | Host contract tests only; real E2E required |
| Cold launch/home/natal/transit/marketplace/50-chat/video UI timings | iPhone physical — | — | — | No IPA | 2026-09-25 | NOT RUN | Signed device build and profiler required |
| VoiceOver critical screens and Dynamic Type 1.6×/2× | iPhone physical — | — | — | No IPA | 2026-09-25 | NOT RUN | Physical accessibility review required |

Host-only Flutter and Dart test results are documented in `b13b_flutter_release_validation.md`; they are not device rows or native-build evidence.
