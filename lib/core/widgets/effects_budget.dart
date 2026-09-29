import 'package:flutter/foundation.dart';
import 'package:flutter/scheduler.dart';

/// Whether this device can afford decorative motion.
///
/// Every redraw of a screen re-rasters all of it (images, text, layers), so a
/// purely decorative animation costs a full frame each time it changes. On a
/// device that cannot raster the scene within one 60 Hz frame, that cost is
/// most of a CPU core. This watches the engine's own frame timings; when the
/// median raster time stays above [rasterBudget] for two windows in a row
/// (the first window after launch is skipped: shader and image warm-up),
/// [reduced] turns on for the rest of the session and decorative motion (the
/// twinkling star field) holds still. Content, transitions and entrance
/// animations are unaffected.
class EffectsBudget {
  EffectsBudget._();

  /// True once the device has shown it cannot afford decorative motion.
  static final ValueNotifier<bool> reduced = ValueNotifier<bool>(false);

  static const Duration rasterBudget = Duration(milliseconds: 16);
  static const int _window = 30;

  static bool _watching = false;
  static int _windows = 0;
  static int _overBudget = 0;
  static final List<Duration> _raster = <Duration>[];

  /// Starts watching frame timings (once; no-op after [reduced]).
  static void watch() {
    if (_watching || reduced.value) return;
    _watching = true;
    SchedulerBinding.instance.addTimingsCallback(_onTimings);
  }

  static void _onTimings(List<FrameTiming> timings) {
    for (final FrameTiming timing in timings) {
      _raster.add(timing.rasterDuration);
      if (_raster.length < _window) continue;
      final List<Duration> sorted = <Duration>[..._raster]..sort();
      final Duration median = sorted[sorted.length ~/ 2];
      _raster.clear();
      if (_windows++ == 0) continue;
      _overBudget = median > rasterBudget ? _overBudget + 1 : 0;
      if (_overBudget >= 2) {
        // One line, once per session: why the stars hold still here.
        debugPrint(
          'EffectsBudget: decorative motion off '
          '(median raster ${median.inMicroseconds / 1000} ms)',
        );
        reduced.value = true;
        SchedulerBinding.instance.removeTimingsCallback(_onTimings);
        _watching = false;
        return;
      }
    }
  }

  @visibleForTesting
  static void debugTimings(List<FrameTiming> timings) => _onTimings(timings);

  @visibleForTesting
  static void debugReset() {
    if (_watching) SchedulerBinding.instance.removeTimingsCallback(_onTimings);
    _watching = false;
    _windows = 0;
    _overBudget = 0;
    _raster.clear();
    reduced.value = false;
  }
}
