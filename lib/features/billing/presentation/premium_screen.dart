import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:intl/intl.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/widgets.dart';
import '../../profile/domain/user_profile.dart';
import '../application/entitlement_controller.dart';
import '../application/entitlement_service.dart';
import '../data/billing_models.dart';
import '../data/coin_models.dart';
import '../data/coin_repository.dart';
import 'coin_wallet_screen.dart' show CoinGlyph;
import 'purchase_status.dart';
import 'subscription_actions.dart';

/// Plans (Ücretsiz / Premium / Kozmik+) and AstroCoin packs.
///
/// What each plan includes comes from the server catalogue (`/coins/catalog`);
/// prices come only from the stores. Access changes only after the server
/// verifies a purchase.
class PremiumScreen extends ConsumerWidget {
  const PremiumScreen({super.key, this.initialTier});
  final String? initialTier;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final controller = ref.watch(entitlementControllerProvider);
    final current = ref.watch(subscriptionTierProvider);
    final catalogValue = ref.watch(coinCatalogProvider);
    final catalog = catalogValue.asData?.value;
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final state = controller.state;
        final busy = busyPurchasePhases.contains(state.purchase);
        CatalogProduct? product(String code) =>
            controller.catalog.where((p) => p.code == code).firstOrNull;
        String? price(String code) {
          final p = product(code);
          return p == null
              ? null
              : controller.localizedProducts[p.storeId]?.localizedPrice;
        }

        final plans = [...?catalog?.plans];
        int rank(PlanInfo p) => p.tier.wire == initialTier
            ? -1
            : p.tier == SubscriptionTier.free
            ? 3
            : p.tier.index;
        plans.sort((a, b) => rank(a).compareTo(rank(b)));
        Future<void> retryCatalog() async {
          ref.invalidate(coinCatalogProvider);
          await controller.loadCatalog();
        }

        return AstroScaffold(
          appBar: AppBar(title: Text(b12(context, 'plans_title'))),
          bottomNavigationBar:
              state.purchase == PurchasePhase.idle && state.errorCode == null
              ? null
              : SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: PurchaseStatusNotice(state: state),
                  ),
                ),
          body: ListView(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.lg,
              AppSpacing.md,
              AppSpacing.lg,
              AppSpacing.huge,
            ),
            children: [
              Text(
                b12(context, 'plans_headline'),
                style: AppTypography.headlineMedium,
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                b12(context, 'subscription_benefit_note'),
                style: AppTypography.bodyMedium,
              ),
              const SizedBox(height: AppSpacing.md),
              _StatusCard(state: state, tier: current),
              if (current.isPaid) ...[
                AstroOutlineButton(
                  key: const ValueKey('manage-subscription'),
                  label: b12(context, 'subscription_manage'),
                  onPressed: () => manageSubscription(context, ref),
                ),
                Text(
                  b12(context, 'subscription_period_note'),
                  style: AppTypography.bodySmall,
                ),
              ],
              if (initialTier != null &&
                  plans.any((p) => p.tier.wire == initialTier))
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    b12(
                      context,
                      'subscription_focus',
                    ).replaceAll('{plan}', b12(context, 'tier_$initialTier')),
                  ),
                ),
              const SizedBox(height: AppSpacing.md),
              // Distinct states: loading is bounded by the request timeout;
              // an error or an empty catalogue says so and offers a retry.
              // An error wins over loading: Riverpod retries a failed
              // provider in the background, and that retry must not look
              // like an endless load.
              if (catalogValue.hasError && catalog == null)
                _CatalogProblem(
                  key: const ValueKey('plans-error'),
                  message: b12(context, 'plans_load_failed'),
                  onRetry: retryCatalog,
                )
              else if (catalogValue.isLoading && catalog == null)
                const AstroSkeletonCard(
                  key: ValueKey('plans-loading'),
                  lines: 4,
                )
              else if (plans.isEmpty)
                _CatalogProblem(
                  key: const ValueKey('plans-empty'),
                  message: b12(context, 'plans_empty'),
                  onRetry: retryCatalog,
                )
              else ...[
                if (!controller.storeAvailable ||
                    controller.catalog.isEmpty ||
                    controller.localizedProducts.length <
                        controller.catalog.length)
                  AstroCard(
                    key: const ValueKey('plans-store-unavailable'),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          b12(
                            context,
                            controller.store.platform ==
                                    StorePlatform.unsupported
                                ? 'store_unavailable_note'
                                : 'store_retry_note',
                          ),
                        ),
                        if (controller.store.platform !=
                            StorePlatform.unsupported)
                          TextButton.icon(
                            key: const ValueKey('reload-store-prices'),
                            onPressed: controller.catalogLoading || busy
                                ? null
                                : retryCatalog,
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
                      ],
                    ),
                  ),
                for (final plan in plans) ...[
                  _PlanCard(
                    plan: plan,
                    current: current == plan.tier,
                    onManage: () => manageSubscription(context, ref),
                    price: price,
                    onBuy: busy
                        ? null
                        : (code) {
                            final p = product(code);
                            if (p != null) controller.buy(p);
                          },
                  ),
                  const SizedBox(height: AppSpacing.md),
                ],
              ],
              const SizedBox(height: AppSpacing.md),
              if (catalog != null && catalog.comparison.isNotEmpty)
                ExpansionTile(
                  key: const ValueKey('expand-plan-comparison'),
                  title: Text(b12(context, 'cmp_title')),
                  children: [
                    _ComparisonTable(catalog: catalog, current: current),
                  ],
                ),
              if (plans.isNotEmpty)
                _MonthlyBonusCard(plans: plans, current: current),
              const SizedBox(height: AppSpacing.md),
              AstroOutlineButton(
                label: b12(context, 'coin_wallet'),
                icon: Icons.account_balance_wallet_outlined,
                onPressed: () => context.push(AppRoutes.coins),
              ),
              Text(
                b12(context, 'subscription_renewal'),
                style: AppTypography.bodySmall,
              ),
              const SubscriptionLegalLinks(),
              const SizedBox(height: AppSpacing.lg),
              AstroOutlineButton(
                label: b12(context, 'restore_purchases'),
                onPressed: controller.storeAvailable && !busy
                    ? controller.restore
                    : null,
              ),
              const SizedBox(height: AppSpacing.sm),
            ],
          ),
        );
      },
    );
  }
}

/// The catalogue did not arrive (network) or arrived empty: say which, and
/// offer to try again - never an endless skeleton.
class _CatalogProblem extends StatelessWidget {
  const _CatalogProblem({
    super.key,
    required this.message,
    required this.onRetry,
  });
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => AstroCard(
    child: Column(
      children: [
        Text(message, textAlign: TextAlign.center),
        const SizedBox(height: AppSpacing.sm),
        AstroOutlineButton(
          key: const ValueKey('plans-retry'),
          label: b12(context, 'retry'),
          icon: Icons.refresh,
          onPressed: onRetry,
        ),
      ],
    ),
  );
}

class _StatusCard extends StatelessWidget {
  const _StatusCard({required this.state, required this.tier});
  final EntitlementSnapshot state;
  final SubscriptionTier tier;

  @override
  Widget build(BuildContext context) => AstroCard(
    key: const ValueKey('plan-status'),
    child: Row(
      children: [
        const Icon(Icons.workspace_premium_outlined, color: AppColors.gold),
        const SizedBox(width: AppSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                state.phase == EntitlementPhase.loading
                    ? b12(context, 'plan_checking')
                    : '${b12(context, 'plan_current')}: ${b12(context, 'tier_${tier.wire}')}',
                style: AppTypography.titleMedium.copyWith(
                  color: AppColors.gold,
                ),
              ),
              if (_phaseNote(state.phase) case final String note)
                Text(b12(context, note), style: AppTypography.bodySmall),
              if (state.summary?.premiumExpiresAt case final DateTime until)
                Text(
                  '${b12(context, 'plan_until')}: ${DateFormat.yMMMd(Localizations.localeOf(context).languageCode).format(until.toLocal())}',
                  style: AppTypography.bodySmall,
                ),
            ],
          ),
        ),
      ],
    ),
  );

  static String? _phaseNote(EntitlementPhase phase) => switch (phase) {
    EntitlementPhase.gracePeriod => 'plan_grace',
    EntitlementPhase.cancelledUntilExpiry => 'plan_cancelled_until',
    EntitlementPhase.expired => 'plan_expired',
    EntitlementPhase.error => 'plan_error',
    _ => null,
  };
}

/// The monthly AstroCoin bonus: what the current plan adds, or what an
/// upgrade would.
class _MonthlyBonusCard extends StatelessWidget {
  const _MonthlyBonusCard({required this.plans, required this.current});
  final List<PlanInfo> plans;
  final SubscriptionTier current;

  @override
  Widget build(BuildContext context) {
    int coinsOf(SubscriptionTier tier) =>
        plans.where((p) => p.tier == tier).firstOrNull?.monthlyCoins ?? 0;
    final mine = coinsOf(current);
    final note = mine > 0
        ? b12(context, 'bonus_yours').replaceAll('{coins}', '$mine')
        : b12(context, 'bonus_upgrade')
              .replaceAll('{premium}', '${coinsOf(SubscriptionTier.premium)}')
              .replaceAll(
                '{cosmic}',
                '${coinsOf(SubscriptionTier.cosmicPlus)}',
              );
    return AstroCard(
      key: const ValueKey('plan-monthly-bonus'),
      borderColor: AppColors.gold,
      child: Row(
        children: [
          const CoinGlyph(size: 34),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  mine > 0
                      ? '+$mine AstroCoin / ${b12(context, 'month_word')}'
                      : b12(context, 'bonus_title'),
                  style: AppTypography.titleLarge.copyWith(
                    color: AppColors.goldBright,
                  ),
                ),
                const SizedBox(height: 2),
                Text(note, style: AppTypography.bodySmall),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// ÜCRETSİZ / PREMIUM / KOZMİK+ side by side: "✓ dahil", "Coin ile" or
/// "— dahil değil" for every row the server lists.
class _ComparisonTable extends StatelessWidget {
  const _ComparisonTable({required this.catalog, required this.current});
  final CoinCatalog catalog;
  final SubscriptionTier current;

  static const _tiers = SubscriptionTier.values;

  @override
  Widget build(BuildContext context) {
    Widget header(SubscriptionTier tier) => Expanded(
      flex: 3,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
        decoration: tier == current
            ? BoxDecoration(
                color: AppColors.gold.withValues(alpha: 0.14),
                borderRadius: AppRadius.brMd,
              )
            : null,
        child: Text(
          b12(context, 'tier_upper_${tier.wire}'),
          textAlign: TextAlign.center,
          style: AppTypography.labelSmall.copyWith(
            color: tier == SubscriptionTier.free
                ? AppColors.ivory
                : AppColors.goldBright,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );

    Widget cell(ComparisonRow row, SubscriptionTier tier) {
      final value = row.value(tier);
      final item = row.coinItem;
      final price = item == null ? 0 : catalog.priceOf(item);
      final (icon, color, label) = switch (row.cell(tier)) {
        PlanAvailability.included => (
          Icons.check,
          AppColors.goldBright,
          value != null && value > 0 ? '$value' : b12(context, 'cmp_included'),
        ),
        PlanAvailability.coins => (
          Icons.toll_outlined,
          AppColors.ivory,
          price > 0
              ? '${b12(context, 'cmp_coins')}\n$price'
              : b12(context, 'cmp_coins'),
        ),
        PlanAvailability.none => (
          Icons.remove,
          AppColors.textSubtle,
          b12(context, 'cmp_none'),
        ),
      };
      return Expanded(
        flex: 3,
        child: Semantics(
          label: '${b12(context, 'tier_${tier.wire}')}: $label',
          excludeSemantics: true,
          child: Column(
            children: [
              Icon(icon, size: 16, color: color),
              Text(
                label,
                textAlign: TextAlign.center,
                style: AppTypography.labelSmall.copyWith(color: color),
              ),
            ],
          ),
        ),
      );
    }

    return AstroCard(
      key: const ValueKey('plan-comparison'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            b12(context, 'cmp_title'),
            style: AppTypography.titleMedium.copyWith(color: AppColors.gold),
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              const Expanded(flex: 4, child: SizedBox.shrink()),
              for (final tier in _tiers) header(tier),
            ],
          ),
          for (final row in catalog.comparison) ...[
            const Divider(height: AppSpacing.md),
            Row(
              key: ValueKey('cmp-${row.key}'),
              children: [
                Expanded(
                  flex: 4,
                  child: Text(
                    b12(context, 'cmp_${row.key}'),
                    style: AppTypography.bodySmall.copyWith(
                      color: AppColors.ivory,
                    ),
                  ),
                ),
                for (final tier in _tiers) cell(row, tier),
              ],
            ),
          ],
          const SizedBox(height: AppSpacing.sm),
          Text(b12(context, 'cmp_note'), style: AppTypography.bodySmall),
        ],
      ),
    );
  }
}

/// The plan-level promises, in display order, each gated on the catalogue.
List<String> planHighlights(PlanInfo plan) => [
  switch (plan.tier) {
    SubscriptionTier.free => 'plan_free_daily',
    SubscriptionTier.premium => 'plan_premium_daily',
    SubscriptionTier.cosmicPlus => 'plan_cosmic_everything',
  },
  if (plan.tier == SubscriptionTier.free) 'plan_free_ads',
  if (plan.adFree) 'plan_ad_free',
  if (plan.features.contains('monthly_forecast')) 'plan_monthly_forecast',
  if (plan.features.contains('advanced_transits')) 'plan_advanced_transits',
  if (plan.features.contains('synastry')) 'plan_relationships',
  if (plan.features.contains('yearly_forecast')) 'plan_yearly_forecast',
  if (plan.features.contains('solar_return')) 'plan_returns',
  if (plan.features.contains('advanced_ai')) 'plan_advanced_ai',
  if (plan.includesPaidReports) 'plan_reports',
];

class _PlanCard extends StatelessWidget {
  const _PlanCard({
    required this.plan,
    required this.current,
    required this.price,
    required this.onBuy,
    required this.onManage,
  });

  final PlanInfo plan;
  final bool current;
  final String? Function(String code) price;
  final void Function(String productCode)? onBuy;
  final VoidCallback onManage;

  @override
  Widget build(BuildContext context) {
    final cosmic = plan.tier == SubscriptionTier.cosmicPlus;
    final accent = cosmic ? AppColors.goldBright : AppColors.gold;
    return AstroCard(
      key: ValueKey('plan-${plan.tier.wire}'),
      borderColor: current || cosmic ? accent : AppColors.hairline,
      gradient: cosmic
          ? LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                AppColors.gold.withValues(alpha: 0.16),
                AppColors.surface.withValues(alpha: 0.92),
              ],
            )
          : AppColors.cardGradient,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  b12(context, 'tier_${plan.tier.wire}'),
                  style: AppTypography.headlineMedium.copyWith(color: accent),
                ),
              ),
              if (current)
                AstroBadge(label: b12(context, 'plan_yours'), icon: Icons.check)
              else if (cosmic)
                AstroBadge(
                  label: b12(context, 'plan_best'),
                  icon: Icons.auto_awesome,
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          if (plan.products.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(
              b12(
                context,
                current
                    ? 'subscription_period_note'
                    : 'subscription_switch_note',
              ),
              style: AppTypography.bodySmall,
            ),
            Text(
              b12(context, 'subscription_renewal'),
              style: AppTypography.bodySmall,
            ),
            const SizedBox(height: AppSpacing.md),
            for (final code in plan.products)
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.sm),
                child: _BuyRow(
                  label: b12(
                    context,
                    code.endsWith('yearly') ? 'plan_yearly' : 'plan_monthly',
                  ),
                  price: price(code),
                  actionLabel: current
                      ? b12(context, 'subscription_period_change')
                      : b12(context, 'buy'),
                  onPressed: current
                      ? onManage
                      : onBuy == null || price(code) == null
                      ? null
                      : () => onBuy!(code),
                ),
              ),
          ],
          const SizedBox(height: AppSpacing.md),
          for (final key in planHighlights(plan))
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.check_circle_outline, size: 16, color: accent),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      b12(context, key)
                          .replaceAll('{draws}', '${plan.dailyDraws}')
                          .replaceAll('{coins}', '${plan.monthlyCoins}'),
                      style: AppTypography.bodyMedium,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _BuyRow extends StatelessWidget {
  const _BuyRow({
    required this.label,
    required this.price,
    required this.onPressed,
    required this.actionLabel,
  });
  final String actionLabel;
  final String label;
  final String? price;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(
      horizontal: AppSpacing.md,
      vertical: AppSpacing.sm,
    ),
    decoration: BoxDecoration(
      borderRadius: AppRadius.brMd,
      border: Border.all(color: AppColors.hairline),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          alignment: WrapAlignment.spaceBetween,
          spacing: 12,
          runSpacing: 6,
          children: [
            Text(label, style: AppTypography.labelLarge),
            Text(
              price ?? '—',
              style: AppTypography.titleMedium.copyWith(
                color: AppColors.goldBright,
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        FilledButton(
          onPressed: onPressed,
          child: Text(actionLabel, textAlign: TextAlign.center),
        ),
      ],
    ),
  );
}
