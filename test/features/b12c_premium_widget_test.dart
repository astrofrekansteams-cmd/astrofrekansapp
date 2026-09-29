import 'package:astrofrekans/features/billing/application/entitlement_controller.dart';
import 'package:astrofrekans/features/billing/data/billing_models.dart';
import 'package:astrofrekans/features/billing/data/billing_repository.dart';
import 'package:astrofrekans/features/billing/data/billing_service.dart';
import 'package:astrofrekans/features/billing/data/coin_models.dart';
import 'package:astrofrekans/features/billing/data/coin_repository.dart';
import 'package:astrofrekans/features/billing/presentation/premium_screen.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  for (final scale in [1.6, 2.0]) {
    testWidgets('premium verified status remains readable at ${scale}x', (
      tester,
    ) async {
      final controller = EntitlementController(
        _FreeBilling(),
        const DisabledBillingService(),
      );
      await controller.start();
      final watch = Stopwatch()..start();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            entitlementControllerProvider.overrideWithValue(controller),
            coinCatalogProvider.overrideWith((ref) async => _catalog),
          ],
          child: MediaQuery(
            data: MediaQueryData(textScaler: TextScaler.linear(scale)),
            child: const MaterialApp(
              locale: Locale('tr'),
              supportedLocales: AppLocalizations.supportedLocales,
              localizationsDelegates: [
                AppLocalizations.delegate,
                GlobalMaterialLocalizations.delegate,
                GlobalWidgetsLocalizations.delegate,
                GlobalCupertinoLocalizations.delegate,
              ],
              home: PremiumScreen(),
            ),
          ),
        ),
      );
      await tester.pump();
      watch.stop();
      // ignore: avoid_print
      print(
        'B12C_HOST_PERF premium_${scale}x_initial_widget=${watch.elapsedMilliseconds}ms',
      );
      await tester.pump();
      await tester.scrollUntilVisible(
        find.byKey(const ValueKey('plan-status')),
        150,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Mevcut plan: Ücretsiz'), findsOneWidget);
      for (final tier in ['premium', 'cosmic_plus']) {
        await tester.scrollUntilVisible(
          find.byKey(ValueKey('plan-$tier')),
          150,
          scrollable: find.byType(Scrollable).first,
        );
      }
      expect(find.text('Kozmik+'), findsOneWidget);
      expect(find.text('Sinastri, Composite ve Davison'), findsOneWidget);
      expect(find.text('Aylık öngörü'), findsNWidgets(2));
      // The store-unavailable state sits above the plans it applies to.
      await tester.scrollUntilVisible(
        find.byKey(const ValueKey('plans-store-unavailable')),
        -150,
        scrollable: find.byType(Scrollable).first,
      );
      expect(
        find.textContaining(
          'Mağaza ürünleri bu ortamda kullanılamıyor',
          skipOffstage: false,
        ),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      controller.dispose();
    });
  }
}

class _FreeBilling extends Fake implements BillingRepository {
  @override
  Future<EntitlementSummary> entitlements() async => EntitlementSummary({
    'tier': 'free',
    'premium': false,
    'credits': <String, int>{},
    'items': <Map<String, dynamic>>[],
  });
}

final _catalog = CoinCatalog({
  'spend_items': [
    {'code': 'extra_draw', 'price': 10, 'available': true},
  ],
  'coin_packs': [
    {'product_code': 'coins_120', 'coins': 120},
  ],
  'plans': [
    {
      'tier': 'free',
      'products': <String>[],
      'daily_draws': 3,
      'monthly_coins': 0,
      'ad_free': false,
      'ad_rewards': true,
      'features': <String>[],
      'includes_paid_reports': false,
    },
    {
      'tier': 'premium',
      'products': ['premium_monthly', 'premium_yearly'],
      'daily_draws': 15,
      'monthly_coins': 150,
      'ad_free': true,
      'ad_rewards': false,
      'features': ['monthly_forecast', 'advanced_transits', 'advanced_tarot'],
      'includes_paid_reports': false,
    },
    {
      'tier': 'cosmic_plus',
      'products': ['cosmic_plus_monthly', 'cosmic_plus_yearly'],
      'daily_draws': 40,
      'monthly_coins': 500,
      'ad_free': true,
      'ad_rewards': false,
      'features': [
        'monthly_forecast',
        'advanced_transits',
        'synastry',
        'yearly_forecast',
        'solar_return',
        'advanced_ai',
      ],
      'includes_paid_reports': true,
    },
  ],
});
