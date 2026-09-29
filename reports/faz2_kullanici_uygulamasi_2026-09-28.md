# Faz 2 — Kullanıcı uygulaması tamamlama

Tarih: 28 Eylül 2026. Kapsam: kullanıcı uygulaması. Admin paneli, site, mağaza/Play Console/AdMob ve gerçek ödeme sağlayıcısı kapsam dışı. Commit yok.

## Özet

| Konu | Durum |
|---|---|
| Hesap Merkezi | TAMAM |
| Bildirim Merkezi | TAMAM |
| Dil sistemi | TAMAM |
| Ayar kaydında geri alma | TAMAM |
| Gece yarısı / gün yenileme | TAMAM (cihazda yalnızca resume denendi, bkz. smoke) |
| Saat dilimi ayrımı | TAMAM |
| Premium katalog hata durumu | TAMAM |
| Kayıtlı kişi düzenleme | TAMAM |
| Uzman global arama | TAMAM |
| Profil menüsü | TAMAM |

## 1. Hesap Merkezi

Profil → Hesabım → Hesap Merkezi. Altı bölüm var; her biri ayrı ekran.

- **Hesap Bilgileri:** ad, dil ve yaşanılan şehir (şehir aramasıyla saat dilimi seçilir).
- **Doğum Bilgileri:** yalnızca doğum tarihi, saati ve yeri. Artık Hesap Bilgileri ile aynı forma gitmiyor.
- **Şifre Değiştir:** mevcut şifre, yeni şifre ve tekrarı.
  - Backend: `POST /auth/change-password`, hesap başına saatte 10 deneme.
  - Diğer cihazlardaki oturumlar kapanır; bu cihaz yeni şifreyle kendiliğinden yeniden giriş yapar.
  - Firebase hesabında şifre Firebase'de, mevcut şifreyle yeniden doğrulandıktan sonra değişir.
- **Oturumlar / Cihazlar:**
  - `GET /auth/sessions`: cihaz başına bir satır; tarayıcı/cihaz bilgisi, kısaltılmış IP (`85.105.x.x`), son kullanım.
  - "Bu cihaz" işaretlidir (access token artık oturum kimliği `sid` taşıyor) ve kapatılamaz.
  - `DELETE /auth/sessions/{id}` o oturumun yenileme token'ını hemen iptal eder.
  - Bildirim alan cihazlar ayrı bir listede; buradan kaldırılabilir.
- **Gizlilik ve Güvenlik:** mevcut görünürlük ayarları.
- **Hesabı Sil:**
  - Önce `GET /users/me/deletion-check` ile kontrol.
  - Aktif randevu, tamamlanmamış sipariş, incelemedeki iade varsa ya da kullanıcı uzmansa ve kendisine verilmiş açık sipariş varsa silme engellenir ve ne açık olduğu gösterilir.
  - Silmek için şifre (şifresi olmayan Firebase hesabında e-posta), "anlıyorum" onayı ve son bir diyalog gerekir.
  - Kayıtlar silinmez (soft delete): tüm oturumlar kapanır, push cihazları devre dışı kalır, uzman profili `inactive` olur. Sipariş, ödeme ve muhasebe kayıtları durur. Log'a e-posta yazılmaz.

Smoke'ta bulunup düzeltilen hata: yanlış mevcut şifre `401` dönüyordu. İstemci bunu "oturum geçersiz" sanıp önce token yenilemeye, sonra da çıkışa götürebilirdi; smoke'ta kullanıcı giriş ekranına düştü. Artık `403 current_password_incorrect` dönüyor. Gerçek HTTP akışıyla (interceptor dahil) regresyon testi eklendi.

## 2. Bildirim Merkezi

Push ile aynı olay kaynağı kullanılıyor (`notification_outbox`). Sahte bildirim üretilmiyor.

- Migration `0017` ekler: `read_at` sütunu ve kullanıcı+tarih indeksi. Yerel Postgres'te uygulandı.
- Uç noktalar:
  - `GET /notifications`: imleçli sayfalama, kategori filtresi, yalnızca okunmamışlar seçeneği.
  - `GET /notifications/unread-count`
  - `PATCH /notifications/{id}`: okundu/okunmadı. Başkasının bildirimi 404.
  - `POST /notifications/read-all`
- Kategoriler:
  - Astro AI / rapor
  - Randevu (cevapsız arama dahil)
  - Danışman mesajı
  - Ödeme / iade (abonelik dahil)
  - Sistem
  - Promosyon
- Listeye girmeyenler:
  - Arama sinyalleri (gelen, cevaplanan, iptal edilen arama).
  - Vakti gelmemiş hatırlatmalar.
  - İptal edilen randevunun düşürülmüş hatırlatmaları.
- Push gönderilemese de (cihaz yok) bildirim listede görünür. Veri yalnızca kimlik (id) taşır; metni uygulama yazar.
- Ana sayfadaki zil "yakında" yerine okunmamış sayısını gösterir ("9+"). Sayı merkez kapanınca ve uygulamaya geri dönülünce yenilenir.
- Bildirime dokununca ilgili ekran açılır: randevu, sipariş, sohbet, rapor ya da plan.

## 3. Dil sistemi

- Profilde, Ayarlar'da ve ana sayfada seçilen dil hem uygulamayı hem backend'deki hesap dilini değiştirir. Hesaba kaydedilemezse uygulama dili geri alınır ve hata gösterilir.
- Giriş yapınca hesabın dili uygulamaya uygulanır. Yeni hesap, kişinin o an kullandığı dille açılır.
- Azerbaycanca seçenek kaldırıldı; tam çevirisi (`app_az.arb`) gelince geri eklenmesi tek satır.
- Sabit metin denetimi: arama ekranları, sipariş ödeme bölümü ve ücretli rapor bölümündeki ~70 sabit Türkçe metin TR/EN çeviriye taşındı. Arama durum adları da çevrildi (önce `ended`, `connected` gibi ham adlar görünüyordu).

## 4. Ayar kaydında geri alma

- Bildirim ve gizlilik anahtarları hemen değişir (iyimser güncelleme).
- Kayıt başarısız olursa anahtar sunucudaki değere döner, hata kartı ve "Tekrar Dene" çıkar. Tekrar Dene, başarısız olan değişikliği yeniden gönderir.

## 5. Gece yarısı / gün yenileme

- `todayProvider` artık saati okuyan `CurrentDayController`'a bağlı. Değişiklik yalnızca istemcide; backend'e dokunulmadı.
- Gece yarısından ~2 sn sonra bir zamanlayıcı günü ilerletir. Uygulamaya dönüşte (resume) tarih ayrıca kontrol edilir, çünkü telefon uyurken zamanlayıcı çalışmaz.
- Günü izleyen içerikler yeniden yüklenir: günlük frekans, ana sayfadaki Ay kartı ve Ay rehberi.
- Test: 23:59:58 → 00:00:03 ve uyku sonrası resume senaryosu (`clockProvider` ile).

## 6. Saat dilimi ayrımı

Backend iki saat dilimini zaten ayrı tutuyordu; hata Flutter eşlemesindeydi. `UserProfile` artık ikisini ayrı taşıyor:

| Alan | Kaynak | Kullanım |
|---|---|---|
| `timezone` | hesap (`users/me`) | yerel saat, randevu, bildirim, "bugün" |
| `birthTimezone` | doğum profili (`birth-profiles/me`) | yalnızca doğum haritası |

- Doğum Bilgileri kaydı yalnızca `PUT birth-profiles/me` gönderir; Hesap Bilgileri kaydı yalnızca hesabı değiştirir.
- Smoke'ta doğrulandı: yaşanılan yer Bakü seçildi (`Asia/Baku`); doğum yeri İstanbul (`Europe/Istanbul`) değişmedi. Doğum bilgisi kaydı Bakü'ye dokunmadı.

## 7. Premium katalog hata durumu

Ayrı durumlar:

- Yükleniyor
- Yüklendi
- Boş ("Şu anda gösterilecek plan yok" + Tekrar Dene)
- Ağ hatası ("Planlar yüklenemedi" + Tekrar Dene)
- Mağaza kullanılamıyor (planların üstünde not)

Riverpod arka planda yeniden denerken bile hata durumu gösterilir; sonsuz iskelet yok.

## 8. Kayıtlı kişi düzenleme

- `PATCH /saved-people/{id}` ile ad, doğum tarihi, saati, yeri, saat dilimi ve "saat bilinmiyor" değiştirilebilir. Yalnızca gönderilen alanlar değişir.
  - Yeni bir yer girilirse eski yerin koordinatları taşınmaz; yer yeniden geocode edilir.
- Kişi listesinde kalem simgesi var; "düzenleme desteklenmiyor" notu kaldırıldı.
- Eski raporlar bozulmaz: raporlar kendi girdi verisinin parmak iziyle (fingerprint) saklanıyor. Düzenleme sonrası yeni rapor ayrı bir kayıt olarak üretilir; eski raporun parmak izi, içeriği ve etiketi aynı kalır. Bu bir testle doğrulandı.

## 9. Uzman global arama

- `GET /experts?q=`: isim, başlık, biyografi ve uzmanlık adlarında (TR/EN; "astroloji", "doğum", "sinastri"…) tüm uzmanlarda arar.
- Büyük/küçük harf, i/ı/İ farkı ve aksanlar (ş, ç…) aramayı etkilemez; "ayse" "Ayşe"yi bulur.
- Dil, fiyat, uzmanlık, "bugün müsait" ve sıralama filtreleriyle birlikte çalışır; sayfalama korunur.
- İstemci 350 ms bekleyip sunucuya sorar. Favoriler (tek parça liste) yerelde süzülür.

## 10. Profil menüsü

Gruplar:

- **Hesabım:** Profil · Hesap Merkezi · Doğum Bilgileri · Kaydedilen Kişiler · Gizlilik
- **Hizmetlerim:** Randevularım · Siparişlerim · Mesajlarım · Raporlarım · Favoriler · Görüşme Geçmişi
- **Astrofrekans:** Planım · AstroCoin · Bildirimler · Ayarlar

Uzman bölümü yalnızca uzman profili olanlarda görünür. "Çıkış Yap" en altta, ayrı ve kırmızı.

## Testler

- **Backend tam paket:** **944 geçti** (Faz 1 sonu 931). Yeni: `tests/test_phase2_account.py` (13 test).
  - Oturumlar ve oturum kapatma
  - Şifre değişimi
  - Silme için yeniden doğrulama ve engeller (kullanıcı ve uzman)
  - Uzman profilinin aramadan çıkması
  - Gelen kutusu: görünürlük, kategori, okundu, sayfalama
  - Kişi düzenleme ve eski raporun korunması
  - Global arama
- **Flutter:** `flutter analyze` temiz; `flutter test` **271 geçti, 2 atlandı** (Faz 1 sonu 251). Yeni: `test/features/phase2_flows_test.dart` (20 test).
- **Güncellenen dört eski test:**
  - Marketplace: artık sunucu araması bekleniyor.
  - Premium: mağaza notunun yeri değişti.
  - Arama ve ödeme widget testleri: Türkçe yerel ayar eklendi.
- **Android emülatör smoke (gerçek API, `:8001`, `local_jwt`):**
  - Zil sayacı ve bildirim merkezi: okundu/okunmadı, kategori filtresi, bildirimden siparişe yönlendirme, tümünü okundu yap.
  - Profil menüsü sırası (TR ve EN).
  - Hesap Merkezi: oturum kapatma, Bakü seçimi, doğum bilgisi kaydı.
  - Şifre değiştirme: yanlış şifre hatası; doğru şifreyle yeniden giriş dahil.
  - Dil değişimi: uygulama İngilizce oldu, hesapta `en`.
  - Toggle geri alma: API kapalıyken anahtar geri döndü, API açılınca Tekrar Dene kaydetti.
  - Premium hata durumu ve Tekrar Dene.
  - Kişi düzenleme: saat bilinmiyor.
  - Global arama.
  - Silme engeli ekranı.
  - Resume'da yenileme.
  - Hesap silme uçtan uca API ile ayrı bir tek kullanımlık hesapta denendi: yanlış şifre reddedildi, silme 200, sonrasında erişim 401, yeniden giriş 401.
- **Cihazda denenmeyen:** gece yarısı geçişi. Emülatörün sistem saatini değiştirmek gerekiyordu; widget testiyle kapsanıyor.

## Kalan blocker'lar

1. **Faz 1'den:** harici ödeme sağlayıcısı kararı, üretim e-posta sağlayıcısı, sıfırlama bağlantısı için https alanı.
2. **Push bildirim metinleri:** kilit ekranında görünen push başlığı ve metni sunucuda Türkçe sabit. Uygulama içi merkez çevriliyor; push'un kullanıcının diline göre gönderilmesi ayrı bir iş.
3. **Firebase/hybrid oturumlar:** Firebase ile açılan oturumlar listede görünmüyor (Firebase yönetiyor). Hybrid derlemede şifre değişimi Firebase üzerinden; bu akış gerçek Firebase'de denenmedi.
4. **Sabit metin denetiminin kalanı:** `transit_meaning.dart`'taki astroloji yorum sözlüğü Türkçe ve sabit; ayrı bir çeviri işi.
5. **Çalışan Docker API (`:8000`):** eski kodla çalışıyor. Yeniden derlenmesi ve `alembic upgrade head` (0017) gerekiyor.
6. **Uzman aramasının ölçeği:** arama, uzmanlık ve dil filtreleri SQLite/Postgres uyumu için Python'da yapılıyor; en fazla 500 uzman taranır. Uzman sayısı büyüyünce Postgres tam metin araması gerekir.
