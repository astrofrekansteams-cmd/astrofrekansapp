import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/astrology/astrology_providers.dart';
import '../../../core/astrology/astrology_service.dart';
import '../../../core/astrology/domain/daily_frequency.dart';
import '../../../core/astrology/domain/moon_phase.dart';
import '../../auth/application/session_controller.dart';
import '../../profile/domain/user_profile.dart';

/// Home view-model: the personalised daily frequency for the signed-in user.
///
/// It is a [FutureProvider] on purpose - the screen only needs data plus
/// loading/error states, and Riverpod already models that.
/// Today's Moon (phase + sign) for the Home calendar card. Read from the
/// existing moon-phase endpoint; the daily-frequency payload carries only the
/// Moon's sign and house.
final FutureProvider<MoonPhase> homeMoonProvider = FutureProvider<MoonPhase>(
  // Watches the day, so the Moon card moves on at midnight with the rest.
  (Ref ref) => ref
      .watch(astrologyServiceProvider)
      .getMoonPhase(date: ref.watch(todayProvider)),
);

final FutureProvider<DailyFrequency> dailyFrequencyProvider =
    FutureProvider<DailyFrequency>((Ref ref) async {
      final UserProfile? user = ref.watch(currentUserProvider);
      if (user == null) {
        throw StateError('Daily frequency requested without a signed-in user');
      }
      final AstrologyService service = ref.watch(astrologyServiceProvider);
      final DateTime today = ref.watch(todayProvider);
      return service.getDailyFrequency(profile: user, date: today);
    });
