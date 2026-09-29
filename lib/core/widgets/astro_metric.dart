import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

/// One scored row: icon, label, progress bar, value.
///
/// Layout is intentionally flexible: on narrow phones the bar shrinks instead
/// of overflowing, and at large text scales the row grows in height.
class AstroMetric extends StatelessWidget {
  const AstroMetric({
    required this.label,
    required this.value,
    required this.color,
    super.key,
    this.leading,
    this.maxValue = 100,
    this.compact = false,
  });

  final String label;
  final int value;
  final Color color;
  final Widget? leading;
  final int maxValue;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final double fraction = (value / maxValue).clamp(0, 1).toDouble();
    final TextScaler scaler = MediaQuery.textScalerOf(context);
    final bool stack = scaler.scale(14) > 19;

    final Widget bar = ClipRRect(
      borderRadius: AppRadius.brPill,
      child: SizedBox(
        height: 5,
        child: Stack(
          children: <Widget>[
            const ColoredBox(
              color: AppColors.surfaceMuted,
              child: SizedBox.expand(),
            ),
            // heightFactor is required: inside a Stack the fill would get
            // loose constraints and collapse to zero height.
            FractionallySizedBox(
              widthFactor: fraction,
              heightFactor: 1,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  borderRadius: AppRadius.brPill,
                  gradient: LinearGradient(
                    colors: <Color>[color.withValues(alpha: 0.75), color],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );

    final Widget labelText = Text(
      label,
      overflow: TextOverflow.ellipsis,
      style: AppTypography.bodyMedium.copyWith(
        color: AppColors.ivory,
        fontSize: compact ? 13 : 14,
      ),
    );

    final Widget valueText = Text(
      '$value',
      style: AppTypography.titleMedium.copyWith(
        color: AppColors.ivory,
        fontFeatures: const <FontFeature>[FontFeature.tabularFigures()],
      ),
    );

    return Semantics(
      label: '$label $value / $maxValue',
      excludeSemantics: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm - 2),
        child: stack
            ? Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      if (leading != null) ...<Widget>[
                        leading!,
                        const SizedBox(width: AppSpacing.sm),
                      ],
                      Expanded(child: labelText),
                      valueText,
                    ],
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  bar,
                ],
              )
            : Row(
                children: <Widget>[
                  if (leading != null) ...<Widget>[
                    leading!,
                    const SizedBox(width: AppSpacing.sm),
                  ],
                  Flexible(flex: 5, child: labelText),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(flex: 6, child: bar),
                  const SizedBox(width: AppSpacing.sm),
                  valueText,
                ],
              ),
      ),
    );
  }
}
