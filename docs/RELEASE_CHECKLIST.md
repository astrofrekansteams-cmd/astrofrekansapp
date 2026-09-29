# Astrofrekans yayın kontrolü

29 Eylül 2026 kod durumuna göre. Bu liste, yerel test sonucunu mağaza yayınıyla eşitlemez.

## Kodda hazırlananlar

- Üretim derlemesi `API_BASE_URL`, `AUTH_MODE=hybrid`, üretim Firebase dosyaları ve yayımlanmış `TERMS_URL` ister.
- Codemagic koşullar, gizlilik, destek, hesap silme ve şifre sıfırlama sayfalarını canlı olarak kontrol eder.
- Yerel hesaplar için şifre sıfırlama e-postası kapalıysa backend üretim modunda başlamaz.
- Şifre sıfırlama kodu artık sayfa URL'sinin `#token=` bölümündedir; statik sunucuya istekle gönderilmez.
- Görseller Git LFS ile saklanır. Codemagic derlemede LFS dosyalarını indirir.

## Yayından önce tamamlanacaklar

1. `codex/release-legal-pages` dalındaki sayfaları ürün ve hukuk açısından inceleyip `main` dalına alın. Canlı `terms.html` ve `reset-password.html` adreslerinin 200 döndürdüğünü doğrulayın. Gizlilik metnine veri sorumlusunun kimliği, açık saklama süreleri ve uygulanabilir kullanıcı hakları eklenmelidir.
2. Hesap silme akışında kullanıcı metinleri, yüklenen görseller ve profil verileri için gerçek silme veya açıkça tanımlanmış saklama işlemi uygulayın. Şu anki işlem erişimi kapatır ve oturumları iptal eder; içerikleri anında fiziksel olarak silmez. Gerekli finansal kayıtları ayrı tutun.
3. Üretim Firebase projesini Android ve iOS için kurun. Yerel dosyalar `astrofrekans-staging` projesine aittir ve üretim doğrulamasından geçmez. Gerçek yapılandırmaları yalnızca CI gizli değişkenlerine koyun.
4. HTTPS üretim API'sini, veritabanını, Redis'i, SMTP'yi, AI ve canlı görüşme sağlayıcılarını kurun. `PREMIUM_GATING_ENABLED=true`, mağaza ürün kimlikleri ve Apple/Google doğrulama kimlik bilgileriyle backend üretim kontrollerini çalıştırın.
5. Google Play ve App Store ürünlerini, abonelik fiyatlarını ve yenileme koşullarını oluşturun. Gerçek mağaza hesaplarıyla satın alma, iptal, süresi dolma ve geri yükleme senaryolarını uçtan uca deneyin.
6. Codemagic'de Android yükleme anahtarını, iOS App Store imzalama profilini ve üretim değişkenlerini tanımlayın; imzalı AAB ve IPA'yı yeniden üretin. Eski yerel AAB yayın kanıtı sayılmaz.
7. Gerçek Android/iPhone cihazlarında giriş, şifre sıfırlama, hesap silme, bildirim, canlı görüşme ve ödeme akışlarını test edin. Mağaza listeleme, ekran görüntüleri, veri güvenliği/gizlilik beyanları ve inceleme hesabını tamamlayın.

`assets/` yaklaşık 903 MB Git LFS verisi içerir. Tekrarlanan CI indirmeleri GitHub LFS kotasını kullanır; görselleri küçültmek yayın maliyeti ve indirme süresi açısından ayrıca değerlendirilmelidir.
