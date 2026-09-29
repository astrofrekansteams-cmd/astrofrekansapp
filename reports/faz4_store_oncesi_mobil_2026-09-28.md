# Faz 4 — Store öncesi son mobil hazırlık

Tarih: 28 Eylül 2026. Kapsam: kullanıcı uygulaması (Android öncelikli) + backend. Admin paneli, astrofrekans.org, site dosyaları, App Store / Play Console ürünleri ve gerçek ödeme sağlayıcısı kapsam dışı. Commit yok.

## Özet

| Konu | Durum |
|---|---|
| Android bildirim kanalı | TAMAM — `astrofrekans_default`, emülatörde gerçek FCM ile doğrulandı |
| Performans (arka plan animasyonu) | TAMAM — darboğaz ölçüldü ve düzeltildi |
| Firebase staging manuel test | HAZIR — staging APK + 5 adımlık liste; Google girişi kodda kapalı |
| `firebase_check_revoked` true/false | ÖLÇÜLDÜ — karar senin (öneri aşağıda); outage hatası düzeltildi |
| Store ürün ID audit | 3 düzeltme (plan değişiminde çift abonelik, ID doğrulaması, eski kod) |
| Satın alma state audit | TAMAM — eksik durumlar eklendi, TR/EN, süresiz bekleme yok |
| Coin / plan tutarlılığı | TAMAM — gerçek API + uçtan uca Google senaryosu |
| Deep link audit | TAMAM — Android ve iOS için tek allowlist |
| Backend tam test | **979 passed** |
| Flutter | analyze temiz, **312 passed**, 2 skipped |

## 1. Android bildirim kanalı

**Öncesi:** push'lar FCM'in adsız `fcm_fallback_notification_channel` ("Miscellaneous") kanalına düşüyordu, status bar ikonu renkli launcher ikonuydu.

**Yapılanlar:**
- `NotificationChannels.kt` (yeni) kanalı oluşturuyor:
  - id: `astrofrekans_default`;
  - ad: "Astrofrekans Bildirimleri" (EN cihazda "Astrofrekans Notifications", `values-en`);
  - açıklama: rapor, randevu, mesaj ve ödeme bildirimleri;
  - importance **DEFAULT**: ses + status bar ikonu, heads-up yok;
  - **badge açık**, varsayılan bildirim sesi.
- Kanal iki yerde oluşturuluyor:
  - `MainActivity.onCreate`;
  - `AstroCallMessagingService.onCreate`: kurulumdan sonra uygulama hiç açılmadan push gelirse diye.
- `AndroidManifest.xml` içine FCM meta-data'ları eklendi:
  - `default_notification_channel_id`;
  - `default_notification_icon` → `ic_stat_astrofrekans` (yeni, tek renk hilal + yıldız vektörü);
  - `default_notification_color` → marka altını `#D9B979`.
- Backend normal push'larda `AndroidNotification(channel_id="astrofrekans_default", sound="default")` gönderiyor. `sound` Android 7'de (minSdk 24, kanal yok) varsayılan ses için gerekli.
- **Gelen arama kanalına (`astrofrekans_calls`) dokunulmadı.** Arama push'ları data-only kalıyor (testle doğrulandı).
- Uygulama içi TR/EN metinleri etkilenmedi.

**Emülatörde gerçek FCM ile doğrulandı:**
- `astrofrekans_default` kanalı: importance=3, `mShowBadge=true`, varsayılan ses.
- Gelen push `channel=astrofrekans_default` kanalına düştü.
- Renk `0xffd9b979`.
- İkon artık drawable kaynağı (`0x7f07…`); önceden mipmap launcher ikonuydu (`0x7f0c…`).

**Neden DEFAULT:** tek kanal rapor, makbuz ve hatırlatmaları birlikte taşıyor. Kanal önemi oluşturulduktan sonra uygulama tarafından yükseltilemiyor. İleride mesaj ve randevu hatırlatması için ayrı bir HIGH kanal açılabilir; bu fazda eklenmedi.

## 2. Performans / arka plan animasyonu

**Ölçüm yöntemi:**
- Profile APK, boşta 20 sn.
- `/proc/<pid>/stat` üzerinden CPU (bir çekirdeğe oranla).
- SurfaceFlinger `timestats` ile kare sayısı.
- Flutter VM timeline (`profileWidgetBuilds`) ile her karede neyin yeniden kurulduğu.

**Bulgu:**
- Boştayken **her karede yalnızca** yıldız alanı yeniden kuruluyordu (`AstroBackground`: `AnimationController.repeat` → `AnimatedBuilder` + `CustomPaint`).
- Impeller'da raster cache yok. Yıldızdaki her değişiklik **tüm ekranı** yeniden raster ettiriyor: görseller, glyph atlas, her karede 3 `saveLayer`.
- Twinkle vsync hızında çalışıyordu: gerçek telefonda saniyede 60–120 tam ekran çizim.
- Kontrol: Reduce Motion açıkken boşta 0 kare. Yani tek kaynak buydu. Shader/blur/particle kaynağı yok; ağır olan buydu.

| Ekran (emülatör, boşta) | Önce | Sonra |
|---|---|---|
| Ana sayfa | app %96 CPU, 12 kare/sn (emülatör doymuş) | %0, 0 kare/sn |
| Keşfet | %127, 15 kare/sn | %0, 0 kare/sn |
| Profil | %94, 15 kare/sn | %0.4, 0 kare/sn |
| Uygulama arka planda | %0.1 | ~%0–3 (ölçüm gürültüsü) |
| Reduce Motion | (zaten statik) 0 kare | 0 kare |

**Düzeltme** (`astro_background.dart`, `effects_budget.dart`; görsel tasarım aynı):
- **Hız:** twinkle saniyede 8 güncelleme yapıyor, vsync yerine zamanlayıcıyla. 9 sn'lik parıltıda iki güncelleme arasındaki opaklık farkı en fazla ~0.03, gözle fark edilmez. Bütçe içindeki bir telefonda tam ekran çizim 60–120/sn'den 8/sn'ye iniyor (~%87–93 az). `repaint: ValueNotifier` kullanıldığı için widget rebuild'i de yok.
- **Ekran görünmüyorsa durur:** üstü kapanan route veya pasif sekme (`TickerMode`).
- **Uygulama arka plandaysa durur** (lifecycle).
- **Reduce Motion:** statik (eskiden de öyleydi, korundu).
- **Düşük cihaz:** `EffectsBudget` motorun kendi `FrameTiming` verisini izliyor. Açılış penceresi atlandıktan sonra art arda iki pencerede medyan raster süresi 16 ms'yi aşarsa oturum boyunca twinkle durur ve logcat'e tek satır yazılır. Bu emülatörde tetiklendi: `EffectsBudget: decorative motion off (median raster 58.52 ms)`. Bu yüzden emülatörde "sonra" değeri %0; bütçe içindeki cihazlarda twinkle 8/sn ile sürüyor (birim testlerle doğrulandı).
- İçerik, geçişler ve giriş animasyonları (`AstroReveal`, sonlu) etkilenmedi.

## 3. Firebase staging manuel test hazırlığı

**Kontroller:**
- Uygulama (`google-services.json`) ve Docker backend aynı projede: `astrofrekans-staging`. Backend `AUTH_MODE=hybrid`, yani Firebase ID token'ı kabul ediyor.
- Debug keystore SHA-1'i (`D0:5E:…:CC:F2`) Firebase'deki Android OAuth client ile eşleşiyor.
- `AUTH_MODE=firebase` + `APP_ENVIRONMENT=staging` + `http://10.0.2.2:8000` geçerli bir kombinasyon (https yalnızca production'da zorunlu).
- **Hazır APK:** `build/staging/astrofrekans-staging-firebase.apk` (emülatör, x86_64). Emülatörde açıldı, giriş ekranına kadar hatasız geldi. Ben giriş yapmadım.
- **Google girişi kodda kapalı:**
  - `signInWithProvider(google)` → `notConfigured`; `isAvailable` yalnızca Apple için true.
  - Buton %55 soluk görünüyor ve "yakında" diyor.
  - Bu yüzden Google adımı bugün test edilemez; aşağıda karar maddesi olarak duruyor.
- Fake testler kaldırılmadı.

**Senin yapman gerekenler** (Docker API 8000 açık, emülatör):
1. `adb install -r build/staging/astrofrekans-staging-firebase.apk`
2. Uygulamada kayıt ol (ya da Firebase Console'da önceden oluşturduğun e-posta/şifre test kullanıcısıyla giriş yap). Ön koşul: Console → Authentication → Sign-in method'da **Email/Password açık** olmalı.
   - Profil → Hesap Merkezi → **Oturumlar ve Cihazlar**'da "Firebase ile giriş · e-posta ve şifre" satırı olmalı, kapatma düğmesi olmamalı, alttaki not görünmeli.
3. Hesap Merkezi → **Şifre Değiştir**:
   - yanlış mevcut şifre → "mevcut şifre yanlış";
   - doğru mevcut şifre → "şifren değişti";
   - Çıkış yap → yeni şifreyle giriş.
4. (İsteğe bağlı, `check_revoked` için) Console'da kullanıcıyı **Disable** et, uygulamada bir ekranı yenile:
   - `false` modda token süresi dolana kadar (≤1 saat) çalışmaya devam eder;
   - `true` modda anında "hesap devre dışı" (403) gelir.
   - Test sonrası kullanıcıyı yeniden **Enable** et.
5. Uygulamayı normal build'e döndürmek için 8000 / local_jwt profile APK'sını yeniden kur.

## 4. `firebase_check_revoked`

**Test:**
- Birim testler: gerçek provider + stub'lanmış SDK.
- API testi: fake Firebase ile uçtan uca.
- Gecikme ölçümü: Docker container'ından Firebase'e salt-okuma `get_user`, var olmayan uid ile. Hiçbir hesap okunmadı veya değişmedi.

| | `false` (mevcut) | `true` |
|---|---|---|
| İptal edilen / devre dışı hesap | ID token süresi dolana kadar (≤1 saat) çalışır | anında reddedilir: iptal → 401 `firebase_token_revoked`, devre dışı → 403, silinmiş → 401 |
| İstek başına ek maliyet | yok (yerel imza doğrulama, ~0.04 ms) | her Firebase istekli çağrıda bir Firebase Auth çağrısı: **medyan +262 ms**, p90 266 ms, en kötü 663 ms, soğuk ilk çağrı ~1 sn |
| Firebase'e erişilemezse | etkilenmez (sertifikalar önbellekte) | **Önce:** yakalanmayan hata → 500. **Şimdi:** 502 `firebase_unavailable`; 401 değil, kullanıcıyı çıkış yaptırmaz |
| Kota | yok | Firebase Admin API kotasına sayılır |

**Düzeltmeler (iki modda da doğru davranış için):**
- `UserNotFoundError` → 401.
- Diğer `firebase_admin` hataları → 502 + sade log (token loglanmıyor).
- Fake provider artık ayarı gerçek provider gibi okuyor.

**Güvenlik avantajı:** hesap devre dışı bırakıldığında, şifre değiştiğinde ya da cihaz çalındığında erişim bir saat yerine hemen kesilir.

**Performans maliyeti:** Firebase ile giriş yapmış kullanıcının her isteğine ~0.26 sn eklenir. Ayrıca Firebase kesintisi tüm Firebase oturumlarını 502'ye düşürür.

**Önerilen kullanım** (karar senin):
- Global olarak `false` kalsın.
- İptal kontrolü yalnızca hassas uçlarda `check_revoked=True` ile yapılsın: şifre değiştirme, hesap silme, satın alma doğrulama, oturum listesi. Kod bunu çağrı başına zaten destekliyor.
- Global `true` istenirse uid başına kısa (ör. 60 sn) önbellek eklenmeli.

## 5. Store ürün kataloğu audit

**Tek kaynak:**
- Kodlar ve ne açtıkları backend'de: `services/payments/catalog.py` → `CATALOG`.
- Mağaza ID'leri yapılandırmada: `STORE_PRODUCT_IDS`, JSON `{kod: {apple, google}}`.
- Uygulama mağaza ID'lerini backend'den alıyor. Flutter'da mağaza ID'si hard-code değil; yalnızca katalog kodları var (plan kartları ve legacy rapor kartları).

| Kod | Tür | Ne verir |
|---|---|---|
| premium_monthly / premium_yearly | subscription | `premium` |
| cosmic_plus_monthly / cosmic_plus_yearly | subscription | `cosmic_plus` (üst plan; yüksek olan kazanır) |
| coins_120 / coins_350 / coins_800 | consumable | coin defterine 120 / 350 / 800 |
| natal_report, synastry_report, annual_forecast_report (legacy) | consumable | tek kullanımlık rapor kredisi |
| ai_pre_analysis (legacy) | consumable | hibrit siparişin dijital ön analizi |

**Doğru olanlar:**
- Duplicate kod yok. Non-consumable ürün yok.
- Android consumable'lar sunucu doğrulamasından **sonra** sunucu tarafında consume ediliyor (`autoConsume: false`).
- Abonelikler acknowledge ediliyor.
- İstekteki kod ile mağazanın bildirdiği ürün ve ürün türü karşılaştırılıyor (ucuz ürünle pahalı erişim açılamıyor).
- Hesap bağlama: `obfuscatedAccountId` / `appAccountToken`.
- Restore: iOS'ta `restorePurchases`, Android'de geçmiş satın almalar; ikisi de backend `reconcile` ile doğrulanıyor.
- `STORE_PRODUCT_IDS` bugün boş, yani hiçbir şey satışta değil ve UI "—" gösteriyor. Legacy raporlar mağaza ID'si verilmedikçe gizli kalıyor.

**Düzeltilenler (minimum):**
1. **Android'de plan değişimi çift abonelik açıyordu.** Premium → Kozmik+ (veya aylık → yıllık) düz yeni satın alma olarak başlatılıyordu; Google ikisini birden çalıştırıp ikisinden de ücret alırdı. Artık çalışan Play aboneliği `ChangeSubscriptionParam` (`withTimeProration`) ile **değiştiriliyor**. Backend `linkedPurchaseToken` ile eskisini emekli ediyor. iOS'ta StoreKit bunu kendisi yapıyor; koşul: 4 aboneliğin **aynı subscription group'ta** olması.
2. **`STORE_PRODUCT_IDS` doğrulaması:** yanlış yazılmış kod (ürün sessizce satıştan kalkıyordu), aynı mağaza ID'sinin iki koda verilmesi (satın alma hangi koda ait çözülemiyor, `scalar()` hatası), bilinmeyen mağaza anahtarı ve bozuk JSON artık **production açılışında reddediliyor** (`store_catalog_problems`).
3. **Kataloğdan çıkarılan kodlar** DB'de `active=True` kalıyordu; artık senkronda pasifleşiyor. Satır duruyor çünkü geçmiş satın almalar ona bağlı.

**Mağazada ürün oluştururken uyulacak kurallar** (backend Google aboneliğini yalnızca `productId` ile eşliyor):
- **Play:** her kod ayrı bir abonelik ürünü olmalı ve her birinde tek base plan olmalı. Öneri: ID'ler kodla aynı olsun (`premium_monthly`, …, `coins_120`, …).
- **App Store:** 4 abonelik tek grupta olmalı; Kozmik+ seviyesi Premium'dan yüksek. Öneri: `com.astrofrekans.premium.monthly` biçimi.

## 6. Satın alma UI durumları

| Durum | Önce | Şimdi |
|---|---|---|
| Mağaza bağlı değil | fiyat "—", butonlar pasif, not | aynı (emülatörde doğrulandı; restore da pasif) |
| Yükleniyor | katalog iskeleti, hata/boş durumda "tekrar dene" | aynı |
| Satın alma sürüyor | butonlar kilitli, **gösterge yok** | "Satın alma sürüyor…" + ince ilerleme çubuğu |
| Doğrulanıyor | **gösterge yok** | "Satın alma doğrulanıyor…" |
| Başarılı | mesaj yok (sessizce idle) | "Satın alma tamamlandı; erişimin açıldı." |
| İptal / bekliyor (pending) | kart vardı | aynı |
| Hata | Türkçe hard-code metin (EN kullanıcı da Türkçe görüyordu) | TR/EN kopya anahtarları |
| Zaten sahip (Android `ITEM_ALREADY_OWNED`) | genel hata | "Bu ürün zaten hesabında… satın alımları geri yükle" |
| Mağaza hiç cevap vermezse | butonlar süresiz kilitli | 3 dk sonra "Mağazadan yanıt gelmedi…"; geç gelen cevap yine işlenir |
| Geri yükleme | ilerleme/sonuç yok; hata olursa tüm plan durumu "hata"ya dönüyordu | "Geri yükleniyor…" → "Satın alımların geri yüklendi" / "Geri yüklenecek satın alma bulunamadı"; hata planı silmiyor |
| Coin cüzdanı | hiçbir satın alma mesajı yoktu | aynı bildirim kartı |

Kırmızı hata ekranı yok. Bekleme durumları süre sınırlı.

## 7. Coin / plan tutarlılığı

**Gerçek API (Docker 8000, gating geçici olarak açıldı, sonra `.env` ayarına geri alındı):**
- **Feature matrisi:**
  - premium: aylık öngörü; gelişmiş tarot, rün ve katina; gelişmiş transit.
  - cosmic_plus: yıllık öngörü, sinastri, composite, davison, solar/lunar return, astrokartografi, gelişmiş AI.
  - Günlük açılım limiti: 3 / 15 / 40.
- Aylık bonus 0 / 150 / 500; paketler 120 / 350 / 800; harcama fiyatları 10–60. Bunların hepsi uygulamadaki kartlarla tutarlı.
- Free kullanıcıda aylık öngörü 403 `premium_required`; yıllık öngörü için Kozmik+ gerekiyor.
- **Harcama idempotency:** 50 coin → aylık öngörü coin ile alındı → 20. Aynı referansla tekrar istek → 200, bakiye yine 20 (tek düşüm). Yeni referans → 402 `insufficient_coins`, bakiye 20 kaldı.

**Uçtan uca Google senaryosu** (fake store, gerçek normalizasyon; `test_phase4_store.py`):
- Free: bonus yok, özellikler kilitli.
- Premium:
  - bonus 150 **bir kez** verildi, ikinci çağrıda 0;
  - aylık öngörü açık, yıllık kapalı.
- Kozmik+'ya yükseltme (`linkedPurchaseToken`):
  - eski Premium satın alma `expired` oldu;
  - bonus 350 tamamlandı (toplam 500), yine **bir kez**.
- Aynı RTDN iki kez geldi → ilki `applied`, ikincisi `duplicate`.
- Süre doldu:
  - kullanıcı free'ye döndü, özellikler kilitlendi, yeni bonus verilmedi;
  - daha önce verilen coinler duruyor (ekonomi değiştirilmedi).
- Refund rollback, coin paketinin tek kez kredilenmesi, eşzamanlı harcama ve iade durumları mevcut testlerde zaten kapsanıyordu; hepsi geçiyor.
- Gerçek mağaza satın alması Play/App Store bilgisi olmadan yapılamadığı için Premium ve Kozmik+ gerçek API'de değil bu testte doğrulandı.

## 8. Deep link audit

**Bulgu (tutarsızlık):**
- iOS `astrofrekans://` şemasının **her yolunu** açıyordu (`FlutterDeepLinkingEnabled`, yol filtresi yok). Örneğin bir web sayfası `…/calls/<id>/incoming` ya da hesap silme ekranını açabiliyordu.
- Android yalnızca `/reset-password` açıyordu.

**Düzeltme:** iki platform da router'a tam URL veriyor (Flutter motor kaynağından doğrulandı: Android `data.toString()`, iOS `absoluteString`). Bu yüzden karar tek yerde, Dart'ta: `lib/core/routing/deep_links.dart`.
- Dışarıdan açılabilen yollar: `astrofrekans://app/` + `reset-password`, `notifications`, `appointments/<uuid>`, `orders/<uuid>`, `astro-ai/reports/<uuid>`.
- Diğer her şey → ana sayfa: başka host, https, UUID olmayan id, arama/ödeme yolları.
- Android filtresi iOS ile aynı yüzeye (`astrofrekans://app`) genişletildi.

| Link (Android emülatör, gerçek VIEW intent) | Sonuç |
|---|---|
| `…/notifications` | Bildirimler açıldı |
| `…/orders/<başkasının/olmayan id>` | Sipariş Detayı: hemen "Kayıt bulunamadı" (Faz 3 retry düzeltmesi sayesinde) |
| `…/appointments/<id>`, `…/astro-ai/reports/<id>` | ilgili ekran, bulunamazsa hemen bildirim |
| `…/profile/account/delete`, `…/calls/<id>/incoming` | ana sayfa |
| `…/reset-password?token=…` (oturum açıkken) | ana sayfa (Faz 1 davranışı). Oturum kapalıyken token ile sıfırlama ekranı açılıyor (widget testi) |
| Push'a dokunma (`subscription_renewed`) | Planlar ekranı (`routeForNotification`, Faz 3) |

**Sınır:** soğuk başlatmada oturum gerektiren bir link (sipariş gibi) açılış ekranından sonra ana sayfaya düşer; link hedefi saklanmaz. Reset link'i bundan etkilenmez.

**Blocker (değişmedi):** `https://astrofrekansteams-cmd.github.io/astrofrekansapp/reset-password.html` hâlâ **404**. Siteye dokunulmadı.

## Testler

**Backend: 979 passed** (26 dk). Yeni `tests/test_phase4_store.py` (12 test):
- normal push kanal + ses; arama push'u data-only;
- `check_revoked` iki mod; iptal / devre dışı / silinmiş; Firebase erişilemezse 502 ve token loglanmıyor; API üzerinden iki mod;
- katalog türleri ve eşlemesi; ID yazım/tekrar kontrolü; production reddi; eski kodun pasifleşmesi;
- Google plan yaşam döngüsü.

**Flutter:** `flutter analyze` temiz; `flutter test` **312 passed, 2 skipped**. Yeni testler:
- `test/core/astro_background_test.dart` (6): 8/sn güncelleme; gizli ekranda, arka planda ve Reduce Motion'da durma; bütçe; hızlı cihazda sürme.
- `test/core/deep_links_test.dart` (4): allowlist; motorun gönderdiği `pushRouteInformation` ile reset ve bildirim link'leri, yasak link → ana sayfa.
- `test/features/phase4_store_test.dart` (8): başarı, iptal, bekleme, zaten sahip, sessiz mağaza, restore ilerleme ve sonuç, restore hatasında planın korunması, TR/EN bildirim ve sınırlı ilerleme çubuğu.

**Android profile build ile emülatör smoke** (Docker 8000):

| Adım | Sonuç |
|---|---|
| Cold start | açılış → ana sayfa (oturum geri yüklendi) |
| Bildirim kanalı + gerçek FCM push | `astrofrekans_default`, badge, ses, marka ikonu ve rengi |
| Arka plan / devam | arka planda ~%0 CPU; dönüşte sekme durumu korundu |
| Premium ekranı | mağaza yok notu, "—", satın al ve geri yükle pasif |
| AstroCoin cüzdanı | bakiye 20 (gerçek API harcamasıyla tutarlı), paketler pasif, not |
| Geri yükleme UI | mağaza yokken pasif; bağlıyken durumlar birim/widget testinde |
| Deep link'ler | tabloya bakın |
| Bildirimler / push'a dokunma | doğru ekran |
| Düşük cihaz / performans | twinkle bütçeyle kapandı, boşta %0 |
| Staging Firebase APK | açıldı, giriş ekranı; giriş yapılmadı |

**Temizlik:**
- Kullanıcının emülatör oturumu yedeklendi ve birebir geri yüklendi (hash aynı).
- Smoke hesabının push cihazı silindi, oturumları kapatıldı.
- Animasyon ayarları varsayılanda. Api container `.env` ayarında çalışıyor (gating geçici açıldı, geri alındı).
- Emülatörde kurulu olan: 8000 / local_jwt profile APK.
- Test şifreleri yalnızca scratchpad'deki state dosyasında; komut satırına ve çıktıya yazılmadı.

## Mağazaya geçmeden kalan blocker'lar

1. **Mağaza ürünleri ve bilgileri:**
   - Play/App Store ürünleri henüz yok; `STORE_PRODUCT_IDS` boş.
   - `GOOGLE_PLAY_*` servis hesabı, RTDN Pub/Sub ve Apple anahtarları yapılandırılmamış.
   - Ürünler oluşturulunca license tester / sandbox ile test edilmeli: satın alma, **plan değişimi (yeni `ChangeSubscriptionParam` yolu cihazda denenmedi)**, restore, iade RTDN.
2. **Google girişi:** kodda kapalı ama buton soluk halde "yakında" diyerek görünüyor. İnceleme riski var. Karar gerekli:
   - Uygularsak: `google_sign_in` veya `signInWithProvider` kullanılır; release ve Play App Signing SHA-1'leri Firebase'e eklenir.
   - Uygulamazsak: production'da buton gizlenir.
   - Google girişi sunulursa iOS'ta Sign in with Apple zorunlu (mevcut).
3. **Release imzalama:** Firebase'de yalnızca debug SHA-1'i kayıtlı. Release ve Play App Signing parmak izleri eklenmeli.
4. **`firebase_check_revoked` kararı:** yukarıdaki öneri.
5. **Staging Firebase manuel testi:** yukarıdaki 5 adım.
6. **SMTP bilgileri** (Faz 3): şifre sıfırlama bilerek 503 dönüyor.
7. **Reset sayfası 404** (site kapsam dışı).
8. **iOS:** değişiklikler Dart tarafında (deep link, billing UI, twinkle). Swift değişmedi, ama bu ortamda iOS build alınamadı. Bir Mac'te build + smoke gerekli.
9. **Legacy ürünler** (`natal_report`, `synastry_report`, `annual_forecast_report`, `ai_pre_analysis`): mağazada oluşturulacaklar mı, yoksa ID'siz bırakılıp gizli mi kalacaklar? Karar gerekli.
10. **Ödeme sağlayıcısı (PSP)** kararı (canlı 1:1 seanslar): hâlâ `disabled`.
11. **Önerilen (blocker değil):**
    - `EffectsBudget` eşiğini (16 ms) gerçek düşük/orta cihazlarda logcat satırıyla gözlemle.
    - Mesaj ve hatırlatmalar için ayrı bir HIGH bildirim kanalı düşünülebilir.

## Değişen / eklenen dosyalar (Faz 4)

**Android:**
- `android/app/src/main/AndroidManifest.xml`
- `kotlin/.../NotificationChannels.kt` (yeni), `MainActivity.kt`, `AstroCallMessagingService.kt`
- `res/drawable/ic_stat_astrofrekans.xml` (yeni), `res/values/strings.xml` (yeni), `res/values-en/strings.xml` (yeni), `res/values/colors.xml`

**Flutter:**
- `lib/core/widgets/astro_background.dart`, `lib/core/widgets/effects_budget.dart` (yeni)
- `lib/core/routing/deep_links.dart` (yeni), `lib/core/routing/app_router.dart`
- `lib/features/billing/data/billing_models.dart`, `billing_service.dart`
- `lib/features/billing/application/entitlement_controller.dart`
- `lib/features/billing/presentation/purchase_status.dart` (yeni), `premium_screen.dart`, `coin_wallet_screen.dart`
- `lib/core/localization/b12_copy.dart`

**Backend:**
- `app/services/firebase/firebase_provider.py`, `fake_provider.py`
- `app/services/payments/catalog.py`, `app/core/config.py`

**Testler:**
- `backend/tests/test_phase4_store.py`
- `test/core/astro_background_test.dart`, `test/core/deep_links_test.dart`, `test/features/phase4_store_test.dart`

**Build çıktısı:** `build/staging/astrofrekans-staging-firebase.apk`
