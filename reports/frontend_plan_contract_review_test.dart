// Audit expectations: these deliberately expose currently missing user paths.
import 'package:astrofrekans/features/billing/application/entitlement_service.dart';
import 'package:astrofrekans/features/billing/data/coin_repository.dart';
import 'package:astrofrekans/features/billing/presentation/premium_screen.dart';
import 'package:astrofrekans/features/explore/presentation/explore_screen.dart';
import 'package:astrofrekans/features/profile/domain/user_profile.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import '../test/helpers/test_harness.dart';
import 'frontend_review_20260928_test.dart' show reviewCatalog;

void main() {
  testWidgets('an active Premium user can see the yearly option for the same plan', (tester) async {
    final env = await TestEnv.create(user: testUser);
    await pumpScreen(tester, ProviderScope(overrides: [
      subscriptionTierProvider.overrideWithValue(SubscriptionTier.premium),
      coinCatalogProvider.overrideWith((ref) async => reviewCatalog),
    ], child: const PremiumScreen()), env: env);
    final card = find.byKey(const ValueKey('plan-premium'));
    await tester.scrollUntilVisible(card, 350, scrollable: find.byType(Scrollable).first);
    expect(find.descendant(of: card, matching: find.text('Yıllık')), findsOneWidget);
  });

  testWidgets('relationship lock names the required Kozmik+ plan', (tester) async {
    final env = await TestEnv.create(user: testUser);
    await pumpScreen(tester, ProviderScope(overrides: [
      subscriptionTierProvider.overrideWithValue(SubscriptionTier.free),
      featureCatalogueProvider.overrideWith((ref) async => const FeatureCatalogue(
        gatingEnabled: true, premiumFeatures: {'synastry'}, freeSpreads: {},
        premiumTransitRanges: {}, featureTiers: {'synastry': SubscriptionTier.cosmicPlus},
      )),
    ], child: const ExploreScreen()), env: env);
    expect(find.text('İlişki Analizi'), findsOneWidget);
    await tester.ensureVisible(find.text('İlişki Analizi'));
    await tester.pumpAndSettle();
    expect(find.text('Kozmik+'), findsWidgets);
  });
}
