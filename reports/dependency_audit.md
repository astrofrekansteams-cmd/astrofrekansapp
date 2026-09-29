# Flutter dependency denetimi

`pubspec.yaml` ve `lib/`/`test/` importları karşılaştırıldı. Paket sürümleri bu fazda değiştirilmedi.

| Dependency | Durum | Gerekçe |
|---|---|---|
| `flutter` | Kullanılıyor | Uygulama SDK'sı. |
| `cupertino_icons` | Doğrudan kullanım bulunmadı | Silme adayı; önce iOS ikonlarının kullanımını release fazında doğrula. |
| `flutter_riverpod` | Kullanılıyor | Provider, state ve test override'ları. |
| `go_router` | Kullanılıyor | Uygulama routing. |
| `dio` | Kullanılıyor | Yeni API transport, refresh ve error testleri. |
| `freezed_annotation` | Kullanılıyor | Domain model anotasyonları. |
| `json_annotation` | Doğrudan import yok; generated model katmanı için tutuluyor | Generator ve üretilen JSON kodu bağımlılık zincirinde; doğrulamadan silme. |
| `flutter_secure_storage` | Kullanılıyor | Token ve kişisel profil saklama. |
| `shared_preferences` | Kullanılıyor | Hassas olmayan tercihler. |
| `intl` | Kullanılıyor | Tarih ve üretilmiş localization. |
| `flutter_localizations` | Kullanılıyor | Material/Cupertino lokalizasyonu. |
| `flutter_test` | Kullanılıyor | Widget, kontrat ve network testleri. |
| `flutter_lints` | Kullanılıyor | `analysis_options.yaml` üzerinden. |
| `build_runner` | Geliştirmede gerekli | Freezed/json_serializable üretimi için; runtime'a girmez. |
| `freezed` | Geliştirmede gerekli | Domain model üretimi. |
| `json_serializable` | Geliştirmede gerekli | JSON üretimi. |

Firebase ve LiveKit SDK paketleri eklenmedi; gerçek proje yapılandırması ve iş akışı gelmeden bağımlılık eklemek yarar sağlamaz.
