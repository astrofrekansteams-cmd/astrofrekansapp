// Regression coverage for subscription visibility and required plan badges.
import 'package:astrofrekans/features/billing/application/entitlement_service.dart';
import 'package:astrofrekans/features/billing/data/coin_repository.dart';
import 'package:astrofrekans/features/billing/presentation/premium_screen.dart';
import 'package:astrofrekans/features/explore/presentation/explore_screen.dart';
import 'package:astrofrekans/features/profile/domain/user_profile.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import '../helpers/test_harness.dart';
import 'package:astrofrekans/features/billing/presentation/subscription_actions.dart';
import 'package:astrofrekans/features/auth/presentation/register_screen.dart';
import 'dart:convert';
import 'dart:io';
import 'package:astrofrekans/features/billing/data/coin_models.dart';

void main() {
  testWidgets(
    'an active Premium user can see the yearly option for the same plan',
    (tester) async {
      final env = await TestEnv.create(user: testUser);
      await pumpScreen(
        tester,
        ProviderScope(
          overrides: [
            subscriptionTierProvider.overrideWithValue(
              SubscriptionTier.premium,
            ),
            coinCatalogProvider.overrideWith((ref) async => reviewCatalog),
          ],
          child: const PremiumScreen(),
        ),
        env: env,
      );
      final card = find.byKey(const ValueKey('plan-premium'));
      await tester.scrollUntilVisible(
        card,
        350,
        scrollable: find.byType(Scrollable).first,
      );
      expect(
        find.descendant(of: card, matching: find.text('Yıllık')),
        findsOneWidget,
      );
    },
  );

  testWidgets('relationship lock names the required Kozmik+ plan', (
    tester,
  ) async {
    final env = await TestEnv.create(user: testUser);
    await pumpScreen(
      tester,
      ProviderScope(
        overrides: [
          subscriptionTierProvider.overrideWithValue(SubscriptionTier.free),
          entitlementServiceProvider.overrideWithValue(
            const EntitlementService(
              premium: false,
              tier: SubscriptionTier.free,
              catalogue: FeatureCatalogue(
                gatingEnabled: true,
                premiumFeatures: {'synastry'},
                freeSpreads: {},
                premiumTransitRanges: {},
                featureTiers: {'synastry': SubscriptionTier.cosmicPlus},
              ),
            ),
          ),
        ],
        child: const ExploreScreen(),
      ),
      env: env,
    );
    expect(find.text('İlişki Analizi'), findsOneWidget);
    await tester.ensureVisible(find.text('İlişki Analizi'));
    await tester.pumpAndSettle();
    expect(find.text('Kozmik+'), findsWidgets);
  });
  testWidgets(
    'relationship lock remains readable at 320px and double text size',
    (tester) async {
      final env = await TestEnv.create(user: testUser);
      await pumpScreen(
        tester,
        ProviderScope(
          overrides: [
            subscriptionTierProvider.overrideWithValue(SubscriptionTier.free),
            entitlementServiceProvider.overrideWithValue(
              const EntitlementService(
                premium: false,
                tier: SubscriptionTier.free,
                catalogue: FeatureCatalogue(
                  gatingEnabled: true,
                  premiumFeatures: {'synastry'},
                  freeSpreads: {},
                  premiumTransitRanges: {},
                  featureTiers: {'synastry': SubscriptionTier.cosmicPlus},
                ),
              ),
            ),
          ],
          child: const ExploreScreen(),
        ),
        env: env,
        size: const Size(320, 640),
        textScale: 2,
      );
      await tester.scrollUntilVisible(
        find.text('İlişki Analizi'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(find.text('İlişki Analizi'));
      await tester.pumpAndSettle();
      expect(find.text('Kozmik+'), findsWidgets);
      expect(tester.takeException(), isNull);
    },
  );
  for (final apple in [true, false]) {
    testWidgets('manage subscription opens the chosen store: $apple', (
      tester,
    ) async {
      final env = await TestEnv.create(user: testUser);
      Uri? launched;
      await pumpScreen(
        tester,
        ProviderScope(
          overrides: [
            billingLinkLauncherProvider.overrideWithValue((uri) async {
              launched = uri;
              return true;
            }),
          ],
          child: Consumer(
            builder: (context, ref, _) => TextButton(
              onPressed: () => manageSubscription(context, ref),
              child: const Text('Manage'),
            ),
          ),
        ),
        env: env,
      );
      await tester.tap(find.text('Manage'));
      await tester.pumpAndSettle();
      await tester.tap(
        find.byKey(ValueKey(apple ? 'manage-apple' : 'manage-google')),
      );
      await tester.pumpAndSettle();
      expect(
        launched.toString(),
        apple
            ? 'https://apps.apple.com/account/subscriptions'
            : 'https://play.google.com/store/account/subscriptions',
      );
    });
  }
  testWidgets('legal links open the supplied policy and omit absent terms', (
    tester,
  ) async {
    final env = await TestEnv.create(user: testUser);
    Uri? launched;
    await pumpScreen(
      tester,
      ProviderScope(
        overrides: [
          billingLinkLauncherProvider.overrideWithValue((uri) async {
            launched = uri;
            return true;
          }),
        ],
        child: const SubscriptionLegalLinks(),
      ),
      env: env,
    );
    expect(find.text('Kullanım koşulları'), findsNothing);
    await tester.tap(find.text('Gizlilik politikası'));
    await tester.pumpAndSettle();
    expect(
      launched.toString(),
      'https://astrofrekansteams-cmd.github.io/astrofrekansapp/',
    );
  });
  testWidgets('explore search can recover from no results', (tester) async {
    final env = await TestEnv.create(user: testUser);
    await pumpScreen(tester, const ExploreScreen(), env: env);
    await tester.enterText(
      find.byKey(const ValueKey('explore-search')),
      'zzzzzzz',
    );
    await tester.pumpAndSettle();
    expect(find.text('İlişki Analizi'), findsNothing);
    await tester.enterText(find.byKey(const ValueKey('explore-search')), '');
    await tester.pumpAndSettle();
    expect(find.text('İlişki Analizi'), findsOneWidget);
  });
  testWidgets(
    'registration validates the first step and retains fields when going back',
    (tester) async {
      final env = await TestEnv.create();
      await pumpScreen(tester, const RegisterScreen(), env: env);
      final next = find.byKey(const ValueKey('register-next'));
      await tester.ensureVisible(next);
      await tester.tap(next);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('register-submit')), findsNothing);
      final fields = find.byType(TextFormField);
      await tester.enterText(fields.at(0), 'Test User');
      await tester.enterText(fields.at(1), 'user@example.com');
      await tester.enterText(fields.at(2), 'Secure123!');
      await tester.enterText(fields.at(3), 'Secure123!');
      await tester.ensureVisible(next);
      await tester.tap(next);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('register-submit')), findsOneWidget);
      expect(find.byType(TextFormField), findsOneWidget);
      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();
      expect(find.text('user@example.com'), findsOneWidget);
    },
  );
}

final reviewCatalog = CoinCatalog(
  jsonDecode(File('test/fixtures/frontend_catalog.json').readAsStringSync())
      as Map<String, dynamic>,
);
