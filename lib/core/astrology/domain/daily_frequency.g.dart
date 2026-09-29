// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'daily_frequency.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_AreaScore _$AreaScoreFromJson(Map<String, dynamic> json) => _AreaScore(
  area: $enumDecode(_$LifeAreaEnumMap, json['area']),
  score: (json['score'] as num).toInt(),
  trend: $enumDecode(_$ScoreTrendEnumMap, json['trend']),
  strength: (json['strength'] as num).toInt(),
  factorIds:
      (json['factor_ids'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList() ??
      const <String>[],
  rawArea: json['raw_area'] as String?,
  rawTrend: json['raw_trend'] as String?,
);

Map<String, dynamic> _$AreaScoreToJson(_AreaScore instance) =>
    <String, dynamic>{
      'area': _$LifeAreaEnumMap[instance.area]!,
      'score': instance.score,
      'trend': _$ScoreTrendEnumMap[instance.trend]!,
      'strength': instance.strength,
      'factor_ids': instance.factorIds,
      'raw_area': ?instance.rawArea,
      'raw_trend': ?instance.rawTrend,
    };

const _$LifeAreaEnumMap = {
  LifeArea.generalEnergy: 'generalEnergy',
  LifeArea.love: 'love',
  LifeArea.relationships: 'relationships',
  LifeArea.career: 'career',
  LifeArea.money: 'money',
  LifeArea.healthBalance: 'healthBalance',
  LifeArea.personalGrowth: 'personalGrowth',
  LifeArea.luck: 'luck',
  LifeArea.mood: 'mood',
  LifeArea.unknown: 'unknown',
};

const _$ScoreTrendEnumMap = {
  ScoreTrend.rising: 'rising',
  ScoreTrend.steady: 'steady',
  ScoreTrend.falling: 'falling',
  ScoreTrend.unknown: 'unknown',
};

_ImportantHour _$ImportantHourFromJson(Map<String, dynamic> json) =>
    _ImportantHour(
      start: DateTime.parse(json['start'] as String),
      end: DateTime.parse(json['end'] as String),
      type: json['type'] as String,
      strength: (json['strength'] as num).toInt(),
      reason: json['reason'] as String,
      factorIds:
          (json['factor_ids'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          const <String>[],
    );

Map<String, dynamic> _$ImportantHourToJson(_ImportantHour instance) =>
    <String, dynamic>{
      'start': instance.start.toIso8601String(),
      'end': instance.end.toIso8601String(),
      'type': instance.type,
      'strength': instance.strength,
      'reason': instance.reason,
      'factor_ids': instance.factorIds,
    };

_SourceFactor _$SourceFactorFromJson(Map<String, dynamic> json) =>
    _SourceFactor(
      id: json['id'] as String,
      kind: json['kind'] as String,
      label: json['label'] as String,
      contribution: (json['contribution'] as num).toDouble(),
      areas:
          (json['areas'] as List<dynamic>?)
              ?.map((e) => $enumDecode(_$LifeAreaEnumMap, e))
              .toList() ??
          const <LifeArea>[],
      at: json['at'] == null ? null : DateTime.parse(json['at'] as String),
      detail:
          json['detail'] as Map<String, dynamic>? ?? const <String, dynamic>{},
    );

Map<String, dynamic> _$SourceFactorToJson(_SourceFactor instance) =>
    <String, dynamic>{
      'id': instance.id,
      'kind': instance.kind,
      'label': instance.label,
      'contribution': instance.contribution,
      'areas': instance.areas.map((e) => _$LifeAreaEnumMap[e]!).toList(),
      'at': ?instance.at?.toIso8601String(),
      'detail': instance.detail,
    };

_FrequencyMetric _$FrequencyMetricFromJson(Map<String, dynamic> json) =>
    _FrequencyMetric(
      category: $enumDecode(_$FrequencyCategoryEnumMap, json['category']),
      score: (json['score'] as num).toInt(),
    );

Map<String, dynamic> _$FrequencyMetricToJson(_FrequencyMetric instance) =>
    <String, dynamic>{
      'category': _$FrequencyCategoryEnumMap[instance.category]!,
      'score': instance.score,
    };

const _$FrequencyCategoryEnumMap = {
  FrequencyCategory.generalEnergy: 'generalEnergy',
  FrequencyCategory.love: 'love',
  FrequencyCategory.career: 'career',
  FrequencyCategory.money: 'money',
  FrequencyCategory.mood: 'mood',
  FrequencyCategory.health: 'health',
  FrequencyCategory.luck: 'luck',
};

_QuickInsight _$QuickInsightFromJson(Map<String, dynamic> json) =>
    _QuickInsight(
      id: json['id'] as String,
      title: json['title'] as String,
      body: json['body'] as String,
      category: $enumDecodeNullable(
        _$FrequencyCategoryEnumMap,
        json['category'],
      ),
    );

Map<String, dynamic> _$QuickInsightToJson(_QuickInsight instance) =>
    <String, dynamic>{
      'id': instance.id,
      'title': instance.title,
      'body': instance.body,
      'category': ?_$FrequencyCategoryEnumMap[instance.category],
    };

_DailyFrequency _$DailyFrequencyFromJson(Map<String, dynamic> json) =>
    _DailyFrequency(
      date: DateTime.parse(json['date'] as String),
      overallScore: (json['overall_score'] as num).toInt(),
      metrics: (json['metrics'] as List<dynamic>)
          .map((e) => FrequencyMetric.fromJson(e as Map<String, dynamic>))
          .toList(),
      scores:
          (json['scores'] as List<dynamic>?)
              ?.map((e) => AreaScore.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const <AreaScore>[],
      importantHours:
          (json['important_hours'] as List<dynamic>?)
              ?.map((e) => ImportantHour.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const <ImportantHour>[],
      influences:
          (json['influences'] as List<dynamic>?)
              ?.map((e) => SourceFactor.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const <SourceFactor>[],
      messageContext:
          json['message_context'] as Map<String, dynamic>? ??
          const <String, dynamic>{},
      timezone: json['timezone'] as String?,
      engineVersion: json['engine_version'] as String?,
      scoringVersion: json['scoring_version'] as String?,
      cached: json['cached'] as bool?,
      transits:
          (json['transits'] as List<dynamic>?)
              ?.map((e) => TransitSummary.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const <TransitSummary>[],
      moon: json['moon'] == null
          ? null
          : MoonPhaseSummary.fromJson(json['moon'] as Map<String, dynamic>),
      message: json['message'] == null
          ? null
          : QuickInsight.fromJson(json['message'] as Map<String, dynamic>),
      suggestedPrompts:
          (json['suggested_prompts'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          const <String>[],
    );

Map<String, dynamic> _$DailyFrequencyToJson(
  _DailyFrequency instance,
) => <String, dynamic>{
  'date': instance.date.toIso8601String(),
  'overall_score': instance.overallScore,
  'metrics': instance.metrics.map((e) => e.toJson()).toList(),
  'scores': instance.scores.map((e) => e.toJson()).toList(),
  'important_hours': instance.importantHours.map((e) => e.toJson()).toList(),
  'influences': instance.influences.map((e) => e.toJson()).toList(),
  'message_context': instance.messageContext,
  'timezone': ?instance.timezone,
  'engine_version': ?instance.engineVersion,
  'scoring_version': ?instance.scoringVersion,
  'cached': ?instance.cached,
  'transits': instance.transits.map((e) => e.toJson()).toList(),
  'moon': ?instance.moon?.toJson(),
  'message': ?instance.message?.toJson(),
  'suggested_prompts': instance.suggestedPrompts,
};
