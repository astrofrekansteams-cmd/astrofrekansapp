import 'package:astrofrekans/core/astrology/data/production_models.dart';
import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/routing/app_routes.dart';
import 'package:astrofrekans/core/storage/app_preferences.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/features/auth/application/session_controller.dart';
import 'package:astrofrekans/features/billing/application/coin_spend.dart';
import 'package:astrofrekans/features/billing/application/entitlement_service.dart';
import 'package:astrofrekans/features/billing/application/entitlement_controller.dart';
import 'package:astrofrekans/features/billing/data/billing_models.dart';
import 'package:astrofrekans/features/billing/data/billing_repository.dart';
import 'package:astrofrekans/features/billing/data/billing_service.dart';
import 'package:astrofrekans/features/billing/data/coin_models.dart';
import 'package:astrofrekans/features/billing/data/coin_repository.dart';
import 'package:astrofrekans/features/billing/presentation/coin_wallet_screen.dart';
import 'package:astrofrekans/features/billing/presentation/premium_screen.dart';
import 'package:astrofrekans/features/consultation/data/push_service.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_models.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_repository.dart';
import 'package:astrofrekans/features/marketplace/presentation/marketplace_screens.dart';
import 'package:astrofrekans/features/profile/domain/user_profile.dart';
import 'package:astrofrekans/features/profile/presentation/profile_settings_screens.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';

const _user = UserProfile(id: 'u1', name: 'Nova', email: 'nova@example.com');

Json _plan(String tier, int coins) => {
  'tier': tier,
  'products': <String>[],
  'daily_draws': 3,
  'monthly_coins': coins,
  'ad_free': tier != 'free',
  'features': <String>[],
  'includes_paid_reports': false,
};

final _catalog = CoinCatalog({
  'spend_items': [
    {'code': 'ai_deep_reading', 'price': 40, 'available': true},
    {'code': 'special_analysis', 'price': 60, 'available': true},
    {'code': 'single_premium_content', 'price': 30, 'available': true},
  ],
  'coin_packs': [
    {'product_code': 'coins_120', 'coins': 120},
  ],
  'plans': [_plan('free', 0), _plan('premium', 150), _plan('cosmic_plus', 500)],
  'comparison': [
    {
      'key': 'ai_deep_reading',
      'cells': {'free': 'coins', 'premium': 'coins', 'cosmic_plus': 'included'},
      'values': <String, int>{},
      'coin_item': 'ai_deep_reading',
    },
    {
      'key': 'ad_free',
      'cells': {
        'free': 'none',
        'premium': 'included',
        'cosmic_plus': 'included',
      },
      'values': <String, int>{},
      'coin_item': null,
    },
    {
      'key': 'monthly_coins',
      'cells': {
        'free': 'none',
        'premium': 'included',
        'cosmic_plus': 'included',
      },
      'values': {'free': 0, 'premium': 150, 'cosmic_plus': 500},
      'coin_item': null,
    },
  ],
});

class _Coins extends CoinRepository {
  _Coins({this.balance = 100}) : super(ApiClient(Dio()));
  final int balance;
  @override
  Future<CoinWallet> wallet() async => CoinWallet({
    'balance': balance,
    'tier': 'free',
    'monthly_bonus': 0,
    'ads_enabled': false,
    'ads_daily_limit': 5,
    'ad_reward_coins': 10,
  });
  @override
  Future<List<CoinTransaction>> transactions({int limit = 50}) async => [];
  @override
  Future<CoinCatalog> catalog() async => _catalog;
}

class _FreeBilling extends Fake implements BillingRepository {
  @override
  Future<EntitlementSummary> entitlements() async => EntitlementSummary({
    'tier': 'free',
    'premium': false,
    'credits': <String, int>{},
    'items': <Map<String, dynamic>>[],
  });
}

class _Market extends ApiMarketplaceRepository {
  _Market() : super(ApiClient(Dio()));
  final queries = <ExpertQuery>[];
  final favoriteCalls = <(String, bool)>[];

  static Json expert(String id, String name, {bool favorite = false}) => {
    'id': id,
    'display_name': name,
    'headline': 'Astroloji',
    'bio': 'On yıllık deneyim.',
    'languages': ['tr', 'en'],
    'specialties': ['astrology', 'tarot'],
    'experience_years': 10,
    'verified': true,
    'rating_average': 4.9,
    'rating_count': 21,
    'is_favorite': favorite,
    'from_price': {'amount_minor': 50000, 'currency': 'TRY'},
  };

  @override
  Future<ExpertPage> search(ExpertQuery query) async {
    queries.add(query);
    return ExpertPage({
      'total': 1,
      'limit': 20,
      'offset': 0,
      'items': [expert('e1', 'Aylin Yıldız')],
    });
  }

  @override
  Future<List<Expert>> favorites() async => [
    Expert(expert('e2', 'Deniz Kaya', favorite: true)),
  ];

  @override
  Future<void> setFavorite(String id, bool value) async =>
      favoriteCalls.add((id, value));

  @override
  Future<Expert> detail(String id) async => Expert({
    ...expert(id, 'Aylin Yıldız'),
    'services': [
      {
        'id': 's1',
        'expert_id': id,
        'service_code': 'natal_consultation',
        'title': 'Doğum haritası görüşmesi',
        'description': 'Haritanın temel temaları.',
        'delivery_type': 'video',
        'duration_minutes': 45,
        'price': {'amount_minor': 50000, 'currency': 'TRY'},
      },
    ],
  });

  @override
  Future<ReviewPage> reviews(
    String id, {
    int limit = 20,
    int offset = 0,
  }) async => ReviewPage({
    'items': [
      {'id': 'r1', 'order_id': 'o1', 'rating': 5, 'comment': 'Çok net.'},
    ],
    'total': 1,
    'rating_average': 5.0,
  });

  @override
  Future<SlotPage> slots(
    String expertId,
    String serviceId,
    DateTime from,
    DateTime to,
  ) async => SlotPage({
    'expert_service_id': serviceId,
    'display_timezone': 'Europe/Istanbul',
    'slots': [
      {
        'starts_at_utc': '2026-10-01T09:00:00Z',
        'ends_at_utc': '2026-10-01T09:45:00Z',
        'display_timezone': 'Europe/Istanbul',
      },
    ],
  });
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
  List<Object> overrides = const [],
  bool scaffold = true,
}) async {
  tester.view.physicalSize =
      const Size(390, 2600) * tester.view.devicePixelRatio;
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
        home: scaffold ? Scaffold(body: child) : child,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('plans compare Ücretsiz / Premium / Kozmik+ row by row', (
    tester,
  ) async {
    final controller = EntitlementController(
      _FreeBilling(),
      const DisabledBillingService(),
    );
    await controller.start();
    addTearDown(controller.dispose);
    await _pump(
      tester,
      const PremiumScreen(),
      scaffold: false,
      overrides: [
        entitlementControllerProvider.overrideWithValue(controller),
        coinCatalogProvider.overrideWith((ref) async => _catalog),
      ],
    );
    expect(find.text('Mevcut plan: Ücretsiz'), findsOneWidget);
    // The monthly bonus, prominent, for an upgrade.
    expect(find.byKey(const ValueKey('plan-monthly-bonus')), findsOneWidget);
    expect(
      find.text('Premium her ay 150, Kozmik+ her ay 500 AstroCoin ekler.'),
      findsOneWidget,
    );
    final expander = find.byKey(const ValueKey('expand-plan-comparison'));
    await tester.ensureVisible(expander);
    await tester.tap(
      find.descendant(of: expander, matching: find.byType(ListTile)).first,
    );
    await tester.pumpAndSettle();
    final table = find.byKey(const ValueKey('plan-comparison'));
    expect(table, findsOneWidget);
    for (final header in ['ÜCRETSİZ', 'PREMIUM', 'KOZMİK+']) {
      expect(
        find.descendant(of: table, matching: find.text(header)),
        findsOneWidget,
      );
    }
    Finder row(String key, String text) => find.descendant(
      of: find.byKey(ValueKey('cmp-$key')),
      matching: find.text(text),
    );
    // Prices come from the catalogue, never from the app.
    expect(row('ai_deep_reading', 'Coin ile\n40'), findsNWidgets(2));
    expect(row('ai_deep_reading', 'dahil'), findsOneWidget);
    expect(row('ad_free', 'dahil değil'), findsOneWidget);
    expect(row('monthly_coins', '150'), findsOneWidget);
    expect(row('monthly_coins', '500'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('wallet: five sections; ads "coming soon" without a network', (
    tester,
  ) async {
    await _pump(
      tester,
      const CoinWalletScreen(),
      overrides: [
        coinRepositoryProvider.overrideWithValue(_Coins()),
        coinCatalogProvider.overrideWith((ref) async => _catalog),
      ],
    );
    expect(find.byKey(const ValueKey('coin-balance')), findsOneWidget);
    for (final title in [
      'Coin Kazan',
      'Coin Satın Al',
      'Coin Harca',
      'Son Hareketler',
    ]) {
      expect(find.text(title), findsOneWidget, reason: title);
    }
    expect(find.byKey(const ValueKey('ads-soon')), findsOneWidget);
    expect(find.text('Reklamla Coin Kazan'), findsOneWidget);
    expect(find.byKey(const ValueKey('watch-ad')), findsNothing);
    expect(find.byKey(const ValueKey('pack-coins_120')), findsOneWidget);
    expect(find.text('Astro AI derin yorum'), findsOneWidget);
  });

  group('coin lock', () {
    Future<ProviderContainer> pumpLock(WidgetTester tester, int balance) async {
      await _pump(
        tester,
        const CoinLockCard(
          unlockKey: 'solar_return:2026',
          feature: PremiumFeature.solarReturn,
        ),
        overrides: [
          coinRepositoryProvider.overrideWithValue(_Coins(balance: balance)),
          coinCatalogProvider.overrideWith((ref) async => _catalog),
        ],
      );
      return ProviderScope.containerOf(
        tester.element(find.byType(CoinLockCard)),
      );
    }

    testWidgets('confirmed spend remembers the unlock', (tester) async {
      final container = await pumpLock(tester, 100);
      expect(find.text('Tek seferlik aç · 30 Coin'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('coin-unlock')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('coin-confirm')), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('coin-confirm-pay')));
      await tester.pumpAndSettle();
      final ref = container.read(coinUnlocksProvider)['solar_return:2026'];
      expect(ref, startsWith('unlock-'));
      // Asking again returns the same reference: never a second charge.
      expect(
        container
            .read(coinUnlocksProvider.notifier)
            .unlock('solar_return:2026'),
        ref,
      );
    });

    testWidgets('a short balance unlocks nothing', (tester) async {
      final container = await pumpLock(tester, 5);
      await tester.tap(find.byKey(const ValueKey('coin-unlock')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('coin-insufficient')), findsOneWidget);
      await tester.tapAt(const Offset(4, 4)); // dismiss
      await tester.pumpAndSettle();
      expect(container.read(coinUnlocksProvider), isEmpty);
    });
  });

  group('consultants', () {
    testWidgets('categories, available today, rating and favourites', (
      tester,
    ) async {
      final market = _Market();
      await _pump(
        tester,
        const MarketplaceScreen(),
        scaffold: false,
        overrides: [marketplaceRepositoryProvider.overrideWithValue(market)],
      );
      expect(find.text('Aylin Yıldız'), findsOneWidget);
      expect(find.text('Astroloji · Tarot'), findsOneWidget);

      await tester.ensureVisible(find.byKey(const ValueKey('category-tarot')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('category-tarot')));
      await tester.pumpAndSettle();
      expect(market.queries.last.specialty, 'tarot');

      await tester.ensureVisible(
        find.byKey(const ValueKey('filter-available-today')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('filter-available-today')));
      await tester.pumpAndSettle();
      expect(market.queries.last.availableToday, isTrue);
      expect(market.queries.last.query['available_today'], isTrue);
      expect(market.queries.last.specialty, 'tarot');

      await tester.ensureVisible(find.byKey(const ValueKey('filter-rating')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('filter-rating')));
      await tester.pumpAndSettle();
      expect(market.queries.last.ratingMin, 4.5);

      await tester.tap(find.byKey(const ValueKey('favorite-e1')));
      await tester.pumpAndSettle();
      expect(market.favoriteCalls, [('e1', true)]);

      await tester.ensureVisible(
        find.byKey(const ValueKey('filter-favorites')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('filter-favorites')));
      await tester.pumpAndSettle();
      expect(find.text('Deniz Kaya'), findsOneWidget);
      expect(find.text('Aylin Yıldız'), findsNothing);
    });

    testWidgets('profile: bio, specialties, languages, slots, Randevu Al', (
      tester,
    ) async {
      await _pump(
        tester,
        const ExpertDetailScreen(expertId: 'e1'),
        scaffold: false,
        overrides: [marketplaceRepositoryProvider.overrideWithValue(_Market())],
      );
      expect(find.byKey(const ValueKey('expert-header')), findsOneWidget);
      expect(find.text('On yıllık deneyim.'), findsOneWidget);
      expect(find.text('10 yıl deneyim'), findsOneWidget);
      expect(find.text('Türkçe'), findsOneWidget);
      expect(find.text('İngilizce'), findsOneWidget);
      expect(find.text('Doğum haritası görüşmesi'), findsOneWidget);
      expect(find.text('Görüntülü görüşme · 45 dk'), findsOneWidget);
      expect(find.byKey(const ValueKey('upcoming-slots')), findsOneWidget);
      expect(find.byKey(const ValueKey('book-appointment')), findsOneWidget);
      expect(find.text('Çok net.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    test('a query copy keeps or clears each filter', () {
      const base = ExpertQuery(specialty: 'tarot', ratingMin: 4.5);
      final cleared = base.copy(specialty: null, availableToday: true);
      expect(cleared.specialty, isNull);
      expect(cleared.ratingMin, 4.5);
      expect(cleared.query['available_today'], isTrue);
      expect(base.copy().specialty, 'tarot');
    });
  });

  testWidgets('notification switches are the ones the server honours', (
    tester,
  ) async {
    final session = _RecordingSession();
    await _pump(
      tester,
      const NotificationSettingsScreen(),
      overrides: [sessionProvider.overrideWith(() => session)],
    );
    for (final key in [
      'daily_horoscope',
      'ai_reports',
      'expert_messages',
      'appointment_reminders',
      'promotions',
    ]) {
      expect(find.byKey(ValueKey('flag-$key')), findsOneWidget, reason: key);
    }
    expect(find.textContaining('Gelen arama'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('flag-ai_reports')));
    await tester.pumpAndSettle();
    expect(
      (session.patches.single['notification_prefs']! as Map)['ai_reports'],
      isFalse,
    );
  });

  test('an "AI report ready" push opens the report', () {
    const id = '0f8fad5b-d9cb-469f-a165-70867728950e';
    expect(
      routeForPush({'event': 'ai_report_ready', 'report_id': id}),
      '${AppRoutes.aiReports}/$id',
    );
    expect(routeForPush({'event': 'ai_report_ready'}), isNull);
  });
}
