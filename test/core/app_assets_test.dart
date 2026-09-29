import 'package:astrofrekans/core/assets/app_assets.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

/// Guards the asset contract: every path referenced from Dart must actually be
/// bundled by `pubspec.yaml`. A renamed folder or a missing pubspec entry fails
/// here instead of at runtime.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  Future<void> expectBundled(String path) async {
    final ByteData data = await rootBundle.load(path);
    expect(data.lengthInBytes, greaterThan(0), reason: '$path is empty');
  }

  test('single asset constants are bundled', () async {
    for (final String path in <String>[
      AppAssets.appIcon,
      AppAssets.splashBackground,
      AppAssets.onboardingCosmicGuide,
      AppAssets.brandMark,
      AppAssets.brandLockupFull,
      AppAssets.brandLockupCompact,
      AppAssets.loginBackground,
      AppAssets.astroAiAvatar,
      AppAssets.astroAiOrb,
      AppAssets.astroAiListening,
      AppAssets.astroAiTyping,
      AppAssets.astroAiEmptyState,
      AppAssets.tarotBack,
      AppAssets.katinaBack,
      AppAssets.runeBack,
      AppAssets.runeStoneBack,
      AppAssets.natalAsc,
      AppAssets.natalDsc,
      AppAssets.natalMc,
      AppAssets.natalIc,
      AppAssets.natalRetrograde,
      AppAssets.natalZodiacWheel,
      AppAssets.natalAspectLine,
      AppAssets.natalHouseWheel,
      AppAssets.consultantPlaceholder,
      AppAssets.premiumCrown,
      AppAssets.premiumStar,
      AppAssets.premiumCrystal,
    ]) {
      await expectBundled(path);
    }
  });

  test('asset maps are complete and bundled', () async {
    expect(AppAssets.zodiac, hasLength(12));
    expect(AppAssets.planets, hasLength(12));
    expect(AppAssets.moonPhases, hasLength(8));
    expect(AppAssets.elements, hasLength(4));
    expect(AppAssets.dailyFrequency, hasLength(7));
    expect(AppAssets.emptyStates, hasLength(6));

    for (final Map<String, String> map in <Map<String, String>>[
      AppAssets.zodiac,
      AppAssets.planets,
      AppAssets.moonPhases,
      AppAssets.elements,
      AppAssets.dailyFrequency,
      AppAssets.emptyStates,
    ]) {
      for (final String path in map.values) {
        await expectBundled(path);
      }
    }
  });

  test('deck helpers resolve to bundled files', () async {
    await expectBundled(AppAssets.tarotCard('adalet'));
    await expectBundled(AppAssets.katinaCard('gunes'));
    await expectBundled(AppAssets.runeCard('algiz'));
    await expectBundled(AppAssets.runeStone('raidho'));
  });
}
