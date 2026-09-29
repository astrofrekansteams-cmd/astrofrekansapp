import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/astrology/astrology_providers.dart';
import '../../../core/astrology/data/api_astrology_service.dart';
import '../../../core/astrology/data/production_repository.dart';
import '../../../core/astrology/domain/natal_chart.dart';
import '../../../core/astrology/domain/transit.dart';
import '../../../core/astrology/domain/cosmic_event.dart';
import '../../../core/astrology/domain/saved_person.dart';
import '../../../core/astrology/data/production_models.dart';
import '../../../core/network/api_exception.dart';
import '../../auth/application/session_controller.dart';
import '../../billing/application/coin_spend.dart';

final natalProvider = FutureProvider<NatalChart>((ref) async {
  final birth = ref.watch(currentUserProvider)?.birthData;
  if (birth == null) {
    throw const ApiException(
      kind: ApiErrorKind.validation,
      code: 'birth_profile_missing',
    );
  }
  return ref.watch(astrologyServiceProvider).getNatalChart(birth);
});

/// What a transit window opened with AstroCoins is remembered as.
String transitUnlockKey(DateTime date, String range) =>
    'advanced_transits:$range:${date.toIso8601String().substring(0, 10)}';

final transitWindowProvider = FutureProvider.autoDispose
    .family<TransitWindow, (DateTime, String)>((ref, query) async {
      final service = ref.watch(astrologyServiceProvider);
      if (service is ApiAstrologyService) {
        return loadWithCoins(
          ref,
          transitUnlockKey(query.$1, query.$2),
          (coinRef) => service.getTransitWindowByRange(
            date: query.$1,
            range: query.$2,
            coinRef: coinRef,
          ),
        );
      }
      final chart = await ref.watch(natalProvider.future);
      final items = await service.getTransits(
        natalChart: chart,
        from: query.$1,
      );
      return TransitWindow(
        startAt: query.$1,
        endAt: query.$1.add(const Duration(days: 1)),
        reference: query.$1,
        timezone: 'UTC',
        range: query.$2,
        active: items,
        approaching: [],
        upcoming: [],
        ingresses: [],
        engineVersion: 'demo',
        scoringVersion: 'demo',
        cached: false,
      );
    });
final calendarProvider = FutureProvider.autoDispose
    .family<List<CosmicEvent>, DateTime>(
      (ref, month) => ref
          .watch(astrologyServiceProvider)
          .getCosmicCalendar(
            from: DateTime(month.year, month.month),
            to: DateTime(month.year, month.month + 1),
          ),
    );
final personalCalendarProvider = FutureProvider.autoDispose
    .family<List<ContractRecord>, DateTime>(
      (ref, month) async =>
          await ref
              .watch(productionRepositoryProvider)
              ?.personalCalendar(month) ??
          <ContractRecord>[],
    );
final savedPeopleProvider = FutureProvider.autoDispose<List<SavedPerson>>(
  (ref) async =>
      await ref.watch(productionRepositoryProvider)?.savedPeople() ??
      <SavedPerson>[],
);
final horaryQuestionsProvider =
    FutureProvider.autoDispose<List<HoraryQuestion>>(
      (ref) async =>
          await ref.watch(productionRepositoryProvider)?.questions() ??
          <HoraryQuestion>[],
    );
final horaryAnalysisProvider = FutureProvider.autoDispose.family(
  (ref, String id) async =>
      ref.watch(productionRepositoryProvider)!.analysis(id),
);
