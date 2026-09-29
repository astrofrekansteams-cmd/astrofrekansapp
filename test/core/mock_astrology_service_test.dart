import 'package:astrofrekans/core/astrology/data/mock_astrology_service.dart';
import 'package:astrofrekans/core/astrology/domain/birth_data.dart';
import 'package:astrofrekans/core/astrology/domain/daily_frequency.dart';
import 'package:astrofrekans/core/astrology/domain/moon_phase.dart';
import 'package:astrofrekans/core/astrology/domain/natal_chart.dart';
import 'package:astrofrekans/core/astrology/domain/planet.dart';
import 'package:astrofrekans/core/astrology/domain/zodiac_sign.dart';
import 'package:astrofrekans/features/profile/domain/user_profile.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final MockAstrologyService service = MockAstrologyService(
    latency: Duration.zero,
  );

  group('moon phase', () {
    test('identifies a known full moon', () {
      // 2026-03-03 is a full moon (lunar eclipse day).
      final MoonPhase phase = service.computeMoonPhase(
        DateTime.utc(2026, 3, 3, 11),
      );
      expect(phase.type, MoonPhaseType.fullMoon);
      expect(phase.illumination, greaterThan(0.97));
    });

    test('identifies a known new moon', () {
      // 2026-03-19 new moon.
      final MoonPhase phase = service.computeMoonPhase(
        DateTime.utc(2026, 3, 19, 1),
      );
      expect(phase.type, MoonPhaseType.newMoon);
      expect(phase.illumination, lessThan(0.03));
    });

    test('cycle progress stays inside the synodic month', () {
      for (int day = 1; day <= 30; day++) {
        final MoonPhase phase = service.computeMoonPhase(
          DateTime.utc(2026, 4, day),
        );
        expect(phase.cycleProgress, inInclusiveRange(0, 1));
        expect(phase.sign, isNotNull);
      }
    });
  });

  test('natal chart is deterministic and complete', () {
    final BirthData birth = BirthData(
      date: DateTime(1995, 3, 12),
      time: '09:41',
      place: 'İstanbul',
    );
    final NatalChart first = service.buildNatalChart(birth);
    final NatalChart second = service.buildNatalChart(birth);

    expect(first.planets, hasLength(Planet.values.length));
    expect(first.houses, hasLength(12));
    expect(first.ascendant, isNotNull);
    // A 12 March birthday is Pisces.
    expect(first.sunSign, ZodiacSign.pisces);
    expect(first.positionOf(Planet.moon), isNotNull);
    expect(
      second.planets.map((PlanetPosition p) => p.longitude),
      first.planets.map((PlanetPosition p) => p.longitude),
    );
  });

  test('daily frequency is personal, scored and deterministic', () {
    final UserProfile user = UserProfile(
      id: 'u1',
      name: 'Defne',
      email: 'defne@test.dev',
      birthDate: DateTime(1995, 3, 12),
      birthTime: '09:41',
    );
    final DateTime date = DateTime(2026, 3, 12);

    final DailyFrequency a = service.buildDailyFrequency(
      profile: user,
      date: date,
    );
    final DailyFrequency b = service.buildDailyFrequency(
      profile: user,
      date: date,
    );

    expect(a.overallScore, inInclusiveRange(0, 100));
    expect(a.overallScore, b.overallScore);
    expect(a.metrics, hasLength(6));
    expect(a.metric(FrequencyCategory.love), isNotNull);
    expect(a.transits, hasLength(3));
    expect(a.moon, isNotNull);
    expect(a.message?.body, isNotEmpty);
    expect(a.suggestedPrompts, isNotEmpty);

    // A different user gets a different reading: this is not a generic
    // sun-sign horoscope.
    final DailyFrequency other = service.buildDailyFrequency(
      profile: user.copyWith(id: 'u2'),
      date: date,
    );
    expect(other.overallScore, isNot(a.overallScore));
  });
}
