# Codemagic release hazırlık planı

Bu belge yapılandırma planıdır; signing dosyası veya yayın workflow'u üretmez. Yerel ortam Windows olduğu için iOS derlemesi burada doğrulanamaz.

## Ortamlar

`APP_ENVIRONMENT=development|staging|production`, `APP_DATA_SOURCE=mock|api`, `API_BASE_URL` ve `ENABLE_DEBUG_TOOLS` Dart define olarak verilir. Production API HTTPS olmalıdır. Development Android emülatörü için `http://10.0.2.2:8000`, yerel Windows/web araçları için `http://127.0.0.1:8000` kullanılır. Bundle ID/applicationId değişikliği release öncesi ayrı karardır.

## Android

1. Play Console uygulaması ve package ID kararı.
2. Upload key/keystore oluşturma; Codemagic secret group içinde saklama.
3. Gradle release signing yalnız gerçek keystore ile yapılandırılır.
4. `flutter build appbundle --release` ve Play internal track yüklemesi.
5. Firebase Android uygulaması oluşturulduğunda gerçek `google-services.json` güvenli CI girdisi olarak sağlanır.

## iOS

1. Apple Developer ve App Store Connect uygulama kaydı; Bundle ID kararı.
2. Distribution certificate, provisioning profile ve App Store Connect API key'i Codemagic code signing alanında yönetme.
3. Gerçek `GoogleService-Info.plist` yalnız Firebase iOS projesi hazır olunca eklenir.
4. macOS runner üzerinde `flutter build ipa`, TestFlight ve cihaz smoke testi.
5. Push, Keychain, entitlements ve universal links gereken özelliklere göre açılır.

## Gizli ve doğrulanacak girdiler

Signing anahtarları, App Store Connect API key, Play service-account yetkisi ve backend/Firebase server secret'ları repo dışında tutulur. `API_BASE_URL` gibi herkese açık istemci konfigürasyonu bile doğru ortama sabitlenmelidir. Firebase Admin ve LiveKit API secret'ları mobil build'e hiçbir zaman eklenmez.

B12C'de `codemagic.yaml` release-candidate iskeleti eklendi. İki workflow da gerçek Firebase konfigürasyonu ve üretim API URL'si olmadan fail-closed çalışır; Android ayrıca `astrofrekans_upload` adlı Codemagic signing identity ve onun `CM_*` değişkenlerini gerektirir. `astrofrekans_mobile_release` environment group'u kullanıcı tarafından oluşturulmalıdır. iOS için App Store dağıtım sertifikası/provisioning profile Codemagic'e yüklenmelidir. Hiçbir workflow otomatik mağaza yayını yapmaz. Firebase dosyaları build sırasında geçici olarak üretilir, repoda tutulmaz. Yerel Android release artık debug anahtarla imzalanmaz.

Şablonun gerçek Codemagic hesabında derlenmesi ve imzalanması henüz doğrulanmadı. Referans: [Codemagic Flutter build ve signing belgeleri](https://docs.codemagic.io/yaml-quick-start/building-a-flutter-app/).

## B13B doğrulama kapısı — 2026-09-25

`codemagic.yaml` artık `AUTH_MODE` seçimini ve HTTPS `API_BASE_URL` değerini zorunlu kılar. Her iki release-candidate workflow'u `APP_ENVIRONMENT=production`, `APP_DATA_SOURCE=api`, `ENABLE_DEBUG_TOOLS=false` ile derler. Android, Flutter testlerinden sonra `:app:testDebugUnitTest` çalıştırır; iOS kullanılabilir bir iPhone simulator bulup `RunnerTests` için `xcodebuild test` çalıştırır. Bu adımlar başarısızsa build durmalıdır. Automatic store submission yoktur.

YAML yerel olarak parse edildi; **Codemagic çalıştırılmadı**. Gerçek Firebase dosyaları, production URL/CORS, Android keystore, Apple team/certificate/profile, APNs VoIP capability, ürün katalogları ve server credentials olmadan native compile, signing, IPA/AAB veya cihaz testleri doğrulanmış sayılmaz. Ayrıntılı durum: `../reports/b13b_flutter_release_validation.md`.
