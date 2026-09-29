import 'package:freezed_annotation/freezed_annotation.dart';

import 'aspect.dart';
import 'planet.dart';

part 'synastry_result.freezed.dart';
part 'synastry_result.g.dart';

enum CompatibilityMode { synastry, composite, davison }

enum CompatibilityArea {
  overall,
  love,
  emotional,
  communication,
  passion,
  trust,
  longTerm,
  karmic,
  challenges,
}

@freezed
abstract class CompatibilityScore with _$CompatibilityScore {
  const factory CompatibilityScore({
    required CompatibilityArea area,
    required int score,
    String? note,
  }) = _CompatibilityScore;

  factory CompatibilityScore.fromJson(Map<String, dynamic> json) =>
      _$CompatibilityScoreFromJson(json);
}

/// Cross-chart aspect between two people.
@freezed
abstract class SynastryAspect with _$SynastryAspect {
  const factory SynastryAspect({
    required Planet personAPlanet,
    required Planet personBPlanet,
    required AspectType type,
    required double orb,
    @Default(InfluenceNature.neutral) InfluenceNature nature,
  }) = _SynastryAspect;

  factory SynastryAspect.fromJson(Map<String, dynamic> json) =>
      _$SynastryAspectFromJson(json);
}

@freezed
abstract class SynastryResult with _$SynastryResult {
  const factory SynastryResult({
    required CompatibilityMode mode,
    required List<CompatibilityScore> scores,
    @Default(<SynastryAspect>[]) List<SynastryAspect> aspects,
    String? summary,
  }) = _SynastryResult;

  factory SynastryResult.fromJson(Map<String, dynamic> json) =>
      _$SynastryResultFromJson(json);
}
