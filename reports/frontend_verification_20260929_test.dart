import 'dart:convert';
import 'dart:io';
import 'package:astrofrekans/features/home/presentation/home_screen.dart';
import 'package:astrofrekans/features/explore/presentation/explore_screen.dart';
import 'package:astrofrekans/features/profile/presentation/profile_screen.dart';
import 'package:astrofrekans/features/auth/presentation/register_screen.dart';
import 'package:astrofrekans/features/billing/presentation/premium_screen.dart';
import 'package:astrofrekans/features/billing/application/entitlement_controller.dart';
import 'package:astrofrekans/features/billing/data/billing_models.dart';
import 'package:astrofrekans/features/billing/data/billing_repository.dart';
import 'package:astrofrekans/features/billing/data/billing_service.dart';
import 'package:astrofrekans/features/billing/data/coin_models.dart';
import 'package:astrofrekans/features/billing/data/coin_repository.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import '../test/helpers/test_harness.dart';
import '../test/preview_capture_test.dart' as preview;

class ReviewBilling extends Fake implements BillingRepository {
  @override
  Future<EntitlementSummary> entitlements() async => EntitlementSummary({
    'tier': 'premium', 'premium': true,
    'credits': <String, int>{}, 'items': <Map<String, dynamic>>[],
  });
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(preview.loadFonts);
  for (final size in [const Size(390, 844), const Size(320, 640)]) {
    for (final scale in [1.0, 2.0]) {
      for (final entry in <String, Widget>{
        'home': const HomeScreen(), 'explore': const ExploreScreen(),
        'profile': const ProfileScreen(), 'register': const RegisterScreen(),
        'premium': const PremiumScreen(),
      }.entries) {
        testWidgets('${entry.key} ${size.width} scale $scale', (tester) async {
          final originalOnError = FlutterError.onError;
          FlutterError.onError = (details) {
            // Preserve the complete layout diagnostic in the review log.
            // ignore: avoid_print
            print(details.toString());
            originalOnError?.call(details);
          };
          addTearDown(() => FlutterError.onError = originalOnError);
          final env = await TestEnv.create(user: testUser);
          final controller = EntitlementController(ReviewBilling(), const DisabledBillingService());
          await controller.refresh();
          controller.catalog = [];
          controller.storeAvailable = true;
          for (final tier in ['premium', 'cosmic_plus']) {
            for (final period in ['monthly', 'yearly']) {
              final code = '${tier}_$period';
              controller.catalog.add(CatalogProduct({
                'code': code, 'product_type': 'subscription',
                'entitlement_code': tier, 'store_product_id': code,
              }));
              controller.localizedProducts[code] = StoreProduct(id: code,
                title: code, localizedPrice: period == 'monthly' ? '₺199,99' : '₺1.999,99', currencyCode: 'TRY');
            }
          }
          await pumpScreen(tester, ProviderScope(overrides: [
            entitlementControllerProvider.overrideWithValue(controller),
            coinCatalogProvider.overrideWith((ref) async => reviewCatalog),
          ], child: entry.value), env: env, size: size, textScale: scale);
          if (size.width == 390 && scale == 1) {
            await tester.runAsync(() async {
              for (final e in find.byType(Image).evaluate()) {
                await precacheImage((e.widget as Image).image, e);
              }
            });
            await tester.pumpAndSettle();
            Directory('reports/frontend_preview_20260929').createSync(recursive: true);
            await expectLater(find.byType(MaterialApp), matchesGoldenFile('frontend_preview_20260929/${entry.key}.png'));
          }
          final scroll = find.byType(Scrollable).first;
          for (var i=0; i<12; i++) {
            await tester.drag(scroll, const Offset(0,-400));
            await tester.pumpAndSettle();
          }
          expect(tester.takeException(), isNull);
          await tester.pumpWidget(const SizedBox.shrink());
          controller.dispose();
        });
      }
    }
  }
}

final reviewCatalog = CoinCatalog(jsonDecode(File('reports/frontend_catalog_fixture.json').readAsStringSync()) as Map<String, dynamic>);
