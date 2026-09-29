import 'dart:math' as math;

import '../../../features/profile/domain/user_profile.dart';
import '../astrology_service.dart';
import '../domain/aspect.dart';
import '../domain/astro_ai_context.dart';
import '../domain/birth_data.dart';
import '../domain/cosmic_event.dart';
import '../domain/daily_frequency.dart';
import '../domain/moon_phase.dart';
import '../domain/natal_chart.dart';
import '../domain/planet.dart';
import '../domain/synastry_result.dart';
import '../domain/transit.dart';
import '../domain/zodiac_sign.dart';
import 'mock_content.dart';

/// Deterministic stand-in for the real astrology engine.
///
/// What is real here: the Moon phase and the Moon's zodiac sign are computed
/// from standard low-precision lunar formulas, so they track the actual sky
/// within roughly a degree.
///
/// What is NOT real: planetary positions, houses, aspects, transit windows and
/// scores are deterministic pseudo-data seeded by the user and the date. They
/// look stable and plausible but they are not an ephemeris. Every screen that
/// shows them also surfaces the demo notice - we never present mock output as a
/// real reading.
class MockAstrologyService implements AstrologyService {
  MockAstrologyService({
    this.latency = const Duration(milliseconds: 320),
    String languageCode = 'tr',
  }) : _content = MockContent.forLanguage(languageCode);

  final Duration latency;
  final MockContent _content;

  Future<T> _delayed<T>(T value) async {
    if (latency > Duration.zero) await Future<void>.delayed(latency);
    return value;
  }

  // ---------------------------------------------------------------- natal

  @override
  Future<NatalChart> getNatalChart(BirthData birthData) =>
      _delayed(buildNatalChart(birthData));

  /// Synchronous so widgets/tests can build a chart without awaiting.
  NatalChart buildNatalChart(BirthData birthData) {
    final int seed = _seedFor(birthData);
    final math.Random random = math.Random(seed);
    final List<PlanetPosition> planets = <PlanetPosition>[];

    for (final Planet planet in Planet.values) {
      final double longitude = switch (planet) {
        // The Sun's sign is the one thing users check first, so at least put it
        // in the right sign for the birth date.
        Planet.sun => _sunLongitude(birthData.date),
        Planet.moon => _moonLongitude(birthData.date),
        _ => random.nextDouble() * 360,
      };
      planets.add(
        PlanetPosition(
          planet: planet,
          sign: ZodiacSign.fromLongitude(longitude),
          longitude: longitude,
          house: birthData.hasExactTime ? random.nextInt(12) + 1 : null,
          isRetrograde: !planet.isPersonal && random.nextDouble() < 0.28,
        ),
      );
    }

    final List<HousePosition> houses = birthData.hasExactTime
        ? List<HousePosition>.generate(12, (int index) {
            final double cusp = (seed % 360 + index * 30) % 360;
            return HousePosition(
              number: index + 1,
              sign: ZodiacSign.fromLongitude(cusp),
              cuspLongitude: cusp,
            );
          })
        : const <HousePosition>[];

    final List<NatalAspect> aspects = <NatalAspect>[];
    for (int i = 0; i < planets.length; i++) {
      for (int j = i + 1; j < planets.length; j++) {
        final double separation = _angularDistance(
          planets[i].longitude,
          planets[j].longitude,
        );
        for (final AspectType type in AspectType.values) {
          final double orb = (separation - type.angle).abs();
          if (orb <= 6) {
            aspects.add(
              NatalAspect(
                first: planets[i].planet,
                second: planets[j].planet,
                type: type,
                orb: double.parse(orb.toStringAsFixed(2)),
              ),
            );
            break;
          }
        }
      }
    }

    return NatalChart(
      birthData: birthData,
      planets: planets,
      houses: houses,
      aspects: aspects,
      ascendant: birthData.hasExactTime ? ZodiacSign.values[seed % 12] : null,
      midheaven: birthData.hasExactTime
          ? ZodiacSign.values[(seed + 9) % 12]
          : null,
      ascendantLongitude: birthData.hasExactTime
          ? (seed % 12) * 30 + (seed % 30)
          : null,
      midheavenLongitude: birthData.hasExactTime
          ? ((seed + 9) % 12) * 30 + (seed % 30)
          : null,
      houseSystem: HouseSystem.equal,
      isMock: true,
    );
  }

  // ------------------------------------------------------------- transits

  @override
  Future<List<Transit>> getTransits({
    required NatalChart natalChart,
    required DateTime from,
    DateTime? to,
  }) => _delayed(buildTransits(natalChart: natalChart, date: from));

  List<Transit> buildTransits({
    required NatalChart natalChart,
    required DateTime date,
  }) {
    final int seed = _dateSeed(date) + _seedFor(natalChart.birthData);
    final math.Random random = math.Random(seed);
    final DateTime day = DateTime(date.year, date.month, date.day);

    final List<TransitSummary> summaries = _content.transitSummaries(
      random: random,
      moonHouse: random.nextInt(12) + 1,
    );

    return <Transit>[
      for (int i = 0; i < summaries.length; i++)
        Transit(
          summary: summaries[i],
          startAt: day.subtract(Duration(days: 2 + random.nextInt(3))).toUtc(),
          exactAt: day.add(Duration(hours: 6 + random.nextInt(12))).toUtc(),
          endAt: day.add(Duration(days: 1 + random.nextInt(4))).toUtc(),
          status: i == 2 ? TransitStatus.approaching : TransitStatus.active,
          orb: double.parse((random.nextDouble() * 3).toStringAsFixed(2)),
          strength: 0.9 - i * 0.15,
          interpretation: summaries[i].headline,
        ),
    ];
  }

  // ------------------------------------------------------- daily frequency

  @override
  Future<DailyFrequency> getDailyFrequency({
    required UserProfile profile,
    required DateTime date,
  }) => _delayed(buildDailyFrequency(profile: profile, date: date));

  DailyFrequency buildDailyFrequency({
    required UserProfile profile,
    required DateTime date,
  }) {
    final int seed = _dateSeed(date) ^ profile.id.hashCode;
    final math.Random random = math.Random(seed);
    final NatalChart chart = buildNatalChart(
      profile.birthData ?? BirthData(date: DateTime(1995, 3, 12)),
    );
    final List<Transit> transits = buildTransits(natalChart: chart, date: date);

    int score(int floor) => floor + random.nextInt(100 - floor);

    final List<FrequencyMetric> metrics = <FrequencyMetric>[
      FrequencyMetric(category: FrequencyCategory.love, score: score(55)),
      FrequencyMetric(category: FrequencyCategory.career, score: score(55)),
      FrequencyMetric(category: FrequencyCategory.money, score: score(45)),
      FrequencyMetric(category: FrequencyCategory.mood, score: score(50)),
      FrequencyMetric(
        category: FrequencyCategory.generalEnergy,
        score: score(50),
      ),
      FrequencyMetric(category: FrequencyCategory.luck, score: score(40)),
    ];

    final int overall =
        (metrics.fold<int>(0, (int sum, FrequencyMetric m) => sum + m.score) /
                metrics.length)
            .round();

    final MoonPhase moon = computeMoonPhase(date);

    return DailyFrequency(
      date: date,
      overallScore: overall,
      metrics: metrics,
      transits: <TransitSummary>[
        for (final Transit transit in transits) transit.summary,
      ],
      moon: MoonPhaseSummary(
        type: moon.type,
        sign: moon.sign,
        message: _content.moonMessage(moon.type),
      ),
      message: QuickInsight(
        id: 'day-${date.toIso8601String().substring(0, 10)}',
        title: _content.levelTitle(overall),
        body: _content.dayMessage(overall),
      ),
      suggestedPrompts: _content.suggestedPrompts,
    );
  }

  // ------------------------------------------------------------ moon phase

  @override
  Future<MoonPhase> getMoonPhase({
    required DateTime date,
    NatalChart? natalChart,
  }) => _delayed(computeMoonPhase(date));

  /// Low-precision but *real* lunar maths (Meeus, simplified):
  /// phase from the synodic cycle, sign from the Moon's mean longitude.
  MoonPhase computeMoonPhase(DateTime date) {
    final DateTime utc = date.toUtc();
    final double daysSinceEpoch =
        utc.difference(DateTime.utc(2000, 1, 6, 18, 14)).inMinutes / 1440.0;
    const double synodicMonth = 29.530588853;
    double progress = (daysSinceEpoch / synodicMonth) % 1;
    if (progress < 0) progress += 1;

    final double illumination = (1 - math.cos(2 * math.pi * progress)) / 2;
    final MoonPhaseType type = switch (progress) {
      < 0.0335 || >= 0.9665 => MoonPhaseType.newMoon,
      < 0.2165 => MoonPhaseType.waxingCrescent,
      < 0.2835 => MoonPhaseType.firstQuarter,
      < 0.4665 => MoonPhaseType.waxingGibbous,
      < 0.5335 => MoonPhaseType.fullMoon,
      < 0.7165 => MoonPhaseType.waningGibbous,
      < 0.7835 => MoonPhaseType.lastQuarter,
      _ => MoonPhaseType.waningCrescent,
    };

    final double longitude = _moonLongitude(date);
    return MoonPhase(
      date: date,
      type: type,
      illumination: double.parse(illumination.toStringAsFixed(3)),
      cycleProgress: double.parse(progress.toStringAsFixed(4)),
      sign: ZodiacSign.fromLongitude(longitude),
      message: _content.moonMessage(type),
    );
  }

  // -------------------------------------------------------------- calendar

  @override
  Future<List<CosmicEvent>> getCosmicCalendar({
    required DateTime from,
    required DateTime to,
    NatalChart? natalChart,
  }) async {
    final List<CosmicEvent> events = <CosmicEvent>[];
    DateTime cursor = DateTime(from.year, from.month, from.day);
    while (!cursor.isAfter(to)) {
      final MoonPhase phase = computeMoonPhase(cursor);
      if (phase.type == MoonPhaseType.newMoon ||
          phase.type == MoonPhaseType.fullMoon) {
        events.add(
          CosmicEvent(
            id: 'moon-${cursor.toIso8601String().substring(0, 10)}',
            type: phase.type == MoonPhaseType.newMoon
                ? CosmicEventType.newMoon
                : CosmicEventType.fullMoon,
            exactAt: cursor.toUtc(),
            moonPhase: phase.type,
            sign: phase.sign,
            planet: Planet.moon,
            description: _content.moonMessage(phase.type),
            isPersonal: natalChart != null,
          ),
        );
      }
      cursor = cursor.add(const Duration(days: 1));
    }
    return _delayed(events);
  }

  // -------------------------------------------------------------- synastry

  @override
  Future<SynastryResult> getSynastry({
    required BirthData personA,
    required BirthData personB,
    CompatibilityMode mode = CompatibilityMode.synastry,
  }) async {
    final math.Random random = math.Random(
      _seedFor(personA) ^ _seedFor(personB),
    );
    return _delayed(
      SynastryResult(
        mode: mode,
        scores: <CompatibilityScore>[
          for (final CompatibilityArea area in CompatibilityArea.values)
            CompatibilityScore(area: area, score: 45 + random.nextInt(50)),
        ],
      ),
    );
  }

  // ------------------------------------------------------------ ai context

  @override
  Future<AstroAIContext> getAstroAIContext({
    required UserProfile profile,
    DateTime? at,
  }) async {
    final DateTime moment = at ?? DateTime.now();
    final NatalChart chart = buildNatalChart(
      profile.birthData ?? BirthData(date: DateTime(1995, 3, 12)),
    );
    return _delayed(
      AstroAIContext(
        natalChart: chart,
        activeTransits: buildTransits(natalChart: chart, date: moment),
        moon: computeMoonPhase(moment),
        generatedAt: moment,
      ),
    );
  }

  // ----------------------------------------------------------------- maths

  static int _seedFor(BirthData data) =>
      data.date.millisecondsSinceEpoch ~/ 86400000 ^
      (data.place?.hashCode ?? 7);

  static int _dateSeed(DateTime date) =>
      date.year * 10000 + date.month * 100 + date.day;

  /// Mean solar longitude - accurate enough to land in the right sign.
  static double _sunLongitude(DateTime date) {
    final double d = _daysSinceJ2000(date);
    final double meanLongitude = 280.460 + 0.9856474 * d;
    final double meanAnomaly = (357.528 + 0.9856003 * d) * math.pi / 180;
    final double ecliptic =
        meanLongitude +
        1.915 * math.sin(meanAnomaly) +
        0.020 * math.sin(2 * meanAnomaly);
    return ecliptic % 360;
  }

  /// Mean lunar longitude (within ~5 degrees of the true position).
  static double _moonLongitude(DateTime date) {
    final double d = _daysSinceJ2000(date);
    final double meanLongitude = 218.316 + 13.176396 * d;
    final double meanAnomaly = (134.963 + 13.064993 * d) * math.pi / 180;
    return (meanLongitude + 6.289 * math.sin(meanAnomaly)) % 360;
  }

  static double _daysSinceJ2000(DateTime date) =>
      date.toUtc().difference(DateTime.utc(2000, 1, 1, 12)).inMinutes / 1440.0;

  static double _angularDistance(double a, double b) {
    final double diff = (a - b).abs() % 360;
    return diff > 180 ? 360 - diff : diff;
  }
}
