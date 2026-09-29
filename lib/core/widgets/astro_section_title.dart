import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

/// Serif section heading with an optional trailing action ("Tümünü Gör →").
class AstroSectionTitle extends StatelessWidget {
  const AstroSectionTitle({
    required this.title,
    super.key,
    this.actionLabel,
    this.onAction,
    this.subtitle,
    this.leading,
  });

  final String title;
  final String? actionLabel;
  final VoidCallback? onAction;
  final String? subtitle;
  final Widget? leading;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: <Widget>[
        if (leading != null) ...<Widget>[
          leading!,
          const SizedBox(width: AppSpacing.sm),
        ],
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Text(
                title,
                style: AppTypography.titleLarge.copyWith(fontSize: 21),
              ),
              if (subtitle != null)
                Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.xxs),
                  child: Text(subtitle!, style: AppTypography.bodySmall),
                ),
            ],
          ),
        ),
        if (actionLabel != null && onAction != null)
          TextButton(
            onPressed: onAction,
            style: TextButton.styleFrom(
              foregroundColor: AppColors.ivoryMuted,
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.sm,
                vertical: AppSpacing.sm,
              ),
              minimumSize: const Size(0, AppSpacing.minTapTarget),
              tapTargetSize: MaterialTapTargetSize.padded,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Text(actionLabel!, style: AppTypography.labelMedium),
                const SizedBox(width: AppSpacing.xs),
                const Icon(
                  Icons.arrow_forward,
                  size: 15,
                  color: AppColors.ivoryMuted,
                ),
              ],
            ),
          ),
      ],
    );
  }
}
