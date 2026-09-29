import 'package:freezed_annotation/freezed_annotation.dart';

import '../../assets/app_assets.dart';
import 'zodiac_sign.dart';

part 'moon_phase.freezed.dart';
part 'moon_phase.g.dart';

enum MoonPhaseType {
  newMoon,
  waxingCrescent,
  firstQuarter,
  waxingGibbous,
  fullMoon,
  waningGibbous,
  lastQuarter,
  waningCrescent;

  String get assetKey => switch (this) {
    MoonPhaseType.newMoon => 'new_moon',
    MoonPhaseType.waxingCrescent => 'waxing_crescent',
    MoonPhaseType.firstQuarter => 'first_quarter',
    MoonPhaseType.waxingGibbous => 'waxing_gibbous',
    MoonPhaseType.fullMoon => 'full_moon',
    MoonPhaseType.waningGibbous => 'waning_gibbous',
    MoonPhaseType.lastQuarter => 'last_quarter',
    MoonPhaseType.waningCrescent => 'waning_crescent',
  };

  String get asset => AppAssets.moonPhases[assetKey]!;
}

/// Where the Moon is and what it means for the user today.
@freezed
abstract class MoonPhase with _$MoonPhase {
  const factory MoonPhase({
    required DateTime date,
    required MoonPhaseType type,

    /// 0..1 lit fraction of the disc.
    required double illumination,

    /// 0..1 position in the synodic cycle.
    double? cycleProgress,
    double? ageDays,
    double? elongation,
    MoonPhaseType? nextPhase,
    DateTime? nextPhaseAt,
    ZodiacSign? sign,

    /// Natal house the Moon is currently transiting, when the chart allows it.
    int? house,
    String? message,
  }) = _MoonPhase;

  factory MoonPhase.fromJson(Map<String, dynamic> json) =>
      _$MoonPhaseFromJson(json);
}

/// Home-screen sized projection of [MoonPhase].
@freezed
abstract class MoonPhaseSummary with _$MoonPhaseSummary {
  const factory MoonPhaseSummary({
    required MoonPhaseType type,
    ZodiacSign? sign,
    String? message,
  }) = _MoonPhaseSummary;

  factory MoonPhaseSummary.fromJson(Map<String, dynamic> json) =>
      _$MoonPhaseSummaryFromJson(json);
}
