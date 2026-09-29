import 'package:astrofrekans/core/widgets/widgets.dart';
import 'package:astrofrekans/features/home/presentation/home_screen.dart';
import 'package:astrofrekans/features/home/presentation/widgets/frequency_ring.dart';
import 'package:astrofrekans/features/home/presentation/widgets/transit_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('renders the personalised daily frequency', (
    WidgetTester tester,
  ) async {
    final TestEnv env = await TestEnv.create(user: testUser);
    await pumpScreen(tester, const HomeScreen(), env: env);

    // Header
    expect(find.text('Merhaba'), findsOneWidget);
    expect(find.text('Defne'), findsOneWidget);

    // Frequency hero
    expect(find.text('Bugünün Frekansı'), findsOneWidget);
    expect(find.byType(FrequencyRing), findsOneWidget);
    expect(find.text('Aşk'), findsOneWidget);
    expect(find.text('Kariyer'), findsOneWidget);
    expect(find.text('Para'), findsOneWidget);
    expect(find.text('Ruh Hali'), findsOneWidget);

    // Sections
    expect(find.text('Bugün seni etkileyen'), findsOneWidget);
    expect(find.byType(TransitCard), findsNWidgets(3));
    expect(find.text('Astro AI\'ya Sor'), findsOneWidget);
    expect(find.text('Kozmik Takvim'), findsOneWidget);
    expect(find.text('İçsel Rehberlik'), findsOneWidget);
  });

  testWidgets('shows English copy when the locale is English', (
    WidgetTester tester,
  ) async {
    final TestEnv env = await TestEnv.create(user: testUser);
    await pumpScreen(
      tester,
      const HomeScreen(),
      env: env,
      locale: const Locale('en'),
    );

    expect(find.text('Hello'), findsOneWidget);
    expect(find.text("Today's Frequency"), findsOneWidget);
    expect(find.text('Love'), findsOneWidget);
  });

  testWidgets('does not overflow on a small phone with large text', (
    WidgetTester tester,
  ) async {
    final TestEnv env = await TestEnv.create(user: testUser);
    await pumpScreen(
      tester,
      const HomeScreen(),
      env: env,
      // iPhone SE class device.
      size: const Size(320, 568),
      textScale: 1.4,
    );

    expect(tester.takeException(), isNull);

    // Scroll the whole page to force every section through layout.
    final Finder list = find.byType(ListView).first;
    await tester.drag(list, const Offset(0, -1200));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets('quick prompts are tappable chips', (WidgetTester tester) async {
    final TestEnv env = await TestEnv.create(user: testUser);
    await pumpScreen(tester, const HomeScreen(), env: env);

    expect(find.byType(AstroChip), findsWidgets);
    expect(find.text('Aşk hayatım nasıl?'), findsOneWidget);
  });
}
