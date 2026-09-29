import 'package:freezed_annotation/freezed_annotation.dart';

import 'aspect.dart';
import 'moon_phase.dart';
import 'planet.dart';
import 'zodiac_sign.dart';

part 'cosmic_event.freezed.dart';
part 'cosmic_event.g.dart';

class CosmicCalendarWindow {
  const CosmicCalendarWindow({
    required this.startAt,
    required this.endAt,
    required this.timezone,
    required this.events,
    required this.engineVersion,
    required this.cached,
  });
  final DateTime startAt;
  final DateTime endAt;
  final String timezone;
  final List<CosmicEvent> events;
  final String engineVersion;
  final bool cached;
}

enum CosmicEventType {
  fullMoon,
  newMoon,
  firstQuarter,
  lastQuarter,
  stationRetrograde,
  stationDirect,
  ingress,
  mercuryRetrograde,
  venusRetrograde,
  marsRetrograde,
  solarEclipse,
  lunarEclipse,
  conjunction,
  opposition,
  square,
  trine,
  sextile,
  personalTransit,
  unknown;

  bool get isMoonEvent =>
      this == CosmicEventType.fullMoon ||
      this == CosmicEventType.newMoon ||
      this == CosmicEventType.firstQuarter ||
      this == CosmicEventType.lastQuarter ||
      this == CosmicEventType.solarEclipse ||
      this == CosmicEventType.lunarEclipse;

  bool get isRetrograde =>
      this == CosmicEventType.mercuryRetrograde ||
      this == CosmicEventType.venusRetrograde ||
      this == CosmicEventType.marsRetrograde ||
      this == CosmicEventType.stationRetrograde;

  bool get isEclipse =>
      this == CosmicEventType.solarEclipse ||
      this == CosmicEventType.lunarEclipse;

  AspectType? get aspect => switch (this) {
    CosmicEventType.conjunction => AspectType.conjunction,
    CosmicEventType.opposition => AspectType.opposition,
    CosmicEventType.square => AspectType.square,
    CosmicEventType.trine => AspectType.trine,
    CosmicEventType.sextile => AspectType.sextile,
    _ => null,
  };
}

/// One entry of the cosmic calendar.
///
/// [isPersonal] marks entries that touch the user's own chart, which drives the
/// "Beni Etkileyenler" section. Instants are UTC; the UI renders local time.
@freezed
abstract class CosmicEvent with _$CosmicEvent {
  const factory CosmicEvent({
    required String id,
    required CosmicEventType type,
    String? rawType,

    /// The moment the event peaks.
    required DateTime exactAt,

    /// Window for events that last (retrogrades, long transits).
    DateTime? startAt,
    DateTime? endAt,
    Planet? planet,
    Planet? secondaryPlanet,
    AspectType? aspectType,
    String? eclipseSubtype,
    double? eclipseMagnitude,
    double? nodeDistance,
    double? longitude,
    int? degree,
    @Default(<String, dynamic>{}) Map<String, dynamic> metadata,
    ZodiacSign? sign,
    MoonPhaseType? moonPhase,

    /// Natal house the event lands in, when the chart is known.
    int? affectedHouse,
    String? title,
    String? description,

    /// Extra line explaining why it matters for this user.
    String? personalNote,
    @Default(false) bool isPersonal,
    String? timezone,
  }) = _CosmicEvent;

  const CosmicEvent._();

  factory CosmicEvent.fromJson(Map<String, dynamic> json) =>
      _$CosmicEventFromJson(json);

  DateTime get exactLocal => exactAt.toLocal();

  /// Calendar day (local) the dot is drawn on.
  DateTime get localDay {
    final DateTime local = exactAt.toLocal();
    return DateTime(local.year, local.month, local.day);
  }

  bool get isRange => startAt != null && endAt != null;
}
