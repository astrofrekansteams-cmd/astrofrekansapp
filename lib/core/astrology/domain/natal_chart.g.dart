// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'natal_chart.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_ChartSubject _$ChartSubjectFromJson(Map<String, dynamic> json) =>
    _ChartSubject(
      kind: json['kind'] as String,
      momentUtc: DateTime.parse(json['moment_utc'] as String),
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      timezone: json['timezone'] as String?,
      locationName: json['location_name'] as String?,
    );

Map<String, dynamic> _$ChartSubjectToJson(_ChartSubject instance) =>
    <String, dynamic>{
      'kind': instance.kind,
      'moment_utc': instance.momentUtc.toIso8601String(),
      'latitude': ?instance.latitude,
      'longitude': ?instance.longitude,
      'timezone': ?instance.timezone,
      'location_name': ?instance.locationName,
    };

_PlanetPosition _$PlanetPositionFromJson(Map<String, dynamic> json) =>
    _PlanetPosition(
      planet: $enumDecode(_$PlanetEnumMap, json['planet']),
      sign: $enumDecode(_$ZodiacSignEnumMap, json['sign']),
      longitude: (json['longitude'] as num).toDouble(),
      house: (json['house'] as num?)?.toInt(),
      isRetrograde: json['is_retrograde'] as bool? ?? false,
      latitude: (json['latitude'] as num?)?.toDouble(),
      speedLongitude: (json['speed_longitude'] as num?)?.toDouble(),
      reportedDegree: (json['reported_degree'] as num?)?.toInt(),
      reportedMinute: (json['reported_minute'] as num?)?.toInt(),
    );

Map<String, dynamic> _$PlanetPositionToJson(_PlanetPosition instance) =>
    <String, dynamic>{
      'planet': _$PlanetEnumMap[instance.planet]!,
      'sign': _$ZodiacSignEnumMap[instance.sign]!,
      'longitude': instance.longitude,
      'house': ?instance.house,
      'is_retrograde': instance.isRetrograde,
      'latitude': ?instance.latitude,
      'speed_longitude': ?instance.speedLongitude,
      'reported_degree': ?instance.reportedDegree,
      'reported_minute': ?instance.reportedMinute,
    };

const _$PlanetEnumMap = {
  Planet.sun: 'sun',
  Planet.moon: 'moon',
  Planet.mercury: 'mercury',
  Planet.venus: 'venus',
  Planet.mars: 'mars',
  Planet.jupiter: 'jupiter',
  Planet.saturn: 'saturn',
  Planet.uranus: 'uranus',
  Planet.neptune: 'neptune',
  Planet.pluto: 'pluto',
  Planet.northNode: 'northNode',
  Planet.southNode: 'southNode',
};

const _$ZodiacSignEnumMap = {
  ZodiacSign.aries: 'aries',
  ZodiacSign.taurus: 'taurus',
  ZodiacSign.gemini: 'gemini',
  ZodiacSign.cancer: 'cancer',
  ZodiacSign.leo: 'leo',
  ZodiacSign.virgo: 'virgo',
  ZodiacSign.libra: 'libra',
  ZodiacSign.scorpio: 'scorpio',
  ZodiacSign.sagittarius: 'sagittarius',
  ZodiacSign.capricorn: 'capricorn',
  ZodiacSign.aquarius: 'aquarius',
  ZodiacSign.pisces: 'pisces',
};

_HousePosition _$HousePositionFromJson(Map<String, dynamic> json) =>
    _HousePosition(
      number: (json['number'] as num).toInt(),
      sign: $enumDecode(_$ZodiacSignEnumMap, json['sign']),
      cuspLongitude: (json['cusp_longitude'] as num).toDouble(),
      degree: (json['degree'] as num?)?.toInt(),
      minute: (json['minute'] as num?)?.toInt(),
    );

Map<String, dynamic> _$HousePositionToJson(_HousePosition instance) =>
    <String, dynamic>{
      'number': instance.number,
      'sign': _$ZodiacSignEnumMap[instance.sign]!,
      'cusp_longitude': instance.cuspLongitude,
      'degree': ?instance.degree,
      'minute': ?instance.minute,
    };

_NatalAspect _$NatalAspectFromJson(Map<String, dynamic> json) => _NatalAspect(
  first: $enumDecode(_$PlanetEnumMap, json['first']),
  second: $enumDecode(_$PlanetEnumMap, json['second']),
  type: $enumDecode(_$AspectTypeEnumMap, json['type']),
  orb: (json['orb'] as num).toDouble(),
  applying: json['applying'] as bool? ?? false,
  rawNature: json['raw_nature'] as String?,
);

Map<String, dynamic> _$NatalAspectToJson(_NatalAspect instance) =>
    <String, dynamic>{
      'first': _$PlanetEnumMap[instance.first]!,
      'second': _$PlanetEnumMap[instance.second]!,
      'type': _$AspectTypeEnumMap[instance.type]!,
      'orb': instance.orb,
      'applying': instance.applying,
      'raw_nature': ?instance.rawNature,
    };

const _$AspectTypeEnumMap = {
  AspectType.conjunction: 'conjunction',
  AspectType.sextile: 'sextile',
  AspectType.square: 'square',
  AspectType.trine: 'trine',
  AspectType.opposition: 'opposition',
};

_NatalChart _$NatalChartFromJson(Map<String, dynamic> json) => _NatalChart(
  birthData: BirthData.fromJson(json['birth_data'] as Map<String, dynamic>),
  planets: (json['planets'] as List<dynamic>)
      .map((e) => PlanetPosition.fromJson(e as Map<String, dynamic>))
      .toList(),
  houses:
      (json['houses'] as List<dynamic>?)
          ?.map((e) => HousePosition.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const <HousePosition>[],
  aspects:
      (json['aspects'] as List<dynamic>?)
          ?.map((e) => NatalAspect.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const <NatalAspect>[],
  ascendant: $enumDecodeNullable(_$ZodiacSignEnumMap, json['ascendant']),
  midheaven: $enumDecodeNullable(_$ZodiacSignEnumMap, json['midheaven']),
  ascendantLongitude: (json['ascendant_longitude'] as num?)?.toDouble(),
  midheavenLongitude: (json['midheaven_longitude'] as num?)?.toDouble(),
  houseSystem:
      $enumDecodeNullable(_$HouseSystemEnumMap, json['house_system']) ??
      HouseSystem.placidus,
  requestedHouseSystem: $enumDecodeNullable(
    _$HouseSystemEnumMap,
    json['requested_house_system'],
  ),
  warnings:
      (json['warnings'] as List<dynamic>?)?.map((e) => e as String).toList() ??
      const <String>[],
  houseRulers:
      (json['house_rulers'] as Map<String, dynamic>?)?.map(
        (k, e) => MapEntry(int.parse(k), $enumDecode(_$PlanetEnumMap, e)),
      ) ??
      const <int, Planet>{},
  engine: json['engine'] as String?,
  engineVersion: json['engine_version'] as String?,
  computedAt: json['computed_at'] == null
      ? null
      : DateTime.parse(json['computed_at'] as String),
  chartKind: json['chart_kind'] as String?,
  subject: json['subject'] == null
      ? null
      : ChartSubject.fromJson(json['subject'] as Map<String, dynamic>),
  sourceMetadata:
      json['source_metadata'] as Map<String, dynamic>? ??
      const <String, dynamic>{},
  isMock: json['is_mock'] as bool? ?? false,
);

Map<String, dynamic> _$NatalChartToJson(_NatalChart instance) =>
    <String, dynamic>{
      'birth_data': instance.birthData.toJson(),
      'planets': instance.planets.map((e) => e.toJson()).toList(),
      'houses': instance.houses.map((e) => e.toJson()).toList(),
      'aspects': instance.aspects.map((e) => e.toJson()).toList(),
      'ascendant': ?_$ZodiacSignEnumMap[instance.ascendant],
      'midheaven': ?_$ZodiacSignEnumMap[instance.midheaven],
      'ascendant_longitude': ?instance.ascendantLongitude,
      'midheaven_longitude': ?instance.midheavenLongitude,
      'house_system': _$HouseSystemEnumMap[instance.houseSystem]!,
      'requested_house_system':
          ?_$HouseSystemEnumMap[instance.requestedHouseSystem],
      'warnings': instance.warnings,
      'house_rulers': instance.houseRulers.map(
        (k, e) => MapEntry(k.toString(), _$PlanetEnumMap[e]!),
      ),
      'engine': ?instance.engine,
      'engine_version': ?instance.engineVersion,
      'computed_at': ?instance.computedAt?.toIso8601String(),
      'chart_kind': ?instance.chartKind,
      'subject': ?instance.subject?.toJson(),
      'source_metadata': instance.sourceMetadata,
      'is_mock': instance.isMock,
    };

const _$HouseSystemEnumMap = {
  HouseSystem.placidus: 'placidus',
  HouseSystem.koch: 'koch',
  HouseSystem.wholeSign: 'wholeSign',
  HouseSystem.equal: 'equal',
};
