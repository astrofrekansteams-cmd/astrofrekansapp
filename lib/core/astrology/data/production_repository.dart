import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../network/api_client.dart';
import '../../network/api_config.dart';
import '../../network/api_exception.dart';
import '../domain/forecast.dart';
import '../domain/saved_person.dart';
import 'api_contract_dto.dart';
import 'production_models.dart';
import '../../../features/auth/application/session_controller.dart';

/// B5/B7 client: the backend owns the draw and every chart calculation.
class ProductionRepository {
  const ProductionRepository(this.api);
  final ApiClient api;
  Future<List<SavedPerson>> savedPeople() async => (await api.getList(
    'saved-people',
  )).map((j) => SavedPersonDto.fromJson(j).toDomain()).toList();
  Future<SavedPerson> createPerson(Json data) async => SavedPersonDto.fromJson(
    await api.postMap('saved-people', data: data),
  ).toDomain();
  Future<SavedPerson> person(String id) async {
    final matches = (await savedPeople()).where((p) => p.id == id);
    if (matches.isEmpty) throw const ApiException(kind: ApiErrorKind.notFound);
    return matches.first;
  }

  // B11 still exposes no PATCH/PUT saved-person endpoint. Never delete and
  // recreate silently: existing compatibility snapshots reference that id.
  /// Only the sent keys change; `birth_time: null` marks the time unknown.
  /// Reports already made keep the birth data they were computed from.
  Future<SavedPerson> updatePerson(String id, Json changes) async =>
      SavedPersonDto.fromJson(
        await api.patchMap(
          'saved-people/${Uri.encodeComponent(id)}',
          data: changes,
        ),
      ).toDomain();
  Future<void> deletePerson(String id) =>
      api.delete('saved-people/${Uri.encodeComponent(id)}');
  Future<List<GeoPlace>> geocode(String query) async {
    final response = await api.getMap(
      'geocode',
      queryParameters: {'query': query, 'limit': 6},
    );
    return ContractJson.maps(
      response['results'],
    ).map(GeoPlace.fromJson).toList();
  }

  Future<List<HoraryQuestion>> questions() async =>
      (await api.getList('horary/questions')).map(HoraryQuestion.new).toList();
  Future<HoraryQuestion> question(String id) async => HoraryQuestion(
    await api.getMap('horary/questions/${Uri.encodeComponent(id)}'),
  );
  Future<HoraryQuestion> createQuestion(Json data) async =>
      HoraryQuestion(await api.postMap('horary/questions', data: data));
  Future<HoraryQuestion> calculate(String id) async => HoraryQuestion(
    await api.postMap('horary/questions/${Uri.encodeComponent(id)}/calculate'),
  );
  Future<HoraryAnalysis> analysis(String id) async => HoraryAnalysis(
    await api.getMap('horary/questions/${Uri.encodeComponent(id)}/analysis'),
  );
  Future<SynastryReport> synastry(
    Json personB, {
    Json personA = const {'me': true},
    String? coinRef,
  }) async => SynastryReport(
    await api.postMap(
      'compatibility/synastry',
      data: {'person_a': personA, 'person_b': personB},
      headers: coinHeader(coinRef),
    ),
  );
  Future<RelationshipChart> relationshipChart(
    String kind,
    Json personB, {
    Json personA = const {'me': true},
    String? coinRef,
  }) async {
    if (!const ['composite', 'davison'].contains(kind)) {
      throw ArgumentError.value(kind);
    }
    return RelationshipChart(
      await api.postMap(
        'compatibility/$kind',
        data: {'person_a': personA, 'person_b': personB},
        headers: coinHeader(coinRef),
      ),
    );
  }

  Future<List<DivinationDeck>> decks() async =>
      (await api.getList('divination/decks')).map(DivinationDeck.new).toList();
  Future<List<DivinationSpread>> spreads(DeckType deck, String locale) async =>
      (await api.getList(
        'divination/decks/${deck.name}/spreads',
        queryParameters: {'locale': locale},
      )).map(DivinationSpread.new).toList();

  /// Deprecated: the server picks the cards. The app uses
  /// [createDrawSession] / [revealDrawSession]; kept for compatibility.
  @Deprecated('Use createDrawSession + revealDrawSession (user-pick flow).')
  Future<DivinationReading> draw(
    DeckType deck,
    String spread, {
    String locale = 'tr',
    String? question,
    bool includeOptional = false,
  }) async => DivinationReading(
    await api.postMap(
      'divination/readings',
      data: {
        'deck_type': deck.name,
        'spread_code': spread,
        'locale': locale,
        'question': question,
        'include_optional_items': includeOptional,
      },
    ),
  );

  /// Shuffle face down (user-pick flow). Idempotent per [consumerRef]: a
  /// retry with the same ref returns the same session.
  Future<DrawSession> createDrawSession(
    DeckType deck,
    String spread, {
    required String consumerRef,
    String locale = 'tr',
    String? question,
    bool includeOptional = false,
    bool payWithCoins = false,
  }) async => DrawSession(
    await api.postMap(
      'divination/sessions',
      data: {
        'consumer_ref': consumerRef,
        'deck_type': deck.name,
        'spread_code': spread,
        'locale': locale,
        'question': question,
        'include_optional_items': includeOptional,
        'pay_with_coins': payWithCoins,
      },
    ),
  );
  Future<DrawSession> drawSession(String id) async => DrawSession(
    await api.getMap('divination/sessions/${Uri.encodeComponent(id)}'),
  );

  /// Reveal the picked face-down slots, in pick order.
  Future<DivinationReading> revealDrawSession(
    String id,
    List<int> positions,
  ) async => DivinationReading(
    await api.postMap(
      'divination/sessions/${Uri.encodeComponent(id)}/reveal',
      data: {'positions': positions},
    ),
  );

  Future<DivinationReading> reading(String id) async => DivinationReading(
    await api.getMap('divination/readings/${Uri.encodeComponent(id)}'),
  );
  Future<List<ContractRecord>> readings() async => (await api.getList(
    'divination/readings',
  )).map(ContractRecord.new).toList();

  /// AI reading of a stored compatibility calculation. Answers with the
  /// report (cached) or a job to poll (`status` + `id`).
  Future<Json> interpretCompatibility(
    String reportId, {
    String locale = 'tr',
    bool refresh = false,
  }) => api.postMap(
    'compatibility/reports/${Uri.encodeComponent(reportId)}/interpretation',
    data: {'locale': locale, 'refresh': refresh, 'background': true},
  );
  Future<Json> reportJob(String id) =>
      api.getMap('ai/report-jobs/${Uri.encodeComponent(id)}');
  Future<Json> aiReport(String id) =>
      api.getMap('ai/reports/${Uri.encodeComponent(id)}');

  /// [consumerRef] pays with AstroCoins when the plan does not include AI
  /// deep readings; the same reference is never charged twice.
  Future<Json> interpret(
    String id, {
    String locale = 'tr',
    String? consumerRef,
  }) => api.postMap(
    'divination/readings/${Uri.encodeComponent(id)}/interpret',
    data: {'locale': locale, 'background': true, 'consumer_ref': ?consumerRef},
  );
  Future<HoroscopeForecast> horoscope(String period, DateTime date) async {
    if (!const ['daily', 'weekly'].contains(period)) {
      throw ArgumentError.value(period);
    }
    return ForecastDto.daily(
      await api.getMap(
        'horoscope/$period',
        queryParameters: {'date': date.toIso8601String().substring(0, 10)},
      ),
    ).toHoroscope();
  }

  Future<MonthlyForecast> monthly(DateTime date, {String? coinRef}) async =>
      ForecastDto.monthly(
        await api.getMap(
          'forecasts/monthly',
          queryParameters: {'year': date.year, 'month': date.month},
          headers: coinHeader(coinRef),
        ),
      ).toMonthly();
  Future<AnnualForecast> yearly(int year, {String? coinRef}) async =>
      ForecastDto.annual(
        await api.getMap(
          'forecasts/yearly',
          queryParameters: {'year': year},
          headers: coinHeader(coinRef),
        ),
      ).toAnnual();
  Future<List<ContractRecord>> personalCalendar(DateTime month) async {
    final response = await api.getMap(
      'calendar/personal',
      queryParameters: {
        'start': '${month.year}-${month.month.toString().padLeft(2, '0')}-01',
        'end': DateTime(
          month.year,
          month.month + 1,
        ).toIso8601String().substring(0, 10),
      },
    );
    return ContractJson.maps(
      response['events'],
    ).map(ContractRecord.new).toList();
  }
}

/// New feature mock mode is explicitly unavailable until a demo fixture is
/// supplied; it never opens a transport or pretends a real draw occurred.
final productionRepositoryProvider = Provider<ProductionRepository?>((ref) {
  ref.watch(currentUserProvider)?.id;
  return ref.watch(appEnvironmentProvider).useMocks
      ? null
      : ProductionRepository(ApiClient(ref.watch(dioProvider)));
});
