# Localization denetimi

`lib/l10n/app_tr.arb` ve `app_en.arb` karşılaştırıldı: her birinde **218** kullanıcı metni anahtarı var; EN eksik **0**, TR eksik **0**. Üretilmiş localization dosyaları mevcut. Bu fazda UI metinleri değiştirilmedi.

AZ eklemeye yapı uygundur: ARB tabanlı Flutter gen-l10n ve merkezi `AppLocales` mevcut. Ancak `lib/core/localization/locale_controller.dart`/`astro_labels.dart` ile `supportedLocales` listesi şu anda yalnız TR/EN bilir; `app_az.arb` eklemek tek başına yeterli değildir. AZ için tüm metinler, burç/gezegen adları, tarih biçimi ve backend `language` tercihi birlikte test edilmelidir.
