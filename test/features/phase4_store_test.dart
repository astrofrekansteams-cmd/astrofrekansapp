// Phase 4: every purchase and restore ends in a state the screen can say -
// success, cancelled, pending, already owned, a silent store - and nothing
// waits forever.
import 'dart:async';

import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/features/billing/application/entitlement_controller.dart';
import 'package:astrofrekans/features/billing/data/billing_models.dart';
import 'package:astrofrekans/features/billing/data/billing_repository.dart';
import 'package:astrofrekans/features/billing/data/billing_service.dart';
import 'package:astrofrekans/features/billing/presentation/purchase_status.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

const _product = {
  'code': 'premium_monthly',
  'product_type': 'subscription',
  'entitlement_code': 'premium',
  'store_product_id': 'test.premium.monthly',
};
const _free = {
  'tier': 'free',
  'premium': false,
  'credits': <String, int>{},
  'capabilities': <String, Object>{},
  'items': <Object>[],
};
const _premium = {
  'tier': 'premium',
  'premium': true,
  'credits': <String, int>{},
  'capabilities': <String, Object>{},
  'items': [
    {
      'entitlement_code': 'premium',
      'kind': 'subscription',
      'status': 'active',
      'active': true,
    },
  ],
};

StorePurchaseEvent _event(StorePurchaseState state) => StorePurchaseEvent(
  platform: StorePlatform.google,
  productId: 'test.premium.monthly',
  state: state,
  verificationData: 'purchase-token',
  transactionId: 'GPA.1',
);

Future<void> _settle() =>
    Future<void>.delayed(const Duration(milliseconds: 20));

Future<(EntitlementController, _Store, _Repository)> _controller({
  Duration timeout = const Duration(minutes: 3),
}) async {
  final store = _Store();
  final repo = _Repository();
  final controller = EntitlementController(
    repo,
    store,
    purchaseTimeout: timeout,
  );
  await controller.start();
  return (controller, store, repo);
}

void main() {
  test(
    'store catalogue recovers after an unavailable store without restart',
    () async {
      final store = _Store()..isAvailable = false;
      final controller = EntitlementController(_Repository(), store);
      await controller.start();
      expect(controller.storeAvailable, isFalse);
      expect(controller.localizedProducts, isEmpty);
      expect(controller.catalogLoading, isFalse);
      store.isAvailable = true;
      await controller.loadCatalog();
      expect(controller.storeAvailable, isTrue);
      expect(
        controller.localizedProducts['test.premium.monthly']?.localizedPrice,
        '₺49,99',
      );
      expect(controller.catalogLoading, isFalse);
      controller.dispose();
    },
  );
  group('purchase states', () {
    test('a verified purchase says so', () async {
      final (c, store, repo) = await _controller();
      await c.buy(c.catalog.single);
      expect(c.state.purchase, PurchasePhase.purchasing);
      repo.summary = EntitlementSummary(_premium);
      store.events.add(_event(StorePurchaseState.purchased));
      await _settle();
      expect(c.state.purchase, PurchasePhase.succeeded);
      expect(c.state.premiumUnlocked, isTrue);
      expect(store.completed, 1);
    });

    test('cancelled and pending are their own states', () async {
      final (c, store, _) = await _controller();
      store.events.add(_event(StorePurchaseState.cancelled));
      await _settle();
      expect(c.state.purchase, PurchasePhase.cancelled);
      store.events.add(_event(StorePurchaseState.pending));
      await _settle();
      expect(c.state.purchase, PurchasePhase.pending);
    });

    test('already owned points to restore, not a generic failure', () async {
      final (c, store, _) = await _controller();
      store.events.add(_event(StorePurchaseState.alreadyOwned));
      await _settle();
      expect(c.state.purchase, PurchasePhase.failed);
      expect(c.state.errorCode, 'already_owned');
    });

    test('a store that never answers does not lock the buttons', () async {
      final (c, _, _) = await _controller(
        timeout: const Duration(milliseconds: 50),
      );
      await c.buy(c.catalog.single);
      expect(busyPurchasePhases, contains(c.state.purchase));
      await Future<void>.delayed(const Duration(milliseconds: 120));
      expect(c.state.purchase, PurchasePhase.failed);
      expect(c.state.errorCode, 'store_no_answer');
      expect(busyPurchasePhases, isNot(contains(c.state.purchase)));
    });

    test('restore shows progress, then what it found', () async {
      final (c, store, _) = await _controller();
      final done = c.restore();
      expect(c.state.purchase, PurchasePhase.restoring);
      await done;
      expect(c.state.purchase, PurchasePhase.restored);
      expect(c.state.errorCode, 'restore_nothing');

      store.restorable = [_event(StorePurchaseState.restored)];
      await c.restore();
      expect(c.state.purchase, PurchasePhase.restored);
      expect(c.state.errorCode, isNull);
    });

    test('a failed restore keeps the plan the server reported', () async {
      final (c, store, repo) = await _controller();
      repo.summary = EntitlementSummary(_premium);
      await c.refresh();
      store.restoreFails = true;
      await c.restore();
      expect(c.state.purchase, PurchasePhase.failed);
      expect(c.state.errorCode, 'restore_failed');
      expect(c.state.premiumUnlocked, isTrue);
    });
  });

  group('the notice speaks the app language', () {
    Future<void> pump(
      WidgetTester tester,
      EntitlementSnapshot state,
      Locale locale,
    ) => tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.dark,
        locale: locale,
        supportedLocales: AppLocalizations.supportedLocales,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        home: Scaffold(body: PurchaseStatusNotice(state: state)),
      ),
    );

    testWidgets('errors in English and Turkish', (tester) async {
      const failed = EntitlementSnapshot(
        phase: EntitlementPhase.free,
        purchase: PurchasePhase.failed,
        errorCode: 'already_owned',
      );
      await pump(tester, failed, const Locale('en'));
      expect(find.textContaining('You already own this'), findsOneWidget);
      await pump(tester, failed, const Locale('tr'));
      expect(find.textContaining('Bu ürün zaten hesabında'), findsOneWidget);
    });

    testWidgets('waiting shows a bounded progress bar; idle shows nothing', (
      tester,
    ) async {
      await pump(
        tester,
        const EntitlementSnapshot(
          phase: EntitlementPhase.free,
          purchase: PurchasePhase.verifying,
        ),
        const Locale('tr'),
      );
      expect(find.text('Satın alma doğrulanıyor…'), findsOneWidget);
      expect(find.byType(LinearProgressIndicator), findsOneWidget);
      await pump(
        tester,
        const EntitlementSnapshot(phase: EntitlementPhase.free),
        const Locale('tr'),
      );
      expect(find.byKey(const ValueKey('purchase-status')), findsNothing);
    });
  });
}

// ------------------------------------------------------------------ fakes

class _Store implements BillingService {
  final events = StreamController<StorePurchaseEvent>.broadcast();
  int completed = 0;
  List<StorePurchaseEvent> restorable = const [];
  bool restoreFails = false;
  bool isAvailable = true;
  @override
  StorePlatform get platform => StorePlatform.google;
  @override
  Stream<StorePurchaseEvent> get purchases => events.stream;
  @override
  Future<bool> available() async => isAvailable;
  @override
  Future<List<StoreProduct>> loadProducts(Set<String> ids) async => [
    for (final id in ids)
      StoreProduct(
        id: id,
        title: 'Premium',
        localizedPrice: '₺49,99',
        currencyCode: 'TRY',
      ),
  ];
  @override
  Future<void> buy(CatalogProduct product, String accountToken) async {}
  @override
  Future<List<StorePurchaseEvent>> restore() async {
    if (restoreFails) throw StateError('store');
    return restorable;
  }

  @override
  Future<void> complete(StorePurchaseEvent event) async => completed++;
  @override
  void dispose() => events.close();
}

class _Repository implements BillingRepository {
  EntitlementSummary summary = EntitlementSummary(_free);
  @override
  Future<BillingAvailability> availability() async => BillingAvailability({
    'apple_configured': true,
    'google_configured': true,
  });
  @override
  Future<ProductCatalog> products(StorePlatform platform) async =>
      ProductCatalog({
        'platform': 'android',
        'items': [_product],
      });
  @override
  Future<AccountTokens> accountTokens() async => AccountTokens({
    'apple_app_account_token': 'a',
    'google_obfuscated_account_id': 'g',
  });
  @override
  Future<EntitlementSummary> entitlements() async => summary;
  @override
  Future<PurchaseResult> verifyGoogle(String code, String token) async =>
      PurchaseResult({'status': 'active', 'entitlements': _premium});
  @override
  Future<ReconcileResult> reconcile(
    List<StorePurchaseEvent> purchases,
    Map<String, CatalogProduct> catalog,
  ) async => ReconcileResult({
    'verified': purchases.length,
    'failed': <Object>[],
    'entitlements': _free,
  });
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
