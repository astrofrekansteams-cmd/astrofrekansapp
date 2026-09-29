// Phase 5: a production binary refuses development settings, shows no Google
// sign-in, never runs a staging Firebase project, and offers only the seven
// store products.
import 'dart:async';

import 'package:astrofrekans/core/config/firebase_client.dart';
import 'package:astrofrekans/core/network/api_config.dart';
import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/features/auth/application/session_controller.dart';
import 'package:astrofrekans/features/auth/domain/auth_repository.dart';
import 'package:astrofrekans/features/auth/presentation/widgets/social_auth_row.dart';
import 'package:astrofrekans/features/billing/application/entitlement_controller.dart';
import 'package:astrofrekans/features/billing/data/billing_models.dart';
import 'package:astrofrekans/features/billing/data/billing_repository.dart';
import 'package:astrofrekans/features/billing/data/billing_service.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

AppEnvironment _production(String url, {bool debugTools = false}) =>
    AppEnvironment.parse(
      environment: 'production',
      dataSource: 'api',
      apiBaseUrl: url,
      enableDebugTools: debugTools,
      authMode: 'hybrid',
    );

void main() {
  group('production build configuration', () {
    test('a public https API is accepted', () {
      expect(_production('https://api.astrofrekans.org').isProduction, isTrue);
    });

    test('local, emulator and private addresses are refused', () {
      for (final url in [
        'https://localhost:8000',
        'https://127.0.0.1',
        'https://10.0.2.2:8000',
        'https://10.0.3.2',
        'https://192.168.1.20',
        'https://172.20.0.5',
        'https://api.astrofrekans.local',
        'https://[::1]:8000',
      ]) {
        expect(() => _production(url), throwsStateError, reason: url);
      }
      expect(
        () => _production('http://api.astrofrekans.org'),
        throwsStateError,
      );
    });

    test('mock data and debug tools are refused', () {
      expect(
        () => AppEnvironment.parse(
          environment: 'production',
          dataSource: 'mock',
          apiBaseUrl: '',
        ),
        throwsStateError,
      );
      expect(
        () => _production('https://api.astrofrekans.org', debugTools: true),
        throwsStateError,
      );
    });

    test('staging, dev and emulator Firebase projects are recognised', () {
      for (final id in [
        'astrofrekans-staging',
        'astrofrekans-dev',
        'astrofrekans-test',
        'demo-astrofrekans',
      ]) {
        expect(looksLikeDevFirebaseProject(id), isTrue, reason: id);
      }
      for (final id in ['astrofrekans', 'astrofrekans-prod', 'devotion-app']) {
        expect(looksLikeDevFirebaseProject(id), isFalse, reason: id);
      }
    });
  });

  group('Google sign-in', () {
    Future<void> pump(WidgetTester tester, AppEnvironment environment) =>
        tester.pumpWidget(
          ProviderScope(
            overrides: [
              appEnvironmentProvider.overrideWithValue(environment),
              socialAuthServiceProvider.overrideWithValue(
                const UnconfiguredSocialAuthService(),
              ),
            ],
            child: MaterialApp(
              theme: AppTheme.dark,
              locale: const Locale('en'),
              supportedLocales: AppLocalizations.supportedLocales,
              localizationsDelegates: const [
                AppLocalizations.delegate,
                GlobalMaterialLocalizations.delegate,
                GlobalWidgetsLocalizations.delegate,
                GlobalCupertinoLocalizations.delegate,
              ],
              home: const Scaffold(body: SocialAuthRow()),
            ),
          ),
        );

    testWidgets('production shows no Google button and no "coming soon"', (
      tester,
    ) async {
      final environment = _production('https://api.astrofrekans.org');
      expect(environment.googleSignInEnabled, isFalse);
      await pump(tester, environment);
      expect(find.byKey(const ValueKey('social-google')), findsNothing);
      expect(find.textContaining('Google'), findsNothing);
      // Nothing else to offer on Android: not even the "or" divider.
      expect(find.byType(SocialAuthRow), findsOneWidget);
      expect(find.text('or'), findsNothing);
    });

    testWidgets('development keeps the integration visible', (tester) async {
      await pump(
        tester,
        AppEnvironment.parse(
          environment: 'development',
          dataSource: 'api',
          apiBaseUrl: 'http://10.0.2.2:8000',
        ),
      );
      expect(find.byKey(const ValueKey('social-google')), findsOneWidget);
    });
  });

  test('only the seven store products are ever offered', () async {
    final controller = EntitlementController(_Repository(), _Store());
    await controller.start();
    expect(controller.catalog.map((p) => p.code).toSet(), {
      'premium_monthly',
      'coins_120',
    });
    expect(storeProductCodes, hasLength(7));
    for (final report in oneOffReports) {
      expect(storeProductCodes, isNot(contains(report.code)));
      expect(report.storeId, isEmpty);
    }
    controller.dispose();
  });
}

// ------------------------------------------------------------------ fakes

class _Store implements BillingService {
  final events = StreamController<StorePurchaseEvent>.broadcast();
  @override
  StorePlatform get platform => StorePlatform.google;
  @override
  Stream<StorePurchaseEvent> get purchases => events.stream;
  @override
  Future<bool> available() async => true;
  @override
  Future<List<StoreProduct>> loadProducts(Set<String> ids) async => [
    for (final id in ids)
      StoreProduct(
        id: id,
        title: id,
        localizedPrice: '₺1',
        currencyCode: 'TRY',
      ),
  ];
  @override
  Future<void> buy(CatalogProduct product, String accountToken) async {}
  @override
  Future<List<StorePurchaseEvent>> restore() async => const [];
  @override
  Future<void> complete(StorePurchaseEvent event) async {}
  @override
  void dispose() => events.close();
}

class _Repository implements BillingRepository {
  @override
  Future<BillingAvailability> availability() async => BillingAvailability({
    'apple_configured': true,
    'google_configured': true,
  });
  @override
  Future<ProductCatalog> products(StorePlatform platform) async =>
      ProductCatalog({
        'platform': 'android',
        'items': [
          for (final (code, type) in const [
            ('premium_monthly', 'subscription'),
            ('coins_120', 'consumable'),
            // A misconfigured server listing a legacy product.
            ('natal_report', 'consumable'),
            ('ai_pre_analysis', 'consumable'),
          ])
            {
              'code': code,
              'product_type': type,
              'entitlement_code': code,
              'store_product_id': 'store.$code',
            },
        ],
      });
  @override
  Future<EntitlementSummary> entitlements() async => EntitlementSummary({
    'tier': 'free',
    'premium': false,
    'credits': <String, int>{},
    'capabilities': <String, Object>{},
    'items': <Object>[],
  });
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
