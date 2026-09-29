import 'package:astrofrekans/core/astrology/astrology_providers.dart';
import 'package:astrofrekans/core/astrology/data/api_astrology_service.dart';
import 'package:astrofrekans/core/astrology/data/mock_astrology_service.dart';
import 'package:astrofrekans/core/astrology/data/production_repository.dart';
import 'package:astrofrekans/core/network/api_config.dart';
import 'package:astrofrekans/core/storage/app_preferences.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/features/astro_ai/application/astro_ai_controller.dart';
import 'package:astrofrekans/features/astro_ai/data/api_astro_ai_repository.dart';
import 'package:astrofrekans/features/astro_ai/data/mock_astro_ai_repository.dart';
import 'package:astrofrekans/features/auth/application/session_controller.dart';
import 'package:astrofrekans/features/auth/data/api_auth_repository.dart';
import 'package:astrofrekans/features/auth/data/mock_auth_repository.dart';
import 'package:astrofrekans/features/auth/data/identity_session.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers/test_harness.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('mock and API defines parse; invalid values fail clearly', () {
    final AppEnvironment mock = AppEnvironment.parse(
      environment: 'development',
      dataSource: 'mock',
      apiBaseUrl: '',
    );
    expect(mock.useMocks, isTrue);
    final AppEnvironment api = AppEnvironment.parse(
      environment: 'staging',
      dataSource: 'api',
      apiBaseUrl: 'https://staging.example.test',
    );
    expect(api.useMocks, isFalse);
    expect(
      () => AppEnvironment.parse(
        environment: 'bad',
        dataSource: 'mock',
        apiBaseUrl: '',
      ),
      throwsFormatException,
    );
    expect(
      () => AppEnvironment.parse(
        environment: 'development',
        dataSource: 'bad',
        apiBaseUrl: '',
      ),
      throwsFormatException,
    );
    expect(
      () => AppEnvironment.parse(
        environment: 'production',
        authMode: 'hybrid',
        dataSource: 'api',
        apiBaseUrl: 'http://example.test',
      ),
      throwsStateError,
    );
    expect(
      () => AppEnvironment.parse(
        environment: 'production',
        authMode: 'hybrid',
        dataSource: 'mock',
        apiBaseUrl: '',
      ),
      throwsStateError,
    );
  });

  test(
    'compile-time data-source define reaches application providers',
    () async {
      SharedPreferences.setMockInitialValues(<String, Object>{
        'locale_code': 'tr',
      });
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final ProviderContainer container = ProviderContainer.test(
        overrides: [
          appPreferencesProvider.overrideWithValue(AppPreferences(prefs)),
          secureStoreProvider.overrideWithValue(InMemorySecureStore()),
        ],
      );
      addTearDown(container.dispose);
      const String define = String.fromEnvironment(
        'APP_DATA_SOURCE',
        defaultValue: 'mock',
      );
      expect(container.read(appEnvironmentProvider).dataSource.name, define);
      if (define == 'api') {
        expect(
          container.read(authRepositoryProvider),
          isA<ApiAuthRepository>(),
        );
        expect(
          container.read(astrologyServiceProvider),
          isA<ApiAstrologyService>(),
        );
      } else {
        expect(
          container.read(authRepositoryProvider),
          isA<MockAuthRepository>(),
        );
        expect(
          container.read(astrologyServiceProvider),
          isA<MockAstrologyService>(),
        );
      }
    },
  );

  for (final AppDataSource source in AppDataSource.values) {
    test('$source selects repositories centrally', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{
        'locale_code': 'tr',
      });
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final ProviderContainer container = ProviderContainer.test(
        overrides: [
          appPreferencesProvider.overrideWithValue(AppPreferences(prefs)),
          secureStoreProvider.overrideWithValue(InMemorySecureStore()),
          appEnvironmentProvider.overrideWithValue(
            AppEnvironment(
              environment: AppEnvironmentName.development,
              apiBaseUrl: 'https://example.test',
              dataSource: source,
              enableDebugTools: false,
            ),
          ),
        ],
      );
      addTearDown(container.dispose);
      if (source == AppDataSource.mock) {
        expect(
          container.read(authRepositoryProvider),
          isA<MockAuthRepository>(),
        );
        expect(
          container.read(astrologyServiceProvider),
          isA<MockAstrologyService>(),
        );
        expect(
          container.read(astroAIRepositoryProvider),
          isA<MockAstroAIRepository>(),
        );
        expect(container.read(productionRepositoryProvider), isNull);
      } else {
        expect(
          container.read(authRepositoryProvider),
          isA<ApiAuthRepository>(),
        );
        expect(
          container.read(astrologyServiceProvider),
          isA<ApiAstrologyService>(),
        );
        expect(
          container.read(astroAIRepositoryProvider),
          isA<ApiAstroAIRepository>(),
        );
        expect(
          container.read(productionRepositoryProvider),
          isA<ProductionRepository>(),
        );
      }
    });
  }

  test('API-mode Astro AI is ready without starting a network call', () async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    final ProviderContainer container = ProviderContainer.test(
      overrides: [
        appPreferencesProvider.overrideWithValue(AppPreferences(prefs)),
        secureStoreProvider.overrideWithValue(InMemorySecureStore()),
        appEnvironmentProvider.overrideWithValue(
          const AppEnvironment(
            environment: AppEnvironmentName.development,
            apiBaseUrl: 'https://example.test',
            dataSource: AppDataSource.api,
            enableDebugTools: false,
          ),
        ),
        sessionProvider.overrideWith(() => SignedInSessionController(testUser)),
      ],
    );
    addTearDown(container.dispose);
    expect(
      container.read(astroAIControllerProvider).status,
      AstroAIStatus.idle,
    );
    final AstroAIState state = container.read(astroAIControllerProvider);
    expect(state.status, AstroAIStatus.idle);
    expect(state.errorKind, isNull);
    expect(state.messages, isEmpty);
  });

  for (final mode in [AuthMode.localJwt, AuthMode.firebase, AuthMode.hybrid]) {
    test(
      'API identity adapter selects $mode without opening Firebase',
      () async {
        SharedPreferences.setMockInitialValues(<String, Object>{});
        final prefs = await SharedPreferences.getInstance();
        final container = ProviderContainer.test(
          overrides: [
            appPreferencesProvider.overrideWithValue(AppPreferences(prefs)),
            secureStoreProvider.overrideWithValue(InMemorySecureStore()),
            appEnvironmentProvider.overrideWithValue(
              AppEnvironment(
                environment: AppEnvironmentName.development,
                apiBaseUrl: 'https://example.test',
                dataSource: AppDataSource.api,
                enableDebugTools: false,
                authMode: mode,
              ),
            ),
          ],
        );
        addTearDown(container.dispose);
        final repository = container.read(authRepositoryProvider);
        expect(repository, isA<IdentitySession>());
        expect(repository, switch (mode) {
          AuthMode.localJwt => isA<LocalJwtAuthAdapter>(),
          AuthMode.firebase => isA<FirebaseAuthAdapter>(),
          AuthMode.hybrid => isA<HybridAuthAdapter>(),
        });
      },
    );
  }
}
