import 'api_contract_dto.dart';

typedef Json = Map<String, dynamic>;

/// Lossless immutable snapshot. Typed accessors expose contract fields while
/// extensions remain available without flattening away scientific metadata.
class ContractRecord {
  ContractRecord(Json value) : json = _freezeMap(value);
  final Json json;
  String text(String key) => ContractJson.string(json, key);
  String? optionalText(String key) => json[key] as String?;
  double number(String key) => ContractJson.number(json, key);
  List<String> strings(String key) =>
      List<String>.unmodifiable((json[key] as List? ?? []).cast<String>());
  List<ContractRecord> records(String key) => List.unmodifiable(
    ContractJson.maps(json[key] ?? []).map(ContractRecord.new),
  );
  ContractRecord record(String key) =>
      ContractRecord(ContractJson.map(json[key]));
  static Json _freezeMap(Json value) =>
      Map.unmodifiable(value.map((k, v) => MapEntry(k, _freeze(v))));
  static dynamic _freeze(dynamic v) => v is Map
      ? _freezeMap(Map<String, dynamic>.from(v))
      : v is List
      ? List<dynamic>.unmodifiable(v.map(_freeze))
      : v;
}

class HoraryQuestion extends ContractRecord {
  HoraryQuestion(super.value) {
    text('id');
    text('question');
    text('status');
  }
  String get id => text('id');
  String get question => text('question');
  String get status => text('status');
}

class Significator extends ContractRecord {
  Significator(super.value);
  String get planet => text('planet');
  String get role => text('role');
  int get house => json['house'] as int;
  ContractRecord? get essential =>
      json['essential'] == null ? null : record('essential');
  ContractRecord? get accidental =>
      json['accidental'] == null ? null : record('accidental');
}

class HoraryAnalysis extends ContractRecord {
  HoraryAnalysis(super.value) {
    text('question_id');
    querent;
    quesited;
    moon;
  }
  Significator get querent => Significator(ContractJson.map(json['querent']));
  Significator get quesited => Significator(ContractJson.map(json['quesited']));
  Significator? get coSignificator => json['co_significator'] == null
      ? null
      : Significator(ContractJson.map(json['co_significator']));
  ContractRecord get moon => record('moon');
  List<ContractRecord> get receptions => records('receptions');
  List<ContractRecord> get dignities => records('dignity_factors');
  List<ContractRecord> get perfection => records('perfection_factors');
  List<ContractRecord> get obstructions => records('obstruction_factors');
  List<ContractRecord> get warnings => records('warnings');
  List<String> get sourceFactors => strings('source_factors');
  List<String> get notImplemented => strings('not_implemented');
}

class SynastryReport extends ContractRecord {
  SynastryReport(super.value) {
    number('overall_score');
    text('score_semantics');
  }
  int get overallIndex => json['overall_score'] as int;
  String get scoreSemantics => text('score_semantics');
  List<ContractRecord> get themes => records('themes');
  List<ContractRecord> get aspects => records('aspects');
  List<ContractRecord> get overlaysAInB => records('overlays_a_in_b');
  List<ContractRecord> get overlaysBInA => records('overlays_b_in_a');
  List<String> get warnings => strings('warnings');
}

class RelationshipChart extends ContractRecord {
  RelationshipChart(super.value) {
    chart;
    text('kind');
  }

  /// Composite and Davison are event charts: their birth_data is null.
  ChartRecord get chart => ChartRecord(ContractJson.map(json['chart']));
  List<String> get warnings => strings('warnings');
  List<String> get ambiguousMidpoints => strings('ambiguous_midpoints');
  DateTime? get midpointUtc => ContractJson.optionalDate(json, 'midpoint_utc');
}

class ChartRecord extends ContractRecord {
  ChartRecord(super.value) {
    text('kind');
    records('planets');
    records('houses');
  }
  List<ContractRecord> get planets => records('planets');
  List<ContractRecord> get houses => records('houses');
  List<ContractRecord> get aspects => records('aspects');

  /// Null when a birth time or place is unknown: the API then computes no
  /// ascendant/MC (NatalChartResponse.angles is nullable).
  ContractRecord? get angles =>
      json['angles'] == null ? null : record('angles');
  List<String> get warnings => strings('warnings');
  ContractRecord get subject => record('subject');
}

/// One `/geocode` match: coordinates and IANA timezone resolved server-side.
class GeoPlace {
  const GeoPlace({
    required this.displayName,
    required this.latitude,
    required this.longitude,
    this.timezone,
  });

  factory GeoPlace.fromJson(Json json) => GeoPlace(
    displayName: ContractJson.string(json, 'display_name'),
    latitude: ContractJson.number(json, 'latitude'),
    longitude: ContractJson.number(json, 'longitude'),
    timezone: json['timezone'] as String?,
  );

  final String displayName;
  final double latitude;
  final double longitude;
  final String? timezone;
}

enum DeckType { tarot, rune, katina }

class DivinationDeck extends ContractRecord {
  DivinationDeck(super.value) {
    text('deck_type');
    number('item_count');
  }
  String get type => text('deck_type');
  List<String> get spreadCodes => strings('spread_codes');
}

class DivinationSpread extends ContractRecord {
  DivinationSpread(super.value) {
    text('spread_code');
    number('card_count');
  }
  String get code => text('spread_code');
  String get name => text('name');
  int get cardCount => json['card_count'] as int;

  /// general, love, relationship, career, money or spiritual.
  String get theme => optionalText('theme') ?? 'general';
  bool get allowReversed => json['allow_reversed'] as bool? ?? true;
  bool get isQuestionSpread => code.startsWith('question');
  List<String> get positionTitles =>
      records('positions').map((p) => p.text('title')).toList();
}

class DrawnItem extends ContractRecord {
  DrawnItem(super.value) {
    text('item_id');
    text('image_asset_key');
  }
  String get assetKey => text('image_asset_key');
  String get name => text('display_name');
  bool get reversed => text('orientation') == 'reversed';
  String get meaning => text('meaning');
  String get position => text('position_title');
  int get positionIndex => json['position_index'] as int? ?? 0;
  String get positionDescription => optionalText('position_description') ?? '';
  String get contextualMeaning => optionalText('contextual_meaning') ?? '';
  String get shadowMeaning => optionalText('shadow_meaning') ?? '';
  String get symbolism => optionalText('symbolism') ?? '';
  List<String> get keywords => strings('keywords');
}

/// Deterministic whole-spread reading computed by the server.
class SpreadSynthesis extends ContractRecord {
  SpreadSynthesis(super.value);
  String get headline => text('headline');
  List<String> get lines => strings('lines');
  List<String> get flow => strings('flow');
}

class DivinationReading extends ContractRecord {
  DivinationReading(super.value) {
    text('id');
    text('deck_type');
    items;
  }
  String get id => text('id');
  String get deckType => text('deck_type');
  String get spreadName => text('spread_name');
  String get spreadTheme => optionalText('spread_theme') ?? 'general';
  String? get question => optionalText('question');
  DateTime? get drawnAt => ContractJson.optionalDate(json, 'drawn_at');
  bool get hasInterpretation => json['has_interpretation'] as bool? ?? false;
  SpreadSynthesis? get synthesis => json['synthesis'] is Map
      ? SpreadSynthesis(ContractJson.map(json['synthesis']))
      : null;
  List<DrawnItem> get items => List.unmodifiable(
    (ContractJson.maps(json['items']).map(DrawnItem.new).toList()
      ..sort((a, b) => a.positionIndex.compareTo(b.positionIndex))),
  );
}

/// A face-down, server-shuffled deck. Carries only what the client may know:
/// the deck size and the spread - never which item sits in which slot.
class DrawSession extends ContractRecord {
  DrawSession(super.value) {
    text('session_id');
    number('deck_size');
    number('required_selections');
  }
  String get id => text('session_id');
  String get deckType => text('deck_type');
  String get spreadCode => text('spread_code');
  String get spreadName => text('spread_name');
  int get deckSize => json['deck_size'] as int;
  int get requiredSelections => json['required_selections'] as int;
  String get status => text('status');
  bool get isOpen => status == 'open';
  DateTime? get expiresAt => ContractJson.optionalDate(json, 'expires_at');
  String? get readingId => optionalText('reading_id');

  /// AstroCoins charged for this shuffle (0 when the plan covered it).
  int get coinsSpent => json['coins_spent'] as int? ?? 0;

  /// Spread positions in order: (title, description).
  List<(String, String)> get positions => [
    for (final p in records('positions'))
      (p.text('title'), p.optionalText('description') ?? ''),
  ];
}

/// Public B8 DTO only. No expert marketplace UI is enabled in B12A.
class PublicExpert extends ContractRecord {
  PublicExpert(super.value) {
    text('id');
    text('display_name');
    number('rating_average');
  }
  String get displayName => text('display_name');
  int? get fromPriceMinor =>
      (json['from_price'] as Map?)?['amount_minor'] as int?;
  String? get currency => (json['from_price'] as Map?)?['currency'] as String?;
}
