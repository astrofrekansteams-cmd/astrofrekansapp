# Faz 6 — Release signing + production Firebase hazırlığı

Tarih: 28 Eylül 2026. Karar: **production `AUTH_MODE = hybrid`**. Play Console / App Store ürünleri oluşturulmadı. Site, admin paneli ve commit yok. **Rapor parola veya secret içermez.**

## Özet

| Konu | Durum |
|---|---|
| Upload keystore | **CREATED** |
| SHA-1 (upload) | `E5:8E:0C:0E:70:CB:6B:D7:D0:1C:45:B1:53:06:05:D2:4A:2E:B4:16` |
| SHA-256 (upload) | `28:5A:F8:59:C6:33:FE:E8:FF:9B:26:61:92:52:73:EC:AF:20:DD:72:44:CE:7B:75:0B:8B:39:6A:CA:93:3E:6B` |
| İmzalı AAB | **BAŞARILI** (non-production/staging tanımlarıyla; upload key ile imzalı) |
| Production Firebase | **USER ACTION REQUIRED** (Console işlemi; proje uydurulmadı) |
| AUTH_MODE hybrid | Doğrulandı ve 2 hata düzeltildi |
| Şifre sıfırlama ayrımı | Doğrulandı ve düzeltildi (sahte başarı giderildi) |
| Apple | Altyapı hazır; production'da anahtarla kapalı; eksik credential ve kod listesi aşağıda |
| Backend tam test | **1011 passed** |
| Flutter | analyze temiz, **334 passed**, 2 skipped |
| **Yeni blocker** | AAB cihaz başına ~**237 MB** > Play'in 200 MB sınırı |

## 1. Android upload keystore — CREATED

- Konum (repo dışında): `C:\Users\nicat\.astrofrekans-keys\astrofrekans-upload.jks`.
- Özellikler: PKCS12, RSA 4096, SHA384withRSA, alias `astrofrekans-upload`, 10000 gün (Şubat 2054'e kadar), `CN=Astrofrekans, O=Astrofrekans, C=TR`.
- **Parola:**
  - Oluşturma sırasında script içinde rastgele üretildi.
  - keytool'a ortam değişkeniyle verildi (komut satırında yok).
  - Hiçbir çıktıya, log'a, rapora ya da koda yazılmadı.
  - Yalnızca git-ignore'lu `android/key.properties` içinde duruyor (`git check-ignore` doğrulandı).
- PKCS12'de store ve key parolası aynı.
- **Senin yapman gereken:**
  1. Parolayı `android/key.properties`'ten parola yöneticine taşı.
  2. `.jks` dosyasını çevrimdışı yedekle.
  3. İkisini Codemagic'e yükle (madde 9).
- `docs/release_signing.md` güncellendi (parola yok).

## 2 ve 3. Production Firebase ve SHA — USER ACTION REQUIRED

Staging projesine (`astrofrekans-staging`) dokunulmadı. Production projesi Google hesabınla Console'da oluşturulmalı. Proje ID küresel ve geri alınamaz; `astrofrekans-prod` alınmışsa Console bir sonek önerir. Bu yüzden uydurmadım.

**Adımlar (sırayla):**
1. **Proje:** Firebase Console → Add project → ID `astrofrekans-prod` (farklı çıkarsa bana bildir). Analytics kullanılmıyor, kapatılabilir.
2. **Plan:** Storage kullanıyoruz (`storage.rules` var). Yeni projelerde Storage bucket'ı Blaze planı gerektiriyor.
3. **Authentication** → Sign-in method:
   - **Email/Password: açık**;
   - Google: **kapalı** (karar);
   - Apple: şimdilik kapalı (madde 7).
   - Templates → Password reset şablonu: dil TR, gönderen adı "Astrofrekans". Action URL varsayılan Firebase sayfası kalsın.
4. **Firestore:** veritabanı oluştur (production mode, staging ile aynı bölge önerilir).
5. **Realtime Database:** oluştur (locked mode). URL → backend `FIREBASE_DATABASE_URL`.
6. **Storage:** başlat. Bucket → backend `FIREBASE_STORAGE_BUCKET`.
7. **Kurallar:** repodaki kurallar gerçek kaynaklar. Proje ID kesinleşince:
   - `firebase use --add` ile `production` alias'ı ekle;
   - `firebase deploy --only firestore:rules,firestore:indexes,database,storage --project <prod-id>`.
8. **Android app:** paket `com.astrofrekans.astrofrekans`. **Upload key** parmak izlerini ekle (yukarıdaki SHA-1 ve SHA-256). `google-services.json` indir.
9. **iOS app:** bundle `com.astrofrekans.astrofrekans`, Team ID, (App Store Connect uygulaması oluşunca) App Store ID. `GoogleService-Info.plist` indir.
10. **Cloud Messaging** → Apple app configuration: **APNs Auth Key (.p8)** + Key ID + Team ID.
11. **Backend servis hesabı:** Project settings → Service accounts → Generate new private key → sunucu secret'ı `FIREBASE_CREDENTIALS_JSON`, `FIREBASE_PROJECT_ID=<prod-id>`. Git'e girmez; ignore listesinde.
12. **Sonra (Play App Signing aktif olunca):** Play Console → App integrity → *App signing key certificate* SHA-1 ve SHA-256'yı **aynı Android app'e ek parmak izi olarak** ekle. **Upload key girişlerini silme veya değiştirme:** iki anahtar ayrı; Play'den yüklenen build'ler app signing key ile imzalanır.

**Dosyalar gelince doğrulama:**
- `dart run tool/validate_firebase_config.dart --production android/app/google-services.json ios/Runner/GoogleService-Info.plist`
- Kontrol ettikleri:
  - proje dev/staging olmamalı;
  - paket ve bundle `com.astrofrekans.astrofrekans`;
  - app id aynı projenin numarasından (`1:<numara>:android|ios:…`);
  - iki dosya aynı projeden.
- Yalnızca proje, paket/bundle ve app id yazdırır; API key yazdırmaz.
- Bugünkü staging dosyaları: normal modda "OK"; `--production`'da **reddediliyor** ✓.
- Codemagic iki platformda enjeksiyondan sonra bunu çalıştırıyor.

**Production koruması (korundu, şimdi 5 katman):**
1. Android Gradle: signing mevcutken de production + staging config yapılandırmada reddedildi (yeniden doğrulandı).
2. Codemagic doğrulayıcı (Android + iOS).
3. Uygulama çalışma anı (dev projesi → fail-closed).
4. Uygulama ↔ backend proje eşleşmesi.
5. Backend production guard.

## 5. AUTH_MODE = hybrid

**Bulunan ve düzeltilen hatalar:**
1. **Local JWT (sunucu) hesapları hybrid uygulamada giriş yapamıyordu.**
   - `HybridAuthAdapter.signIn` yalnızca Firebase'i deniyordu; yalnızca eski kayıtlı oturumlar geri yüklenebiliyordu.
   - Backend'de oluşturulan hesaplar (ör. uzmanlar) yeni cihazda giremezdi.
   - Artık önce Firebase deneniyor. Kimlik bilgisi kabul edilmezse, ya da adres bağlanmamış bir sunucu hesabına aitse, backend girişi deneniyor.
   - Başarısızlık iki durumda da aynı "geçersiz bilgi" mesajı; hangi tür hesabın var olduğu açığa çıkmıyor.
   - Ağ, rate-limit ve yapılandırma hatalarında ikinci kapı denenmiyor.
2. **Kayıtta yetim Firebase hesabı:** sunucu hesabı olan bir adresle uygulamadan kayıt olunursa Firebase kullanıcısı oluşuyor ama backend bağlamayı reddediyordu. Artık yeni Firebase kullanıcısı siliniyor ve "e-posta kullanımda" deniyor.

**Doğrulananlar:**

| Kontrol | Sonuç |
|---|---|
| Local JWT kullanıcıları giriş yapabiliyor | ✓ (Flutter + backend testleri) |
| Firebase email/password kullanıcıları giriş yapabiliyor | ✓ |
| Apple altyapısı korunuyor | ✓ (madde 7) |
| Google butonu production'da gizli | ✓ |
| Aynı e-posta ile duplicate profil | **Oluşmuyor.** Firebase girişi sunucu hesabıyla çakışırsa (doğrulanmış e-posta dahil, auto-link kapalı) 409 `account_link_required`, kullanıcı sayısı değişmiyor. Firebase hesabının adresiyle yerel kayıt 409 `email_in_use`. |
| Hesap ele geçirme | Yok. E-posta eşleşmesi kimlik kanıtı sayılmıyor; bağlama yalnızca oturum içinden (`/auth/firebase/link`) |
| Mevcut kullanıcılar | Migration yok. Kayıtlı yerel oturumlar geri yükleniyor; hiçbir hesap dönüştürülmüyor |

**Hybrid'in zorunlu hale getirildiği yerler:**
- Codemagic (`AUTH_MODE` hybrid değilse durur);
- uygulama production doğrulaması;
- backend production guard.

## 6. Şifre sıfırlama (hybrid)

**Bulunan sahte başarı:** hybrid build tüm sıfırlamaları Firebase'e gönderiyordu. Sunucu hesabı olan biri "bağlantı gönderildi" görüyor ama hiç e-posta almıyordu. Düzeltme `HybridPasswordResetService`:
- Firebase ve backend'e birlikte soruluyor.
- **Firebase hesabı → Firebase** kendi e-postasını ve kendi sayfasını kullanıyor.
- **Sunucu hesabı → backend SMTP**, link uygulamada açılıyor.
- Backend yalnızca yerel şifresi olan hesaplara token üretiyor. Firebase hesabına backend şifresi hiç tanımlanamıyor (testle doğrulandı).

| Durum | Ekranda |
|---|---|
| SMTP var | "Hesap uygunsa bağlantı gönderildi" |
| SMTP yok (bugün) | **"Hesap varsa bağlantı e-postana gönderildi. Uzman ve sunucu hesapları için sıfırlama e-postası şu an gönderilemiyor; destekle iletişime geç."** (yeni `requestedFirebaseOnly`) |
| İkisi de yok | "Şu an gönderilemiyor" |

- Yanıt yalnızca yapılandırmaya bağlı, adrese bağlı değil; enumeration yok.
- **Local JWT reset: BLOCKED** (SMTP yok).
- **`reset-password.html` 404: BLOCKED** (site kapsam dışı). Yalnızca sunucu hesaplarını etkiliyor.

## 7. Apple hazırlık

| | Durum |
|---|---|
| Entitlements (`Runner.entitlements`) | ✓ `aps-environment`, `com.apple.developer.applesignin` (Faz 5) |
| Kod | ✓ Firebase `AppleAuthProvider` (iOS native akış); hybrid'de kullanılabilir |
| Production görünürlüğü | **Yeni release anahtarı:** `ENABLE_APPLE_SIGN_IN` (varsayılan kapalı; Codemagic'ten verilir). Development ve staging'de açık. Google kapalı olduğu için 4.8 gereği Apple zorunlu değil |
| App ID capability | **USER ACTION:** Apple Developer → Identifiers → `com.astrofrekans.astrofrekans` → **Sign In with Apple** + **Push Notifications**. Entitlement dosyası bunları içerdiği için capability yoksa imzalama başarısız olur |
| Firebase Apple provider | **USER ACTION:** production projesinde Apple'ı etkinleştir. iOS native akış için Services ID ve redirect gerekmiyor; web/Android Apple girişi kullanılmıyor, `https://<prod>.firebaseapp.com/__/auth/handler` şimdilik gereksiz |
| Hesap silmede Apple token iptali (App Store 5.1.1(v)) | **EKSİK (kod + credential):** Apple ile giriş açılmadan önce silme akışı `revokeTokenWithAuthorizationCode` ile token iptal etmeli. Firebase Apple provider'a Team ID + Key ID + "Sign in with Apple" anahtarı (`.p8`) girilmeli. Bu yüzden anahtar kapalı |

## 8. İmzalı release build

`flutter build appbundle --release`, staging tanımlarıyla (`APP_ENVIRONMENT=staging`, `AUTH_MODE=hybrid`). Production Firebase config olmadığı için production build zorlanmadı.

| Kontrol | Sonuç |
|---|---|
| Sonuç | ✓ `build/app/outputs/bundle/release/app-release.aab` (292 MB) |
| İmza | `keytool -printcert -jarfile`: Owner `CN=Astrofrekans…`, SHA-1/256 = **upload key**. Debug (`D0:5E…`) **değil** ✓ |
| applicationId | `com.astrofrekans.astrofrekans` ✓ |
| versionCode / versionName | 1 / 1.0.0. Her Play yüklemesinde `pubspec.yaml`'daki `+N` artırılmalı |
| debuggable | yok ✓ |
| Firebase | bu non-production AAB'de `astrofrekans-staging` (beklenen). **Production tanımlarıyla build Gradle'da reddediliyor** ✓ |
| Codemagic | yeni adım: AAB `CN=Android Debug` ile imzalıysa build başarısız olur |

**YENİ BLOCKER — boyut:**
- Cihaz başına indirme ≈ **237 MB** (arm64): asset'ler 219 MB (PNG 141 MB, WebP 77 MB; rün 54, tarot 41, katina 26, gezegen 16, burç 15, marka 13 MB), native 16 MB.
- Google Play base modül sıkıştırılmış indirme sınırı **200 MB** → yükleme reddedilir.
- Çözüm ayrı iş: PNG → WebP (kayıplı/kalite ayarlı) ve büyük setler için Play Asset Delivery.
- iOS'ta hücresel indirme uyarısı da çıkar.

## 9. Codemagic

**Android** (`android-release-candidate`):

| | Durum |
|---|---|
| Signing identity `astrofrekans_upload` | **Eksik (senin işin):** Team settings → Code signing identities → Android keystores → `.jks` yükle; alias `astrofrekans-upload`, parolalar `key.properties`'teki. Codemagic `CM_KEYSTORE_PATH`, `CM_KEYSTORE_PASSWORD`, `CM_KEY_ALIAS`, `CM_KEY_PASSWORD` değişkenlerini kendisi sağlar. İsimler `build.gradle.kts` ve workflow'la uyumlu ✓ |
| `FIREBASE_ANDROID_JSON_B64` | **Eksik:** production `google-services.json`, base64. İsim doğrulandı ✓ |
| `API_BASE_URL` | **Eksik:** https production API |
| `AUTH_MODE` | `hybrid` olmalı (workflow başka değeri reddediyor) |
| `ENABLE_APPLE_SIGN_IN` | opsiyonel; varsayılan `false` |

**iOS** (`ios-release-candidate`):

| | Durum |
|---|---|
| `FIREBASE_IOS_PLIST_B64` | **Eksik:** production `GoogleService-Info.plist`, base64. İsim doğrulandı ✓ |
| App Store Connect API key | **Eksik:** Issuer ID, Key ID, `.p8` (Codemagic → Integrations) |
| Signing | **Eksik:** Apple Distribution sertifikası + App Store provisioning profile (`com.astrofrekans.astrofrekans`, Push + Sign in with Apple). Codemagic API key ile üretebilir |
| Apple Developer | App ID + capability'ler, Team ID |
| APNs | `.p8` → Firebase Cloud Messaging + backend `APNS_*` (VoIP) |
| Build | bu ortamda (Windows) iOS build edilemedi; ilk iOS build Codemagic'te |

## 10. Testler

- **Backend: 1011 passed** (21 dk).
  - İlk koşuda 1 test zamanlama yüzünden düştü: `test_appointment_cancel…[expert]`, seçilen ilk slot test sırasında başladı. Önceden de var olan bir kırılganlıktı. Test yardımcısı `order_for` artık 10 dakika içinde başlayan slotları atlıyor; ardından temiz koşu alındı.
  - Yeni `tests/test_phase6_hybrid.py` (7 test):
  - production hybrid zorunlu;
  - iki hesap türü de giriş yapıyor;
  - Firebase girişi sunucu hesabını ele geçirmiyor ve çoğaltmıyor (doğrulanmış e-posta dahil);
  - Firebase adresine yerel kayıt reddediliyor;
  - backend reset yalnızca sunucu hesabına gidiyor ve üç durumda aynı yanıt;
  - mail yokken herkese aynı 503.
- **Flutter:** analyze temiz (`tool/` dahil), **334 passed**, 2 skipped. Yeni testler:
  - `test/features/phase6_hybrid_test.dart` (10):
    - Firebase hesabı yalnızca Firebase'le giriyor;
    - sunucu hesabı backend'le giriyor;
    - bağlanmamış adres ikinci profil olmuyor;
    - her yerde yanlış şifre aynı mesaj;
    - ağ hatasında ikinci kapı denenmiyor;
    - kayıtta yetim Firebase kullanıcısı silinip "kullanımda" deniyor;
    - reset sonuçları yapılandırmaya bağlı, sahte "gönderildi" yok;
    - uygulamadaki link sunucu link'i;
    - her mod doğru reset servisini seçiyor;
    - iOS production'da Apple anahtarsız görünmüyor, Google hiç görünmüyor.
  - `test/tool/firebase_config_check_test.dart` (5): production dosyaları geçiyor, staging production'da reddediliyor, yanlış paket/bundle, başka projenin app id'si, farklı projeden Android/iOS.
  - Mevcut production ortam testleri (`b12a_network`, `data_source_config`, Faz 5) `authMode: 'hybrid'` ile sabitlendi. Böylece host/http/mock kontrollerini gerçekten test etmeye devam ediyorlar.
- **"Upload signing debug key kullanmıyor":** gerçek AAB imza kontrolüyle doğrulandı + Codemagic build sonrası adımı.

## 11. Play / App Store ürünlerini oluşturmaya hazır mıyız?

**Kısmen.**
- **Hazır:**
  - 7 ürün kodu, türleri ve backend eşlemesi;
  - production guard'ları;
  - Android upload key ve imzalı AAB üretimi;
  - hybrid auth.
- Konsolda uygulama kaydı ve ürün tanımları oluşturulabilir.
- **Ama ilk yüklemeden önce:**
  1. **AAB boyutu** (237 MB > 200 MB): Play yüklemeyi reddeder. Asset optimizasyonu gerekli.
  2. **Production Firebase projesi** ve config dosyaları (yukarıdaki adımlar) → production build ancak bundan sonra geçer.
  3. **Codemagic secret'ları** (upload key, Firebase base64'leri, `API_BASE_URL`; iOS için App Store Connect API key + signing).
  4. Apple: App ID capability'leri, APNs anahtarı. Apple girişi açılacaksa hesap silmede token iptali.
  5. **SMTP** (sunucu hesapları için sıfırlama) ve **reset sayfası 404**: blocked; Firebase hesaplarını etkilemiyor.
  6. Önceki fazlardan açık: staging Firebase manuel testi, plan değişimi license tester testi, PSP kararı, Play beyanları (full-screen intent, Data safety), iPad ekran görüntüleri, Çin hariç tutma.

## Değişen / eklenen dosyalar (Faz 6)

**Repo dışı:** `C:\Users\nicat\.astrofrekans-keys\astrofrekans-upload.jks` (yeni)

**Git-ignore:** `android/key.properties` (yeni, parola içerir, git'e girmez)

**Flutter:**
- `lib/features/auth/data/identity_session.dart`, `lib/features/auth/data/password_reset_service.dart`
- `lib/features/auth/presentation/password_reset_screens.dart`, `lib/features/auth/presentation/widgets/social_auth_row.dart`
- `lib/core/network/api_config.dart`, `lib/core/localization/b12_copy.dart`

**Araç:** `tool/firebase_config_check.dart`, `tool/validate_firebase_config.dart` (yeni)

**Backend:**
- `app/core/config.py` (hybrid zorunlu)
- `tests/test_phase6_hybrid.py` (yeni), `tests/test_phase5_release.py`, `tests/test_payments.py` (slot kırılganlığı)

**Testler:**
- `test/features/phase6_hybrid_test.dart`, `test/tool/firebase_config_check_test.dart` (yeni)
- `test/core/b12a_network_test.dart`, `test/core/data_source_config_test.dart`, `test/features/phase5_release_test.dart`

**CI / doküman:** `codemagic.yaml` (hybrid zorunlu, Firebase doğrulayıcı, imza kontrolü, Apple anahtarı), `docs/release_signing.md`
