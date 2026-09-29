/// Canonical production asset paths for Astrofrekans.
///
/// Source PNG masters and UI reference screenshots are intentionally excluded
/// from runtime lookups. Card faces use the optimized WebP derivatives.
abstract final class AppAssets {
  static const entryLogo = 'assets/logo/1logo.png';
  static const appIcon = 'assets/branding/app_icon/app_icon.png';
  static const splashBackground =
      'assets/branding/splash/splash_background.png';
  static const onboardingCosmicGuide =
      'assets/branding/onboarding/onboarding_cosmic_guide.png';
  static const brandMark = 'assets/branding/logo/brand_mark.png';
  static const brandLockupFull = 'assets/branding/logo/brand_lockup_full.png';
  static const brandLockupCompact =
      'assets/branding/logo/brand_lockup_compact.png';
  static const loginBackground = 'assets/backgrounds/login_background.png';

  static const zodiac = <String, String>{
    'aries': 'assets/zodiac/aries/aries.png',
    'taurus': 'assets/zodiac/taurus/taurus.png',
    'gemini': 'assets/zodiac/gemini/gemini.png',
    'cancer': 'assets/zodiac/cancer/cancer.png',
    'leo': 'assets/zodiac/leo/leo.png',
    'virgo': 'assets/zodiac/virgo/virgo.png',
    'libra': 'assets/zodiac/libra/libra.png',
    'scorpio': 'assets/zodiac/scorpio/scorpio.png',
    'sagittarius': 'assets/zodiac/sagittarius/sagittarius.png',
    'capricorn': 'assets/zodiac/capricorn/capricorn.png',
    'aquarius': 'assets/zodiac/aquarius/aquarius.png',
    'pisces': 'assets/zodiac/pisces/pisces.png',
  };

  static const planets = <String, String>{
    'sun': 'assets/planets/sun/sun.png',
    'moon': 'assets/planets/moon/moon.png',
    'mercury': 'assets/planets/mercury/mercury.png',
    'venus': 'assets/planets/venus/venus.png',
    'mars': 'assets/planets/mars/mars.png',
    'jupiter': 'assets/planets/jupiter/jupiter.png',
    'saturn': 'assets/planets/saturn/saturn.png',
    'uranus': 'assets/planets/uranus/uranus.png',
    'neptune': 'assets/planets/neptune/neptune.png',
    'pluto': 'assets/planets/pluto/pluto.png',
    'north_node': 'assets/planets/north_node/north_node.png',
    'south_node': 'assets/planets/south_node/south_node.png',
  };

  static const moonPhases = <String, String>{
    'new_moon': 'assets/moon_phases/new_moon/new_moon.png',
    'waxing_crescent': 'assets/moon_phases/waxing_crescent/waxing_crescent.png',
    'first_quarter': 'assets/moon_phases/first_quarter/first_quarter.png',
    'waxing_gibbous': 'assets/moon_phases/waxing_gibbous/waxing_gibbous.png',
    'full_moon': 'assets/moon_phases/full_moon/full_moon.png',
    'waning_gibbous': 'assets/moon_phases/waning_gibbous/waning_gibbous.png',
    'last_quarter': 'assets/moon_phases/last_quarter/last_quarter.png',
    'waning_crescent': 'assets/moon_phases/waning_crescent/waning_crescent.png',
  };

  static const elements = <String, String>{
    'fire': 'assets/elements/fire/fire.png',
    'earth': 'assets/elements/earth/earth.png',
    'air': 'assets/elements/air/air.png',
    'water': 'assets/elements/water/water.png',
  };

  static const dailyFrequency = <String, String>{
    'general_energy':
        'assets/daily_frequency/general_energy/general_energy.png',
    'love': 'assets/daily_frequency/love/love.png',
    'money': 'assets/daily_frequency/money/money.png',
    'career': 'assets/daily_frequency/career/career.png',
    'health_balance':
        'assets/daily_frequency/health_balance/health_balance.png',
    'luck': 'assets/daily_frequency/luck/luck.png',
    'important_hours':
        'assets/daily_frequency/important_hours/important_hours.png',
  };

  static const astroAiAvatar = 'assets/astro_ai/avatar/astro_ai_avatar.png';
  static const astroAiOrb = 'assets/astro_ai/orb/astro_ai_orb.png';
  static const astroAiListening =
      'assets/astro_ai/listening/astro_ai_listening.png';
  static const astroAiTyping = 'assets/astro_ai/typing/astro_ai_typing.png';
  static const astroAiEmptyState =
      'assets/astro_ai/empty_state/astro_ai_empty_state.png';

  static const tarotCardsRoot = 'assets/tarot/cards';
  static const katinaCardsRoot = 'assets/katina/cards';
  static const runeCardsRoot = 'assets/rune/cards';
  static const runeStonesRoot = 'assets/rune/stones';
  static const tarotBack = 'assets/cards-back/webp/tarot_back.webp';
  static const katinaBack = 'assets/cards-back/webp/katina_back.webp';
  static const runeBack = 'assets/cards-back/webp/rune_back.webp';
  static const runeStoneBack = 'assets/cards-back/webp/runetas_back.webp';

  static String tarotCard(String fileStem) => '$tarotCardsRoot/$fileStem.webp';
  static String katinaCard(String fileStem) =>
      '$katinaCardsRoot/$fileStem.webp';
  static String runeCard(String fileStem) => '$runeCardsRoot/$fileStem.webp';
  static String runeStone(String fileStem) => '$runeStonesRoot/$fileStem.png';

  static const natalAsc = 'assets/natal_chart/asc/asc.png';
  static const natalDsc = 'assets/natal_chart/dsc/dsc.png';
  static const natalMc = 'assets/natal_chart/mc/mc.png';
  static const natalIc = 'assets/natal_chart/ic/ic.png';
  static const natalRetrograde = 'assets/natal_chart/retrograde/retrograde.png';
  static const natalZodiacWheel =
      'assets/natal_chart/zodiac_wheel/zodiac_wheel.png';
  static const natalAspectLine = 'assets/natal_chart/overlays/aspect_line.png';
  static const natalHouseWheel = 'assets/natal_chart/overlays/house_wheel.png';

  static const emptyStates = <String, String>{
    'no_data': 'assets/empty_states/no_data/no_data.png',
    'no_birth_data': 'assets/empty_states/no_birth_data/no_birth_data.png',
    'no_results': 'assets/empty_states/no_results/no_results.png',
    'offline': 'assets/empty_states/offline/offline.png',
    'premium_locked': 'assets/empty_states/premium_locked/premium_locked.png',
    'loading': 'assets/empty_states/loading/loading.png',
  };

  static const consultantPlaceholder =
      'assets/consultants/placeholders/consultant_placeholder.png';
  static const premiumCrown = 'assets/premium/crown/premium_crown.png';
  static const premiumStar = 'assets/premium/star/premium_star.png';
  static const premiumCrystal = 'assets/premium/crystal/premium_crystal.png';
}
