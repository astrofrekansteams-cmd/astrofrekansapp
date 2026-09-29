import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_exception.dart';
import '../../auth/application/session_controller.dart';
import 'billing_models.dart';

abstract interface class BillingRepository {
  Future<BillingAvailability> availability();
  Future<ProductCatalog> products(StorePlatform platform);
  Future<AccountTokens> accountTokens();
  Future<EntitlementSummary> entitlements();
  Future<PurchaseResult> verifyApple(
    String productCode, {
    String? jws,
    String? transactionId,
  });
  Future<PurchaseResult> verifyGoogle(String productCode, String purchaseToken);
  Future<ReconcileResult> reconcile(
    List<StorePurchaseEvent> purchases,
    Map<String, CatalogProduct> byStoreId,
  );
  Future<OrderPayment> orderPayment(String orderId);
  Future<OrderPaymentStart> payOrder(
    String orderId, {
    required String method,
    required String idempotencyKey,
  });
  Future<void> consumeCredit(String entitlementCode, String consumerRef);
}

class ApiBillingRepository implements BillingRepository {
  const ApiBillingRepository(this.api);
  final ApiClient api;
  String _id(String value) => Uri.encodeComponent(value);
  @override
  Future<BillingAvailability> availability() async =>
      BillingAvailability(await api.getMap('billing/status'));
  @override
  Future<ProductCatalog> products(StorePlatform platform) async =>
      ProductCatalog(
        await api.getMap(
          'billing/products',
          queryParameters: {
            'platform': switch (platform) {
              StorePlatform.apple => 'ios',
              StorePlatform.google => 'android',
              StorePlatform.unsupported => 'web',
            },
          },
        ),
      );
  @override
  Future<AccountTokens> accountTokens() async =>
      AccountTokens(await api.getMap('billing/account-tokens'));
  @override
  Future<EntitlementSummary> entitlements() async =>
      EntitlementSummary(await api.getMap('billing/entitlements'));
  @override
  Future<PurchaseResult> verifyApple(
    String productCode, {
    String? jws,
    String? transactionId,
  }) async => PurchaseResult(
    await api.postMap(
      'billing/apple/verify',
      data: {
        'product_code': productCode,
        'signed_transaction': ?jws,
        'transaction_id': ?transactionId,
      },
    ),
  );
  @override
  Future<PurchaseResult> verifyGoogle(
    String productCode,
    String purchaseToken,
  ) async => PurchaseResult(
    await api.postMap(
      'billing/google/verify',
      data: {'product_code': productCode, 'purchase_token': purchaseToken},
    ),
  );
  @override
  Future<ReconcileResult> reconcile(
    List<StorePurchaseEvent> purchases,
    Map<String, CatalogProduct> byStoreId,
  ) async {
    final apple = <Map<String, dynamic>>[];
    final google = <Map<String, dynamic>>[];
    for (final purchase in purchases) {
      final product = byStoreId[purchase.productId];
      if (product == null || purchase.state == StorePurchaseState.pending) {
        continue;
      }
      if (purchase.platform == StorePlatform.apple) {
        apple.add({
          'product_code': product.code,
          if (purchase.verificationData != null)
            'signed_transaction': purchase.verificationData,
          if (purchase.transactionId != null)
            'transaction_id': purchase.transactionId,
        });
      } else if (purchase.platform == StorePlatform.google &&
          purchase.verificationData != null) {
        google.add({
          'product_code': product.code,
          'purchase_token': purchase.verificationData,
        });
      }
    }
    // B11 caps each platform at 20 proofs per request. Reconcile all pages;
    // the final response carries the latest server-authoritative summary.
    ReconcileResult? latest;
    var verified = 0;
    final failed = <Map<String, dynamic>>[];
    final pages = (apple.length > google.length ? apple.length : google.length);
    for (var offset = 0; offset < (pages == 0 ? 1 : pages); offset += 20) {
      latest = ReconcileResult(
        await api.postMap(
          'billing/reconcile',
          data: {
            'apple': apple.skip(offset).take(20).toList(),
            'google': google.skip(offset).take(20).toList(),
          },
        ),
      );
      verified += latest.verified;
      failed.addAll(latest.failed);
    }
    return ReconcileResult({
      'verified': verified,
      'failed': failed,
      'entitlements': latest!.entitlements.json,
    });
  }

  @override
  Future<OrderPayment> orderPayment(String orderId) async =>
      OrderPayment(await api.getMap('orders/${_id(orderId)}/payment'));
  @override
  Future<OrderPaymentStart> payOrder(
    String orderId, {
    required String method,
    required String idempotencyKey,
  }) async => OrderPaymentStart(
    await api.postMap(
      'orders/${_id(orderId)}/payment',
      data: {'method': method, 'idempotency_key': idempotencyKey},
    ),
  );
  @override
  Future<void> consumeCredit(String entitlementCode, String consumerRef) async {
    await api.postMap(
      'billing/credits/consume',
      data: {'entitlement_code': entitlementCode, 'consumer_ref': consumerRef},
    );
  }
}

class DisabledBillingRepository implements BillingRepository {
  const DisabledBillingRepository();
  ApiException get _error => const ApiException(
    kind: ApiErrorKind.server,
    code: 'billing_not_configured',
  );
  @override
  Future<BillingAvailability> availability() async => BillingAvailability({
    'apple_configured': false,
    'google_configured': false,
    'external_marketplace_configured': false,
  });
  @override
  Future<ProductCatalog> products(StorePlatform platform) async =>
      ProductCatalog({'platform': 'web', 'items': <Map<String, dynamic>>[]});
  @override
  Future<AccountTokens> accountTokens() async => throw _error;
  @override
  Future<EntitlementSummary> entitlements() async => EntitlementSummary({
    'tier': 'free',
    'premium': false,
    'credits': <String, int>{},
    'items': <Map<String, dynamic>>[],
  });
  @override
  Future<PurchaseResult> verifyApple(
    String productCode, {
    String? jws,
    String? transactionId,
  }) async => throw _error;
  @override
  Future<PurchaseResult> verifyGoogle(
    String productCode,
    String purchaseToken,
  ) async => throw _error;
  @override
  Future<ReconcileResult> reconcile(
    List<StorePurchaseEvent> purchases,
    Map<String, CatalogProduct> byStoreId,
  ) async => throw _error;
  @override
  Future<OrderPayment> orderPayment(String orderId) async => throw _error;
  @override
  Future<OrderPaymentStart> payOrder(
    String orderId, {
    required String method,
    required String idempotencyKey,
  }) async => throw _error;
  @override
  Future<void> consumeCredit(
    String entitlementCode,
    String consumerRef,
  ) async => throw _error;
}

final billingRepositoryProvider = Provider<BillingRepository>((ref) {
  ref.watch(currentUserProvider)?.id;
  return ref.watch(appEnvironmentProvider).useMocks
      ? const DisabledBillingRepository()
      : ApiBillingRepository(ApiClient(ref.watch(dioProvider)));
});
