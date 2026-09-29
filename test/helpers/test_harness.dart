import 'package:astrofrekans/app/app.dart';
import 'package:astrofrekans/core/astrology/astrology_providers.dart';
import 'package:astrofrekans/core/astrology/data/mock_astrology_service.dart';
import 'package:astrofrekans/core/storage/app_preferences.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/features/astro_ai/application/astro_ai_controller.dart';
import 'package:astrofrekans/features/astro_ai/data/mock_astro_ai_repository.dart';
import 'package:astrofrekans/features/auth/application/session_controller.dart';
import 'package:astrofrekans/features/profile/domain/user_profile.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Deterministic profile used across tests.
final UserProfile testUser = UserProfile(
  id: 'test-user',
  name: 'Defne Yıldız',
  email: 'defne@astrofrekans.test',
  birthDate: DateTime(1995, 3, 12),
  birthTime: '09:41',
  birthPlace: 'İstanbul, Türkiye',
);

/// Session controller pinned to a signed-in state.
class SignedInSessionController extends SessionController {
  SignedInSessionController(this.user);

  final UserProfile user;

  @override
  SessionState build() => SessionState(
    status: SessionStatus.authenticated,
    user: user,
    onboardingSeen: true,
  );
}

/// The test environment: preferences + secure storage seeds and the clock.
///
/// Riverpod 3 does not export the `Override` type, so override lists are always
/// built inline (where the target type is inferred) instead of being passed
/// around as a typed value.
class TestEnv {
  TestEnv._(this.preferences, this.store, this.today, this.user);

  final AppPreferences preferences;
  final InMemorySecureStore store;
  final DateTime today;
  final UserProfile? user;

  static Future<TestEnv> create({
    UserProfile? user,
    Map<String, Object> preferences = const <String, Object>{},
    Map<String, String> secure = const <String, String>{},
    DateTime? today,
  }) async {
    // Tests run on an en-US host; pin the app language so copy assertions are
    // stable (the app itself falls back to the device language, then Turkish).
    SharedPreferences.setMockInitialValues(<String, Object>{
      'locale_code': 'tr',
      ...preferences,
    });
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    return TestEnv._(
      AppPreferences(prefs),
      InMemorySecureStore(secure),
      today ?? DateTime(2026, 3, 12),
      user,
    );
  }
}

/// Builds a scope with every artificial delay removed.
ProviderScope scopeFor(TestEnv env, {required Widget child}) => ProviderScope(
  overrides: [
    appPreferencesProvider.overrideWithValue(env.preferences),
    secureStoreProvider.overrideWithValue(env.store),
    astrologyServiceProvider.overrideWithValue(
      MockAstrologyService(latency: Duration.zero),
    ),
    astroAIRepositoryProvider.overrideWithValue(
      MockAstroAIRepository(
        wordDelay: Duration.zero,
        thinkingDelay: Duration.zero,
      ),
    ),
    todayProvider.overrideWithValue(env.today),
    if (env.user != null)
      sessionProvider.overrideWith(() => SignedInSessionController(env.user!)),
  ],
  child: child,
);

/// Container for provider-level tests.
ProviderContainer containerFor(TestEnv env) {
  final ProviderContainer container = ProviderContainer.test(
    overrides: [
      appPreferencesProvider.overrideWithValue(env.preferences),
      secureStoreProvider.overrideWithValue(env.store),
      astrologyServiceProvider.overrideWithValue(
        MockAstrologyService(latency: Duration.zero),
      ),
      astroAIRepositoryProvider.overrideWithValue(
        MockAstroAIRepository(
          wordDelay: Duration.zero,
          thinkingDelay: Duration.zero,
        ),
      ),
      todayProvider.overrideWithValue(env.today),
      if (env.user != null)
        sessionProvider.overrideWith(
          () => SignedInSessionController(env.user!),
        ),
    ],
  );
  return container;
}

/// Pumps a single screen with the app theme + localizations, without routing.
Future<void> pumpScreen(
  WidgetTester tester,
  Widget child, {
  required TestEnv env,
  Size size = const Size(390, 844),
  double textScale = 1.0,
  Locale locale = const Locale('tr'),
}) async {
  tester.view.physicalSize = size * tester.view.devicePixelRatio;
  addTearDown(tester.view.reset);
  disableAnimations(tester);

  await tester.pumpWidget(
    scopeFor(
      env,
      child: MaterialApp(
        theme: AppTheme.dark,
        locale: locale,
        supportedLocales: AppLocalizations.supportedLocales,
        localizationsDelegates: const <LocalizationsDelegate<Object>>[
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        builder: (BuildContext context, Widget? widget) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: TextScaler.linear(textScale)),
          child: widget ?? const SizedBox.shrink(),
        ),
        home: Scaffold(backgroundColor: Colors.black, body: child),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

/// Pumps the whole app (router included).
Future<void> pumpApp(
  WidgetTester tester, {
  required TestEnv env,
  Size size = const Size(390, 844),
}) async {
  tester.view.physicalSize = size * tester.view.devicePixelRatio;
  addTearDown(tester.view.reset);
  disableAnimations(tester);

  await tester.pumpWidget(scopeFor(env, child: const AstrofrekansApp()));
  await tester.pumpAndSettle();
}

/// Reduce-motion for tests: repeating animations would keep `pumpAndSettle`
/// spinning forever, and every animated widget in the app honours this flag.
void disableAnimations(WidgetTester tester) {
  tester.binding.platformDispatcher.accessibilityFeaturesTestValue =
      const FakeAccessibilityFeatures(disableAnimations: true);
  addTearDown(
    tester.binding.platformDispatcher.clearAccessibilityFeaturesTestValue,
  );
}
