import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/astrology/astrology_providers.dart';
import '../../../core/localization/locale_controller.dart';
import '../../../core/network/api_exception.dart';
import '../../billing/application/coin_spend.dart';
import '../data/guides_repository.dart';
import '../domain/guide_models.dart';

/// Thrown when a guide is opened in mock mode, where no fixture exists.
const guidesUnavailable = ApiException(
  kind: ApiErrorKind.validation,
  code: 'demo_unavailable',
);

GuidesRepository _repo(Ref ref) {
  final repo = ref.watch(guidesRepositoryProvider);
  if (repo == null) throw guidesUnavailable;
  return repo;
}

String _locale(Ref ref) => ref.watch(localeControllerProvider).languageCode;

final moonGuideProvider = FutureProvider.autoDispose<MoonGuide>((ref) {
  // Today's guide: reload when the date moves on.
  ref.watch(todayProvider);
  return _repo(ref).moonGuide(locale: _locale(ref));
});

/// What a return chart opened with AstroCoins is remembered as.
String solarReturnUnlockKey(int year) => 'solar_return:$year';
String lunarReturnUnlockKey(DateTime after) =>
    'lunar_return:${after.toIso8601String().substring(0, 10)}';

final solarReturnProvider = FutureProvider.autoDispose
    .family<ReturnReading, int>((ref, year) {
      final repo = _repo(ref);
      final locale = _locale(ref);
      return loadWithCoins(
        ref,
        solarReturnUnlockKey(year),
        (coinRef) => repo.solarReturn(year, locale: locale, coinRef: coinRef),
      );
    });

final lunarReturnProvider = FutureProvider.autoDispose
    .family<ReturnReading, DateTime>((ref, after) {
      final repo = _repo(ref);
      final locale = _locale(ref);
      return loadWithCoins(
        ref,
        lunarReturnUnlockKey(after),
        (coinRef) => repo.lunarReturn(after, locale: locale, coinRef: coinRef),
      );
    });

/// Keyed by an optional full-name override (null = profile name).
final numerologyProvider = FutureProvider.autoDispose
    .family<NumerologyProfile, String?>(
      (ref, name) => _repo(ref).numerology(name: name, locale: _locale(ref)),
    );

final stoneProvider = FutureProvider.autoDispose
    .family<StoneRecommendation, (StoneMode, StoneIntent?)>(
      (ref, query) => _repo(
        ref,
      ).stones(mode: query.$1, intent: query.$2, locale: _locale(ref)),
    );
