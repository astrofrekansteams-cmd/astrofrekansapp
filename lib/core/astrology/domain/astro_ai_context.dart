import 'package:freezed_annotation/freezed_annotation.dart';

import 'moon_phase.dart';
import 'natal_chart.dart';
import 'transit.dart';

part 'astro_ai_context.freezed.dart';
part 'astro_ai_context.g.dart';

/// The astrological facts handed to Astro AI.
///
/// Astro AI interprets; it never computes the astrology itself. Everything in
/// this object comes from the astrology engine.
@freezed
abstract class AstroAIContext with _$AstroAIContext {
  const factory AstroAIContext({
    required NatalChart natalChart,
    @Default(<Transit>[]) List<Transit> activeTransits,
    MoonPhase? moon,
    DateTime? generatedAt,
  }) = _AstroAIContext;

  factory AstroAIContext.fromJson(Map<String, dynamic> json) =>
      _$AstroAIContextFromJson(json);
}
