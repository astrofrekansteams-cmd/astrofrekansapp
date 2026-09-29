import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/routing/app_routes.dart';
import '../../../core/storage/secure_storage.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/widgets/widgets.dart';
import '../../astro_ai/data/api_astro_ai_repository.dart';
import '../../../core/localization/b12_copy.dart';
import '../application/coin_spend.dart';
import '../application/entitlement_controller.dart';
import '../application/paid_report_service.dart';
import '../data/billing_models.dart';
import '../data/billing_repository.dart';
import '../data/coin_repository.dart';
import '../../auth/application/session_controller.dart';

class PaidReportsSection extends ConsumerStatefulWidget {
  const PaidReportsSection({super.key, required this.reports});
  final ApiAstroAIRepository reports;
  @override
  ConsumerState<PaidReportsSection> createState() => _PaidReportsSectionState();
}

class _PaidReportsSectionState extends ConsumerState<PaidReportsSection> {
  bool _busy = false;
  String? _message;

  Future<void> _create(CatalogProduct product, {bool coins = false}) async {
    if (_busy) return;
    if (coins &&
        !await confirmCoinSpend(context, ref, CoinItem.specialAnalysis)) {
      return;
    }
    if (!mounted) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final ownerId = ref.read(currentUserProvider)?.id;
      if (ownerId == null) throw StateError('Authenticated user required');
      final service = PaidReportService(
        ref.read(billingRepositoryProvider),
        widget.reports,
        ref.read(secureStoreProvider),
        ownerId: ownerId,
        locale: widget.reports.locale,
      );
      final delivery = coins
          ? await service.createWithCoins(product)
          : await service.createWithCredit(product);
      if (coins) ref.invalidate(coinWalletProvider);
      await ref.read(entitlementControllerProvider).refresh();
      if (mounted) {
        final route = switch (delivery) {
          PaidReportReady(:final report) =>
            '${AppRoutes.aiReports}/${Uri.encodeComponent(report.id)}',
          PaidReportQueued(:final job) =>
            '${AppRoutes.aiReports}?job=${Uri.encodeQueryComponent(job.id)}',
        };
        unawaited(context.push(route));
      }
    } on Object catch (error) {
      if (mounted) {
        setState(
          () => _message = b12(context, switch (error) {
            ApiException(code: 'insufficient_coins') => 'report_err_coins',
            ApiException(code: 'report_payment_required') =>
              'report_err_payment',
            ApiException(code: 'report_credit_conflict') =>
              'report_err_conflict',
            ApiException(code: 'report_credit_unavailable') =>
              'report_err_unavailable',
            _ => 'report_err_generic',
          }),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = ref.watch(entitlementControllerProvider);
    final coinPrice = ref
        .watch(coinCatalogProvider)
        .asData
        ?.value
        ?.priceOf(CoinItem.specialAnalysis);
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        // Not sold in the stores: offered with AstroCoin (or a credit
        // bought earlier), independent of the store catalogue.
        final bool coinsOffered = coinPrice != null && coinPrice > 0;
        final products = oneOffReports.where(
          (product) =>
              (coinsOffered && product.code != 'synastry_report') ||
              controller.state.summary?.hasCredit(product.entitlementCode) ==
                  true,
        );
        if (products.isEmpty) return const SizedBox.shrink();
        return AstroCard(
          key: const ValueKey('special-reports'),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(b12(context, 'reports_special_title')),
              for (final product in products) ...[
                const Divider(),
                Text(
                  b12(context, switch (product.code) {
                    'natal_report' => 'report_natal',
                    'synastry_report' => 'report_synastry',
                    _ => 'report_annual',
                  }),
                ),
                if (controller.state.summary?.hasCredit(
                      product.entitlementCode,
                    ) ==
                    true)
                  product.code == 'synastry_report'
                      ? Text(b12(context, 'report_synastry_pending'))
                      : FilledButton(
                          onPressed: _busy ? null : () => _create(product),
                          child: Text(
                            b12(context, 'report_create_with_credit'),
                          ),
                        ),
                if (product.code != 'synastry_report' &&
                    coinPrice != null &&
                    coinPrice > 0)
                  OutlinedButton.icon(
                    key: ValueKey('report-coins-${product.code}'),
                    onPressed: _busy
                        ? null
                        : () => _create(product, coins: true),
                    icon: const Icon(Icons.toll_outlined, size: 18),
                    label: Text(
                      b12(
                        context,
                        'pay_with_coins_report',
                      ).replaceAll('{price}', '$coinPrice'),
                    ),
                  ),
              ],
              if (_busy) const AstroLoading(size: 44),
              if (_message != null) Text(_message!),
            ],
          ),
        );
      },
    );
  }
}
