import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:in_app_purchase_android/billing_client_wrappers.dart'
    show ProductType, ReplacementMode;
import 'package:in_app_purchase_android/in_app_purchase_android.dart';
import 'package:in_app_purchase_storekit/in_app_purchase_storekit.dart';

import '../../../core/network/api_config.dart';
import 'billing_models.dart';

abstract interface class BillingService {
  StorePlatform get platform;
  Stream<StorePurchaseEvent> get purchases;
  Future<bool> available();
  Future<List<StoreProduct>> loadProducts(Set<String> storeIds);
  Future<void> buy(CatalogProduct product, String accountToken);
  Future<List<StorePurchaseEvent>> restore();
  Future<void> complete(StorePurchaseEvent event);
  void dispose();
}

abstract class NativeBillingService implements BillingService {
  NativeBillingService(this._store);
  final InAppPurchase _store;
  final _events = StreamController<StorePurchaseEvent>.broadcast();
  StreamSubscription<List<PurchaseDetails>>? _subscription;
  final Map<String, ProductDetails> _products = {};
  final Map<String, PurchaseDetails> _pendingCompletion = {};
  final List<StorePurchaseEvent> _restored = [];
  bool _disposed = false;

  void start() {
    // Exactly one native listener, owned by the application-level provider.
    _subscription ??= _store.purchaseStream.listen(_onPurchases);
  }

  @override
  Stream<StorePurchaseEvent> get purchases => _events.stream;

  @override
  Future<bool> available() => _store.isAvailable();

  @override
  Future<List<StoreProduct>> loadProducts(Set<String> storeIds) async {
    if (storeIds.isEmpty || !await available()) return const [];
    final response = await _store.queryProductDetails(storeIds);
    _products
      ..clear()
      ..addEntries(response.productDetails.map((p) => MapEntry(p.id, p)));
    return response.productDetails
        .map(
          (p) => StoreProduct(
            id: p.id,
            title: p.title,
            localizedPrice: p.price,
            currencyCode: p.currencyCode,
          ),
        )
        .toList(growable: false);
  }

  @override
  Future<void> buy(CatalogProduct product, String accountToken) async {
    final details = _products[product.storeId];
    if (details == null) throw StateError('Product unavailable in store');
    final params = await purchaseParam(product, details, accountToken);
    final launched = product.isConsumable
        ? await _store.buyConsumable(purchaseParam: params, autoConsume: false)
        : await _store.buyNonConsumable(purchaseParam: params);
    if (!launched) {
      throw StateError('Store did not start purchase');
    }
  }

  /// What to hand the store for [product]. Platforms override this.
  @protected
  Future<PurchaseParam> purchaseParam(
    CatalogProduct product,
    ProductDetails details,
    String accountToken,
  ) async =>
      PurchaseParam(productDetails: details, applicationUserName: accountToken);

  StorePurchaseEvent _convert(PurchaseDetails details) {
    final state = switch (details.status) {
      PurchaseStatus.purchased => StorePurchaseState.purchased,
      PurchaseStatus.restored => StorePurchaseState.restored,
      PurchaseStatus.pending => StorePurchaseState.pending,
      PurchaseStatus.canceled => StorePurchaseState.cancelled,
      PurchaseStatus.error
          when details.error?.message.contains('itemAlreadyOwned') == true =>
        StorePurchaseState.alreadyOwned,
      PurchaseStatus.error => StorePurchaseState.failed,
    };
    return StorePurchaseEvent(
      platform: platform,
      productId: details.productID,
      state: state,
      // StoreKit 2 supplies a JWS. StoreKit 1 falls back to the transaction id.
      // Android supplies the purchase token. Neither is logged or persisted.
      verificationData:
          platform == StorePlatform.apple && details is! SK2PurchaseDetails
          ? null
          : details.verificationData.serverVerificationData,
      transactionId: details.purchaseID,
    );
  }

  void _onPurchases(List<PurchaseDetails> updates) {
    if (_disposed) return;
    for (final details in updates) {
      final event = _convert(details);
      if (details.status == PurchaseStatus.restored) _restored.add(event);
      if (details.pendingCompletePurchase) {
        _pendingCompletion[_key(event)] = details;
      }
      _events.add(event);
    }
  }

  String _key(StorePurchaseEvent event) =>
      '${event.productId}:${event.transactionId ?? event.verificationData.hashCode}';

  @override
  Future<List<StorePurchaseEvent>> restore() async {
    _restored.clear();
    await _store.restorePurchases();
    // Store callbacks are asynchronous. Late callbacks are still handled by
    // the app-level listener; this snapshot is only for backend reconciliation.
    await Future<void>.delayed(const Duration(seconds: 2));
    return List.unmodifiable(_restored);
  }

  @override
  Future<void> complete(StorePurchaseEvent event) async {
    final details = _pendingCompletion.remove(_key(event));
    if (details != null && details.pendingCompletePurchase) {
      await _store.completePurchase(details);
    }
  }

  @override
  void dispose() {
    if (_disposed) return;
    _disposed = true;
    _subscription?.cancel();
    _subscription = null;
    _events.close();
  }
}

class AppleStoreBillingService extends NativeBillingService {
  AppleStoreBillingService(super.store);
  @override
  StorePlatform get platform => StorePlatform.apple;
}

class GooglePlayBillingService extends NativeBillingService {
  GooglePlayBillingService(super.store);
  @override
  StorePlatform get platform => StorePlatform.google;

  /// Switching plans (Premium -> Kozmik+, monthly -> yearly) must *replace*
  /// the running Play subscription. Bought as a plain new purchase, Google
  /// would keep both running and charge for both. The replaced purchase's
  /// token comes back as `linkedPurchaseToken`, and the server retires it.
  /// App Store does the same by itself for products in one subscription group.
  @override
  Future<PurchaseParam> purchaseParam(
    CatalogProduct product,
    ProductDetails details,
    String accountToken,
  ) async {
    if (product.type != 'subscription') {
      return super.purchaseParam(product, details, accountToken);
    }
    final GooglePlayPurchaseDetails? current = await _runningSubscription(
      except: product.storeId,
    );
    return GooglePlayPurchaseParam(
      productDetails: details,
      applicationUserName: accountToken,
      changeSubscriptionParam: current == null
          ? null
          : ChangeSubscriptionParam(
              oldPurchaseDetails: current,
              // Immediate; the unused time of the old plan is credited.
              replacementMode: ReplacementMode.withTimeProration,
            ),
    );
  }

  Future<GooglePlayPurchaseDetails?> _runningSubscription({
    required String except,
  }) async {
    final Set<String> subscriptions = {
      for (final ProductDetails p in _products.values)
        if (p is GooglePlayProductDetails &&
            p.productDetails.productType == ProductType.subs)
          p.id,
    }..remove(except);
    if (subscriptions.isEmpty) return null;
    try {
      final QueryPurchaseDetailsResponse past = await _store
          .getPlatformAddition<InAppPurchaseAndroidPlatformAddition>()
          .queryPastPurchases();
      return past.pastPurchases
          .where(
            (p) =>
                p.status == PurchaseStatus.purchased &&
                subscriptions.contains(p.productID),
          )
          .firstOrNull;
    } on Object {
      // No answer from Play: buying without replacement is what the old
      // code did; Play itself refuses buying the *same* plan twice.
      return null;
    }
  }
}

class DisabledBillingService implements BillingService {
  const DisabledBillingService();
  @override
  StorePlatform get platform => StorePlatform.unsupported;
  @override
  Stream<StorePurchaseEvent> get purchases => const Stream.empty();
  @override
  Future<bool> available() async => false;
  @override
  Future<List<StoreProduct>> loadProducts(Set<String> storeIds) async =>
      const [];
  Never get _disabled => throw StateError('Store billing unavailable');
  @override
  Future<void> buy(CatalogProduct product, String accountToken) async =>
      _disabled;
  @override
  Future<List<StorePurchaseEvent>> restore() async => _disabled;
  @override
  Future<void> complete(StorePurchaseEvent event) async => _disabled;
  @override
  void dispose() {}
}

final billingServiceProvider = Provider<BillingService>((ref) {
  final environment = ref.watch(appEnvironmentProvider);
  if (environment.environment == AppEnvironmentName.production &&
      environment.useMocks) {
    throw StateError('Production billing requires APP_DATA_SOURCE=api');
  }
  if (environment.useMocks || kIsWeb) return const DisabledBillingService();
  final NativeBillingService service = switch (defaultTargetPlatform) {
    TargetPlatform.iOS => AppleStoreBillingService(InAppPurchase.instance),
    TargetPlatform.android => GooglePlayBillingService(InAppPurchase.instance),
    _ => throw StateError(
      'Production billing requires an iOS or Android store',
    ),
  };
  service.start();
  ref.onDispose(service.dispose);
  return service;
});
