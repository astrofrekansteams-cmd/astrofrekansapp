import '../../../core/astrology/data/api_contract_dto.dart';
import '../../../core/astrology/data/production_models.dart';

enum StorePlatform { apple, google, unsupported }

enum StorePurchaseState {
  purchased,
  restored,
  pending,
  cancelled,
  failed,

  /// The store refused because this account already owns it (Google Play
  /// `ITEM_ALREADY_OWNED`): the answer is "restore", not "try again".
  alreadyOwned,
}

class BillingAvailability extends ContractRecord {
  BillingAvailability(super.value);
  bool get appleConfigured => json['apple_configured'] == true;
  bool get googleConfigured => json['google_configured'] == true;
  bool get externalConfigured =>
      json['external_marketplace_configured'] == true;
}

/// What the stores sell: four subscriptions and three AstroCoin packs. The
/// store ids come from the server; the app only refuses to offer anything
/// outside these codes, whatever a misconfigured server lists.
const Set<String> storeProductCodes = {
  'premium_monthly',
  'premium_yearly',
  'cosmic_plus_monthly',
  'cosmic_plus_yearly',
  'coins_120',
  'coins_350',
  'coins_800',
};

/// The one-off reports. Not sold in the stores: paid with AstroCoin, included
/// in a plan, or with a credit bought earlier. Described here (no store id)
/// so the reports screen does not depend on the store catalogue.
final List<CatalogProduct> oneOffReports = List.unmodifiable([
  for (final (code, credit) in const [
    ('natal_report', 'natal_report_credit'),
    ('synastry_report', 'synastry_report_credit'),
    ('annual_forecast_report', 'annual_forecast_credit'),
  ])
    CatalogProduct({
      'code': code,
      'product_type': 'consumable',
      'entitlement_code': credit,
      'store_product_id': '',
    }),
]);

class CatalogProduct extends ContractRecord {
  CatalogProduct(super.value) {
    text('code');
    text('product_type');
    text('store_product_id');
  }
  String get code => text('code');
  String get type => text('product_type');
  String get entitlementCode => text('entitlement_code');
  String get storeId => text('store_product_id');
  bool get isConsumable => type == 'consumable';
}

class ProductCatalog extends ContractRecord {
  ProductCatalog(super.value);
  String get platform => text('platform');
  List<CatalogProduct> get items => ContractJson.maps(
    json['items'],
  ).map(CatalogProduct.new).toList(growable: false);
}

class StoreProduct {
  const StoreProduct({
    required this.id,
    required this.title,
    required this.localizedPrice,
    required this.currencyCode,
  });
  final String id, title, localizedPrice, currencyCode;
}

/// Sensitive verification material remains in memory and is never formatted.
class StorePurchaseEvent {
  const StorePurchaseEvent({
    required this.platform,
    required this.productId,
    required this.state,
    this.verificationData,
    this.transactionId,
  });
  final StorePlatform platform;
  final String productId;
  final StorePurchaseState state;
  final String? verificationData, transactionId;
  @override
  String toString() => 'StorePurchaseEvent(redacted)';
}

class AccountTokens extends ContractRecord {
  AccountTokens(super.value);
  String get apple => text('apple_app_account_token');
  String get google => text('google_obfuscated_account_id');
  @override
  String toString() => 'AccountTokens(redacted)';
}

class EntitlementItem extends ContractRecord {
  EntitlementItem(super.value);
  String get code => text('entitlement_code');
  String get kind => text('kind');
  String get status => text('status');
  bool get active => json['active'] == true;
  DateTime? get expiresAt => ContractJson.optionalDate(json, 'expires_at');
  DateTime? get graceUntil => ContractJson.optionalDate(json, 'grace_until');
}

class EntitlementSummary extends ContractRecord {
  EntitlementSummary(super.value);
  bool get premium => json['premium'] == true;
  String get tier => text('tier');
  DateTime? get premiumExpiresAt =>
      ContractJson.optionalDate(json, 'premium_expires_at');
  Map<String, int> get credits =>
      Map<String, int>.from(json['credits'] as Map? ?? {});
  List<EntitlementItem> get items => ContractJson.maps(
    json['items'] ?? [],
  ).map(EntitlementItem.new).toList(growable: false);
  bool hasCredit(String code) => (credits[code] ?? 0) > 0;
}

class PurchaseResult extends ContractRecord {
  PurchaseResult(super.value);
  String get status => text('status');
  EntitlementSummary get entitlements =>
      EntitlementSummary(ContractJson.map(json['entitlements']));
}

class ReconcileResult extends ContractRecord {
  ReconcileResult(super.value);
  int get verified => json['verified'] as int;
  List<Map<String, dynamic>> get failed => ContractJson.maps(json['failed']);
  EntitlementSummary get entitlements =>
      EntitlementSummary(ContractJson.map(json['entitlements']));
}

class PaymentGroup extends ContractRecord {
  PaymentGroup(super.value);
  String get classification => text('classification');
  String get rail => text('rail');
  String get status => text('status');
  int? get amountMinor => json['amount_minor'] as int?;
  String get currency => text('currency');
  bool get reviewRequired =>
      classification == 'review_required' || status == 'blocked_review';
}

class PaymentLine extends ContractRecord {
  PaymentLine(super.value);
  String get classification => text('payment_classification');
  String? get storeProductCode => optionalText('store_product_code');
  String get status => text('line_status');
}

class OrderPayment extends ContractRecord {
  OrderPayment(super.value);
  String get orderId => text('order_id');
  bool get payableExternally => json['payable_externally'] == true;
  bool get blockedByReview => json['blocked_by_policy_review'] == true;
  List<PaymentGroup> get groups => ContractJson.maps(
    json['groups'],
  ).map(PaymentGroup.new).toList(growable: false);
  List<PaymentLine> get lines => ContractJson.maps(
    json['lines'],
  ).map(PaymentLine.new).toList(growable: false);
}

class OrderPaymentStart extends ContractRecord {
  OrderPaymentStart(super.value);
  String get status => text('status');
  String? get clientHandoff => optionalText('client_handoff');
  OrderPayment get order => OrderPayment(ContractJson.map(json['order']));
}
