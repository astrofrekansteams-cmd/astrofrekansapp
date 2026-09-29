# Faz 5 — Release configuration + store hazırlık

Tarih: 28 Eylül 2026. App Store Connect ve Play Console'da ürün oluşturulmadı. Site, admin paneli ve commit yok.

## Uygulanan kararlar

| Karar | Uygulama |
|---|---|
| Google Sign-In ilk sürümde kapalı | Production build'de Google butonu **hiç** görünmüyor. Genel kural: production'da çalışmayan sosyal buton gösterilmiyor, yani "yakında" butonu da yok. `SocialAuthService` altyapısı duruyor. Development ve staging'de buton görünmeye devam ediyor. |
| `firebase_check_revoked` global false | Default `false` (testle sabitlendi). Hassas işlemlerde `SensitiveUser` bağımlılığı Firebase'e iptal kontrolü soruyor: şifre değiştirme, hesap silme (iki uç), satın alma doğrulama (Apple, Google), restore, oturum listesi, oturum kapatma, tüm oturumlardan çıkış. |
| Legacy ürünler mağazada yok | `natal_report`, `synastry_report`, `annual_forecast_report` ve `ai_pre_analysis` artık `sellable=False`. ID verilse de yok sayılıyor, DB'de pasifler; production'da bunlara ID verilirse sunucu başlamıyor. Raporlar AstroCoin ile veya plana dahil olarak ödeniyor. |

## 1. Android release signing

| | Durum |
|---|---|
| applicationId / namespace | `com.astrofrekans.astrofrekans` ✓ |
| Release keystore | **YOK**: repoda ve kullanıcı dizininde bulunamadı. Oluşturmayı onayına bırakıyorum. |
| Release SHA-1 / SHA-256 | Keystore olmadığı için **yok** |
| Debug SHA-1 | `D0:5E:5E:F4:22:8E:D3:73:8D:EF:7D:AB:84:DB:3B:AA:47:D6:CC:F2` (yalnızca geliştirme) |
| İmzalama yaklaşımı | CI: Codemagic `CM_KEYSTORE_*` env (vardı). **Yeni:** yerelde git-ignore'lu `android/key.properties`, şablonu `android/key.properties.example`. |
| Secret git'e giriyor mu | Hayır: `key.properties`, `*.jks`, `*.keystore`, `.env`, `*.p8`, servis hesapları, `google-services.json` ve `GoogleService-Info.plist` ignore listesinde |
| Debug anahtarıyla release | **Engelli:** upload key yoksa build `:app:signReleaseBundle` adımında net bir mesajla duruyor |

**Keystore oluşturma** (onayını bekliyor). Adımlar `docs/release_signing.md`'de:

```bash
keytool -genkeypair -v -keystore ~/.astrofrekans-keys/astrofrekans-upload.jks -storetype PKCS12 -keyalg RSA -keysize 4096 -validity 10000 -alias astrofrekans-upload -dname "CN=Astrofrekans, O=Astrofrekans, C=TR"
```

```bash
keytool -list -v -keystore ~/.astrofrekans-keys/astrofrekans-upload.jks -alias astrofrekans-upload
```

İkinci komut SHA1 ve SHA256'yı yazdırır.

**Saklama:**
- Dosya repo dışında (`C:\Users\<sen>\.astrofrekans-keys\`), parolalar parola yöneticisinde, bir de çevrimdışı yedek.
- Codemagic'e signing identity olarak **`astrofrekans_upload`** adıyla yüklenecek.

**Play App Signing SHA:** ilk yüklemeden sonra Play Console → App integrity → App signing bölümünden alınacak.

## 2. Firebase release config

- `google-services.json` paket adı `com.astrofrekans.astrofrekans` ile uyuşuyor ✓. iOS plist `BUNDLE_ID` da uyuşuyor ✓.
- **Repodaki iki config de `astrofrekans-staging` projesine ait.** Bir production Firebase projesi ve onun config dosyaları gerekiyor (blocker).
- **Production build'de staging/dev config engellendi** (4 katman):
  1. **Android Gradle:** `APP_ENVIRONMENT=production` + staging/dev `project_id` → build daha yapılandırmada duruyor. Doğrulandı: "Production build with a non-production Firebase config (… project_id=astrofrekans-staging)".
  2. **Codemagic iOS:** enjekte edilen plist'in `PROJECT_ID`'si staging/dev ise ya da `BUNDLE_ID` farklıysa adım başarısız oluyor.
  3. **Uygulama runtime:** production'da dev projesi → Firebase `error` (`firebase_dev_project_in_production`), fail-closed. Buna ek olarak mevcut koruma: uygulamanın projesi backend'inkiyle aynı olmalı.
  4. **Backend:** production'da `FIREBASE_PROJECT_ID` staging/dev gibi görünüyorsa ya da emülatör host'ları doluysa başlamıyor.
- **SHA'ların ekleneceği yerler** (production Firebase projesi):
  - Project settings → Android app → Add fingerprint;
  - upload key SHA-1 ve SHA-256;
  - Play app signing key SHA-1 ve SHA-256.
  - Sonra yeni `google-services.json` → Codemagic `FIREBASE_ANDROID_JSON_B64`.
  - Google Cloud OAuth client'larını Firebase otomatik oluşturuyor.

## 3. Store ürünleri: son audit

**Aktif 7 ürün** (backend `SELLABLE_CODES`, Flutter `storeProductCodes` allowlist):

| Kod | Tür | Verdiği |
|---|---|---|
| premium_monthly, premium_yearly | subscription | `premium` (aylık ve yıllık aynı tier) |
| cosmic_plus_monthly, cosmic_plus_yearly | subscription | `cosmic_plus` (Premium'dan üst; ikisi birlikteyse yüksek olan kazanır) |
| coins_120, coins_350, coins_800 | consumable | coin defterine 120 / 350 / 800 |

**Legacy (kapalı):**
- `natal_report`, `synastry_report`, `annual_forecast_report`, `ai_pre_analysis`.
- Backend bunları hiçbir platformda listelemiyor (gerçek API: pasif). Flutter bir sunucu hatasıyla listelense bile göstermiyor (test).
- **Düzeltilen ek sorun:** rapor kartları (AstroCoin ile alma butonu dahil) yalnızca mağaza legacy ürün listelerse görünüyordu. Legacy kapanınca AstroCoin ile rapor alma yolu da kaybolacaktı. Kartlar mağaza kataloğundan ayrıldı: doğum haritası ve yıllık öngörü raporu "{price} Coin ile al" ile; önceden alınmış kredisi olan için kredi butonu. Mağaza satın alma butonu kaldırıldı.
- Hibrit siparişte `ai_pre_analysis` satırı "hariç" kalıyor; otomatik rapor siparişleri bugünkü gibi. Kod yolu değişmedi.

| Kontrol | Sonuç |
|---|---|
| Entitlement eşlemesi | ✓ (katalog testi + Faz 4 yaşam döngüsü testi) |
| Aylık/yıllık aynı tier | ✓ |
| Kozmik+ > Premium | ✓ (tier sırası testi; üst plan kazanıyor) |
| Coin paketleri consumable, sunucuda consume | ✓ |
| Restore yalnız abonelikte entitlement açıyor | ✓. Yeni test: coin paketi iki kez restore edildi, bakiye 120'de kaldı, `premium=false` |
| Duplicate webhook | ✓ (Faz 4: aynı RTDN → `duplicate`) |
| Refund/revoke | ✓ (mevcut testler: coin paketi iadesi geri alıyor, Apple/Google iptali erişimi kapatıyor) |
| Flutter mağaza ID hard-code | Yok. Yalnızca 7 katalog kodu ve 3 rapor kodu (mağaza ID'siz) |

Production'da başlatmayı engelleyen katalog durumları:
- boş `STORE_PRODUCT_IDS` (açık mesaj: hangi 7 kodun eşlenmesi gerektiği yazıyor);
- legacy ürüne ID;
- bilinmeyen kod veya tekrar eden ID;
- doğrulaması yapılandırılmış bir mağazada 7 üründen birinin ID'sinin olmaması;
- ID'si olan ama doğrulaması yapılandırılmamış mağaza.

## 4. Production build config audit

**Flutter (dart-define) — production'da reddedilenler:**

| Girdi | Kural |
|---|---|
| `APP_DATA_SOURCE=mock` | reddedilir (vardı) |
| `API_BASE_URL` | https zorunlu (vardı). **Yeni:** localhost, 127.x, **10.0.2.2 / 10.0.3.2**, 10.x / 172.16–31 / 192.168 / 169.254, IPv6 loopback/yerel, `.local` / `.test` / `.internal` reddedilir |
| `ENABLE_DEBUG_TOOLS=true` | **yeni:** reddedilir. Uygulamada debug menüsü zaten yok; bayrak hiçbir yerde kullanılmıyor |
| `AUTH_MODE` | serbest (`local_jwt` / `firebase` / `hybrid`); Codemagic seçmeyi zorunlu tutuyor. Karar notu aşağıda |
| Firebase | staging/dev proje → fail-closed (yukarıda) |
| Billing | production + mock → hata (vardı); satın alınabilir liste 7 kodla sınırlı |
| Google girişi | production'da gizli |

**Backend `assert_production_ready`** — vardı ve korunuyor: JWT secret'ları, CORS, DEBUG, gating, fake AI / Firebase / realtime / store / APNs / ödeme, log/memory mail, SMTP eksikliği, reset URL https, LiveKit wss. Yeni eklenenler:
- boş, eksik veya legacy mağaza ID'leri; doğrulaması olmayan mağaza;
- `AD_REWARD_VERIFIER=mock` (mock rewarded ads);
- staging/dev `FIREBASE_PROJECT_ID`, Firebase emülatör host'ları;
- istemciye giden adreslerde yerel adres (reset URL, LiveKit URL, CORS origin'leri, Pub/Sub audience): localhost, 10.0.2.2, özel ağ, `.local` vb.
- Test ödeme sağlayıcısı (`EXTERNAL_PAYMENT_PROVIDER=fake`) zaten reddediliyordu.

**LiveKit, APNs, FCM:**
- LiveKit URL'si wss olmalı ve yerel olmamalı.
- APNs fake reddediliyor; production'da APNs anahtarı ve FCM (Firebase servis hesabı) backend secret'ı olarak verilecek.
- Android push kanalı Faz 4'te hazırlandı.

**`AUTH_MODE` kararı için bilgi** (karar senin):
- `firebase` / `hybrid`:
  - şifre sıfırlama e-postasını ve sayfasını **Firebase** sağlar → SMTP ve 404 sayfa blocker'ları bu hesapları etkilemez;
  - iOS'ta Sign in with Apple çalışır.
- `local_jwt`: sıfırlama backend SMTP ve GitHub sayfasına bağlı (ikisi de blocked); Apple girişi yok.

## 5. Reset password

- Kodda `PASSWORD_RESET_URL_BASE = https://astrofrekansteams-cmd.github.io/astrofrekansapp/reset-password.html` doğrulandı: tek kaynak, docker-compose ve `.env.example` aynı, production'da https ve yerel olmayan adres zorunlu.
- **Sayfa hâlâ 404 → BLOCKER** (site kapsam dışı). Yalnızca `local_jwt` hesaplarını etkiliyor.

## 6. SMTP

- **BLOCKED:** credential yok. Mail kodu değiştirilmedi.
- `MAIL_PROVIDER=smtp` seçilip ayarlar eksikse production başlamıyor. Faz 3 guard'ı, bu fazda yeniden testlendi.

## 7. Store metadata (koddan)

**Android:**

| | |
|---|---|
| Package | `com.astrofrekans.astrofrekans` |
| minSdk / targetSdk / compileSdk | 24 / 36 / 37 |
| versionName / versionCode | 1.0.0 / 1 (`pubspec.yaml` `version: 1.0.0+1`; her yüklemede versionCode artmalı) |
| İzinler | INTERNET, ACCESS_NETWORK_STATE, WAKE_LOCK, **POST_NOTIFICATIONS** (Android 13+, çalışma anında istenir), **com.android.vending.BILLING**, CAMERA, RECORD_AUDIO, MODIFY_AUDIO_SETTINGS, BLUETOOTH (≤ API 30), **USE_FULL_SCREEN_INTENT**, c2dm RECEIVE (FCM) |
| Donanım | **Düzeltildi:** kamera, mikrofon ve bluetooth artık `required=false`. Önceden izinler bu donanımları zorunlu kılıyordu ve Play kamerasız tabletlerde uygulamayı gizlerdi |
| Firebase | Auth, Cloud Messaging, Cloud Firestore, Realtime Database, Storage (Analytics/Crashlytics yok) |
| Bildirim | `astrofrekans_default` kanalı "Astrofrekans Bildirimleri" + `astrofrekans_calls` (gelen görüşme) |
| Deep link | `astrofrekans://app/...` (allowlist Dart'ta) |
| Play Console beyanları | Full-screen intent beyanı (gelen görüşme); Data safety (kamera, mikrofon, hesap, satın alma); abonelikler |

**iOS:**

| | |
|---|---|
| Bundle id | `com.astrofrekans.astrofrekans` |
| Minimum iOS | **15.0**. **Düzeltildi:** 13.0 idi; firebase_core, messaging ve firestore 15.0 istiyor, `pod install` başarısız olurdu |
| Cihaz | iPhone + iPad (`TARGETED_DEVICE_FAMILY 1,2`): iPad ekran görüntüleri gerekecek |
| Capabilities | Push Notifications, Background Modes (Remote notifications, Voice over IP), Sign in with Apple, In-App Purchase |
| Entitlements | **Eklendi:** `Runner/Runner.entitlements` (`aps-environment`, `com.apple.developer.applesignin`). Önceden dosya yoktu, release'de push token alınamazdı |
| Push | FCM (APNs) + PushKit VoIP (CallKit). CallKit nedeniyle Çin mağazası hariç tutulmalı (Apple kuralı) |
| Sign in with Apple | Kod hazır; yalnızca Firebase `AUTH_MODE`'da ve App ID'de capability açıksa görünür. Production'da çalışmıyorsa gizli. Google kapalı olduğu için 4.8 gereği zorunlu değil |
| In-app purchase | StoreKit 2 (`in_app_purchase_storekit`) |
| URL scheme | `astrofrekans` (`com.astrofrekans.links`) |
| Diğer | `ITSAppUsesNonExemptEncryption = false`; kamera/mikrofon açıklamaları TR; yalnız dark arayüz |

## 8. Build

- **Android release AAB**, staging tanımlarıyla, signing'siz:
  - Derleme tamamlandı (`bundleRelease` 325 sn, imzasız ara bundle üretildi).
  - Build **yalnızca `:app:signReleaseBundle` adımında** durdu: "Release signing is not configured: set CM_KEYSTORE_PATH… or create android/key.properties…". ✓
- **Android production tanımlarıyla:** staging `google-services.json` nedeniyle yapılandırmada durdu. ✓ (beklenen)
- **iOS:** bu ortamda (Windows) build edilemiyor.

**Codemagic için gerekenler:**

| Yer | Değer |
|---|---|
| Env group `astrofrekans_mobile_release` | `API_BASE_URL` (https, production), `AUTH_MODE`, `FIREBASE_ANDROID_JSON_B64` (production `google-services.json`, base64), `FIREBASE_IOS_PLIST_B64` (production `GoogleService-Info.plist`, base64) |
| Android signing identity | `astrofrekans_upload` (upload `.jks` + alias + iki parola → `CM_KEYSTORE_*`) |
| iOS signing | Codemagic App Store Connect entegrasyonu (API key: Issuer ID, Key ID, `.p8`); `ios_signing` app_store dağıtım sertifikası ve profili (Codemagic üretebilir) |
| Apple Developer | App ID `com.astrofrekans.astrofrekans`: Push Notifications + Sign In with Apple (+ In-App Purchase) capability'leri. Entitlements eklendiği için profil bunları içermezse imzalama başarısız olur |
| APNs | APNs Auth Key (`.p8`) → Firebase Console (Cloud Messaging) + backend `APNS_*` (PushKit VoIP) |
| Instance | `mac_mini_m2`, Xcode latest (mevcut) |

**Backend production secret'ları** (Codemagic değil, sunucu):
- `JWT_*`, `CORS_ORIGINS`, `FIREBASE_*` (production projesi), `STORE_PRODUCT_IDS`;
- `GOOGLE_PLAY_*` + RTDN Pub/Sub; `APPLE_*` + root sertifikaları; `APNS_*`;
- `LIVEKIT_*`, AI anahtarları; `MAIL_*` / `SMTP_*`.

## 9. Testler

- **Backend: 1004 passed** (25 dk). Yeni `tests/test_phase5_release.py` (25 test):
  - tam doğru production config başlıyor;
  - 6 mock/test sağlayıcı reddediliyor;
  - boş `STORE_PRODUCT_IDS` açık mesaj veriyor;
  - legacy ID reddediliyor;
  - eksik mağaza ID'si ve yapılandırılmamış mağaza reddediliyor;
  - 5 yerel adres vakası reddediliyor;
  - reset URL https olmalı;
  - SMTP eksikse başlamıyor;
  - staging Firebase ve emülatör reddediliyor;
  - `check_revoked` default false;
  - tam 7 ürün satılıyor, legacy ID'ler olsa bile satışa çıkmıyor;
  - coin restore ikinci kez coin vermiyor;
  - iptal edilmiş Firebase oturumu okuyabiliyor ama 6 hassas işlemde 401 alıyor;
  - devre dışı hesap 403, Firebase kesintisi 502 (çıkış yok);
  - local JWT Firebase'e gitmiyor.
- Kredi mekaniğini test eden 21 mevcut test legacy satışı yalnızca test içinde açan `legacy_products_sellable` fixture'ıyla korundu. Ürün listesi testi yeni gerçeğe göre güncellendi.
- **Flutter:** `flutter analyze` temiz; **319 passed**, 2 skipped. Yeni `test/features/phase5_release_test.dart` (7 test):
  - public https kabul;
  - 8 yerel/özel adres reddi + http reddi;
  - mock ve debug tools reddi;
  - dev Firebase projesi tanıma;
  - production'da Google ve "yakında" yok;
  - development'ta Google butonu görünüyor;
  - legacy ürün sunucuda listelense bile yalnızca 7 kod sunuluyor.
- Docker güncel (0017 head, `/ready` OK). Gerçek API'de 4 legacy satır pasif, 7 ürün aktif, local JWT ile hassas uç 200.
- Emülatör smoke bu fazda yapılmadı (değişiklikler production yapılandırmasına özgü; birim ve widget testleriyle doğrulandı).

## 10. Mağaza konsollarına geçmek için kalan blocker'lar

1. **Upload keystore** oluşturulması (onayın) → SHA-1/SHA-256 → Codemagic `astrofrekans_upload`.
2. **Production Firebase projesi:** Android ve iOS config'leri, SHA parmak izleri, APNs anahtarı. Şu an yalnızca staging var; production build bilerek reddediliyor.
3. **Mağaza ürünleri:** Play'de 4 abonelik (her biri tek base plan) + 3 managed product; App Store'da 4 abonelik tek grupta (Kozmik+ üst seviye) + 3 consumable. Sonra `STORE_PRODUCT_IDS` ve mağaza doğrulama secret'ları (`GOOGLE_PLAY_*`, RTDN, `APPLE_*`).
4. **Apple Developer:** App ID capability'leri (Push, Sign in with Apple), App Store Connect API anahtarı; ilk iOS build ve smoke bir Mac'te / Codemagic'te.
5. **`AUTH_MODE` kararı:** firebase/hybrid seçilirse SMTP ve reset sayfası kullanıcıları etkilemez.
6. **SMTP credential** (`local_jwt` hesapları için): BLOCKED.
7. **Reset sayfası 404** (site, kapsam dışı): BLOCKED.
8. **Play Console beyanları:** full-screen intent, Data safety, içerik derecelendirmesi, abonelik ve iptal açıklamaları. App Store: gizlilik etiketleri, iPad ekran görüntüleri, Çin hariç tutma.
9. Faz 4'ten açık: staging Firebase manuel testi, plan değişimi (`ChangeSubscriptionParam`) license tester ile, PSP kararı.

## Değişen / eklenen dosyalar (Faz 5)

**Backend:**
- `app/api/deps.py` (`SensitiveUser`)
- `app/api/v1/auth.py`, `app/api/v1/users.py`, `app/api/v1/billing.py`
- `app/services/payments/catalog.py` (`sellable`, `SELLABLE_CODES`/`LEGACY_CODES`, `store_release_problems`)
- `app/core/config.py` (production guard'ları)
- `.env.example`
- `tests/test_phase5_release.py` (yeni), `tests/conftest.py` (`legacy_products_sellable`), `tests/test_payments.py`, `tests/test_report_payments.py`

**Flutter:**
- `lib/core/network/api_config.dart`
- `lib/core/config/firebase_client.dart`
- `lib/features/auth/presentation/widgets/social_auth_row.dart`
- `lib/features/billing/data/billing_models.dart`, `lib/features/billing/application/entitlement_controller.dart`, `lib/features/billing/presentation/paid_reports_section.dart`
- `lib/core/localization/b12_copy.dart`
- `test/features/phase5_release_test.dart` (yeni)

**Android:**
- `android/app/build.gradle.kts` (key.properties, signing adımında durma, production Firebase koruması)
- `android/app/src/main/AndroidManifest.xml` (`uses-feature required=false`)
- `android/key.properties.example` (yeni)

**iOS:**
- `ios/Podfile` ve `ios/Runner.xcodeproj/project.pbxproj` (iOS 15.0, `CODE_SIGN_ENTITLEMENTS`)
- `ios/Runner/Runner.entitlements` (yeni)

**CI / doküman:** `codemagic.yaml` (iOS Firebase plist koruması), `docs/release_signing.md` (yeni)
