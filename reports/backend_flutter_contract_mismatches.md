# Backend ↔ Flutter sözleşme farkları

Kaynaklar: `docs/api_contracts.md`, `backend/app/schemas/{auth,user,astrology,forecast}.py`, B1–B4 route dosyaları ve mevcut Flutter domain modelleri. Backend dosyaları yalnız okundu. `test/fixtures/b1_b4_contract_samples.json` şema/belge örneklerinden oluşturulmuş sözleşme fixture'ıdır; canlı API yanıtı değildir.

| Backend field | Flutter field | Type | Severity | Recommended fix / status |
|---|---|---|---|---|
| `access_token`, `refresh_token` | Secure storage | Auth | Orta | **RESOLVED** — JWT repository API modunda bağlı; tokenlar ayrı secure storage alanlarında. |
| `/users/me` ve `/birth-profiles/me` | `UserProfile` | Ayrı kaynak | Orta | **RESOLVED** — auth adapter iki kaynağı birleştirir. |
| `birth_date/time/place`, `whole_sign` | `BirthData`, `HouseSystem` | İsim/enum | Düşük | **RESOLVED** — DTO dönüşümü ve test. |
| `planets[].retrograde`, `aspects[].aspect`, `angles` | Natal domain | İsim/nesting | Düşük | **RESOLVED** — DTO dönüşümü. |
| `warnings`, `house_rulers`, `engine_version`, `kind`, `subject` | `NatalChart` metadata | Veri kaybı | Orta | **RESOLVED** — typed alanlar; ilave kaynak dağılımları `sourceMetadata` içinde. |
| Transit null `start_at/exact_at/end_at` | `Transit` tarihleri | Nullability | Yüksek | **RESOLVED** — null uydurulmadan korunur. |
| `status: exact` ve bilinmeyen değerler | `TransitStatus` | Enum | Orta | **RESOLVED** — `exact`, `unknown` ve `rawStatus` var. |
| `strength: 0..100` | `strength`, `strengthScore` | Ölçek | Düşük | **RESOLVED** — hem eski 0..1 projeksiyon hem orijinal tam sayı korunur. |
| `natal_angle`, `house_ingress`, hedef alanları | `TransitSummary` | Hedef | Yüksek | **RESOLVED** — tür, açı, gezegen, ev ve raw hedef türü korunur. |
| `passes`, `affected_houses`, `window_clipped`, metadata | `Transit` | Çoklu geçiş | Yüksek | **RESOLVED** — typed pass ve alanlar, fixture regresyonu. |
| Transit response `ingresses`/window metadata | `TransitWindow` | Üst seviye zarf | Orta | **RESOLVED** — `toWindow()` ve API servisindeki `getTransitWindow()` korur; eski `getTransits()` liste projeksiyonudur. |
| `/astrology/transits` sabit `range` | `getTransits(from,to)` | İstek aralığı | Orta | **OPEN** — serbest tarih aralığı yaklaşık day/week/month/year'a eşlenir; API serbest aralık desteklemiyor. |
| `overall`, `scores` ve dokuz yaşam alanı | `DailyFrequency.scores` | Skor haritası | Yüksek | **RESOLVED** — bütün B4 alanları typed; mevcut `metrics` Home uyumluluğu için sürer. |
| `trend`, `strength`, `factor_ids`, `important_hours`, `influences` | Daily domain | Kaynak açıklanabilirliği | Yüksek | **RESOLVED** — kaynak ve saatler birebir; regresyon testi var. |
| `age_days`, `elongation`, `next_phase` | `MoonPhase` | Ayrı kavramlar | Orta | **RESOLVED** — `ageDays` ayrı; API dönüşümünde tahmini `cycleProgress` üretilmez. |
| `first_quarter`, `last_quarter`, stations, `ingress` | `CosmicEventType` | Enum | Yüksek | **RESOLVED** — B4 değerleri ve `unknown`/`rawType` fallback. |
| `secondary_planet`, `aspect`, eclipse ve metadata | `CosmicEvent` | Ayrıntı | Orta | **RESOLVED** — typed alanlar ve metadata korunur. |
| Calendar window metadata | `CosmicCalendarWindow` | Üst seviye zarf | Düşük | **RESOLVED** — `toWindow()` ve API servisinde erişilebilir; eski ekran liste tüketir. |
| Daily/Weekly/Monthly/Annual structured responses | Forecast domain | Eksik consumer | Orta | **RESOLVED** — typed forecast modelleri ve DTO dönüşümleri; prose/AI varsayımı yok. |
| `SavedPersonResponse` | `SavedPerson` | Eksik model | Orta | **RESOLVED** — B1 kullanıcı şemasına bağlı DTO/domain; B5 çağrısı yok. |
| `SavedPerson.updated_at` talebi | Backend schema | Şemada yok | Düşük | **OPEN** — backend `SavedPersonResponse` yalnız `created_at` gönderiyor; `updatedAt` uydurulmadı. |

Backend kontratı değiştirilmedi. B4 sözleşme fixture'ı canlı yanıt değildir; gerçek backend smoke testi manuel çalıştırılmalıdır.
