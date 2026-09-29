import 'dart:async';

import 'package:astrofrekans/core/astrology/data/production_models.dart';
import 'package:astrofrekans/core/astrology/data/production_repository.dart';
import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/features/billing/data/coin_models.dart';
import 'package:astrofrekans/features/billing/data/coin_repository.dart';
import 'package:astrofrekans/core/storage/app_preferences.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/core/widgets/widgets.dart';
import 'package:astrofrekans/features/billing/application/entitlement_service.dart';
import 'package:astrofrekans/features/production/presentation/divination_picker.dart';
import 'package:astrofrekans/features/profile/domain/user_profile.dart';
import 'package:astrofrekans/features/production/presentation/divination_screen.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';

const _titles = ['Geçmiş', 'Şimdi', 'Gidişat'];

Json _spread(DeckType deck) => {
  'spread_code': deck == DeckType.rune ? 'three_rune' : 'three_card',
  'name': 'Üçlü Açılım',
  'theme': 'general',
  'card_count': 3,
  'positions': [
    for (final (i, t) in _titles.indexed)
      {'index': i + 1, 'key': 'p$i', 'title': t, 'description': 'd$i'},
  ],
};

int _deckSize(DeckType deck) => switch (deck) {
  DeckType.tarot => 78,
  DeckType.katina => 65,
  DeckType.rune => 24,
};

Json _session(DeckType deck) => {
  'session_id': 's-${deck.name}',
  'deck_type': deck.name,
  'deck_size': _deckSize(deck),
  'spread_code': _spread(deck)['spread_code']!,
  'spread_name': 'Üçlü Açılım',
  'required_selections': 3,
  'positions': [
    for (final (i, t) in _titles.indexed)
      {'index': i + 1, 'key': 'p$i', 'title': t, 'description': 'd$i'},
  ],
  // Always in the future: a fixed date turns every test red once it passes.
  'expires_at': DateTime.now()
      .toUtc()
      .add(const Duration(minutes: 15))
      .toIso8601String(),
  'status': 'open',
  'reading_id': null,
};

Json _reading(DeckType deck, List<int> picks) => {
  'id': 'reading-${deck.name}',
  'deck_type': deck.name,
  'deck_version': 'v1',
  'spread_code': _spread(deck)['spread_code']!,
  'spread_version': 'v1',
  'spread_name': 'Üçlü Açılım',
  'spread_theme': 'general',
  'locale': 'tr',
  'rng_source': 'system_csprng',
  'drawn_at': '2026-09-27T12:00:00Z',
  'status': 'drawn',
  'has_interpretation': false,
  'created_at': '2026-09-27T12:00:00Z',
  'items': [
    for (final (i, slot) in picks.indexed)
      {
        'draw_order': i + 1,
        'position_index': i + 1,
        'position_key': 'p$i',
        'position_title': _titles[i],
        'position_role': 'role',
        'item_id': '${deck.name}:slot$slot',
        'display_name': 'Öğe $slot',
        'canonical_name': 'Item $slot',
        'orientation': 'upright',
        'image_asset_key': deck == DeckType.rune
            ? ['fehu', 'uruz', 'ansuz'][i]
            : 'missing_$slot',
        'keywords': <String>[],
        'meaning': 'Anlam $slot',
        'content_status': 'traditional',
      },
  ],
};

class _FakeRepo extends ProductionRepository {
  _FakeRepo(this.deck) : super(ApiClient(Dio()));
  final DeckType deck;
  final createdRefs = <String>[];
  final reveals = <List<int>>[];
  final fetched = <String>[];
  Completer<void>? revealGate;
  String serverStatus = 'open';
  ApiException? revealError;
  bool limitReached = false;
  final paidWithCoins = <bool>[];
  final interpretRefs = <String?>[];

  @override
  Future<Json> interpret(
    String id, {
    String locale = 'tr',
    String? consumerRef,
  }) async {
    interpretRefs.add(consumerRef);
    throw const ApiException(kind: ApiErrorKind.network);
  }

  @override
  Future<List<DivinationSpread>> spreads(DeckType deck, String locale) async =>
      [DivinationSpread(_spread(deck))];

  @override
  Future<List<ContractRecord>> readings() async => [];

  @override
  Future<DrawSession> createDrawSession(
    DeckType deck,
    String spread, {
    required String consumerRef,
    String locale = 'tr',
    String? question,
    bool includeOptional = false,
    bool payWithCoins = false,
  }) async {
    paidWithCoins.add(payWithCoins);
    if (limitReached && !payWithCoins) {
      throw const ApiException(
        kind: ApiErrorKind.rateLimited,
        statusCode: 429,
        code: 'daily_draw_limit_reached',
      );
    }
    createdRefs.add(consumerRef);
    return DrawSession(_session(deck));
  }

  @override
  Future<DivinationReading> revealDrawSession(
    String id,
    List<int> positions,
  ) async {
    reveals.add(List.of(positions));
    await revealGate?.future;
    if (revealError case final ApiException e) throw e;
    return DivinationReading(_reading(deck, positions));
  }

  @override
  Future<DrawSession> drawSession(String id) async {
    fetched.add(id);
    return DrawSession({..._session(deck), 'status': serverStatus});
  }
}

class _FakeCoins extends CoinRepository {
  _FakeCoins() : super(ApiClient(Dio()));
  @override
  Future<DrawAllowance> drawAllowance() async => DrawAllowance({
    'enforced': true,
    'daily_limit': 3,
    'used_today': 3,
    'remaining': 0,
    'extra_draw_price': 10,
    'advanced_spread_price': 25,
  });
}

/// Leaves the divination route (the screen is disposed) and comes back.
final _onScreen = ValueNotifier<bool>(true);

Future<void> _leaveAndReturn(WidgetTester tester) async {
  _onScreen.value = false;
  await tester.pumpAndSettle();
  expect(find.byType(DivinationScreen), findsNothing);
  _onScreen.value = true;
  await tester.pumpAndSettle();
}

Future<_FakeRepo> _pump(
  WidgetTester tester,
  DeckType deck, {
  bool animations = false,
  RevealPrecache? precache,
  bool coins = false,
  int balance = 30,
  EntitlementService entitlements = const EntitlementService(
    catalogue: null,
    premium: true,
  ),
}) async {
  _onScreen.value = true;
  tester.view.physicalSize =
      const Size(390, 5000) * tester.view.devicePixelRatio;
  addTearDown(tester.view.reset);
  if (!animations) disableAnimations(tester);
  final env = await TestEnv.create();
  final repo = _FakeRepo(deck);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        appPreferencesProvider.overrideWithValue(env.preferences),
        secureStoreProvider.overrideWithValue(env.store),
        productionRepositoryProvider.overrideWithValue(repo),
        entitlementServiceProvider.overrideWithValue(entitlements),
        if (precache != null)
          revealPrecacheProvider.overrideWithValue(precache),
        if (coins) ...[
          coinRepositoryProvider.overrideWithValue(_FakeCoins()),
          coinCatalogProvider.overrideWith(
            (ref) async => CoinCatalog({
              'spend_items': [
                {'code': 'extra_draw', 'price': 10, 'available': true},
                {'code': 'advanced_spread', 'price': 25, 'available': true},
                {'code': 'ai_deep_reading', 'price': 40, 'available': true},
              ],
              'coin_packs': <Json>[],
              'plans': <Json>[],
            }),
          ),
          coinWalletProvider.overrideWith(
            (ref) async => CoinWallet({'balance': balance}),
          ),
        ],
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
        home: ValueListenableBuilder<bool>(
          valueListenable: _onScreen,
          builder: (_, on, _) => on
              ? DivinationScreen(deck: deck)
              : const Scaffold(body: Text('Başka sayfa')),
        ),
      ),
    ),
  );
  if (animations) {
    // The cosmic background never settles; step time instead.
    await tester.pump(const Duration(seconds: 1));
  } else {
    await tester.pumpAndSettle();
  }
  return repo;
}

Finder _slot(int i) => find.byKey(ValueKey('slot-$i'));

/// The order badge number shown on [slot], or null.
String? _badge(WidgetTester tester, int slot) {
  final badge = find.descendant(
    of: _slot(slot),
    matching: find.byWidgetPredicate(
      (w) =>
          w.key is ValueKey<String> &&
          (w.key! as ValueKey<String>).value.startsWith('order-'),
    ),
  );
  if (badge.evaluate().isEmpty) return null;
  return (badge.evaluate().single.widget.key! as ValueKey<String>).value
      .substring('order-'.length);
}

bool _revealEnabled(WidgetTester tester) =>
    tester
        .widget<AstroButton>(find.byKey(const ValueKey('reveal-button')))
        .onPressed !=
    null;

Future<void> _tapSlot(WidgetTester tester, int slot) async {
  await tester.ensureVisible(_slot(slot));
  await tester.pumpAndSettle();
  await tester.tap(_slot(slot));
  await tester.pumpAndSettle();
}

Future<void> _shuffleTo(WidgetTester tester, DeckType deck) async {
  await tester.tap(find.text('Üçlü Açılım'));
  await tester.pumpAndSettle();
  final label = deck == DeckType.rune
      ? 'Rünleri Karıştır'
      : 'Kartları Karıştır';
  await tester.ensureVisible(find.text(label));
  await tester.tap(find.text(label));
  await tester.pumpAndSettle();
}

Future<void> _tapReveal(WidgetTester tester) async {
  await tester.ensureVisible(find.byKey(const ValueKey('reveal-button')));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(const ValueKey('reveal-button')));
}

void main() {
  group('DivinationSelection', () {
    test('keeps pick order and numbers 1..n', () {
      final s = DivinationSelection(required: 3, deckSize: 78);
      for (final slot in [51, 7, 24]) {
        expect(s.toggle(slot), isTrue);
      }
      expect(s.picks, [51, 7, 24]); // never sorted
      expect([s.orderOf(51), s.orderOf(7), s.orderOf(24)], [1, 2, 3]);
      expect(s.isComplete, isTrue);
    });

    test('deselect recomputes the numbering', () {
      final s = DivinationSelection(required: 3, deckSize: 24)
        ..toggle(4)
        ..toggle(9)
        ..toggle(2);
      s.toggle(4); // remove the first pick
      expect(s.picks, [9, 2]);
      expect(s.orderOf(9), 1);
      expect(s.orderOf(2), 2);
      expect(s.orderOf(4), isNull);
      s.toggle(4); // back in, now last
      expect(s.picks, [9, 2, 4]);
      expect(s.orderOf(4), 3);
    });

    test('a full selection ignores new slots; out of range is ignored', () {
      final s = DivinationSelection(required: 2, deckSize: 10)
        ..toggle(1)
        ..toggle(2);
      expect(s.toggle(3), isFalse);
      expect(s.toggle(10), isFalse);
      expect(s.toggle(-1), isFalse);
      expect(s.picks, [1, 2]);
    });

    test('locked selection is immutable', () {
      final s = DivinationSelection(required: 3, deckSize: 65)
        ..toggle(0)
        ..toggle(64)
        ..toggle(32)
        ..lock();
      expect(s.toggle(64), isFalse);
      expect(s.toggle(5), isFalse);
      expect(s.picks, [0, 64, 32]);
    });

    test('consumer refs are fresh and fit the server pattern', () {
      final a = newConsumerRef();
      final b = newConsumerRef();
      expect(a, isNot(b));
      expect(RegExp(r'^[A-Za-z0-9._:-]{8,80}$').hasMatch(a), isTrue);
    });
  });

  for (final deck in DeckType.values) {
    final unit = deck == DeckType.rune ? 'rün' : 'kart';
    final shuffle = deck == DeckType.rune
        ? 'Rünleri Karıştır'
        : 'Kartları Karıştır';
    final reveal = deck == DeckType.rune ? 'Rünleri Aç' : 'Kartları Aç';

    testWidgets('${deck.name}: shuffle, pick in order, reveal', (tester) async {
      final repo = await _pump(tester, deck);

      await tester.tap(find.text('Üçlü Açılım'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text(shuffle));
      await tester.tap(find.text(shuffle));
      await tester.pumpAndSettle();
      expect(repo.createdRefs, hasLength(1));

      // Only face-down slots 0..deck_size-1.
      expect(_slot(0), findsOneWidget);
      expect(_slot(_deckSize(deck) - 1), findsOneWidget);
      expect(_slot(_deckSize(deck)), findsNothing);
      expect(find.text('0 / 3 $unit seçildi'), findsOneWidget);
      expect(_revealEnabled(tester), isFalse);
      expect(
        find.text('1. Geçmiş — seçim bekleniyor', findRichText: true),
        findsOneWidget,
      );

      await _tapSlot(tester, 5);
      await _tapSlot(tester, 1);
      expect(_badge(tester, 5), '1');
      expect(_badge(tester, 1), '2');
      expect(find.text('2 / 3 $unit seçildi'), findsOneWidget);
      expect(find.text('1. Geçmiş', findRichText: true), findsOneWidget);
      expect(find.text('2. Şimdi', findRichText: true), findsOneWidget);
      expect(
        find.text('3. Gidişat — seçim bekleniyor', findRichText: true),
        findsOneWidget,
      );
      expect(_revealEnabled(tester), isFalse);

      // Deselect the first pick: numbering shifts.
      await _tapSlot(tester, 5);
      expect(_badge(tester, 5), isNull);
      expect(_badge(tester, 1), '1');

      await _tapSlot(tester, 9);
      await _tapSlot(tester, 3);
      expect(_badge(tester, 9), '2');
      expect(_badge(tester, 3), '3');

      // Complete: no auto reveal; the CTA waits for the user.
      expect(find.text('Seçimin tamamlandı'), findsOneWidget);
      expect(repo.reveals, isEmpty);
      expect(_revealEnabled(tester), isTrue);

      // A fourth pick is ignored.
      await _tapSlot(tester, 12);
      expect(_badge(tester, 12), isNull);

      await tester.ensureVisible(find.text(reveal));
      await tester.tap(find.text(reveal));
      await tester.pumpAndSettle();
      expect(repo.reveals, [
        [1, 9, 3],
      ]);
      // Revealed in position order.
      expect(find.text('Öğe 1'), findsOneWidget);
      expect(find.text('Öğe 9'), findsOneWidget);
      expect(find.text('Öğe 3'), findsOneWidget);
      expect(
        tester.getTopLeft(find.text('Öğe 1')).dy,
        lessThan(tester.getTopLeft(find.text('Öğe 9')).dy),
      );
      expect(
        tester.getTopLeft(find.text('Öğe 9')).dy,
        lessThan(tester.getTopLeft(find.text('Öğe 3')).dy),
      );
      expect(find.text('Yeniden Açılım Yap'), findsOneWidget);
    });
  }

  testWidgets('selection is frozen once the reveal starts', (tester) async {
    final repo = await _pump(tester, DeckType.tarot);
    await tester.tap(find.text('Üçlü Açılım'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Kartları Karıştır'));
    await tester.tap(find.text('Kartları Karıştır'));
    await tester.pumpAndSettle();
    for (final slot in [2, 0, 4]) {
      await _tapSlot(tester, slot);
    }
    repo.revealGate = Completer<void>();
    await tester.ensureVisible(find.text('Kartları Aç'));
    await tester.tap(find.text('Kartları Aç'));
    await tester.pump();

    // In flight: taps change nothing.
    await tester.tap(_slot(0), warnIfMissed: false);
    await tester.tap(_slot(6), warnIfMissed: false);
    await tester.pump();
    expect(_badge(tester, 0), '2');
    expect(_badge(tester, 6), isNull);

    repo.revealGate!.complete();
    await tester.pumpAndSettle();
    expect(repo.reveals, [
      [2, 0, 4],
    ]);
    expect(_slot(0), findsNothing); // the deck is gone after the reveal

    // "Yeniden Açılım Yap" is a new shuffle with a new ref.
    await tester.ensureVisible(find.text('Yeniden Açılım Yap'));
    await tester.tap(find.text('Yeniden Açılım Yap'));
    await tester.pumpAndSettle();
    expect(repo.createdRefs, hasLength(2));
    expect(repo.createdRefs.toSet(), hasLength(2));
    expect(find.text('0 / 3 kart seçildi'), findsOneWidget);
  });

  testWidgets('with motion: shuffle pause, then 1 -> 2 -> 3 flip', (
    tester,
  ) async {
    final repo = await _pump(
      tester,
      DeckType.rune,
      animations: true,
      precache: (_, _, _, _) async {},
    );
    await tester.tap(find.text('Üçlü Açılım'));
    await tester.pump(const Duration(seconds: 3));
    await tester.ensureVisible(find.text('Rünleri Karıştır'));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Rünleri Karıştır'));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Rünler karıştırılıyor…'), findsWidgets);
    expect(_slot(0), findsNothing); // still shuffling
    await tester.pump(const Duration(seconds: 3));
    expect(_slot(0), findsOneWidget);
    for (final slot in [20, 3, 11]) {
      await tester.tap(_slot(slot));
      await tester.pump(const Duration(milliseconds: 300));
    }
    expect(_badge(tester, 11), '3');
    await tester.ensureVisible(find.text('Rünleri Aç'));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Rünleri Aç'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    // Sequence running: the full reading is not shown yet.
    expect(find.byType(RevealSequence), findsOneWidget);
    expect(find.text('Yeniden Açılım Yap'), findsNothing);
    await tester.pump(const Duration(seconds: 3));
    expect(find.byType(RevealSequence), findsNothing);
    expect(find.text('Yeniden Açılım Yap'), findsOneWidget);
    expect(repo.reveals, [
      [20, 3, 11],
    ]);
  });
  group('route restore', () {
    for (final deck in DeckType.values) {
      testWidgets('${deck.name}: 2/3 survives leaving the route', (
        tester,
      ) async {
        final repo = await _pump(tester, deck);
        await _shuffleTo(tester, deck);
        await _tapSlot(tester, 5);
        await _tapSlot(tester, 1);
        final unit = deck == DeckType.rune ? 'rün' : 'kart';
        expect(find.text('2 / 3 $unit seçildi'), findsOneWidget);

        await _leaveAndReturn(tester);

        // Same session, same slots, same order - nothing new created.
        expect(find.text('2 / 3 $unit seçildi'), findsOneWidget);
        expect(_badge(tester, 5), '1');
        expect(_badge(tester, 1), '2');
        expect(repo.createdRefs, hasLength(1));
        expect(repo.fetched, ['s-${deck.name}']);
        await _tapSlot(tester, 7);
        await _tapReveal(tester);
        await tester.pumpAndSettle();
        expect(repo.reveals, [
          [5, 1, 7],
        ]);
      });
    }

    testWidgets('an expired session restores as expired, never revealable', (
      tester,
    ) async {
      final repo = await _pump(tester, DeckType.tarot);
      await _shuffleTo(tester, DeckType.tarot);
      for (final s in [2, 4, 6]) {
        await _tapSlot(tester, s);
      }
      repo.serverStatus = 'expired';
      await _leaveAndReturn(tester);

      expect(find.byKey(const ValueKey('session-expired')), findsOneWidget);
      expect(find.byKey(const ValueKey('reshuffle-button')), findsOneWidget);
      expect(_revealEnabled(tester), isFalse);
      await tester.ensureVisible(find.byKey(const ValueKey('reveal-button')));
      await tester.tap(
        find.byKey(const ValueKey('reveal-button')),
        warnIfMissed: false,
      );
      await tester.pumpAndSettle();
      expect(repo.reveals, isEmpty);
      // Picks are frozen on an expired session.
      await _tapSlot(tester, 2);
      expect(_badge(tester, 2), '1');
    });

    testWidgets('a revealed session comes back as its reading', (tester) async {
      final repo = await _pump(tester, DeckType.katina);
      await _shuffleTo(tester, DeckType.katina);
      for (final s in [3, 0, 8]) {
        await _tapSlot(tester, s);
      }
      await _tapReveal(tester);
      await tester.pumpAndSettle();
      await _leaveAndReturn(tester);
      expect(_slot(0), findsNothing);
      expect(find.text('Öğe 3'), findsOneWidget);
      expect(find.text('Yeniden Açılım Yap'), findsOneWidget);
      expect(repo.reveals, hasLength(1));
      expect(repo.createdRefs, hasLength(1));
    });

    testWidgets('a 410 on reveal disables the CTA and offers a reshuffle', (
      tester,
    ) async {
      final repo = await _pump(tester, DeckType.rune);
      await _shuffleTo(tester, DeckType.rune);
      for (final s in [1, 2, 3]) {
        await _tapSlot(tester, s);
      }
      repo.revealError = const ApiException(
        kind: ApiErrorKind.unknown,
        statusCode: 410,
        code: 'divination_session_expired',
      );
      await _tapReveal(tester);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('session-expired')), findsOneWidget);
      expect(_revealEnabled(tester), isFalse);
      repo.revealError = null;
      await tester.ensureVisible(
        find.byKey(const ValueKey('reshuffle-button')),
      );
      await tester.tap(find.byKey(const ValueKey('reshuffle-button')));
      await tester.pumpAndSettle();
      expect(repo.createdRefs, hasLength(2));
      expect(find.text('0 / 3 rün seçildi'), findsOneWidget);
    });
  });

  group('accessibility', () {
    testWidgets('reveal CTA, progress and selected slots are real nodes', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      await _pump(tester, DeckType.tarot);
      await _shuffleTo(tester, DeckType.tarot);
      final cta = find.byKey(const ValueKey('reveal-button'));
      expect(
        tester.getSemantics(cta),
        isSemantics(
          label: 'Kartları Aç',
          isButton: true,
          hasEnabledState: true,
          isEnabled: false,
        ),
      );
      expect(
        tester.getSemantics(find.byKey(const ValueKey('selection-progress'))),
        isSemantics(label: '0 / 3 kart seçildi', isLiveRegion: true),
      );
      await _tapSlot(tester, 3);
      expect(
        tester.getSemantics(_slot(3)),
        isSemantics(
          label: 'Kapalı kart 4, 1. seçim',
          isButton: true,
          isSelected: true,
        ),
      );
      expect(
        tester.getSemantics(_slot(9)),
        isSemantics(label: 'Kapalı kart 10', isSelected: false),
      );
      await _tapSlot(tester, 5);
      await _tapSlot(tester, 7);
      expect(
        tester.getSemantics(cta),
        isSemantics(
          label: 'Kartları Aç',
          isButton: true,
          isEnabled: true,
          hasTapAction: true,
        ),
      );
      handle.dispose();
    });

    testWidgets('rune CTA label; shuffle button stays a button', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      await _pump(tester, DeckType.rune);
      await tester.tap(find.text('Üçlü Açılım'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Rünleri Karıştır'));
      await tester.pumpAndSettle();
      expect(
        tester.getSemantics(find.text('Rünleri Karıştır')),
        isSemantics(isButton: true, isEnabled: true, hasTapAction: true),
      );
      await tester.tap(find.text('Rünleri Karıştır'));
      await tester.pumpAndSettle();
      expect(
        tester.getSemantics(find.byKey(const ValueKey('reveal-button'))),
        isSemantics(label: 'Rünleri Aç', isButton: true),
      );
      handle.dispose();
    });
  });

  group('picker visuals', () {
    testWidgets('order badges stay inside the fan clip; picked card on top', (
      tester,
    ) async {
      await _pump(tester, DeckType.tarot);
      await _shuffleTo(tester, DeckType.tarot);
      await _tapSlot(tester, 3);
      final fan = find.descendant(
        of: find.byKey(const ValueKey('fan-fade')),
        matching: find.byType(SingleChildScrollView),
      );
      final clip = tester.getRect(fan);
      final badge = tester.getRect(
        find.descendant(
          of: _slot(3),
          matching: find.byKey(const ValueKey('order-1')),
        ),
      );
      expect(badge.top, greaterThanOrEqualTo(clip.top));

      // The picked card paints above its right-hand neighbour: a tap on
      // their overlap reaches the picked card (deselects it).
      final picked = tester.getRect(_slot(3));
      await tester.tapAt(Offset(picked.right - 6, picked.center.dy));
      await tester.pumpAndSettle();
      expect(_badge(tester, 3), isNull);
      expect(_badge(tester, 4), isNull);

      expect(find.byKey(const ValueKey('scroll-hint')), findsOneWidget);
    });

    testWidgets('runes are whole stones: no clip, no frame, stone art', (
      tester,
    ) async {
      await _pump(tester, DeckType.rune);
      expect(find.text('Taş rün görseli'), findsNothing);
      await _shuffleTo(tester, DeckType.rune);
      final art = tester.widget<AstroImage>(
        find.descendant(of: _slot(0), matching: find.byType(AstroImage)),
      );
      expect(art.asset, 'assets/cards-back/webp/runetas_back.webp');
      expect(art.fit, BoxFit.contain);
      expect(
        find.descendant(of: _slot(0), matching: find.byType(ClipRRect)),
        findsNothing,
      );
      expect(find.byKey(const ValueKey('scroll-hint')), findsNothing);
      for (final s in [1, 2, 3]) {
        await _tapSlot(tester, s);
      }
      await _tapReveal(tester);
      await tester.pumpAndSettle();
      final shown = tester
          .widgetList<AstroImage>(find.byType(AstroImage))
          .map((i) => i.asset)
          .toList();
      expect(shown, contains('assets/rune/stones/fehu.png'));
      expect(shown.where((a) => a.startsWith('assets/rune/cards/')), isEmpty);
    });

    testWidgets('the flip waits until its art is precached', (tester) async {
      final gate = Completer<void>();
      final repo = await _pump(
        tester,
        DeckType.tarot,
        precache: (_, _, _, _) => gate.future,
      );
      await _shuffleTo(tester, DeckType.tarot);
      for (final s in [1, 2, 3]) {
        await _tapSlot(tester, s);
      }
      await _tapReveal(tester);
      await tester.pump(const Duration(seconds: 1));
      expect(repo.reveals, hasLength(1));
      expect(find.byType(RevealSequence), findsNothing);
      expect(find.text('Yeniden Açılım Yap'), findsNothing);
      expect(_slot(1), findsOneWidget); // the deck stays until the art is ready
      gate.complete();
      await tester.pumpAndSettle();
      expect(find.text('Yeniden Açılım Yap'), findsOneWidget);
    });
  });

  testWidgets('daily limit: coins are offered, and paying reshuffles', (
    tester,
  ) async {
    final repo = await _pump(tester, DeckType.tarot, coins: true);
    repo.limitReached = true;
    await tester.tap(find.text('Üçlü Açılım'));
    await tester.pumpAndSettle();
    expect(
      find.text('Bugünkü hakların doldu · ek açılım 10 coin'),
      findsOneWidget,
    );
    await tester.ensureVisible(find.text('Kartları Karıştır'));
    await tester.tap(find.text('Kartları Karıştır'));
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('coin-offer')), findsOneWidget);
    expect(find.text('Bugünkü açılım hakların doldu'), findsOneWidget);
    expect(find.textContaining('Bakiyen: 30 coin'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('coin-offer-pay')));
    await tester.pumpAndSettle();

    expect(repo.paidWithCoins, [false, true]);
    expect(find.text('0 / 3 kart seçildi'), findsOneWidget);
  });

  group('Astro AI deep reading', () {
    const freePlan = EntitlementService(
      catalogue: FeatureCatalogue(
        gatingEnabled: true,
        premiumFeatures: {'advanced_ai'},
        freeSpreads: {},
        premiumTransitRanges: {},
        featureTiers: {'advanced_ai': SubscriptionTier.cosmicPlus},
      ),
      premium: false,
    );

    Future<_FakeRepo> reveal(WidgetTester tester, {int balance = 100}) async {
      final repo = await _pump(
        tester,
        DeckType.tarot,
        coins: true,
        balance: balance,
        entitlements: freePlan,
      );
      await _shuffleTo(tester, DeckType.tarot);
      for (final slot in [1, 2, 3]) {
        await _tapSlot(tester, slot);
      }
      await _tapReveal(tester);
      await tester.pumpAndSettle();
      return repo;
    }

    testWidgets('priced from the catalogue, confirmed, retried on one ref', (
      tester,
    ) async {
      final repo = await reveal(tester);
      final button = find.byKey(const ValueKey('deepen-button'));
      await tester.ensureVisible(button);
      expect(find.text('Astro AI ile Derinleştir · 40 Coin'), findsOneWidget);

      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('coin-confirm')), findsOneWidget);
      expect(find.textContaining('40 AstroCoin'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('coin-confirm-pay')));
      await tester.pumpAndSettle();
      expect(repo.interpretRefs, hasLength(1));
      expect(repo.interpretRefs.single, startsWith('deep-'));

      // A network failure: the retry reuses the same purchase, unasked.
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('coin-confirm')), findsNothing);
      expect(repo.interpretRefs, hasLength(2));
      expect(repo.interpretRefs[1], repo.interpretRefs[0]);
    });

    testWidgets('a short balance sends to the wallet, nothing is sent', (
      tester,
    ) async {
      final repo = await reveal(tester, balance: 10);
      final button = find.byKey(const ValueKey('deepen-button'));
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('coin-insufficient')), findsOneWidget);
      expect(find.text('Yetersiz AstroCoin'), findsOneWidget);
      expect(find.byKey(const ValueKey('coin-go-wallet')), findsOneWidget);
      expect(repo.interpretRefs, isEmpty);
    });

    testWidgets('an including plan shows no price and sends no ref', (
      tester,
    ) async {
      final repo = await _pump(tester, DeckType.tarot, coins: true);
      await _shuffleTo(tester, DeckType.tarot);
      for (final slot in [1, 2, 3]) {
        await _tapSlot(tester, slot);
      }
      await _tapReveal(tester);
      await tester.pumpAndSettle();
      final button = find.byKey(const ValueKey('deepen-button'));
      await tester.ensureVisible(button);
      expect(find.text('Astro AI ile Derinleştir'), findsOneWidget);
      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(repo.interpretRefs, [null]);
    });
  });
}
