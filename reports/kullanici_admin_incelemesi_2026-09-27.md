# Astrofrekans: kullanıcı ve admin incelemesi

Tarih: 27 Eylül 2026. Kapsam: bu depodaki Flutter istemcisi, FastAPI backend, ekran yönlendirmeleri, iş kuralları ve yerel testler. Gerçek mağaza satın alımı, canlı ödeme sağlayıcısı, fiziksel cihazdaki arama/push ve üretim ortamı bu incelemede uçtan uca denenmedi.

## Genel değerlendirme

Uygulama, kişisel astroloji + AI + kart açılımı + uzman danışmanlığı etrafında geniş bir ürün temeline sahip. Görsel dil tutarlı; backend tarafında ödeme doğrulaması, para tutarlarının tam sayı tutulması, siparişe bağlı izinler, tekrar eden isteklerin yönetilmesi ve bildirim kuyruğu gibi önemli altyapılar mevcut. Ancak kullanıcı yolculuğunun özellikle hesap kurtarma, danışmanlıktan çıkış, iptal/iade ve yönetim aşamalarında tamamlanmamış bağlantılar var.

Bu nedenle öncelik, yeni içerik türleri eklemeden önce mevcut hizmetin baştan sona tamamlanmasını sağlamak olmalı.

## Öncelikli mantık hataları ve eksikler

### 1. P1 — Randevuyu iptal etmek siparişin iade sürecini başlatmıyor

**Yeniden üretildi.** Ödenmiş bir randevu hem kullanıcı hem uzman endpoint'inden iptal edildiğinde randevu `cancelled`, sipariş `confirmed`, ödeme `paid` kalıyor; iade talebi sayısı sıfır.

Sipariş iptal servisi iade incelemesi açarken randevu iptal servisi bunu yapmıyor. Böylece aynı hizmet için iki iptal yolu farklı finansal sonuç veriyor. Kullanıcı iptal edilmiş bir hizmetin parasını takip edemiyor; adminin iade kuyruğuna da kayıt düşmüyor.

Öneri: iki yolu ortak bir iptal işlemi üzerinden yürütmek; sipariş, randevu, çağrı ve iade incelemesini aynı işlemde tutarlı hale getirmek. İptal öncesinde olası iade sonucunu göstermek.

Kanıt: [randevu endpoint'i](../backend/app/api/v1/orders.py#L403), [uzman iptali](../backend/app/api/v1/orders.py#L645), [randevu servisi](../backend/app/services/marketplace/booking.py#L422), [sipariş iptali](../backend/app/services/marketplace/orders.py#L491). Reprodüksiyon: `review_backend_probe.py` ve `review_backend_probe.log`.

### 2. P1 — Hizmetin tamamlanması kullanıcı/uzman akışına bağlanmamış

`OrderService.complete()` var, fakat uygulama kodunda bu metoda ulaşan bir endpoint veya üretim çağrısı bulunmuyor. Canlı görüşmenin bitmesi de siparişi tamamlamaya bağlanmamış. Servisin kendi açıklaması da bu yüzeyin henüz olmadığını belirtiyor.

Etkisi: tamamlanmış danışmanlık `completed` durumuna geçemediğinde değerlendirme yazma ve uzman kazancının serbest bırakılması doğal akışta çalışamıyor.

Öneri: teslim edildi/tamamlandı/itiraz süreci, görüşme sonucu ve teslim türüne uygun kurallar; uzman ve kullanıcıya sonraki adımı gösteren tek bir sipariş zaman çizelgesi.

Kanıt: [tamamlama](../backend/app/services/marketplace/orders.py#L552), [kazanç serbest bırakma koşulu](../backend/app/services/payments/settlement.py#L82), `lib/features/marketplace/data/marketplace_models.dart` içindeki `reviewEligible`.

### 3. P1 — Canlı uzman hizmetleri için gerçek harici ödeme adaptörü yok

Factory yalnızca test sağlayıcısı veya kapalı sağlayıcı döndürüyor. Bu, yalnızca bir anahtar girilerek açılacak mevcut bir gerçek sağlayıcı entegrasyonu değil. Ücretli canlı danışmanlık akışının tahsilat adımı eksik. Dijital ürünlerin mağaza entegrasyonu bundan ayrı bir alan.

Öneri: seçilen sağlayıcının ödeme başlatma, imzalı bildirim, başarısızlık, süre aşımı, iade ve mutabakat yollarını tamamlamak. Satın alınamayan hizmetleri rezervasyon aşamasından önce anlaşılır biçimde belirtmek.

Kanıt: [provider factory](../backend/app/services/payments/factory.py#L50).

### 4. P1 — Admin operasyon yüzeyi bulunmuyor

Bu depoda admin ekranı veya admin işlemlerini sunan ayrı API yönlendirmesi yok. Uzman onayı, askıya alma, iade onayı ve ödeme çıkarma için bazı servisler yazılmış, fakat yönetim yüzeyi henüz bağlanmamış. Bu bir yetki aşımı tespiti değil; operasyonu uygulama üzerinden yürütememe eksikliği.

Öneri: aşağıdaki admin kapsamını, rol ve işlem kaydı ile birlikte oluşturmak. Servis metotlarını kimlik/yetki kontrolü olmadan dışarı açmamak.

Kanıt: [uzman onayı](../backend/app/services/marketplace/experts.py#L279), [hakediş işlemleri](../backend/app/services/payments/settlement.py#L145), `backend/app/api/v1/router.py`, `lib/core/routing/app_router.dart`.

### 5. P1 — Şifre kurtarma tamamlanmamış

Girişte “Şifremi unuttum” yalnızca “yakında” bildirimi gösteriyor. Backend token üretiyor fakat e-posta göndermiyor; buna rağmen API yanıtı bağlantının gönderildiğini söylüyor. Yerel JWT hesabıyla şifresini unutan kullanıcı için gerçek kurtarma yolu yok.

Öneri: e-posta gönderimi, sıfırlama bağlantısının uygulamada açılması, yeni şifre formu ve süresi geçmiş bağlantı ekranı. Hesap var/yok bilgisini açığa çıkarmayan yanıt yapısını korumak.

Kanıt: [giriş ekranı](../lib/features/auth/presentation/login_screen.dart#L184), [backend reset isteği](../backend/app/api/v1/auth.py#L138).

### 6. P1 — Takvimde gün değişince eski saatle rezervasyon yapılabiliyor

**Widget etkileşimiyle yeniden üretildi.** Bir günün saatini seçip takvimden ertesi güne geçince görünür saatlerde seçim yok, ama rezervasyon düğmesi açık kalıyor. Düğmeye basınca önceki günün saati gönderiliyor.

Nedeni: gün değişikliğinde yalnızca `date` güncelleniyor; `selected` ve `intent` temizlenmiyor.

Öneri: tarih değişiminde seçimi temizlemek, gönderimde seçilen slotun görünür güne ait olduğunu kontrol etmek ve son onayda tam gün/saat/saat dilimi göstermek.

Kanıt: [tarih değişimi](../lib/features/marketplace/presentation/booking_screens.dart#L127), [isteğin hazırlanması](../lib/features/marketplace/presentation/booking_screens.dart#L61). Reprodüksiyon: `review_booking_probe_test.dart`.

### 7. P2 — Ödeme sonrası sipariş ekranı eski durumda kalabiliyor

Ödeme bileşeni ödeme durumunu yeniliyor, ancak üst ekrandaki sipariş provider'ını yenilemiyor. “Ödeme durumunu yenile” de yalnızca ödeme bileşenini güncelliyor. Böylece ödeme onaylansa bile açık sipariş sayfasında `pendingPayment` durumu ve görüşme erişimleri eski kalabiliyor.

Öneri: ödeme sonucu ve dış ödeme uygulamasından dönüşte sipariş/randevu/ödeme durumunu birlikte yenilemek; sonuca göre net bir “Görüşmeye git” eylemi sunmak.

Kanıt: [ödeme yenilemesi](../lib/features/billing/presentation/order_payment_section.dart#L69), [sipariş koşulları](../lib/features/marketplace/presentation/booking_screens.dart#L296).

### 8. P2 — Profilde dil değiştirmek uygulamanın dilini değiştirmiyor

Profil formu `language` değerini backend'e kaydediyor. Uygulamanın dili ise ayrı `localeControllerProvider` tarafından yönetiliyor; profil kaydı bu controller'ı güncellemiyor. Profil ekranında Azerbaycanca seçeneği de var, ancak uygulamanın desteklenen dilleri yalnızca Türkçe ve İngilizce.

Öneri: hesap dili ve uygulama dili için tek tutarlı akış; desteklenmeyen seçeneği tam çeviri gelene kadar sunmamak. Ödeme, arama, randevu durumları ve izin etiketlerindeki sabit Türkçe/teknik metinleri de çevirmek.

Kanıt: [dil kaydı](../lib/features/profile/presentation/profile_settings_screens.dart#L44), [Azerbaycanca seçeneği](../lib/features/profile/presentation/profile_settings_screens.dart#L155), [desteklenen diller](../lib/core/localization/locale_controller.dart#L13), [profil güncelleme](../lib/features/auth/application/session_controller.dart#L178).

### 9. P2 — Ayar kaydı başarısız olunca anahtar yeni değerde kalıyor

Bildirim/gizlilik anahtarları sunucu yanıtından önce değişiyor. İstek başarısız olursa hata gösteriliyor fakat anahtar eski değerine dönmüyor. Kullanıcı özellikle bir bildirimi veya görünürlüğü kapattığını yanlış anlayabilir.

Öneri: başarısız istekte eski değere dönmek veya kaydedilmemiş durumu açıkça göstermek; yeniden deneme sunmak.

Kanıt: [ayar değiştirme](../lib/features/profile/presentation/profile_settings_screens.dart#L244).

### 10. P2 — Yeni güne geçildiğinde ana sayfa dünkü içeriği koruyabiliyor

`todayProvider` zamanı ilk okumada hesaplayan, zamanlayıcısı olmayan bir provider. Ana sayfayı yenileme yalnızca günlük içerik provider'ını geçersiz kılıyor; tarih provider'ını değil. Açık oturum gece yarısını geçtiğinde başlık ve istenen içerik tarihi eski kalabilir.

Öneri: gün sınırında ve uygulama tekrar öne geldiğinde tarihi kontrol edip günlük içerikleri yenilemek.

Kanıt: [tarih provider'ı](../lib/core/astrology/astrology_providers.dart#L12), `lib/features/home/application/home_providers.dart`, ana ekranın `onRefresh` işlevi.

### 11. P2 — Doğum saat dilimi ve yaşanılan yerin saat dilimi karışıyor

Backend bunları ayrı tutuyor. Flutter dönüşümünde ise doğum profili saat dilimi kullanıcı profilinin saat diliminin önüne geçiyor. Profil güncellenirken aynı değer hem kullanıcıya hem doğum profiline yazılıyor.

Örnek: İstanbul'da doğmuş ve Bakü'de yaşayan kişinin doğum verisini düzenlemek hesap saat dilimini İstanbul'a çevirebilir. Sonraki kişisel gün/tarih gösterimleri yanlış bölgeyi kullanabilir.

Öneri: `birthTimezone` ve `timezone` alanlarını ayrı modellemek; kullanıcıya yaşadığı bölgeyi ayrıca seçtirmek.

Kanıt: [DTO](../lib/features/auth/data/auth_dto.dart#L48), [hesap güncelleme](../lib/features/auth/data/api_auth_repository.dart#L111), aynı dosyada doğum profili payload'ı.

### 12. P2 — Plan kataloğu hatası sonsuz yükleme gibi gösteriliyor

Premium ekranı katalogdaki hata bilgisini `asData?.value` ile kaybediyor. Katalog gelmezse boş plan listesi üzerinden sürekli iskelet görünümü çiziliyor; katalogya özel hata/yeniden dene eylemi yok.

Öneri: yükleniyor, boş, bağlantı hatası ve mağazada kullanılamıyor durumlarını ayrı göstermek.

Kanıt: [katalog okuma](../lib/features/billing/presentation/premium_screen.dart#L33), [boş plan gösterimi](../lib/features/billing/presentation/premium_screen.dart#L96).

## Kullanıcı açısından gerekli tamamlamalar

- **Hesap merkezi:** hesap silme ve şifre değiştirme endpoint'lerini arayüze bağlamak. Mevcut “Hesap Bilgileri” ve “Doğum Bilgileri” aynı forma gidiyor; “Gizlilik ve Güvenlik” yalnızca profil görünürlük anahtarlarını içeriyor.
- **Gerçek bildirim merkezi:** ana sayfadaki zilin rozeti sürekli açık ve tıklama “yakında” mesajı veriyor. Okunmamış sayısı, okundu işareti ve ilgili kayda yönlendirme gerekli. Push teslim altyapısı bulunması bu ekranın yerini tutmuyor.
- **Randevu/sipariş merkezi:** yaklaşan/geçmiş/iptal filtreleri, yeniden planlama, hizmet öncesi hazırlık, ücret/iade açıklaması ve tek olay zaman çizelgesi. Şu an iptal düğmesi doğrudan işlem yapıyor; sonuç özeti ve onay adımı gerekli.
- **İade takibi ve destek:** API'deki iade talebi/listesi kullanıcıya açılmalı; talep nedeni, tutar, durum ve destek kaydı aynı siparişten erişilmeli.
- **Kayıtlı kişileri düzenleme:** mevcut arayüz ekleme/silme sunuyor ve API'nin düzenleme desteklemediğini kullanıcıya teknik cümleyle bildiriyor. Basit bir doğum saati düzeltmesi silip yeniden oluşturmayı gerektirmemeli; eski raporların tarihsel görüntüsü korunmalı.
- **Uzman araması:** mevcut metin araması yalnızca yüklenmiş sayfadaki uzmanları filtreliyor ve bunu etiketinde belirtiyor. Tüm uzmanlarda arama, dil, fiyat, uzmanlık ve uygun saat filtreleri birlikte çalışmalı.
- **Kayıt sürtünmesi:** ilk kayıtta uzun doğum formu yerine hesap açıldıktan sonra neden gerekli olduğunu anlatan adımlı tamamlama; doğum saati bilinmiyorsa hangi sonuçların sınırlı kaldığını açıklamak.
- **Profil menüsü:** randevu/sipariş/mesajları çıkış düğmesinin altından daha görünür bir “Hizmetlerim” grubuna taşımak. Uzman çalışma alanını role göre sunmak; kullanıcıya başvuru yolu göstermek.
- **Plan ve AstroCoin açıklığı:** mevcut coin harcama onayı fiyat ve bakiye gösteriyor; bu olumlu. Planın kapsadığı haklarla tek seferlik coin kullanımı arasındaki ilişkiyi tüm satın alma ekranlarında aynı dille anlatmak ve teknik “sunucu doğruladı” mesajlarını işlem sonucuna çevirmek gerekli.

## Admin ve uzman operasyonları için gerekli kapsam

| Alan | Gerekli ekran ve işlem |
|---|---|
| Operasyon özeti | Bugünkü randevular, yaklaşan görüşmeler, bekleyen iadeler, başarısız ödemeler ve geciken raporlar; ilgili kayda tek tık |
| Kullanıcı yönetimi | Kullanıcı arama, hesap durumu, satın alma/hak geçmişi, destek kayıtları, sınırlı yetkili müdahaleler |
| Uzman yönetimi | Başvuru inceleme, onay/ret/askıya alma, belge ve uzmanlık doğrulama, hizmet denetimi |
| Randevu yönetimi | Kullanıcı/uzman takvimi, çakışma, gelmedi/iptal/teknik sorun durumu, yeniden planlama ve sonuç takibi |
| Finans | Ödeme–sipariş eşleştirme, iade kuyruğu, komisyon, bekleyen/kullanılabilir hakediş, ödeme çıkarma ve mutabakat |
| Katalog ve planlar | Hizmet aktifleştirme, mağaza ürün eşleştirmeleri, plan hakları, coin fiyatları ve değişiklik geçmişi |
| AI operasyonu | Bekleyen/başarısız rapor işleri, kontrollü tekrar deneme, maliyet/kota, kullanıcı geri bildirimi ve içerik inceleme |
| Bildirim operasyonu | Şablonlar, kullanıcı tercihleri, teslim hataları ve tekrar deneme durumları |
| Destek/moderasyon | Siparişe bağlı şikâyet, kullanıcı/uzman itirazı, yorum incelemesi; gerekli veriyle sınırlı erişim |
| Yetki ve kayıt | Admin, destek, finans, içerik sorumlusu rolleri; hassas işlem gerekçesi ve kim-ne-zaman kaydı |

Mevcut uzman çalışma alanı hizmetleri ve çalışma saatlerini listeliyor; bunları düzenleyen kontroller, izin/tatil yönetimi ve kazanç ekranları eksik. Backend'de karşılıkları bulunan işlemler bu panele bağlanmalı. Admin paneli ayrı hazırlanmalı.

## Eklenebilecek özellikler — mevcut hatalar kapandıktan sonra

1. **Kişisel günlük:** günlük yorum/kart açılımına not ekleme, ruh hali kaydı, geçmişi ay/tarih/konu ile arama. Kullanıcıyı geri getiren kişisel bir arşiv oluşturur.
2. **Birleşik “Bugün” ekranı:** günlük yorum, yaklaşan randevu, hazır rapor ve tek önerilen sonraki adımı bir araya getirir.
3. **Açıklanabilir sonuçlar:** mevcut AI etken listelerini “Bu puan neden böyle?”, kullanılan doğum verisi ve saat belirsizliğinin etkisiyle geliştirmek. Sayısal astroloji endekslerinin anlamını anlaşılır kılar.
4. **Uzman eşleştirme:** kullanıcının konusu, dili, bütçesi ve uygun zamanına göre birkaç uygun uzman; öneri gerekçesi görünür olmalı.
5. **Hizmet öncesi hazırlık formu:** soru, paylaşılacak doğum profili, rapor ve izinleri randevudan önce tamamlama. Mevcut backend izin modelinden yararlanır.
6. **Paylaşılabilir rapor/PDF:** kullanıcının seçtiği bölümlerle, kişisel doğum verisini varsayılan olarak içermeyen dışa aktarım.
7. **Admin ürün analitiği:** kayıt → doğum profili → ilk yorum → satın alma → tamamlanan hizmet aşamalarındaki terk oranları; hata ve iade nedenleriyle birlikte.

## Önerilen uygulama sırası

1. **İş kaybını ve kullanıcı mağduriyetini engelle:** yanlış gün rezervasyonu, iptal/iade tutarlılığı, tamamlanma akışı, gerçek ödeme adaptörü, hesap kurtarma.
2. **Operasyonu yönetilebilir yap:** temel admin paneli, uzman yönetimi, iade/hakediş kuyruğu ve destek.
3. **Günlük kullanım pürüzlerini gider:** dil, ayar kaydı, gün yenileme, saat dilimi, ödeme ekranı senkronizasyonu, bildirim merkezi ve kayıtlı kişi düzenleme.
4. **Sonra ürün geliştirme:** günlük, açıklanabilir raporlar, uzman eşleştirme ve analitik.

## Doğrulama kanıtları

- `flutter analyze --no-pub`: temiz, 188.2 saniye.
- Tam Flutter test paketi: **234 geçti, 2 atlandı**; `review_flutter_tests.log`.
- Tam backend test paketi: **908 geçti**, 972.02 saniye. Testler izole SQLite ve test sağlayıcılarıyla çalışır; gerçek PostgreSQL eşzamanlılığı veya canlı sağlayıcı kabul testi yerine geçmez.
- Randevu iptalindeki finansal tutarsızlık: **iki izole API senaryosunda yeniden üretildi** (kullanıcı/uzman). SQLite ve sahte ödeme sağlayıcısı kullanıldı; gerçek hesap/para işlemi yapılmadı.
- Yanlış gün rezervasyonu: **bir widget etkileşim testiyle yeniden üretildi**; `review_booking_probe.log`.
- Güncel kaynaklardan ana sayfa, profil ve giriş ekranı için **3 görsel yakalama testi geçti**; `review_preview/`. Görseller test verisiyle üretilmiş tek ekran önizlemeleridir; home/profile uygulama kabuğu ve alt gezinmeyi içermez.
- Diğer bulgular kaynak kodu ve çağrı/yönlendirme takibiyle doğrulandı; her biri gerçek cihazda uçtan uca denenmiş kabul edilmemeli.
- Üretim uygulama kodu değiştirilmedi. İnceleme raporu, reprodüksiyon betikleri ve çıktılar `reports/` altında tutuldu.
