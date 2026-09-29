import 'package:astrofrekans/core/astrology/astrology_providers.dart';
import 'package:astrofrekans/core/astrology/data/mock_astrology_service.dart';
import 'package:astrofrekans/core/storage/app_preferences.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/features/auth/application/session_controller.dart';
import 'package:astrofrekans/features/billing/application/entitlement_service.dart';
import 'package:astrofrekans/features/guides/data/guides_repository.dart';
import 'package:astrofrekans/features/guides/domain/guide_models.dart';
import 'package:astrofrekans/features/guides/presentation/moon_guide_screen.dart';
import 'package:astrofrekans/features/guides/presentation/stone_guide_screen.dart';
import 'package:astrofrekans/core/network/api_client.dart';
import 'package:dio/dio.dart';
import 'package:astrofrekans/core/astrology/data/production_models.dart';
import 'package:astrofrekans/core/astrology/data/production_repository.dart';
import 'package:astrofrekans/features/production/presentation/divination_screen.dart';
import 'package:astrofrekans/features/home/presentation/home_screen.dart';
import 'package:astrofrekans/features/explore/presentation/explore_screen.dart';
import 'package:astrofrekans/features/production/presentation/sky_detail_screens.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';
import 'guides_test.dart' show moonGuideJson, stonesJson;

/// Every polished screen must lay out without overflow on 360-430 px phones,
/// at normal and at enlarged text.
const widths = <double>[360, 375, 390, 430];
const scales = <double>[1.0, 1.3];

typedef OverrideList = List<Object>;

Future<void> pumpAt(
  WidgetTester tester, {
  required TestEnv env,
  required Widget child,
  required double width,
  double textScale = 1.0,
  List<dynamic> extra = const [],
}) async {
  tester.view.physicalSize = Size(width, 844) * tester.view.devicePixelRatio;
  addTearDown(tester.view.reset);
  disableAnimations(tester);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        appPreferencesProvider.overrideWithValue(env.preferences),
        secureStoreProvider.overrideWithValue(env.store),
        astrologyServiceProvider.overrideWithValue(
          MockAstrologyService(latency: Duration.zero),
        ),
        todayProvider.overrideWithValue(env.today),
        entitlementServiceProvider.overrideWithValue(
          const EntitlementService(catalogue: null, premium: false),
        ),
        if (env.user != null)
          sessionProvider.overrideWith(
            () => SignedInSessionController(env.user!),
          ),
        ...extra.cast(),
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
        builder: (context, widget) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: TextScaler.linear(textScale)),
          child: widget!,
        ),
        home: Scaffold(backgroundColor: Colors.black, body: child),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

/// Pumps [build] at every width/scale and scrolls through it, failing on any
/// layout exception.
Future<void> sweep(
  WidgetTester tester,
  Widget Function() build, {
  List<dynamic> extra = const [],
}) async {
  final env = await TestEnv.create(user: testUser);
  for (final width in widths) {
    for (final scale in scales) {
      final errors = <FlutterErrorDetails>[];
      final previous = FlutterError.onError;
      FlutterError.onError = errors.add;
      try {
        await pumpAt(
          tester,
          env: env,
          child: build(),
          width: width,
          textScale: scale,
          extra: extra,
        );
        final scrollables = find.byType(Scrollable);
        if (scrollables.evaluate().isNotEmpty) {
          await tester.drag(scrollables.first, const Offset(0, -2400));
          await tester.pumpAndSettle();
        }
      } finally {
        FlutterError.onError = previous;
      }
      if (errors.isNotEmpty) {
        final detail = errors.first.toString().split('\n').take(40).join('\n');
        fail('layout error at ${width}px, text x$scale:\n$detail');
      }
    }
  }
}

class _Guides extends GuidesRepository {
  _Guides() : super(ApiClient(Dio()));
  @override
  Future<MoonGuide> moonGuide({
    DateTime? moment,
    required String locale,
  }) async => MoonGuide.fromJson(moonGuideJson());
  @override
  Future<StoneRecommendation> stones({
    required StoneMode mode,
    StoneIntent? intent,
    required String locale,
  }) async => StoneRecommendation.fromJson(stonesJson());
}

class _Production extends ProductionRepository {
  _Production() : super(ApiClient(Dio()));
  @override
  Future<List<DivinationSpread>> spreads(
    DeckType deck,
    String locale,
  ) async => [
    for (final (code, name, theme, titles) in [
      ('single_card', 'Tek Kart', 'general', ['Odak']),
      (
        'past_present_future',
        'Geçmiş - Şimdi - Gidişat',
        'general',
        ['Geçmiş', 'Şimdi', 'Gidişat'],
      ),
      (
        'love_spread',
        'Aşk Açılımı',
        'love',
        [
          'Sen',
          'Karşı Taraf',
          'Bağ',
          'Güçlü Yan',
          'Zorluk',
          'Tavsiye',
          'Gidişat',
        ],
      ),
      (
        'celtic_cross',
        'Kelt Haçı',
        'general',
        List.generate(10, (i) => 'Pozisyon ${i + 1}'),
      ),
    ])
      DivinationSpread({
        'spread_code': code,
        'name': name,
        'theme': theme,
        'card_count': titles.length,
        'allow_reversed': true,
        'positions': [
          for (final t in titles) {'title': t, 'description': 'Açıklama: $t'},
        ],
      }),
  ];
  @override
  Future<List<ContractRecord>> readings() async => [];
}

void main() {
  testWidgets('home lays out at 360-430 px', (tester) async {
    await sweep(tester, () => const HomeScreen());
  });

  testWidgets('natal chart lays out at 360-430 px', (tester) async {
    await sweep(tester, () => const NatalScreen());
    expect(find.text('Gezegenler'), findsOneWidget);
  });

  testWidgets('transits lay out at 360-430 px', (tester) async {
    await sweep(tester, () => const TransitsScreen());
  });

  testWidgets('moon guide lays out at 360-430 px', (tester) async {
    await sweep(
      tester,
      () => const MoonGuideScreen(),
      extra: [guidesRepositoryProvider.overrideWithValue(_Guides())],
    );
    expect(find.text('Tam Dolunay anı'), findsNothing); // next phase differs
  });

  testWidgets('stone guide lays out at 360-430 px', (tester) async {
    await sweep(
      tester,
      () => const StoneGuideScreen(),
      extra: [guidesRepositoryProvider.overrideWithValue(_Guides())],
    );
  });

  testWidgets('tarot lays out at 360-430 px', (tester) async {
    await sweep(
      tester,
      () => const DivinationScreen(deck: DeckType.tarot),
      extra: [productionRepositoryProvider.overrideWithValue(_Production())],
    );
    // Name already spells the positions: no duplicated subtitle.
    expect(find.text('Geçmiş · Şimdi · Gidişat'), findsNothing);
  });

  testWidgets('explore lays out at 360-430 px', (tester) async {
    await sweep(tester, () => const ExploreScreen());
    // Astro AI lives in the tab bar, not in the Explore hero.
    expect(find.text('Astro AI'), findsNothing);
  });

  testWidgets('home date stays on one line on 360-375 px phones', (
    tester,
  ) async {
    final env = await TestEnv.create(user: testUser);
    for (final width in <double>[360, 375]) {
      for (final scale in scales) {
        await pumpAt(
          tester,
          env: env,
          child: const HomeScreen(),
          width: width,
          textScale: scale,
        );
        // Test clock: 12 March 2026; every format keeps the month.
        final date = find.textContaining('MAR').first;
        final text = tester.widget<Text>(date);
        expect(text.maxLines, 1);
        // One line of 12 px text (x1.3 at most) is well under 24 px.
        expect(tester.getSize(date).height, lessThan(24));
        expect(tester.takeException(), isNull);
      }
    }
  });

  testWidgets('hero stone tags share one row at 375 px', (tester) async {
    final env = await TestEnv.create(user: testUser);
    await pumpAt(
      tester,
      env: env,
      child: const StoneGuideScreen(),
      width: 375,
      extra: [guidesRepositoryProvider.overrideWithValue(_Guides())],
    );
    final tags = [find.text('Niyet'), find.text('Transit')];
    final ys = [for (final t in tags) tester.getTopLeft(t.first).dy];
    expect(ys.toSet().length, 1, reason: 'tags wrapped onto separate lines');
  });
}
