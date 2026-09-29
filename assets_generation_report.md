# Astrofrekans Missing Asset Generation Report

## Method

- Generator: built-in OpenAI ImageGen.
- Scope: only the 20 files marked `MISSING` in the approved audit.
- Existing artwork was not regenerated.
- Style anchors were taken from the strongest existing Astrofrekans assets: `references/ui_screens/home.png`, `references/ui_screens/astro_ai.png`, `burc/aslan.png`, `gezegen/saturn.png`, `ay-fazlari/dolunay.png`, `element/su.png`, `tarot/yildiz.png`, `katina/gunes.png`, `rune/sowilo.png`, `rune/stones/source_opaque/algiz.png`, and the existing logo/banner family.
- Shared art direction: deep navy and near-black, champagne gold, restrained glow, premium celestial ornament, centered mobile composition; no neon cyberpunk, game UI, robot styling, sci-fi HUD, text, or watermark.

## Final prompt set

### Branding

Create a premium Astrofrekans mobile-brand asset using the supplied visual anchors. Preserve the established deep-navy, near-black, and champagne-gold celestial language with restrained glow and precise ornamental linework. For the app icon, use a readable golden crescent, compass star, and subtle zodiac-orbit hint on an opaque square background, with no text. For the splash background, create a clean vertical 9:16 cosmic field with quiet central negative space and no UI. For the onboarding hero, create a transparent, centered cosmic guide illustration belonging to the same visual universe, without text or watermark.

### Astro AI character set

Create one identity-consistent premium feminine cosmic guide, human and celestial rather than robotic, with deep-navy galaxy textures, champagne-gold light, crescent and orbital details. Deliver avatar, listening, typing, and pre-chat open-hand/orb states plus one standalone floating orb. Keep the character recognizable across every state, centered, readable at mobile size, transparent, and free of text, watermark, HUD, cyberpunk, or game styling.

### Natal markers

Create `DSC` and `IC` markers that match the existing `ASC` and `MC` assets in gold material, frame geometry, line weight, scale, centering, and restrained glow. Transparent background, no additional text beyond the required three/two-letter marker.

### Empty states

Create a coherent set of compact premium celestial spot illustrations for no data, offline, missing birth data, no results, premium locked, and loading. Use simple centered forms, consistent optical scale, transparent background, and the existing navy-and-gold language. No captions, interface chrome, watermark, or excessive fantasy detail.

### Consultant and premium set

Create a neutral premium cosmic consultant avatar suitable for a circular crop, avoiding a fake photoreal specialist. Create a matching minimal celestial crown, eight-point compass star, and restrained navy-and-gold cosmic crystal as one coherent premium icon family. Transparent background, centered scale, no text or watermark.

## Produced files

- `assets/branding/app_icon/app_icon.png`
- `assets/branding/splash/splash_background.png`
- `assets/branding/onboarding/onboarding_cosmic_guide.png`
- `assets/astro_ai/avatar/astro_ai_avatar.png`
- `assets/astro_ai/orb/astro_ai_orb.png`
- `assets/astro_ai/listening/astro_ai_listening.png`
- `assets/astro_ai/typing/astro_ai_typing.png`
- `assets/astro_ai/empty_state/astro_ai_empty_state.png`
- `assets/natal_chart/dsc/dsc.png`
- `assets/natal_chart/ic/ic.png`
- `assets/empty_states/no_data/no_data.png`
- `assets/empty_states/offline/offline.png`
- `assets/empty_states/no_birth_data/no_birth_data.png`
- `assets/empty_states/no_results/no_results.png`
- `assets/empty_states/premium_locked/premium_locked.png`
- `assets/empty_states/loading/loading.png`
- `assets/consultants/placeholders/consultant_placeholder.png`
- `assets/premium/crown/premium_crown.png`
- `assets/premium/star/premium_star.png`
- `assets/premium/crystal/premium_crystal.png`

Raw generated outputs are preserved under `assets/masters/generated_missing_raw/`; production files were only resized or fitted deterministically to their required canvases.
