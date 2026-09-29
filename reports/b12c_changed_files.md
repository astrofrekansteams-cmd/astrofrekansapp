# B12C changed-file manifest

Git has no baseline commit in this checkout, so this manifest records Codex-owned B12C writes rather than a Git diff.

| FILE | ACTION | PURPOSE |
| --- | --- | --- |
| `pubspec.yaml` | MODIFIED | LiveKit, store billing, permission and secure external handoff dependencies |
| `pubspec.lock` | MODIFIED | Resolved dependencies |
| `lib/app/app.dart` | MODIFIED | Authenticated deep-link queue, entitlement startup, 2× text scaling |
| `lib/core/routing/app_routes.dart` | MODIFIED | Call/history/order routes |
| `lib/core/routing/app_router.dart` | MODIFIED | Call and Premium production screens |
| `lib/core/routing/pending_deep_links.dart` | CREATED | Cold-start push queue/deduplication |
| `lib/features/astro_ai/data/api_astro_ai_repository.dart` | MODIFIED | Typed paid-report generator interface |
| `lib/features/astro_ai/presentation/ai_library_screen.dart` | MODIFIED | Verified-credit report section |
| `lib/features/billing/application/entitlement_controller.dart` | CREATED | Backend-authoritative Premium/restore lifecycle |
| `lib/features/billing/application/paid_report_service.dart` | CREATED | Stable report-credit consumer reference |
| `lib/features/billing/data/billing_models.dart` | CREATED | B11 typed catalog/entitlement/payment DTOs |
| `lib/features/billing/data/billing_repository.dart` | CREATED | B11 API adapter |
| `lib/features/billing/data/billing_service.dart` | CREATED | StoreKit/Play single purchase listener and adapters |
| `lib/features/billing/presentation/premium_screen.dart` | CREATED | Backend-verified Premium UI |
| `lib/features/billing/presentation/order_payment_section.dart` | CREATED | Separate expert/digital/review payment groups |
| `lib/features/billing/presentation/paid_reports_section.dart` | CREATED | Store-priced report-credit UI |
| `lib/features/calls/application/call_controller.dart` | CREATED | B10 call/media orchestration |
| `lib/features/calls/data/call_media_service.dart` | CREATED | LiveKit media and permissions abstraction |
| `lib/features/calls/data/call_models.dart` | CREATED | Typed B10 DTOs and redacted join grant |
| `lib/features/calls/data/call_repository.dart` | CREATED | B10 API adapter |
| `lib/features/calls/presentation/call_screens.dart` | CREATED | Audio/video/incoming/history UX |
| `lib/features/consultation/data/push_service.dart` | MODIFIED | B10 FCM event routes |
| `lib/features/marketplace/data/marketplace_models.dart` | MODIFIED | Order delivery type for call entry |
| `lib/features/marketplace/presentation/booking_screens.dart` | MODIFIED | Payment groups and call entry in order detail |
| `lib/features/profile/presentation/profile_screen.dart` | MODIFIED | Verified Premium badge and call history link |
| `android/app/src/main/AndroidManifest.xml` | MODIFIED | Call, notification and billing permissions |
| `android/app/build.gradle.kts` | MODIFIED | Firebase plugin, min SDK 24, no debug release signing |
| `android/settings.gradle.kts` | MODIFIED | Google Services Gradle plugin declaration |
| `ios/Runner/Info.plist` | MODIFIED | Camera/microphone usage descriptions |
| `ios/Podfile` | MODIFIED | Permission-handler iOS macros |
| `codemagic.yaml` | CREATED | Android/iOS release-candidate build workflows |
| `docs/codemagic_release_plan.md` | MODIFIED | Workflow prerequisites and signing status |
| `test/fixtures/b12c_contract_samples.json` | CREATED | Sanitized B10/B11 fixtures |
| `test/features/b12c_billing_test.dart` | CREATED | Billing/entitlement/report security regressions |
| `test/features/b12c_call_test.dart` | CREATED | Call/media/push regressions |
| `test/features/b12c_premium_widget_test.dart` | CREATED | 1.6×/2× Premium UI regression |
| `test/features/b12c_order_payment_widget_test.dart` | CREATED | Hybrid/review payment UI regression |
| `test/features/b12c_call_widget_test.dart` | CREATED | 2× call controls and host render check |
| `test/core/b12c_perf_test.dart` | CREATED | Host-side DTO benchmark |
| `test/core/b12c_security_test.dart` | CREATED | No sensitive persistence/logging source regression |
| `reports/b12c_changed_files.md` | CREATED | This manifest |
| `reports/b12c_backend_contract_issues.md` | CREATED | Backend-owned payment-contract gaps |
| `reports/b12c_integration_verification.md` | CREATED | Validation evidence and limits |
| `reports/mobile_release_blockers.md` | CREATED | Release gate inventory |
| `reports/device_test_matrix.md` | CREATED | Physical-device QA checklist |

Backend files modified by Codex: **0**. Assets modified: **0**. No Git commit was created.
