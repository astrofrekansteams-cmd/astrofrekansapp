// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'cosmic_event.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_CosmicEvent _$CosmicEventFromJson(Map<String, dynamic> json) => _CosmicEvent(
  id: json['id'] as String,
  type: $enumDecode(_$CosmicEventTypeEnumMap, json['type']),
  rawType: json['raw_type'] as String?,
  exactAt: DateTime.parse(json['exact_at'] as String),
  startAt: json['start_at'] == null
      ? null
      : DateTime.parse(json['start_at'] as String),
  endAt: json['end_at'] == null
      ? null
      : DateTime.parse(json['end_at'] as String),
  planet: $enumDecodeNullable(_$PlanetEnumMap, json['planet']),
  secondaryPlanet: $enumDecodeNullable(
    _$PlanetEnumMap,
    json['secondary_planet'],
  ),
  aspectType: $enumDecodeNullable(_$AspectTypeEnumMap, json['aspect_type']),
  eclipseSubtype: json['eclipse_subtype'] as String?,
  eclipseMagnitude: (json['eclipse_magnitude'] as num?)?.toDouble(),
  nodeDistance: (json['node_distance'] as num?)?.toDouble(),
  longitude: (json['longitude'] as num?)?.toDouble(),
  degree: (json['degree'] as num?)?.toInt(),
  metadata:
      json['metadata'] as Map<String, dynamic>? ?? const <String, dynamic>{},
  sign: $enumDecodeNullable(_$ZodiacSignEnumMap, json['sign']),
  moonPhase: $enumDecodeNullable(_$MoonPhaseTypeEnumMap, json['moon_phase']),
  affectedHouse: (json['affected_house'] as num?)?.toInt(),
  title: json['title'] as String?,
  description: json['description'] as String?,
  personalNote: json['personal_note'] as String?,
  isPersonal: json['is_personal'] as bool? ?? false,
  timezone: json['timezone'] as String?,
);

Map<String, dynamic> _$CosmicEventToJson(_CosmicEvent instance) =>
    <String, dynamic>{
      'id': instance.id,
      'type': _$CosmicEventTypeEnumMap[instance.type]!,
      'raw_type': ?instance.rawType,
      'exact_at': instance.exactAt.toIso8601String(),
      'start_at': ?instance.startAt?.toIso8601String(),
      'end_at': ?instance.endAt?.toIso8601String(),
      'planet': ?_$PlanetEnumMap[instance.planet],
      'secondary_planet': ?_$PlanetEnumMap[instance.secondaryPlanet],
      'aspect_type': ?_$AspectTypeEnumMap[instance.aspectType],
      'eclipse_subtype': ?instance.eclipseSubtype,
      'eclipse_magnitude': ?instance.eclipseMagnitude,
      'node_distance': ?instance.nodeDistance,
      'longitude': ?instance.longitude,
      'degree': ?instance.degree,
      'metadata': instance.metadata,
      'sign': ?_$ZodiacSignEnumMap[instance.sign],
      'moon_phase': ?_$MoonPhaseTypeEnumMap[instance.moonPhase],
      'affected_house': ?instance.affectedHouse,
      'title': ?instance.title,
      'description': ?instance.description,
      'personal_note': ?instance.personalNote,
      'is_personal': instance.isPersonal,
      'timezone': ?instance.timezone,
    };

const _$CosmicEventTypeEnumMap = {
  CosmicEventType.fullMoon: 'fullMoon',
  CosmicEventType.newMoon: 'newMoon',
  CosmicEventType.firstQuarter: 'firstQuarter',
  CosmicEventType.lastQuarter: 'lastQuarter',
  CosmicEventType.stationRetrograde: 'stationRetrograde',
  CosmicEventType.stationDirect: 'stationDirect',
  CosmicEventType.ingress: 'ingress',
  CosmicEventType.mercuryRetrograde: 'mercuryRetrograde',
  CosmicEventType.venusRetrograde: 'venusRetrograde',
  CosmicEventType.marsRetrograde: 'marsRetrograde',
  CosmicEventType.solarEclipse: 'solarEclipse',
  CosmicEventType.lunarEclipse: 'lunarEclipse',
  CosmicEventType.conjunction: 'conjunction',
  CosmicEventType.opposition: 'opposition',
  CosmicEventType.square: 'square',
  CosmicEventType.trine: 'trine',
  CosmicEventType.sextile: 'sextile',
  CosmicEventType.personalTransit: 'personalTransit',
  CosmicEventType.unknown: 'unknown',
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

const _$MoonPhaseTypeEnumMap = {
  MoonPhaseType.newMoon: 'newMoon',
  MoonPhaseType.waxingCrescent: 'waxingCrescent',
  MoonPhaseType.firstQuarter: 'firstQuarter',
  MoonPhaseType.waxingGibbous: 'waxingGibbous',
  MoonPhaseType.fullMoon: 'fullMoon',
  MoonPhaseType.waningGibbous: 'waningGibbous',
  MoonPhaseType.lastQuarter: 'lastQuarter',
  MoonPhaseType.waningCrescent: 'waningCrescent',
};
