import '../../l10n/generated/app_localizations.dart';
import '../astrology/domain/aspect.dart';
import '../astrology/domain/daily_frequency.dart';
import '../astrology/domain/moon_phase.dart';
import '../astrology/domain/planet.dart';
import '../astrology/domain/transit.dart';
import '../astrology/domain/zodiac_sign.dart';

/// Localized names for astrological entities.
///
/// The services return structured data (enums), never display strings, so this
/// is the single place where astrology vocabulary is translated.
extension AstroLabels on AppLocalizations {
  String planet(Planet planet) => switch (planet) {
    Planet.sun => planetSun,
    Planet.moon => planetMoon,
    Planet.mercury => planetMercury,
    Planet.venus => planetVenus,
    Planet.mars => planetMars,
    Planet.jupiter => planetJupiter,
    Planet.saturn => planetSaturn,
    Planet.uranus => planetUranus,
    Planet.neptune => planetNeptune,
    Planet.pluto => planetPluto,
    Planet.northNode => planetNorthNode,
    Planet.southNode => planetSouthNode,
  };

  String sign(ZodiacSign sign) => switch (sign) {
    ZodiacSign.aries => signAries,
    ZodiacSign.taurus => signTaurus,
    ZodiacSign.gemini => signGemini,
    ZodiacSign.cancer => signCancer,
    ZodiacSign.leo => signLeo,
    ZodiacSign.virgo => signVirgo,
    ZodiacSign.libra => signLibra,
    ZodiacSign.scorpio => signScorpio,
    ZodiacSign.sagittarius => signSagittarius,
    ZodiacSign.capricorn => signCapricorn,
    ZodiacSign.aquarius => signAquarius,
    ZodiacSign.pisces => signPisces,
  };

  String aspect(AspectType type) => switch (type) {
    AspectType.conjunction => aspectConjunction,
    AspectType.sextile => aspectSextile,
    AspectType.square => aspectSquare,
    AspectType.trine => aspectTrine,
    AspectType.opposition => aspectOpposition,
  };

  String moonPhase(MoonPhaseType type) => switch (type) {
    MoonPhaseType.newMoon => moonPhaseNew,
    MoonPhaseType.waxingCrescent => moonPhaseWaxingCrescent,
    MoonPhaseType.firstQuarter => moonPhaseFirstQuarter,
    MoonPhaseType.waxingGibbous => moonPhaseWaxingGibbous,
    MoonPhaseType.fullMoon => moonPhaseFull,
    MoonPhaseType.waningGibbous => moonPhaseWaningGibbous,
    MoonPhaseType.lastQuarter => moonPhaseLastQuarter,
    MoonPhaseType.waningCrescent => moonPhaseWaningCrescent,
  };

  String frequencyCategory(FrequencyCategory category) => switch (category) {
    FrequencyCategory.generalEnergy => metricGeneralEnergy,
    FrequencyCategory.love => metricLove,
    FrequencyCategory.career => metricCareer,
    FrequencyCategory.money => metricMoney,
    FrequencyCategory.mood => metricMood,
    FrequencyCategory.health => metricHealth,
    FrequencyCategory.luck => metricLuck,
  };

  String influenceNature(InfluenceNature nature) => switch (nature) {
    InfluenceNature.supportive => influenceSupportive,
    InfluenceNature.challenging => influenceChallenging,
    InfluenceNature.emotional => influenceEmotional,
    InfluenceNature.lesson => influenceLesson,
    InfluenceNature.neutral => influenceNeutral,
  };

  /// Plain-text rendering of an influence, used for semantics labels and for
  /// anywhere a rich widget is not possible.
  String transitTitle(TransitSummary summary) => switch (summary.shape) {
    TransitShape.aspect => transitAspect(
      planet(summary.transitingPlanet),
      aspect(summary.aspect!),
      planet(summary.natalPlanet!),
    ),
    TransitShape.houseIngress => transitIntoHouse(
      planet(summary.transitingPlanet),
      summary.house!,
    ),
    TransitShape.retrograde => retrogradeOf(planet(summary.transitingPlanet)),
    TransitShape.planetary => planet(summary.transitingPlanet),
  };
}
