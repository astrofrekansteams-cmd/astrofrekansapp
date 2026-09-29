import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/localization/b12_copy.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/storage/app_preferences.dart';
import '../../../core/widgets/astro_buttons.dart';
import '../../../core/widgets/astro_empty_state.dart';
import '../../auth/application/session_controller.dart';
import '../data/coin_repository.dart';
import 'entitlement_service.dart';

/// Spend items, as named by the server's coin catalogue. Prices always come
/// from `GET /coins/catalog`; the app never hard-codes one.
abstract final class CoinItem {
  static const aiDeepReading = 'ai_deep_reading';
  static const specialAnalysis = 'special_analysis';
  static const singlePremiumContent = 'single_premium_content';
}

/// A fresh idempotency reference for one coin purchase attempt. Reused on
/// every retry of that attempt so the server never charges twice.
String newCoinRef([String prefix = 'coin']) {
  final random = math.Random.secure();
  final hex = List.generate(
    24,
    (_) => random.nextInt(16).toRadixString(16),
  ).join();
  return '$prefix-$hex';
}

/// The server said the balance is short.
bool isInsufficientCoins(Object? error) =>
    error is ApiException && error.code == 'insufficient_coins';

/// Content opened with AstroCoins, keyed by what it is (`solar_return:2026`).
///
/// The value is the reference the server charged against: loading the same
/// content with it again is free, so a paid solar return stays open after a
/// restart. Kept per account on the device.
class CoinUnlocks extends Notifier<Map<String, String>> {
  String? _userId;

  AppPreferences? get _prefs {
    try {
      return ref.read(appPreferencesProvider);
    } on Object {
      return null; // not configured (tests): memory only
    }
  }

  @override
  Map<String, String> build() {
    _userId = ref.watch(currentUserProvider)?.id;
    final userId = _userId;
    final raw = userId == null ? null : _prefs?.coinUnlocks(userId);
    if (raw == null) return const {};
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map) return const {};
      return {
        for (final entry in decoded.entries)
          if (entry.key is String && entry.value is String)
            entry.key as String: entry.value as String,
      };
    } on FormatException {
      return const {};
    }
  }

  /// The reference for [key], created on first use.
  String unlock(String key) {
    final existing = state[key];
    if (existing != null) return existing;
    final created = newCoinRef('unlock');
    state = {...state, key: created};
    _save();
    return created;
  }

  /// Drop a reference the server did not charge (e.g. the balance was short).
  void forget(String key) {
    if (!state.containsKey(key)) return;
    state = {...state}..remove(key);
    _save();
  }

  void _save() {
    final userId = _userId;
    if (userId == null) return;
    _prefs?.setCoinUnlocks(userId, jsonEncode(state));
  }
}

final coinUnlocksProvider = NotifierProvider<CoinUnlocks, Map<String, String>>(
  CoinUnlocks.new,
);

/// Ask before spending: shows the catalogue price and the balance.
///
/// Returns true when the user confirmed and the balance covers it. A short
/// balance offers the wallet (buy / earn coins) and the plans instead.
Future<bool> confirmCoinSpend(
  BuildContext context,
  WidgetRef ref,
  String item,
) async {
  if (ref.read(coinRepositoryProvider) == null) return false;
  ref.invalidate(coinWalletProvider);
  final catalog = await ref.read(coinCatalogProvider.future);
  final wallet = await ref.read(coinWalletProvider.future);
  if (!context.mounted || catalog == null || wallet == null) return false;
  final price = catalog.priceOf(item);
  if (price <= 0) return false;
  final enough = wallet.balance >= price;
  String fill(String key) => b12(context, key)
      .replaceAll('{price}', '$price')
      .replaceAll('{balance}', '${wallet.balance}')
      .replaceAll('{item}', b12(context, 'spend_$item'));
  final choice = await showDialog<String>(
    context: context,
    builder: (context) => AlertDialog(
      key: ValueKey(enough ? 'coin-confirm' : 'coin-insufficient'),
      title: Text(fill(enough ? 'coin_confirm_title' : 'coin_short_title')),
      content: Text(fill(enough ? 'coin_confirm_body' : 'coin_short_body')),
      actions: [
        if (enough)
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(b12(context, 'cancel')),
          )
        else
          TextButton(
            onPressed: () => Navigator.pop(context, 'plans'),
            child: Text(b12(context, 'coin_offer_plans')),
          ),
        if (enough)
          FilledButton(
            key: const ValueKey('coin-confirm-pay'),
            onPressed: () => Navigator.pop(context, 'pay'),
            child: Text(fill('coin_confirm_pay')),
          )
        else
          FilledButton(
            key: const ValueKey('coin-go-wallet'),
            onPressed: () => Navigator.pop(context, 'wallet'),
            child: Text(b12(context, 'coin_get_more')),
          ),
      ],
    ),
  );
  if (!context.mounted) return false;
  switch (choice) {
    case 'plans':
      await context.push(AppRoutes.premium);
    case 'wallet':
      await context.push(AppRoutes.coins);
  }
  return choice == 'pay';
}

/// "Astro AI ile Derinleştir · 40 Coin": the catalogue price after a label,
/// or the label alone while the catalogue is unknown.
String withCoinPrice(
  BuildContext context,
  WidgetRef ref,
  String label,
  String item,
) {
  final price = ref.watch(coinCatalogProvider).asData?.value?.priceOf(item);
  if (price == null || price <= 0) return label;
  return '$label · $price ${b12(context, 'coin_word')}';
}

/// A plan-gated block: the plans, or this one piece for coins.
class CoinLockCard extends ConsumerWidget {
  const CoinLockCard({
    super.key,
    required this.unlockKey,
    required this.feature,
    this.item = CoinItem.singlePremiumContent,
  });

  /// What is opened (`solar_return:2026`); see [CoinUnlocks].
  final String unlockKey;
  final PremiumFeature feature;
  final String item;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final price = ref.watch(coinCatalogProvider).asData?.value?.priceOf(item);
    final tier = ref.watch(entitlementServiceProvider).requiredTier(feature);
    final plan = b12(context, 'tier_${tier.wire}');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AstroEmptyState(
          kind: AstroEmptyStateKind.premiumLocked,
          title: tier.isPaid
              ? b12(context, 'required_plan_feature').replaceAll('{plan}', plan)
              : b12(context, 'premium_required'),
          message: b12(context, 'coin_lock_note'),
          actionLabel: tier.isPaid
              ? b12(context, 'unlock_with_plan').replaceAll('{plan}', plan)
              : b12(context, 'unlock_premium'),
          onAction: () => context.push(
            tier.isPaid
                ? '${AppRoutes.premium}?tier=${tier.wire}'
                : AppRoutes.premium,
          ),
        ),
        if (price != null && price > 0)
          AstroOutlineButton(
            key: const ValueKey('coin-unlock'),
            label: b12(
              context,
              'coin_unlock_once',
            ).replaceAll('{price}', '$price'),
            icon: Icons.toll_outlined,
            onPressed: () async {
              if (await confirmCoinSpend(context, ref, item)) {
                ref.read(coinUnlocksProvider.notifier).unlock(unlockKey);
              }
            },
          ),
      ],
    );
  }
}

/// For a provider that loads coin-unlocked content: the reference to send,
/// and the bookkeeping around the request.
///
/// Watches the unlock so the content reloads once it is bought; a short
/// balance forgets the reference (nothing was charged) so the lock returns;
/// a paid load refreshes the wallet.
Future<T> loadWithCoins<T>(
  Ref ref,
  String unlockKey,
  Future<T> Function(String? coinRef) load,
) async {
  final coinRef = ref.watch(
    coinUnlocksProvider.select((unlocks) => unlocks[unlockKey]),
  );
  try {
    final result = await load(coinRef);
    if (coinRef != null) ref.invalidate(coinWalletProvider);
    return result;
  } on ApiException catch (error) {
    if (coinRef != null && isInsufficientCoins(error)) {
      ref.read(coinUnlocksProvider.notifier).forget(unlockKey);
    }
    rethrow;
  }
}
