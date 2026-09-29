# Faz 3 — Production readiness / kalan uygulama eksikleri

Tarih: 28 Eylül 2026. Kapsam: backend + kullanıcı uygulaması. Admin paneli, astrofrekans.org, site dosyaları, mağaza ürünleri ve yeni astroloji/fal özelliği kapsam dışı. Commit yok.

## Özet

| Konu | Durum |
|---|---|
| Docker ortamı (8000) | TAMAM — son kodla yeniden kuruldu, 8001 kapalı |
| Migration | TAMAM — `0017_notification_inbox (head)` |
| E-posta (kod) | TAMAM |
| E-posta (production) | **BLOCKED** — SMTP bilgisi yok |
| Reset URL | TAMAM (config) / **BLOCKED** — sayfa 404 veriyor |
| Push TR/EN | TAMAM — emülatörde gerçek FCM ile doğrulandı |
| Firebase oturum görünürlüğü | TAMAM — dürüst satır, kapatılamaz |
| Hybrid şifre değiştirme | TAMAM (fake'lerle test) / staging'de **manuel test gerekli** |
| Transit lokalizasyonu | TAMAM — 2452 vakada birebir aynı metin |
| Bildirim idempotency | TAMAM — Postgres'te doğrulandı |
| Uzman araması 500+ | **HATA BULUNDU ve düzeltildi** |
| Backend tam test | 967 passed |
| Flutter tam test | 294 passed, 2 skipped, analyze temiz |
| Emülatör smoke (8000) | TAMAM — push çekmecesi hariç (emülatör sorunu, aşağıda) |

## 1. Ortam

- `docker compose build` + `up -d`: `api`, `notification-worker`, `ai-worker`, `call-worker` son kodla. Postgres ve Redis'e dokunulmadı (5 gündür ayakta, healthy).
- `/health` → `ok`, `/ready` → `database/cache/ephemeris: ok`.
- `alembic current` → `0017_notification_inbox (head)`.
- 8001 portunda dinleyen süreç yok.
- Flutter build `API_BASE_URL=http://10.0.2.2:8000` ile kuruldu (profile APK, `AUTH_MODE=local_jwt`, `APP_DATA_SOURCE=api`).

**Gerçek API smoke** (8000, yeni test hesabı; hepsi PASS):

| İstek | Sonuç |
|---|---|
| register | 201 |
| login | 200 |
| `users/me` | `has_local_password=True`, `firebase_linked=False` |
| `auth/sessions` | yalnızca `password` türü; hepsi kapatılabilir |
| `DELETE auth/sessions/firebase:current` | 409 |
| `DELETE auth/sessions/not-a-uuid` | 404 |
| notifications, unread-count | 200 |
| appointments, orders | 200 |
| coins/wallet, coins/catalog | 200 |
| horoscope daily/weekly | 200 |
| forecasts monthly/yearly | 200 |
| transits, daily-frequency | 200 |
| forgot-password (mail kapalı) | 503 `password_reset_unavailable`; kayıtlı ve kayıtsız adrese aynı cevap |
| change-password (yanlış mevcut şifre) | 403 `current_password_incorrect` |

## 2. Production e-posta

**Kod: TAMAM. Production: BLOCKED — SMTP sağlayıcısı ve credential yok.** Sağlayıcı uydurulmadı.

**Yapılandırma doğrulaması** (`smtp_config_problems()`):
- host var mı;
- `MAIL_FROM` geçerli mi;
- port 1–65535 aralığında mı;
- SSL ve STARTTLS birlikte açık değil mi;
- kullanıcı adı ile şifre birlikte mi verilmiş;
- timeout > 0, `max_attempts` ≥ 1.

Production açılışta (`assert_production_ready`):
- `MAIL_PROVIDER=smtp` ise ayar eksikse uygulama başlamaz;
- reset URL `https` değilse uygulama başlamaz.

**Gönderim:**
- `SMTP_TIMEOUT_SECONDS` (10 sn) bağlantı süresini sınırlar.
- `SMTP_MAX_ATTEMPTS=3` deneme yapılır; aralar 1 sn, 2 sn diye üstel artar.
- Yalnızca geçici hatalar yeniden denenir: bağlantı hatası, timeout, 4xx SMTP kodları.
- Kalıcı hatalar (5xx, kimlik doğrulama, reddedilen alıcı) hemen durur.

**Log:** yalnızca `kind`, `attempt`, `reason`, `smtp_code`, `error_class` yazılır. Adres, token, konu ve şifre yazılmaz; testle doğrulandı.

**Şablon:**
- Mail çok parçalı: önce düz metin, sonra HTML.
- Hesabın diline göre TR veya EN.
- `Date`, `Message-ID` ve `Auto-Submitted: auto-generated` başlıkları var.

**Enumeration güvenliği:**
- Kayıtlı ve kayıtsız adrese aynı cevap döner.
- Mail, cevap gönderildikten sonra arka planda gider, böylece cevap süresi de aynı kalır.
- Mail sağlayıcısı yokken herkese aynı 503 döner ve uygulama bunu dürüstçe gösterir: "Password reset emails cannot be sent right now."

**Production için yapılacak:**
1. SMTP sağlayıcısı seçilip `.env` doldurulacak: `MAIL_PROVIDER=smtp`, `MAIL_FROM`, `SMTP_HOST/PORT/USERNAME/PASSWORD`, `SMTP_STARTTLS` veya `SMTP_SSL`.
2. Gönderen alan adı için SPF/DKIM/DMARC kayıtları eklenecek.

## 3. Reset URL

- Tek kaynak `PASSWORD_RESET_URL_BASE`. Varsayılanı `https://astrofrekansteams-cmd.github.io/astrofrekansapp/reset-password.html`; `docker-compose.yml` ve `.env.example` aynı değeri kullanıyor.
- Link `password_reset_link(token)` ile üretiliyor: `<base>?token=<url-encoded>`. Kodda başka bir yerde hard-code yok.
- **BLOCKER:** bu adres bugün **404** dönüyor (site ana sayfası 200). Site dosyalarına dokunulmadı.
- Sayfanın yapması gereken tek şey `?token=` değerini `astrofrekans://app/reset-password?token=<token>` adresine iletmek.
  - Android: intent filter hazır (`scheme=astrofrekans host=app pathPrefix=/reset-password`).
  - iOS: `CFBundleURLSchemes` içinde `astrofrekans` var.
  - Uygulamadaki `/reset-password` ekranı hazır.

## 4. Push TR/EN

- Olay adı (`event`), `data`, deep-link alanları ve dedupe anahtarı dile bağlı değil. Yalnızca başlık ve gövde dile göre değişiyor.
- Metinler `services/notifications/messages.py` dosyasında; her olay için TR ve EN var:
  - rapor hazır;
  - randevu hatırlatma / değişti / iptal;
  - danışman mesajı;
  - ödeme / iade;
  - abonelik;
  - arama;
  - sistem.
- Mesaj bildirimi nötr: "Yeni bir mesajın var." Böylece hem kullanıcıya hem danışmana doğru okunuyor.
- Metin kuyruğa girerken hesabın dilinde yazılır ve **gönderim anında yeniden** o anki dile göre hazırlanır. Arada dil değişirse yeni dil kullanılır. Bu, arama push'ları için de geçerli.
- Sunucu, gönderdiği push'un `data` alanına `notification_id` ekliyor. Böylece push, bildirim merkezindeki kaydın ta kendisi oluyor. Arama push'larında inbox kaydı yok, bu alan da yok.

**Emülatörde gerçek FCM ile görülenler:**
- TR hesapta sistem bildirimi: "Aboneliğinin süresi doldu."
- Uygulamada dil EN yapılınca hesap dili sunucuya yazıldı (`PATCH /users/me` 200). Sonraki push: "Your subscription renewed."
- Cihaza gelen `data`: `{notification_id, event}`. Deep-link alanları değişmemiş.

## 5. Firebase / hybrid oturumlar

- **Oturumlar ve Cihazlar** ekranında Firebase ile açılmış oturum ayrı bir satır olarak görünür:
  - "Firebase ile giriş · Google" gibi başlık;
  - "Firebase tarafından yönetiliyor";
  - giriş zamanı (token'daki `auth_time`);
  - **kapatma düğmesi yok**.
- Altında açıklama var: "Bu oturum Firebase tarafından yönetiliyor; buradan kapatılamaz. Diğer cihazlardaki Firebase oturumları bu listede görünmez…"
- Backend bu satırı yalnızca isteği yapan Firebase token'ından üretiyor (`id: firebase:current`, `kind: firebase`, `revocable: false`). Sahte yerel oturum yok.
- `DELETE /auth/sessions/firebase:*` → 409 `session_not_revocable`; geçersiz id → 404.
- Yerel şifre oturumları eskisi gibi listelenip kapatılabiliyor. Smoke'ta başka bir oturum kapatıldı.
- **Sınır:** Firebase'in diğer cihazlardaki oturumları sunucu tarafından görülemiyor. `firebase_check_revoked` varsayılan olarak kapalı: iptal edilen bir Firebase ID token en fazla 1 saat daha geçerli kalır. Production kararı gerekiyor (aşağıda).

## 6. Hybrid şifre değiştirme

**Karar mantığı** (`ApiAccountRepository.passwordCapability`):

| Hesap | Davranış |
|---|---|
| Firebase + `password` sağlayıcısı | Şifre **Firebase'de** değişir: mevcut şifreyle yeniden kimlik doğrulama → `updatePassword` → token yenileme. Backend şifre endpoint'i **çağrılmaz** (testle doğrulandı). |
| Yalnızca Google/Apple | Form gösterilmez: "Google ile giriş yapıyorsun; şifren Google hesabında yönetilir. Burada değiştirilecek bir şifre yok." Hesap Merkezi satırı da aynı notu gösterir. |
| Yerel hesap | Backend `POST /auth/change-password` (Faz 2 davranışı). |

**Firebase hata eşlemesi:**
- `wrong-password` / `invalid-credential` → "mevcut şifre yanlış";
- `requires-recent-login` / `user-token-expired` → "güvenlik için yeniden giriş yap";
- `weak-password` → zayıf şifre;
- `too-many-requests` → hız sınırı;
- `network-request-failed` → ağ hatası.

**Durum:**
- Emülatörde yerel hesapla doğrulandı:
  - yanlış mevcut şifre → hata;
  - doğru şifre → "Your password was changed.";
  - API: eski şifre 401, yeni şifre 200, diğer oturumlar kapandı, bu cihaz açık kaldı.
- Firebase yolları fake `FirebasePasswordOps` ile birim ve widget testlerinde doğrulandı.
- **Staging Firebase ile gerçek test yapılmadı.** Harici bir kimlik sağlayıcısında hesap açmak veya o hesapla giriş yapmak benim yapabileceğim bir işlem değil. Manuel kontrol listesi aşağıda.

## 7. Transit lokalizasyonu

- `transit_meaning.dart` içindeki TR/EN metinler kopya kataloğuna taşındı: `b12_copy.dart`, 33 anahtar (`transit_theme_*`, `transit_house_*`, `transit_angle_*` ve 5 şablon).
- Dosya artık yalnızca metinleri birleştiriyor. Public API aynı.
- Hesaplama motoruna ve astrolojik anlama dokunulmadı.
- **Birebir kanıt:** eski kodun ürettiği 2452 çıktı (tüm gezegen × açı × ev × açı noktası × dil) `test/fixtures/transit_meaning_golden.json` dosyasında. Yeni kod hepsini aynen üretiyor (`transit_meaning_parity_test.dart`).
- Emülatörde görüldü:
  - TR: "Sorumluluk, sınır ve yapı temaları 1. evinde: kendin ve bedenin gündemde."
  - EN: "Themes of responsibility, limits and structure move through your house 1: …"

## 8. Bildirim merkezi ve push tutarlılığı

- **Tek rota:** `lib/core/routing/notification_routes.dart` → `routeForNotification(event, data)`.
  - Push'a dokunmak ve bildirim merkezinde satır açmak aynı fonksiyonu kullanıyor.
  - Allowlist: bilinmeyen olay hiçbir yere gitmez.
  - Id'ler UUID olarak doğrulanıyor.
  - Test: 13 olayda push ve inbox aynı ekrana gidiyor.
- **Okundu:** push açılınca (uygulama arka plandayken veya kapalıyken) içindeki `notification_id` kaydı okundu yapılıyor ve rozet yenileniyor. Uygulama açıkken gelen push rozeti hemen artırıyor.
- **Idempotency:** aynı olay tekrar gelirse (aynı dedupe anahtarı) tek kayıt oluşur. Postgres'te doğrulandı: ilk `enqueue` kayıt yarattı, tekrarı `None` döndü, satır sayısı 1. Okundu işaretini tekrar göndermek sayacı değiştirmiyor.
- **Emülatörde:**
  - Rozet API ile aynı (1 → oku → 0; üç push → 3, sonra 4).
  - Rapor bildirimi açıldı → rapor ekranı → kayıt okundu.
  - `subscription_expired` push'unun açılma intent'i (gerçek FCM message id ile) → `/premium` açıldı. Yalnızca o kayıt okundu oldu, diğer üçü okunmamış kaldı (API ile doğrulandı).
- **Smoke'ta bulunan hata (düzeltildi):** silinmiş veya olmayan bir kayda giden bildirim, rapor ekranını yaklaşık 1 dakika "Gökyüzün hazırlanıyor…" durumunda tutuyor, API'ye 10 kez 404 isteği gidiyordu.
  - Neden: Riverpod 3'ün varsayılan otomatik retry'ı.
  - Düzeltme: `lib/core/network/retry_policy.dart` (`apiRetry`, `main.dart`'ta `ProviderScope(retry:)`). Kesin cevaplarda (404/403/401/422/429) retry yok; ağ ve 5xx hataları eski backoff ile yeniden deneniyor.
  - Emülatörde doğrulandı: tek istek, hemen "Kayıt bulunamadı veya erişimin yok." ve "Tekrar dene".

## 9. Uzman araması (500 sınırı)

- **Gerçek hata bulundu:** metin araması Python tarafında ilk 500 uzmanı tarıyordu. 500'den sonraki eşleşmeler hiç bulunmuyordu; test boş sonuç verdi.
- **Düzeltme:** 500'lük gruplar halinde sonuna kadar taranıyor (`SEARCH_SCAN_BATCH`). Sıralamaların hepsi `Expert.id` ile bitiyor, sayfalar kararlı.
- Test: 500'den sonraki uzman bulunuyor.
- **Borç** (`docs/marketplace_architecture.md`): arama hâlâ doğrusal. Uzman sayısı büyüdüğünde Postgres FTS + GIN indeksi gerekecek. Bugünkü ölçekte gereksiz optimizasyon yapılmadı.

## Testler

**Backend:**
- Faz 3 testleri (`tests/test_phase3_mail_push.py`, 16 test): SMTP doğrulama, production reddi, retry / kalıcı hata / limit, log temizliği, çok parçalı ve dile göre mail, yapılandırılmış URL, tüm olaylarda iki dil, gönderim anı dili, arama push'u, tekrar eden olay → tek kayıt, 500+ arama, Firebase oturum satırı, şifre oturumları.
- İlgili suite'ler (auth, firebase, phase1/2/3, call delivery, chat, marketplace): **226 passed**.
- **Tam suite: 967 passed** (23 dk).

**Flutter:**
- `flutter analyze`: temiz.
- `flutter test`: **294 passed, 2 skipped, 0 failed**.
- Yeni `test/features/phase3_flows_test.dart` (22 test):
  - push/inbox rota eşitliği ve allowlist;
  - açılan push'un rota + kayıt id'si üretmesi;
  - Firebase şifresinin yalnızca Firebase'de değişmesi;
  - Google hesabında form olmaması;
  - Firebase hata kodları;
  - yeniden giriş mesajı;
  - Firebase oturum satırında kapatma olmaması;
  - retry politikası.
- Yeni `test/core/transit_meaning_parity_test.dart`: 2452 vaka.
- Güncellenen test: `phase2_flows_test.dart` bildirim rotası artık gerçek UUID kullanıyor. Inbox da push gibi UUID doğruluyor; backend id'leri zaten UUID.

**Emülatör smoke** (Android emülatör, profile APK, Docker API 8000):

| Adım | Sonuç |
|---|---|
| Cold start (temiz veri) | TAMAM — onboarding, cihaz diline göre EN |
| Şifre sıfırlama başlangıcı | TAMAM — mail kapalı olduğu dürüstçe gösteriliyor |
| Giriş | TAMAM — hesap dili TR, arayüz TR'ye geçti |
| Oturum geri yükleme (force-stop → aç) | TAMAM |
| Bildirim merkezi, okundu/okunmadı, rozet | TAMAM |
| Push (gerçek FCM) TR ve EN metin | TAMAM |
| Push'a dokunma → ekran + okundu | TAMAM (açılma intent'i adb ile, aşağıya bakın) |
| TR ↔ EN geçişi | TAMAM |
| Şifre değiştirme (yanlış / doğru) | TAMAM |
| Oturumlar ve Cihazlar (liste, başka oturumu kapatma, cihaz listesi) | TAMAM |
| Profil, AstroCoin cüzdanı, Randevularım, Öngörüler | TAMAM |
| Transit ekranı TR/EN | TAMAM |

**Emülatör notları:**
- Bu emülatörün SystemUI bildirim çekmecesi hiçbir bildirimi listelemiyor. NotificationManager'da kayıt var, sistemin "Set a screen lock" bildirimi de görünmüyor; bu uygulamadan bağımsız. Bu yüzden push'a dokunma, FCM'in açtığı intent gerçek message id ile `adb am start` üzerinden tetiklenerek yapıldı. Plugin mesajı kendi deposundan okudu, akış gerçek dokunmayla aynı. Gerçek cihazda bir kez elle dokunulması önerilir.
- Debug APK araç bağlı olmadan (JIT) ANR verdi. Smoke profile APK ile yapıldı. Emülatör ayrıca ağır yük altında: uygulama sürekli animasyonla yaklaşık %80 CPU kullanıyor, bellek neredeyse dolu. Düşük uçlu cihazlarda arka plan animasyonunun maliyeti ayrıca ölçülmeli (bu fazda değiştirilmedi).
- Kullanıcının emülatördeki uygulama oturumu yedeklendi ve smoke sonrası birebir geri yüklendi (dosya hash'leri aynı). Smoke hesabının push cihazı silindi, oturumları kapatıldı. Kurulu APK artık 8000'e bakan profile build.
- Secret'lar loglanmadı. Test şifresi üretildi, yalnızca scratchpad'deki state dosyasında tutuldu, komut satırına veya çıktıya yazılmadı.

## Manuel kontrol listesi — staging Firebase (senin yapman gereken)

1. E-posta/şifre ile Firebase hesabına gir → Hesap Merkezi → Şifre Değiştir.
   - Yanlış mevcut şifre → "mevcut şifre yanlış".
   - Doğru şifre → "şifren değişti".
   - Çıkış yap, yeni şifreyle gir.
2. Uygulama değişiklikten önce mevcut şifreyle yeniden doğrulama yaptığı için `requires-recent-login` normalde gelmemeli. Gelirse (örn. uzun süre açık kalmış oturum) "güvenlik için yeniden giriş yap" mesajı görünmeli, uygulama çökmemeli.
3. Google hesabıyla gir.
   - Şifre satırı "Google ile giriş yapıyorsun…" notunu göstermeli.
   - Form görünmemeli.
4. Oturumlar ve Cihazlar'da:
   - "Firebase ile giriş · Google" satırı olmalı;
   - kapatma düğmesi olmamalı;
   - alttaki not görünmeli.
5. Şifre değiştikten sonra eski cihazdaki oturum: Firebase refresh token'ları iptal olur, ama mevcut ID token en fazla 1 saat daha geçerli (`firebase_check_revoked=false`).

## Kalan production blocker'ları

1. **SMTP credential yok:** sağlayıcı, `.env`, SPF/DKIM/DMARC. O zamana kadar şifre sıfırlama bilerek 503 dönüyor.
2. **Reset sayfası 404:** `reset-password.html` yayında değil. Token'ı `astrofrekans://app/reset-password?token=` adresine ileten sayfa gerekiyor (site kapsam dışı olduğu için dokunulmadı).
3. **Staging Firebase manuel testi:** yukarıdaki liste.
4. **`firebase_check_revoked` kararı:** `true` olursa her istekte Firebase'e ek çağrı yapılır ama iptal hemen geçerli olur; `false` iken bu gecikme 1 saate kadar sürer.
5. **Ödeme sağlayıcısı (PSP) kararı:** Faz 2'den açık; kapsam dışı.
6. **Arama borcu:** doğrusal tarama; ölçek büyüyünce Postgres FTS/GIN.
7. **Önerilen (blocker değil):** Android'de varsayılan bildirim kanalı tanımlı değil. Push'lar `fcm_fallback_notification_channel` ("Miscellaneous") kanalına düşüyor. Mağaza öncesi adlandırılmış bir kanal (`default_notification_channel_id`) eklenmeli.

## Değişen / eklenen dosyalar (Faz 3)

**Backend:**
- `app/services/mail/mailer.py` (yeniden yazıldı), `app/services/mail/templates.py` (yeni)
- `app/services/notifications/messages.py` (yeni), `outbox.py`, `sender.py`, `call_delivery.py`
- `app/core/config.py`, `app/api/v1/auth.py`, `app/api/deps.py`
- `app/services/auth/service.py`, `app/schemas/auth.py`, `app/schemas/user.py`, `app/services/users/service.py`
- `app/services/marketplace/discovery.py`
- `docker-compose.yml`, `.env.example`
- `tests/test_phase3_mail_push.py` (yeni), `tests/test_call_delivery.py`, `tests/test_chat_api.py`, `tests/test_phase1_flows.py`

**Flutter:**
- `lib/core/routing/notification_routes.dart` (yeni), `lib/core/network/retry_policy.dart` (yeni)
- `lib/main.dart`, `lib/app/app.dart`
- `lib/features/consultation/data/push_service.dart`
- `lib/features/notifications/presentation/notification_center_screen.dart`
- `lib/features/profile/data/account_repository.dart`, `lib/features/profile/presentation/account_center_screens.dart`
- `lib/core/localization/transit_meaning.dart`, `lib/core/localization/b12_copy.dart`
- Testler: `test/features/phase3_flows_test.dart` (yeni), `test/core/transit_meaning_parity_test.dart` (yeni), `test/fixtures/transit_meaning_golden.json` (yeni), `test/features/phase2_flows_test.dart`

**Doküman:** `docs/marketplace_architecture.md` (arama bölümü)
