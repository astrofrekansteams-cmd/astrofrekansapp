import 'dart:convert';
import 'dart:io';

import 'package:astrofrekans/core/astrology/data/api_contract_dto.dart';
import 'package:astrofrekans/core/astrology/domain/cosmic_event.dart';
import 'package:astrofrekans/core/astrology/domain/daily_frequency.dart';
import 'package:astrofrekans/core/astrology/domain/planet.dart';
import 'package:astrofrekans/core/astrology/domain/transit.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final Map<String, dynamic> fixture = Map<String, dynamic>.from(
    jsonDecode(
          File('test/fixtures/b1_b4_contract_samples.json').readAsStringSync(),
        )
        as Map,
  );
  Map<String, dynamic> sample(String key) =>
      Map<String, dynamic>.from(fixture[key] as Map);

  test('B4 transit fixture survives DTO to domain, including null windows', () {
    final Map<String, dynamic> json = sample('transits');
    final Map<String, dynamic> original = Map<String, dynamic>.from(
      (json['active'] as List).single as Map,
    );
    original['start_at'] = null;
    original['exact_at'] = null;
    original['end_at'] = null;
    original['status'] = 'exact';
    original['target_type'] = 'natal_angle';
    original['target_body'] = null;
    original['target_angle'] = 'mc';
    original['passes'] = <Map<String, dynamic>>[
      ...((original['passes'] as List).cast<Map<String, dynamic>>()),
      <String, dynamic>{
        'pass_number': 2,
        'exact_at': '2026-10-01T02:40:20Z',
        'direction': 'retrograde',
        'speed': -0.08,
      },
    ];
    json['active'] = <Map<String, dynamic>>[original];
    json['ingresses'] = <Map<String, dynamic>>[
      <String, dynamic>{
        'id': 'ing-1',
        'planet': 'jupiter',
        'from_house': 8,
        'to_house': 9,
        'entered_at': '2026-09-24T02:40:20Z',
        'estimated_exit_at': null,
        'retrograde': false,
        're_entry': false,
      },
    ];
    final TransitWindow window = TransitListDto.fromJson(json).toWindow();
    final Transit result = window.all.single;
    expect(result.startAt, isNull);
    expect(result.exactAt, isNull);
    expect(result.endAt, isNull);
    expect(result.status, TransitStatus.exact);
    expect(result.targetType, TransitTargetType.natalAngle);
    expect(result.targetAngle, ChartAngle.mc);
    expect(result.passes.length, (original['passes'] as List).length);
    expect(result.passes.last.direction, TransitPassDirection.retrograde);
    expect(result.affectedHouses, original['affected_houses']);
    expect(result.windowClipped, original['window_clipped']);
    expect(result.metadata['transiting_house'], 3);
    expect(result.summary.rawNature, 'challenging');
    expect(result.strengthScore, original['strength']);
    expect(window.ingresses.single.toHouse, 9);
    expect(window.range, 'day');

    original['target_type'] = 'house_ingress';
    original['target_angle'] = null;
    original['target_house'] = 9;
    expect(
      TransitDto.fromJson(original).toDomain(timezone: 'UTC').targetType,
      TransitTargetType.houseIngress,
    );
  });

  test('frequency factors, all B4 categories and hours survive', () {
    final Map<String, dynamic> json = sample('daily_frequency');
    final Map<String, dynamic> scores = Map<String, dynamic>.from(
      json['scores'] as Map,
    );
    scores['relationships'] = <String, dynamic>{
      'area': 'relationships',
      'score': 64,
      'trend': 'rising',
      'strength': 55,
      'factor_ids': <String>['f025', 'f026'],
    };
    scores['personal_growth'] = <String, dynamic>{
      'area': 'personal_growth',
      'score': 71,
      'trend': 'steady',
      'strength': 60,
      'factor_ids': <String>['f026'],
    };
    json['scores'] = scores;
    final DailyFrequency result = DailyFrequencyDto.fromJson(json).toDomain();
    expect(result.scores.length, scores.length);
    expect(
      result.scores
          .singleWhere((e) => e.area == LifeArea.relationships)
          .factorIds,
      <String>['f025', 'f026'],
    );
    expect(result.scores.any((e) => e.area == LifeArea.personalGrowth), isTrue);
    expect(result.importantHours.single.factorIds, <String>['f025']);
    expect(result.sourceFactors.single.detail['orb'], 0.12);
    expect(result.messageContext['moon_house'], 6);
  });

  test('calendar phases, stations, ingress and aspect preserve detail', () {
    final Map<String, dynamic> json = sample('calendar');
    final Map<String, dynamic> base = Map<String, dynamic>.from(
      (json['events'] as List).single as Map,
    );
    const List<String> kinds = <String>[
      'first_quarter',
      'last_quarter',
      'station_retrograde',
      'station_direct',
      'ingress',
      'conjunction',
    ];
    json['events'] = <Map<String, dynamic>>[
      for (final String kind in kinds)
        <String, dynamic>{
          ...base,
          'id': kind,
          'type': kind,
          'secondary_planet': 'venus',
          'aspect': 'conjunction',
          'eclipse_subtype': 'partial',
          'metadata': <String, dynamic>{'source': 'b4'},
        },
    ];
    final List<CosmicEvent> result = CosmicCalendarDto.fromJson(
      json,
    ).toDomain();
    expect(result.map((e) => e.type).toList(), <CosmicEventType>[
      CosmicEventType.firstQuarter,
      CosmicEventType.lastQuarter,
      CosmicEventType.stationRetrograde,
      CosmicEventType.stationDirect,
      CosmicEventType.ingress,
      CosmicEventType.conjunction,
    ]);
    expect(result.first.secondaryPlanet?.name, 'venus');
    expect(result.first.aspectType?.name, 'conjunction');
    expect(result.first.eclipseSubtype, 'partial');
    expect(result.first.metadata['source'], 'b4');
  });

  test('natal warnings, rulers and subject metadata survive', () {
    final Map<String, dynamic> json = sample('natal_chart');
    json['warnings'] = <String>['birth_time_unknown'];
    final chart = NatalChartDto.fromJson(json).toDomain();
    expect(chart.warnings, json['warnings']);
    expect(chart.houseRulers[1]?.name, 'mercury');
    expect(chart.planets.first.reportedDegree, 23);
    expect(chart.planets.first.reportedMinute, 55);
    expect(chart.subject?.locationName, 'Istanbul');
    expect(chart.sourceMetadata['big_three'], json['big_three']);
  });

  test(
    'structured forecast scores, periods, factors and solar return survive',
    () {
      final Map<String, dynamic> daily = sample('daily_horoscope');
      daily['areas'] = <Map<String, dynamic>>[
        <String, dynamic>{
          'area': 'relationships',
          'score': 67,
          'trend': 'rising',
          'strength': 60,
          'factor_ids': <String>['factor-1'],
        },
      ];
      daily['source_factors'] = <Map<String, dynamic>>[
        <String, dynamic>{
          'id': 'factor-1',
          'kind': 'transit',
          'label': 'Saturn contact',
          'contribution': 0.2,
          'areas': <String>['relationships'],
          'at': null,
          'detail': <String, dynamic>{'orb': 1.2},
        },
      ];
      daily['key_periods'] = <Map<String, dynamic>>[
        <String, dynamic>{
          'start_at': '2026-09-23T08:00:00Z',
          'end_at': '2026-09-23T12:00:00Z',
          'areas': <String>['relationships'],
          'strength': 60,
          'label': 'supportive',
          'source_factors': <String>['factor-1'],
        },
      ];
      final horoscope = ForecastDto.daily(daily).toHoroscope();
      expect(horoscope.areas.single.factorIds, <String>['factor-1']);
      expect(horoscope.sourceFactors.single.detail['orb'], 1.2);
      expect(horoscope.keyPeriods.single.sourceFactors, <String>['factor-1']);

      final Map<String, dynamic> monthly = sample('monthly_forecast');
      monthly['general_theme'] = <String>['personal_growth'];
      expect(
        ForecastDto.monthly(monthly).toMonthly().generalTheme.single,
        LifeArea.personalGrowth,
      );
      final annual = ForecastDto.annual(sample('annual_forecast')).toAnnual();
      expect(annual.solarReturn?.ascendant, 212.4);
      expect(annual.solarReturn?.sunHouse, 7);
    },
  );
}
