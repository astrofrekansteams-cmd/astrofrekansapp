import 'package:astrofrekans/core/astrology/data/production_models.dart';
import 'package:astrofrekans/core/astrology/data/production_repository.dart';
import 'package:astrofrekans/core/astrology/domain/aspect.dart';
import 'package:astrofrekans/core/astrology/domain/planet.dart';
import 'package:astrofrekans/core/astrology/domain/transit.dart';
import 'package:astrofrekans/core/localization/transit_meaning.dart';
import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/storage/app_preferences.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/features/billing/application/entitlement_service.dart';
import 'package:astrofrekans/features/production/presentation/birth_form.dart';
import 'package:astrofrekans/features/production/presentation/divination_screen.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';

Json readingJson() => {
  'id': 'r1',
  'deck_type': 'tarot',
  'deck_version': 'tarot_v1',
  'spread_code': 'love_three_card',
  'spread_version': 'tarot_love_three_card_v1',
  'spread_name': 'Aşk Üçlemesi',
  'spread_theme': 'love',
  'locale': 'tr',
  'question': 'İlişkim nereye gidiyor?',
  'rng_source': 'system',
  'drawn_at': '2026-09-26T12:00:00Z',
  'status': 'drawn',
  'has_interpretation': false,
  'created_at': '2026-09-26T12:00:00Z',
  'synthesis': {
    'headline': 'Sen konumundaki Aşıklar ile başlayan hikâye...',
    'lines': ['Tüm kartlar düz geldi.'],
    'flow': ['Sen: Aşıklar', 'Diğer Kişi: Kupa İkilisi', 'Aranızdaki: Güneş'],
    'counts': {'cards': 3, 'reversed': 0},
    'version': 'spread_synthesis_v1',
  },
  'items': [
    for (final (i, name, love) in [
      (3, 'Güneş', 'Aşkta açıklık.'),
      (1, 'Aşıklar', 'Değerlerle uyumlu bir seçim.'),
      (2, 'Kupa İkilisi', 'Karşılıklı bağ.'),
    ])
      {
        'draw_order': i,
        'position_index': i,
        'position_key': 'p$i',
        'position_title': ['Sen', 'Diğer Kişi', 'Aranızdaki'][i - 1],
        'position_role': 'role',
        'position_description': 'Açıklama $i',
        'item_id': 'tarot:x:$i',
        'display_name': name,
        'canonical_name': name,
        'orientation': 'upright',
        'image_asset_key': 'missing_asset_$i',
        'keywords': ['anahtar$i'],
        'meaning': 'Genel anlam $i',
        'contextual_meaning': love,
        'shadow_meaning': 'Gölge $i',
        'content_status': 'traditional',
      },
  ],
};

class _FakeProduction extends ProductionRepository {
  _FakeProduction() : super(ApiClient(Dio()));
  @override
  Future<DivinationReading> reading(String id) async =>
      DivinationReading(readingJson());
}

void main() {
  test('reading orders cards by position and exposes synthesis', () {
    final reading = DivinationReading(readingJson());
    expect(reading.items.map((i) => i.name), [
      'Aşıklar',
      'Kupa İkilisi',
      'Güneş',
    ]);
    expect(reading.spreadTheme, 'love');
    expect(reading.synthesis!.flow, hasLength(3));
    expect(
      reading.items.first.contextualMeaning,
      'Değerlerle uyumlu bir seçim.',
    );
  });

  testWidgets('reading view shows positions, meanings and the AI action', (
    tester,
  ) async {
    tester.view.physicalSize =
        const Size(390, 4000) * tester.view.devicePixelRatio;
    addTearDown(tester.view.reset);
    disableAnimations(tester);
    final env = await TestEnv.create();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          appPreferencesProvider.overrideWithValue(env.preferences),
          secureStoreProvider.overrideWithValue(env.store),
          productionRepositoryProvider.overrideWithValue(_FakeProduction()),
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
          home: const DivinationScreen(deck: DeckType.tarot, readingId: 'r1'),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('İlişkim nereye gidiyor?'), findsOneWidget);
    expect(find.text('Açıklama 1'), findsOneWidget);
    expect(find.text('Genel anlam 1'), findsOneWidget);
    expect(find.text('Değerlerle uyumlu bir seçim.'), findsOneWidget);
    expect(find.text('Aşk bağlamında'), findsWidgets);
    expect(find.text('Gölge yönü'), findsWidgets);
    expect(find.text('Birleşik Yorum'), findsOneWidget);
    expect(find.text('Astro AI ile Derinleştir'), findsOneWidget);
  });

  group('transit meaning', () {
    Transit transit(AspectType aspect) => Transit(
      summary: TransitSummary(
        id: 't',
        transitingPlanet: Planet.saturn,
        aspect: aspect,
        natalPlanet: Planet.sun,
      ),
    );

    test('reads the aspect nature deterministically', () {
      expect(
        transitMeaning(transit(AspectType.square), 'tr'),
        contains('baskı'),
      );
      expect(
        transitMeaning(transit(AspectType.trine), 'tr'),
        contains('destekliyor'),
      );
      expect(
        transitMeaning(transit(AspectType.square), 'en'),
        contains('press'),
      );
      expect(
        transitMeaning(transit(AspectType.square), 'tr'),
        transitMeaning(transit(AspectType.square), 'tr'),
      );
    });
  });

  group('birth form helpers', () {
    test('format and parse birth date and time', () {
      expect(formatBirthDate(DateTime(1990, 5, 3)), '1990-05-03');
      expect(formatBirthTime(const TimeOfDay(hour: 9, minute: 5)), '09:05');
      expect(parseBirthTime('14:30:00'), const TimeOfDay(hour: 14, minute: 30));
      expect(parseBirthTime('25:00'), isNull);
      expect(parseBirthTime(null), isNull);
    });

    test('describes coordinates with hemispheres', () {
      expect(
        describeCoordinates(41.0082, 28.9784, 'Europe/Istanbul'),
        '41.01° N, 28.98° E · Europe/Istanbul',
      );
      expect(describeCoordinates(-33.9, -70.6, ''), '33.90° S, 70.60° W');
    });
  });
}
