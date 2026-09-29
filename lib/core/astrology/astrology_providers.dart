import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../localization/locale_controller.dart';
import '../network/api_client.dart';
import '../network/api_config.dart';
import 'astrology_service.dart';
import 'data/api_astrology_service.dart';
import 'data/mock_astrology_service.dart';

/// The wall clock, injectable so a test can move time.
final Provider<DateTime Function()> clockProvider =
    Provider<DateTime Function()>((Ref ref) => DateTime.now);

DateTime _dateOnly(DateTime moment) =>
    DateTime(moment.year, moment.month, moment.day);

/// Today's local date, kept current while the app stays open.
///
/// An app left open across midnight must not keep showing yesterday: a timer
/// fires just after local midnight, and returning to the app (resume) checks
/// again - a timer does not run while the phone sleeps. Everything that
/// watches [todayProvider] (daily frequency, the Moon, the header date)
/// reloads when the date moves.
class CurrentDayController extends Notifier<DateTime> {
  Timer? _timer;
  AppLifecycleListener? _lifecycle;

  @override
  DateTime build() {
    final DateTime Function() clock = ref.watch(clockProvider);
    ref.onDispose(() {
      _timer?.cancel();
      _lifecycle?.dispose();
      _lifecycle = null;
    });
    _listenForResume();
    final DateTime now = clock();
    _schedule(now);
    return _dateOnly(now);
  }

  void _listenForResume() {
    if (_lifecycle != null) return;
    try {
      _lifecycle = AppLifecycleListener(onResume: check);
    } on Object {
      // No widgets binding (a plain unit test): the midnight timer still runs.
    }
  }

  void _schedule(DateTime now) {
    _timer?.cancel();
    final DateTime nextMidnight = DateTime(now.year, now.month, now.day + 1);
    // A little after midnight, so a clock that is a hair behind still lands
    // on the new day.
    _timer = Timer(
      nextMidnight.difference(now) + const Duration(seconds: 2),
      check,
    );
  }

  /// Re-read the clock; move to the new day if it has changed.
  void check() {
    final DateTime now = ref.read(clockProvider)();
    final DateTime today = _dateOnly(now);
    if (today != state) state = today;
    _schedule(now);
  }
}

final NotifierProvider<CurrentDayController, DateTime> currentDayProvider =
    NotifierProvider<CurrentDayController, DateTime>(CurrentDayController.new);

/// "Today" as a plain date. Tests override this directly to pin a date.
final Provider<DateTime> todayProvider = Provider<DateTime>(
  (Ref ref) => ref.watch(currentDayProvider),
);

/// One data-source decision shared by all astrology consumers.
final Provider<AstrologyService> astrologyServiceProvider =
    Provider<AstrologyService>((Ref ref) {
      final AppEnvironment environment = ref.watch(appEnvironmentProvider);
      if (!environment.useMocks) {
        return ApiAstrologyService(ApiClient(ref.watch(dioProvider)));
      }
      final String language = ref.watch(localeControllerProvider).languageCode;
      return MockAstrologyService(languageCode: language);
    });
