# Mobile güvenlik hızlı denetimi

İncelenenler: `lib/`, Android/iOS konfigürasyonu, `pubspec.yaml`; backend B5 kodu salt okunur bırakıldı.

| Kontrol | Sonuç | Kanıt / kalan iş |
|---|---|---|
| Hardcoded API/AI secret | Tespit edilmedi | `lib/`, `android/`, `ios/` kaynak taramasında provider anahtarı yok. Flutter binary'ye hiçbir server secret konmamalı. |
| JWT ve kişisel veri logları | Yeni network kodunda yok | Önceki path/status debug logu kaldırıldı; token, header, body ve doğum verisi loglanmıyor. |
| Access/refresh token saklama | Secure storage | `SecureTokenStorage` mevcut `PlatformSecureStore` üstünde. Refresh token rotasyonu yeni değeri kaydediyor. |
| Paralel refresh | Test edildi | 10 eşzamanlı 401 için 1 refresh; başarı ve hata senaryoları testte. |
| Refresh başarısızlığında oturum | Test edildi | Tokenlar temizlenir; `sessionExpiredCallbackProvider` mevcut `sessionProvider` üzerinden oturumu kapatır. 10 eşzamanlı 401 testinde callback yalnızca bir kez çağrılır; varsayılan callback'in session durumunu `unauthenticated` yaptığı da doğrulandı. |
| Production HTTPS | Yeni config doğruluyor | `AppEnvironment.validate()` API production modunda HTTPS ister. Mevcut application bootstrap henüz bu config'i kullanmıyor; provider bağlama yapılmadan release gate geçmemeli. |
| Android backup | Kapatılmış | `AndroidManifest.xml` `allowBackup=false`, `fullBackupContent=false`; data extraction kuralları shared preferences'ı dışlıyor. |
| Firebase/LiveKit secret | Yok | Gerçek credential/config dosyası üretilmedi. |

Flutter Contract Alignment güncellemesi: `authRepositoryProvider` ve `astrologyServiceProvider` artık `APP_DATA_SOURCE` ile merkezi olarak mock/API seçer. Astro AI API modunda B6 öncesi kontrollü unavailable durumundadır. Canlı API, Android/iOS build ve release güvenlik doğrulaması yine yapılmadı; yerel provider testi bunların yerini tutmaz.
