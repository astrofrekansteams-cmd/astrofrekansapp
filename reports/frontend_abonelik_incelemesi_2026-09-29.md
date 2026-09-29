# Astrofrekans — kullanıcı deneyimi ve abonelik incelemesi

İnceleme: 28–29 Eylül 2026. Güncel kaynak kodu, yeni web derlemesi, Chrome'da yerel demo kullanıcı ve Flutter ekran testleri kullanıldı. Uygulama kaynak kodu değiştirilmedi. Bu çalışma frontend incelemesidir; gerçek mağaza ödemesi ve native cihazda uçtan uca satın alma doğrulaması değildir.

## Genel değerlendirme

Koyu lacivert, altın çizgiler, astroloji görselleri ve başlık yazı tipi birbiriyle tutarlı. Profil artık hesap, hizmetler ve uygulama ayarları olarak gruplanmış. Ana sorun görsel kimlikten çok, kullanıcının hangi özelliğe nasıl ulaşacağını ve hangi paketin neyi açacağını anlaması.

Ana sayfa, Keşfet ve Profil yerel demo oturumunda gezildi. 390×844 ve 320×640 boyutlarında; normal ve %200 yazıyla Home, Explore, Profile, Register ve Premium bileşenleri kaydırılarak kontrol edildi. Ekran testlerindeki hesap, fiyat ve içerikler test verisidir. Plan karşılaştırması güncel backend katalog fonksiyonlarından alınmıştır; mağaza fiyatları değildir.

## Doğrulanan hatalar ve işlevsel eksikler

### 1. P1 — Kozmik+ özellikleri Premium diye sunuluyor

**Kullanıcı senaryosu:** İlişki analizi veya yıllık öngörüyü açmak isteyen kullanıcı “Premium” kilidi ve “Premium ile aç” mesajı görüyor. Oysa Sinastri, Composite, Davison, yıllık öngörü ve dönüş haritaları backend'de Kozmik+ gerektiriyor. Premium satın alması bu özellikleri plana dahil hale getirmiyor; ayrıca coin alternatifi var.

**Kanıt:**

- [Keşfet kilit rozeti](/C:/astrofrekans/lib/features/explore/presentation/explore_screen.dart:266) sadece kilitli/kilitsiz bilgisi alıyor; tüm kilitlerde aynı Premium metnini gösteriyor.
- [Kilit kartı](/C:/astrofrekans/lib/features/billing/application/coin_spend.dart:198) gerekli planı parametre olarak almıyor.
- [Kullanıcı mesajları](/C:/astrofrekans/lib/core/localization/b12_copy.dart:693) özelliğin Premium ile kullanılabileceğini söylüyor.
- [Gerçek plan eşlemesi](/C:/astrofrekans/backend/app/services/features.py:39).

**Öneri:** Rozet ve kilit kartı gerçek gerekli tier'ı kullanmalı: “Kozmik+ ile dahil” ve “30 AstroCoin ile bu içeriği aç”. Satın alma ekranında ilgili plan önceden seçilmeli. Kullanıcı hangi özelliği açmak için geldiğini kaybetmemeli.

### 2. P1 — Abonelik yönetimi ve yenileme açıklaması eksik

Plan ekranında satın alma ve satın alımları geri yükleme var. Uygulama içinde aboneliği yönetme/iptal merkezine giden bağlantı bulunamadı. “Aylık / Yıllık” fiyat satırlarında otomatik yenileme, iptalin nasıl yapılacağı ve satın alma koşullarına erişim açıklanmıyor. “Erişim bitişi” tek başına yenileme bilgisinin yerini tutmuyor.

**Kanıt:** [Plan ekranı](/C:/astrofrekans/lib/features/billing/presentation/premium_screen.dart:154), [fiyat satırı](/C:/astrofrekans/lib/features/billing/presentation/premium_screen.dart:513). `lib` içinde ilgili mağaza abonelik merkezi URL'si veya yönetim eylemi bulunmadı.

**Öneri:** “Aboneliği Yönet”, yenileme/erişim tarihi, satın alınan mağaza ve açık yenileme açıklaması eklenmeli. Gizlilik ve kullanım koşulları da ödeme ekranından erişilebilir olmalı. Google açık yenileme bilgisi ve uygulama içinden kolay iptal yöntemine erişim istiyor: [Google Play abonelik politikası](https://support.google.com/googleplay/android-developer/answer/9900533?hl=en).

### 3. P2 — Mevcut planın aylık/yıllık seçeneğine geçiş yok

**Kullanıcı senaryosu:** Premium aylık kullanıcısı yıllık Premium'a geçmek istiyor. Mevcut plan kartındaki tüm satın alma satırları `!current` şartıyla kaldırılıyor. Bu yüzden aynı tier içinde dönem değiştirecek bir eylem yok; Kozmik+ için de aynı durum geçerli.

**Kanıt:** [Koşul](/C:/astrofrekans/lib/features/billing/presentation/premium_screen.dart:495).

**Öneri:** “Mevcut plan” ile “mevcut ödeme dönemi” ayrı tutulmalı. Mevcut ürün seçili gösterilmeli; alternatif dönem için “Yıllığa geç” eylemi olmalı. Değişikliğin ne zaman başlayacağı ve mağazanın hesapladığı ücret farkı açık gösterilmeli.

### 4. P2 — Küçük ekran ve büyük yazıda satın alma satırı taşıyor

320×640, %200 sistem yazı boyutu, örnek yerelleştirilmiş fiyatlar `₺199,99` ve `₺1.999,99` ile satın alma satırında **10 ve 40 piksel yatay taşma** tekrarlandı. Satırdaki fiyat ve satın alma butonu esnemiyor.

**Kanıt:** [Satın alma Row bileşeni](/C:/astrofrekans/lib/features/billing/presentation/premium_screen.dart:538), [inceleme test kaydı](/C:/astrofrekans/reports/frontend_review_20260928_test.log).

**Öneri:** Dar alanda dönem/fiyat üstte, tam genişlikte buton altta olacak şekilde yerleşim değişmeli. Fiyatı küçültmek veya kesmek yerine sarmalayan düzen kullanılmalı.

### 5. P3 — Keşfet grup başlığı küçük miktarda taşıyor

Aynı 320×640 ve %200 yazı senaryosunda grup başlığının Row'u **0,770 piksel** taşıyor. Satın alma taşması kadar ağır değil; yine de erişilebilirlik sınırında yerleşim hatası var.

**Kanıt:** [Grup başlığı](/C:/astrofrekans/lib/features/explore/presentation/explore_screen.dart:251).

**Öneri:** Başlık `Flexible` ile sarmalanmalı; dar alanda dekoratif çizgi kaldırılabilir.

### 6. P2 — Mağaza fiyatları yüklenemediğinde yeniden deneme yolu yok

Coin kataloğu hatasında yeniden deneme eklenmiş. Ancak mağaza ürünlerinin ayrı yükleme yolu hata alınca yalnızca `storeAvailable=false` yapıyor. `loadCatalog()` yalnızca ilk başlangıçta çağrılıyor; ekranın “Tekrar dene” eylemi sadece coin kataloğunu yeniliyor. Geçici bağlantı sorunu yaşayan kullanıcı aynı oturumda fiyatları tekrar yükleyemeyebilir.

**Kanıt:** [Mağaza yükleme](/C:/astrofrekans/lib/features/billing/application/entitlement_controller.dart:153), [yalnız coin kataloğunu yenileyen eylem](/C:/astrofrekans/lib/features/billing/presentation/premium_screen.dart:104).

**Öneri:** Gerçekten desteklenmeyen ortam ile geçici bağlantı hatası ayrılmalı. Desteklenen mağazada “Fiyatları yeniden yükle” eylemi bulunmalı.

## Frontend için tasarım önerileri

1. **Ana sayfada günlük eylemi öne çıkar.** Frekans kartı 390 px görünümde ekranın büyük bölümünü kaplıyor. Kartı kısaltıp hemen altına “Kartını çek”, “Günlük yorum”, “Danışman bul” kısa yolları ekle. Yalnız puanları görmek yerine kullanıcıya bugün yapacağı bir eylem ver.
2. **Keşfet'i kategori seçimiyle kısalt.** Astroloji, İlişkiler, Açılımlar, Danışmanlar sekmeleri/chip'leri ve üstte arama kullan. Şu an danışmanlar, öngörüler, dönüşler ve kişisel rehberlerden sonra geliyor. Danışmana ulaşmak fazla kaydırma istiyor.
3. **Teknik astroloji adlarına günlük dil ekle.** “Sinastri — İlişki uyumunuz”, “Composite — İlişkinizin ortak dinamiği”, “Solar Return — Yeni yaş yılın” gibi açıklamalar kullan. Mevcut “karşılıklı açılar ve ev bindirmeleri” yeni kullanıcı için hâlâ uzman dili.
4. **Kayıt formunu iki adıma böl.** Önce hesap bilgileri, sonra doğum bilgileri; ilerleme göstergesi ve doğum yerinde şehir seçimi. Şu an uzun formda kayıt butonuna ulaşmak için kaydırmak gerekiyor. “Doğum saatimi bilmiyorum” seçeneğini koru, hangi hesapların yaklaşık olacağını açıkla.
5. **Satış ekranında kararı üstte verdir.** Taç, slogan, teknik açıklama, mevcut plan, bonus kartı ve uzun karşılaştırma tablosundan sonra fiyatlara geliniyor. Üste plan/dönem seçimi, fiyat ve üç temel fayda; alta açılabilir karşılaştırma koy. Coin paketlerini ayrı cüzdan sayfasına taşı. Mevcut plan sayfasındaki “sunucu tarafından doğrulanır” metnini kullanıcı faydasıyla değiştir.
6. **Profilde tekrarları azalt.** Profil kalemi + Profil menüsü; Hesap Merkezi + ayrıca Doğum Bilgileri/Gizlilik yolları var. Bunları tek anlaşılır hesap alanında topla. Yaklaşan randevu ve okunmamış mesaj gibi zaman duyarlı içerikleri profilin üstüne ve ana sayfaya taşı.
7. **Puanın anlamını açıklayan kısa bilgi ekle.** “84/100 neye göre?” eylemi ile kişiselleştirme girdileri ve yorumun sınırları açıklansın. Günlük puanların yanında kısa, uygulanabilir rehberlik bulunsun.
8. **Ödeme durumunu işlem yapılan yerde göster.** `PurchaseStatusNotice` sayfanın en sonunda. Kullanıcı plan seçtiği sırada “Mağaza açılıyor / Onay bekleniyor / Erişim açıldı” durumunu aynı kartta veya sabit alt alanda görmeli.

## Önerilen abonelik modeli

Mevcut Ücretsiz / Premium / Kozmik+ isimleri korunabilir. Premium günlük kullanım, Kozmik+ ilişki analizleri ve daha derin kişisel çalışmalar için anlatılmalı. Coin, pakete dahil olmayan tek kullanımlık işlemlerin alternatifi olmalı.

| Plan | Kullanıcıya vaat | İçerik önerisi | Türkiye için başlangıç fiyat hipotezi |
|---|---|---|---|
| Ücretsiz | Uygulamayı gerçekten deneyimle | Günlük özet, temel doğum haritası, mevcut 3 açılım/gün; arşive erişim | 0 TL |
| Premium | Günlük kişisel rehberliğin | Reklamsız, gelişmiş açılımlar, aylık öngörü, gelişmiş transitler; mevcut 15 açılım/gün ve 150 coin/ay | 149,99 TL/ay veya 1.499,99 TL/yıl |
| Kozmik+ | İlişkilerini ve uzun dönemini keşfet | Premium'a ek ilişki haritaları, yıllık öngörü, dönüş haritaları, ileri AI; mevcut 40 açılım/gün; uzun AI raporlarına açık aylık bütçe | 299,99 TL/ay veya 2.999,99 TL/yıl |

Bunlar pazar araştırması sonucu veya mağazada tanımlı fiyatlar değildir. Türkiye pazarı varsayımıyla test edilecek başlangıç adaylarıdır. Gerçek fiyat; mağaza kesintileri, vergi, model kullanımı, iade oranı ve kullanıcı başına destek maliyeti görüldükten sonra belirlenmeli. Azerbaycan ve diğer ülkelerde mağazanın yerelleştirilmiş fiyatı kullanılmalı.

### Coin ve AI kuralı

- Mevcut katalogda açılım 10, gelişmiş açılım 25, derin AI yorumu 40, uzun rapor 60, tek premium içerik 30 coin. Bu ayrım ödeme öncesi net görünmeli.
- Pakete dahil bir işlemden tekrar coin düşülmemeli. UI açıkça “Planına dahil” yazmalı.
- Kozmik+ şu an neredeyse tüm ücretli işlemleri açarken ayrıca 500 coin veriyor. Kullanıcı bu bonusu nerede harcayacağını anlamayabilir. Paket dışı ek kullanımların somut listesini göster; yeterli kullanım alanı yoksa bu bonusu ana satış vaadi yapma.
- Uzun AI raporları için “sınırsız” vaat etme. Örneğin 10 rapor/ay ilk test kotası olabilir; son karar gerçek üretim maliyetiyle verilmeli. Kalan hak ve yenilenme günü görünmeli. Saatlik teknik hız sınırı, anlaşılır bir aylık abonelik hakkının yerini tutmaz.
- Yıllık abonelikte aylık haklar her ay verilsin. “500 coin/ay” yazıyorsa bunu yıllık ödeme anında tek seferlik bonus gibi uygulama.
- Canlı uzman seanslarını ayrı hizmet olarak fiyatlandır. Coin veya abonelik satın alırken uzman görüşmesinin dahil olup olmadığı açık olsun.
- Yeniden açılan önceden üretilmiş rapor yeni üretim sayılmamalı. Arşiv ile yeni rapor üretimi ayrı anlatılmalı.

Aboneliğin ana değeri düzenli güncellenen kişisel içerik ve özellik erişimi olmalı. Coin bonusu destekleyici fayda olarak kalmalı; [Google Play](https://support.google.com/googleplay/android-developer/answer/9900533?hl=en) ve [Apple](https://developer.apple.com/app-store/subscriptions/) abonelikte süreklilik taşıyan değer bekliyor.

### Ödeme ekranının önerilen sırası

1. Açmak istediğin fayda: örneğin “İlişki analizini aç”.
2. Premium / Kozmik+ ve Aylık / Yıllık seçimi.
3. Toplam tahsil edilecek fiyat; yıllık üründe yıllık toplam daha belirgin, aylık karşılığı ikincil.
4. Üç somut fayda ve varsa kullanım kotası.
5. “Kozmik+'a abone ol” butonu; açık otomatik yenileme ve iptal bilgisi.
6. Ayrıntılı karşılaştırma, satın alımları geri yükle, aboneliği yönet ve koşullar.

## Yeni özellikler için öncelik

- **Önce:** Ana sayfada yaklaşan randevu/rapor teslimi, kalan haklar ve kaldığın yerden devam et kartı.
- **Sonra:** “Yorum bana uydu mu?” geri bildirimiyle kişisel günlük; geçmiş yorum ve notlarda arama.
- **Sonra:** Kaydedilen bir kişi için ilişki analizlerini tek sayfada toplayan kişi dosyası.
- **Daha sonra:** Haftalık kişisel özet ve kullanıcı seçimiyle hatırlatma. Bu düzenli fayda abonelik değerini de güçlendirir.

## Doğrulama ve sınırlar

- `flutter analyze --no-pub`: sorun yok.
- Mevcut Flutter paketi: **334 başarılı, 2 atlanan**. [Log](/C:/astrofrekans/reports/frontend_full_tests_20260928.log).
- Ek responsive inceleme: **20 senaryo, 18 başarılı, 2 başarısız**; iki hata yukarıdaki taşmalar. [Test](/C:/astrofrekans/reports/frontend_review_20260928_test.dart).
- İki ek kullanıcı beklentisi testi de hataları tekrar üretti: mevcut Premium kartında yıllık seçenek bulunamadı; Kozmik+ gereken ilişki analizinde doğru paket etiketi bulunamadı. **Ek inceleme toplamı: 22 senaryo, 18 başarılı, 4 başarısız.** Bu dört başarısızlık mevcut sorunları görünür kılmak için yazılan, beklenen kullanıcı davranışını doğrulayan testlerdir. [Test ve tekrar üretme koşulları](/C:/astrofrekans/reports/frontend_plan_contract_review_test.dart), [log](/C:/astrofrekans/reports/frontend_plan_contract_review_test.log).
- Güncel profile web derlemesi başarılı; Chrome'da mock giriş, ana sayfa, Keşfet, Profil gezildi. Native Android/iOS ödeme, gerçek API randevusu ve mağaza yenilemesi bu turda denenmedi. Demo ortamında bulunmayan veri/mağaza olanakları üretim hatası sayılmadı.
- Test hesabı/fiyatları ve çizim kontrolü kullanıldı. Bu ekran görüntüleri uygulama bileşenlerinin test render'larıdır: [Ana sayfa](/C:/astrofrekans/reports/frontend_preview_20260928/home.png), [Keşfet](/C:/astrofrekans/reports/frontend_preview_20260928/explore.png), [Kayıt](/C:/astrofrekans/reports/frontend_preview_20260928/register.png), [Planlar](/C:/astrofrekans/reports/frontend_preview_20260928/premium.png).
- Önceki randevu tarihi seçimi, ödeme sonrası yenileme, dil eşitleme, ayar kaydetme başarısızlığında geri alma, premium katalog hata görünümü gibi düzeltmeler mevcut frontend testlerinde kapsanıyor ve bu çalıştırmada geçti. Eski bulgular yeniden açık hata olarak yazılmadı. Backend test paketi bu turda yeniden çalıştırılmadı.

## Uygulama sırası

1. Yanlış paket etiketleri, abonelik yönetimi/yenileme açıklaması ve mevcut planın dönem değiştirmesi.
2. Küçük ekran taşmaları ve mağaza kataloğu tekrar denemesi.
3. Plan ekranının sadeleşmesi, Keşfet kategorileri ve ana sayfa kısa yolları.
4. Gerçek maliyet ölçümü sonrası fiyat/kota deneyi; sonra düzenli geri dönüş sağlayan yeni özellikler.
