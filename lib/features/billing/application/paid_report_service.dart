import 'dart:math';

import '../../../core/network/api_exception.dart';
import '../../../core/storage/secure_storage.dart';
import '../../astro_ai/data/ai_models.dart';
import '../data/billing_models.dart';
import '../data/billing_repository.dart';

sealed class PaidReportDelivery {
  const PaidReportDelivery();
}

class PaidReportReady extends PaidReportDelivery {
  const PaidReportReady(this.report);
  final AIReport report;
}

class PaidReportQueued extends PaidReportDelivery {
  const PaidReportQueued(this.job);
  final AIReportJob job;
}

abstract interface class ReportGenerator {
  Future<PaidReportDelivery> createReport(
    String type, {
    String? sourceId,
    required String consumerRef,
    bool payWithCoins = false,
  });
}

/// Backend owns reserve, consumption and delivery atomically. Only an opaque
/// idempotency reference is persisted for an interrupted retry.
class PaidReportService {
  const PaidReportService(
    this.billing,
    this.reports,
    this.store, {
    required this.ownerId,
    required this.locale,
  });
  final BillingRepository billing;
  final ReportGenerator reports;
  final SecureStore store;
  final String ownerId;
  final String locale;

  static String _newReference() {
    final random = Random.secure();
    final hex = List<int>.generate(
      16,
      (_) => random.nextInt(256),
    ).map((byte) => byte.toRadixString(16).padLeft(2, '0')).join();
    return 'report-$hex';
  }

  static String _typeOf(CatalogProduct product) => switch (product.code) {
    'natal_report' => 'natal',
    'synastry_report' => 'synastry',
    'annual_forecast_report' => 'yearly',
    _ => throw StateError('Unsupported paid report product'),
  };

  /// The same report paid with AstroCoins (the server's `special_analysis`
  /// price) instead of a store credit. The reference survives a restart so
  /// a retry never pays twice; a report that fails is refunded server-side.
  Future<PaidReportDelivery> createWithCoins(CatalogProduct product) async {
    final type = _typeOf(product);
    if (type == 'synastry') {
      throw StateError('Synastry source is required');
    }
    final key = 'paid_report_coins:$ownerId:$type:self:$locale';
    var consumerRef = await store.read(key);
    if (consumerRef == null) {
      consumerRef = _newReference();
      await store.write(key, consumerRef);
    }
    try {
      final delivery = await reports.createReport(
        type,
        consumerRef: consumerRef,
        payWithCoins: true,
      );
      if (delivery is PaidReportReady) await store.delete(key);
      return delivery;
    } on ApiException catch (error) {
      if (error.code == 'insufficient_coins' ||
          error.code == 'report_credit_conflict') {
        await store.delete(key); // nothing was charged
      }
      rethrow;
    }
  }

  Future<PaidReportDelivery> createWithCredit(
    CatalogProduct product, {
    String? sourceId,
  }) async {
    final type = _typeOf(product);
    if (type == 'synastry' && sourceId == null) {
      throw StateError('Synastry source is required');
    }
    final key =
        'paid_report_attempt:$ownerId:$type:${sourceId ?? "self"}:$locale';
    var consumerRef = await store.read(key);
    if (consumerRef == null) {
      final entitlements = await billing.entitlements();
      if (!entitlements.hasCredit(product.entitlementCode)) {
        throw StateError('Verified report credit required');
      }
      consumerRef = _newReference();
      await store.write(key, consumerRef);
    }
    try {
      final delivery = await reports.createReport(
        type,
        sourceId: sourceId,
        consumerRef: consumerRef,
      );
      // A 202 keeps the reference: a retry resumes the same reserved job.
      if (delivery is PaidReportReady) await store.delete(key);
      return delivery;
    } on ApiException catch (error) {
      if (error.code == 'report_credit_conflict' ||
          error.code == 'report_credit_unavailable') {
        await store.delete(key);
      }
      rethrow;
    }
  }
}
