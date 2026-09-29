import 'package:astrofrekans/core/astrology/data/production_models.dart';
import 'package:astrofrekans/core/astrology/domain/moon_phase.dart';
import 'package:astrofrekans/core/astrology/domain/planet.dart';
import 'package:astrofrekans/core/astrology/domain/zodiac_sign.dart';
import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/core/storage/app_preferences.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/features/billing/application/entitlement_service.dart';
import 'package:astrofrekans/features/guides/application/guides_providers.dart';
import 'package:astrofrekans/features/guides/data/guides_repository.dart';
import 'package:astrofrekans/features/guides/domain/guide_models.dart';
import 'package:astrofrekans/features/guides/presentation/moon_guide_screen.dart';
import 'package:astrofrekans/features/guides/presentation/stone_guide_screen.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';

Json moonGuideJson() => {
  'moment': '2026-09-26T17:00:00Z',
  'sign': 'aries',
  'degree': 3.4,
  'phase': 'full_moon',
  'illumination': 0.999,
  'age_days': 14.8,
  'next_phase': 'waning_gibbous',
  'next_phase_at': '2026-09-28T10:00:00Z',
  'next_sign': 'taurus',
  'next_sign_at': '2026-09-28T14:40:02Z',
  'natal_house': 7,
  'sky_aspects': [
    {
      'body': 'sun',
      'aspect': 'opposition',
      'orb': 0.2,
      'applying': false,
      'nature': 'challenging',
      'to_natal': false,
    },
  ],
  'natal_aspects': [
    {
      'body': 'north_node',
      'aspect': 'trine',
      'orb': 1.1,
      'applying': true,
      'nature': 'harmonious',
      'to_natal': true,
    },
  ],
  'good_for': ['Sonuçları görmek, kutlamak ve paylaşmak'],
  'careful_with': ['Duygusal tepkileri büyütmek'],
  'summary': 'Dolunay, Ay Koç burcunda ve 7. evinde.',
  'version': 'moon_guide_v1',
};

Json stonesJson() => {
  'mode': 'today',
  'intent': 'love',
  'moment': '2026-09-26T12:00:00Z',
  'element_balance': {'fire': 1, 'earth': 6, 'air': 0, 'water': 3},
  'weakest_elements': ['air'],
  'suggestions': [
    {
      'stone': {
        'key': 'malachite',
        'name': 'Malakit',
        'color': '#0B8457',
        'elements': ['earth', 'water'],
        'planets': ['venus', 'saturn'],
        'signs': ['taurus', 'capricorn'],
        'intents': ['protection', 'love', 'career'],
        'note': 'Değişim ve korunma temasıyla ilişkilendirilir.',
      },
      'score': 64,
      'reasons': [
        {
          'kind': 'intent',
          'weight': 40,
          'text': 'Aşk niyetinle ilişkilendirilir.',
        },
        {
          'kind': 'transit',
          'weight': 10,
          'text': 'Transit Merkür natal Satürn ile kare.',
        },
      ],
    },
  ],
  'disclaimer': 'Taş önerileri tıbbi tavsiye değildir.',
  'version': 'stones_v1',
};

class _FakeGuides extends GuidesRepository {
  _FakeGuides() : super(ApiClient(Dio()));
  int moonCalls = 0;

  @override
  Future<MoonGuide> moonGuide({
    DateTime? moment,
    required String locale,
  }) async {
    moonCalls++;
    return MoonGuide.fromJson(moonGuideJson());
  }

  @override
  Future<StoneRecommendation> stones({
    required StoneMode mode,
    StoneIntent? intent,
    required String locale,
  }) async => StoneRecommendation.fromJson(stonesJson());
}

Widget _app(Widget child, _FakeGuides repo, TestEnv env) => ProviderScope(
  overrides: [
    appPreferencesProvider.overrideWithValue(env.preferences),
    secureStoreProvider.overrideWithValue(env.store),
    guidesRepositoryProvider.overrideWithValue(repo),
    entitlementServiceProvider.overrideWithValue(
      const EntitlementService(catalogue: null, premium: false),
    ),
  ],
  child: MaterialApp(
    theme: AppTheme.dark,
    locale: const Locale('tr'),
    supportedLocales: AppLocalizations.supportedLocales,
    localizationsDelegates: const [
      AppLocalizations.delegate,
      GlobalMaterialLocalizations.delegate,
      GlobalWidgetsLocalizations.delegate,
      GlobalCupertinoLocalizations.delegate,
    ],
    home: child,
  ),
);

void main() {
  group('guide models', () {
    test('moon guide parses every field', () {
      final guide = MoonGuide.fromJson(moonGuideJson());
      expect(guide.sign, ZodiacSign.aries);
      expect(guide.phase, MoonPhaseType.fullMoon);
      expect(guide.nextSign, ZodiacSign.taurus);
      expect(guide.natalHouse, 7);
      expect(guide.skyAspects.single.body, Planet.sun);
      expect(guide.natalAspects.single.body, Planet.northNode);
      expect(guide.natalAspects.single.toJson()['body'], 'north_node');
    });

    test('stone recommendation parses reasons and colour', () {
      final result = StoneRecommendation.fromJson(stonesJson());
      final stone = result.suggestions.single.stone;
      expect(stone.intents, contains(StoneIntent.love));
      expect(stone.colorValue, 0xFF0B8457);
      expect(result.weakestElements, ['air']);
      expect(result.suggestions.single.reasons.first.kind, 'intent');
    });

    test('numerology keeps display order and master flags', () {
      Json n(int v) => {
        'number': v,
        'is_master': v > 9,
        'title': 't$v',
        'keywords': 'k',
        'meaning': 'm',
      };
      final profile = NumerologyProfile.fromJson({
        'name_used': 'Nicat Test',
        'birth_date': '1990-05-15',
        'reference': '2026-09-26',
        'life_path': n(11),
        'destiny': n(3),
        'soul_urge': n(6),
        'personality': n(6),
        'birthday': n(6),
        'personal_year': n(3),
        'personal_month': n(3),
        'version': 'numerology_pythagorean_v1',
      });
      expect(profile.numbers.keys.first, 'life_path');
      expect(profile.numbers['life_path']!.isMaster, isTrue);
    });
  });

  group('providers', () {
    test('mock mode has no guide data and says so', () async {
      final env = await TestEnv.create();
      final container = ProviderContainer.test(
        overrides: [
          appPreferencesProvider.overrideWithValue(env.preferences),
          guidesRepositoryProvider.overrideWithValue(null),
        ],
      );
      final sub = container.listen(moonGuideProvider, (_, _) {});
      addTearDown(sub.close);
      await Future<void>.delayed(Duration.zero);
      expect(
        sub.read().error,
        isA<ApiException>().having((e) => e.code, 'code', 'demo_unavailable'),
      );
    });

    test('moon guide provider reads the repository once', () async {
      final repo = _FakeGuides();
      final env = await TestEnv.create();
      final container = ProviderContainer.test(
        overrides: [
          appPreferencesProvider.overrideWithValue(env.preferences),
          guidesRepositoryProvider.overrideWithValue(repo),
        ],
      );
      final sub = container.listen(moonGuideProvider, (_, _) {});
      final guide = await container.read(moonGuideProvider.future);
      expect(guide.sign, ZodiacSign.aries);
      expect(repo.moonCalls, 1);
      sub.close();
    });
  });

  group('entitlement service', () {
    const catalogue = FeatureCatalogue(
      gatingEnabled: true,
      premiumFeatures: {'advanced_tarot', 'synastry', 'advanced_transits'},
      freeSpreads: {
        'tarot': {'single_card'},
      },
      premiumTransitRanges: {'month', 'year'},
    );
    DivinationSpread spread(String code) => DivinationSpread({
      'spread_code': code,
      'card_count': 1,
      'positions': <Json>[],
    });

    test('free user sees locks from the catalogue only', () {
      const service = EntitlementService(catalogue: catalogue, premium: false);
      expect(service.canUse(PremiumFeature.synastry), isFalse);
      expect(service.canUse(PremiumFeature.advancedRune), isTrue);
      expect(
        service.canUseSpread(DeckType.tarot, spread('single_card')),
        isTrue,
      );
      expect(
        service.canUseSpread(DeckType.tarot, spread('celtic_cross')),
        isFalse,
      );
      expect(service.canUseTransitRange('week'), isTrue);
      expect(service.canUseTransitRange('month'), isFalse);
    });

    test('premium and disabled gating unlock everything', () {
      const premium = EntitlementService(catalogue: catalogue, premium: true);
      expect(premium.canUse(PremiumFeature.synastry), isTrue);
      const off = EntitlementService(
        catalogue: FeatureCatalogue(
          gatingEnabled: false,
          premiumFeatures: {'synastry'},
          freeSpreads: {},
          premiumTransitRanges: {'month'},
        ),
        premium: false,
      );
      expect(off.canUse(PremiumFeature.synastry), isTrue);
      expect(off.canUseTransitRange('month'), isTrue);
    });

    test('unknown catalogue never shows a lock', () {
      const unknown = EntitlementService(catalogue: null, premium: false);
      expect(unknown.canUse(PremiumFeature.synastry), isTrue);
      expect(
        unknown.canUseSpread(DeckType.tarot, spread('celtic_cross')),
        isTrue,
      );
    });

    test('catalogue parses the server payload', () {
      final parsed = FeatureCatalogue.fromJson({
        'version': 'features_v1',
        'gating_enabled': true,
        'premium_features': ['synastry'],
        'free_spreads': {
          'rune': ['single_rune'],
        },
        'premium_transit_ranges': ['month'],
      });
      expect(parsed.freeSpreads['rune'], {'single_rune'});
      expect(parsed.premiumFeatures, {'synastry'});
    });
  });

  group('screens', () {
    testWidgets('moon guide shows phase, house and guidance', (tester) async {
      tester.view.physicalSize =
          const Size(390, 1600) * tester.view.devicePixelRatio;
      addTearDown(tester.view.reset);
      disableAnimations(tester);
      final env = await TestEnv.create();
      await tester.pumpWidget(
        _app(const MoonGuideScreen(), _FakeGuides(), env),
      );
      await tester.pumpAndSettle();
      expect(
        find.text('Dolunay, Ay Koç burcunda ve 7. evinde.'),
        findsOneWidget,
      );
      expect(find.textContaining('7. ev'), findsWidgets);
      expect(
        find.text('Sonuçları görmek, kutlamak ve paylaşmak'),
        findsOneWidget,
      );
      expect(find.text('Duygusal tepkileri büyütmek'), findsOneWidget);
    });

    testWidgets('stone guide explains why a stone was chosen', (tester) async {
      tester.view.physicalSize =
          const Size(390, 2000) * tester.view.devicePixelRatio;
      addTearDown(tester.view.reset);
      disableAnimations(tester);
      final env = await TestEnv.create();
      await tester.pumpWidget(
        _app(const StoneGuideScreen(), _FakeGuides(), env),
      );
      await tester.pumpAndSettle();
      expect(find.text('Malakit'), findsOneWidget);
      // Short tags up front; the full astrological reason one tap away.
      expect(find.text('Transit'), findsOneWidget);
      await tester.tap(find.text('Neden önerildi?').first);
      await tester.pumpAndSettle();
      expect(
        find.text('Transit Merkür natal Satürn ile kare.'),
        findsOneWidget,
      );
      expect(
        find.text('Taş önerileri tıbbi tavsiye değildir.'),
        findsOneWidget,
      );
    });
  });
}
