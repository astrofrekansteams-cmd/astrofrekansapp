import 'package:freezed_annotation/freezed_annotation.dart';

import '../../assets/app_assets.dart';
import 'moon_phase.dart';
import 'transit.dart';

part 'daily_frequency.freezed.dart';
part 'daily_frequency.g.dart';

/// Life areas scored by the daily frequency.
enum FrequencyCategory {
  generalEnergy,
  love,
  career,
  money,
  mood,
  health,
  luck;

  /// Key used by [AppAssets.dailyFrequency].
  String get assetKey => switch (this) {
    FrequencyCategory.generalEnergy => 'general_energy',
    FrequencyCategory.mood => 'health_balance',
    FrequencyCategory.health => 'health_balance',
    _ => name,
  };

  String get asset => AppAssets.dailyFrequency[assetKey]!;
}

/// Full B4 score taxonomy; the existing Home metrics remain a projection.
enum LifeArea {
  generalEnergy,
  love,
  relationships,
  career,
  money,
  healthBalance,
  personalGrowth,
  luck,
  mood,
  unknown,
}

enum ScoreTrend { rising, steady, falling, unknown }

@freezed
abstract class AreaScore with _$AreaScore {
  const factory AreaScore({
    required LifeArea area,
    required int score,
    required ScoreTrend trend,
    required int strength,
    @Default(<String>[]) List<String> factorIds,
    String? rawArea,
    String? rawTrend,
  }) = _AreaScore;

  factory AreaScore.fromJson(Map<String, dynamic> json) =>
      _$AreaScoreFromJson(json);
}

@freezed
abstract class ImportantHour with _$ImportantHour {
  const factory ImportantHour({
    required DateTime start,
    required DateTime end,
    required String type,
    required int strength,
    required String reason,
    @Default(<String>[]) List<String> factorIds,
  }) = _ImportantHour;

  factory ImportantHour.fromJson(Map<String, dynamic> json) =>
      _$ImportantHourFromJson(json);
}

@freezed
abstract class SourceFactor with _$SourceFactor {
  const factory SourceFactor({
    required String id,
    required String kind,
    required String label,
    required double contribution,
    @Default(<LifeArea>[]) List<LifeArea> areas,
    DateTime? at,
    @Default(<String, dynamic>{}) Map<String, dynamic> detail,
  }) = _SourceFactor;

  factory SourceFactor.fromJson(Map<String, dynamic> json) =>
      _$SourceFactorFromJson(json);
}

/// A single scored area.
@freezed
abstract class FrequencyMetric with _$FrequencyMetric {
  const factory FrequencyMetric({
    required FrequencyCategory category,

    /// 0-100.
    required int score,
  }) = _FrequencyMetric;

  factory FrequencyMetric.fromJson(Map<String, dynamic> json) =>
      _$FrequencyMetricFromJson(json);
}

enum FrequencyLevel { calm, balanced, high }

/// Short personalised note (day message, quick guidance).
@freezed
abstract class QuickInsight with _$QuickInsight {
  const factory QuickInsight({
    required String id,
    required String title,
    required String body,
    FrequencyCategory? category,
  }) = _QuickInsight;

  factory QuickInsight.fromJson(Map<String, dynamic> json) =>
      _$QuickInsightFromJson(json);
}

/// The Home screen payload: "Bugünün Frekansı".
///
/// This is *personal*: it is derived from the user's natal chart and the
/// transits hitting it, not from a generic sun-sign horoscope.
@freezed
abstract class DailyFrequency with _$DailyFrequency {
  const factory DailyFrequency({
    required DateTime date,

    /// 0-100 overall score.
    required int overallScore,
    required List<FrequencyMetric> metrics,
    @Default(<AreaScore>[]) List<AreaScore> scores,
    @Default(<ImportantHour>[]) List<ImportantHour> importantHours,
    @Default(<SourceFactor>[]) List<SourceFactor> influences,
    @Default(<String, dynamic>{}) Map<String, dynamic> messageContext,
    String? timezone,
    String? engineVersion,
    String? scoringVersion,
    bool? cached,
    @Default(<TransitSummary>[]) List<TransitSummary> transits,
    MoonPhaseSummary? moon,
    QuickInsight? message,
    @Default(<String>[]) List<String> suggestedPrompts,
  }) = _DailyFrequency;

  const DailyFrequency._();

  factory DailyFrequency.fromJson(Map<String, dynamic> json) =>
      _$DailyFrequencyFromJson(json);

  FrequencyLevel get level => switch (overallScore) {
    >= 78 => FrequencyLevel.high,
    >= 55 => FrequencyLevel.balanced,
    _ => FrequencyLevel.calm,
  };

  List<SourceFactor> get sourceFactors => influences;

  FrequencyMetric? metric(FrequencyCategory category) {
    for (final FrequencyMetric metric in metrics) {
      if (metric.category == category) return metric;
    }
    return null;
  }
}
