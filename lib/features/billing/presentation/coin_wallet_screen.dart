import 'package:flutter/foundation.dart' show kReleaseMode;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/localization/b12_copy.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../application/entitlement_controller.dart';
import 'purchase_status.dart';
import '../data/coin_models.dart';
import '../data/billing_models.dart';
import '../data/coin_repository.dart';

/// AstroCoin: balance, ways to earn, what coins buy, and the history.
class CoinWalletScreen extends ConsumerStatefulWidget {
  const CoinWalletScreen({super.key});
  @override
  ConsumerState<CoinWalletScreen> createState() => _CoinWalletState();
}

class _CoinWalletState extends ConsumerState<CoinWalletScreen> {
  bool _watching = false;

  Future<void> _watchAd() async {
    final repo = ref.read(coinRepositoryProvider);
    if (repo == null || _watching) return;
    setState(() => _watching = true);
    final messenger = ScaffoldMessenger.of(context);
    String text(String key) => b12(context, key);
    final closed = text('coin_ad_closed');
    final rewarded = text('coin_ad_rewarded');
    final limit = text('coin_ad_limit');
    final unavailable = text('coin_ad_unavailable');
    final failed = text('error');
    String message;
    try {
      final token = await ref.read(rewardedAdServiceProvider).show();
      if (token == null) {
        message = closed;
      } else {
        final wallet = await repo.rewardAd(token);
        message = rewarded.replaceAll('{coins}', '${wallet.adRewardCoins}');
        ref
          ..invalidate(coinWalletProvider)
          ..invalidate(coinTransactionsProvider);
      }
    } on ApiException catch (e) {
      message = switch (e.code) {
        'ad_reward_limit_reached' => limit,
        'ad_rewards_unavailable' => unavailable,
        _ => failed,
      };
    }
    if (!mounted) return;
    setState(() => _watching = false);
    messenger.showSnackBar(SnackBar(content: Text(message)));
  }

  /// Rewarded ads pay only through a real ad network. The demo service is a
  /// development aid: a release build never offers it.
  bool _adsReady(CoinWallet wallet) =>
      wallet.adsEnabled &&
      (!ref.watch(rewardedAdServiceProvider).isDemo || !kReleaseMode);

  @override
  Widget build(BuildContext context) {
    final wallet = ref.watch(coinWalletProvider);
    final catalog = ref.watch(coinCatalogProvider).asData?.value;
    final history = ref.watch(coinTransactionsProvider);
    return CorePage(
      title: 'coin_wallet',
      children: [
        ApiStateView<CoinWallet?>(
          value: wallet,
          onRetry: () => ref.invalidate(coinWalletProvider),
          builder: (w) => w == null
              ? AstroCard(child: Text(b12(context, 'demo_unavailable')))
              : _BalanceCard(wallet: w),
        ),
        if (wallet.asData?.value case final CoinWallet w) ...[
          AstroSectionTitle(title: b12(context, 'wallet_earn')),
          _EarnCard(
            wallet: w,
            adsReady: _adsReady(w),
            watching: _watching,
            onWatchAd: _watchAd,
          ),
          AstroSectionTitle(title: b12(context, 'wallet_buy')),
          _BuyCard(packs: catalog?.coinPacks ?? const []),
          if (catalog != null) ...[
            AstroSectionTitle(title: b12(context, 'wallet_spend')),
            _SpendCard(catalog: catalog),
          ],
        ],
        AstroSectionTitle(title: b12(context, 'wallet_recent')),
        ApiStateView<List<CoinTransaction>>(
          value: history,
          onRetry: () => ref.invalidate(coinTransactionsProvider),
          builder: (rows) => rows.isEmpty
              ? AstroCard(child: Text(b12(context, 'coin_history_empty')))
              : AstroCard(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                    vertical: AppSpacing.sm,
                  ),
                  child: Column(
                    children: [
                      for (final (i, row) in rows.indexed) ...[
                        if (i > 0)
                          const Divider(color: AppColors.hairline, height: 1),
                        _HistoryRow(row: row),
                      ],
                    ],
                  ),
                ),
        ),
      ],
    );
  }
}

class _BalanceCard extends StatelessWidget {
  const _BalanceCard({required this.wallet});
  final CoinWallet wallet;

  @override
  Widget build(BuildContext context) => AstroCard(
    key: const ValueKey('coin-balance'),
    borderColor: AppColors.hairlineStrong,
    gradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [
        AppColors.gold.withValues(alpha: 0.18),
        AppColors.surface.withValues(alpha: 0.92),
      ],
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(b12(context, 'coin_balance'), style: AppTypography.bodySmall),
        const SizedBox(height: AppSpacing.xs),
        Semantics(
          label: '${wallet.balance} ${b12(context, 'coins_unit')}',
          excludeSemantics: true,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const CoinGlyph(size: 30),
              const SizedBox(width: AppSpacing.sm),
              // UI sans: the serif's old-style numerals read "0" as "o".
              Text(
                '${wallet.balance}',
                style: AppTypography.labelLarge.copyWith(
                  color: AppColors.goldBright,
                  fontSize: 34,
                  fontWeight: FontWeight.w600,
                  height: 1.1,
                ),
              ),
              const SizedBox(width: AppSpacing.xs),
              Text(
                b12(context, 'coins_unit'),
                style: AppTypography.titleMedium,
              ),
            ],
          ),
        ),
        if (wallet.bonusGranted > 0) ...[
          const SizedBox(height: AppSpacing.sm),
          AstroBadge(
            label: b12(
              context,
              'coin_bonus_granted',
            ).replaceAll('{coins}', '${wallet.bonusGranted}'),
            icon: Icons.card_giftcard,
          ),
        ],
      ],
    ),
  );
}

class _EarnCard extends StatelessWidget {
  const _EarnCard({
    required this.wallet,
    required this.adsReady,
    required this.watching,
    required this.onWatchAd,
  });
  final CoinWallet wallet;
  final bool adsReady;
  final bool watching;
  final VoidCallback onWatchAd;

  @override
  Widget build(BuildContext context) => AstroCard(
    key: const ValueKey('wallet-earn'),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _EarnRow(
          icon: Icons.card_giftcard,
          title: b12(context, 'bonus_title'),
          detail: wallet.monthlyBonus > 0
              ? b12(
                  context,
                  'coin_monthly_bonus',
                ).replaceAll('{coins}', '${wallet.monthlyBonus}')
              : b12(context, 'coin_monthly_bonus_upgrade'),
        ),
        const Divider(color: AppColors.hairline, height: AppSpacing.lg),
        if (adsReady) ...[
          AstroButton(
            key: const ValueKey('watch-ad'),
            label: b12(
              context,
              'coin_watch_ad',
            ).replaceAll('{coins}', '${wallet.adRewardCoins}'),
            icon: Icons.play_circle_outline,
            isLoading: watching,
            onPressed: wallet.canWatchAd && !watching ? onWatchAd : null,
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            b12(context, 'coin_ads_left')
                .replaceAll(
                  '{left}',
                  '${(wallet.adsDailyLimit - wallet.adsWatchedToday).clamp(0, 999)}',
                )
                .replaceAll('{limit}', '${wallet.adsDailyLimit}'),
            style: AppTypography.bodySmall,
          ),
        ] else
          _EarnRow(
            key: const ValueKey('ads-soon'),
            icon: Icons.play_circle_outline,
            title: b12(context, 'coin_ads_title'),
            detail: wallet.tier.isPaid
                ? b12(context, 'coin_ads_paid_plan')
                : b12(context, 'coin_ads_soon_note'),
            badge: wallet.tier.isPaid ? null : b12(context, 'coming_soon'),
            muted: true,
          ),
      ],
    ),
  );
}

class _EarnRow extends StatelessWidget {
  const _EarnRow({
    super.key,
    required this.icon,
    required this.title,
    required this.detail,
    this.badge,
    this.muted = false,
  });
  final IconData icon;
  final String title;
  final String detail;
  final String? badge;
  final bool muted;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Icon(icon, color: muted ? AppColors.textSubtle : AppColors.gold),
      const SizedBox(width: AppSpacing.md),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: AppTypography.labelLarge.copyWith(
                color: muted ? AppColors.ivoryMuted : AppColors.ivory,
              ),
            ),
            const SizedBox(height: 2),
            Text(detail, style: AppTypography.bodySmall),
          ],
        ),
      ),
      if (badge != null) ...[
        const SizedBox(width: AppSpacing.sm),
        AstroBadge(label: badge!),
      ],
    ],
  );
}

/// Coin packs at the store's localized price. Coins are credited only after
/// the server verifies the purchase.
class _BuyCard extends ConsumerWidget {
  const _BuyCard({required this.packs});
  final List<CoinPack> packs;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final controller = ref.watch(entitlementControllerProvider);
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final busy = busyPurchasePhases.contains(controller.state.purchase);
        return AstroCard(
          key: const ValueKey('wallet-buy'),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                b12(context, 'coin_packs_note'),
                style: AppTypography.bodySmall,
              ),
              for (final pack in packs) ...[
                const SizedBox(height: AppSpacing.sm),
                Builder(
                  builder: (context) {
                    final product = controller.catalog
                        .where((p) => p.code == pack.productCode)
                        .firstOrNull;
                    final price = product == null
                        ? null
                        : controller
                              .localizedProducts[product.storeId]
                              ?.localizedPrice;
                    return Column(
                      key: ValueKey('pack-${pack.productCode}'),
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Wrap(
                          spacing: 12,
                          runSpacing: 8,
                          alignment: WrapAlignment.spaceBetween,
                          children: [
                            Text(
                              '${pack.coins} AstroCoin',
                              style: AppTypography.labelLarge,
                            ),
                            Text(
                              price ?? '—',
                              style: AppTypography.titleMedium.copyWith(
                                color: AppColors.goldBright,
                              ),
                            ),
                          ],
                        ),
                        TextButton(
                          onPressed: busy || product == null || price == null
                              ? null
                              : () => controller.buy(product),
                          child: Text(b12(context, 'buy')),
                        ),
                      ],
                    );
                  },
                ),
              ],
              if (!controller.storeAvailable) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(
                  b12(context, 'store_unavailable_note'),
                  style: AppTypography.bodySmall,
                ),
              ],
              const SizedBox(height: AppSpacing.sm),
              if (controller.store.platform != StorePlatform.unsupported)
                TextButton.icon(
                  onPressed: busy || controller.catalogLoading
                      ? null
                      : controller.loadCatalog,
                  icon: const Icon(Icons.refresh),
                  label: Text(
                    b12(
                      context,
                      controller.catalogLoading
                          ? 'store_loading'
                          : 'store_reload',
                    ),
                  ),
                ),
              PurchaseStatusNotice(state: controller.state),
            ],
          ),
        );
      },
    );
  }
}

class _SpendCard extends StatelessWidget {
  const _SpendCard({required this.catalog});
  final CoinCatalog catalog;

  /// Where each spend is used.
  static String? _route(String code) => switch (code) {
    'extra_draw' || 'advanced_spread' || 'ai_deep_reading' => AppRoutes.tarot,
    'special_analysis' => AppRoutes.aiReports,
    'single_premium_content' => '${AppRoutes.forecasts}?period=monthly',
    _ => null,
  };

  @override
  Widget build(BuildContext context) => AstroCard(
    key: const ValueKey('wallet-spend'),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final item in catalog.spendItems)
          InkWell(
            onTap: item.available && _route(item.code) != null
                ? () => context.push(_route(item.code)!)
                : null,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      b12(context, 'spend_${item.code}'),
                      style: AppTypography.bodyMedium.copyWith(
                        color: item.available
                            ? AppColors.ivory
                            : AppColors.textSubtle,
                      ),
                    ),
                  ),
                  if (!item.available)
                    Padding(
                      padding: const EdgeInsets.only(right: AppSpacing.sm),
                      child: AstroBadge(label: b12(context, 'coming_soon')),
                    ),
                  const CoinGlyph(size: 14),
                  const SizedBox(width: 4),
                  Text('${item.price}', style: AppTypography.labelLarge),
                  const Icon(
                    Icons.chevron_right,
                    size: 18,
                    color: AppColors.textSubtle,
                  ),
                ],
              ),
            ),
          ),
      ],
    ),
  );
}

/// Spend reasons the catalogue names (`spend_items`).
const _spendReasons = {
  'extra_draw',
  'advanced_spread',
  'ai_deep_reading',
  'special_analysis',
  'single_premium_content',
};

class _HistoryRow extends StatelessWidget {
  const _HistoryRow({required this.row});
  final CoinTransaction row;

  @override
  Widget build(BuildContext context) {
    final positive = row.amount > 0;
    final when = row.createdAt?.toLocal();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Row(
        children: [
          Icon(
            switch (row.kind) {
              'purchase' => Icons.shopping_bag_outlined,
              'ad_reward' => Icons.play_circle_outline,
              'monthly_bonus' => Icons.card_giftcard,
              'refund' => Icons.undo,
              _ => Icons.auto_awesome,
            },
            size: 20,
            color: AppColors.gold,
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  row.kind == 'spend' && _spendReasons.contains(row.reason)
                      ? b12(context, 'spend_${row.reason}')
                      : b12(context, 'coin_kind_${row.kind}'),
                  style: AppTypography.labelLarge,
                ),
                if (when != null)
                  Text(
                    '${when.day.toString().padLeft(2, '0')}.${when.month.toString().padLeft(2, '0')}.${when.year} ${when.hour.toString().padLeft(2, '0')}:${when.minute.toString().padLeft(2, '0')}',
                    style: AppTypography.bodySmall,
                  ),
              ],
            ),
          ),
          Text(
            '${positive ? '+' : ''}${row.amount}',
            style: AppTypography.titleMedium.copyWith(
              color: positive ? AppColors.success : AppColors.ivoryMuted,
            ),
          ),
        ],
      ),
    );
  }
}

/// A small gold coin, drawn (no asset needed).
class CoinGlyph extends StatelessWidget {
  const CoinGlyph({super.key, this.size = 18});
  final double size;
  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: AppColors.goldGradient,
        border: Border.all(color: AppColors.goldDeep, width: size / 14),
      ),
      child: Text(
        '✦',
        style: TextStyle(
          fontSize: size * 0.55,
          height: 1,
          color: AppColors.onGold,
        ),
      ),
    ),
  );
}

/// Balance chip for headers (profile, divination). Taps open the wallet.
class CoinBalanceChip extends ConsumerWidget {
  const CoinBalanceChip({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final wallet = ref.watch(coinWalletProvider).asData?.value;
    if (wallet == null) return const SizedBox.shrink();
    return Semantics(
      button: true,
      label: '${wallet.balance} ${b12(context, 'coins_unit')}',
      excludeSemantics: true,
      child: InkWell(
        key: const ValueKey('coin-chip'),
        borderRadius: AppRadius.brPill,
        onTap: () => context.push(AppRoutes.coins),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            borderRadius: AppRadius.brPill,
            border: Border.all(color: AppColors.hairlineStrong),
            color: AppColors.surface.withValues(alpha: 0.6),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CoinGlyph(size: 16),
              const SizedBox(width: 6),
              Text('${wallet.balance}', style: AppTypography.labelLarge),
            ],
          ),
        ),
      ),
    );
  }
}
