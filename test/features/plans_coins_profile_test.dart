import 'package:astrofrekans/core/astrology/data/production_models.dart';
import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/core/storage/app_preferences.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/features/auth/application/session_controller.dart';
import 'package:astrofrekans/features/billing/application/entitlement_service.dart';
import 'package:astrofrekans/features/billing/data/coin_models.dart';
import 'package:astrofrekans/features/billing/data/coin_repository.dart';
import 'package:astrofrekans/features/billing/presentation/coin_wallet_screen.dart';
import 'package:astrofrekans/features/explore/presentation/widgets/marketplace_hub.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_models.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_repository.dart';
import 'package:astrofrekans/features/production/application/core_providers.dart';
import 'package:astrofrekans/features/profile/domain/user_profile.dart';
import 'package:astrofrekans/features/profile/presentation/profile_settings_screens.dart';
import 'package:astrofrekans/features/profile/presentation/profile_widgets.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';

const _user = UserProfile(
  id: 'u1',
  name: 'Nova Star',
  email: 'nova@example.com',
  avatarPreset: 'pisces',
  bio: 'Balık Güneş, Akrep yükselen.',
  coverTheme: 'aurora',
  subscriptionTier: SubscriptionTier.cosmicPlus,
);

Json _wallet({int balance = 40, bool ads = true, int watched = 1}) => {
  'balance': balance,
  'lifetime_earned': 60,
  'lifetime_spent': 20,
  'tier': 'free',
  'monthly_bonus': 0,
  'ads_enabled': ads,
  'ads_watched_today': watched,
  'ads_daily_limit': 5,
  'ad_reward_coins': 10,
  'bonus_granted': 0,
};

final _catalog = CoinCatalog({
  'spend_items': [
    {'code': 'extra_draw', 'price': 10, 'available': true},
    {'code': 'ai_deep_reading', 'price': 40, 'available': false},
  ],
  'coin_packs': [
    {'product_code': 'coins_120', 'coins': 120},
  ],
  'plans': <Json>[],
});

class _FakeCoins extends CoinRepository {
  _FakeCoins() : super(ApiClient(Dio()));
  final rewarded = <String>[];
  int balance = 40;
  ApiException? rewardError;

  @override
  Future<CoinWallet> wallet() async => CoinWallet(_wallet(balance: balance));
  @override
  Future<List<CoinTransaction>> transactions({int limit = 50}) async => [
    CoinTransaction({
      'id': 't1',
      'amount': 10,
      'balance_after': 40,
      'kind': 'ad_reward',
      'reason': 'mock',
      'created_at': '2026-09-27T10:00:00Z',
    }),
    CoinTransaction({
      'id': 't2',
      'amount': -25,
      'balance_after': 30,
      'kind': 'spend',
      'reason': 'advanced_spread',
      'created_at': '2026-09-26T10:00:00Z',
    }),
  ];
  @override
  Future<CoinCatalog> catalog() async => _catalog;
  @override
  Future<CoinWallet> rewardAd(String token) async {
    if (rewardError case final ApiException e) throw e;
    rewarded.add(token);
    balance += 10;
    return CoinWallet(_wallet(balance: balance, watched: 2));
  }
}

class _FakeAds implements RewardedAdService {
  @override
  bool get isDemo => true;
  @override
  Future<String?> show() async => 'reward-token-123';
}

class _FakeMarket extends ApiMarketplaceRepository {
  _FakeMarket({this.experts = true}) : super(ApiClient(Dio()));
  final bool experts;
  @override
  Future<ExpertPage> search(ExpertQuery query) async => ExpertPage({
    'total': experts ? 2 : 0,
    'limit': 6,
    'offset': 0,
    'items': [
      if (experts) ...[
        {
          'id': 'e1',
          'display_name': 'Aylin Yıldız',
          'headline': 'Doğum haritası ve ilişki astrolojisi',
          'specialties': ['astrology', 'synastry'],
          'experience_years': 8,
          'verified': true,
          'rating_average': 4.8,
          'rating_count': 12,
          'from_price': {'amount_minor': 45000, 'currency': 'TRY'},
        },
        {
          'id': 'e2',
          'display_name': 'Deniz Kaya',
          'specialties': ['tarot'],
          'experience_years': 3,
          'verified': false,
          'rating_average': 0,
          'rating_count': 0,
        },
      ],
    ],
  });
  @override
  Future<List<Appointment>> appointments({
    bool expert = false,
    bool upcoming = false,
  }) async => [
    Appointment({
      'id': 'a1',
      'expert_id': 'e1',
      'expert_service_id': 's1',
      'starts_at_utc': '2026-10-02T15:30:00Z',
      'ends_at_utc': '2026-10-02T16:00:00Z',
      'timezone': 'Europe/Istanbul',
      'status': 'confirmed',
    }),
  ];
}

class _RecordingSession extends SignedInSessionController {
  _RecordingSession() : super(_user);
  final patches = <Map<String, Object?>>[];
  @override
  Future<void> customizeProfile(Map<String, Object?> patch) async {
    patches.add(patch);
  }
}

Future<void> _pump(
  WidgetTester tester,
  Widget child, {
  required List<Object> overrides,
}) async {
  tester.view.physicalSize =
      const Size(390, 2400) * tester.view.devicePixelRatio;
  addTearDown(tester.view.reset);
  disableAnimations(tester);
  final env = await TestEnv.create(user: _user);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        appPreferencesProvider.overrideWithValue(env.preferences),
        secureStoreProvider.overrideWithValue(env.store),
        ...overrides.cast(),
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
        home: Scaffold(body: child),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  group('plans', () {
    const catalogue = FeatureCatalogue(
      gatingEnabled: true,
      premiumFeatures: {'monthly_forecast', 'synastry', 'advanced_tarot'},
      freeSpreads: {
        'tarot': {'three_card'},
      },
      premiumTransitRanges: {'month'},
      featureTiers: {
        'monthly_forecast': SubscriptionTier.premium,
        'advanced_tarot': SubscriptionTier.premium,
        'synastry': SubscriptionTier.cosmicPlus,
      },
    );

    test('each plan opens its own features', () {
      const free = EntitlementService(catalogue: catalogue, premium: false);
      const premium = EntitlementService(
        catalogue: catalogue,
        premium: true,
        tier: SubscriptionTier.premium,
      );
      const cosmic = EntitlementService(
        catalogue: catalogue,
        premium: true,
        tier: SubscriptionTier.cosmicPlus,
      );
      expect(free.canUse(PremiumFeature.monthlyForecast), isFalse);
      expect(premium.canUse(PremiumFeature.monthlyForecast), isTrue);
      expect(premium.canUse(PremiumFeature.synastry), isFalse);
      expect(
        premium.requiredTier(PremiumFeature.synastry),
        SubscriptionTier.cosmicPlus,
      );
      expect(cosmic.canUse(PremiumFeature.synastry), isTrue);
      // A feature the catalogue does not gate is free for everyone.
      expect(free.canUse(PremiumFeature.davison), isTrue);
    });

    test('tiers order and parse', () {
      expect(
        SubscriptionTier.fromWire('cosmic_plus'),
        SubscriptionTier.cosmicPlus,
      );
      expect(SubscriptionTier.fromWire('unknown'), SubscriptionTier.free);
      expect(
        SubscriptionTier.cosmicPlus.includes(SubscriptionTier.premium),
        isTrue,
      );
      expect(
        SubscriptionTier.premium.includes(SubscriptionTier.cosmicPlus),
        isFalse,
      );
      expect(_user.isPremium, isTrue);
    });
  });

  group('coin wallet', () {
    testWidgets('balance, earning, spending and history', (tester) async {
      final coins = _FakeCoins();
      await _pump(
        tester,
        const CoinWalletScreen(),
        overrides: [
          coinRepositoryProvider.overrideWithValue(coins),
          rewardedAdServiceProvider.overrideWithValue(_FakeAds()),
        ],
      );
      expect(find.byKey(const ValueKey('coin-balance')), findsOneWidget);
      Finder inBalance(String text) => find.descendant(
        of: find.byKey(const ValueKey('coin-balance')),
        matching: find.text(text),
      );
      expect(inBalance('40'), findsOneWidget);
      expect(find.text('Bugün kalan: 4 / 5'), findsOneWidget);
      // What coins buy, including items that are not live yet.
      expect(find.text('Günlük hakkın bittiğinde ek açılım'), findsOneWidget);
      expect(find.text('Yakında'), findsOneWidget);
      // History, newest first, signed amounts.
      expect(find.text('Reklam ödülü'), findsOneWidget);
      expect(find.text('+10'), findsOneWidget);
      expect(find.text('-25'), findsOneWidget);

      await tester.tap(find.byKey(const ValueKey('watch-ad')));
      await tester.pumpAndSettle();
      expect(coins.rewarded, ['reward-token-123']);
      expect(find.text('+10 coin hesabına eklendi.'), findsOneWidget);
      expect(inBalance('50'), findsOneWidget);
    });

    testWidgets('daily ad limit is explained', (tester) async {
      final coins = _FakeCoins()
        ..rewardError = const ApiException(
          kind: ApiErrorKind.rateLimited,
          statusCode: 429,
          code: 'ad_reward_limit_reached',
        );
      await _pump(
        tester,
        const CoinWalletScreen(),
        overrides: [
          coinRepositoryProvider.overrideWithValue(coins),
          rewardedAdServiceProvider.overrideWithValue(_FakeAds()),
        ],
      );
      await tester.tap(find.byKey(const ValueKey('watch-ad')));
      await tester.pumpAndSettle();
      expect(find.text('Bugünkü reklam hakların doldu.'), findsOneWidget);
    });
  });

  group('explore marketplace hub', () {
    testWidgets('consultants, service types and appointments', (tester) async {
      await _pump(
        tester,
        const SingleChildScrollView(
          child: Column(
            children: [
              SpreadsSection(),
              ConsultantsSection(),
              ServiceTypesSection(),
              AppointmentsEntry(),
            ],
          ),
        ),
        overrides: [
          marketplaceRepositoryProvider.overrideWithValue(_FakeMarket()),
        ],
      );
      for (final deck in ['tarot', 'rune', 'katina']) {
        expect(find.byKey(ValueKey('deck-$deck')), findsOneWidget);
      }
      expect(find.text('Danışmanlarla Görüş'), findsOneWidget);
      expect(find.text('Tümünü gör'), findsOneWidget);
      expect(find.text('Aylin Yıldız'), findsOneWidget);
      expect(find.text('Astroloji · Sinastri'), findsOneWidget);
      expect(find.text('4.8 (12)'), findsOneWidget);
      expect(find.text('450.00 TRY’den'), findsOneWidget);
      expect(find.text('Yeni'), findsOneWidget); // no reviews yet
      for (final chip in [
        'Astrologlar',
        'Tarot Danışmanları',
        'Rün Danışmanları',
        'Katina Danışmanları',
      ]) {
        expect(find.text(chip), findsOneWidget, reason: chip);
      }
      for (final type in ['chat', 'voice', 'video', 'written_report']) {
        expect(find.byKey(ValueKey('service-$type')), findsOneWidget);
      }
      expect(find.text('Yazışarak danış'), findsOneWidget);
      expect(find.text('Görüntülü görüşme'), findsOneWidget);
      expect(find.text('Randevularım'), findsOneWidget);
      expect(find.textContaining('Sıradaki:'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('no consultants yet', (tester) async {
      await _pump(
        tester,
        const ConsultantsSection(),
        overrides: [
          marketplaceRepositoryProvider.overrideWithValue(
            _FakeMarket(experts: false),
          ),
        ],
      );
      expect(find.text('Şu an öne çıkan danışman yok.'), findsOneWidget);
    });
  });

  group('profile', () {
    testWidgets('header shows avatar, bio, plan and coins', (tester) async {
      await _pump(
        tester,
        const ProfileHeader(user: _user),
        overrides: [
          subscriptionTierProvider.overrideWithValue(
            SubscriptionTier.cosmicPlus,
          ),
          coinWalletProvider.overrideWith(
            (ref) async => CoinWallet(_wallet(balance: 275)),
          ),
          natalProvider.overrideWith(
            (ref) async =>
                throw const ApiException(kind: ApiErrorKind.validation),
          ),
        ],
      );
      expect(find.text('Nova Star'), findsOneWidget);
      expect(find.text('Balık Güneş, Akrep yükselen.'), findsOneWidget);
      expect(find.text('Kozmik+'), findsOneWidget);
      expect(find.byKey(const ValueKey('coin-chip')), findsOneWidget);
      expect(find.text('275'), findsOneWidget);
    });

    testWidgets('customisation saves only what the server accepts', (
      tester,
    ) async {
      final session = _RecordingSession();
      await _pump(
        tester,
        const ProfileCustomizeScreen(),
        overrides: [sessionProvider.overrideWith(() => session)],
      );
      await tester.tap(find.byKey(const ValueKey('avatar-leo')));
      await tester.enterText(
        find.byKey(const ValueKey('profile-bio')),
        '  Aslan ruhu  ',
      );
      await tester.tap(find.byKey(const ValueKey('cover-golden_dawn')));
      await tester.tap(find.text('English'));
      await tester.pump();
      await tester.ensureVisible(find.byKey(const ValueKey('profile-save')));
      await tester.tap(find.byKey(const ValueKey('profile-save')));
      await tester.pumpAndSettle();
      expect(session.patches, [
        {
          'name': 'Nova Star',
          'bio': 'Aslan ruhu',
          'avatar_preset': 'leo',
          'cover_theme': 'golden_dawn',
          'language': 'en',
        },
      ]);
    });

    testWidgets('privacy switches save the whole map', (tester) async {
      final session = _RecordingSession();
      await _pump(
        tester,
        const PrivacySettingsScreen(),
        overrides: [sessionProvider.overrideWith(() => session)],
      );
      await tester.tap(find.byKey(const ValueKey('flag-show_rising_sign')));
      await tester.pumpAndSettle();
      expect(session.patches.single['privacy'], {
        'show_sun_sign': true,
        'show_moon_sign': true,
        'show_rising_sign': false,
        'show_birth_date': false,
        'show_bio': true,
      });
    });
  });
}
