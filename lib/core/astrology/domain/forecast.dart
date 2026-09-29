import 'cosmic_event.dart';
import 'daily_frequency.dart';
import 'house_ingress.dart';
import 'planet.dart';
import 'transit.dart';

class ForecastImportantDate {
  const ForecastImportantDate({
    required this.date,
    required this.label,
    required this.strength,
    required this.nature,
    required this.factorIds,
  });
  final DateTime date;
  final String label;
  final int strength;
  final String nature;
  final List<String> factorIds;
}

class ForecastPeriod {
  const ForecastPeriod({
    required this.startAt,
    required this.endAt,
    required this.areas,
    required this.strength,
    required this.label,
    required this.sourceFactors,
  });
  final DateTime startAt;
  final DateTime endAt;
  final List<LifeArea> areas;
  final int strength;
  final String label;
  final List<String> sourceFactors;
}

class HouseActivation {
  const HouseActivation({
    required this.house,
    required this.planets,
    required this.strength,
    required this.factorIds,
  });
  final int house;
  final List<Planet> planets;
  final int strength;
  final List<String> factorIds;
}

class NatalContact {
  const NatalContact({
    this.targetBody,
    this.targetAngle,
    this.rawTargetAngle,
    required this.aspect,
    required this.orb,
  });
  final Planet? targetBody;
  final ChartAngle? targetAngle;
  final String? rawTargetAngle;
  final String aspect;
  final double orb;
}

class PersonalForecastEvent {
  const PersonalForecastEvent({
    required this.event,
    this.affectedHouse,
    required this.natalAspects,
    required this.strength,
    required this.personalRelevance,
    required this.sourceFactors,
  });
  final CosmicEvent event;
  final int? affectedHouse;
  final List<NatalContact> natalAspects;
  final int strength;
  final String personalRelevance;
  final List<String> sourceFactors;
}

class SolarReturnSummary {
  const SolarReturnSummary({
    required this.year,
    required this.exactAt,
    this.ascendant,
    this.ascendantSign,
    this.sunHouse,
  });
  final int year;
  final DateTime exactAt;
  final double? ascendant;
  final String? ascendantSign;
  final int? sunHouse;
}

/// Structured daily/weekly HoroscopeResponse; no generated AI prose.
class HoroscopeForecast {
  const HoroscopeForecast({
    required this.period,
    required this.startAt,
    required this.endAt,
    required this.timezone,
    required this.overallScore,
    required this.areas,
    required this.importantDates,
    required this.importantHours,
    required this.opportunities,
    required this.challenges,
    required this.majorTransits,
    required this.moonEvents,
    required this.houseActivations,
    required this.keyPeriods,
    required this.sourceFactors,
    required this.engineVersion,
    required this.scoringVersion,
    required this.cached,
  });
  final String period;
  final DateTime startAt;
  final DateTime endAt;
  final String timezone;
  final int overallScore;
  final List<AreaScore> areas;
  final List<ForecastImportantDate> importantDates;
  final List<ImportantHour> importantHours;
  final List<String> opportunities;
  final List<String> challenges;
  final List<Transit> majorTransits;
  final List<CosmicEvent> moonEvents;
  final List<HouseActivation> houseActivations;
  final List<ForecastPeriod> keyPeriods;
  final List<SourceFactor> sourceFactors;
  final String engineVersion;
  final String scoringVersion;
  final bool cached;
}

class MonthlyForecast {
  const MonthlyForecast({
    required this.year,
    required this.month,
    required this.startAt,
    required this.endAt,
    required this.timezone,
    required this.overall,
    required this.areas,
    required this.generalTheme,
    required this.keyPeriods,
    required this.importantDates,
    required this.opportunities,
    required this.challenges,
    required this.majorTransits,
    required this.moonEvents,
    required this.retrogrades,
    required this.houseActivations,
    required this.personalEvents,
    required this.sourceFactors,
    required this.engineVersion,
    required this.scoringVersion,
    required this.cached,
  });
  final int year;
  final int month;
  final DateTime startAt;
  final DateTime endAt;
  final String timezone;
  final int overall;
  final List<AreaScore> areas;
  final List<LifeArea> generalTheme;
  final List<ForecastPeriod> keyPeriods;
  final List<ForecastImportantDate> importantDates;
  final List<String> opportunities;
  final List<String> challenges;
  final List<Transit> majorTransits;
  final List<CosmicEvent> moonEvents;
  final List<CosmicEvent> retrogrades;
  final List<HouseActivation> houseActivations;
  final List<PersonalForecastEvent> personalEvents;
  final List<SourceFactor> sourceFactors;
  final String engineVersion;
  final String scoringVersion;
  final bool cached;
}

class AnnualForecast {
  const AnnualForecast({
    required this.year,
    required this.startAt,
    required this.endAt,
    required this.timezone,
    required this.overall,
    required this.areas,
    required this.majorTransits,
    required this.retrogradePeriods,
    required this.eclipses,
    required this.jupiterMovements,
    required this.saturnMovements,
    required this.outerPlanetHits,
    required this.houseActivations,
    required this.keyPeriods,
    required this.importantDates,
    this.solarReturn,
    required this.sourceFactors,
    required this.engineVersion,
    required this.scoringVersion,
    required this.cached,
  });
  final int year;
  final DateTime startAt;
  final DateTime endAt;
  final String timezone;
  final int overall;
  final List<AreaScore> areas;
  final List<Transit> majorTransits;
  final List<CosmicEvent> retrogradePeriods;
  final List<CosmicEvent> eclipses;
  final List<HouseIngress> jupiterMovements;
  final List<HouseIngress> saturnMovements;
  final List<Transit> outerPlanetHits;
  final List<HouseActivation> houseActivations;
  final List<ForecastPeriod> keyPeriods;
  final List<ForecastImportantDate> importantDates;
  final SolarReturnSummary? solarReturn;
  final List<SourceFactor> sourceFactors;
  final String engineVersion;
  final String scoringVersion;
  final bool cached;
}
