import 'dart:convert';
import 'dart:io';

import 'package:astrofrekans/core/astrology/data/api_contract_dto.dart';
import 'package:astrofrekans/core/localization/astro_labels.dart';
import 'package:astrofrekans/core/localization/b12_copy.dart';
import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/features/production/application/forecast_digest.dart';
import 'package:astrofrekans/features/production/presentation/forecast_reading_view.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';

import '../helpers/test_harness.dart';

/// Real `/horoscope/daily`, `/forecasts/monthly` and `/forecasts/yearly`
/// answers from the local API.
final Map<String, dynamic> _samples =
    jsonDecode(
          File('test/fixtures/forecast_live_samples.json').readAsStringSync(),
        )
        as Map<String, dynamic>;

Object _forecast(String period) => switch (period) {
  'daily' => ForecastDto.daily(
    _samples['daily'] as Map<String, dynamic>,
  ).toHoroscope(),
  'monthly' => ForecastDto.monthly(
    _samples['monthly'] as Map<String, dynamic>,
  ).toMonthly(),
  _ => ForecastDto.annual(
    _samples['yearly'] as Map<String, dynamic>,
  ).toAnnual(),
};

/// Anything the reader must never see: engine ids, snake_case keys, the
/// engine's English labels.
final _raw = RegExp(
  r'[0-9a-f]{16,}|[a-z]+_[a-z_]+|\b(trine|square|sextile|opposition|conjunction)\b|engine|scoring',
);

void main() {
  setUpAll(() => initializeDateFormatting('tr'));

  for (final period in ['daily', 'monthly', 'yearly']) {
    testWidgets('$period: readable sections, no internal keys', (tester) async {
      tester.view.physicalSize =
          const Size(390, 6000) * tester.view.devicePixelRatio;
      addTearDown(tester.view.reset);
      disableAnimations(tester);
      late ForecastDigest digest;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.dark,
          locale: const Locale('tr'),
          supportedLocales: AppLocalizations.supportedLocales,
          localizationsDelegates: const [
            AppLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          home: Scaffold(
            body: SingleChildScrollView(
              child: Builder(
                builder: (context) {
                  final l10n = AppLocalizations.of(context);
                  digest = ForecastDigest.of(
                    _forecast(period),
                    ForecastWords(
                      language: 'tr',
                      copy: (key) => b12(context, key),
                      planet: l10n.planet,
                      sign: l10n.sign,
                      aspect: l10n.aspect,
                    ),
                  )!;
                  return ForecastReadingView(digest: digest, period: period);
                },
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      for (final title in [
        'Genel Enerji',
        'Aşk ve İlişkiler',
        'Kariyer',
        'Para',
        'Duygusal Durum',
        'Önemli Tarihler',
        'Bu yorumu oluşturan etkiler',
      ]) {
        expect(find.text(title), findsOneWidget, reason: '$period $title');
      }
      // Named in the chart's calendar, not shifted a day by the UTC bounds.
      expect(
        find.text(switch (period) {
          'daily' => '27 Eylül 2026, Pazar',
          'monthly' => 'Eylül 2026',
          _ => '2026',
        }),
        findsOneWidget,
      );
      expect(digest.supports, isNotEmpty);
      expect(digest.cautions, isNotEmpty);
      expect(find.text('Dikkat Edilecek Konular'), findsOneWidget);
      expect(find.text('Destekleyici Etkiler'), findsOneWidget);
      expect(digest.dates, isNotEmpty);

      // Open the influences and read every string on screen.
      await tester.tap(find.text('Bu yorumu oluşturan etkiler'));
      await tester.pumpAndSettle();
      final shown = [
        for (final t in tester.widgetList<Text>(find.byType(Text)))
          t.data ?? t.textSpan?.toPlainText() ?? '',
      ];
      for (final text in shown) {
        expect(_raw.hasMatch(text), isFalse, reason: '$period shows "$text"');
      }
      // Explanations are sentences.
      for (final line in [...digest.supports, ...digest.cautions]) {
        final meaning = line.meaning;
        if (meaning == null) continue;
        expect(meaning[0], meaning[0].toUpperCase(), reason: meaning);
      }
      // Influences read as Turkish astrology, not as engine labels.
      expect(
        shown.any((t) => t.contains('natal') && t.contains(' – ')),
        isTrue,
      );
      expect(tester.takeException(), isNull);
    });
  }

  test('an influence label reads in Turkish', () {
    final influence = Influence.parse('mercury conjunction asc')!;
    expect(influence.angle, 'asc');
    expect(Influence.parse('moon_enters_house_8'), isNull);
    expect(
      Influence.parse('saturn sextile north_node')!.target?.name,
      'northNode',
    );
  });
}
