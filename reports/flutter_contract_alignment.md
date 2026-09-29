# Flutter Contract Alignment — 2026-09-23

Kapsam: yalnız Flutter domain, DTO, application provider, minimum demo-badge koşulları, test ve manuel smoke aracı. Backend B1–B4 şemaları yalnız okundu; B5 ve B6 entegrasyonu yapılmadı.

## Domain ve DTO eşlemesi

- **Transit:** Null `startAt/exactAt/endAt`, `exact` ve bilinmeyen durum, natal gezegen/açı/ev hedefleri, orijinal hedef türü, çoklu `TransitPass`, affected houses, clipping, tam sayı güç, orb, applying, motor/scoring sürümü ve metadata korunur. `TransitWindow` ayrıca response gruplarını, ingressleri ve zarf metadata'sını taşır. Eski UI için `getTransits()` liste döndürür.
- **Daily Frequency:** Dokuz B4 yaşam alanı `scores` içinde trend, strength ve factorIds ile taşınır. `importantHours`, `influences/sourceFactors`, `messageContext`, timezone ve sürümler eklenmiştir. Eski Home `metrics[]` projeksiyonunu kullanmaya devam eder.
- **Cosmic Calendar:** B4 ay fazları, station, ingress ve aspect tipleri; secondary planet, aspect, eclipse subtype/magnitude, node distance, longitude/degree ve metadata korunur. Bilinmeyen tür `unknown` + `rawType` olur; başka bir türe dönüştürülmez. `CosmicCalendarWindow` zarf metadata'sını korur.
- **Natal:** `warnings`, `houseRulers`, engine/version, kind, computedAt, requested house system ve typed subject eklenmiştir. Gezegen latitude/speed ve raporlanan degree/minute, ev degree/minute ve aspect raw nature taşınır; server dağılımları ve diğer yardımcı alanlar `sourceMetadata` içinde saklanır.
- **Moon:** `ageDays` ve `cycleProgress` ayrı alanlardır. API yalnız ageDays sağladığından cycleProgress uydurulmaz (`null`); elongation ve sonraki faz bilgisi korunur.
- **Saved People:** `SavedPersonDto → SavedPerson` B1 kullanıcı şemasına göre ilişki, zaman bilinirliği, doğum ve konum alanlarıyla uygulanmıştır. Backend şeması `updated_at` sağlamadığı için `updatedAt` icat edilmedi. B5 compatibility endpoint çağrısı yoktur.
- **Forecast:** Günlük/haftalık horoscope, aylık ve yıllık forecast için typed modeller; skorlar, faktörler, önemli saat/tarihler, dönemler, transitler, olaylar, ev aktivasyonları, ingressler, personal events ve solar return korunur. B6 prose alanı varsayılmaz.

## Provider wiring

`APP_DATA_SOURCE=mock` mevcut MockAuthRepository, MockAstrologyService ve MockAstroAIRepository davranışını korur. `APP_DATA_SOURCE=api` FastAPI JWT `ApiAuthRepository`, B1–B4 `ApiAstrologyService` ve B6 öncesi `DisabledApiAstroAIRepository` seçer. Karar application/config provider katmanındadır; widget'larda repository seçimi yoktur. Yalnız mevcut demo badge görünürlüğü merkezi `showDemoNoticeProvider` ile hizalanmıştır. API modunda Astro AI ekranı typed `AstroAIServiceUnavailable` durumuyla açılır, hayali endpoint çağrısı yapmaz.

## Test ve smoke

Fixture testleri null transit tarihlerini, exact status'u, natal angle/house ingress'i, pass'leri, kategori faktörlerini, B4 takvim enum'larını, natal uyarıları ve ruler'ları doğrular. `data_loss_regression_test.dart` fixture → DTO → domain alan bütünlüğünü sınar. `data_source_config_test.dart` mock/API seçimini ve geçersiz define hatalarını doğrular.

`tool/api_smoke.dart` CI dışı manuel araçtır. Önce yalnız `/health` ve `/ready` yoklar; `ASTRO_EMAIL`/`ASTRO_PASSWORD` verilirse login ve kişisel B1–B4 endpointleri de okunur. `ASTRO_REGISTER=1` olmadan hesap oluşturmaz. Credential kodda tutulmaz. Canlı backend bu fazda varsayılmadı; araç çalıştırılmış canlı kanıtı değildir.

Son yerel doğrulama: `flutter analyze` 0 issue; `flutter test --dart-define=APP_DATA_SOURCE=mock` 48 başarılı, 1 kasıtlı preview skip; `dart format --output=none --set-exit-if-changed lib test tool` 0 değişiklik. Smoke aracı URL verilmeden güvenli şekilde bağlantı açmadan çıktı; canlı endpoint smoke yapılmadı.

## Açık konular

- Backend transit API sabit `range` değerleri kullanıyor; mevcut serbest `from/to` arayüzü yaklaşık aralığa eşleniyor. Tam serbest interval için sözleşme değişikliği gerekir.
- Mevcut UI servis arayüzü transit/takvim listesini tüketir; tam zarf metadata'sı yeni API-specific window metotlarında mevcut, fakat UI bunu henüz göstermiyor.
- `SavedPersonResponse` şemasında `updated_at` yok. Bu alan backend değiştirilmeden sağlanamaz.
- Canlı API smoke, Android/iOS build ve gerçek kullanıcı akışı backend/SDK ortamı olmadan doğrulanmadı.

Claude-owned backend files modified by Codex: **0**.
