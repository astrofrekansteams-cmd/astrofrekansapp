# Live API Integration Validation — 2026-09-23

Kaynak: çalışan yerel Docker Compose (`backend/docker-compose.yml`), `ENVIRONMENT=local`, loopback `127.0.0.1:8000`. Backend source/migration/B5 dosyalarına yazılmadı. Bu bir yük testi değil; süreler tekil gözlemdir.

## Servis ve probe

| Servis / endpoint | Sonuç | Kanıt |
|---|---|---|
| PostgreSQL | Healthy | `docker compose ps`; `/ready` `checks.database=ok` |
| Redis | Healthy | `docker compose ps`; `/ready` `checks.cache=ok` |
| FastAPI | Healthy | `docker compose ps`; konteyner `ENVIRONMENT=local`, DB host `postgres`, Redis host `redis` |
| `GET /health` | HTTP 200, ~261 ms | `status=ok`, `app=Astrofrekans API`, `environment=local` |
| `GET /ready` | HTTP 200, ~22 ms | `status=ready`, database/cache/ephemeris `ok` |

## Canlı akış

Runtime'da üretilen sentetik `@example.com` hesap kullanıldı; credential hiçbir kaynak veya fixture dosyasına yazılmadı. `ApiAuthRepository.register` ve `.signIn` gerçek `TokenResponse`u `AuthTokenDto` ile parse etti. `signOut` çalıştı. Bilerek geçersiz erişim tokenı, **tek** korumalı istekte 401 → gerçek refresh → retry akışını tetikledi; token değeri loglanmadı. `/users/me` parse edildi. İş sonunda disposable kullanıcı mevcut `DELETE /users/me` endpoint'iyle silindi (`DISPOSABLE_USER_DELETED=true`).

`PUT /birth-profiles/me` sentetik 1992-05-14 doğum bilgisi, İstanbul koordinatları ve IANA timezone ile çalıştı. `GET` yanıtı `BirthProfileDto → BirthData` olarak parse edildi.

| Canlı endpoint | DTO/domain kanıtı | Son gözlemsel süre |
|---|---|---:|
| `/astrology/natal-chart/me` | 12 gezegen, 12 ev, 20 açı, açı noktaları, 12 ruler; `kind`, `subject`, `engine_version`, boş ama mevcut `warnings` | 46.5 ms |
| `/astrology/moon-phase` | `MoonPhaseDto → MoonPhase`, gerçek `age_days` | 26.9 ms |
| `/astrology/transits?range=day` | `TransitWindow`: 20 transit, 1 ingress, 21 pass, 3 null tarihli transit | 48.9 ms |
| `/astrology/transits?range=week` | 47 transit, 4 ingress, 49 pass, 2 null tarihli transit | 41.9 ms |
| `/astrology/transits?range=month` | 44 transit, 5 ingress, 45 pass, 3 null tarihli transit | 47.6 ms |
| `/astrology/daily-frequency` | 9 skor kategorisi, 4 önemli saat, 12 influence/factor; trend, strength, factorIds ve sürümler parse edildi | 28.1 ms |
| `/calendar/events` | 13 olay; ingress, dolunay, trine, station retrograde/direct, iki quarter, sextile, yeni ay parse edildi | 16.5 ms |
| `/horoscope/daily` | `HoroscopeForecast` typed parse | 29.7 ms |
| `/horoscope/weekly` | `HoroscopeForecast` typed parse | 16.8 ms |
| `/forecasts/monthly` | `MonthlyForecast` typed parse | 26.6 ms |
| `/forecasts/yearly` | `AnnualForecast` typed parse; yalnız bir çağrı/tur | 27.9 ms |

Önceki ilk cold gözlemde takvim ~571 ms, günlük horoscope ~885 ms idi; warm sonuçlar benchmark olarak yorumlanmamalı. `ApiAstrologyService` de ayrıca canlı POST natal, haftalık transit, günlük frekans, ay fazı ve takvim metotlarıyla sınandı: 12 gezegen, 47 transit, 9 skor, 13 olay döndü. B5 endpoint'i çağrılmadı.

Saved People: `POST /saved-people` başarılı; yanıt `SavedPersonDto → SavedPerson` parse edildi, `GET /saved-people` liste parse edildi, `DELETE /saved-people/{id}` başarılı. B1–B4 router'da `GET /saved-people/{id}` ve update endpoint'i yok; bu iki işlem denenmedi/uydurulmadı.

## Negatif yanıtlar

| Senaryo | HTTP | Flutter mapping |
|---|---:|---|
| Yanlış parola | 401 | `unauthorized`, `invalid_credentials` |
| Geçersiz transit range | 422 | `validation`, `validation_error` |
| Bearer olmadan `/users/me` | 401 | `unauthorized`, `unauthenticated` |
| Olmayan kaynak rotası | 404 | `notFound`, `not_found` |

Missing birth profile ayrı sınanmadı: Flutter kayıt akışı doğum tarihiyle profil yaratıyor. Rate limit spam yapılmadı; 429 yalnız mevcut unit mapping testi kapsamındadır.

## Fixture ve schema/live farkları

`test/fixtures/live_b1_b4_contract_samples.json`: `source=local_live_backend`, `captured_at=2026-09-23T07:43:17.417022Z`, `engine_version=1.0.0-de421`, `sanitized=true`; 13 bölüm, ~496 KB. Token, parola, e-posta, Authorization ve özel Windows yolu işareti yok. UUID'ler deterministik placeholder'a çevrildi; doğum verisi sentetiktir. `test/core/live_contract_fixture_test.dart` normal test takımında yalnız diskten okur, ağ kullanmaz. Schema-derived fixture korunmuştur.

Ortak 11 bölümün üst düzey alan anahtarları ile transit item, daily score ve source-factor anahtarları schema fixture ile canlı response arasında aynıydı. Schema calendar örneği bazı opsiyonel `aspect`, `secondary_planet`, eclipse ve pencere/metadata anahtarlarını atlamıştı; canlı yanıt bunları (çoğu null) içerir ve Flutter parser korur. Kritik semantik contract mismatch bulunmadı.

| ENDPOINT | DOCUMENTED/SCHEMA FIELD | LIVE FIELD | FLUTTER EXPECTATION | SEVERITY | ACTION |
|---|---|---|---|---|---|
| `/calendar/events` | Opsiyonel aspect/secondary/eclipses/metadata | Anahtarlar canlı yanıtta mevcut | Nullable alanlar korunur | Bilgi | Live fixture regresyonuna alındı; backend değişmedi. |
| `/saved-people/{id}` | ID ile GET/update şemada yok | Endpoint yok | CRUD isteğinde read/update mümkün değil | Düşük | Yalnız mevcut create/list/delete doğrulandı; backend'e dokunulmadı. |

## Çalıştırılan doğrulamalar

- `flutter test tool/live_api_validation.dart`: canlı test geçti; yalnız manuel, normal CI takımına dahil değil.
- `tool/api_smoke.dart` aynı canlı test içinde gerçek backend'e karşı çalıştı ve tüm mevcut adımları geçti.
- `flutter test test/core/live_contract_fixture_test.dart`: 6/6 ağsız test geçti.
- `flutter test test/core/data_source_config_test.dart --dart-define=APP_DATA_SOURCE=api --dart-define=API_BASE_URL=http://127.0.0.1:8000`: 5/5 provider testi geçti; API modunda `ApiAuthRepository` ve `ApiAstrologyService` seçildi.
- `flutter analyze`: 0 issue.
- `flutter test --dart-define=APP_DATA_SOURCE=mock`: 55 başarılı, 1 kasıtlı preview skip. Live fixture testi bu normal takımda ağ kullanmadan geçti.
- `dart format --output=none --set-exit-if-changed lib test tool`: 0 değişiklik.

Backend source files modified by Codex: **0**. Claude-owned B5 files modified by Codex: **0**.
