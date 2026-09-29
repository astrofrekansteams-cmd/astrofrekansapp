import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/astrology/data/api_contract_dto.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../auth/application/session_controller.dart';
import '../domain/guide_models.dart';

/// Personal guides client. The server computes everything; mock mode has no
/// fixture for these modules, so the provider is null there and screens show
/// the API-mode notice instead of invented data.
class GuidesRepository {
  const GuidesRepository(this.api);
  final ApiClient api;

  static String _date(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-'
      '${d.month.toString().padLeft(2, '0')}-'
      '${d.day.toString().padLeft(2, '0')}';

  Future<MoonGuide> moonGuide({
    DateTime? moment,
    required String locale,
  }) async => MoonGuide.fromJson(
    await api.getMap(
      'astrology/moon-guide',
      queryParameters: {
        'locale': locale,
        if (moment != null) 'moment': moment.toUtc().toIso8601String(),
      },
    ),
  );

  Future<ReturnReading> solarReturn(
    int year, {
    required String locale,
    String? coinRef,
  }) async => ReturnReading.fromJson(
    await api.getMap(
      'astrology/solar-return',
      queryParameters: {'year': year, 'locale': locale},
      headers: coinHeader(coinRef),
    ),
  );

  Future<ReturnReading> lunarReturn(
    DateTime after, {
    required String locale,
    String? coinRef,
  }) async => ReturnReading.fromJson(
    await api.getMap(
      'astrology/lunar-return',
      queryParameters: {'after': _date(after), 'locale': locale},
      headers: coinHeader(coinRef),
    ),
  );

  Future<NumerologyProfile> numerology({
    String? name,
    DateTime? reference,
    required String locale,
  }) async => NumerologyProfile.fromJson(
    await api.getMap(
      'numerology/me',
      queryParameters: {
        'locale': locale,
        if (name != null && name.trim().isNotEmpty) 'name': name.trim(),
        if (reference != null) 'reference': _date(reference),
      },
    ),
  );

  Future<StoneRecommendation> stones({
    required StoneMode mode,
    StoneIntent? intent,
    required String locale,
  }) async => StoneRecommendation.fromJson(
    await api.getMap(
      'stones/recommendation',
      queryParameters: {
        'mode': mode.name,
        'locale': locale,
        if (intent != null) 'intent': ContractJson.snake(intent.name),
      },
    ),
  );
}

final guidesRepositoryProvider = Provider<GuidesRepository?>((ref) {
  ref.watch(currentUserProvider)?.id;
  return ref.watch(appEnvironmentProvider).useMocks
      ? null
      : GuidesRepository(ApiClient(ref.watch(dioProvider)));
});
