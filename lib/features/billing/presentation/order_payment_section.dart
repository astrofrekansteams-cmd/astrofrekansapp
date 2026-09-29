import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/localization/b12_copy.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../application/entitlement_controller.dart';
import '../data/billing_models.dart';
import '../data/billing_repository.dart';

/// Auto-disposed so a return visit never shows a payment state cached from an
/// earlier one.
final orderPaymentProvider = FutureProvider.autoDispose
    .family<OrderPayment, String>(
      (ref, id) => ref.watch(billingRepositoryProvider).orderPayment(id),
    );

bool paymentSettled(OrderPayment payment) =>
    payment.groups.isNotEmpty &&
    payment.groups.every(
      (group) => group.status == 'satisfied' || group.status == 'not_required',
    );

/// The backend owns each rail and each group's status. A client cannot mark an
/// order paid; this widget only starts the provider handoff or spends a verified
/// store credit through the backend endpoint.
///
/// Payment state is never refreshed alone: every refresh - the button, coming
/// back from the provider's page, a started payment - also calls [onRefresh],
/// so the screen around it re-reads the order, its appointment and its access
/// together. Otherwise a paid order could still say "awaiting payment".
class OrderPaymentSection extends ConsumerStatefulWidget {
  const OrderPaymentSection({super.key, required this.orderId, this.onRefresh});
  final String orderId;

  /// Re-read everything that depends on this payment (order, appointment,
  /// entitlements). Called with every payment refresh.
  final VoidCallback? onRefresh;

  @override
  ConsumerState<OrderPaymentSection> createState() =>
      _OrderPaymentSectionState();
}

class _OrderPaymentSectionState extends ConsumerState<OrderPaymentSection> {
  late final String _idempotencyKey = _randomKey();
  late final AppLifecycleListener _lifecycle;
  bool _busy = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    // Back from the provider's payment page: the webhook may have landed.
    _lifecycle = AppLifecycleListener(onResume: _refreshAll);
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    super.dispose();
  }

  void _refreshAll() {
    if (!mounted) return;
    ref.invalidate(orderPaymentProvider(widget.orderId));
    widget.onRefresh?.call();
  }

  static String _randomKey() {
    final random = Random.secure();
    return List<int>.generate(
      16,
      (_) => random.nextInt(256),
    ).map((byte) => byte.toRadixString(16).padLeft(2, '0')).join();
  }

  Future<void> _start(String method) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final result = await ref
          .read(billingRepositoryProvider)
          .payOrder(
            widget.orderId,
            method: method,
            idempotencyKey: _idempotencyKey,
          );
      if (method == 'external') {
        final uri = Uri.tryParse(result.clientHandoff ?? '');
        if (uri == null || uri.scheme != 'https' || uri.host.isEmpty) {
          throw StateError('No secure provider handoff');
        }
        if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
          throw StateError('Provider handoff unavailable');
        }
        _message = 'pay_redirected';
      } else {
        _message = 'pay_credit_checked';
      }
      _refreshAll();
      await ref.read(entitlementControllerProvider).refresh();
    } on Object {
      _message = method == 'external'
          ? 'pay_external_failed'
          : 'pay_credit_failed';
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<AsyncValue<OrderPayment>>(orderPaymentProvider(widget.orderId), (
      previous,
      next,
    ) {
      // `value` keeps the previous data while a refresh is loading, so a
      // reload of an already-settled payment is not mistaken for a new one.
      bool settled(AsyncValue<OrderPayment>? value) {
        final data = value?.value;
        return data != null && paymentSettled(data);
      }

      if (!next.isLoading && settled(next) && !settled(previous)) {
        // Paid while this screen was open: the order, its appointment and any
        // store access change with it.
        widget.onRefresh?.call();
        ref.read(entitlementControllerProvider).refresh();
      }
    });
    final payment = ref.watch(orderPaymentProvider(widget.orderId));
    final entitlements = ref.watch(entitlementControllerProvider);
    return ApiStateView(
      value: payment,
      onRetry: _refreshAll,
      builder: (order) => ListenableBuilder(
        listenable: entitlements,
        builder: (context, _) => AstroCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(b12(context, 'pay_groups')),
              for (final group in order.groups) ...[
                const Divider(),
                Text(_groupLabel(context, group)),
                Text(_statusLabel(context, group.status)),
                if (group.reviewRequired)
                  Text(b12(context, 'pay_review_blocked')),
                if (group.classification == 'live_person_to_person' &&
                    group.status == 'required')
                  FilledButton(
                    onPressed:
                        !_busy &&
                            order.payableExternally &&
                            !order.blockedByReview
                        ? () => _start('external')
                        : null,
                    child: Text(b12(context, 'pay_expert_start')),
                  ),
                if (group.classification == 'digital_store' &&
                    group.status == 'required')
                  _digitalActions(order, entitlements),
              ],
              if (_busy) const AstroLoading(size: 44),
              if (_message != null) Text(b12(context, _message!)),
              TextButton(
                onPressed: _refreshAll,
                child: Text(b12(context, 'pay_refresh')),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _digitalActions(OrderPayment order, EntitlementController controller) {
    final productCodes = order.lines
        .where((line) => line.classification == 'digital_store')
        .map((line) => line.storeProductCode)
        .whereType<String>()
        .toSet();
    final products = controller.catalog.where(
      (product) => productCodes.contains(product.code),
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final product in products)
          if (controller.localizedProducts[product.storeId]
              case final StoreProduct localized)
            OutlinedButton(
              onPressed: _busy ? null : () => controller.buy(product),
              child: Text('${localized.title} — ${localized.localizedPrice}'),
            ),
        if (products.isEmpty || !controller.storeAvailable)
          Text(b12(context, 'pay_digital_unavailable')),
        if (products.any(
          (product) =>
              controller.state.summary?.hasCredit(product.entitlementCode) ==
              true,
        ))
          FilledButton(
            onPressed: _busy ? null : () => _start('store_credit'),
            child: Text(b12(context, 'pay_apply_credit')),
          ),
      ],
    );
  }
}

String _groupLabel(BuildContext context, PaymentGroup group) =>
    b12(context, switch (group.classification) {
      'digital_store' => 'pay_group_digital',
      'live_person_to_person' => 'pay_group_live',
      'review_required' => 'pay_group_review',
      'free' => 'pay_group_free',
      _ => 'pay_group_unknown',
    });

String _statusLabel(BuildContext context, String status) =>
    b12(context, switch (status) {
      'required' => 'pay_status_required',
      'satisfied' => 'pay_status_satisfied',
      'blocked_review' => 'pay_status_blocked',
      'not_required' => 'pay_status_not_required',
      'refunded' => 'pay_status_refunded',
      _ => 'pay_status_unknown',
    });
