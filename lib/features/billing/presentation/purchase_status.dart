import 'package:flutter/material.dart';

import '../../../core/localization/b12_copy.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/widgets.dart';
import '../application/entitlement_controller.dart';

/// One line about the purchase or restore in progress, or how it ended.
/// Shared by the plans screen and the AstroCoin wallet so both say the same
/// thing. Waiting states are bounded (the controller times out a silent
/// store), so the progress bar never runs forever.
class PurchaseStatusNotice extends StatelessWidget {
  const PurchaseStatusNotice({super.key, required this.state});
  final EntitlementSnapshot state;

  @override
  Widget build(BuildContext context) {
    final (String? key, bool working) = switch (state.purchase) {
      PurchasePhase.purchasing => ('purchase_in_progress', true),
      PurchasePhase.verifying => ('purchase_verifying', true),
      PurchasePhase.restoring => ('restore_in_progress', true),
      PurchasePhase.pending => ('purchase_pending', false),
      PurchasePhase.cancelled => ('purchase_cancelled', false),
      PurchasePhase.succeeded => ('purchase_succeeded', false),
      PurchasePhase.restored => (
        state.errorCode == 'restore_nothing'
            ? 'restore_nothing'
            : 'restore_done',
        false,
      ),
      PurchasePhase.failed || PurchasePhase.idle => (
        state.errorCode == null ? null : billingErrorKey(state.errorCode!),
        false,
      ),
    };
    if (key == null) return const SizedBox.shrink();
    return AstroCard(
      key: const ValueKey('purchase-status'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(b12(context, key), style: AppTypography.bodyMedium),
          if (working) ...[
            const SizedBox(height: AppSpacing.sm),
            const LinearProgressIndicator(minHeight: 2),
          ],
        ],
      ),
    );
  }
}

/// Copy key for a billing error code; unknown codes get the generic line.
String billingErrorKey(String code) => switch (code) {
  'product_unavailable' ||
  'store_unavailable' ||
  'store_no_answer' ||
  'verification_failed' ||
  'restore_failed' ||
  'entitlement_refresh_failed' ||
  'already_owned' => 'billing_error_$code',
  _ => 'billing_error_generic',
};
