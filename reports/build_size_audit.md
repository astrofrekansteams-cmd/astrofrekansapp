# Build boyutu denetimi

Ölçüm: 2026-09-23, `build/unit_test_assets` içindeki Flutter asset paketi. Bu bir APK/AAB değildir. Android SDK bulunmadığı için `flutter build apk --debug` başlamadı; Dart AOT/native library, APK sıkıştırma ve cihaz kurulum boyutu **ölçülmedi**. Önceki yaklaşık 368 MiB debug APK / 287 MiB debug AAB değerleri kullanıcı tarafından aktarılan eski ölçümlerdir, bu checkout için doğrulanmadı.

| Grup | Dosya | Paket içindeki kaynak boyut |
|---|---:|---:|
| Rune kart + taş | 49 | 51,60 MiB |
| Tarot kartları | 78 | 39,00 MiB |
| Katina kartları | 65 | 24,94 MiB |
| Gezegenler | 12 | 15,37 MiB |
| Burçlar | 12 | 14,70 MiB |
| Branding | 6 | 12,14 MiB |
| Ay fazları | 8 | 9,95 MiB |
| Astro AI | 5 | 8,81 MiB |
| Günlük frekans | 7 | 8,21 MiB |
| Doğum haritası | 8 | 6,14 MiB |
| Empty states | 6 | 4,58 MiB |
| Elementler | 4 | 3,63 MiB |
| Premium | 3 | 2,13 MiB |
| Login background | 1 | 2,13 MiB |
| Danışman placeholder | 1 | 1,81 MiB |
| Kart arka yüzleri | 4 | 1,69 MiB |
| Font ve lisans dosyaları | 9 | 1,06 MiB |
| **Toplam** | **278** | **207,88 MiB** |

10 UI referans ekranı `assets_manifest.json` içinde yer alır (18,05 MiB), ancak `pubspec.yaml` ile paketlenmez. `assets/masters` ve kartların kaynak PNG'leri de pakette yoktur. Test asset bundle içindeki manifest/Flutter dosyaları ayrıca yaklaşık 1,97 MiB'dir.

## En büyük 50 paket dosyası

| # | MiB | Dosya |
|---:|---:|---|
| 1 | 4,05 | `assets/branding/splash/splash_background.png` |
| 2 | 2,72 | `assets/branding/onboarding/onboarding_cosmic_guide.png` |
| 3 | 2,13 | `assets/backgrounds/login_background.png` |
| 4 | 1,97 | `assets/astro_ai/listening/astro_ai_listening.png` |
| 5 | 1,96 | `assets/astro_ai/empty_state/astro_ai_empty_state.png` |
| 6 | 1,93 | `assets/astro_ai/typing/astro_ai_typing.png` |
| 7 | 1,93 | `assets/rune/stones/sowilo.png` |
| 8 | 1,92 | `assets/rune/stones/mannaz.png` |
| 9 | 1,91 | `assets/rune/stones/tiwaz.png` |
| 10 | 1,90 | `assets/rune/stones/ehwaz.png` |
| 11 | 1,89 | `assets/rune/stones/algiz.png` |
| 12 | 1,89 | `assets/rune/stones/isa.png` |
| 13 | 1,88 | `assets/rune/stones/berkano.png` |
| 14 | 1,87 | `assets/rune/stones/jera.png` |
| 15 | 1,87 | `assets/rune/stones/hagalaz.png` |
| 16 | 1,86 | `assets/rune/stones/fehu.png` |
| 17 | 1,85 | `assets/rune/stones/eihwaz.png` |
| 18 | 1,85 | `assets/branding/app_icon/app_icon.png` |
| 19 | 1,85 | `assets/rune/stones/raidho.png` |
| 20 | 1,83 | `assets/rune/stones/wunjo.png` |
| 21 | 1,82 | `assets/rune/stones/ansuz.png` |
| 22 | 1,82 | `assets/rune/stones/laguz.png` |
| 23 | 1,82 | `assets/rune/stones/ingwaz.png` |
| 24 | 1,81 | `assets/consultants/placeholders/consultant_placeholder.png` |
| 25 | 1,81 | `assets/rune/stones/uruz.png` |
| 26 | 1,81 | `assets/astro_ai/avatar/astro_ai_avatar.png` |
| 27 | 1,80 | `assets/rune/stones/perthro.png` |
| 28 | 1,79 | `assets/rune/stones/thurisaz.png` |
| 29 | 1,74 | `assets/rune/stones/othala.png` |
| 30 | 1,73 | `assets/rune/stones/dagaz.png` |
| 31 | 1,72 | `assets/branding/logo/brand_lockup_full.png` |
| 32 | 1,71 | `assets/rune/stones/gebo.png` |
| 33 | 1,70 | `assets/rune/stones/nauthiz.png` |
| 34 | 1,69 | `assets/rune/stones/kenaz.png` |
| 35 | 1,48 | `assets/moon_phases/full_moon/full_moon.png` |
| 36 | 1,43 | `assets/planets/mercury/mercury.png` |
| 37 | 1,39 | `assets/moon_phases/waning_gibbous/waning_gibbous.png` |
| 38 | 1,36 | `assets/planets/north_node/north_node.png` |
| 39 | 1,35 | `assets/planets/south_node/south_node.png` |
| 40 | 1,35 | `assets/planets/sun/sun.png` |
| 41 | 1,34 | `assets/daily_frequency/money/money.png` |
| 42 | 1,33 | `assets/moon_phases/last_quarter/last_quarter.png` |
| 43 | 1,32 | `assets/planets/saturn/saturn.png` |
| 44 | 1,32 | `assets/daily_frequency/career/career.png` |
| 45 | 1,32 | `assets/planets/neptune/neptune.png` |
| 46 | 1,29 | `assets/daily_frequency/luck/luck.png` |
| 47 | 1,28 | `assets/planets/uranus/uranus.png` |
| 48 | 1,28 | `assets/planets/venus/venus.png` |
| 49 | 1,27 | `assets/moon_phases/waxing_gibbous/waxing_gibbous.png` |
| 50 | 1,27 | `assets/planets/moon/moon.png` |

## Release asset stratejisi

| Seviye | İçerik | Karar gerekçesi |
|---|---|---|
| Tier A: ilk açılış | Splash, logo, onboarding, login/home background, temel gezinme ikonları, bir küçük Astro AI avatarı | İlk ekran için gerçekten gerekli; ağ bağımlılığı olmasın. |
| Tier B: feature açılınca | Burç/gezegen/ay görselleri, Astro AI durumları, rune taşları | Özelliğe giren kullanıcıya gecikmeli yüklenebilir; Flutter asset bundle'da kalırsa yine base binary boyutuna girer. |
| Tier C: isteğe bağlı uzaktan | Tarot 78 kart (39,00 MiB), Katina 65 kart (24,94 MiB), rune kartları (7,73 MiB), gerekirse rune taşları (~43,87 MiB) | Kullanıcı ilgili desteyi hiç açmayabilir; sürüm, checksum, cache, offline ve lisans politikasından sonra CDN seçeneği değerlendirilsin. |

Bu fazda remote asset sistemi, yeniden üretim veya agresif resize yapılmadı. Güvenli sonraki adım: gerçek release APK/AAB build alıp split-per-ABI/asset analizi yapmak; ardından asset tier kararını ürün/offline gereksinimiyle vermek.
