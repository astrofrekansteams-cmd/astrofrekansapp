import '../domain/aspect.dart';
import '../domain/birth_data.dart';
import '../domain/cosmic_event.dart';
import '../domain/daily_frequency.dart';
import '../domain/moon_phase.dart';
import '../domain/natal_chart.dart';
import '../domain/planet.dart';
import '../domain/transit.dart';
import '../domain/zodiac_sign.dart';
import '../domain/saved_person.dart';
import '../domain/forecast.dart';
import '../domain/house_ingress.dart';

/// Strict JSON helpers: unexpected backend shapes fail at the data boundary.
abstract final class ContractJson {
  static Map<String, dynamic> map(Object? value) =>
      Map<String, dynamic>.from(value as Map);

  static List<Map<String, dynamic>> maps(Object? value) =>
      (value as List<dynamic>).map(map).toList();

  static String string(Map<String, dynamic> json, String key) =>
      json[key] as String;

  static double number(Map<String, dynamic> json, String key) =>
      (json[key] as num).toDouble();

  static DateTime date(Map<String, dynamic> json, String key) =>
      DateTime.parse(string(json, key));

  static String snake(String name) => name.replaceAllMapped(
    RegExp(r'[A-Z]'),
    (Match match) => '_${match.group(0)!.toLowerCase()}',
  );

  static T bySnake<T extends Enum>(List<T> values, String wire) =>
      values.firstWhere((T value) => snake(value.name) == wire);

  static T bySnakeOr<T extends Enum>(List<T> values, String wire, T fallback) {
    for (final T value in values) {
      if (snake(value.name) == wire) return value;
    }
    return fallback;
  }

  static DateTime? optionalDate(Map<String, dynamic> json, String key) =>
      json[key] == null ? null : DateTime.parse(json[key] as String);
}

class BirthProfileDto {
  const BirthProfileDto(this.json);

  final Map<String, dynamic> json;

  factory BirthProfileDto.fromJson(Map<String, dynamic> json) {
    ContractJson.string(json, 'birth_date');
    ContractJson.string(json, 'house_system');
    json['can_compute_houses'] as bool;
    return BirthProfileDto(json);
  }

  BirthData toDomain() => BirthData(
    date: ContractJson.date(json, 'birth_date'),
    time: (json['birth_time'] as String?)?.substring(0, 5),
    place: json['birth_place'] as String?,
    latitude: (json['latitude'] as num?)?.toDouble(),
    longitude: (json['longitude'] as num?)?.toDouble(),
    timezone: json['timezone'] as String?,
  );
}

class SavedPersonDto {
  const SavedPersonDto(this.json);

  final Map<String, dynamic> json;

  factory SavedPersonDto.fromJson(Map<String, dynamic> json) {
    ContractJson.string(json, 'id');
    ContractJson.string(json, 'name');
    ContractJson.string(json, 'relation');
    ContractJson.string(json, 'birth_date');
    return SavedPersonDto(json);
  }

  SavedPerson toDomain() => SavedPerson(
    id: ContractJson.string(json, 'id'),
    name: ContractJson.string(json, 'name'),
    relationship: ContractJson.string(json, 'relation'),
    birthDate: ContractJson.date(json, 'birth_date'),
    birthTime: (json['birth_time'] as String?)?.substring(0, 5),
    birthTimeKnown: json['birth_time_known'] as bool,
    birthPlace: json['birth_place'] as String?,
    latitude: (json['latitude'] as num?)?.toDouble(),
    longitude: (json['longitude'] as num?)?.toDouble(),
    timezone: json['timezone'] as String?,
    houseSystem: ContractJson.string(json, 'house_system'),
    note: json['note'] as String?,
    createdAt: ContractJson.date(json, 'created_at'),
  );
}

class NatalChartDto {
  const NatalChartDto(this.json);

  final Map<String, dynamic> json;

  factory NatalChartDto.fromJson(Map<String, dynamic> json) {
    ContractJson.string(json, 'kind');
    ContractJson.string(json, 'house_system');
    ContractJson.maps(json['planets']);
    ContractJson.maps(json['houses']);
    ContractJson.maps(json['aspects']);
    return NatalChartDto(json);
  }

  /// [event] allows charts cast for a moment rather than a birth (solar and
  /// lunar returns, composite, Davison): their birth_data is null and the
  /// chart subject supplies the instant and place instead.
  NatalChart toDomain({bool event = false}) {
    Map<String, dynamic>? birth = json['birth_data'] == null
        ? null
        : ContractJson.map(json['birth_data']);
    if (birth == null && event && json['subject'] is Map) {
      final Map<String, dynamic> subject = ContractJson.map(json['subject']);
      final String moment = ContractJson.string(subject, 'moment_utc');
      birth = <String, dynamic>{
        'birth_date': moment.substring(0, 10),
        'birth_time': moment.substring(11, 16),
        'place': subject['location_name'],
        'latitude': subject['latitude'],
        'longitude': subject['longitude'],
        'timezone': 'UTC',
      };
    }
    if (birth == null) {
      throw const FormatException('A natal chart requires birth_data.');
    }
    final Map<String, dynamic>? angles = json['angles'] == null
        ? null
        : ContractJson.map(json['angles']);
    return NatalChart(
      birthData: BirthData(
        date: ContractJson.date(birth, 'birth_date'),
        time: (birth['birth_time'] as String?)?.substring(0, 5),
        place: birth['place'] as String?,
        latitude: (birth['latitude'] as num?)?.toDouble(),
        longitude: (birth['longitude'] as num?)?.toDouble(),
        timezone: birth['timezone'] as String?,
      ),
      planets: <PlanetPosition>[
        for (final Map<String, dynamic> item in ContractJson.maps(
          json['planets'],
        ))
          PlanetPosition(
            planet: ContractJson.bySnake(
              Planet.values,
              ContractJson.string(item, 'planet'),
            ),
            sign: ContractJson.bySnake(
              ZodiacSign.values,
              ContractJson.string(item, 'sign'),
            ),
            longitude: ContractJson.number(item, 'longitude'),
            house: item['house'] as int?,
            isRetrograde: item['retrograde'] as bool? ?? false,
            latitude: (item['latitude'] as num?)?.toDouble(),
            speedLongitude: (item['speed_longitude'] as num?)?.toDouble(),
            reportedDegree: item['degree'] as int?,
            reportedMinute: item['minute'] as int?,
          ),
      ],
      houses: <HousePosition>[
        for (final Map<String, dynamic> item in ContractJson.maps(
          json['houses'],
        ))
          HousePosition(
            number: item['number'] as int,
            sign: ContractJson.bySnake(
              ZodiacSign.values,
              ContractJson.string(item, 'sign'),
            ),
            cuspLongitude: ContractJson.number(item, 'cusp_longitude'),
            degree: item['degree'] as int?,
            minute: item['minute'] as int?,
          ),
      ],
      aspects: <NatalAspect>[
        for (final Map<String, dynamic> item in ContractJson.maps(
          json['aspects'],
        ))
          NatalAspect(
            first: ContractJson.bySnake(
              Planet.values,
              ContractJson.string(item, 'first'),
            ),
            second: ContractJson.bySnake(
              Planet.values,
              ContractJson.string(item, 'second'),
            ),
            type: ContractJson.bySnake(
              AspectType.values,
              ContractJson.string(item, 'aspect'),
            ),
            orb: ContractJson.number(item, 'orb'),
            applying: item['applying'] as bool? ?? false,
            rawNature: item['nature'] as String?,
          ),
      ],
      ascendant: angles == null
          ? null
          : ContractJson.bySnake(
              ZodiacSign.values,
              ContractJson.string(angles, 'ascendant_sign'),
            ),
      midheaven: angles == null
          ? null
          : ContractJson.bySnake(
              ZodiacSign.values,
              ContractJson.string(angles, 'midheaven_sign'),
            ),
      ascendantLongitude: (angles?['ascendant'] as num?)?.toDouble(),
      midheavenLongitude: (angles?['midheaven'] as num?)?.toDouble(),
      houseSystem: ContractJson.bySnake(
        HouseSystem.values,
        ContractJson.string(json, 'house_system'),
      ),
      requestedHouseSystem: json['requested_house_system'] == null
          ? null
          : ContractJson.bySnake(
              HouseSystem.values,
              json['requested_house_system'] as String,
            ),
      warnings: (json['warnings'] as List<dynamic>? ?? const <dynamic>[])
          .cast<String>(),
      houseRulers: <int, Planet>{
        for (final MapEntry<String, dynamic> entry in ContractJson.map(
          json['house_rulers'] ?? <String, dynamic>{},
        ).entries)
          int.parse(entry.key): ContractJson.bySnake(
            Planet.values,
            entry.value as String,
          ),
      },
      engine: json['engine'] as String?,
      engineVersion: json['engine_version'] as String?,
      computedAt: ContractJson.optionalDate(json, 'computed_at'),
      chartKind: json['kind'] as String?,
      subject: json['subject'] == null
          ? null
          : _chartSubject(ContractJson.map(json['subject'])),
      sourceMetadata: <String, dynamic>{
        for (final String key in <String>[
          'elements',
          'modalities',
          'dominant_element',
          'dominant_modality',
          'dominant_planet',
          'big_three',
          'angles',
          'birth_data',
        ])
          if (json.containsKey(key)) key: json[key],
      },
      isMock: false,
    );
  }

  static ChartSubject _chartSubject(Map<String, dynamic> subject) =>
      ChartSubject(
        kind: ContractJson.string(subject, 'kind'),
        momentUtc: ContractJson.date(subject, 'moment_utc'),
        latitude: (subject['latitude'] as num?)?.toDouble(),
        longitude: (subject['longitude'] as num?)?.toDouble(),
        timezone: subject['timezone'] as String?,
        locationName: subject['location_name'] as String?,
      );
}

/// B4 transit adapter, including nullable windows and multi-pass cycles.
class TransitDto {
  const TransitDto(this.json);

  final Map<String, dynamic> json;

  factory TransitDto.fromJson(Map<String, dynamic> json) {
    ContractJson.string(json, 'id');
    ContractJson.string(json, 'status');
    ContractJson.string(json, 'target_type');
    ContractJson.maps(json['passes']);
    return TransitDto(json);
  }

  Transit toDomain({required String timezone}) {
    final String? targetBody = json['target_body'] as String?;
    final String? targetAngle = json['target_angle'] as String?;
    final String? aspect = json['aspect_type'] as String?;
    final String status = ContractJson.string(json, 'status');
    return Transit(
      summary: TransitSummary(
        id: ContractJson.string(json, 'id'),
        transitingPlanet: ContractJson.bySnake(
          Planet.values,
          ContractJson.string(json, 'transiting_body'),
        ),
        aspect: aspect == null
            ? null
            : ContractJson.bySnake(AspectType.values, aspect),
        natalPlanet: targetBody == null
            ? null
            : ContractJson.bySnake(Planet.values, targetBody),
        natalAngle: targetAngle == null
            ? null
            : ChartAngle.values
                  .where((ChartAngle angle) => angle.name == targetAngle)
                  .firstOrNull,
        rawTargetAngle: targetAngle,
        rawTargetType: ContractJson.string(json, 'target_type'),
        nature: switch (json['nature']) {
          'harmonious' => InfluenceNature.supportive,
          'challenging' => InfluenceNature.challenging,
          _ => InfluenceNature.neutral,
        },
        rawNature: json['nature'] as String?,
        backendTargetType: ContractJson.bySnakeOr(
          TransitTargetType.values,
          ContractJson.string(json, 'target_type'),
          TransitTargetType.unknown,
        ),
        house: json['target_house'] as int?,
      ),
      startAt: ContractJson.optionalDate(json, 'start_at'),
      exactAt: ContractJson.optionalDate(json, 'exact_at'),
      endAt: ContractJson.optionalDate(json, 'end_at'),
      status: ContractJson.bySnakeOr(
        TransitStatus.values,
        status,
        TransitStatus.unknown,
      ),
      rawStatus: status,
      passes: <TransitPass>[
        for (final Map<String, dynamic> pass in ContractJson.maps(
          json['passes'],
        ))
          TransitPass(
            number: pass['pass_number'] as int,
            exactAt: ContractJson.date(pass, 'exact_at'),
            direction: ContractJson.bySnakeOr(
              TransitPassDirection.values,
              ContractJson.string(pass, 'direction'),
              TransitPassDirection.unknown,
            ),
            speed: ContractJson.number(pass, 'speed'),
            rawDirection: ContractJson.string(pass, 'direction'),
          ),
      ],
      affectedHouses:
          (json['affected_houses'] as List<dynamic>? ?? const <dynamic>[])
              .cast<int>(),
      windowClipped: json['window_clipped'] as bool? ?? false,
      maximumOrb: (json['maximum_orb'] as num?)?.toDouble(),
      applying: json['applying'] as bool?,
      engineVersion: json['engine_version'] as String?,
      scoringVersion: json['scoring_version'] as String?,
      metadata: ContractJson.map(json['metadata'] ?? <String, dynamic>{}),
      orb: ContractJson.number(json, 'orb'),
      strength: ContractJson.number(json, 'strength') / 100,
      strengthScore: json['strength'] as int,
      timezone: timezone,
    );
  }
}

class TransitListDto {
  const TransitListDto(this.json);

  final Map<String, dynamic> json;

  factory TransitListDto.fromJson(Map<String, dynamic> json) {
    for (final String key in <String>['active', 'approaching', 'upcoming']) {
      for (final Map<String, dynamic> item in ContractJson.maps(json[key])) {
        TransitDto.fromJson(item);
      }
    }
    return TransitListDto(json);
  }

  TransitWindow toWindow() {
    final String zone = ContractJson.string(json, 'timezone');
    List<Transit> group(String key) => <Transit>[
      for (final Map<String, dynamic> item in ContractJson.maps(json[key]))
        TransitDto.fromJson(item).toDomain(timezone: zone),
    ];
    return TransitWindow(
      startAt: ContractJson.date(json, 'start_at'),
      endAt: ContractJson.date(json, 'end_at'),
      reference: ContractJson.date(json, 'reference'),
      timezone: zone,
      range: ContractJson.string(json, 'range'),
      active: group('active'),
      approaching: group('approaching'),
      upcoming: group('upcoming'),
      ingresses: <HouseIngress>[
        for (final Map<String, dynamic> item in ContractJson.maps(
          json['ingresses'],
        ))
          parseHouseIngress(item),
      ],
      engineVersion: ContractJson.string(json, 'engine_version'),
      scoringVersion: ContractJson.string(json, 'scoring_version'),
      cached: json['cached'] as bool,
    );
  }

  List<Transit> toDomain() => toWindow().all;
}

HouseIngress parseHouseIngress(Map<String, dynamic> item) => HouseIngress(
  id: ContractJson.string(item, 'id'),
  planet: ContractJson.bySnake(
    Planet.values,
    ContractJson.string(item, 'planet'),
  ),
  fromHouse: item['from_house'] as int,
  toHouse: item['to_house'] as int,
  enteredAt: ContractJson.date(item, 'entered_at'),
  estimatedExitAt: ContractJson.optionalDate(item, 'estimated_exit_at'),
  retrograde: item['retrograde'] as bool,
  reEntry: item['re_entry'] as bool,
);

class DailyFrequencyDto {
  const DailyFrequencyDto(this.json);

  final Map<String, dynamic> json;

  factory DailyFrequencyDto.fromJson(Map<String, dynamic> json) {
    ContractJson.date(json, 'date');
    json['overall'] as int;
    ContractJson.map(json['scores']);
    ContractJson.maps(json['important_hours']);
    ContractJson.maps(json['influences']);
    return DailyFrequencyDto(json);
  }

  DailyFrequency toDomain() {
    final Map<String, dynamic> scores = ContractJson.map(json['scores']);
    const Map<String, FrequencyCategory> categories =
        <String, FrequencyCategory>{
          'general_energy': FrequencyCategory.generalEnergy,
          'love': FrequencyCategory.love,
          'career': FrequencyCategory.career,
          'money': FrequencyCategory.money,
          'mood': FrequencyCategory.mood,
          'health_balance': FrequencyCategory.health,
          'luck': FrequencyCategory.luck,
        };
    return DailyFrequency(
      date: ContractJson.date(json, 'date'),
      overallScore: json['overall'] as int,
      scores: <AreaScore>[
        for (final MapEntry<String, dynamic> entry in scores.entries)
          _areaScore(ContractJson.map(entry.value), areaWire: entry.key),
      ],
      metrics: <FrequencyMetric>[
        for (final MapEntry<String, FrequencyCategory> entry
            in categories.entries)
          if (scores[entry.key] is Map)
            FrequencyMetric(
              category: entry.value,
              score: ContractJson.map(scores[entry.key])['score'] as int,
            ),
      ],
      importantHours: <ImportantHour>[
        for (final Map<String, dynamic> item in ContractJson.maps(
          json['important_hours'],
        ))
          _importantHour(item),
      ],
      influences: <SourceFactor>[
        for (final Map<String, dynamic> item in ContractJson.maps(
          json['influences'],
        ))
          _sourceFactor(item),
      ],
      // Today's transit influences, strongest contribution first, for the
      // home "affecting you today" row.
      transits: _transitInfluences(ContractJson.maps(json['influences'])),
      messageContext: ContractJson.map(
        json['message_context'] ?? <String, dynamic>{},
      ),
      timezone: json['timezone'] as String?,
      engineVersion: json['engine_version'] as String?,
      scoringVersion: json['scoring_version'] as String?,
      cached: json['cached'] as bool?,
    );
  }
}

List<TransitSummary> _transitInfluences(List<Map<String, dynamic>> items) {
  final transits =
      items
          .where(
            (item) =>
                item['kind'] == 'transit' &&
                item['detail'] is Map &&
                (item['detail'] as Map)['transiting_body'] is String,
          )
          .toList()
        ..sort(
          (a, b) => ((b['contribution'] as num?)?.abs() ?? 0).compareTo(
            (a['contribution'] as num?)?.abs() ?? 0,
          ),
        );
  return <TransitSummary>[
    for (final item in transits)
      if (_transitSummary(item) case final TransitSummary summary) summary,
  ];
}

TransitSummary? _transitSummary(Map<String, dynamic> item) {
  final Map<String, dynamic> detail = ContractJson.map(item['detail']);
  final Planet? body = _planetOrNull(detail['transiting_body'] as String?);
  if (body == null) return null;
  final String? target = detail['target'] as String?;
  final String? aspect = detail['aspect'] as String?;
  return TransitSummary(
    id: ContractJson.string(item, 'id'),
    transitingPlanet: body,
    aspect: AspectType.values
        .where((AspectType type) => type.name == aspect)
        .firstOrNull,
    natalPlanet: _planetOrNull(target),
    natalAngle: switch (target) {
      'asc' || 'ascendant' => ChartAngle.asc,
      'dsc' || 'descendant' => ChartAngle.dsc,
      'mc' || 'midheaven' => ChartAngle.mc,
      'ic' || 'imum_coeli' => ChartAngle.ic,
      _ => null,
    },
    rawNature: ((item['contribution'] as num?) ?? 0) >= 0
        ? 'supportive'
        : 'challenging',
  );
}

Planet? _planetOrNull(String? wire) {
  if (wire == null) return null;
  for (final Planet planet in Planet.values) {
    if (ContractJson.snake(planet.name) == wire) return planet;
  }
  return null;
}

AreaScore _areaScore(Map<String, dynamic> item, {String? areaWire}) {
  final String area = areaWire ?? ContractJson.string(item, 'area');
  final String trend = ContractJson.string(item, 'trend');
  return AreaScore(
    area: ContractJson.bySnakeOr(LifeArea.values, area, LifeArea.unknown),
    rawArea: area,
    score: item['score'] as int,
    trend: ContractJson.bySnakeOr(ScoreTrend.values, trend, ScoreTrend.unknown),
    rawTrend: trend,
    strength: item['strength'] as int,
    factorIds: (item['factor_ids'] as List<dynamic>? ?? const <dynamic>[])
        .cast<String>(),
  );
}

ImportantHour _importantHour(Map<String, dynamic> item) => ImportantHour(
  start: ContractJson.date(item, 'start'),
  end: ContractJson.date(item, 'end'),
  type: ContractJson.string(item, 'type'),
  strength: item['strength'] as int,
  reason: ContractJson.string(item, 'reason'),
  factorIds: (item['factor_ids'] as List<dynamic>? ?? const <dynamic>[])
      .cast<String>(),
);

SourceFactor _sourceFactor(Map<String, dynamic> item) => SourceFactor(
  id: ContractJson.string(item, 'id'),
  kind: ContractJson.string(item, 'kind'),
  label: ContractJson.string(item, 'label'),
  contribution: ContractJson.number(item, 'contribution'),
  areas: <LifeArea>[
    for (final String area
        in (item['areas'] as List<dynamic>? ?? const <dynamic>[])
            .cast<String>())
      ContractJson.bySnakeOr(LifeArea.values, area, LifeArea.unknown),
  ],
  at: ContractJson.optionalDate(item, 'at'),
  detail: ContractJson.map(item['detail'] ?? <String, dynamic>{}),
);

class CosmicCalendarDto {
  const CosmicCalendarDto(this.json);

  final Map<String, dynamic> json;

  factory CosmicCalendarDto.fromJson(Map<String, dynamic> json) {
    for (final Map<String, dynamic> item in ContractJson.maps(json['events'])) {
      ContractJson.string(item, 'type');
      ContractJson.date(item, 'exact_at');
    }
    return CosmicCalendarDto(json);
  }

  CosmicCalendarWindow toWindow() => CosmicCalendarWindow(
    startAt: ContractJson.date(json, 'start_at'),
    endAt: ContractJson.date(json, 'end_at'),
    timezone: ContractJson.string(json, 'timezone'),
    events: toDomain(),
    engineVersion: ContractJson.string(json, 'engine_version'),
    cached: json['cached'] as bool,
  );

  List<CosmicEvent> toDomain() => <CosmicEvent>[
    for (final Map<String, dynamic> item in ContractJson.maps(json['events']))
      CosmicEvent(
        id: ContractJson.string(item, 'id'),
        type: ContractJson.bySnakeOr(
          CosmicEventType.values,
          ContractJson.string(item, 'type'),
          CosmicEventType.unknown,
        ),
        rawType: ContractJson.string(item, 'type'),
        exactAt: ContractJson.date(item, 'exact_at'),
        startAt: item['start_at'] == null
            ? null
            : DateTime.parse(item['start_at'] as String),
        endAt: item['end_at'] == null
            ? null
            : DateTime.parse(item['end_at'] as String),
        planet: item['planet'] == null
            ? null
            : ContractJson.bySnake(Planet.values, item['planet'] as String),
        secondaryPlanet: item['secondary_planet'] == null
            ? null
            : ContractJson.bySnake(
                Planet.values,
                item['secondary_planet'] as String,
              ),
        aspectType: item['aspect'] == null
            ? null
            : ContractJson.bySnake(AspectType.values, item['aspect'] as String),
        eclipseSubtype: item['eclipse_subtype'] as String?,
        eclipseMagnitude: (item['eclipse_magnitude'] as num?)?.toDouble(),
        nodeDistance: (item['node_distance'] as num?)?.toDouble(),
        longitude: (item['longitude'] as num?)?.toDouble(),
        degree: item['degree'] as int?,
        metadata: ContractJson.map(item['metadata'] ?? <String, dynamic>{}),
        sign: item['sign'] == null
            ? null
            : ContractJson.bySnake(ZodiacSign.values, item['sign'] as String),
        timezone: json['timezone'] as String?,
      ),
  ];
}

class MoonPhaseDto {
  const MoonPhaseDto(this.json);

  final Map<String, dynamic> json;

  factory MoonPhaseDto.fromJson(Map<String, dynamic> json) {
    ContractJson.string(json, 'phase');
    ContractJson.date(json, 'moment');
    return MoonPhaseDto(json);
  }

  MoonPhase toDomain() => MoonPhase(
    date: ContractJson.date(json, 'moment'),
    type: ContractJson.bySnake(
      MoonPhaseType.values,
      ContractJson.string(json, 'phase'),
    ),
    illumination: ContractJson.number(json, 'illumination'),
    ageDays: ContractJson.number(json, 'age_days'),
    elongation: ContractJson.number(json, 'elongation'),
    nextPhase: json['next_phase'] == null
        ? null
        : ContractJson.bySnake(
            MoonPhaseType.values,
            json['next_phase'] as String,
          ),
    nextPhaseAt: ContractJson.optionalDate(json, 'next_phase_at'),
    sign: ContractJson.bySnake(
      ZodiacSign.values,
      ContractJson.string(json, 'sign'),
    ),
  );
}

class ForecastDto {
  const ForecastDto(this.json);

  final Map<String, dynamic> json;

  factory ForecastDto.daily(Map<String, dynamic> json) {
    ContractJson.string(json, 'period');
    _validateCommon(json);
    return ForecastDto(json);
  }

  factory ForecastDto.monthly(Map<String, dynamic> json) {
    json['month'] as int;
    _validateCommon(json);
    return ForecastDto(json);
  }

  factory ForecastDto.annual(Map<String, dynamic> json) {
    json['year'] as int;
    _validateCommon(json);
    if (json['solar_return'] != null) {
      ContractJson.map(json['solar_return']);
    }
    return ForecastDto(json);
  }

  static void _validateCommon(Map<String, dynamic> json) {
    ContractJson.date(json, 'start_at');
    ContractJson.date(json, 'end_at');
    ContractJson.maps(json['areas']);
    ContractJson.maps(json['major_transits']);
    ContractJson.maps(json['source_factors']);
  }

  HoroscopeForecast toHoroscope() => HoroscopeForecast(
    period: ContractJson.string(json, 'period'),
    startAt: ContractJson.date(json, 'start_at'),
    endAt: ContractJson.date(json, 'end_at'),
    timezone: ContractJson.string(json, 'timezone'),
    overallScore: json['overall_score'] as int,
    areas: _areas(),
    importantDates: _importantDates(),
    importantHours: _importantHours(),
    opportunities: _strings('opportunities'),
    challenges: _strings('challenges'),
    majorTransits: _transits('major_transits'),
    moonEvents: _events('moon_events'),
    houseActivations: _houseActivations(),
    keyPeriods: _periods(),
    sourceFactors: _factors(),
    engineVersion: ContractJson.string(json, 'engine_version'),
    scoringVersion: ContractJson.string(json, 'scoring_version'),
    cached: json['cached'] as bool,
  );

  MonthlyForecast toMonthly() => MonthlyForecast(
    year: json['year'] as int,
    month: json['month'] as int,
    startAt: ContractJson.date(json, 'start_at'),
    endAt: ContractJson.date(json, 'end_at'),
    timezone: ContractJson.string(json, 'timezone'),
    overall: json['overall'] as int,
    areas: _areas(),
    generalTheme: <LifeArea>[
      for (final String value in _strings('general_theme'))
        ContractJson.bySnakeOr(LifeArea.values, value, LifeArea.unknown),
    ],
    keyPeriods: _periods(),
    importantDates: _importantDates(),
    opportunities: _strings('opportunities'),
    challenges: _strings('challenges'),
    majorTransits: _transits('major_transits'),
    moonEvents: _events('moon_events'),
    retrogrades: _events('retrogrades'),
    houseActivations: _houseActivations(),
    personalEvents: <PersonalForecastEvent>[
      for (final Map<String, dynamic> item in ContractJson.maps(
        json['personal_events'],
      ))
        PersonalForecastEvent(
          event: _event(ContractJson.map(item['event'])),
          affectedHouse: item['affected_house'] as int?,
          natalAspects: <NatalContact>[
            for (final Map<String, dynamic> contact in ContractJson.maps(
              item['natal_aspects'],
            ))
              NatalContact(
                targetBody: contact['target_body'] == null
                    ? null
                    : ContractJson.bySnake(
                        Planet.values,
                        contact['target_body'] as String,
                      ),
                targetAngle: ChartAngle.values
                    .where(
                      (ChartAngle angle) =>
                          angle.name == contact['target_angle'],
                    )
                    .firstOrNull,
                rawTargetAngle: contact['target_angle'] as String?,
                aspect: ContractJson.string(contact, 'aspect'),
                orb: ContractJson.number(contact, 'orb'),
              ),
          ],
          strength: item['strength'] as int,
          personalRelevance: ContractJson.string(item, 'personal_relevance'),
          sourceFactors: (item['source_factors'] as List<dynamic>)
              .cast<String>(),
        ),
    ],
    sourceFactors: _factors(),
    engineVersion: ContractJson.string(json, 'engine_version'),
    scoringVersion: ContractJson.string(json, 'scoring_version'),
    cached: json['cached'] as bool,
  );

  AnnualForecast toAnnual() => AnnualForecast(
    year: json['year'] as int,
    startAt: ContractJson.date(json, 'start_at'),
    endAt: ContractJson.date(json, 'end_at'),
    timezone: ContractJson.string(json, 'timezone'),
    overall: json['overall'] as int,
    areas: _areas(),
    majorTransits: _transits('major_transits'),
    retrogradePeriods: _events('retrograde_periods'),
    eclipses: _events('eclipses'),
    jupiterMovements: _ingresses('jupiter_movements'),
    saturnMovements: _ingresses('saturn_movements'),
    outerPlanetHits: _transits('outer_planet_hits'),
    houseActivations: _houseActivations(),
    keyPeriods: _periods(),
    importantDates: _importantDates(),
    solarReturn: json['solar_return'] == null
        ? null
        : _solarReturn(ContractJson.map(json['solar_return'])),
    sourceFactors: _factors(),
    engineVersion: ContractJson.string(json, 'engine_version'),
    scoringVersion: ContractJson.string(json, 'scoring_version'),
    cached: json['cached'] as bool,
  );

  List<String> _strings(String key) =>
      (json[key] as List<dynamic>? ?? const <dynamic>[]).cast<String>();

  List<AreaScore> _areas() => <AreaScore>[
    for (final Map<String, dynamic> item in ContractJson.maps(json['areas']))
      _areaScore(item),
  ];

  List<ImportantHour> _importantHours() => <ImportantHour>[
    for (final Map<String, dynamic> item in ContractJson.maps(
      json['important_hours'],
    ))
      _importantHour(item),
  ];

  List<SourceFactor> _factors() => <SourceFactor>[
    for (final Map<String, dynamic> item in ContractJson.maps(
      json['source_factors'],
    ))
      _sourceFactor(item),
  ];

  List<Transit> _transits(String key) => <Transit>[
    for (final Map<String, dynamic> item in ContractJson.maps(json[key]))
      TransitDto.fromJson(
        item,
      ).toDomain(timezone: ContractJson.string(json, 'timezone')),
  ];

  CosmicEvent _event(Map<String, dynamic> item) =>
      CosmicCalendarDto.fromJson(<String, dynamic>{
        'timezone': json['timezone'],
        'events': <Map<String, dynamic>>[item],
      }).toDomain().single;

  List<CosmicEvent> _events(String key) => <CosmicEvent>[
    for (final Map<String, dynamic> item in ContractJson.maps(json[key]))
      _event(item),
  ];

  List<ForecastImportantDate> _importantDates() => <ForecastImportantDate>[
    for (final Map<String, dynamic> item in ContractJson.maps(
      json['important_dates'],
    ))
      ForecastImportantDate(
        date: ContractJson.date(item, 'date'),
        label: ContractJson.string(item, 'label'),
        strength: item['strength'] as int,
        nature: ContractJson.string(item, 'nature'),
        factorIds: (item['factor_ids'] as List<dynamic>).cast<String>(),
      ),
  ];

  List<ForecastPeriod> _periods() => <ForecastPeriod>[
    for (final Map<String, dynamic> item in ContractJson.maps(
      json['key_periods'],
    ))
      ForecastPeriod(
        startAt: ContractJson.date(item, 'start_at'),
        endAt: ContractJson.date(item, 'end_at'),
        areas: <LifeArea>[
          for (final String area
              in (item['areas'] as List<dynamic>).cast<String>())
            ContractJson.bySnakeOr(LifeArea.values, area, LifeArea.unknown),
        ],
        strength: item['strength'] as int,
        label: ContractJson.string(item, 'label'),
        sourceFactors: (item['source_factors'] as List<dynamic>).cast<String>(),
      ),
  ];

  List<HouseActivation> _houseActivations() => <HouseActivation>[
    for (final Map<String, dynamic> item in ContractJson.maps(
      json['house_activations'],
    ))
      HouseActivation(
        house: item['house'] as int,
        planets: <Planet>[
          for (final String planet
              in (item['planets'] as List<dynamic>).cast<String>())
            ContractJson.bySnake(Planet.values, planet),
        ],
        strength: item['strength'] as int,
        factorIds: (item['factor_ids'] as List<dynamic>).cast<String>(),
      ),
  ];

  List<HouseIngress> _ingresses(String key) => <HouseIngress>[
    for (final Map<String, dynamic> item in ContractJson.maps(json[key]))
      parseHouseIngress(item),
  ];

  SolarReturnSummary _solarReturn(Map<String, dynamic> item) =>
      SolarReturnSummary(
        year: item['year'] as int,
        exactAt: ContractJson.date(item, 'exact_at'),
        ascendant: (item['ascendant'] as num?)?.toDouble(),
        ascendantSign: item['ascendant_sign'] as String?,
        sunHouse: item['sun_house'] as int?,
      );
}
