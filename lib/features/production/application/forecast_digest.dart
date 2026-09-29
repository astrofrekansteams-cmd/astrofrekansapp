import '../../../core/astrology/domain/aspect.dart';
import '../../../core/astrology/domain/cosmic_event.dart';
import '../../../core/astrology/domain/daily_frequency.dart';
import '../../../core/astrology/domain/forecast.dart';
import '../../../core/astrology/domain/house_ingress.dart';
import '../../../core/astrology/domain/planet.dart';
import '../../../core/astrology/domain/zodiac_sign.dart';
import '../../../core/localization/transit_meaning.dart';
import '../../../core/utils/text_case.dart';

/// A readable account of a daily, weekly, monthly or yearly forecast.
///
/// Presentation only: every score, date and influence comes from the
/// deterministic engine, and every sentence is a fixed template over them.
/// Nothing here computes astrology, and no internal id reaches the reader.
class ForecastDigest {
  const ForecastDigest({
    required this.score,
    required this.tone,
    required this.startAt,
    required this.endAt,
    required this.areas,
    required this.highlights,
    required this.dates,
    required this.supports,
    required this.cautions,
    required this.influences,
  });

  final int score;
  final ForecastTone tone;
  final DateTime startAt;
  final DateTime endAt;

  /// Genel Enerji, Aşk ve İlişkiler, Kariyer, Para, Duygusal Durum.
  final List<AreaReading> areas;

  /// Period-wide notes: the month's themes, the solar return.
  final List<String> highlights;
  final List<DatedLine> dates;
  final List<InfluenceLine> supports;
  final List<InfluenceLine> cautions;

  /// "Bu yorumu oluşturan etkiler": the engine's factors, readable.
  final List<InfluenceLine> influences;

  /// Builds the digest of any forecast the API returns; null for anything
  /// else.
  static ForecastDigest? of(Object forecast, ForecastWords words) =>
      switch (forecast) {
        final HoroscopeForecast f => _Builder(words, f.sourceFactors).build(
          score: f.overallScore,
          startAt: f.startAt,
          endAt: f.endAt,
          areas: f.areas,
          opportunities: f.opportunities,
          challenges: f.challenges,
          importantDates: f.importantDates,
          keyPeriods: f.keyPeriods,
          events: f.moonEvents,
          hours: f.importantHours,
          dateLimit: 6,
        ),
        final MonthlyForecast f => _Builder(words, f.sourceFactors).build(
          score: f.overall,
          startAt: f.startAt,
          endAt: f.endAt,
          areas: f.areas,
          opportunities: f.opportunities,
          challenges: f.challenges,
          importantDates: f.importantDates,
          keyPeriods: f.keyPeriods,
          events: f.moonEvents,
          retrogrades: f.retrogrades,
          themes: f.generalTheme,
          dateLimit: 10,
        ),
        final AnnualForecast f => _Builder(words, f.sourceFactors).build(
          score: f.overall,
          startAt: f.startAt,
          endAt: f.endAt,
          areas: f.areas,
          opportunities: const [],
          challenges: const [],
          importantDates: f.importantDates,
          keyPeriods: f.keyPeriods,
          events: f.eclipses,
          retrogrades: f.retrogradePeriods,
          growth: f.jupiterMovements,
          structure: f.saturnMovements,
          solarReturn: f.solarReturn,
          dateLimit: 12,
        ),
        _ => null,
      };
}

enum ForecastTone { strong, balanced, demanding }

ForecastTone toneOf(int score) => score >= 67
    ? ForecastTone.strong
    : score >= 45
    ? ForecastTone.balanced
    : ForecastTone.demanding;

class AreaReading {
  const AreaReading({
    required this.key,
    required this.score,
    required this.trend,
    required this.summary,
    this.support,
    this.caution,
  });

  /// general_energy, love, career, money or mood.
  final String key;
  final int score;
  final ScoreTrend trend;
  final String summary;
  final InfluenceLine? support;
  final InfluenceLine? caution;
}

class DatedLine {
  const DatedLine({
    required this.at,
    required this.title,
    this.until,
    this.note,
    this.supportive,
    this.withTime = false,
  });
  final DateTime at;
  final DateTime? until;
  final String title;
  final String? note;

  /// True = opportunity, false = take care, null = neither.
  final bool? supportive;
  final bool withTime;
}

class InfluenceLine {
  const InfluenceLine({
    required this.title,
    required this.supportive,
    this.meaning,
    this.weight = 0,
    this.at,
  });
  final String title;
  final String? meaning;
  final bool supportive;

  /// 0-100: how much it moves the scores.
  final int weight;
  final DateTime? at;
}

/// The words a digest needs, resolved by the caller from the app's l10n.
class ForecastWords {
  const ForecastWords({
    required this.language,
    required this.copy,
    required this.planet,
    required this.sign,
    required this.aspect,
  });
  final String language;

  /// A TR/EN copy key lookup (`b12`).
  final String Function(String key) copy;
  final String Function(Planet planet) planet;
  final String Function(ZodiacSign sign) sign;
  final String Function(AspectType aspect) aspect;

  String area(LifeArea area) => copy('fc_area_${lifeAreaWire(area)}');
}

String lifeAreaWire(LifeArea area) => switch (area) {
  LifeArea.generalEnergy => 'general_energy',
  LifeArea.healthBalance => 'health_balance',
  LifeArea.personalGrowth => 'personal_growth',
  _ => area.name,
};

/// A moving planet in aspect to a natal planet or chart angle, as the engine
/// labels it ("sun trine moon", "mercury conjunction asc").
class Influence {
  const Influence(this.moving, this.aspect, {this.target, this.angle});
  final Planet moving;
  final AspectType aspect;
  final Planet? target;
  final String? angle;

  static const angles = {'asc', 'mc', 'dsc', 'ic'};

  static Influence? parse(String label) {
    final parts = label.trim().split(RegExp(r'\s+'));
    if (parts.length != 3) return null;
    return from(parts[0], parts[1], parts[2]);
  }

  static Influence? from(Object? moving, Object? aspect, Object? target) {
    final m = planetFromWire(moving);
    final a = aspectFromWire(aspect);
    if (m == null || a == null) return null;
    final t = planetFromWire(target);
    final angle = angles.contains(target) ? target! as String : null;
    if (t == null && angle == null) return null;
    return Influence(m, a, target: t, angle: angle);
  }

  String title(ForecastWords words) {
    final target = this.target != null
        ? '${words.copy('fc_natal')} ${words.planet(this.target!)}'
        : words.copy('fc_angle_$angle');
    return '${words.planet(moving)} – $target · ${words.aspect(aspect)}';
  }

  String? meaning(ForecastWords words) => influenceMeaning(
    moving: moving,
    aspect: aspect,
    targetPlanet: target,
    targetAngle: angle,
    language: words.language,
  );

  bool get supportive => aspect.nature != AspectNature.hard;
}

Planet? planetFromWire(Object? code) =>
    Planet.values.where((p) => p.assetKey == code).firstOrNull;

AspectType? aspectFromWire(Object? code) =>
    AspectType.values.where((a) => a.name == code).firstOrNull;

ZodiacSign? signFromWire(Object? code) =>
    ZodiacSign.values.where((s) => s.name == code).firstOrNull;

class _Builder {
  _Builder(this.words, List<SourceFactor> factors)
    : _factors = {for (final f in factors) f.id: f},
      _all = factors;

  final ForecastWords words;
  final Map<String, SourceFactor> _factors;
  final List<SourceFactor> _all;

  String _t(String key) => words.copy(key);

  ForecastDigest build({
    required int score,
    required DateTime startAt,
    required DateTime endAt,
    required List<AreaScore> areas,
    required List<String> opportunities,
    required List<String> challenges,
    required List<ForecastImportantDate> importantDates,
    required List<ForecastPeriod> keyPeriods,
    required List<CosmicEvent> events,
    List<ImportantHour> hours = const [],
    List<CosmicEvent> retrogrades = const [],
    List<LifeArea> themes = const [],
    List<HouseIngress> growth = const [],
    List<HouseIngress> structure = const [],
    SolarReturnSummary? solarReturn,
    required int dateLimit,
  }) {
    final supports = <InfluenceLine>[
      ..._labelled(opportunities),
      for (final m in growth) ?_movement(m, supportive: true),
    ];
    final cautions = <InfluenceLine>[
      ..._labelled(challenges).take(3),
      for (final r in retrogrades.take(2)) ?_retrograde(r),
      for (final m in structure) ?_movement(m, supportive: false),
    ];
    // A period without labelled lists reads its strongest factors instead.
    final described = [for (final f in _all) ?_describe(f)]
      ..sort((a, b) => b.weight.compareTo(a.weight));
    if (opportunities.isEmpty) {
      supports.addAll(described.where((f) => f.supportive).take(4));
    }
    if (challenges.isEmpty) {
      cautions.addAll(described.where((f) => !f.supportive).take(4));
    }

    return ForecastDigest(
      score: score,
      tone: toneOf(score),
      startAt: startAt,
      endAt: endAt,
      areas: _areas(areas),
      highlights: [
        if (themes.isNotEmpty)
          _t(
            'fc_month_themes',
          ).replaceAll('{themes}', themes.map(words.area).join(', ')),
        if (solarReturn != null) ?_solarReturn(solarReturn),
      ],
      dates: _dates(
        importantDates,
        keyPeriods,
        events,
        hours,
      ).take(dateLimit).toList(growable: false),
      supports: _unique(supports).take(5).toList(growable: false),
      cautions: _unique(cautions).take(5).toList(growable: false),
      influences: described.take(15).toList(growable: false),
    );
  }

  // ------------------------------------------------------------------ areas

  static const _groups = <String, Set<LifeArea>>{
    'general_energy': {LifeArea.generalEnergy},
    'love': {LifeArea.love, LifeArea.relationships},
    'career': {LifeArea.career},
    'money': {LifeArea.money},
    'mood': {LifeArea.mood},
  };

  List<AreaReading> _areas(List<AreaScore> scores) {
    // Each card names its own influences where it can: one already named
    // on an earlier card is used again only when nothing else applies.
    final named = <String>{};
    return [
      for (final entry in _groups.entries)
        if (scores.where((s) => entry.value.contains(s.area)).toList()
            case final group when group.isNotEmpty)
          _area(entry.key, group, named),
    ];
  }

  AreaReading _area(String key, List<AreaScore> group, Set<String> named) {
    final score =
        (group.map((s) => s.score).reduce((a, b) => a + b) / group.length)
            .round();
    final trend = group.first.trend;
    final factors = {
      for (final s in group)
        for (final id in s.factorIds) ?_factors[id],
    }.toList();
    SourceFactor? best(bool positive) {
      final pool = factors.where(
        (f) => f.kind == 'transit' && (f.contribution > 0) == positive,
      );
      if (pool.isEmpty) return null;
      final fresh = pool.where((f) => !named.contains(f.id));
      final pick = (fresh.isEmpty ? pool : fresh).reduce(
        (a, b) => a.contribution.abs() >= b.contribution.abs() ? a : b,
      );
      named.add(pick.id);
      return pick;
    }

    final trendText = switch (trend) {
      ScoreTrend.rising => _t('fc_trend_rising'),
      ScoreTrend.falling => _t('fc_trend_falling'),
      _ => '',
    };
    return AreaReading(
      key: key,
      score: score,
      trend: trend,
      summary: [
        _t(
          'fc_tone_${toneOf(score).name}_${key == 'general_energy' ? 'general' : 'area'}',
        ),
        if (trendText.isNotEmpty) trendText,
      ].join(' '),
      support: switch (best(true)) {
        final f? => _describe(f),
        null => null,
      },
      caution: switch (best(false)) {
        final f? => _describe(f),
        null => null,
      },
    );
  }

  // --------------------------------------------------------------- factors

  InfluenceLine? _describe(SourceFactor f) {
    final weight = (f.contribution.abs() * 100).round().clamp(0, 100);
    final supportive = f.contribution >= 0;
    final d = f.detail;
    switch (f.kind) {
      case 'transit':
        final influence =
            Influence.from(d['transiting_body'], d['aspect'], d['target']) ??
            Influence.parse(f.label);
        if (influence == null) return null;
        return InfluenceLine(
          title: influence.title(words),
          meaning: influence.meaning(words),
          supportive: supportive,
          weight: weight,
          at: f.at,
        );
      case 'house_ingress':
        final planet = planetFromWire(d['planet']);
        final house = d['to_house'];
        if (planet == null || house is! int) return null;
        return InfluenceLine(
          title: _t('fc_enters_house')
              .replaceAll('{planet}', words.planet(planet))
              .replaceAll('{house}', '$house'),
          meaning: _houseMeaning(planet, house),
          supportive: supportive,
          weight: weight,
          at: f.at,
        );
      case 'retrograde':
        final planet = planetFromWire(d['planet']);
        if (planet == null) return null;
        return InfluenceLine(
          title: _t(
            'fc_retrograde',
          ).replaceAll('{planet}', words.planet(planet)),
          meaning: _retrogradeMeaning(planet),
          supportive: false,
          weight: weight,
          at: DateTime.tryParse('${d['end_at']}'),
        );
      case 'moon_phase':
        final type = '${d['type']}';
        final sign = signFromWire(d['sign']);
        return InfluenceLine(
          title: [
            _t('fc_event_$type'),
            if (sign != null) words.sign(sign),
          ].join(' · '),
          meaning: _t('fc_event_${type}_note'),
          supportive: supportive,
          weight: weight,
          at: f.at,
        );
    }
    return null;
  }

  List<InfluenceLine> _labelled(List<String> labels) => [
    for (final label in labels)
      if (Influence.parse(label) case final influence?)
        InfluenceLine(
          title: influence.title(words),
          meaning: influence.meaning(words),
          supportive: influence.supportive,
        ),
  ];

  InfluenceLine? _retrograde(CosmicEvent event) {
    final planet = event.planet;
    if (planet == null) return null;
    return InfluenceLine(
      title: _t('fc_retrograde').replaceAll('{planet}', words.planet(planet)),
      meaning: _retrogradeMeaning(planet),
      supportive: false,
      at: event.endAt,
    );
  }

  InfluenceLine? _movement(HouseIngress m, {required bool supportive}) =>
      InfluenceLine(
        title: _t('fc_enters_house')
            .replaceAll('{planet}', words.planet(m.planet))
            .replaceAll('{house}', '${m.toHouse}'),
        meaning: _houseMeaning(m.planet, m.toHouse),
        supportive: supportive,
        at: m.enteredAt,
      );

  String? _houseMeaning(Planet planet, int house) {
    final topic = houseTopic(house, words.language);
    if (topic == null) return null;
    return _sentence(
      _t('fc_house_meaning')
          .replaceAll('{theme}', planetTheme(planet, words.language))
          .replaceAll('{topic}', topic),
    );
  }

  String _retrogradeMeaning(Planet planet) => _sentence(
    _t(
      'fc_retrograde_meaning',
    ).replaceAll('{theme}', planetTheme(planet, words.language)),
  );

  /// Themes are lower-case table entries; a sentence starts upper-case in
  /// the reader's own casing (i -> İ in Turkish).
  String _sentence(String text) => text.isEmpty
      ? text
      : text.substring(0, 1).toUpperCaseFor(words.language) + text.substring(1);

  String? _solarReturn(SolarReturnSummary s) {
    final sign = signFromWire(s.ascendantSign);
    return [
      _t('fc_solar_return'),
      if (sign != null)
        _t('fc_solar_return_asc').replaceAll('{sign}', words.sign(sign)),
      if (s.sunHouse case final house?)
        if (houseTopic(house, words.language) case final topic?)
          _t('fc_solar_return_sun').replaceAll('{topic}', topic),
    ].join(' ');
  }

  // ----------------------------------------------------------------- dates

  List<DatedLine> _dates(
    List<ForecastImportantDate> dates,
    List<ForecastPeriod> periods,
    List<CosmicEvent> events,
    List<ImportantHour> hours,
  ) {
    final lines = <DatedLine>[
      for (final d in dates)
        if (Influence.parse(d.label) case final influence?)
          // The meaning is told under the areas and lists; a date only
          // says what happens and whether it helps.
          DatedLine(
            at: d.date,
            title: influence.title(words),
            supportive: d.nature == 'opportunity'
                ? true
                : d.nature == 'challenge'
                ? false
                : null,
          ),
      for (final h in hours)
        if (Influence.parse(h.reason) case final influence?)
          DatedLine(
            at: h.start,
            until: h.end,
            title: influence.title(words),
            supportive: h.type == 'supportive',
            withTime: true,
          ),
      for (final p in periods)
        if (p.areas.isNotEmpty)
          DatedLine(
            at: p.startAt,
            until: p.endAt,
            title: _t('fc_key_period').replaceAll(
              '{areas}',
              p.areas.take(2).map(words.area).join(' & '),
            ),
            supportive: true,
          ),
      for (final e in events)
        if (_eventKey(e.type) case final key?)
          DatedLine(
            at: e.exactAt,
            title: [
              _t('fc_event_$key'),
              if (e.sign != null) words.sign(e.sign!),
            ].join(' · '),
            note: _t('fc_event_${key}_note'),
          ),
    ]..sort((a, b) => a.at.compareTo(b.at));
    return lines;
  }

  static String? _eventKey(CosmicEventType type) => switch (type) {
    CosmicEventType.newMoon => 'new_moon',
    CosmicEventType.fullMoon => 'full_moon',
    CosmicEventType.firstQuarter => 'first_quarter',
    CosmicEventType.lastQuarter => 'last_quarter',
    CosmicEventType.solarEclipse => 'solar_eclipse',
    CosmicEventType.lunarEclipse => 'lunar_eclipse',
    _ => null,
  };

  static List<InfluenceLine> _unique(List<InfluenceLine> lines) {
    final seen = <String>{};
    return [
      for (final l in lines)
        if (seen.add(l.title)) l,
    ];
  }
}
