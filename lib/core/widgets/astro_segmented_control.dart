import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

/// One option of an [AstroSegmentedControl].
class AstroSegment<T> {
  const AstroSegment({required this.value, required this.label, this.icon});
  final T value;
  final String label;
  final IconData? icon;
}

/// Equal-width pill segments: champagne fill + dark text when selected,
/// ivory text on navy otherwise. Labels scale down rather than overflow on
/// narrow phones; every segment keeps the 44 px touch height.
class AstroSegmentedControl<T> extends StatelessWidget {
  const AstroSegmentedControl({
    super.key,
    required this.segments,
    required this.selected,
    required this.onChanged,
  });

  final List<AstroSegment<T>> segments;

  /// Null when no segment applies (e.g. a custom date is picked).
  final T? selected;
  final ValueChanged<T> onChanged;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(AppSpacing.xs),
    decoration: BoxDecoration(
      color: AppColors.surface.withValues(alpha: 0.72),
      borderRadius: AppRadius.chip,
      border: Border.all(color: AppColors.hairlineStrong),
    ),
    child: Row(
      children: [
        for (final segment in segments)
          Expanded(
            child: _SegmentButton(
              segment: segment,
              selected: segment.value == selected,
              onTap: () => onChanged(segment.value),
            ),
          ),
      ],
    ),
  );
}

class _SegmentButton<T> extends StatelessWidget {
  const _SegmentButton({
    required this.segment,
    required this.selected,
    required this.onTap,
  });
  final AstroSegment<T> segment;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected ? AppColors.onGold : AppColors.ivory;
    return Semantics(
      button: true,
      selected: selected,
      label: segment.label,
      excludeSemantics: true,
      child: Material(
        color: selected ? AppColors.gold : Colors.transparent,
        borderRadius: AppRadius.chip,
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: AppSpacing.chipHeight),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
              child: Center(
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (segment.icon != null) ...[
                        Icon(segment.icon, size: 16, color: color),
                        const SizedBox(width: AppSpacing.xs + 2),
                      ],
                      Text(
                        segment.label,
                        maxLines: 1,
                        style: AppTypography.labelLarge.copyWith(
                          fontSize: 14,
                          fontWeight: selected
                              ? FontWeight.w600
                              : FontWeight.w500,
                          color: color,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
