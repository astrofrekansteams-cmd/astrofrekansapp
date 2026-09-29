import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:astrofrekans/features/billing/application/entitlement_controller.dart';
import 'package:astrofrekans/features/billing/application/paid_report_service.dart';
import 'package:astrofrekans/features/billing/data/billing_models.dart';
import 'package:astrofrekans/features/billing/data/billing_repository.dart';
import 'package:astrofrekans/features/billing/data/billing_service.dart';
import 'package:astrofrekans/core/network/api_config.dart';
import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:dio/dio.dart';
import 'package:astrofrekans/features/calls/data/call_media_service.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:astrofrekans/features/astro_ai/data/ai_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final fixtures =
      jsonDecode(
            File('test/fixtures/b12c_contract_samples.json').readAsStringSync(),
          )
          as Map<String, dynamic>;

  test(
    'catalog maps backend store id and localized price without inventing SKU',
    () async {
      final repository = _Repository(fixtures);
      final store = _Store();
      final controller = EntitlementController(repository, store);
      await controller.start();
      expect(controller.catalog.single.code, 'premium_monthly');
      expect(
        controller.localizedProducts.values.single.localizedPrice,
        '₺49,99',
      );
      controller.dispose();
      store.dispose();
    },
  );

  test(
    'purchased callback with inactive backend entitlement stays locked',
    () async {
      final repository = _Repository(fixtures);
      final store = _Store();
      final controller = EntitlementController(repository, store);
      await controller.start();
      store.emit(
        const StorePurchaseEvent(
          platform: StorePlatform.apple,
          productId: 'test.premium.monthly',
          state: StorePurchaseState.purchased,
          transactionId: 'test-transaction',
        ),
      );
      await _pump();
      expect(repository.appleVerifications, 1);
      expect(controller.state.premiumUnlocked, isFalse);
      expect(store.completed, 1);
      controller.dispose();
      store.dispose();
    },
  );

  test(
    'backend active/grace/expired statuses control premium, not local clock',
    () async {
      final repository = _Repository(fixtures);
      final store = _Store();
      final controller = EntitlementController(repository, store);
      await controller.start();
      repository.summary = EntitlementSummary(
        fixtures['entitlements_active'] as Map<String, dynamic>,
      );
      await controller.refresh();
      expect(controller.state.phase, EntitlementPhase.premiumActive);
      expect(controller.state.premiumUnlocked, isTrue);
      repository.summary = EntitlementSummary({
        'tier': 'premium',
        'premium': true,
        'credits': <String, int>{},
        'items': [
          {
            'entitlement_code': 'premium',
            'kind': 'subscription',
            'status': 'grace_period',
            'active': true,
          },
        ],
      });
      await controller.refresh();
      expect(controller.state.phase, EntitlementPhase.gracePeriod);
      expect(controller.state.premiumUnlocked, isTrue);
      repository.summary = EntitlementSummary({
        'tier': 'free',
        'premium': false,
        'credits': <String, int>{},
        'items': [
          {
            'entitlement_code': 'premium',
            'kind': 'subscription',
            'status': 'expired',
            'active': false,
          },
        ],
      });
      await controller.refresh();
      expect(controller.state.phase, EntitlementPhase.expired);
      expect(controller.state.premiumUnlocked, isFalse);
      controller.dispose();
      store.dispose();
    },
  );

  test(
    'pending, duplicate callbacks, restore, and listener disposal',
    () async {
      final repository = _Repository(fixtures);
      final store = _Store();
      final controller = EntitlementController(repository, store);
      await controller.start();
      const pending = StorePurchaseEvent(
        platform: StorePlatform.apple,
        productId: 'test.premium.monthly',
        state: StorePurchaseState.pending,
      );
      store.emit(pending);
      await _pump();
      expect(controller.state.purchase, PurchasePhase.pending);
      expect(controller.state.premiumUnlocked, isFalse);
      const purchased = StorePurchaseEvent(
        platform: StorePlatform.apple,
        productId: 'test.premium.monthly',
        state: StorePurchaseState.purchased,
        transactionId: 'one',
      );
      store.emit(purchased);
      store.emit(purchased);
      await _pump();
      expect(repository.appleVerifications, 1);
      await controller.restore();
      expect(repository.reconciliations, 1);
      expect(repository.summary.hasCredit('natal_report_credit'), isFalse);
      controller.dispose();
      store.emit(
        const StorePurchaseEvent(
          platform: StorePlatform.apple,
          productId: 'test.premium.monthly',
          state: StorePurchaseState.purchased,
          transactionId: 'two',
        ),
      );
      await _pump();
      expect(repository.appleVerifications, 1);
      store.dispose();
    },
  );

  test('hybrid payment groups remain separate and review is blocked', () {
    final payment = OrderPayment(
      fixtures['payment_groups'] as Map<String, dynamic>,
    );
    expect(payment.groups.map((e) => e.classification), [
      'digital_store',
      'live_person_to_person',
      'review_required',
    ]);
    expect(payment.groups.last.reviewRequired, isTrue);
    expect(payment.blockedByReview, isTrue);
    expect(payment.lines.single.storeProductCode, 'ai_pre_analysis');
  });

  test(
    'Google purchase proof is verified but inactive backend remains locked',
    () async {
      final repository = _Repository(fixtures);
      final store = _Store(StorePlatform.google);
      final controller = EntitlementController(repository, store);
      await controller.start();
      store.emit(
        const StorePurchaseEvent(
          platform: StorePlatform.google,
          productId: 'test.premium.monthly',
          state: StorePurchaseState.purchased,
          verificationData: 'sanitized-purchase-token',
          transactionId: 'google-one',
        ),
      );
      await _pump();
      expect(repository.googleVerifications, 1);
      expect(controller.state.premiumUnlocked, isFalse);
      controller.dispose();
      store.dispose();
    },
  );

  test(
    'purchase cancellation and failed backend verification are controlled',
    () async {
      final repository = _Repository(fixtures)..failVerification = true;
      final store = _Store();
      final controller = EntitlementController(repository, store);
      await controller.start();
      store.emit(
        const StorePurchaseEvent(
          platform: StorePlatform.apple,
          productId: 'test.premium.monthly',
          state: StorePurchaseState.cancelled,
        ),
      );
      await _pump();
      expect(controller.state.purchase, PurchasePhase.cancelled);
      store.emit(
        const StorePurchaseEvent(
          platform: StorePlatform.apple,
          productId: 'test.premium.monthly',
          state: StorePurchaseState.purchased,
          transactionId: 'failed-one',
        ),
      );
      await _pump();
      expect(controller.state.errorCode, 'verification_failed');
      expect(controller.state.premiumUnlocked, isFalse);
      expect(store.completed, 0);
      controller.dispose();
      store.dispose();
    },
  );

  test('store unavailable cannot begin purchase', () async {
    final repository = _Repository(fixtures);
    final store = _Store()..isAvailable = false;
    final controller = EntitlementController(repository, store);
    await controller.start();
    expect(controller.storeAvailable, isFalse);
    await controller.buy(
      CatalogProduct(
        (fixtures['products'] as Map<String, dynamic>)['items'][0]
            as Map<String, dynamic>,
      ),
    );
    expect(controller.state.errorCode, 'product_unavailable');
    expect(store.bought, 0);
    controller.dispose();
    store.dispose();
  });

  test('restore reconciliation batches over 20 store proofs', () async {
    final requests = <Map<String, dynamic>>[];
    final dio = Dio()
      ..interceptors.add(
        InterceptorsWrapper(
          onRequest: (options, handler) {
            requests.add(Map<String, dynamic>.from(options.data as Map));
            handler.resolve(
              Response(
                requestOptions: options,
                data: {
                  'verified': (options.data['apple'] as List).length,
                  'failed': <Map<String, String>>[],
                  'entitlements': fixtures['entitlements_free'],
                },
              ),
            );
          },
        ),
      );
    final repository = ApiBillingRepository(ApiClient(dio));
    final product = CatalogProduct({
      'code': 'natal_report',
      'product_type': 'consumable',
      'store_product_id': 'natal.test',
      'entitlement_code': 'natal_report_credit',
    });
    final purchases = [
      for (var i = 0; i < 21; i++)
        StorePurchaseEvent(
          platform: StorePlatform.apple,
          productId: 'natal.test',
          state: StorePurchaseState.restored,
          transactionId: 'transaction-$i',
        ),
    ];
    final result = await repository.reconcile(purchases, {
      'natal.test': product,
    });
    expect(requests.map((r) => (r['apple'] as List).length), [20, 1]);
    expect(result.verified, 21);
    dio.close();
  });

  test('production mock media and billing adapters fail closed', () {
    final container = ProviderContainer(
      overrides: [
        appEnvironmentProvider.overrideWithValue(
          const AppEnvironment(
            environment: AppEnvironmentName.production,
            apiBaseUrl: '',
            dataSource: AppDataSource.mock,
            enableDebugTools: false,
          ),
        ),
      ],
    );
    expect(
      () => container.read(billingServiceProvider),
      throwsA(
        predicate(
          (e) => e.toString().contains(
            'Production billing requires APP_DATA_SOURCE=api',
          ),
        ),
      ),
    );
    expect(
      () => container.read(callMediaProvider),
      throwsA(
        predicate(
          (e) => e.toString().contains(
            'Production calls require APP_DATA_SOURCE=api',
          ),
        ),
      ),
    );
    container.dispose();
  });

  test(
    'report requires verified credit, retries same consumer_ref, never consumes client-side',
    () async {
      final repository = _Repository(fixtures);
      final generator = _Reports()..failOnce = true;
      final secure = InMemorySecureStore();
      final service = PaidReportService(
        repository,
        generator,
        secure,
        ownerId: 'user-1',
        locale: 'tr',
      );
      final product = CatalogProduct({
        'code': 'natal_report',
        'product_type': 'consumable',
        'store_product_id': 'natal.test',
        'entitlement_code': 'natal_report_credit',
      });
      await expectLater(service.createWithCredit(product), throwsStateError);
      expect(generator.created, 0);
      repository.summary = EntitlementSummary(
        fixtures['entitlements_active'] as Map<String, dynamic>,
      );
      await expectLater(
        service.createWithCredit(product),
        throwsA(isA<ApiException>()),
      );
      // The backend may have reserved the credit before the response was lost.
      // A retry must replay the saved reference even if balance is now zero.
      repository.summary = EntitlementSummary(
        fixtures['entitlements_free'] as Map<String, dynamic>,
      );
      expect(await service.createWithCredit(product), isA<PaidReportReady>());
      expect(generator.references, hasLength(2));
      expect(generator.references[0], generator.references[1]);
      expect(
        generator.references.first,
        matches(RegExp(r'^report-[0-9a-f]{32}$')),
      );
      expect(repository.consumerRefs, isEmpty);
      expect(
        await secure.read('paid_report_attempt:user-1:natal:self:tr'),
        isNull,
      );
    },
  );

  test('202 job keeps consumer_ref for idempotent retry', () async {
    final repository = _Repository(fixtures)
      ..summary = EntitlementSummary(
        fixtures['entitlements_active'] as Map<String, dynamic>,
      );
    final reports = _Reports()..queued = true;
    final secure = InMemorySecureStore();
    final service = PaidReportService(
      repository,
      reports,
      secure,
      ownerId: 'user-1',
      locale: 'tr',
    );
    final product = CatalogProduct({
      'code': 'natal_report',
      'product_type': 'consumable',
      'store_product_id': 'natal.test',
      'entitlement_code': 'natal_report_credit',
    });
    expect(await service.createWithCredit(product), isA<PaidReportQueued>());
    expect(await service.createWithCredit(product), isA<PaidReportQueued>());
    expect(reports.references[0], reports.references[1]);
    expect(
      await secure.read('paid_report_attempt:user-1:natal:self:tr'),
      reports.references[0],
    );
    expect(repository.consumerRefs, isEmpty);
  });

  test('409 conflict clears the attempt reference for a fresh retry', () async {
    final repository = _Repository(fixtures)
      ..summary = EntitlementSummary(
        fixtures['entitlements_active'] as Map<String, dynamic>,
      );
    final reports = _Reports()..failCode = 'report_credit_conflict';
    final secure = InMemorySecureStore();
    final service = PaidReportService(
      repository,
      reports,
      secure,
      ownerId: 'user-1',
      locale: 'tr',
    );
    final product = CatalogProduct({
      'code': 'natal_report',
      'product_type': 'consumable',
      'store_product_id': 'natal.test',
      'entitlement_code': 'natal_report_credit',
    });
    await expectLater(
      service.createWithCredit(product),
      throwsA(
        isA<ApiException>().having(
          (e) => e.code,
          'code',
          'report_credit_conflict',
        ),
      ),
    );
    expect(
      await secure.read('paid_report_attempt:user-1:natal:self:tr'),
      isNull,
    );
    await service.createWithCredit(product);
    expect(reports.references[0], isNot(reports.references[1]));
    expect(repository.consumerRefs, isEmpty);
  });
}

Future<void> _pump() async {
  await Future<void>.delayed(const Duration(milliseconds: 20));
}

class _Store implements BillingService {
  _Store([this.platform = StorePlatform.apple]);
  final events = StreamController<StorePurchaseEvent>.broadcast();
  int completed = 0, bought = 0;
  bool isAvailable = true;
  @override
  final StorePlatform platform;
  @override
  Stream<StorePurchaseEvent> get purchases => events.stream;
  void emit(StorePurchaseEvent event) => events.add(event);
  @override
  Future<bool> available() async => isAvailable;
  @override
  Future<List<StoreProduct>> loadProducts(Set<String> ids) async => [
    for (final id in ids)
      StoreProduct(
        id: id,
        title: 'Test planı',
        localizedPrice: '₺49,99',
        currencyCode: 'TRY',
      ),
  ];
  @override
  Future<void> buy(CatalogProduct product, String accountToken) async {
    bought++;
  }

  @override
  Future<List<StorePurchaseEvent>> restore() async => const [];
  @override
  Future<void> complete(StorePurchaseEvent event) async {
    completed++;
  }

  @override
  void dispose() => events.close();
}

class _Repository implements BillingRepository {
  _Repository(this.fixtures)
    : summary = EntitlementSummary(
        fixtures['entitlements_free'] as Map<String, dynamic>,
      );
  final Map<String, dynamic> fixtures;
  EntitlementSummary summary;
  int appleVerifications = 0, googleVerifications = 0, reconciliations = 0;
  bool failVerification = false;
  final consumerRefs = <String>[];
  @override
  Future<BillingAvailability> availability() async => BillingAvailability({
    'apple_configured': true,
    'google_configured': true,
    'external_marketplace_configured': false,
  });
  @override
  Future<ProductCatalog> products(StorePlatform platform) async =>
      ProductCatalog(fixtures['products'] as Map<String, dynamic>);
  @override
  Future<AccountTokens> accountTokens() async => AccountTokens({
    'apple_app_account_token': 'sanitized-account-token',
    'google_obfuscated_account_id': 'sanitized-account-id',
  });
  @override
  Future<EntitlementSummary> entitlements() async => summary;
  @override
  Future<PurchaseResult> verifyApple(
    String productCode, {
    String? jws,
    String? transactionId,
  }) async {
    appleVerifications++;
    if (failVerification) throw StateError('sanitized backend failure');
    return PurchaseResult(
      fixtures['apple_verification_response'] as Map<String, dynamic>,
    );
  }

  @override
  Future<PurchaseResult> verifyGoogle(
    String productCode,
    String purchaseToken,
  ) async {
    googleVerifications++;
    return PurchaseResult(
      fixtures['google_verification_response'] as Map<String, dynamic>,
    );
  }

  @override
  Future<ReconcileResult> reconcile(
    List<StorePurchaseEvent> purchases,
    Map<String, CatalogProduct> byStoreId,
  ) async {
    reconciliations++;
    return ReconcileResult({
      'verified': 0,
      'failed': <Map<String, String>>[],
      'entitlements': summary.json,
    });
  }

  @override
  Future<OrderPayment> orderPayment(String orderId) async =>
      OrderPayment(fixtures['payment_groups'] as Map<String, dynamic>);
  @override
  Future<OrderPaymentStart> payOrder(
    String orderId, {
    required String method,
    required String idempotencyKey,
  }) async => throw UnimplementedError();
  @override
  Future<void> consumeCredit(String entitlementCode, String consumerRef) async {
    consumerRefs.add(consumerRef);
  }
}

class _Reports implements ReportGenerator {
  int created = 0;
  bool failOnce = false;
  String? failCode;
  bool queued = false;
  final references = <String>[];
  @override
  Future<PaidReportDelivery> createReport(
    String type, {
    String? sourceId,
    required String consumerRef,
    bool payWithCoins = false,
  }) async {
    created++;
    references.add(consumerRef);
    if (failOnce) {
      failOnce = false;
      throw const ApiException(kind: ApiErrorKind.network);
    }
    if (failCode case final code?) {
      failCode = null;
      throw ApiException(kind: ApiErrorKind.unknown, code: code);
    }
    if (queued) {
      return PaidReportQueued(AIReportJob({'id': 'job-1', 'status': 'queued'}));
    }
    return PaidReportReady(
      AIReport({
        'id': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        'report_type': type,
        'status': 'completed',
      }),
    );
  }
}
