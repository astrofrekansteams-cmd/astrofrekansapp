# Flutter B12A change manifest

The repository has no usable baseline commit; this manifest records B12A writes. `backend/` was read-only throughout this phase. No assets were generated, renamed, or resized.

| FILE | ACTION | PURPOSE |
|---|---|---|
| `pubspec.yaml` | MODIFIED | Add verified FlutterFire core/auth dependencies |
| `pubspec.lock` | MODIFIED | Lock resolved FlutterFire dependency graph |
| `lib/core/assets/divination_asset_resolver.dart` | CREATED | Resolve backend deck keys only to bundled card assets |
| `lib/core/astrology/data/api_astrology_service.dart` | MODIFIED | Fetch backend transit windows by range |
| `lib/core/astrology/data/production_models.dart` | CREATED | Lossless B5–B11 contract models |
| `lib/core/astrology/data/production_repository.dart` | CREATED | Saved people, horary, compatibility, divination, forecasts and calendar API |
| `lib/core/config/firebase_client.dart` | CREATED | Real-config-only Firebase SDK and push cleanup seam |
| `lib/core/localization/b12_copy.dart` | CREATED | TR/EN production integration copy |
| `lib/core/network/api_client.dart` | MODIFIED | Token-provider transport and list/delete methods |
| `lib/core/network/api_config.dart` | MODIFIED | Environment/auth modes and production URL guard |
| `lib/core/network/api_error.dart` | MODIFIED | Preserve missing Firebase configuration as a stable UI error |
| `lib/core/network/auth_interceptor.dart` | MODIFIED | Single-flight JWT/Firebase refresh and bounded retry |
| `lib/core/network/token_provider.dart` | CREATED | Local JWT, Firebase ID token, and hybrid selection |
| `lib/core/routing/app_router.dart` | MODIFIED | B12A routes in existing router |
| `lib/core/routing/app_routes.dart` | MODIFIED | Central route names |
| `lib/core/widgets/api_state_view.dart` | CREATED | Loading, empty, error, retry, facts and factor widgets |
| `lib/features/astro_ai/application/astro_ai_controller.dart` | MODIFIED | API conversation stream, cancellation and partial status |
| `lib/features/astro_ai/data/ai_models.dart` | CREATED | Conversation, message, report and job DTOs |
| `lib/features/astro_ai/data/api_astro_ai_repository.dart` | CREATED | B6 chat, SSE, report and bounded job-poll client |
| `lib/features/astro_ai/domain/astro_ai_repository.dart` | MODIFIED | Metadata stream event |
| `lib/features/astro_ai/domain/chat_message.dart` | MODIFIED | Partial/cancelled message states |
| `lib/features/astro_ai/domain/chat_message.g.dart` | GENERATED | Serialization for message states |
| `lib/features/astro_ai/presentation/ai_library_screen.dart` | CREATED | Conversations, reports and jobs UI |
| `lib/features/astro_ai/presentation/astro_ai_screen.dart` | MODIFIED | API error, stop and reports entry |
| `lib/features/astro_ai/presentation/widgets/chat_bubble.dart` | MODIFIED | Partial/cancelled display |
| `lib/features/auth/application/session_controller.dart` | MODIFIED | Single identity state and social/login/logout handling |
| `lib/features/auth/data/api_auth_repository.dart` | MODIFIED | JWT-compatible profile API and adapter selection |
| `lib/features/auth/data/identity_session.dart` | CREATED | Local JWT/Firebase/hybrid identity adapters |
| `lib/features/auth/presentation/login_screen.dart` | MODIFIED | Clear configuration error |
| `lib/features/auth/presentation/widgets/social_auth_row.dart` | MODIFIED | Social identity seam |
| `lib/features/explore/presentation/explore_screen.dart` | MODIFIED | Production feature navigation |
| `lib/features/production/application/action_state.dart` | CREATED | Safe mutation state |
| `lib/features/production/application/core_providers.dart` | CREATED | Natal/transit/frequency/calendar providers |
| `lib/features/production/presentation/birth_form.dart` | CREATED | Validated birth/person form |
| `lib/features/production/presentation/divination_screen.dart` | CREATED | Backend-owned Tarot/Rune/Katina draw UI |
| `lib/features/production/presentation/forecast_screen.dart` | CREATED | Daily/weekly/monthly/yearly structured facts UI |
| `lib/features/production/presentation/profile_data_screens.dart` | CREATED | Profile, birth and saved people UI |
| `lib/features/production/presentation/relationship_screens.dart` | CREATED | Horary and three compatibility modes |
| `lib/features/production/presentation/sky_detail_screens.dart` | CREATED | Natal, transit, calendar and frequency details |
| `lib/features/profile/presentation/profile_screen.dart` | MODIFIED | B12A menu routes |
| `lib/features/shell/app_shell.dart` | MODIFIED | Cancel AI stream on tab leave |
| `test/core/b12a_contract_test.dart` | CREATED | B5–B11 sanitized contract parsing |
| `test/core/b12a_network_test.dart` | CREATED | Concurrent token refresh, SSE and polling tests |
| `test/core/api_error_test.dart` | MODIFIED | Firebase configuration error regression test |
| `test/core/data_source_config_test.dart` | MODIFIED | Mock/API and auth-mode provider selection |
| `test/features/b12a_state_widget_test.dart` | CREATED | Error/loading/empty/retry/text-scale widget tests |
| `test/fixtures/b12a_schema_samples.json` | CREATED | Sanitized AI/report/expert schema samples |
| `test/fixtures/live_b5_b11_contract_samples.json` | CREATED | Sanitized live contract samples |
| `tool/b12a_live_validation.dart` | CREATED | Disposable-account local backend smoke |
| `reports/b12a_live_timings.json` | CREATED | Local remote HTTP timings, not device timings |
| `reports/b12a_backend_contract_issues.md` | CREATED | Saved-person API gaps and safe handling |
| `reports/b12a_integration_verification.md` | CREATED | B12A verification and blockers |
| `docs/firebase_integration.md` | MODIFIED | Current Flutter Firebase integration/config status |
| `reports/b12a_changed_files.md` | CREATED | This change manifest |

Backend files modified by Codex: **0**. Existing `assets/` files modified by Codex: **0**. No commit was created.
