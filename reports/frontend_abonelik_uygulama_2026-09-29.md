# Frontend ve abonelik düzenlemeleri — 29 Eylül 2026

## Uygulananlar

- Keşfet ve tek kullanımlık içerik kilitleri, özellik kataloğundaki gerekli planı gösterir. Kozmik+ gerektiren içeriğe Premium etiketi basılmaz. Katalog bilinmiyorsa genel plan çağrısı kullanılır.
- Kilit ekranından planlara geçiş, gerekli planı öne çıkarır.
- Aktif planda aylık ve yıllık seçenekler görünür. Mevcut aboneliğin ödeme dönemi ve iptali için kullanıcı satın aldığı mağazayı seçer; resmi App Store veya Google Play abonelik yönetimi açılır. Uygulama mevcut mağaza ürününü tahmin ederek ikinci abonelik satın almaz.
- Plan fiyatları avantaj listesinin üstüne taşındı; karşılaştırma tablosu açılır bölüm oldu. AstroCoin paketleri cüzdanda toplandı.
- Otomatik yenileme bilgisi eklendi. Satın alma durumu ekranın altından izlenebilir.
- Mağaza fiyatları yeniden yüklenebilir; yükleme sürerken tekrar istek engellenir. Eksik fiyatlar sabit fiyatlarla doldurulmaz.
- Plan ve coin fiyat satırları küçük ekran ve büyük yazı boyutuna uyum sağlar. Kilit rozeti, özellik başlığının altında gösterilir.
- Keşfet'e kategori filtreleri ve özellik araması eklendi. Arama, bölüm/özellik adlarını tarar; uzman profilleri üzerinde sunucu araması değildir.
- Ana sayfaya kart çekme, günlük yorum ve danışman bulma kısayolları ile frekans puanı açıklaması eklendi.
- Kayıt formu iki adıma ayrıldı. İlk adım doğrulanır; geri dönüldüğünde alanlar korunur.
- Profilde yinelenen plan menüsü kaldırıldı; üst plan kartı korundu. Çıkış düğmesinin alt menü arkasında kalmasını önlemek için kaydırma boşluğu artırıldı.

## Verilen sayfalar

Aşağıdaki yayımlanmış sayfalar HTTP 200 ve sayfa başlıklarıyla doğrulandı; abonelik ve profil ekranlarına bağlandı:

- Gizlilik: https://astrofrekansteams-cmd.github.io/astrofrekansapp/
- Destek: https://astrofrekansteams-cmd.github.io/astrofrekansapp/support.html
- Hesap silme bilgisi: https://astrofrekansteams-cmd.github.io/astrofrekansapp/delete-account.html

Kullanım koşulları belgesi verilmedi. `TERMS_URL` derleme ayarı hazırdır; boş olduğunda sahte bağlantı gösterilmez. `PRIVACY_URL` ile gizlilik adresi değiştirilebilir. Bu çalışma dışarıdaki HTML sayfalarını veya yayın ayarlarını değiştirmedi.

## Doğrulama

- Tam Flutter turu: **341 geçti, 2 atlandı, 2 başarısız**. Başarısız kontroller eski arayüz beklentileriydi: kapalı karşılaştırma tablosu ve görünür alana gelmeden çıkış düğmesine basılması.
- Bu iki kontrol yeni akışa göre güncellendi; ilgili dosyalar ile abonelik/kayıt regresyonlarının son tekrarı **22/22 geçti**. Tam suite bu test güncellemelerinden sonra yeniden çalıştırılmadı.
- Kanıtlar: `frontend_fix_full_final.log`, `frontend_fix_final_regressions.log`, `frontend_fix_responsive.log`, `frontend_fix_analyze_final.log`.
- Son statik analiz: `dart analyze` → **No issues found!**. Flutter analiz başlatıcısı beklediği için aynı projede doğrudan Dart SDK analiz aracı kullanıldı.

- Görsel/yerleşim kontrolü: 5 ekran × 2 genişlik (320, 390) × 2 yazı ölçeği (1, 2) = **20/20 geçti**. Kayıt ekranında bu tarama ilk adımı kapsar; ikinci adıma geçiş ayrı widget testindedir.
- Ayrı regresyonlar: aktif planda yıllık seçenek, gerekli Kozmik+ etiketi, kilitli 320px/2x düzeni, iki mağazanın yönetim bağlantısı, gizlilik bağlantısı, aramada sonuçsuz durumdan dönüş, kayıt doğrulaması ve geri dönüş, mağaza kataloğunun yeniden yüklenmesi.
- Görseller `reports/frontend_preview_20260929/` altında. Bunlar sahte verili widget yakalamalarıdır; ekran görüntülerindeki fiyatlar test verisidir.

## Yayın öncesi kalanlar

- Gerçek iOS/Android mağaza sandbox hesaplarında satın alma, geri yükleme, iptal, dönem değişikliği ve sunucu bildirimleri uçtan uca doğrulanmalıdır. Widget testleri gerçek mağaza işlemi değildir.
- Yayımlanmış kullanım koşulları bağlantısı eksik.
- Destek sayfasındaki “üçüncü taraflarla paylaşılmaz” ifadesi ile gizlilik politikasındaki üçüncü taraf hizmetleri birlikte gözden geçirilmeli. Silme ve yanıt süresi vaatleri gerçek işleyişle eşleştirilmeli.
- Önerilen yeni fiyatlar, AI kotaları ve mağaza ürün yapılandırması bu frontend çalışmasında değiştirilmedi. Bunlar maliyet ve mağaza doğrulamasından sonra ele alınmalıdır.
- Dağıtım/yayın yapılmadı.
