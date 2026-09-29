import '../../assets/app_assets.dart';
import 'planet.dart';

/// The twelve tropical zodiac signs.
enum ZodiacSign {
  aries,
  taurus,
  gemini,
  cancer,
  leo,
  virgo,
  libra,
  scorpio,
  sagittarius,
  capricorn,
  aquarius,
  pisces;

  /// Key used by [AppAssets.zodiac].
  String get assetKey => name;

  String get asset => AppAssets.zodiac[assetKey]!;

  ZodiacElement get element => switch (this) {
    ZodiacSign.aries ||
    ZodiacSign.leo ||
    ZodiacSign.sagittarius => ZodiacElement.fire,
    ZodiacSign.taurus ||
    ZodiacSign.virgo ||
    ZodiacSign.capricorn => ZodiacElement.earth,
    ZodiacSign.gemini ||
    ZodiacSign.libra ||
    ZodiacSign.aquarius => ZodiacElement.air,
    ZodiacSign.cancer ||
    ZodiacSign.scorpio ||
    ZodiacSign.pisces => ZodiacElement.water,
  };

  /// Traditional ruling planet; used to weight the dominant planet.
  Planet get ruler => switch (this) {
    ZodiacSign.aries || ZodiacSign.scorpio => Planet.mars,
    ZodiacSign.taurus || ZodiacSign.libra => Planet.venus,
    ZodiacSign.gemini || ZodiacSign.virgo => Planet.mercury,
    ZodiacSign.cancer => Planet.moon,
    ZodiacSign.leo => Planet.sun,
    ZodiacSign.sagittarius || ZodiacSign.pisces => Planet.jupiter,
    ZodiacSign.capricorn || ZodiacSign.aquarius => Planet.saturn,
  };

  /// Start of the sign on the ecliptic, in degrees.
  double get startLongitude => index * 30;

  /// Sign that contains the given ecliptic longitude in degrees.
  static ZodiacSign fromLongitude(double longitude) {
    final double normalized = longitude % 360;
    final int index = (normalized / 30).floor().clamp(0, 11);
    return ZodiacSign.values[index];
  }
}

enum ZodiacElement {
  fire,
  earth,
  air,
  water;

  String get asset => AppAssets.elements[name]!;
}
