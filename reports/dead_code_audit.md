# Flutter dead code denetimi

Statik arama `lib/` ve `test/` kaynaklarında yapıldı; generated `.g.dart`/`.freezed.dart` ve B5 backend dosyaları değiştirilmedi. `flutter analyze` kullanılmayan import uyarılarını ayrıca kontrol eder. Hiçbir aday silinmedi.

| FILE | SYMBOL | USED? | SAFE_TO_REMOVE? | REASON |
|---|---|---|---|---|
| `lib/core/astrology/data/low_precision_ephemeris.dart` | `LowPrecisionEphemeris` | Hayır; dosyaya import/call bulunmadı | Muhtemelen, ayrıca doğrula | Mock servis kendi hesabını yapıyor; bu sınıf çağrı zincirinde görünmüyor. Silme bu fazın kapsamı dışında. |
| `lib/core/network/api_response.dart` | `ApiResponse<T>` | Henüz hayır | Hayır | Yeni network seam; sonraki endpointlerde request-id ile typed response taşıyabilir. |
| `lib/core/network/api_health_service.dart` | `ApiHealthService` | Henüz UI çağrısı yok | Hayır | İstenen debug/diagnostic servis, ekrana bağlanması bu fazda istenmedi. |
| `lib/features/astro_ai/data/disabled_api_astro_ai_repository.dart` | `DisabledApiAstroAIRepository` | Henüz provider override yok | Hayır | B6 kontratı gelene kadar açıkça devre dışı adapter. |
| `lib/core/assets/app_assets.dart` | `appIcon`, `brandLockupFull`, `brandLockupCompact`, `astroAiTyping`, `astroAiEmptyState`, `premiumCrystal` | Uygulama kodunda doğrudan referans bulunmadı | Hayır | Bazıları launcher/store veya gelecek ekranlar için; asset ve sabit silinmemeli. |
| `lib/core/assets/app_assets.dart` | `tarotCard`, `katinaCard`, `runeCard` | Testte var, feature ekranında henüz yok | Hayır | Kart feature'ları henüz implementation aşamasında değil. |

Risk: `rg` tabanlı bu tarama reflection/dinamik asset anahtarlarını kesin olarak kanıtlamaz. `dart analyze` sonucu ile birlikte yorumlanmalıdır.
