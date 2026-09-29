# Faz 1 — Kritik kullanıcı akışları

Tarih: 27 Eylül 2026. Kapsam: kullanıcı/admin incelemesindeki P1/P2 kullanıcı akışları. Yeni özellik, admin paneli, store/AdMob ve commit yok.

## Durum

| Konu | Durum | Not |
|---|---|---|
| Stale slot | FIXED | Tarih değişince seçim + intent temizlenir, CTA kapanır; istemci gönderimde seçimin görünen güne ait olduğunu yeniden kontrol eder; sunucu `selected_local_date` + `selected_utc_offset_minutes` ile `422 slot_date_mismatch` döner. Son onay: Tarih, Saat, Saat dilimi, Uzman, Hizmet. |
| Kullanıcı iptali / iade | FIXED | Sipariş ve randevu iptali tek yol: `services/marketplace/cancellation.py`. Ödenmiş sipariş → `refund_pending` + tek iade talebi (`cancel:{order_id}`), açık ödeme niyetleri kapanır, çağrılar durur. |
| Uzman iptali / iade | FIXED | Uzmanın randevu iptali siparişi aynı yoldan iptal eder; aynı finansal sonuç. |
| Tamamlama akışı | FIXED | Canlı seans: başlangıç saatinden sonra kullanıcı (`POST /orders/{id}/complete`) veya uzman (`POST /expert/orders/{id}/complete`). Yazılı analiz: `POST /expert/orders/{id}/deliver`. Çağrı bitişi siparişi tamamlamaz (invariant korundu); çağrı sonrası ekrandan siparişe yönlendirme var. |
| Hakediş serbest bırakma | FIXED (kurala bağlı) | Tamamlama `SettlementService.release_order` çağırır. `EXPERT_SETTLEMENT_HOLD_DAYS` kararı yok → otomatik serbest bırakma yok (tasarım gereği). `hold=0` ile test edildi. |
| Ödeme sonrası yenileme | FIXED | Ödeme bölümü her yenilemede sipariş, randevu, ödeme ve hak durumunu birlikte yeniler; uygulamaya dönüşte (resume) de yeniler. Başarılı ödemede "Ödeme onaylandı" + "Görüşmeye Git" / "Randevuyu Gör". |
| Şifre sıfırlama | PARTIAL | Kod hazır (genel yanıt, enumeration yok, 30 dk, tek kullanımlık, yeni istek eskisini geçersiz kılar, deep link, süresi dolmuş/kullanılmış ekranı). Üretimde e-posta sağlayıcısı kimlik bilgileri yok → endpoint dürüstçe `503 password_reset_unavailable` döner. |
| Harici PSP | BLOCKED | Sağlayıcı kararı gerekli. `fake` (test) / `disabled` korunuyor. |

## Randevu merkezi

- Yaklaşan / Geçmiş / İptal edilen filtreleri.
- İptal öncesi onay: hizmet, tarih/saat, saat dilimi ve olası iade durumu (sunucunun `cancellation` önizlemesi).
- İade durumu (incelemede / iade edildi / reddedildi / başarısız) sipariş ve randevu ekranından görünür.
- İptal butonu önceden genel `cancel` anahtarı yüzünden "Vazgeç" yazıyordu; "Randevuyu iptal et" oldu.

## Sipariş okuma modeli (türetilir, saklanmaz)

`lifecycle`, `actions`, `completion_block`, `refund`, `cancellation`, `delivery` ve `timeline` alanları eklendi. Ekrandaki durum etiketleri:

- Bekliyor
- Ödendi
- Planlandı
- Tamamlanmayı bekliyor
- Tamamlandı
- İptal edildi
- İade incelemesinde
- İade edildi

## Testler

- Backend tam paket: **931 geçti** (önce 908). Yeni: `tests/test_phase1_flows.py` (23 test).
  - Kullanıcı/uzman iptali, tekrarlanan iptal, ödenmiş/ödenmemiş sipariş, mevcut veya kısmi iade.
  - İptal sonrası gelen ödeme, iade reddi/onayı.
  - Tamamlama (canlı/yazılı), hakediş, ödeme yenileme sözleşmesi, slot tarihi.
  - Şifre sıfırlama: mail, tek kullanım, süre, enumeration, mailer yok, prod reddi, SMTP.
- Değişen sözleşme: iptal edilmiş siparişi tekrar iptal etmek artık `409` değil, aynı sonucu `200` döndürür (idempotent). Tamamlanmış sipariş iptali hâlâ `409`. İlgili test güncellendi.
- Randevu yoluyla iptal edilen aramanın bitiş nedeni `appointment_cancelled` olarak korundu.
- Flutter: `flutter analyze` temiz. `flutter test` **251 geçti, 2 atlandı** (önce 234). Yeni: `test/features/phase1_flows_test.dart` (17 test).
  - Tarih değişince seçim temizlenir, eski slot gönderilemez, onay içeriği, sunucu tarih uyumsuzluğu.
  - İptal onayı, iade durumları, filtreler, ödeme sonrası yenileme, şifre sıfırlama durumları.

## Android emülatör smoke (gerçek API)

Ortam: yerel Postgres/Redis üzerinde bu kod, `:8001` portunda. Ayarlar: `AUTH_MODE=local_jwt`, `MAIL_PROVIDER=log`, `EXTERNAL_PAYMENT_PROVIDER=fake`. Uygulama debug derlemesi `10.0.2.2:8001`'e bağlıydı. Ödeme onayı, test sağlayıcısının imzalı webhook'uyla simüle edildi.

| Senaryo | Sonuç |
|---|---|
| Yanlış gün slot | Uygulamada 27 Eylül'de saat seçildi, tarih 28 Eylül yapıldı → seçim temizlendi, buton kapandı; basmak bir şey göndermedi. API'de uyumsuz gün → `422 slot_date_mismatch`. Doğru günle sipariş 28.09 18:00 UTC kaydedildi. |
| Kullanıcı iptali | Randevu detayından iptal → onay diyaloğu "9.99 TRY iade incelemesine alınır" → "İade incelemesinde"; DB'de tek talep (`user_cancellation`, `manual_review`). |
| Uzman iptali | Uzman rotası (API) iki kez çağrıldı → tek iade talebi (`expert_cancellation`). Kullanıcı ekranında "İade incelemesinde · 9.99 TRY". Ödenmemiş siparişte iade açılmadı. |
| Ödeme sonrası yenileme | "Bekliyor / Ödeme bekleniyor" → webhook → "Ödeme durumunu yenile" → "Planlandı / Ödendi", "Ödeme onaylandı + Görüşmeye Git", zaman çizelgesinde "Ödeme alındı". |
| Tamamlama | Seans saati geçmişe alındı → "Tamamlanmayı bekliyor" + "Hizmet gerçekleşti olarak işaretle" → onay → "Tamamlandı". |
| Değerlendirme | Tamamlama sonrası form açıldı, kayıt `201`. |
| Şifre sıfırlama | "Şifremi unuttum" → genel yanıt → log e-postasındaki `astrofrekans://app/reset-password?token=…` deep link → yeni şifre → başarı → aynı bağlantı tekrar: "daha önce kullanılmış" → yeni şifreyle giriş (uygulama + API). |

Smoke'un yakaladığı ve düzeltilen sorunlar:

- Log mailer, Windows konsolunda (cp1252) Türkçe karakterde hata veriyordu. Artık ASCII-güvenli yazıyor. Hata zaten kullanıcıya sızmıyordu.
- Sıfırlama ekranı açıkken farklı bir bağlantı gelirse eski token'ın durumu korunuyordu. Rota artık token'a göre key'li.
- Onay diyaloğunda gün adı İngilizce çıkıyordu. Artık uygulama diliyle biçimleniyor.
- Kısa sıfırlama ekranlarında geri butonu ortada kalıyordu. Artık üste hizalı.

Smoke'ta uygulamadan denenmeyenler: uzman ekranından tamamlama/teslim (API ve widget testleriyle doğrulandı), Firebase/hybrid şifre sıfırlama (staging Firebase'e dokunulmadı).

## Kalan blocker'lar

1. **Harici PSP** — sağlayıcı kararı gerekli. Canlı 1:1 seanslar üretimde tahsil edilemez.
2. **E-posta sağlayıcısı** — üretimde bir SMTP relay'i gerekli (`MAIL_PROVIDER=smtp`, `SMTP_HOST`, `MAIL_FROM`, kimlik bilgileri). Olmadan sıfırlama `503` döner.
3. **Sıfırlama bağlantısı** — bağlantı adresi (`PASSWORD_RESET_URL_BASE`) için karar gerekli. Çoğu e-posta istemcisi `astrofrekans://` gibi özel şemaları tıklanabilir yapmaz. Uygulamaya yönlendiren bir https sayfası (App Links / Universal Links) için alan adı ve doğrulama dosyaları gerekir.
4. **Hybrid/Firebase derlemeleri** — şifre sıfırlama Firebase'in kendi e-postası ve sayfasıyla yapılır. Firebase e-posta şablonu doğrulanmadı.
5. **Hakediş bekleme süresi** — `EXPERT_SETTLEMENT_HOLD_DAYS` iş kararı bekliyor.
6. **İade inceleme ve onay yüzeyi** — iade kuyruğu var, ama onay/red yalnızca servis metodu. Bu, admin fazında ele alınacak.
7. **Canlı PostgreSQL eşzamanlılığı** — iptal satır kilidi eşzamanlı isteklerle gerçek PostgreSQL'de denenmedi. Testler SQLite'ta koştu; smoke tek iş parçacıklıydı.
8. **Önceki incelemeden açık kalan** — giriş hız sınırı `X-Forwarded-For` ile aşılabiliyor. Faz 1 kapsamı dışında.
9. **Eski kusur testi** — `reports/review_booking_probe_test.dart` eski kusuru doğruluyor, artık başarısız olur. `test/` dışında olduğu için pakete girmiyor.
10. **Çalışan Docker API** (`:8000`) eski kodla çalışıyor. Yeni kod için yeniden derlenmesi gerekir; veritabanı migration'ı gerekmiyor.
