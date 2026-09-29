import 'package:freezed_annotation/freezed_annotation.dart';

import 'aspect.dart';
import 'birth_data.dart';
import 'planet.dart';
import 'zodiac_sign.dart';

part 'natal_chart.freezed.dart';
part 'natal_chart.g.dart';

/// House systems the engine can be asked for. Placidus is the default for
/// western natal work.
enum HouseSystem {
  placidus,
  koch,
  wholeSign,
  equal;

  String get displayName => switch (this) {
    HouseSystem.placidus => 'Placidus',
    HouseSystem.koch => 'Koch',
    HouseSystem.wholeSign => 'Whole Sign',
    HouseSystem.equal => 'Equal',
  };
}

@freezed
abstract class ChartSubject with _$ChartSubject {
  const factory ChartSubject({
    required String kind,
    required DateTime momentUtc,
    double? latitude,
    double? longitude,
    String? timezone,
    String? locationName,
  }) = _ChartSubject;

  factory ChartSubject.fromJson(Map<String, dynamic> json) =>
      _$ChartSubjectFromJson(json);
}

/// A body placed in the chart.
@freezed
abstract class PlanetPosition with _$PlanetPosition {
  const factory PlanetPosition({
    required Planet planet,
    required ZodiacSign sign,

    /// Ecliptic longitude in degrees (0-360).
    required double longitude,

    /// House number 1-12. Null when the birth time is unknown.
    int? house,
    @Default(false) bool isRetrograde,
    double? latitude,
    double? speedLongitude,
    int? reportedDegree,
    int? reportedMinute,
  }) = _PlanetPosition;

  const PlanetPosition._();

  factory PlanetPosition.fromJson(Map<String, dynamic> json) =>
      _$PlanetPositionFromJson(json);

  /// Degrees within the sign (0-30).
  double get degreeInSign => longitude % 30;

  /// Whole degrees within the sign, as astrologers write them.
  int get degree => degreeInSign.floor();

  /// Arc minutes within the degree.
  int get minute => ((degreeInSign - degree) * 60).floor();
}

/// One of the twelve houses.
@freezed
abstract class HousePosition with _$HousePosition {
  const factory HousePosition({
    required int number,
    required ZodiacSign sign,
    required double cuspLongitude,
    int? degree,
    int? minute,
  }) = _HousePosition;

  const HousePosition._();

  factory HousePosition.fromJson(Map<String, dynamic> json) =>
      _$HousePositionFromJson(json);

  double get cuspDegreeInSign => cuspLongitude % 30;

  int get cuspDegree => cuspDegreeInSign.floor();
}

/// An aspect between two natal bodies.
@freezed
abstract class NatalAspect with _$NatalAspect {
  const factory NatalAspect({
    required Planet first,
    required Planet second,
    required AspectType type,
    required double orb,

    /// True when the faster body is still moving towards exactness.
    @Default(false) bool applying,
    String? rawNature,
  }) = _NatalAspect;

  const NatalAspect._();

  factory NatalAspect.fromJson(Map<String, dynamic> json) =>
      _$NatalAspectFromJson(json);

  AspectNature get nature => type.nature;
}

/// Quality of a sign. Used by the analysis tab.
enum Modality { cardinal, fixed, mutable }

extension ZodiacModality on ZodiacSign {
  Modality get modality => switch (index % 3) {
    0 => Modality.cardinal,
    1 => Modality.fixed,
    _ => Modality.mutable,
  };
}

/// The chart itself. Computed by the astrology engine, never by the AI.
@freezed
abstract class NatalChart with _$NatalChart {
  const factory NatalChart({
    required BirthData birthData,
    required List<PlanetPosition> planets,
    @Default(<HousePosition>[]) List<HousePosition> houses,
    @Default(<NatalAspect>[]) List<NatalAspect> aspects,
    ZodiacSign? ascendant,
    ZodiacSign? midheaven,

    /// Ecliptic longitude of the ascendant; drives the wheel rotation.
    double? ascendantLongitude,
    double? midheavenLongitude,
    @Default(HouseSystem.placidus) HouseSystem houseSystem,
    HouseSystem? requestedHouseSystem,
    @Default(<String>[]) List<String> warnings,
    @Default(<int, Planet>{}) Map<int, Planet> houseRulers,
    String? engine,
    String? engineVersion,
    DateTime? computedAt,
    String? chartKind,
    ChartSubject? subject,
    @Default(<String, dynamic>{}) Map<String, dynamic> sourceMetadata,

    /// True while the chart comes from [MockAstrologyService] instead of a real
    /// ephemeris. Surfaced in the UI so mock output is never mistaken for a
    /// real reading.
    @Default(false) bool isMock,
  }) = _NatalChart;

  const NatalChart._();

  factory NatalChart.fromJson(Map<String, dynamic> json) =>
      _$NatalChartFromJson(json);

  PlanetPosition? positionOf(Planet planet) {
    for (final PlanetPosition position in planets) {
      if (position.planet == planet) return position;
    }
    return null;
  }

  HousePosition? house(int number) {
    for (final HousePosition house in houses) {
      if (house.number == number) return house;
    }
    return null;
  }

  PlanetPosition? get sun => positionOf(Planet.sun);

  PlanetPosition? get moon => positionOf(Planet.moon);

  ZodiacSign? get sunSign => sun?.sign;

  ZodiacSign? get moonSign => moon?.sign;

  /// Descendant / Imum Coeli are the opposite points of ASC / MC.
  ZodiacSign? get descendant => _opposite(ascendant);

  ZodiacSign? get imumCoeli => _opposite(midheaven);

  double? get descendantLongitude =>
      ascendantLongitude == null ? null : (ascendantLongitude! + 180) % 360;

  double? get imumCoeliLongitude =>
      midheavenLongitude == null ? null : (midheavenLongitude! + 180) % 360;

  /// Sun / Moon / Rising, the trio every astrology user asks for first.
  List<ZodiacSign?> get bigThree => <ZodiacSign?>[sunSign, moonSign, ascendant];

  Map<ZodiacElement, int> get elementDistribution {
    final Map<ZodiacElement, int> counts = <ZodiacElement, int>{
      for (final ZodiacElement element in ZodiacElement.values) element: 0,
    };
    for (final PlanetPosition position in planets) {
      counts[position.sign.element] = counts[position.sign.element]! + 1;
    }
    return counts;
  }

  Map<Modality, int> get modalityDistribution {
    final Map<Modality, int> counts = <Modality, int>{
      for (final Modality modality in Modality.values) modality: 0,
    };
    for (final PlanetPosition position in planets) {
      counts[position.sign.modality] = counts[position.sign.modality]! + 1;
    }
    return counts;
  }

  ZodiacElement get dominantElement {
    final Map<ZodiacElement, int> counts = elementDistribution;
    return counts.entries
        .reduce(
          (MapEntry<ZodiacElement, int> a, MapEntry<ZodiacElement, int> b) =>
              b.value > a.value ? b : a,
        )
        .key;
  }

  Modality get dominantModality {
    final Map<Modality, int> counts = modalityDistribution;
    return counts.entries
        .reduce(
          (MapEntry<Modality, int> a, MapEntry<Modality, int> b) =>
              b.value > a.value ? b : a,
        )
        .key;
  }

  /// The planet carrying the most weight: aspect count, with rulership of the
  /// big three as a tie-breaker.
  Planet get dominantPlanet {
    final Map<Planet, int> weights = <Planet, int>{
      for (final PlanetPosition position in planets) position.planet: 0,
    };
    for (final NatalAspect aspect in aspects) {
      weights[aspect.first] = (weights[aspect.first] ?? 0) + 1;
      weights[aspect.second] = (weights[aspect.second] ?? 0) + 1;
    }
    for (final ZodiacSign? sign in bigThree) {
      if (sign == null) continue;
      final Planet ruler = sign.ruler;
      weights[ruler] = (weights[ruler] ?? 0) + 2;
    }
    return weights.entries
        .reduce(
          (MapEntry<Planet, int> a, MapEntry<Planet, int> b) =>
              b.value > a.value ? b : a,
        )
        .key;
  }

  List<NatalAspect> aspectsOf(Planet planet) => <NatalAspect>[
    for (final NatalAspect aspect in aspects)
      if (aspect.first == planet || aspect.second == planet) aspect,
  ];

  static ZodiacSign? _opposite(ZodiacSign? sign) =>
      sign == null ? null : ZodiacSign.values[(sign.index + 6) % 12];
}
