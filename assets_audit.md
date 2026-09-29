# Astrofrekans Assets Audit

Generated from the current `assets/` tree. Visual judgments were checked against category contact sheets; file facts are read from the source images.

## Executive summary

- Source images: **260** files, **655.2 MB** total.
- File results: **136 OK**, **100 RENAME**, **24 WRONG_SIZE**, **0 DUPLICATE**.
- Required additions explicitly identified: **20 MISSING** assets.
- Exact byte-for-byte duplicates: **none detected**.
- Every current PNG is encoded without an alpha channel. This is acceptable for full-bleed cards/screens, but reusable emblems, chart overlays, icons, logos, and rune stones need transparent derivatives or controlled background removal before production use.
- Strongest existing visual language: deep navy/near-black, champagne-gold filigree, restrained celestial glow, centered premium compositions. New generation must match this set rather than introducing a new visual language.

## Blocking cleanup before application coding

1. Rename misspelled folders: `tarrot` -> `tarot`, `backgraunds` -> `backgrounds`, `tas-rune` -> `rune/stones`, `app-thema` -> `references/ui_screens`, `dogumharitasi` -> `natal_chart`.
2. Resolve known filename defects: `puluto` -> `pluto`, `saturun` -> `saturn`, `lngwaz` -> `ingwaz`, `aspect-line` -> `aspect_line`, plus UUID-based UI/category names.
3. Normalize the 24 rune-stone canvases; the current set mixes 1024x1536, 1086x1448, and 1122x1402.
4. Produce or derive the missing Astro AI, empty-state, premium, consultant-placeholder, DSC, and IC assets.
5. Create transparent derivatives for reusable symbol/icon categories while preserving original masters and their exact visual style.

## Approved style anchors for future generation

| Use | Primary reference | Why |
|---|---|---|
| Overall UI | `assets/app-thema/c4dc11cc-d22c-490c-96a5-6acf1e1e4021.png` | Best consolidated dashboard palette, spacing, glow, cards, and icon treatment. |
| Astro AI | `assets/app-thema/d6b71bc7-7950-44d1-834d-3871f8e16420.png` | Defines the non-robotic cosmic guide, gold-lit navy body, and AI surface language. |
| Entry/onboarding | `assets/app-thema/login_register.png` | Strong full-screen cosmic atmosphere and premium brand hierarchy. |
| Zodiac/icon rendering | `assets/burc/aslan.png` | Clean gold relief, deep-blue enamel, centered scale, controlled ornament. |
| Planet symbols | `assets/gezegen/saturun.png` | Strong material, line weight, ring detail, and circular frame. |
| Moon phases | `assets/ay-fazlari/dolunay.png` | Realistic moon texture integrated with the gold celestial frame. |
| Element icons | `assets/element/su.png` | Balanced ornamental illustration with readable elemental symbolism. |
| Tarot | `assets/tarrot/yildiz.png` | Representative polished tarot frame, palette, and illustration density. |
| Katina | `assets/katina/gunes.png` | Representative Katina frame and luminous focal treatment. |
| Rune cards | `assets/rune/sowilo.png` | Representative rune glow, frame, and narrative background. |
| Rune stones | `assets/tas-rune/algiz.png` | Strongest readable stone silhouette and engraved gold treatment. |
| Branding | `assets/logo/banner.png` | Canonical celestial landscape, logo gold, and brand mood. |

These anchors are mandatory inputs for ImageGen prompts. New assets must keep the same navy/gold palette, material response, glow restraint, centered object scale, and ornate-but-premium detail level. No cyberpunk neon, game UI, robotic AI, text, watermark, or unrelated fantasy styling.

## Missing assets

| CATEGORY | FILE | SIZE | FORMAT | TRANSPARENT | PURPOSE | STATUS | ACTION |
|---|---|---:|---|---|---|---|---|
| branding | `branding/app_icon/app_icon.png` | TBD | PNG/WebP | YES where reusable | App icon master | MISSING | Generate or derive only after applying the approved style anchors. |
| branding | `branding/splash/splash_background.png` | TBD | PNG/WebP | YES where reusable | Splash background | MISSING | Generate or derive only after applying the approved style anchors. |
| branding | `branding/onboarding/onboarding_cosmic_guide.png` | TBD | PNG/WebP | YES where reusable | Onboarding hero | MISSING | Generate or derive only after applying the approved style anchors. |
| astro_ai | `astro_ai/avatar/astro_ai_avatar.png` | TBD | PNG/WebP | YES where reusable | AI guide avatar | MISSING | Generate or derive only after applying the approved style anchors. |
| astro_ai | `astro_ai/orb/astro_ai_orb.png` | TBD | PNG/WebP | YES where reusable | Idle orb | MISSING | Generate or derive only after applying the approved style anchors. |
| astro_ai | `astro_ai/listening/astro_ai_listening.png` | TBD | PNG/WebP | YES where reusable | Listening state | MISSING | Generate or derive only after applying the approved style anchors. |
| astro_ai | `astro_ai/typing/astro_ai_typing.png` | TBD | PNG/WebP | YES where reusable | Typing state | MISSING | Generate or derive only after applying the approved style anchors. |
| astro_ai | `astro_ai/empty_state/astro_ai_empty_state.png` | TBD | PNG/WebP | YES where reusable | Empty state | MISSING | Generate or derive only after applying the approved style anchors. |
| natal_chart | `natal_chart/dsc/dsc.png` | TBD | PNG/WebP | YES where reusable | DSC marker | MISSING | Generate or derive only after applying the approved style anchors. |
| natal_chart | `natal_chart/ic/ic.png` | TBD | PNG/WebP | YES where reusable | IC marker | MISSING | Generate or derive only after applying the approved style anchors. |
| empty_states | `empty_states/no_data/no_data.png` | TBD | PNG/WebP | YES where reusable | No-data state | MISSING | Generate or derive only after applying the approved style anchors. |
| empty_states | `empty_states/offline/offline.png` | TBD | PNG/WebP | YES where reusable | Offline state | MISSING | Generate or derive only after applying the approved style anchors. |
| empty_states | `empty_states/no_birth_data/no_birth_data.png` | TBD | PNG/WebP | YES where reusable | Missing birth data | MISSING | Generate or derive only after applying the approved style anchors. |
| empty_states | `empty_states/no_results/no_results.png` | TBD | PNG/WebP | YES where reusable | No-results state | MISSING | Generate or derive only after applying the approved style anchors. |
| empty_states | `empty_states/premium_locked/premium_locked.png` | TBD | PNG/WebP | YES where reusable | Premium lock state | MISSING | Generate or derive only after applying the approved style anchors. |
| empty_states | `empty_states/loading/loading.png` | TBD | PNG/WebP | YES where reusable | Loading state | MISSING | Generate or derive only after applying the approved style anchors. |
| consultants | `consultants/placeholders/consultant_placeholder.png` | TBD | PNG/WebP | YES where reusable | Consultant fallback avatar | MISSING | Generate or derive only after applying the approved style anchors. |
| premium | `premium/crown/premium_crown.png` | TBD | PNG/WebP | YES where reusable | Premium crown | MISSING | Generate or derive only after applying the approved style anchors. |
| premium | `premium/star/premium_star.png` | TBD | PNG/WebP | YES where reusable | Premium star | MISSING | Generate or derive only after applying the approved style anchors. |
| premium | `premium/crystal/premium_crystal.png` | TBD | PNG/WebP | YES where reusable | Premium crystal | MISSING | Generate or derive only after applying the approved style anchors. |

## Current file inventory

| CATEGORY | FILE | SIZE | ASPECT | FORMAT | TRANSPARENT | PURPOSE | STATUS | ACTION |
|---|---|---:|---:|---|---|---|---|---|
| app-thema | `app-thema/04bdc8c6-3497-4bcd-9f8b-f5e5a877ac56.png` | 941x1672 | 0.563 | PNG | NO | UI screen reference | RENAME | Rename to the represented screen; retain as a UI style reference only. |
| app-thema | `app-thema/07cc11d7-18f7-4203-988e-8f99c81c4849.png` | 941x1672 | 0.563 | PNG | NO | UI screen reference | RENAME | Rename to the represented screen; retain as a UI style reference only. |
| app-thema | `app-thema/16e6a90e-b355-4ef5-ab8e-3dc2dbdb8fbf.png` | 941x1672 | 0.563 | PNG | NO | UI screen reference | RENAME | Rename to the represented screen; retain as a UI style reference only. |
| app-thema | `app-thema/755e9d0f-3c5f-45b0-b952-a1599cdb620a.png` | 941x1672 | 0.563 | PNG | NO | UI screen reference | RENAME | Rename to the represented screen; retain as a UI style reference only. |
| app-thema | `app-thema/81da2f94-6e26-47fa-b96e-5eeedd5de16a.png` | 941x1672 | 0.563 | PNG | NO | UI screen reference | RENAME | Rename to the represented screen; retain as a UI style reference only. |
| app-thema | `app-thema/9bf23e5d-713e-4f06-8b0c-52e64225856e.png` | 941x1672 | 0.563 | PNG | NO | UI screen reference | RENAME | Rename to the represented screen; retain as a UI style reference only. |
| app-thema | `app-thema/c4dc11cc-d22c-490c-96a5-6acf1e1e4021.png` | 941x1672 | 0.563 | PNG | NO | UI screen reference | RENAME | Rename to the represented screen; retain as a UI style reference only. |
| app-thema | `app-thema/d6b71bc7-7950-44d1-834d-3871f8e16420.png` | 941x1672 | 0.563 | PNG | NO | UI screen reference | RENAME | Rename to the represented screen; retain as a UI style reference only. |
| app-thema | `app-thema/e57798f5-1714-438e-a611-9b7643db35cc.png` | 941x1672 | 0.563 | PNG | NO | UI screen reference | RENAME | Rename to the represented screen; retain as a UI style reference only. |
| app-thema | `app-thema/login_register.png` | 941x1672 | 0.563 | PNG | NO | UI screen reference | OK | Keep; use as an in-category style reference. |
| ay-fazlari | `ay-fazlari/buyuyen_hilal.png` | 1254x1254 | 1 | PNG | NO | Moon phase illustration | OK | Keep; use as an in-category style reference. |
| ay-fazlari | `ay-fazlari/buyuyen_siskin_ay.png` | 1254x1254 | 1 | PNG | NO | Moon phase illustration | OK | Keep; use as an in-category style reference. |
| ay-fazlari | `ay-fazlari/dolunay.png` | 1254x1254 | 1 | PNG | NO | Moon phase illustration | OK | Keep; use as an in-category style reference. |
| ay-fazlari | `ay-fazlari/ilk_dordun.png` | 1254x1254 | 1 | PNG | NO | Moon phase illustration | OK | Keep; use as an in-category style reference. |
| ay-fazlari | `ay-fazlari/kuculen_hilal.png` | 1254x1254 | 1 | PNG | NO | Moon phase illustration | OK | Keep; use as an in-category style reference. |
| ay-fazlari | `ay-fazlari/kuculen_siskin_ay.png` | 1254x1254 | 1 | PNG | NO | Moon phase illustration | OK | Keep; use as an in-category style reference. |
| ay-fazlari | `ay-fazlari/son_dordun.png` | 1254x1254 | 1 | PNG | NO | Moon phase illustration | OK | Keep; use as an in-category style reference. |
| ay-fazlari | `ay-fazlari/yeni_ay.png` | 1254x1254 | 1 | PNG | NO | Moon phase illustration | OK | Keep; use as an in-category style reference. |
| backgraunds | `backgraunds/login_backgraud.png` | 941x1672 | 0.563 | PNG | NO | Screen background | RENAME | Rename folder to backgrounds and file to login_background.png. |
| burc | `burc/akrep.png` | 1254x1254 | 1 | PNG | NO | Zodiac illustration | OK | Keep; use as an in-category style reference. |
| burc | `burc/aslan.png` | 1254x1254 | 1 | PNG | NO | Zodiac illustration | OK | Keep; use as an in-category style reference. |
| burc | `burc/balik.png` | 1254x1254 | 1 | PNG | NO | Zodiac illustration | OK | Keep; use as an in-category style reference. |
| burc | `burc/basak.png` | 1254x1254 | 1 | PNG | NO | Zodiac illustration | OK | Keep; use as an in-category style reference. |
| burc | `burc/boga.png` | 1254x1254 | 1 | PNG | NO | Zodiac illustration | OK | Keep; use as an in-category style reference. |
| burc | `burc/ikizler.png` | 1254x1254 | 1 | PNG | NO | Zodiac illustration | OK | Keep; use as an in-category style reference. |
| burc | `burc/koc.png` | 1254x1254 | 1 | PNG | NO | Zodiac illustration | OK | Keep; use as an in-category style reference. |
| burc | `burc/kova.png` | 1254x1254 | 1 | PNG | NO | Zodiac illustration | OK | Keep; use as an in-category style reference. |
| burc | `burc/oglak.png` | 1254x1254 | 1 | PNG | NO | Zodiac illustration | OK | Keep; use as an in-category style reference. |
| burc | `burc/terazi.png` | 1254x1254 | 1 | PNG | NO | Zodiac illustration | OK | Keep; use as an in-category style reference. |
| burc | `burc/yay.png` | 1254x1254 | 1 | PNG | NO | Zodiac illustration | OK | Keep; use as an in-category style reference. |
| burc | `burc/yengec.png` | 1254x1254 | 1 | PNG | NO | Zodiac illustration | OK | Keep; use as an in-category style reference. |
| cards-back | `cards-back/katina_back.png` | 1024x1536 | 0.667 | PNG | NO | Card/deck reverse | OK | Keep; use as an in-category style reference. |
| cards-back | `cards-back/rune_back.png` | 1024x1536 | 0.667 | PNG | NO | Card/deck reverse | OK | Keep; use as an in-category style reference. |
| cards-back | `cards-back/runetas_back.png` | 1024x1536 | 0.667 | PNG | NO | Card/deck reverse | OK | Keep; use as an in-category style reference. |
| cards-back | `cards-back/tarot_back.png` | 1024x1536 | 0.667 | PNG | NO | Card/deck reverse | OK | Keep; use as an in-category style reference. |
| dogumharitasi | `dogumharitasi/asc.png` | 1254x1254 | 1 | PNG | NO | Natal chart overlay/symbol | OK | Keep; use as an in-category style reference. |
| dogumharitasi | `dogumharitasi/aspect-line.png` | 1254x1254 | 1 | PNG | NO | Natal chart overlay/symbol | RENAME | Rename to aspect_line.png. |
| dogumharitasi | `dogumharitasi/ev_cemberi.png` | 1254x1254 | 1 | PNG | NO | Natal chart overlay/symbol | OK | Keep; use as an in-category style reference. |
| dogumharitasi | `dogumharitasi/mc.png` | 1254x1254 | 1 | PNG | NO | Natal chart overlay/symbol | OK | Keep; use as an in-category style reference. |
| dogumharitasi | `dogumharitasi/retrograde.png` | 1254x1254 | 1 | PNG | NO | Natal chart overlay/symbol | OK | Keep; use as an in-category style reference. |
| dogumharitasi | `dogumharitasi/zodiac_wheel.png` | 1254x1254 | 1 | PNG | NO | Natal chart overlay/symbol | OK | Keep; use as an in-category style reference. |
| element | `element/ates.png` | 1254x1254 | 1 | PNG | NO | Element illustration | OK | Keep; use as an in-category style reference. |
| element | `element/hava.png` | 1254x1254 | 1 | PNG | NO | Element illustration | OK | Keep; use as an in-category style reference. |
| element | `element/su.png` | 1254x1254 | 1 | PNG | NO | Element illustration | OK | Keep; use as an in-category style reference. |
| element | `element/toprak.png` | 1254x1254 | 1 | PNG | NO | Element illustration | OK | Keep; use as an in-category style reference. |
| gezegen | `gezegen/ay.png` | 1254x1254 | 1 | PNG | NO | Planet/node symbol | OK | Keep; use as an in-category style reference. |
| gezegen | `gezegen/gunes.png` | 1254x1254 | 1 | PNG | NO | Planet/node symbol | OK | Keep; use as an in-category style reference. |
| gezegen | `gezegen/guney_ay_dugumu.png` | 1254x1254 | 1 | PNG | NO | Planet/node symbol | OK | Keep; use as an in-category style reference. |
| gezegen | `gezegen/jupiter.png` | 1254x1254 | 1 | PNG | NO | Planet/node symbol | OK | Keep; use as an in-category style reference. |
| gezegen | `gezegen/kuzey_ay_dugumu.png` | 1254x1254 | 1 | PNG | NO | Planet/node symbol | OK | Keep; use as an in-category style reference. |
| gezegen | `gezegen/mars.png` | 1254x1254 | 1 | PNG | NO | Planet/node symbol | OK | Keep; use as an in-category style reference. |
| gezegen | `gezegen/merkur.png` | 1254x1254 | 1 | PNG | NO | Planet/node symbol | OK | Keep; use as an in-category style reference. |
| gezegen | `gezegen/neptun.png` | 1254x1254 | 1 | PNG | NO | Planet/node symbol | OK | Keep; use as an in-category style reference. |
| gezegen | `gezegen/puluto.png` | 1254x1254 | 1 | PNG | NO | Planet/node symbol | RENAME | Rename to pluto.png. |
| gezegen | `gezegen/saturun.png` | 1254x1254 | 1 | PNG | NO | Planet/node symbol | RENAME | Rename to saturn.png. |
| gezegen | `gezegen/uranus.png` | 1254x1254 | 1 | PNG | NO | Planet/node symbol | OK | Keep; use as an in-category style reference. |
| gezegen | `gezegen/venus.png` | 1254x1254 | 1 | PNG | NO | Planet/node symbol | OK | Keep; use as an in-category style reference. |
| kategori | `kategori/116b61bb-4123-45d2-b6b8-66467896db0f.png` | 1254x1254 | 1 | PNG | NO | Daily frequency category icon | RENAME | Map the icon to its semantic purpose, then rename with lowercase_snake_case. |
| kategori | `kategori/3e34eb61-b400-46f6-a41c-0425808dfe66.png` | 1254x1254 | 1 | PNG | NO | Daily frequency category icon | RENAME | Map the icon to its semantic purpose, then rename with lowercase_snake_case. |
| kategori | `kategori/46e809ba-d6cc-45f5-a830-c10f7a5902eb.png` | 1254x1254 | 1 | PNG | NO | Daily frequency category icon | RENAME | Map the icon to its semantic purpose, then rename with lowercase_snake_case. |
| kategori | `kategori/93ee8630-2111-4ba8-8a6f-a725d013a633.png` | 1254x1254 | 1 | PNG | NO | Daily frequency category icon | RENAME | Map the icon to its semantic purpose, then rename with lowercase_snake_case. |
| kategori | `kategori/f06eaffc-0a89-4fad-b0ba-bffa643fa17c.png` | 1254x1254 | 1 | PNG | NO | Daily frequency category icon | RENAME | Map the icon to its semantic purpose, then rename with lowercase_snake_case. |
| kategori | `kategori/f171b089-7f1f-4b2f-95d4-c535a1555a72.png` | 1254x1254 | 1 | PNG | NO | Daily frequency category icon | RENAME | Map the icon to its semantic purpose, then rename with lowercase_snake_case. |
| kategori | `kategori/f6e8d555-a5c3-4bb9-b74b-3a6c1568333e.png` | 1254x1254 | 1 | PNG | NO | Daily frequency category icon | RENAME | Map the icon to its semantic purpose, then rename with lowercase_snake_case. |
| katina | `katina/adhamdeva.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/afyon.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/agac.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/albanoz.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/alyans.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/anahtar.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/aral.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/ariman.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/assyranta.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/attart.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/ay.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/bahceler.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/balik.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/baykus.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/bedes.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/bulutlar.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/cilekler.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/dag.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/dare.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/dastar.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/dervis.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/deste.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/deve.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/elmas.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/eprahhat.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/ev.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/fareler.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/gamhat.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/gunes.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/hac.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/hesse.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/isfahan.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/kale.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/kalif.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/kalp.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/kapi.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/kitap.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/kiz_cocugu.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/kopek.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/mektup.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/mezar.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/mida.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/munzur.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/nil_nehri.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/parsadra.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/saah.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/samyeli.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/selana.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/selcuksassa.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/sunit.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/supurge.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/tagral.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/tattaret.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/tilki.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/turan.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/urmia.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/valide.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/yakut.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/yatagan.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/yelkenli.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/yilan.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/yildizlar.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/yol.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/zara.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| katina | `katina/zumrut.png` | 1024x1536 | 0.667 | PNG | NO | Katina card face | OK | Keep; use as an in-category style reference. |
| logo | `logo/1logo.png` | 1122x1402 | 0.8 | PNG | NO | Branding | RENAME | Rename by role, for example brand_lockup_full and brand_lockup_compact. |
| logo | `logo/2logo.png` | 1448x1086 | 1.333 | PNG | NO | Branding | RENAME | Rename by role, for example brand_lockup_full and brand_lockup_compact. |
| logo | `logo/banner.png` | 1672x941 | 1.777 | PNG | NO | Branding | OK | Keep; use as an in-category style reference. |
| logo | `logo/logo.png` | 1254x1254 | 1 | PNG | NO | Branding | OK | Keep; use as an in-category style reference. |
| rune | `rune/algiz.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/ansuz.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/berkano.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/dagaz.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/ehwaz.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/eihwaz.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/fehu.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/gebo.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/hagalaz.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/ingwaz.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/isa.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/jera.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/kenaz.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/laguz.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/mannaz.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/nauthiz.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/odin_runesi.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/othala.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/perthro.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/raidho.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/sowilo.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/thurisaz.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/tiwaz.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/uruz.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| rune | `rune/wunjo.png` | 1024x1536 | 0.667 | PNG | NO | Rune card face | OK | Keep; use as an in-category style reference. |
| tarrot | `tarrot/adalet.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/asiklar.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/asilan_adam.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/ay.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/aziz.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/basrahibe.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/buyucu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/degnek_altilisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/degnek_asi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/degnek_beslisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/degnek_dokuzlusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/degnek_dortlusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/degnek_ikilisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/degnek_krali.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/degnek_kralicesi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/degnek_onlusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/degnek_prensi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/degnek_sekizlisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/degnek_sovalyesi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/degnek_uclusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/degnek_yedilisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/deli.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/denge.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/dunya.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/ermis.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/guc.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/gunes.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/imparator.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/imparatorice.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kader_carki.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kilic_altilisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kilic_asi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kilic_beslisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kilic_dokuzlusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kilic_dortlusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kilic_ikilisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kilic_krali.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kilic_kralicesi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kilic_onlusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kilic_prensi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kilic_sekizlisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kilic_sovalyesi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kilic_uclusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kilic_yedilisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kule.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kupa_altilisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kupa_asi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kupa_beslisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kupa_dokuzlusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kupa_dortlusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kupa_ikilisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kupa_krali.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kupa_kralicesi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kupa_onlusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kupa_prensi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kupa_sekizlisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kupa_sovalyesi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kupa_uclusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/kupa_yedilisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/mahkeme.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/olum.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/savas_arabasi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/seytan.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/tilsim_altilisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/tilsim_asi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/tilsim_beslisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/tilsim_dokuzlusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/tilsim_dortlusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/tilsim_ikilisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/tilsim_krali.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/tilsim_kralicesi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/tilsim_onlusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/tilsim_prensi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/tilsim_sekizlisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/tilsim_sovalyesi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/tilsim_uclusu.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/tilsim_yedilisi.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tarrot | `tarrot/yildiz.png` | 1024x1536 | 0.667 | PNG | NO | Tarot card face | RENAME | Keep the image; rename the folder from tarrot to tarot during reorganization. |
| tas-rune | `tas-rune/algiz.png` | 1122x1402 | 0.8 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/ansuz.png` | 1086x1448 | 0.75 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/berkano.png` | 1122x1402 | 0.8 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/dagaz.png` | 1024x1536 | 0.667 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/ehwaz.png` | 1122x1402 | 0.8 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/eihwaz.png` | 1122x1402 | 0.8 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/fehu.png` | 1086x1448 | 0.75 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/gebo.png` | 1086x1448 | 0.75 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/hagalaz.png` | 1086x1448 | 0.75 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/isa.png` | 1122x1402 | 0.8 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/jera.png` | 1122x1402 | 0.8 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/kenaz.png` | 1086x1448 | 0.75 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/laguz.png` | 1024x1536 | 0.667 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/lngwaz.png` | 1024x1536 | 0.667 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/mannaz.png` | 1122x1402 | 0.8 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/nauthiz.png` | 1086x1448 | 0.75 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/othala.png` | 1024x1536 | 0.667 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/perthro.png` | 1122x1402 | 0.8 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/raidho.png` | 1086x1448 | 0.75 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/sowilo.png` | 1122x1402 | 0.8 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/thurisaz.png` | 1122x1402 | 0.8 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/tiwaz.png` | 1122x1402 | 0.8 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/uruz.png` | 1086x1448 | 0.75 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |
| tas-rune | `tas-rune/wunjo.png` | 1086x1448 | 0.75 | PNG | NO | Rune stone illustration | WRONG_SIZE | Normalize the full set to one canvas, crop, object scale, and transparent-background policy. |

## Notes on scope

- Full-screen backgrounds can often be built as gradients, particles, and subtle overlays in Flutter; do not generate a separate raster background for every screen unless it materially improves the design.
- Card faces and UI screenshots are intentionally opaque and do not require alpha.
- The original image masters should remain untouched until the rename/reorganization mapping is applied atomically and verified against the application asset manifest.
