# B12B changed-file manifest

The repository has no baseline commit; this is the explicit B12B write record. Paths are relative to `C:/astrofrekans`. No backend or asset file was written.

| FILE | ACTION | PURPOSE |
| --- | --- | --- |
| pubspec.yaml | MODIFIED | Add official FlutterFire and image-picker dependencies. |
| pubspec.lock | MODIFIED | Lock resolved B12B dependency versions. |
| lib/app/app.dart | MODIFIED | Route allowlisted push taps through GoRouter. |
| lib/core/config/firebase_client.dart | MODIFIED | Central Firebase capability/bootstrap state without fake config. |
| lib/core/localization/b12_copy.dart | MODIFIED | Turkish/English B12B interface and error copy. |
| lib/core/network/api_client.dart | MODIFIED | Required list PUT, map DELETE, and idempotency-header requests. |
| lib/core/network/api_error.dart | MODIFIED | Parse Retry-After and stable errors. |
| lib/core/network/api_exception.dart | MODIFIED | Carry retry cooldown metadata. |
| lib/core/network/auth_interceptor.dart | MODIFIED | Keep auth capabilities endpoint public. |
| lib/core/routing/app_router.dart | MODIFIED | Register marketplace, order, appointment, chat and expert routes. |
| lib/core/routing/app_routes.dart | MODIFIED | Define typed route paths. |
| lib/core/widgets/api_state_view.dart | MODIFIED | Map B12B API codes to user-friendly states. |
| lib/features/auth/application/session_controller.dart | MODIFIED | Start permitted push registration after auth and clean up on logout. |
| lib/features/splash/presentation/splash_screen.dart | MODIFIED | Start central Firebase bootstrap without blocking non-Firebase features. |
| lib/features/explore/presentation/explore_screen.dart | MODIFIED | Link consulting entry to expert marketplace. |
| lib/features/profile/presentation/profile_screen.dart | MODIFIED | Add account entries and contextual notification permission. |
| lib/features/marketplace/data/marketplace_models.dart | CREATED | Typed, lossless expert/service/slot/order/appointment/review/availability DTOs. |
| lib/features/marketplace/data/marketplace_repository.dart | CREATED | Backend-mediated marketplace and expert-workspace contract adapter. |
| lib/features/marketplace/presentation/marketplace_screens.dart | CREATED | Expert discovery, filters, detail, reviews and favorites UI. |
| lib/features/marketplace/presentation/booking_screens.dart | CREATED | Slots, orders, appointments, consent and reviews UI. |
| lib/features/marketplace/presentation/expert_workspace_screen.dart | CREATED | Minimal expert profile, orders, appointments and schedule overview. |
| lib/features/consultation/data/consultation_models.dart | CREATED | Typed chat, message, attachment, policy and device DTOs. |
| lib/features/consultation/data/consultation_repository.dart | CREATED | FastAPI-mediated conversation, message, attachment and device adapter. |
| lib/features/consultation/data/realtime_services.dart | CREATED | Firestore read listener and scoped RTDB presence/typing adapter. |
| lib/features/consultation/data/attachment_service.dart | CREATED | Validated picker, authorized Storage upload and finalize coordinator. |
| lib/features/consultation/data/push_service.dart | CREATED | Explicit FCM permission, token lifecycle and allowlisted navigation. |
| lib/features/consultation/application/chat_controller.dart | CREATED | History/realtime merge, idempotent send, upload and listener lifecycle. |
| lib/features/consultation/presentation/consultation_screens.dart | CREATED | Conversation list, backend-gated opening and chat UI. |
| test/fixtures/b12b_schema_samples.json | CREATED | Sanitized B12B API contract fixtures. |
| test/core/b12b_contract_test.dart | CREATED | DTO, timezone, status, consent and push-route tests. |
| test/core/b12b_repository_test.dart | CREATED | Filter, idempotency, consent and send wire-contract tests. |
| test/core/b12b_live_smoke_test.dart | CREATED | Opt-in loopback disposable-account smoke. |
| test/core/b12b_perf_test.dart | CREATED | Host-side synthetic parse and byte-processing measurements. |
| test/features/b12b_chat_controller_test.dart | CREATED | History, realtime, pagination, send retry, deletion and attachment tests. |
| test/features/b12b_push_test.dart | CREATED | Permission, token-refresh, logout and route tests. |
| test/features/b12b_marketplace_widget_test.dart | CREATED | Discovery/search and large-text widget tests. |
| reports/b12b_changed_files.md | CREATED | This manifest. |
| reports/b12b_backend_contract_issues.md | CREATED | Contract gaps and cross-tier issues. |
| reports/b12b_integration_verification.md | CREATED | Verification results and limits. |
