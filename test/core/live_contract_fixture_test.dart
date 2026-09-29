import 'dart:convert';
import 'dart:io';

import 'package:astrofrekans/core/astrology/data/api_contract_dto.dart';
import 'package:astrofrekans/core/astrology/domain/cosmic_event.dart';
import 'package:flutter_test/flutter_test.dart';

/// A captured, sanitized local backend response. This suite never uses HTTP.
void main() {
  final String raw = File(
    'test/fixtures/live_b1_b4_contract_samples.json',
  ).readAsStringSync();
  final Map<String, dynamic> fixture = Map<String, dynamic>.from(
    jsonDecode(raw) as Map,
  );
  Map<String, dynamic> sample(String key) =>
      Map<String, dynamic>.from(fixture[key] as Map);

  test('capture metadata and sensitive-data gate', () {
    expect(fixture['source'], 'local_live_backend');
    expect(fixture['sanitized'], isTrue);
    expect(DateTime.parse(fixture['captured_at'] as String).isUtc, isTrue);
    expect(fixture['engine_version'], isA<String>());
    expect(
      RegExp(
        r'access_token|refresh_token|password|authorization|'
        r'codex-live-',
        caseSensitive: false,
      ).hasMatch(raw),
      isFalse,
    );
    expect(RegExp(r'"email"\s*:', caseSensitive: false).hasMatch(raw), isFalse);
    expect(raw.contains('C:\\Users\\'), isFalse);
  });

  test('live birth, natal and moon responses parse into domain', () {
    expect(
      BirthProfileDto.fromJson(sample('birth_profile')).toDomain().time,
      '14:30',
    );
    final chart = NatalChartDto.fromJson(sample('natal_chart')).toDomain();
    expect(chart.planets, isNotEmpty);
    expect(chart.houses, isNotEmpty);
    expect(chart.aspects, isNotEmpty);
    expect(chart.houseRulers, isNotEmpty);
    expect(chart.engineVersion, fixture['engine_version']);
    expect(chart.chartKind, 'natal');
    expect(chart.subject, isNotNull);
    expect(
      MoonPhaseDto.fromJson(sample('moon_phase')).toDomain().ageDays,
      isNonNegative,
    );
  });

  test(
    'live day, week and month transit windows parse without date guesses',
    () {
      for (final String range in <String>['day', 'week', 'month']) {
        final Map<String, dynamic> wire = sample('transits_$range');
        final window = TransitListDto.fromJson(wire).toWindow();
        expect(window.range, range);
        expect(window.all, isNotEmpty);
        expect(window.all.every((t) => t.rawStatus != null), isTrue);
        expect(window.all.every((t) => t.strengthScore != null), isTrue);
        expect(window.ingresses.length, (wire['ingresses'] as List).length);
        final List<Map<String, dynamic>> rawTransits = <Map<String, dynamic>>[
          for (final String group in <String>[
            'active',
            'approaching',
            'upcoming',
          ])
            for (final Object? item in wire[group] as List)
              Map<String, dynamic>.from(item as Map),
        ];
        expect(window.all.length, rawTransits.length);
        for (int i = 0; i < rawTransits.length; i++) {
          expect(
            window.all[i].passes.length,
            (rawTransits[i]['passes'] as List).length,
          );
          expect(
            window.all[i].exactAt == null,
            rawTransits[i]['exact_at'] == null,
          );
          expect(
            window.all[i].affectedHouses.length,
            (rawTransits[i]['affected_houses'] as List).length,
          );
        }
      }
    },
  );

  test('live daily frequency and calendar preserve B4 structure', () {
    final frequency = DailyFrequencyDto.fromJson(
      sample('daily_frequency'),
    ).toDomain();
    expect(frequency.scores, hasLength(9));
    expect(frequency.influences, isNotEmpty);
    expect(frequency.engineVersion, isNotEmpty);
    final CosmicCalendarWindow calendar = CosmicCalendarDto.fromJson(
      sample('calendar'),
    ).toWindow();
    expect(calendar.events, isNotEmpty);
    expect(calendar.events.every((e) => e.rawType != null), isTrue);
  });

  test('all four live structured forecast responses parse', () {
    expect(
      ForecastDto.daily(sample('daily_horoscope')).toHoroscope().period,
      'daily',
    );
    expect(
      ForecastDto.daily(sample('weekly_horoscope')).toHoroscope().period,
      'weekly',
    );
    expect(
      ForecastDto.monthly(sample('monthly_forecast')).toMonthly().year,
      isPositive,
    );
    expect(
      ForecastDto.annual(sample('annual_forecast')).toAnnual().year,
      isPositive,
    );
  });

  test('live saved person response parses without fabricated updatedAt', () {
    final person = SavedPersonDto.fromJson(sample('saved_person')).toDomain();
    expect(person.name, 'Disposable Friend');
    expect(person.relationship, 'friend');
    expect(person.createdAt.isUtc, isTrue);
  });
}
