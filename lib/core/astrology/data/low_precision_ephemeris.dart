import 'dart:math' as math;

import '../domain/planet.dart';

/// Low-precision sky maths used by [MockAstrologyService].
///
/// It is deliberately *coherent* rather than accurate: bodies move with their
/// real mean motions, so positions advance, aspects form and separate, the Moon
/// cycles correctly and retrogrades/eclipse seasons land in plausible windows.
/// Errors of several degrees are expected for the planets (no perturbation
/// terms, mean elements only), which is why every chart built from it is tagged
/// `isMock: true`.
///
/// A real ephemeris (Swiss Ephemeris service, backend API) replaces this file
/// without touching the domain models or the UI.
abstract final class LowPrecisionEphemeris {
  /// Mean orbital elements at J2000: longitude in degrees, motion in deg/day.
  static const Map<Planet, (double l0, double rate)> _meanElements =
      <Planet, (double, double)>{
        Planet.mercury: (252.25084, 4.09233445),
        Planet.venus: (181.97973, 1.60213034),
        Planet.mars: (355.43300, 0.52403840),
        Planet.jupiter: (34.35151, 0.08308676),
        Planet.saturn: (50.07744, 0.03344414),
        Planet.uranus: (314.05500, 0.01176904),
        Planet.neptune: (304.34867, 0.00602008),
        Planet.pluto: (238.92881, 0.00396000),
      };

  /// Obliquity of the ecliptic (J2000), in degrees.
  static const double obliquity = 23.4392911;

  static const double synodicMonth = 29.530588853;

  /// Days since J2000.0 (2000-01-01 12:00 UTC).
  static double daysSinceJ2000(DateTime moment) =>
      moment.toUtc().difference(DateTime.utc(2000, 1, 1, 12)).inSeconds /
      86400.0;

  static double _norm(double degrees) {
    final double value = degrees % 360;
    return value < 0 ? value + 360 : value;
  }

  static double _rad(double degrees) => degrees * math.pi / 180;

  static double _deg(double radians) => radians * 180 / math.pi;

  /// Apparent solar longitude (good to ~0.01 degrees).
  static double sunLongitude(DateTime moment) {
    final double d = daysSinceJ2000(moment);
    final double meanLongitude = 280.46646 + 0.98564736 * d;
    final double meanAnomaly = _rad(_norm(357.52911 + 0.98560028 * d));
    return _norm(
      meanLongitude +
          1.914602 * math.sin(meanAnomaly) +
          0.019993 * math.sin(2 * meanAnomaly),
    );
  }

  /// Lunar longitude with the two biggest terms (evection omitted): within a
  /// couple of degrees of the true Moon.
  static double moonLongitude(DateTime moment) {
    final double d = daysSinceJ2000(moment);
    final double meanLongitude = 218.3164477 + 13.17639648 * d;
    final double meanAnomaly = _rad(_norm(134.9633964 + 13.06499295 * d));
    final double meanElongation = _rad(_norm(297.8501921 + 12.19074912 * d));
    return _norm(
      meanLongitude +
          6.289 * math.sin(meanAnomaly) +
          1.274 * math.sin(2 * meanElongation - meanAnomaly) +
          0.658 * math.sin(2 * meanElongation),
    );
  }

  /// Mean ascending lunar node (retrograde by definition).
  static double northNodeLongitude(DateTime moment) =>
      _norm(125.04452 - 0.05295377 * daysSinceJ2000(moment));

  static double longitudeOf(Planet planet, DateTime moment) {
    switch (planet) {
      case Planet.sun:
        return sunLongitude(moment);
      case Planet.moon:
        return moonLongitude(moment);
      case Planet.northNode:
        return northNodeLongitude(moment);
      case Planet.southNode:
        return _norm(northNodeLongitude(moment) + 180);
      default:
        final (double l0, double rate) = _meanElements[planet]!;
        return _norm(l0 + rate * daysSinceJ2000(moment));
    }
  }

  /// Degrees per day, used for "applying vs separating" and for orb windows.
  static double dailyMotion(Planet planet) => switch (planet) {
    Planet.sun => 0.9856,
    Planet.moon => 13.1764,
    Planet.northNode || Planet.southNode => -0.0529,
    _ => _meanElements[planet]!.$2,
  };

  /// Retrograde heuristic based on elongation from the Sun.
  ///
  /// Inner planets turn retrograde around inferior conjunction, outer planets
  /// around opposition. The windows are the classic ones, so roughly the right
  /// proportion of the year is retrograde for each body.
  static bool isRetrograde(Planet planet, DateTime moment) {
    switch (planet) {
      case Planet.sun:
      case Planet.moon:
        return false;
      case Planet.northNode:
      case Planet.southNode:
        // The lunar nodes always move backwards.
        return true;
      default:
        final double elongation = signedSeparation(
          longitudeOf(planet, moment),
          sunLongitude(moment),
        ).abs();
        return switch (planet) {
          Planet.mercury => elongation < 11,
          Planet.venus => elongation < 8,
          Planet.mars => elongation > 156,
          Planet.jupiter => elongation > 118,
          Planet.saturn => elongation > 111,
          Planet.uranus => elongation > 104,
          Planet.neptune => elongation > 101,
          Planet.pluto => elongation > 100,
          _ => false,
        };
    }
  }

  /// Shortest signed angle from [b] to [a], in [-180, 180].
  static double signedSeparation(double a, double b) {
    double diff = (a - b) % 360;
    if (diff > 180) diff -= 360;
    if (diff < -180) diff += 360;
    return diff;
  }

  static double separation(double a, double b) => signedSeparation(a, b).abs();

  // ------------------------------------------------------------- moon phase

  /// 0..1 position in the synodic cycle (0 = new moon, 0.5 = full moon).
  static double moonPhaseProgress(DateTime moment) {
    final double elongation = _norm(
      moonLongitude(moment) - sunLongitude(moment),
    );
    return elongation / 360;
  }

  static double moonIllumination(DateTime moment) =>
      (1 - math.cos(2 * math.pi * moonPhaseProgress(moment))) / 2;

  /// The instant the Moon next reaches [targetProgress] (0 new, 0.5 full),
  /// searched forward from [from] by bisection on the elongation.
  static DateTime? nextMoonPhase(
    DateTime from,
    double targetProgress, {
    int searchDays = 40,
  }) {
    double offset(DateTime moment) =>
        signedSeparation(moonPhaseProgress(moment) * 360, targetProgress * 360);

    DateTime previous = from.toUtc();
    double previousOffset = offset(previous);
    for (int hour = 1; hour <= searchDays * 24; hour++) {
      final DateTime current = from.toUtc().add(Duration(hours: hour));
      final double currentOffset = offset(current);
      if (previousOffset < 0 && currentOffset >= 0) {
        return _bisect(previous, current, offset);
      }
      previous = current;
      previousOffset = currentOffset;
    }
    return null;
  }

  /// True when a luminary syzygy at [moment] is close enough to the lunar nodes
  /// to produce an eclipse (the classic ~15.4 degree limit).
  static bool isEclipseSeason(DateTime moment, {double limit = 15.4}) {
    final double node = northNodeLongitude(moment);
    final double sun = sunLongitude(moment);
    final double toNode = separation(sun, node);
    final double toSouthNode = separation(sun, _norm(node + 180));
    return math.min(toNode, toSouthNode) <= limit;
  }

  // ------------------------------------------------------------ chart angles

  /// Greenwich mean sidereal time in degrees.
  static double gmst(DateTime moment) =>
      _norm(280.46061837 + 360.98564736629 * daysSinceJ2000(moment));

  /// Right ascension of the midheaven, in degrees.
  static double ramc(DateTime moment, double longitudeEast) =>
      _norm(gmst(moment) + longitudeEast);

  /// Ecliptic longitude of the Midheaven.
  static double midheaven(DateTime moment, double longitudeEast) {
    final double ramcRad = _rad(ramc(moment, longitudeEast));
    final double value = math.atan2(
      math.tan(ramcRad),
      math.cos(_rad(obliquity)),
    );
    double longitude = _deg(value);
    // atan2 collapses the circle onto a half-turn; restore the quadrant.
    if (math.cos(ramcRad) < 0) longitude += 180;
    return _norm(longitude);
  }

  /// Ecliptic longitude of the Ascendant for a place and moment.
  static double ascendant(
    DateTime moment,
    double latitude,
    double longitudeEast,
  ) {
    final double ramcRad = _rad(ramc(moment, longitudeEast));
    final double obliquityRad = _rad(obliquity);
    final double latitudeRad = _rad(latitude.clamp(-66.0, 66.0));

    final double y = -math.cos(ramcRad);
    final double x =
        math.sin(ramcRad) * math.cos(obliquityRad) +
        math.tan(latitudeRad) * math.sin(obliquityRad);
    return _norm(_deg(math.atan2(y, x)));
  }

  // ------------------------------------------------------------------ search

  /// Bisection helper for a function that crosses zero between [a] and [b].
  static DateTime _bisect(
    DateTime a,
    DateTime b,
    double Function(DateTime) f, {
    int iterations = 24,
  }) {
    DateTime low = a;
    DateTime high = b;
    for (int i = 0; i < iterations; i++) {
      final DateTime mid = low.add(
        Duration(milliseconds: high.difference(low).inMilliseconds ~/ 2),
      );
      if (f(low) * f(mid) <= 0) {
        high = mid;
      } else {
        low = mid;
      }
    }
    return low.add(
      Duration(milliseconds: high.difference(low).inMilliseconds ~/ 2),
    );
  }

  /// Finds the moment an aspect between a moving body and a fixed point is
  /// exact, scanning [searchDays] around [around].
  static DateTime? exactAspectTime({
    required Planet transiting,
    required double targetLongitude,
    required double aspectAngle,
    required DateTime around,
    int searchDays = 60,
    int stepHours = 6,
  }) {
    double delta(DateTime moment) => signedSeparation(
      separation(longitudeOf(transiting, moment), targetLongitude),
      aspectAngle,
    );

    DateTime previous = around.toUtc().subtract(Duration(days: searchDays));
    double previousDelta = delta(previous);
    final int steps = (searchDays * 2 * 24) ~/ stepHours;
    DateTime? best;
    Duration bestDistance = const Duration(days: 9999);

    for (int i = 1; i <= steps; i++) {
      final DateTime current = previous.add(Duration(hours: stepHours));
      final double currentDelta = delta(current);
      if (previousDelta == 0 || previousDelta * currentDelta < 0) {
        final DateTime crossing = _bisect(previous, current, delta);
        final Duration distance = crossing.difference(around.toUtc()).abs();
        if (distance < bestDistance) {
          best = crossing;
          bestDistance = distance;
        }
      }
      previous = current;
      previousDelta = currentDelta;
    }
    return best;
  }

  /// Walks outward from [exact] until the aspect orb exceeds [orbLimit].
  static (DateTime start, DateTime end) aspectWindow({
    required Planet transiting,
    required double targetLongitude,
    required double aspectAngle,
    required DateTime exact,
    required double orbLimit,
    int maxDays = 400,
  }) {
    double orb(DateTime moment) =>
        (separation(longitudeOf(transiting, moment), targetLongitude) -
                aspectAngle)
            .abs();

    DateTime start = exact.toUtc();
    DateTime end = exact.toUtc();
    for (int hours = 6; hours <= maxDays * 24; hours += 6) {
      final DateTime candidate = exact.toUtc().subtract(Duration(hours: hours));
      if (orb(candidate) > orbLimit) break;
      start = candidate;
    }
    for (int hours = 6; hours <= maxDays * 24; hours += 6) {
      final DateTime candidate = exact.toUtc().add(Duration(hours: hours));
      if (orb(candidate) > orbLimit) break;
      end = candidate;
    }
    return (start, end);
  }
}
