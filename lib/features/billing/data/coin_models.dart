import '../../../core/astrology/data/api_contract_dto.dart';
import '../../../core/astrology/data/production_models.dart';
import '../../profile/domain/user_profile.dart';

/// `GET /coins/wallet`.
class CoinWallet extends ContractRecord {
  CoinWallet(super.value) {
    number('balance');
  }
  int get balance => json['balance'] as int;
  int get lifetimeEarned => json['lifetime_earned'] as int? ?? 0;
  int get lifetimeSpent => json['lifetime_spent'] as int? ?? 0;
  SubscriptionTier get tier => SubscriptionTier.fromWire(optionalText('tier'));
  int get monthlyBonus => json['monthly_bonus'] as int? ?? 0;
  bool get adsEnabled => json['ads_enabled'] == true;
  int get adsWatchedToday => json['ads_watched_today'] as int? ?? 0;
  int get adsDailyLimit => json['ads_daily_limit'] as int? ?? 0;
  int get adRewardCoins => json['ad_reward_coins'] as int? ?? 0;
  int get bonusGranted => json['bonus_granted'] as int? ?? 0;
  bool get canWatchAd => adsEnabled && adsWatchedToday < adsDailyLimit;
}

/// One ledger row. Positive = earned, negative = spent.
class CoinTransaction extends ContractRecord {
  CoinTransaction(super.value) {
    text('id');
    number('amount');
  }
  String get id => text('id');
  int get amount => json['amount'] as int;
  int get balanceAfter => json['balance_after'] as int? ?? 0;

  /// purchase / ad_reward / monthly_bonus / spend / refund / purchase_reversal
  String get kind => text('kind');
  String get reason => optionalText('reason') ?? '';
  DateTime? get createdAt => ContractJson.optionalDate(json, 'created_at');
}

class SpendItem extends ContractRecord {
  SpendItem(super.value);
  String get code => text('code');
  int get price => json['price'] as int;
  bool get available => json['available'] == true;
}

class CoinPack extends ContractRecord {
  CoinPack(super.value);
  String get productCode => text('product_code');
  int get coins => json['coins'] as int;
}

class PlanInfo extends ContractRecord {
  PlanInfo(super.value);
  SubscriptionTier get tier => SubscriptionTier.fromWire(text('tier'));
  List<String> get products => strings('products');
  int get dailyDraws => json['daily_draws'] as int? ?? 0;
  int get monthlyCoins => json['monthly_coins'] as int? ?? 0;
  bool get adFree => json['ad_free'] == true;
  List<String> get features => strings('features');
  bool get includesPaidReports => json['includes_paid_reports'] == true;
}

/// How an item is available on a plan.
enum PlanAvailability {
  included,
  coins,
  none;

  static PlanAvailability fromWire(Object? value) => switch (value) {
    'included' => included,
    'coins' => coins,
    _ => none,
  };
}

/// One row of the plan comparison (`comparison` in `/coins/catalog`).
class ComparisonRow extends ContractRecord {
  ComparisonRow(super.value);
  String get key => text('key');

  /// The spend item that buys it when a plan answers [PlanAvailability.coins].
  String? get coinItem => optionalText('coin_item');

  PlanAvailability cell(SubscriptionTier tier) {
    final cells = json['cells'];
    return PlanAvailability.fromWire(cells is Map ? cells[tier.wire] : null);
  }

  /// A number the row carries for the plan (daily draws, monthly coins).
  int? value(SubscriptionTier tier) {
    final values = json['values'];
    final v = values is Map ? values[tier.wire] : null;
    return v is int ? v : null;
  }
}

/// `GET /coins/catalog`: what coins buy, the packs, the plans.
class CoinCatalog extends ContractRecord {
  CoinCatalog(super.value);
  List<SpendItem> get spendItems => records(
    'spend_items',
  ).map((r) => SpendItem(r.json)).toList(growable: false);
  List<CoinPack> get coinPacks => records(
    'coin_packs',
  ).map((r) => CoinPack(r.json)).toList(growable: false);
  List<PlanInfo> get plans =>
      records('plans').map((r) => PlanInfo(r.json)).toList(growable: false);
  List<ComparisonRow> get comparison => records(
    'comparison',
  ).map((r) => ComparisonRow(r.json)).toList(growable: false);
  int priceOf(String code) =>
      spendItems.where((i) => i.code == code).firstOrNull?.price ?? 0;
}

/// `GET /divination/allowance`.
class DrawAllowance extends ContractRecord {
  DrawAllowance(super.value);
  bool get enforced => json['enforced'] == true;
  int get dailyLimit => json['daily_limit'] as int? ?? 0;
  int get usedToday => json['used_today'] as int? ?? 0;
  int get remaining => json['remaining'] as int? ?? 0;
  int get extraDrawPrice => json['extra_draw_price'] as int? ?? 0;
  int get advancedSpreadPrice => json['advanced_spread_price'] as int? ?? 0;
}
