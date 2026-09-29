import 'dart:convert';
import 'dart:io';

import 'package:astrofrekans/core/astrology/data/api_contract_dto.dart';
import 'package:astrofrekans/core/astrology/domain/cosmic_event.dart';
import 'package:astrofrekans/core/astrology/domain/natal_chart.dart';
import 'package:astrofrekans/core/astrology/domain/transit.dart';
import 'package:astrofrekans/core/astrology/domain/daily_frequency.dart';
import 'package:astrofrekans/features/auth/data/auth_dto.dart';
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

  test('auth, user, birth profile and saved person parse', () {
    expect(AuthTokenDto.fromJson(sample('auth')).accessToken, 'fixture-access');
    final BirthProfileDto birth = BirthProfileDto.fromJson(
      sample('birth_profile'),
    );
    expect(birth.toDomain().time, '14:30');
    expect(
      UserDto.fromJson(sample('user')).toDomain(birth: birth).hasBirthData,
      isTrue,
    );
    final saved = SavedPersonDto.fromJson(sample('saved_person')).toDomain();
    expect(saved.relationship, 'friend');
    expect(saved.birthTimeKnown, isFalse);
    expect(saved.createdAt.year, 2026);
  });

  test('natal chart maps snake_case house and planet enums', () {
    final chart = NatalChartDto.fromJson(sample('natal_chart')).toDomain();
    expect(chart.houseSystem, HouseSystem.wholeSign);
    expect(chart.planets.length, 2);
    expect(chart.planets.last.planet.name, 'northNode');
    expect(chart.isMock, isFalse);
    expect(chart.houseRulers[1]?.name, 'mercury');
    expect(chart.engineVersion, '1.0.0-de421');
  });

  test('transits map exact status and retain source DTO structure', () {
    final Map<String, dynamic> json = sample('transits');
    final dto = TransitListDto.fromJson(json);
    expect(dto.toDomain().first.status, TransitStatus.approaching);
    final Map<String, dynamic> exact = Map<String, dynamic>.from(
      (json['active'] as List).first as Map,
    );
    exact['status'] = 'exact';
    expect(
      TransitDto.fromJson(exact).toDomain(timezone: 'Europe/Istanbul').status,
      TransitStatus.exact,
    );
    exact['exact_at'] = null;
    exact['start_at'] = null;
    exact['end_at'] = null;
    final Transit open = TransitDto.fromJson(exact).toDomain(timezone: 'UTC');
    expect(open.exactAt, isNull);
    expect(open.startAt, isNull);
    expect(open.endAt, isNull);
    expect(open.passes.single.number, 1);
    expect(open.affectedHouses, <int>[3, 9]);
    exact['status'] = 'future_status';
    final Transit unknown = TransitDto.fromJson(
      exact,
    ).toDomain(timezone: 'UTC');
    expect(unknown.status, TransitStatus.unknown);
    expect(unknown.rawStatus, 'future_status');
  });

  test('daily frequency, moon phase, calendar and forecasts parse', () {
    final daily = DailyFrequencyDto.fromJson(
      sample('daily_frequency'),
    ).toDomain();
    expect(daily.overallScore, 36);
    expect(daily.scores.first.factorIds, <String>['f025']);
    expect(daily.importantHours.single.factorIds, <String>['f025']);
    expect(daily.influences.single.id, 'f025');
    expect(daily.metric(FrequencyCategory.love)?.score, 40);
    final moon = MoonPhaseDto.fromJson(sample('moon_phase')).toDomain();
    expect(moon.type.name, 'waxingGibbous');
    expect(moon.ageDays, 11.062);
    expect(moon.cycleProgress, isNull);
    expect(
      CosmicCalendarDto.fromJson(sample('calendar')).toDomain().first.type,
      CosmicEventType.fullMoon,
    );
    expect(
      ForecastDto.daily(sample('daily_horoscope')).toHoroscope().period,
      'daily',
    );
    expect(
      ForecastDto.daily(sample('weekly_horoscope')).toHoroscope().period,
      'weekly',
    );
    expect(
      ForecastDto.monthly(sample('monthly_forecast')).toMonthly().month,
      10,
    );
    expect(
      ForecastDto.annual(
        sample('annual_forecast'),
      ).toAnnual().solarReturn?.sunHouse,
      7,
    );
  });

  test('backend calendar enum is represented without false fallback', () {
    final Map<String, dynamic> calendar = sample('calendar');
    final Map<String, dynamic> event = Map<String, dynamic>.from(
      (calendar['events'] as List).first as Map,
    );
    event['type'] = 'first_quarter';
    calendar['events'] = <Map<String, dynamic>>[event];
    expect(CosmicCalendarDto.fromJson(calendar).json['events'], hasLength(1));
    expect(
      CosmicCalendarDto.fromJson(calendar).toDomain().single.type,
      CosmicEventType.firstQuarter,
    );
    event['type'] = 'unreleased_event';
    expect(
      CosmicCalendarDto.fromJson(calendar).toDomain().single.type,
      CosmicEventType.unknown,
    );
    expect(
      CosmicCalendarDto.fromJson(calendar).toDomain().single.rawType,
      'unreleased_event',
    );
  });
}
