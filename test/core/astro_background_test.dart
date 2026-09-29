// The star field twinkles at a few updates a second, only while it is on the
// visible screen of a resumed app, never with reduced motion, and not on a
// device that cannot afford it.
import 'dart:ui' show FrameTiming;

import 'package:astrofrekans/core/widgets/astro_background.dart';
import 'package:astrofrekans/core/widgets/effects_budget.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

ValueListenable<double> _phase(WidgetTester tester) {
  final CustomPaint paint = tester.widget<CustomPaint>(
    find.descendant(
      of: find.byType(AstroBackground),
      matching: find.byType(CustomPaint),
    ),
  );
  return (paint.painter! as dynamic).phase as ValueListenable<double>;
}

Future<int> _updatesIn(WidgetTester tester, Duration window) async {
  var updates = 0;
  final ValueListenable<double> phase = _phase(tester);
  void count() => updates++;
  phase.addListener(count);
  await tester.pump(window);
  phase.removeListener(count);
  return updates;
}

Widget _app({bool reduceMotion = false, bool tickers = true}) => MediaQuery(
  data: MediaQueryData(disableAnimations: reduceMotion),
  child: TickerMode(
    enabled: tickers,
    child: const Directionality(
      textDirection: TextDirection.ltr,
      child: AstroBackground(asset: null),
    ),
  ),
);

FrameTiming _frame(int rasterMs) => FrameTiming(
  vsyncStart: 0,
  buildStart: 0,
  buildFinish: 1000,
  rasterStart: 1000,
  rasterFinish: 1000 + rasterMs * 1000,
  rasterFinishWallTime: 1000 + rasterMs * 1000,
);

void main() {
  setUp(EffectsBudget.debugReset);
  tearDown(EffectsBudget.debugReset);

  testWidgets('twinkles about 8 times a second, not every frame', (
    tester,
  ) async {
    await tester.pumpWidget(_app());
    final int updates = await _updatesIn(tester, const Duration(seconds: 1));
    expect(updates, inInclusiveRange(7, 9));
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('holds still on a hidden screen (covered route, other tab)', (
    tester,
  ) async {
    await tester.pumpWidget(_app(tickers: false));
    expect(await _updatesIn(tester, const Duration(seconds: 1)), 0);
    await tester.pumpWidget(_app());
    expect(
      await _updatesIn(tester, const Duration(seconds: 1)),
      greaterThan(0),
    );
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('pauses in the background and resumes', (tester) async {
    await tester.pumpWidget(_app());
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    expect(await _updatesIn(tester, const Duration(seconds: 2)), 0);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    expect(
      await _updatesIn(tester, const Duration(seconds: 1)),
      greaterThan(0),
    );
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('reduced motion keeps the stars still', (tester) async {
    await tester.pumpWidget(_app(reduceMotion: true));
    expect(await _updatesIn(tester, const Duration(seconds: 2)), 0);
  });

  testWidgets('a device over the frame budget stops the twinkle', (
    tester,
  ) async {
    await tester.pumpWidget(_app());
    expect(
      await _updatesIn(tester, const Duration(seconds: 1)),
      greaterThan(0),
    );
    // Warm-up window is ignored; then two slow windows in a row.
    EffectsBudget.debugTimings(List.filled(30, _frame(60)));
    expect(EffectsBudget.reduced.value, isFalse);
    EffectsBudget.debugTimings(List.filled(30, _frame(40)));
    expect(EffectsBudget.reduced.value, isFalse);
    EffectsBudget.debugTimings(List.filled(30, _frame(40)));
    expect(EffectsBudget.reduced.value, isTrue);
    await tester.pump();
    expect(await _updatesIn(tester, const Duration(seconds: 2)), 0);
  });

  test('a fast device keeps it', () {
    for (var i = 0; i < 6; i++) {
      EffectsBudget.debugTimings(List.filled(30, _frame(6)));
    }
    // One slow window (a busy moment) is not enough.
    EffectsBudget.debugTimings(List.filled(30, _frame(40)));
    EffectsBudget.debugTimings(List.filled(30, _frame(6)));
    expect(EffectsBudget.reduced.value, isFalse);
  });
}
