import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

/// Tappable pill used for filters, quick prompts and influence chips.
///
/// Selected: champagne-gold fill with dark text. Unselected: a visible gold
/// hairline with ivory text. Never shorter than the 44 px touch minimum.
class AstroChip extends StatelessWidget {
  const AstroChip({
    required this.label,
    super.key,
    this.onTap,
    this.selected = false,
    this.leading,
    this.subtitle,
    this.semanticLabel,
    this.titleWidget,
  });

  final String label;
  final VoidCallback? onTap;
  final bool selected;
  final Widget? leading;
  final String? subtitle;
  final String? semanticLabel;

  /// Replaces the plain [label] when the title needs rich content, e.g. an
  /// aspect glyph or an arrow that the UI font does not carry.
  final Widget? titleWidget;

  @override
  Widget build(BuildContext context) {
    final Widget content = Padding(
      padding: EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: subtitle == null ? AppSpacing.sm : AppSpacing.xs + 2,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          if (leading != null) ...<Widget>[
            leading!,
            const SizedBox(width: AppSpacing.sm),
          ],
          Flexible(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                titleWidget ??
                    Text(
                      label,
                      overflow: TextOverflow.ellipsis,
                      style: AppTypography.labelLarge.copyWith(
                        fontSize: 14,
                        fontWeight: selected
                            ? FontWeight.w600
                            : FontWeight.w500,
                        color: selected ? AppColors.onGold : AppColors.ivory,
                      ),
                    ),
                if (subtitle != null)
                  Text(
                    subtitle!,
                    overflow: TextOverflow.ellipsis,
                    style: AppTypography.bodySmall.copyWith(
                      fontSize: AppTypography.minFontSize,
                      color: selected
                          ? AppColors.onGold.withValues(alpha: 0.75)
                          : AppColors.textSubtle,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );

    return Semantics(
      button: onTap != null,
      selected: selected,
      label: semanticLabel,
      child: Material(
        color: selected
            ? AppColors.gold
            : AppColors.surface.withValues(alpha: 0.72),
        borderRadius: AppRadius.chip,
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Container(
            constraints: const BoxConstraints(minHeight: AppSpacing.chipHeight),
            alignment: Alignment.center,
            decoration: BoxDecoration(
              borderRadius: AppRadius.chip,
              border: Border.all(
                color: selected
                    ? AppColors.goldBright
                    : AppColors.hairlineStrong,
              ),
            ),
            child: content,
          ),
        ),
      ),
    );
  }
}
