import 'package:flutter/foundation.dart';

import '../../../core/astrology/data/api_contract_dto.dart';
import '../../../core/astrology/data/production_models.dart';
import '../../../core/astrology/domain/moon_phase.dart';
import '../../../core/astrology/domain/planet.dart';
import '../../../core/astrology/domain/zodiac_sign.dart';

/// Typed contracts for `/astrology/moon-guide`, `/astrology/solar-return`,
/// `/astrology/lunar-return`, `/numerology/me` and `/stones/recommendation`.
/// Every number is computed server-side; these classes only carry it.

@immutable
class MoonAspect {
  const MoonAspect({
    required this.body,
    required this.aspect,
    required this.orb,
    required this.applying,
    required this.nature,
    required this.toNatal,
  });

  factory MoonAspect.fromJson(Json json) => MoonAspect(
    body: ContractJson.bySnake(Planet.values, json['body'] as String),
    aspect: json['aspect'] as String,
    orb: ContractJson.number(json, 'orb'),
    applying: json['applying'] as bool? ?? false,
    nature: json['nature'] as String? ?? 'neutral',
    toNatal: json['to_natal'] as bool? ?? false,
  );

  final Planet body;
  final String aspect;
  final double orb;
  final bool applying;
  final String nature;
  final bool toNatal;

  Json toJson() => {
    'body': ContractJson.snake(body.name),
    'aspect': aspect,
    'orb': orb,
    'applying': applying,
    'nature': nature,
    'to_natal': toNatal,
  };
}

@immutable
class MoonGuide {
  const MoonGuide({
    required this.moment,
    required this.sign,
    required this.degree,
    required this.phase,
    required this.illumination,
    required this.ageDays,
    required this.nextPhase,
    required this.nextPhaseAt,
    required this.nextSign,
    required this.nextSignAt,
    required this.natalHouse,
    required this.skyAspects,
    required this.natalAspects,
    required this.goodFor,
    required this.carefulWith,
    required this.summary,
  });

  factory MoonGuide.fromJson(Json json) => MoonGuide(
    moment: ContractJson.date(json, 'moment'),
    sign: ContractJson.bySnake(ZodiacSign.values, json['sign'] as String),
    degree: ContractJson.number(json, 'degree'),
    phase: ContractJson.bySnake(MoonPhaseType.values, json['phase'] as String),
    illumination: ContractJson.number(json, 'illumination'),
    ageDays: ContractJson.number(json, 'age_days'),
    nextPhase: json['next_phase'] == null
        ? null
        : ContractJson.bySnake(
            MoonPhaseType.values,
            json['next_phase'] as String,
          ),
    nextPhaseAt: ContractJson.optionalDate(json, 'next_phase_at'),
    nextSign: ContractJson.bySnake(
      ZodiacSign.values,
      json['next_sign'] as String,
    ),
    nextSignAt: ContractJson.optionalDate(json, 'next_sign_at'),
    natalHouse: json['natal_house'] as int?,
    skyAspects: ContractJson.maps(
      json['sky_aspects'],
    ).map(MoonAspect.fromJson).toList(),
    natalAspects: ContractJson.maps(
      json['natal_aspects'],
    ).map(MoonAspect.fromJson).toList(),
    goodFor: (json['good_for'] as List? ?? []).cast<String>(),
    carefulWith: (json['careful_with'] as List? ?? []).cast<String>(),
    summary: json['summary'] as String? ?? '',
  );

  final DateTime moment;
  final ZodiacSign sign;
  final double degree;
  final MoonPhaseType phase;
  final double illumination;
  final double ageDays;
  final MoonPhaseType? nextPhase;
  final DateTime? nextPhaseAt;
  final ZodiacSign nextSign;
  final DateTime? nextSignAt;
  final int? natalHouse;
  final List<MoonAspect> skyAspects;
  final List<MoonAspect> natalAspects;
  final List<String> goodFor;
  final List<String> carefulWith;
  final String summary;
}

@immutable
class ReturnTheme {
  const ReturnTheme({
    required this.headline,
    required this.lines,
    required this.focusHouses,
    required this.angularPlanets,
    required this.ascendantInNatalHouse,
  });

  factory ReturnTheme.fromJson(Json json) => ReturnTheme(
    headline: json['headline'] as String? ?? '',
    lines: (json['lines'] as List? ?? []).cast<String>(),
    focusHouses: (json['focus_houses'] as List? ?? []).cast<int>(),
    angularPlanets: [
      for (final p in (json['angular_planets'] as List? ?? []))
        ContractJson.bySnake(Planet.values, p as String),
    ],
    ascendantInNatalHouse: json['ascendant_in_natal_house'] as int?,
  );

  final String headline;
  final List<String> lines;
  final List<int> focusHouses;
  final List<Planet> angularPlanets;
  final int? ascendantInNatalHouse;
}

/// A solar or lunar return: the return instant, the chart cast for it and
/// the deterministic theme read from its placements.
@immutable
class ReturnReading {
  const ReturnReading({
    required this.kind,
    required this.moment,
    required this.chart,
    required this.theme,
  });

  factory ReturnReading.fromJson(Json json) => ReturnReading(
    kind: json['kind'] as String,
    moment: ContractJson.date(json, 'moment'),
    chart: ChartRecord(ContractJson.map(json['chart'])),
    theme: ReturnTheme.fromJson(ContractJson.map(json['theme'])),
  );

  final String kind;
  final DateTime moment;
  final ChartRecord chart;
  final ReturnTheme theme;
  bool get isSolar => kind == 'solar_return';
}

@immutable
class NumberMeaning {
  const NumberMeaning({
    required this.number,
    required this.isMaster,
    required this.title,
    required this.keywords,
    required this.meaning,
  });

  factory NumberMeaning.fromJson(Json json) => NumberMeaning(
    number: json['number'] as int,
    isMaster: json['is_master'] as bool? ?? false,
    title: json['title'] as String? ?? '',
    keywords: json['keywords'] as String? ?? '',
    meaning: json['meaning'] as String? ?? '',
  );

  final int number;
  final bool isMaster;
  final String title;
  final String keywords;
  final String meaning;
}

@immutable
class NumerologyProfile {
  const NumerologyProfile({
    required this.nameUsed,
    required this.birthDate,
    required this.reference,
    required this.numbers,
  });

  /// Keys in display order; each maps to a server field of the same name.
  static const keys = <String>[
    'life_path',
    'destiny',
    'soul_urge',
    'personality',
    'birthday',
    'personal_year',
    'personal_month',
  ];

  factory NumerologyProfile.fromJson(Json json) => NumerologyProfile(
    nameUsed: json['name_used'] as String? ?? '',
    birthDate: ContractJson.date(json, 'birth_date'),
    reference: ContractJson.date(json, 'reference'),
    numbers: {
      for (final key in keys)
        key: NumberMeaning.fromJson(ContractJson.map(json[key])),
    },
  );

  final String nameUsed;
  final DateTime birthDate;
  final DateTime reference;
  final Map<String, NumberMeaning> numbers;
}

enum StoneIntent {
  love,
  money,
  career,
  calm,
  motivation,
  communication,
  protection,
  confidence,
  meditation,
}

enum StoneMode { today, personal }

@immutable
class StoneReason {
  const StoneReason({
    required this.kind,
    required this.weight,
    required this.text,
  });
  factory StoneReason.fromJson(Json json) => StoneReason(
    kind: json['kind'] as String,
    weight: json['weight'] as int,
    text: json['text'] as String,
  );
  final String kind;
  final int weight;
  final String text;
}

@immutable
class Stone {
  const Stone({
    required this.key,
    required this.name,
    required this.color,
    required this.elements,
    required this.planets,
    required this.intents,
    required this.note,
  });

  factory Stone.fromJson(Json json) => Stone(
    key: json['key'] as String,
    name: json['name'] as String,
    color: json['color'] as String,
    elements: (json['elements'] as List? ?? []).cast<String>(),
    planets: [
      for (final p in (json['planets'] as List? ?? []))
        ContractJson.bySnake(Planet.values, p as String),
    ],
    intents: [
      for (final i in (json['intents'] as List? ?? []))
        ContractJson.bySnake(StoneIntent.values, i as String),
    ],
    note: json['note'] as String? ?? '',
  );

  final String key;
  final String name;

  /// `#RRGGBB`, from the server catalogue.
  final String color;
  final List<String> elements;
  final List<Planet> planets;
  final List<StoneIntent> intents;
  final String note;

  int get colorValue =>
      0xFF000000 | int.parse(color.replaceFirst('#', ''), radix: 16);
}

@immutable
class StoneSuggestion {
  const StoneSuggestion({
    required this.stone,
    required this.score,
    required this.reasons,
  });
  factory StoneSuggestion.fromJson(Json json) => StoneSuggestion(
    stone: Stone.fromJson(ContractJson.map(json['stone'])),
    score: json['score'] as int,
    reasons: ContractJson.maps(
      json['reasons'],
    ).map(StoneReason.fromJson).toList(),
  );
  final Stone stone;
  final int score;
  final List<StoneReason> reasons;
}

@immutable
class StoneRecommendation {
  const StoneRecommendation({
    required this.mode,
    required this.intent,
    required this.elementBalance,
    required this.weakestElements,
    required this.suggestions,
    required this.disclaimer,
  });

  factory StoneRecommendation.fromJson(Json json) => StoneRecommendation(
    mode: ContractJson.bySnake(StoneMode.values, json['mode'] as String),
    intent: json['intent'] == null
        ? null
        : ContractJson.bySnake(StoneIntent.values, json['intent'] as String),
    elementBalance: {
      for (final e in (json['element_balance'] as Map? ?? {}).entries)
        e.key as String: e.value as int,
    },
    weakestElements: (json['weakest_elements'] as List? ?? []).cast<String>(),
    suggestions: ContractJson.maps(
      json['suggestions'],
    ).map(StoneSuggestion.fromJson).toList(),
    disclaimer: json['disclaimer'] as String? ?? '',
  );

  final StoneMode mode;
  final StoneIntent? intent;
  final Map<String, int> elementBalance;
  final List<String> weakestElements;
  final List<StoneSuggestion> suggestions;
  final String disclaimer;
}
