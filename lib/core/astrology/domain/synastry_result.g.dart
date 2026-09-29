// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'synastry_result.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_CompatibilityScore _$CompatibilityScoreFromJson(Map<String, dynamic> json) =>
    _CompatibilityScore(
      area: $enumDecode(_$CompatibilityAreaEnumMap, json['area']),
      score: (json['score'] as num).toInt(),
      note: json['note'] as String?,
    );

Map<String, dynamic> _$CompatibilityScoreToJson(_CompatibilityScore instance) =>
    <String, dynamic>{
      'area': _$CompatibilityAreaEnumMap[instance.area]!,
      'score': instance.score,
      'note': ?instance.note,
    };

const _$CompatibilityAreaEnumMap = {
  CompatibilityArea.overall: 'overall',
  CompatibilityArea.love: 'love',
  CompatibilityArea.emotional: 'emotional',
  CompatibilityArea.communication: 'communication',
  CompatibilityArea.passion: 'passion',
  CompatibilityArea.trust: 'trust',
  CompatibilityArea.longTerm: 'longTerm',
  CompatibilityArea.karmic: 'karmic',
  CompatibilityArea.challenges: 'challenges',
};

_SynastryAspect _$SynastryAspectFromJson(Map<String, dynamic> json) =>
    _SynastryAspect(
      personAPlanet: $enumDecode(_$PlanetEnumMap, json['person_a_planet']),
      personBPlanet: $enumDecode(_$PlanetEnumMap, json['person_b_planet']),
      type: $enumDecode(_$AspectTypeEnumMap, json['type']),
      orb: (json['orb'] as num).toDouble(),
      nature:
          $enumDecodeNullable(_$InfluenceNatureEnumMap, json['nature']) ??
          InfluenceNature.neutral,
    );

Map<String, dynamic> _$SynastryAspectToJson(_SynastryAspect instance) =>
    <String, dynamic>{
      'person_a_planet': _$PlanetEnumMap[instance.personAPlanet]!,
      'person_b_planet': _$PlanetEnumMap[instance.personBPlanet]!,
      'type': _$AspectTypeEnumMap[instance.type]!,
      'orb': instance.orb,
      'nature': _$InfluenceNatureEnumMap[instance.nature]!,
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

const _$InfluenceNatureEnumMap = {
  InfluenceNature.supportive: 'supportive',
  InfluenceNature.challenging: 'challenging',
  InfluenceNature.emotional: 'emotional',
  InfluenceNature.lesson: 'lesson',
  InfluenceNature.neutral: 'neutral',
};

_SynastryResult _$SynastryResultFromJson(Map<String, dynamic> json) =>
    _SynastryResult(
      mode: $enumDecode(_$CompatibilityModeEnumMap, json['mode']),
      scores: (json['scores'] as List<dynamic>)
          .map((e) => CompatibilityScore.fromJson(e as Map<String, dynamic>))
          .toList(),
      aspects:
          (json['aspects'] as List<dynamic>?)
              ?.map((e) => SynastryAspect.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const <SynastryAspect>[],
      summary: json['summary'] as String?,
    );

Map<String, dynamic> _$SynastryResultToJson(_SynastryResult instance) =>
    <String, dynamic>{
      'mode': _$CompatibilityModeEnumMap[instance.mode]!,
      'scores': instance.scores.map((e) => e.toJson()).toList(),
      'aspects': instance.aspects.map((e) => e.toJson()).toList(),
      'summary': ?instance.summary,
    };

const _$CompatibilityModeEnumMap = {
  CompatibilityMode.synastry: 'synastry',
  CompatibilityMode.composite: 'composite',
  CompatibilityMode.davison: 'davison',
};
