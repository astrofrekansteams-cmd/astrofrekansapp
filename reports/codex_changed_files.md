# Codex değişiklik manifesti

Bu manifest, Git baseline commit bulunmadığı için bu çalışma sırasında Codex tarafından yapılan değişiklikleri kaydeder. Başka oturumların veya Claude'un değişiklikleri bu listeye dahil değildir.

| FILE | ACTION | PURPOSE |
|---|---|---|
| `lib/core/network/api_client.dart` | MODIFIED | Dio transport, API base path, refresh ve session invalidation bağlantısı |
| `lib/core/network/api_exception.dart` | MODIFIED | API hata türleri ve alan doğrulama hataları |
| `lib/core/network/api_config.dart` | CREATED | Ortam/data-source Dart define konfigürasyonu ve HTTPS doğrulaması |
| `lib/core/network/api_error.dart` | CREATED | FastAPI ve Dio hata eşleme |
| `lib/core/network/api_response.dart` | CREATED | Tipli yanıt abstraction'ı |
| `lib/core/network/token_storage.dart` | CREATED | Secure token storage arayüzü ve adapter |
| `lib/core/network/request_id_interceptor.dart` | CREATED | İstek kimliği interceptor'ı |
| `lib/core/network/auth_interceptor.dart` | CREATED | Bearer token, single-flight refresh, tek retry ve expiry |
| `lib/core/network/api_health_service.dart` | CREATED | Health/ready API çağrıları |
| `lib/core/network/realtime_interfaces.dart` | CREATED | Firebase chat/presence/storage/push ve çağrı arayüzleri; credential yok |
| `lib/features/auth/data/api_auth_repository.dart` | CREATED | Mevcut FastAPI JWT auth adapter'ı ve repository seam |
| `lib/features/auth/data/auth_dto.dart` | CREATED | Auth/user response DTO'ları |
| `lib/core/astrology/data/api_contract_dto.dart` | CREATED | B1–B4 sözleşme DTO ve güvenli domain dönüşümleri |
| `lib/core/astrology/data/api_astrology_service.dart` | CREATED | B1–B4 HTTP astrology adapter'ı; B5 bilinçli olarak kapalı |
| `lib/features/astro_ai/data/disabled_api_astro_ai_repository.dart` | CREATED | B6 endpoint'i olmadan yapılandırılmamış AI adapter'ı |
| `test/core/auth_interceptor_test.dart` | CREATED | 10 eşzamanlı 401 başarı/hata refresh regresyonu |
| `test/core/api_contract_parsing_test.dart` | CREATED | B1–B4 fixture parsing ve model farkı testleri |
| `test/core/api_error_test.dart` | CREATED | FastAPI error envelope/422/403/404/429 testleri |
| `test/fixtures/b1_b4_contract_samples.json` | CREATED | Şema kaynaklı, canlı API olmayan sözleşme fixture'ı |
| `.github/workflows/flutter_ci.yml` | CREATED | Flutter format kontrolü, analiz ve test CI |
| `.github/workflows/backend_ci.yml` | CREATED | Gelecekte CI içinde backend pytest; backend kaynaklarına dokunmaz |
| `docs/firebase_integration.md` | CREATED | Firebase Auth/Firestore/RTDB/Storage/FCM mimarisi ve JWT geçiş yolu |
| `docs/realtime_architecture.md` | CREATED | Chat, presence, push ve çağrı arayüz/sorumluluk mimarisi |
| `docs/codemagic_release_plan.md` | CREATED | Android/iOS signing ve release hazırlık planı |
| `reports/backend_flutter_contract_mismatches.md` | CREATED | Backend/Flutter alan, tip ve şiddet farkları |
| `reports/build_size_audit.md` | CREATED | Asset bundle ölçümü ve APK ölçüm engeli |
| `reports/dead_code_audit.md` | CREATED | Kullanılmayan/tekrar eden kod incelemesi |
| `reports/dependency_audit.md` | CREATED | Paket kullanım incelemesi |
| `reports/mobile_security_audit.md` | CREATED | Mobil secret, token, HTTPS ve release riski incelemesi |
| `reports/localization_audit.md` | CREATED | TR/EN anahtar sayımı ve AZ kapsam notları |
| `reports/accessibility_audit.md` | CREATED | Erişilebilirlik incelemesi |
| `reports/codex_changed_files.md` | CREATED | Bu değişiklik manifesti |

Claude-owned backend files modified by Codex: **0**. `backend/` altında hiçbir dosya yazılmadı veya formatlanmadı. `pubspec.yaml`, analysis config, uygulama UI dosyaları ve mevcut asset görselleri değiştirilmedi.

## Flutter Contract Alignment fazı — ek değişiklikler

Önceki bölüm Integration Readiness fazının tarihsel manifestidir. Bu fazda yalnız aşağıdakiler yazıldı; önceki bölümdeki "UI dosyaları değiştirilmedi" ifadesi yalnız o faz için geçerlidir.

| FILE | ACTION | PURPOSE |
|---|---|---|
| `lib/core/astrology/domain/transit.dart` | MODIFIED | Nullable dates, exact/unknown status, hedefler, pass ve tam B4 zarfı |
| `lib/core/astrology/domain/daily_frequency.dart` | MODIFIED | Dokuz kategorili skor, faktör, saat ve kaynak modelleri |
| `lib/core/astrology/domain/cosmic_event.dart` | MODIFIED | B4 olay enum'ları, unknown fallback, eclipse/aspect metadata ve calendar zarfı |
| `lib/core/astrology/domain/natal_chart.dart` | MODIFIED | Uyarılar, ruler'lar, subject ve engine metadata |
| `lib/core/astrology/domain/moon_phase.dart` | MODIFIED | Gerçek ageDays ve nullable cycleProgress ayrımı |
| `lib/core/astrology/domain/saved_person.dart` | CREATED | B1 SavedPersonResponse domain modeli |
| `lib/core/astrology/domain/forecast.dart` | CREATED | Structured daily/weekly/monthly/annual modeller |
| `lib/core/astrology/domain/house_ingress.dart` | CREATED | B4 ingress tipi |
| `lib/core/astrology/domain/transit.freezed.dart` | GENERATED | Transit domain codegen |
| `lib/core/astrology/domain/transit.g.dart` | GENERATED | Transit JSON codegen |
| `lib/core/astrology/domain/daily_frequency.freezed.dart` | GENERATED | Daily domain codegen |
| `lib/core/astrology/domain/daily_frequency.g.dart` | GENERATED | Daily JSON codegen |
| `lib/core/astrology/domain/cosmic_event.freezed.dart` | GENERATED | Calendar domain codegen |
| `lib/core/astrology/domain/cosmic_event.g.dart` | GENERATED | Calendar JSON codegen |
| `lib/core/astrology/domain/natal_chart.freezed.dart` | GENERATED | Natal domain codegen |
| `lib/core/astrology/domain/natal_chart.g.dart` | GENERATED | Natal JSON codegen |
| `lib/core/astrology/domain/moon_phase.freezed.dart` | GENERATED | Moon domain codegen |
| `lib/core/astrology/domain/moon_phase.g.dart` | GENERATED | Moon JSON codegen |
| `lib/core/astrology/data/api_contract_dto.dart` | MODIFIED | B1–B4 DTO → domain kayıpsız dönüşüm ve forecast parsing |
| `lib/core/astrology/data/api_astrology_service.dart` | MODIFIED | Transit/calendar full window erişimi, eski liste sözleşmesi korunarak |
| `lib/core/astrology/astrology_providers.dart` | MODIFIED | Mock/API astrology servis seçimi |
| `lib/core/network/api_config.dart` | MODIFIED | Kontrollü define parsing ve demo notice provider |
| `lib/features/auth/application/session_controller.dart` | MODIFIED | JWT API repository merkezi provider bağlantısı |
| `lib/features/astro_ai/application/astro_ai_controller.dart` | MODIFIED | API modunda kontrollü B6 öncesi unavailable state |
| `lib/features/astro_ai/data/disabled_api_astro_ai_repository.dart` | MODIFIED | Tipli unavailable hatası |
| `lib/features/astro_ai/presentation/astro_ai_screen.dart` | MODIFIED | Demo badge görünürlüğünü merkezi config'e bağlama; tasarım aynı |
| `lib/features/auth/presentation/login_screen.dart` | MODIFIED | Demo badge görünürlüğünü merkezi config'e bağlama; tasarım aynı |
| `lib/features/auth/presentation/register_screen.dart` | MODIFIED | Demo badge görünürlüğünü merkezi config'e bağlama; tasarım aynı |
| `test/core/api_contract_parsing_test.dart` | MODIFIED | Yeni domain sözleşme assertion'ları |
| `test/core/data_loss_regression_test.dart` | CREATED | Fixture → DTO → domain veri kaybı regresyonu |
| `test/core/data_source_config_test.dart` | CREATED | Mock/API/invalid define ve Astro AI unavailable testleri |
| `tool/api_smoke.dart` | CREATED | Manuel, credential'sız varsayılan canlı API smoke harness |
| `reports/backend_flutter_contract_mismatches.md` | MODIFIED | Çözülen/açık sözleşme farkı durumları |
| `reports/mobile_security_audit.md` | MODIFIED | Provider wiring riskinin güncel durumu |
| `reports/flutter_contract_alignment.md` | CREATED | Bu fazın teknik raporu |
| `reports/codex_changed_files.md` | MODIFIED | Bu ek manifest |

Bu fazda `backend/`, migrations, horary, synastry, composite, davison veya compatibility dosyalarına write yapılmadı. Mevcut görsel assets değişmedi.

## Live API Integration Validation fazı — ek değişiklikler

| FILE | ACTION | PURPOSE |
|---|---|---|
| `tool/api_smoke.dart` | MODIFIED | Loopback/local güvenlik kontrolü, AuthTokenDto doğrulaması, aynı süreçten manuel çağrı |
| `tool/live_api_validation.dart` | CREATED | Yerel disposable hesap, canlı B1–B4 parse, negatif yanıt ve güvenli fixture yakalama |
| `test/fixtures/live_b1_b4_contract_samples.json` | GENERATED | Sanitized gerçek local backend yanıtları; token/credential içermez |
| `test/core/live_contract_fixture_test.dart` | CREATED | Yakalanan yanıtların ağsız DTO → domain regresyonu |
| `test/core/data_source_config_test.dart` | MODIFIED | Compile-time `APP_DATA_SOURCE=api` provider bağlantısı doğrulaması |
| `reports/live_api_contract_validation.md` | CREATED | Canlı sonuçlar, gözlemsel gecikme, negatif yanıt ve fark raporu |
| `reports/codex_changed_files.md` | MODIFIED | Bu fazın ayrı değişiklik manifesti |

Backend source files modified by Codex: **0**. Claude-owned B5 files modified by Codex: **0**. Docker runtime volume/cache verileri kaynak dosyası değişikliği olarak sayılmaz.

## B12C.1 Native Incoming Call Hardening

| FILE | ACTION | PURPOSE |
|---|---|---|
| `lib/features/calls/application/incoming_call_presentation.dart` | CREATED | Sunucu doğrulamalı sunum soyutlaması, Android/iOS/in-app/fake uygulamaları, duplicate/cancel/accept/decline yönetimi |
| `android/app/src/main/kotlin/com/astrofrekans/astrofrekans/MainActivity.kt` | MODIFIED | Android foreground çağrı bildirimi, güvenli native eylemler ve full-screen izin kontrolü |
| `android/app/src/main/kotlin/com/astrofrekans/astrofrekans/IncomingCallActivity.kt` | CREATED | Kilit ekranında yalnız genel çağrı bilgisi gösteren ayrı native yüzey |
| `android/app/src/main/AndroidManifest.xml` | MODIFIED | Gerçek çağrı bildirimi için kısıtlı full-screen intent izni |
| `lib/features/consultation/data/push_service.dart` | MODIFIED | Foreground call event akışı ve terminal event aktarımı |
| `lib/features/calls/application/call_controller.dart` | MODIFIED | Katılmadan hemen önce GET ile terminal durum doğrulaması |
| `lib/features/calls/presentation/call_screens.dart` | MODIFIED | Native Answer eyleminden doğrulanmış Flutter/LiveKit handoff |
| `lib/core/routing/app_router.dart` | MODIFIED | Answer route flag aktarımı |
| `lib/app/app.dart` | MODIFIED | Push/native action orkestrasyonu ve auth-gated cold-start yönlendirme |
| `test/features/b12b_push_test.dart` | MODIFIED | Genişletilen push gateway fake'i |
| `test/features/b12c_call_test.dart` | MODIFIED | Terminal server refresh regresyonu |
| `test/features/b12c1_incoming_call_test.dart` | CREATED | Fake presentation ile incoming, duplicate, cancel, stale, decline, cold-start/disposal testleri |
| `reports/mobile_release_blockers.md` | MODIFIED | Uygulanan ancak cihazda doğrulanmayan işler ve gerçek sunucu/platform blokları ayrımı |
| `reports/b12c1_native_call_contract_issues.md` | CREATED | B9 iOS VoIP ve Android background delivery eksiklerinin ayrı sözleşme raporu |
| `reports/codex_changed_files.md` | MODIFIED | Bu fazın değişiklik manifesti |

Bu fazda backend ve assets dosyalarına Codex tarafından yazılmadı; commit atılmadı.

## B12C.2 Native Call Delivery Bridge

| FILE | ACTION | PURPOSE |
|---|---|---|
| `android/app/src/main/kotlin/com/astrofrekans/astrofrekans/NativeCallDelivery.kt` | CREATED | Data-only call payload, persistent version/expiry/pending policy and generic notification |
| `android/app/src/main/kotlin/com/astrofrekans/astrofrekans/AstroCallMessagingService.kt` | CREATED | Native FCM call event receiver |
| `android/app/src/main/kotlin/com/astrofrekans/astrofrekans/MainActivity.kt` | MODIFIED | Auth-ready one-time native action handoff |
| `android/app/src/main/kotlin/com/astrofrekans/astrofrekans/IncomingCallActivity.kt` | MODIFIED | Expiry-aware lock-screen UI |
| `android/app/src/main/AndroidManifest.xml` | MODIFIED | Single messaging service, no duplicate FCM receiver service |
| `android/app/build.gradle.kts` | MODIFIED | Native unit test dependency |
| `android/app/src/test/kotlin/com/astrofrekans/astrofrekans/NativeCallDeliveryTest.kt` | CREATED | Android event/expiry/version/full-screen policy tests |
| `ios/Runner/VoipCallBridge.swift` | CREATED | PushKit token and CallKit call/action/audio bridge |
| `ios/Runner/AppDelegate.swift` | MODIFIED | Start and attach native VoIP bridge |
| `ios/Runner/Info.plist` | MODIFIED | VoIP and remote-notification background modes |
| `ios/Runner.xcodeproj/project.pbxproj` | MODIFIED | Include Swift bridge in Runner source build |
| `ios/RunnerTests/RunnerTests.swift` | MODIFIED | UUID, version and expiry policy tests |
| `lib/features/calls/data/voip_device_service.dart` | CREATED | Authenticated VoIP registration/rotation/invalidation/logout |
| `lib/features/calls/application/incoming_call_presentation.dart` | MODIFIED | iOS CallKit actions/reconcile/audio and Android pending actions |
| `lib/features/calls/presentation/call_screens.dart` | MODIFIED | LiveKit handoff and CallKit connected/end lifecycle |
| `lib/features/auth/application/session_controller.dart` | MODIFIED | VoIP start and logout cleanup |
| `lib/app/app.dart` | MODIFIED | Native action queue, limited reconciliation and typed error UX |
| `test/features/b12c1_incoming_call_test.dart` | MODIFIED | Preserve CallKit through answer; end/expiry regression |
| `test/features/b12c2_voip_device_test.dart` | CREATED | VoIP token lifecycle tests |
| `reports/b12c2_native_call_verification.md` | CREATED | Native implementation and verification boundary |
| `reports/b12c_integration_verification.md` | MODIFIED | B12C.2 addendum |
| `reports/mobile_release_blockers.md` | MODIFIED | Current platform/device blockers |
| `reports/device_test_matrix.md` | MODIFIED | Native delivery device scenarios |
| `reports/codex_changed_files.md` | MODIFIED | This manifest |

Backend modified: **0**. Assets modified: **0**. Git commit: **no**.

## B13B Flutter / native / store validation

Git baseline hâlâ yok; aşağıdaki liste bu fazdaki Codex değişikliklerinin manuel manifestidir. Backend veya assets altında write yapılmadı.

| FILE | ACTION | PURPOSE |
|---|---|---|
| `lib/core/network/api_config.dart` | MODIFIED | Production/release mock source fail-closed kontrolü |
| `lib/features/billing/application/paid_report_service.dart` | MODIFIED | B13A atomik rapor-kredi sözleşmesi, güvenli stable `consumer_ref`, kredi ayrıldıktan sonra da retry |
| `lib/features/astro_ai/data/api_astro_ai_repository.dart` | MODIFIED | `POST /ai/reports` 200/202 ve tipli 402/409 hata eşleme |
| `lib/features/billing/presentation/paid_reports_section.dart` | MODIFIED | Paid report 200 report / 202 job routing ve tipli kullanıcı mesajları |
| `lib/features/astro_ai/presentation/ai_library_screen.dart` | MODIFIED | Generic job ekranından paid report bypass seçeneklerini çıkarma |
| `test/core/data_source_config_test.dart` | MODIFIED | Production mock rejection regresyonu |
| `test/features/b12c_billing_test.dart` | MODIFIED | Backend entitlement lock ve aynı `consumer_ref` ile sıfır bakiye sonrası retry regresyonu |
| `test/features/b13b_paid_report_contract_test.dart` | CREATED | Report 200/202/402/409 HTTP kontrat testleri |
| `codemagic.yaml` | MODIFIED | AUTH_MODE/HTTPS guard, Android JUnit ve iOS RunnerTests gate'i |
| `docs/codemagic_release_plan.md` | MODIFIED | B13B CI doğrulama sınırı ve native gate dokümantasyonu |
| `reports/device_test_matrix.md` | MODIFIED | Cihaz/OS/build/environment/date/status/evidence alanlarıyla NOT RUN matrisi |
| `reports/mobile_release_blockers.md` | MODIFIED | OPEN/CLOSED blocker, owner ve kapanış kanıtı |
| `reports/b13b_flutter_release_validation.md` | CREATED | Baseline/final kanıt, native/store blokları, privacy inventory ve release önerisi |
| `reports/codex_changed_files.md` | MODIFIED | B13B değişiklik manifesti |

Backend source modified by Codex: **0**. Assets modified: **0**. Git commit: **no**.

## B13C real environment / native / device validation

Validation-only phase. No Flutter/native/backend/assets product code, credential, signing input or build artifact was created or changed. No commit or store submission.

| FILE | ACTION | PURPOSE |
|---|---|---|
| `reports/b13c_real_environment_validation.md` | CREATED | Actual prerequisite inventory, executed/blocked test evidence and release verdict |
| `reports/b13c_store_validation.md` | CREATED | Apple/Google sandbox blockers, metadata gaps and source-only privacy inventory |
| `reports/device_test_matrix.md` | MODIFIED | B13C device-specific BLOCKED rows with OS/build/environment/audit timestamp/evidence |
| `reports/mobile_release_blockers.md` | MODIFIED | Current P0/P1 OPEN/PARTIAL/CLOSED gates and owners |
| `reports/codex_changed_files.md` | MODIFIED | B13C manual change manifest; repo still has no baseline commit |

Backend modified by Codex: **0**. Assets modified: **0**. Git commit: **no**.

## 2026-09-26 reference UI refresh

Existing artwork reused; no image generation, backend changes or commit.

| FILE | ACTION | PURPOSE |
|---|---|---|
| web/index.html | CREATED | Minimal Flutter browser bootstrap for profile preview |
| test/preview_capture_test.dart | MODIFIED | Isolate visual captures into separate provider scopes |
| lib/core/assets/app_assets.dart | MODIFIED | Supplied entry logo path |
| pubspec.yaml | MODIFIED | Bundle assets/logo/1logo.png |
| lib/core/theme/app_colors.dart | MODIFIED | Reference-aligned dark surfaces |
| lib/core/widgets/astro_brand_logo.dart | CREATED | Full logo lockup without cropping |
| lib/core/widgets/astro_motion.dart | CREATED | Reduced-motion-aware entrance and pointer feedback |
| lib/core/widgets/widgets.dart | MODIFIED | Shared widget exports |
| lib/core/widgets/astro_background.dart | MODIFIED | Existing cosmic background throughout app |
| lib/core/widgets/astro_scaffold.dart | MODIFIED | Bounded desktop canvas |
| lib/core/widgets/astro_card.dart | MODIFIED | Interactive card feedback |
| lib/core/widgets/astro_bottom_navigation.dart | MODIFIED | Rounded navigation and selection motion |
| lib/core/widgets/api_state_view.dart | MODIFIED | Editorial page headings and entrance motion |
| lib/features/onboarding/presentation/onboarding_screen.dart | MODIFIED | Reference-inspired single welcome composition |
| lib/features/auth/presentation/login_screen.dart | MODIFIED | Supplied logo and backdrop contrast |
| lib/features/splash/presentation/splash_screen.dart | MODIFIED | Supplied logo |
| lib/features/home/presentation/home_screen.dart | MODIFIED | Staggered sections |
| lib/features/home/presentation/widgets/frequency_card.dart | MODIFIED | Larger editorial hero and moon artwork |
| lib/features/profile/presentation/profile_screen.dart | MODIFIED | Brand heading, larger identity and divided settings |
| lib/features/production/presentation/sky_detail_screens.dart | MODIFIED | Zodiac ring and selectable calendar grid using existing event dates |
| lib/features/production/presentation/divination_screen.dart | MODIFIED | Existing deck-back artwork before reading |
| test/features/ui_refresh_test.dart | CREATED | Logo, small/desktop layout and reduced motion checks |
| test/core/app_router_test.dart | MODIFIED | New welcome expectation and scroll-to-logout |
| test/features/b12b_marketplace_widget_test.dart | MODIFIED | Scroll outer page to expert at large text |
| test/features/b12c_premium_widget_test.dart | MODIFIED | Verify reachable content at large text |
| test/preview/home.png | GENERATED | Visual review capture |
| test/preview/astro_ai.png | GENERATED | Visual review capture |
| test/preview/astro_ai_chat.png | GENERATED | Visual review capture |
| test/preview/login.png | GENERATED | Visual review capture |
| test/preview/onboarding.png | GENERATED | Visual review capture |
| test/preview/profile.png | GENERATED | Visual review capture |
| reports/ui_before.png | GENERATED | Initial browser capture |
| reports/ui_after_welcome.png | GENERATED | Browser capture |
| reports/ui_after_login.png | GENERATED | Loaded login browser capture |
| reports/ui_debug.png | GENERATED | Preview loading diagnostic capture |
| reports/ui_test_run.log | GENERATED | Full Flutter test output |
| reports/ui_refresh_verification.md | CREATED | Scope and verification limits |
| reports/codex_changed_files.md | MODIFIED | Manual manifest |
