import 'package:freezed_annotation/freezed_annotation.dart';

import 'aspect.dart';
import 'house_ingress.dart';
import 'planet.dart';

part 'transit.freezed.dart';
part 'transit.g.dart';

/// A compact, *structured* description of one sky influence.
///
/// The UI never receives pre-formatted strings like "Jüpiter △ Venüs": it
/// receives this record and formats it through the localization layer, so the
/// same data works in Turkish, English and later Azerbaijani.
@freezed
abstract class TransitSummary with _$TransitSummary {
  const factory TransitSummary({
    required String id,
    required Planet transitingPlanet,

    /// Set when the influence is an aspect to a natal body.
    AspectType? aspect,
    Planet? natalPlanet,
    ChartAngle? natalAngle,
    String? rawTargetAngle,
    String? rawTargetType,
    TransitTargetType? backendTargetType,

    /// Set when the influence is an ingress into a natal house (1-12).
    int? house,
    @Default(false) bool isRetrograde,
    @Default(InfluenceNature.neutral) InfluenceNature nature,
    String? rawNature,

    /// Short, already-localized interpretation coming from the content layer.
    String? headline,
  }) = _TransitSummary;

  const TransitSummary._();

  factory TransitSummary.fromJson(Map<String, dynamic> json) =>
      _$TransitSummaryFromJson(json);

  TransitShape get shape {
    if (aspect != null && natalPlanet != null) return TransitShape.aspect;
    if (house != null) return TransitShape.houseIngress;
    if (isRetrograde) return TransitShape.retrograde;
    return TransitShape.planetary;
  }

  /// What the transiting body is hitting.
  TransitTargetType get targetType =>
      backendTargetType ??
      switch (shape) {
        TransitShape.aspect => TransitTargetType.natalPlanet,
        TransitShape.houseIngress => TransitTargetType.house,
        _ => TransitTargetType.none,
      };
}

enum TransitShape { aspect, houseIngress, retrograde, planetary }

enum TransitTargetType {
  natalPlanet,
  natalAngle,
  houseIngress,
  house,
  none,
  unknown,
}

enum TransitPassDirection { direct, retrograde, unknown }

/// Full B4 envelope; the legacy UI continues to consume [all].
class TransitWindow {
  const TransitWindow({
    required this.startAt,
    required this.endAt,
    required this.reference,
    required this.timezone,
    required this.range,
    required this.active,
    required this.approaching,
    required this.upcoming,
    required this.ingresses,
    required this.engineVersion,
    required this.scoringVersion,
    required this.cached,
  });
  final DateTime startAt;
  final DateTime endAt;
  final DateTime reference;
  final String timezone;
  final String range;
  final List<Transit> active;
  final List<Transit> approaching;
  final List<Transit> upcoming;
  final List<HouseIngress> ingresses;
  final String engineVersion;
  final String scoringVersion;
  final bool cached;
  List<Transit> get all => <Transit>[...active, ...approaching, ...upcoming];
}

@freezed
abstract class TransitPass with _$TransitPass {
  const factory TransitPass({
    required int number,
    required DateTime exactAt,
    required TransitPassDirection direction,
    required double speed,
    String? rawDirection,
  }) = _TransitPass;

  factory TransitPass.fromJson(Map<String, dynamic> json) =>
      _$TransitPassFromJson(json);
}

/// Where a transit sits in its own life cycle.
enum TransitStatus {
  /// Exact aspect has not happened yet.
  approaching,

  /// Exact perfection, distinct from the legacy active UI state.
  exact,

  /// Exact, or within a tight orb around it.
  active,

  /// Past exact and fading out.
  separating,
  unknown,
}

/// The full transit record with timing, used by the transits feature and as
/// context for Astro AI.
@freezed
abstract class Transit with _$Transit {
  const factory Transit({
    required TransitSummary summary,
    DateTime? startAt,
    DateTime? exactAt,
    DateTime? endAt,

    /// Distance from exactness in degrees.
    @Default(0) double orb,

    /// 0..1 relative weight used for ordering and emphasis.
    @Default(0.5) double strength,
    int? strengthScore,
    @Default(TransitStatus.active) TransitStatus status,
    String? rawStatus,
    @Default(<TransitPass>[]) List<TransitPass> passes,
    @Default(<int>[]) List<int> affectedHouses,
    @Default(false) bool windowClipped,
    double? maximumOrb,
    bool? applying,
    String? engineVersion,
    String? scoringVersion,
    @Default(<String, dynamic>{}) Map<String, dynamic> metadata,

    /// IANA timezone the [startAt]/[exactAt]/[endAt] instants were computed
    /// for. The instants themselves are stored in UTC.
    String? timezone,
    String? interpretation,

    /// "What to do with it" copy shown in the detail screen.
    String? guidance,
  }) = _Transit;

  const Transit._();

  factory Transit.fromJson(Map<String, dynamic> json) =>
      _$TransitFromJson(json);

  String get id => summary.id;

  Planet get transitingPlanet => summary.transitingPlanet;

  AspectType? get aspectType => summary.aspect;

  Planet? get targetPlanet => summary.natalPlanet;

  ChartAngle? get targetAngle => summary.natalAngle;

  int? get targetHouse => summary.house;

  TransitTargetType get targetType => summary.targetType;

  bool isActiveOn(DateTime date) =>
      (startAt == null || !date.isBefore(startAt!)) &&
      (endAt == null || !date.isAfter(endAt!));

  /// Local-time instants for display. The model keeps UTC; the UI converts.
  DateTime? get exactLocal => exactAt?.toLocal();

  DateTime? get startLocal => startAt?.toLocal();

  DateTime? get endLocal => endAt?.toLocal();

  Duration? remainingFrom(DateTime moment) => endAt?.difference(moment);
}
