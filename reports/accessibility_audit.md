# Erişilebilirlik hızlı denetimi

Kapsam: Home, Astro AI, Login, Register ve Onboarding kaynak incelemesi. Bu bir ekran okuyucu/cihaz testi değildir; tasarım değiştirilmedi.

| Ekran | Semantics ve hedefler | Risk |
|---|---|---|
| Home | Skor ve kılavuz öğeleri `Semantics`, ikon butonları etiketli; ortak `AstroIconButton` en az `AppSpacing.minTapTarget` alanı açıyor. | `_GuidanceItem` ve chip'ler için gerçek dokunma alanı ile VoiceOver/TalkBack sırası cihazda doğrulanmalı. |
| Astro AI | Gönder, ses ve ek butonlarında semantic label var; mesaj balonunda semantic metin bulunuyor. | Streaming/typing güncellemelerinin ekran okuyucuya tekrar tekrar okunmaması cihazda kontrol edilmeli. |
| Login | Geri ve logo etiketli; parola görünürlüğü butonunda tooltip var. | Form hata duyurusu ve klavye focus sırası manuel test gerektirir. |
| Register | Date/time picker `Semantics` ile sarmalanmış; parola butonunda tooltip. | `authBirthTimeUnknown` metnine bağlı `GestureDetector` ayrı semantic button/checkbox ilişkisi kurmuyor; hit area cihazda ölçülmeli. |
| Onboarding | Sayfa içeriğinde `Semantics` var. | Sayfa değişiminde announce/focus geçişi ve küçük telefonlarda büyük metin manuel test gerektirir. |

Genel: `MaterialApp` metin ölçeğini 0,9–1,6 aralığına kısıyor; 1,6 üstü kullanıcı tercihleri karşılanmaz. Altın/gri yazının koyu arka plan kontrastı için ölçülmüş WCAG sonucu yok. Önce widget/semantics ve küçük telefon + 200% metin senaryosu ile doğrulama yapılmalı; bu faz UI'yi değiştirmedi.
