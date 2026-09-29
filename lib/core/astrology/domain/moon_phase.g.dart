// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'moon_phase.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_MoonPhase _$MoonPhaseFromJson(Map<String, dynamic> json) => _MoonPhase(
  date: DateTime.parse(json['date'] as String),
  type: $enumDecode(_$MoonPhaseTypeEnumMap, json['type']),
  illumination: (json['illumination'] as num).toDouble(),
  cycleProgress: (json['cycle_progress'] as num?)?.toDouble(),
  ageDays: (json['age_days'] as num?)?.toDouble(),
  elongation: (json['elongation'] as num?)?.toDouble(),
  nextPhase: $enumDecodeNullable(_$MoonPhaseTypeEnumMap, json['next_phase']),
  nextPhaseAt: json['next_phase_at'] == null
      ? null
      : DateTime.parse(json['next_phase_at'] as String),
  sign: $enumDecodeNullable(_$ZodiacSignEnumMap, json['sign']),
  house: (json['house'] as num?)?.toInt(),
  message: json['message'] as String?,
);

Map<String, dynamic> _$MoonPhaseToJson(_MoonPhase instance) =>
    <String, dynamic>{
      'date': instance.date.toIso8601String(),
      'type': _$MoonPhaseTypeEnumMap[instance.type]!,
      'illumination': instance.illumination,
      'cycle_progress': ?instance.cycleProgress,
      'age_days': ?instance.ageDays,
      'elongation': ?instance.elongation,
      'next_phase': ?_$MoonPhaseTypeEnumMap[instance.nextPhase],
      'next_phase_at': ?instance.nextPhaseAt?.toIso8601String(),
      'sign': ?_$ZodiacSignEnumMap[instance.sign],
      'house': ?instance.house,
      'message': ?instance.message,
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

_MoonPhaseSummary _$MoonPhaseSummaryFromJson(Map<String, dynamic> json) =>
    _MoonPhaseSummary(
      type: $enumDecode(_$MoonPhaseTypeEnumMap, json['type']),
      sign: $enumDecodeNullable(_$ZodiacSignEnumMap, json['sign']),
      message: json['message'] as String?,
    );

Map<String, dynamic> _$MoonPhaseSummaryToJson(_MoonPhaseSummary instance) =>
    <String, dynamic>{
      'type': _$MoonPhaseTypeEnumMap[instance.type]!,
      'sign': ?_$ZodiacSignEnumMap[instance.sign],
      'message': ?instance.message,
    };
