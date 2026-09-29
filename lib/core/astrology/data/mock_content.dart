import 'dart:math' as math;

import '../domain/aspect.dart';
import '../domain/moon_phase.dart';
import '../domain/planet.dart';
import '../domain/transit.dart';

/// Interpretation copy for the mock engine.
///
/// Real interpretations will come from the backend in the user's language;
/// until then this class keeps the demo copy out of the service logic and out
/// of the ARB files (ARB is for UI chrome, not for content).
class MockContent {
  const MockContent._({
    required this.transitHeadlines,
    required this.moonMessages,
    required this.dayMessages,
    required this.levelTitles,
    required this.suggestedPrompts,
  });

  final List<String> transitHeadlines;
  final Map<MoonPhaseType, String> moonMessages;
  final List<String> dayMessages;
  final List<String> levelTitles;
  final List<String> suggestedPrompts;

  factory MockContent.forLanguage(String languageCode) =>
      languageCode == 'en' ? _english : _turkish;

  String moonMessage(MoonPhaseType type) => moonMessages[type]!;

  String dayMessage(int score) =>
      dayMessages[(score ~/ 34).clamp(0, dayMessages.length - 1)];

  String levelTitle(int score) =>
      levelTitles[(score ~/ 34).clamp(0, levelTitles.length - 1)];

  /// The three influence cards shown on Home and under an AI answer.
  List<TransitSummary> transitSummaries({
    required math.Random random,
    required int moonHouse,
  }) => <TransitSummary>[
    TransitSummary(
      id: 'jupiter-trine-venus',
      transitingPlanet: Planet.jupiter,
      aspect: AspectType.trine,
      natalPlanet: Planet.venus,
      nature: InfluenceNature.supportive,
      headline: transitHeadlines[0],
    ),
    TransitSummary(
      id: 'moon-house-$moonHouse',
      transitingPlanet: Planet.moon,
      house: moonHouse,
      nature: InfluenceNature.emotional,
      headline: transitHeadlines[1],
    ),
    TransitSummary(
      id: 'saturn-retrograde',
      transitingPlanet: Planet.saturn,
      isRetrograde: true,
      nature: InfluenceNature.lesson,
      headline: transitHeadlines[2],
    ),
  ];

  static const MockContent _turkish = MockContent._(
    transitHeadlines: <String>[
      'Aşk, bolluk ve fırsatlar için destekleyici bir gün.',
      'Yaratıcılık, aşk ve kendini ifade etme ön planda.',
      'Geçmişi gözden geçir, kalıcı yapılar kur.',
    ],
    moonMessages: <MoonPhaseType, String>{
      MoonPhaseType.newMoon: 'Yeni niyetler için temiz bir sayfa.',
      MoonPhaseType.waxingCrescent: 'Başlattığın şeye küçük adımlar ekle.',
      MoonPhaseType.firstQuarter: 'Kararlılık isteyen bir eşikte olabilirsin.',
      MoonPhaseType.waxingGibbous:
          'Detayları düzeltme ve olgunlaştırma zamanı.',
      MoonPhaseType.fullMoon: 'Görünür olan tamamlanıyor; duygular yüksek.',
      MoonPhaseType.waningGibbous: 'Paylaş, anlat, öğrendiğini aktar.',
      MoonPhaseType.lastQuarter: 'Bırakman gerekeni fark et.',
      MoonPhaseType.waningCrescent: 'Dinlen ve içeri dön.',
    },
    dayMessages: <String>[
      'Bugün sakin bir frekanstasın. Kendine alan aç, zorlamadan ilerle.',
      'Bugün dengeli bir akıştasın. Küçük ama net adımlar iyi sonuç verir.',
      'Bugün, evren seninle aynı ritimde. Cesur adımlar destek buluyor.',
    ],
    levelTitles: <String>['Sakin Frekans', 'Dengeli Frekans', 'Yüksek Frekans'],
    suggestedPrompts: <String>[
      'Aşk hayatım nasıl?',
      'Kariyerimde ne görünüyor?',
      'Bugünün enerjisi ne?',
    ],
  );

  static const MockContent _english = MockContent._(
    transitHeadlines: <String>[
      'A supportive day for love, abundance and opportunity.',
      'Creativity, love and self-expression come forward.',
      'Review the past, build structures that last.',
    ],
    moonMessages: <MoonPhaseType, String>{
      MoonPhaseType.newMoon: 'A clean page for new intentions.',
      MoonPhaseType.waxingCrescent: 'Add small steps to what you started.',
      MoonPhaseType.firstQuarter: 'A threshold that asks for a decision.',
      MoonPhaseType.waxingGibbous: 'Time to refine the details.',
      MoonPhaseType.fullMoon: 'What is visible completes; feelings run high.',
      MoonPhaseType.waningGibbous: 'Share what you have learned.',
      MoonPhaseType.lastQuarter: 'Notice what needs to be released.',
      MoonPhaseType.waningCrescent: 'Rest and turn inward.',
    },
    dayMessages: <String>[
      'You are on a calm frequency today. Make room for yourself.',
      'You are in a balanced flow today. Small, clear steps work well.',
      'Today the universe moves at your rhythm. Bold steps find support.',
    ],
    levelTitles: <String>[
      'Calm Frequency',
      'Balanced Frequency',
      'High Frequency',
    ],
    suggestedPrompts: <String>[
      'How is my love life?',
      'What does my career look like?',
      "What is today's energy?",
    ],
  );
}
