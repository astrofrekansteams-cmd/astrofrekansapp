import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/billing_models.dart';
import '../data/billing_repository.dart';
import '../data/billing_service.dart';

enum EntitlementPhase {
  loading,
  free,
  premiumActive,
  gracePeriod,
  cancelledUntilExpiry,
  expired,
  error,
}

enum PurchasePhase {
  idle,
  purchasing,
  pending,
  cancelled,
  verifying,
  failed,

  /// Verified by the server and access updated.
  succeeded,
  restoring,

  /// Restore finished; [EntitlementSnapshot.errorCode] is `restore_nothing`
  /// when the store had nothing for this account.
  restored,
}

/// States during which another purchase or restore must not start.
const Set<PurchasePhase> busyPurchasePhases = {
  PurchasePhase.purchasing,
  PurchasePhase.verifying,
  PurchasePhase.pending,
  PurchasePhase.restoring,
};

@immutable
class EntitlementSnapshot {
  const EntitlementSnapshot({
    required this.phase,
    this.summary,
    this.purchase = PurchasePhase.idle,
    this.errorCode,
  });
  final EntitlementPhase phase;
  final EntitlementSummary? summary;
  final PurchasePhase purchase;
  final String? errorCode;
  bool get premiumUnlocked =>
      summary?.premium == true &&
      const {
        EntitlementPhase.premiumActive,
        EntitlementPhase.gracePeriod,
        EntitlementPhase.cancelledUntilExpiry,
      }.contains(phase);
}

class EntitlementController extends ChangeNotifier {
  EntitlementController(
    this.repository,
    this.store, {
    this.purchaseTimeout = const Duration(minutes: 3),
  });
  final BillingRepository repository;
  final BillingService store;

  /// How long "purchasing" may wait for the store's answer. The store sheet
  /// always answers (bought, cancelled, failed); if it never does - the app
  /// was killed mid-sheet, a store bug - the buttons must not stay locked.
  /// A late answer is still processed by the purchase listener.
  final Duration purchaseTimeout;
  Timer? _purchaseWatchdog;
  StreamSubscription<StorePurchaseEvent>? _subscription;
  Future<void>? _starting;
  bool _disposed = false;
  final _queued = <StorePurchaseEvent>[];
  final _processed = <String>{};
  Map<String, CatalogProduct> _catalogByStoreId = {};
  List<CatalogProduct> catalog = const [];
  Map<String, StoreProduct> localizedProducts = {};
  bool storeAvailable = false;
  bool catalogLoading = false;
  EntitlementSnapshot state = const EntitlementSnapshot(
    phase: EntitlementPhase.loading,
  );

  void _emit(EntitlementSnapshot value) {
    if (_disposed) return;
    state = value;
    notifyListeners();
  }

  Future<void> start() => _starting ??= _start();

  Future<void> _start() async {
    _subscription ??= store.purchases.listen((event) {
      if (_catalogByStoreId.isEmpty) {
        _queued.add(event);
      } else {
        unawaited(_process(event));
      }
    });
    await refresh();
    await loadCatalog();
    for (final event in List<StorePurchaseEvent>.of(_queued)) {
      await _process(event);
    }
    _queued.clear();
  }

  EntitlementPhase _phase(EntitlementSummary summary) {
    if (!summary.premium) {
      return summary.items.any((item) => item.status == 'expired')
          ? EntitlementPhase.expired
          : EntitlementPhase.free;
    }
    final premiumItems = summary.items.where(
      (item) =>
          (item.code == 'premium' || item.code == 'cosmic_plus') && item.active,
    );
    if (premiumItems.any((item) => item.status == 'grace_period')) {
      return EntitlementPhase.gracePeriod;
    }
    if (premiumItems.any((item) => item.status == 'cancelled_pending_expiry')) {
      return EntitlementPhase.cancelledUntilExpiry;
    }
    return EntitlementPhase.premiumActive;
  }

  Future<void> refresh() async {
    _emit(const EntitlementSnapshot(phase: EntitlementPhase.loading));
    try {
      final summary = await repository.entitlements();
      _emit(EntitlementSnapshot(phase: _phase(summary), summary: summary));
    } on Object {
      // Network failure is not a licence to trust an old store callback.
      _emit(
        const EntitlementSnapshot(
          phase: EntitlementPhase.error,
          errorCode: 'entitlement_refresh_failed',
        ),
      );
    }
  }

  Future<void> loadCatalog() async {
    if (_disposed ||
        catalogLoading ||
        store.platform == StorePlatform.unsupported) {
      return;
    }
    catalogLoading = true;
    storeAvailable = false;
    localizedProducts = {};
    notifyListeners();
    try {
      final availability = await repository.availability();
      final configured = switch (store.platform) {
        StorePlatform.apple => availability.appleConfigured,
        StorePlatform.google => availability.googleConfigured,
        StorePlatform.unsupported => false,
      };
      if (!configured || !await store.available()) {
        storeAvailable = false;
        return;
      }
      final products = await repository.products(store.platform);
      catalog = products.items
          .where((product) => storeProductCodes.contains(product.code))
          .toList(growable: false);
      _catalogByStoreId = {
        for (final product in catalog) product.storeId: product,
      };
      final localized = await store.loadProducts(
        _catalogByStoreId.keys.toSet(),
      );
      localizedProducts = {
        for (final product in localized) product.id: product,
      };
      storeAvailable = true;
    } on Object {
      storeAvailable = false;
    } finally {
      catalogLoading = false;
      if (!_disposed) notifyListeners();
    }
  }

  Future<void> buy(CatalogProduct product) async {
    if (busyPurchasePhases.contains(state.purchase)) {
      return;
    }
    if (!storeAvailable || localizedProducts[product.storeId] == null) {
      _emit(
        EntitlementSnapshot(
          phase: state.phase,
          summary: state.summary,
          purchase: PurchasePhase.failed,
          errorCode: 'product_unavailable',
        ),
      );
      return;
    }
    _emit(
      EntitlementSnapshot(
        phase: state.phase,
        summary: state.summary,
        purchase: PurchasePhase.purchasing,
      ),
    );
    try {
      final tokens = await repository.accountTokens();
      await store.buy(
        product,
        store.platform == StorePlatform.apple ? tokens.apple : tokens.google,
      );
      _purchaseWatchdog?.cancel();
      _purchaseWatchdog = Timer(purchaseTimeout, () {
        if (state.purchase != PurchasePhase.purchasing) return;
        _emit(
          EntitlementSnapshot(
            phase: state.phase,
            summary: state.summary,
            purchase: PurchasePhase.failed,
            errorCode: 'store_no_answer',
          ),
        );
      });
    } on Object {
      _emit(
        EntitlementSnapshot(
          phase: state.phase,
          summary: state.summary,
          purchase: PurchasePhase.failed,
          errorCode: 'store_unavailable',
        ),
      );
    }
  }

  String _eventKey(StorePurchaseEvent event) =>
      '${event.platform.name}:${event.productId}:${event.transactionId ?? event.verificationData.hashCode}';

  Future<void> _process(StorePurchaseEvent event) async {
    if (_disposed) return;
    if (event.state == StorePurchaseState.pending) {
      _emit(
        EntitlementSnapshot(
          phase: state.phase,
          summary: state.summary,
          purchase: PurchasePhase.pending,
        ),
      );
      return;
    }
    if (event.state == StorePurchaseState.cancelled) {
      _emit(
        EntitlementSnapshot(
          phase: state.phase,
          summary: state.summary,
          purchase: PurchasePhase.cancelled,
        ),
      );
      return;
    }
    if (event.state == StorePurchaseState.failed ||
        event.state == StorePurchaseState.alreadyOwned) {
      _emit(
        EntitlementSnapshot(
          phase: state.phase,
          summary: state.summary,
          purchase: PurchasePhase.failed,
          errorCode: event.state == StorePurchaseState.alreadyOwned
              ? 'already_owned'
              : 'purchase_failed',
        ),
      );
      return;
    }
    final product = _catalogByStoreId[event.productId];
    if (product == null) return;
    final key = _eventKey(event);
    if (!_processed.add(key)) return;
    _emit(
      EntitlementSnapshot(
        phase: state.phase,
        summary: state.summary,
        purchase: PurchasePhase.verifying,
      ),
    );
    try {
      if (event.platform == StorePlatform.apple) {
        if (event.verificationData == null && event.transactionId == null) {
          throw StateError('Missing Apple proof');
        }
        await repository.verifyApple(
          product.code,
          jws: event.verificationData,
          transactionId: event.transactionId,
        );
      } else if (event.platform == StorePlatform.google) {
        final token = event.verificationData;
        if (token == null || token.isEmpty) {
          throw StateError('Missing Google proof');
        }
        await repository.verifyGoogle(product.code, token);
      } else {
        return;
      }
      await refresh(); // GET /billing/entitlements remains authoritative.
      await store.complete(event);
      if (event.state == StorePurchaseState.purchased) {
        _emit(
          EntitlementSnapshot(
            phase: state.phase,
            summary: state.summary,
            purchase: PurchasePhase.succeeded,
          ),
        );
      }
    } on Object {
      _processed.remove(key); // a later callback/restore may retry safely.
      _emit(
        const EntitlementSnapshot(
          phase: EntitlementPhase.error,
          purchase: PurchasePhase.failed,
          errorCode: 'verification_failed',
        ),
      );
    }
  }

  Future<void> restore() async {
    if (busyPurchasePhases.contains(state.purchase)) return;
    _emit(
      EntitlementSnapshot(
        phase: state.phase,
        summary: state.summary,
        purchase: PurchasePhase.restoring,
      ),
    );
    try {
      final purchases = await store.restore();
      final result = await repository.reconcile(purchases, _catalogByStoreId);
      await refresh();
      _emit(
        EntitlementSnapshot(
          phase: state.phase,
          summary: state.summary,
          purchase: result.failed.isNotEmpty
              ? PurchasePhase.failed
              : PurchasePhase.restored,
          errorCode: result.failed.isNotEmpty
              ? 'restore_failed'
              : purchases.isEmpty
              ? 'restore_nothing'
              : null,
        ),
      );
    } on Object {
      // The plan shown stays what the server last said; only the restore
      // failed.
      _emit(
        EntitlementSnapshot(
          phase: state.phase,
          summary: state.summary,
          purchase: PurchasePhase.failed,
          errorCode: 'restore_failed',
        ),
      );
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _purchaseWatchdog?.cancel();
    _subscription?.cancel();
    super.dispose();
  }
}

final entitlementControllerProvider = Provider<EntitlementController>((ref) {
  final controller = EntitlementController(
    ref.watch(billingRepositoryProvider),
    ref.watch(billingServiceProvider),
  );
  ref.onDispose(controller.dispose);
  unawaited(controller.start());
  return controller;
});
