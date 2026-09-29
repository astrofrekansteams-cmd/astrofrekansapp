// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'transit.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_TransitSummary _$TransitSummaryFromJson(Map<String, dynamic> json) =>
    _TransitSummary(
      id: json['id'] as String,
      transitingPlanet: $enumDecode(_$PlanetEnumMap, json['transiting_planet']),
      aspect: $enumDecodeNullable(_$AspectTypeEnumMap, json['aspect']),
      natalPlanet: $enumDecodeNullable(_$PlanetEnumMap, json['natal_planet']),
      natalAngle: $enumDecodeNullable(_$ChartAngleEnumMap, json['natal_angle']),
      rawTargetAngle: json['raw_target_angle'] as String?,
      rawTargetType: json['raw_target_type'] as String?,
      backendTargetType: $enumDecodeNullable(
        _$TransitTargetTypeEnumMap,
        json['backend_target_type'],
      ),
      house: (json['house'] as num?)?.toInt(),
      isRetrograde: json['is_retrograde'] as bool? ?? false,
      nature:
          $enumDecodeNullable(_$InfluenceNatureEnumMap, json['nature']) ??
          InfluenceNature.neutral,
      rawNature: json['raw_nature'] as String?,
      headline: json['headline'] as String?,
    );

Map<String, dynamic> _$TransitSummaryToJson(_TransitSummary instance) =>
    <String, dynamic>{
      'id': instance.id,
      'transiting_planet': _$PlanetEnumMap[instance.transitingPlanet]!,
      'aspect': ?_$AspectTypeEnumMap[instance.aspect],
      'natal_planet': ?_$PlanetEnumMap[instance.natalPlanet],
      'natal_angle': ?_$ChartAngleEnumMap[instance.natalAngle],
      'raw_target_angle': ?instance.rawTargetAngle,
      'raw_target_type': ?instance.rawTargetType,
      'backend_target_type':
          ?_$TransitTargetTypeEnumMap[instance.backendTargetType],
      'house': ?instance.house,
      'is_retrograde': instance.isRetrograde,
      'nature': _$InfluenceNatureEnumMap[instance.nature]!,
      'raw_nature': ?instance.rawNature,
      'headline': ?instance.headline,
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

const _$AspectTypeEnumMap = {
  AspectType.conjunction: 'conjunction',
  AspectType.sextile: 'sextile',
  AspectType.square: 'square',
  AspectType.trine: 'trine',
  AspectType.opposition: 'opposition',
};

const _$ChartAngleEnumMap = {
  ChartAngle.asc: 'asc',
  ChartAngle.dsc: 'dsc',
  ChartAngle.mc: 'mc',
  ChartAngle.ic: 'ic',
};

const _$TransitTargetTypeEnumMap = {
  TransitTargetType.natalPlanet: 'natalPlanet',
  TransitTargetType.natalAngle: 'natalAngle',
  TransitTargetType.houseIngress: 'houseIngress',
  TransitTargetType.house: 'house',
  TransitTargetType.none: 'none',
  TransitTargetType.unknown: 'unknown',
};

const _$InfluenceNatureEnumMap = {
  InfluenceNature.supportive: 'supportive',
  InfluenceNature.challenging: 'challenging',
  InfluenceNature.emotional: 'emotional',
  InfluenceNature.lesson: 'lesson',
  InfluenceNature.neutral: 'neutral',
};

_TransitPass _$TransitPassFromJson(Map<String, dynamic> json) => _TransitPass(
  number: (json['number'] as num).toInt(),
  exactAt: DateTime.parse(json['exact_at'] as String),
  direction: $enumDecode(_$TransitPassDirectionEnumMap, json['direction']),
  speed: (json['speed'] as num).toDouble(),
  rawDirection: json['raw_direction'] as String?,
);

Map<String, dynamic> _$TransitPassToJson(_TransitPass instance) =>
    <String, dynamic>{
      'number': instance.number,
      'exact_at': instance.exactAt.toIso8601String(),
      'direction': _$TransitPassDirectionEnumMap[instance.direction]!,
      'speed': instance.speed,
      'raw_direction': ?instance.rawDirection,
    };

const _$TransitPassDirectionEnumMap = {
  TransitPassDirection.direct: 'direct',
  TransitPassDirection.retrograde: 'retrograde',
  TransitPassDirection.unknown: 'unknown',
};

_Transit _$TransitFromJson(Map<String, dynamic> json) => _Transit(
  summary: TransitSummary.fromJson(json['summary'] as Map<String, dynamic>),
  startAt: json['start_at'] == null
      ? null
      : DateTime.parse(json['start_at'] as String),
  exactAt: json['exact_at'] == null
      ? null
      : DateTime.parse(json['exact_at'] as String),
  endAt: json['end_at'] == null
      ? null
      : DateTime.parse(json['end_at'] as String),
  orb: (json['orb'] as num?)?.toDouble() ?? 0,
  strength: (json['strength'] as num?)?.toDouble() ?? 0.5,
  strengthScore: (json['strength_score'] as num?)?.toInt(),
  status:
      $enumDecodeNullable(_$TransitStatusEnumMap, json['status']) ??
      TransitStatus.active,
  rawStatus: json['raw_status'] as String?,
  passes:
      (json['passes'] as List<dynamic>?)
          ?.map((e) => TransitPass.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const <TransitPass>[],
  affectedHouses:
      (json['affected_houses'] as List<dynamic>?)
          ?.map((e) => (e as num).toInt())
          .toList() ??
      const <int>[],
  windowClipped: json['window_clipped'] as bool? ?? false,
  maximumOrb: (json['maximum_orb'] as num?)?.toDouble(),
  applying: json['applying'] as bool?,
  engineVersion: json['engine_version'] as String?,
  scoringVersion: json['scoring_version'] as String?,
  metadata:
      json['metadata'] as Map<String, dynamic>? ?? const <String, dynamic>{},
  timezone: json['timezone'] as String?,
  interpretation: json['interpretation'] as String?,
  guidance: json['guidance'] as String?,
);

Map<String, dynamic> _$TransitToJson(_Transit instance) => <String, dynamic>{
  'summary': instance.summary.toJson(),
  'start_at': ?instance.startAt?.toIso8601String(),
  'exact_at': ?instance.exactAt?.toIso8601String(),
  'end_at': ?instance.endAt?.toIso8601String(),
  'orb': instance.orb,
  'strength': instance.strength,
  'strength_score': ?instance.strengthScore,
  'status': _$TransitStatusEnumMap[instance.status]!,
  'raw_status': ?instance.rawStatus,
  'passes': instance.passes.map((e) => e.toJson()).toList(),
  'affected_houses': instance.affectedHouses,
  'window_clipped': instance.windowClipped,
  'maximum_orb': ?instance.maximumOrb,
  'applying': ?instance.applying,
  'engine_version': ?instance.engineVersion,
  'scoring_version': ?instance.scoringVersion,
  'metadata': instance.metadata,
  'timezone': ?instance.timezone,
  'interpretation': ?instance.interpretation,
  'guidance': ?instance.guidance,
};

const _$TransitStatusEnumMap = {
  TransitStatus.approaching: 'approaching',
  TransitStatus.exact: 'exact',
  TransitStatus.active: 'active',
  TransitStatus.separating: 'separating',
  TransitStatus.unknown: 'unknown',
};
