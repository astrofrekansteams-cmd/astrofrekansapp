import 'package:astrofrekans/core/assets/app_assets.dart';
import 'package:astrofrekans/core/widgets/widgets.dart';
import 'package:astrofrekans/features/onboarding/presentation/onboarding_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import '../helpers/test_harness.dart';

void main() {
  for (final width in [320.0, 430.0, 1280.0]) {
    testWidgets('welcome is scrollable and uses supplied logo at $width', (
      tester,
    ) async {
      final env = await TestEnv.create();
      await pumpScreen(
        tester,
        const OnboardingScreen(),
        env: env,
        size: Size(width, 800),
        textScale: 1.5,
      );
      expect(find.byType(AstroBrandLogo), findsOneWidget);
      expect(
        find.byWidgetPredicate(
          (widget) =>
              widget is AstroImage && widget.asset == AppAssets.entryLogo,
        ),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      await tester.drag(
        find.byType(SingleChildScrollView),
        const Offset(0, -700),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }
  testWidgets('reduced motion reveals content immediately', (tester) async {
    final env = await TestEnv.create();
    await pumpScreen(
      tester,
      const AstroReveal(order: 6, child: Text('Visible')),
      env: env,
    );
    expect(
      tester
          .widget<FadeTransition>(find.byType(FadeTransition).first)
          .opacity
          .value,
      1,
    );
    expect(find.text('Visible'), findsOneWidget);
  });
}
