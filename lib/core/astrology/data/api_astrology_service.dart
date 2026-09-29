import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../features/profile/domain/user_profile.dart';
import '../../network/api_client.dart';
import '../../network/api_config.dart';
import '../../network/api_exception.dart';
import '../astrology_service.dart';
import '../domain/astro_ai_context.dart';
import '../domain/birth_data.dart';
import '../domain/cosmic_event.dart';
import '../domain/daily_frequency.dart';
import '../domain/moon_phase.dart';
import '../domain/natal_chart.dart';
import '../domain/synastry_result.dart';
import '../domain/transit.dart';
import 'api_contract_dto.dart';
import 'mock_astrology_service.dart';

/// B1-B4 API adapter. B5 compatibility stays outside this integration phase.
class ApiAstrologyService implements AstrologyService {
  const ApiAstrologyService(this._api);

  final ApiClient _api;

  @override
  Future<NatalChart> getNatalChart(BirthData birthData) async {
    final Map<String, dynamic> json = await _api.postMap(
      'astrology/natal-chart',
      data: <String, dynamic>{
        'birth_date': _dateOnly(birthData.date),
        'birth_time': birthData.time == null
            ? null
            : birthData.time!.length == 5
            ? '${birthData.time}:00'
            : birthData.time,
        'birth_place': birthData.place,
        'latitude': birthData.latitude,
        'longitude': birthData.longitude,
        'timezone': birthData.timezone,
      },
    );
    return NatalChartDto.fromJson(json).toDomain();
  }

  @override
  Future<List<Transit>> getTransits({
    required NatalChart natalChart,
    required DateTime from,
    DateTime? to,
  }) async => (await getTransitWindow(from: from, to: to)).all;

  /// Full grouped B4 response for future transit timeline consumers.
  Future<TransitWindow> getTransitWindow({
    required DateTime from,
    DateTime? to,
  }) async {
    final int days = to?.difference(from).inDays ?? 0;
    final String range = days <= 1
        ? 'day'
        : days <= 7
        ? 'week'
        : days <= 31
        ? 'month'
        : 'year';
    return getTransitWindowByRange(date: from, range: range);
  }

  Future<TransitWindow> getTransitWindowByRange({
    required DateTime date,
    required String range,
    String? coinRef,
  }) async {
    if (!const ['day', 'tomorrow', 'week', 'month', 'year'].contains(range)) {
      throw ArgumentError.value(range);
    }
    final Map<String, dynamic> json = await _api.getMap(
      'astrology/transits',
      queryParameters: <String, dynamic>{
        'date': _dateOnly(date),
        'range': range,
      },
      headers: coinHeader(coinRef),
    );
    try {
      return TransitListDto.fromJson(json).toWindow();
    } on FormatException {
      throw const ApiException(
        kind: ApiErrorKind.validation,
        code: 'client_model_mismatch',
      );
    }
  }

  @override
  Future<DailyFrequency> getDailyFrequency({
    required UserProfile profile,
    required DateTime date,
  }) async {
    final Map<String, dynamic> json = await _api.getMap(
      'astrology/daily-frequency',
      queryParameters: <String, dynamic>{'date': _dateOnly(date)},
    );
    return DailyFrequencyDto.fromJson(json).toDomain();
  }

  @override
  Future<MoonPhase> getMoonPhase({
    required DateTime date,
    NatalChart? natalChart,
  }) async {
    final Map<String, dynamic> json = await _api.getMap(
      'astrology/moon-phase',
      queryParameters: <String, dynamic>{
        'moment': date.toUtc().toIso8601String(),
      },
    );
    return MoonPhaseDto.fromJson(json).toDomain();
  }

  @override
  Future<List<CosmicEvent>> getCosmicCalendar({
    required DateTime from,
    required DateTime to,
    NatalChart? natalChart,
  }) async => (await getCosmicCalendarWindow(from: from, to: to)).events;

  Future<CosmicCalendarWindow> getCosmicCalendarWindow({
    required DateTime from,
    required DateTime to,
  }) async {
    final Map<String, dynamic> json = await _api.getMap(
      'calendar/events',
      queryParameters: <String, dynamic>{
        'start': _dateOnly(from),
        'end': _dateOnly(to),
      },
    );
    try {
      return CosmicCalendarDto.fromJson(json).toWindow();
    } on StateError {
      throw const ApiException(
        kind: ApiErrorKind.validation,
        code: 'client_model_mismatch',
      );
    }
  }

  @override
  Future<AstroAIContext> getAstroAIContext({
    required UserProfile profile,
    DateTime? at,
  }) async {
    final BirthData? birth = profile.birthData;
    if (birth == null) {
      throw const ApiException(
        kind: ApiErrorKind.validation,
        code: 'birth_profile_missing',
      );
    }
    final DateTime moment = at ?? DateTime.now();
    final NatalChart chart = await getNatalChart(birth);
    final List<Transit> transits = await getTransits(
      natalChart: chart,
      from: moment,
    );
    final MoonPhase moon = await getMoonPhase(date: moment);
    return AstroAIContext(
      natalChart: chart,
      activeTransits: transits,
      moon: moon,
      generatedAt: moment,
    );
  }

  @override
  Future<SynastryResult> getSynastry({
    required BirthData personA,
    required BirthData personB,
    CompatibilityMode mode = CompatibilityMode.synastry,
  }) => throw UnsupportedError('B5 compatibility integration is not enabled.');

  static String _dateOnly(DateTime date) =>
      '${date.year.toString().padLeft(4, '0')}-'
      '${date.month.toString().padLeft(2, '0')}-'
      '${date.day.toString().padLeft(2, '0')}';
}

/// Application wiring can override the existing astrology provider with this.
final Provider<AstrologyService> configuredAstrologyServiceProvider =
    Provider<AstrologyService>((Ref ref) {
      final AppEnvironment config = ref.watch(appEnvironmentProvider);
      return config.useMocks
          ? MockAstrologyService()
          : ApiAstrologyService(ApiClient(ref.watch(dioProvider)));
    });
