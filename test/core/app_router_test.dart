import 'package:astrofrekans/features/astro_ai/presentation/astro_ai_screen.dart';
import 'package:astrofrekans/features/auth/presentation/login_screen.dart';
import 'package:astrofrekans/features/home/presentation/home_screen.dart';
import 'package:astrofrekans/features/onboarding/presentation/onboarding_screen.dart';
import 'package:astrofrekans/features/profile/presentation/profile_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';
import 'package:astrofrekans/core/widgets/astro_brand_logo.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('a fresh install lands on onboarding', (
    WidgetTester tester,
  ) async {
    final TestEnv env = await TestEnv.create();
    await pumpApp(tester, env: env);

    expect(find.byType(OnboardingScreen), findsOneWidget);
    expect(find.byType(AstroBrandLogo), findsOneWidget);
    expect(find.text('Hadi Başlayalım'), findsOneWidget);
  });

  testWidgets('after onboarding, an unauthenticated user lands on login', (
    WidgetTester tester,
  ) async {
    final TestEnv env = await TestEnv.create(
      preferences: <String, Object>{'onboarding_seen': true},
    );
    await pumpApp(tester, env: env);

    expect(find.byType(LoginScreen), findsOneWidget);
  });

  testWidgets('an authenticated user lands on the Home tab', (
    WidgetTester tester,
  ) async {
    final TestEnv env = await TestEnv.create(user: testUser);
    await pumpApp(tester, env: env);

    expect(find.byType(HomeScreen), findsOneWidget);
    expect(find.text('Bugün'), findsWidgets);
  });

  testWidgets('bottom navigation switches tabs and keeps their state', (
    WidgetTester tester,
  ) async {
    final TestEnv env = await TestEnv.create(user: testUser);
    await pumpApp(tester, env: env);

    // Go to the Astro AI tab and ask a question.
    await tester.tap(find.text('Astro AI').last);
    await tester.pumpAndSettle();
    expect(find.byType(AstroAiScreen), findsOneWidget);

    await tester.enterText(find.byType(TextField).last, 'Bugün nasıl?');
    await tester.pump();
    await tester.tap(find.byIcon(Icons.send).last);
    await tester.pumpAndSettle();
    await tester.drag(find.byType(ListView).last, const Offset(0, 600));
    await tester.pumpAndSettle();
    expect(find.text('Bugün nasıl?'), findsOneWidget);

    // Switch to Profile, then back: the conversation is still there.
    await tester.tap(find.text('Profil').last);
    await tester.pumpAndSettle();
    expect(find.byType(ProfileScreen), findsOneWidget);

    await tester.tap(find.text('Astro AI').last);
    await tester.pumpAndSettle();
    await tester.dragUntilVisible(
      find.text('Bugün nasıl?'),
      find.byType(ListView).last,
      const Offset(0, 300),
    );
    await tester.pumpAndSettle();
    expect(find.text('Bugün nasıl?'), findsOneWidget);
  });

  testWidgets('signing out returns to login', (WidgetTester tester) async {
    final TestEnv env = await TestEnv.create(
      preferences: <String, Object>{'onboarding_seen': true},
      secure: <String, String>{
        'auth_token': 'mock.test-user',
        'user_profile':
            '{"id":"test-user","name":"Defne Yıldız",'
            '"email":"defne@astrofrekans.test","language":"tr",'
            '"subscription_tier":"free"}',
      },
    );
    await pumpApp(tester, env: env);

    expect(find.byType(HomeScreen), findsOneWidget);

    await tester.tap(find.text('Profil').last);
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(
      find.byKey(const ValueKey('menu-sign-out')).hitTestable(),
      200,
      scrollable: find.byType(Scrollable).last,
    );
    await tester.tap(find.text('Çıkış Yap').last);
    await tester.pumpAndSettle();

    await tester.tap(find.text('Çıkış Yap').last);
    await tester.pumpAndSettle();

    expect(find.byType(LoginScreen), findsOneWidget);
  });
}
