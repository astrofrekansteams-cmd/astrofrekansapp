import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

/// Small gold tag: PREMIUM, status, keyword. Radius 12 (badge token).
class AstroBadge extends StatelessWidget {
  const AstroBadge({
    required this.label,
    super.key,
    this.icon,
    this.filled = false,
    this.color = AppColors.gold,
  });

  final String label;
  final IconData? icon;
  final bool filled;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm + 2,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: filled ? color : color.withValues(alpha: 0.12),
        borderRadius: AppRadius.badge,
        border: Border.all(color: color.withValues(alpha: filled ? 1 : 0.55)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          if (icon != null) ...<Widget>[
            Icon(icon, size: 13, color: filled ? AppColors.onGold : color),
            const SizedBox(width: AppSpacing.xs + 2),
          ],
          Flexible(
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTypography.labelSmall.copyWith(
                color: filled ? AppColors.onGold : color,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
