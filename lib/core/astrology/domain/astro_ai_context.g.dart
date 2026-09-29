// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'astro_ai_context.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_AstroAIContext _$AstroAIContextFromJson(Map<String, dynamic> json) =>
    _AstroAIContext(
      natalChart: NatalChart.fromJson(
        json['natal_chart'] as Map<String, dynamic>,
      ),
      activeTransits:
          (json['active_transits'] as List<dynamic>?)
              ?.map((e) => Transit.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const <Transit>[],
      moon: json['moon'] == null
          ? null
          : MoonPhase.fromJson(json['moon'] as Map<String, dynamic>),
      generatedAt: json['generated_at'] == null
          ? null
          : DateTime.parse(json['generated_at'] as String),
    );

Map<String, dynamic> _$AstroAIContextToJson(
  _AstroAIContext instance,
) => <String, dynamic>{
  'natal_chart': instance.natalChart.toJson(),
  'active_transits': instance.activeTransits.map((e) => e.toJson()).toList(),
  'moon': ?instance.moon?.toJson(),
  'generated_at': ?instance.generatedAt?.toIso8601String(),
};
