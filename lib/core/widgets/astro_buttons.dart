import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

/// Primary call to action: the pale ivory pill from the reference screens.
class AstroButton extends StatelessWidget {
  const AstroButton({
    required this.label,
    required this.onPressed,
    super.key,
    this.icon,
    this.trailingArrow = false,
    this.isLoading = false,
    this.expand = true,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool trailingArrow;
  final bool isLoading;
  final bool expand;

  @override
  Widget build(BuildContext context) {
    final bool enabled = onPressed != null && !isLoading;

    final Widget content = Row(
      mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: trailingArrow
          ? MainAxisAlignment.spaceBetween
          : MainAxisAlignment.center,
      children: <Widget>[
        if (trailingArrow) const SizedBox(width: AppSpacing.xxl),
        Flexible(
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              if (icon != null) ...<Widget>[
                Icon(icon, size: 18, color: AppColors.ctaLabel),
                const SizedBox(width: AppSpacing.sm),
              ],
              Flexible(
                child: Text(
                  label,
                  textAlign: TextAlign.center,
                  overflow: TextOverflow.ellipsis,
                  style: AppTypography.labelLarge.copyWith(
                    color: AppColors.ctaLabel,
                    fontSize: 16,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
        ),
        if (trailingArrow)
          const Icon(Icons.arrow_forward, size: 20, color: AppColors.ctaLabel),
      ],
    );

    // One button node with an explicit enabled state, also while disabled
    // (a disabled InkWell alone exposes no button semantics at all).
    return Semantics(
      container: true,
      button: true,
      enabled: enabled,
      child: _buildSurface(enabled, content),
    );
  }

  Widget _buildSurface(bool enabled, Widget content) {
    return Opacity(
      opacity: enabled ? 1 : 0.5,
      child: Material(
        color: AppColors.ctaSurface,
        borderRadius: AppRadius.brPill,
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: enabled ? onPressed : null,
          child: Container(
            constraints: const BoxConstraints(
              minHeight: AppSpacing.minTapTarget + 8,
            ),
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.xxl,
              vertical: AppSpacing.md,
            ),
            alignment: Alignment.center,
            child: isLoading
                ? const SizedBox(
                    height: 22,
                    width: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: AppColors.ctaLabel,
                    ),
                  )
                : content,
          ),
        ),
      ),
    );
  }
}

/// Secondary action: gold hairline outline on the dark ground.
class AstroOutlineButton extends StatelessWidget {
  const AstroOutlineButton({
    required this.label,
    required this.onPressed,
    super.key,
    this.icon,
    this.trailingArrow = false,
    this.expand = true,
    this.isLoading = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool trailingArrow;
  final bool expand;
  final bool isLoading;

  @override
  Widget build(BuildContext context) {
    final bool enabled = onPressed != null && !isLoading;
    return Semantics(
      container: true,
      button: true,
      enabled: enabled,
      child: _buildSurface(enabled),
    );
  }

  Widget _buildSurface(bool enabled) {
    return Opacity(
      opacity: enabled ? 1 : 0.45,
      child: Material(
        color: AppColors.surface.withValues(alpha: 0.45),
        borderRadius: AppRadius.brPill,
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: enabled ? onPressed : null,
          child: Container(
            constraints: const BoxConstraints(
              minHeight: AppSpacing.minTapTarget + 8,
            ),
            decoration: BoxDecoration(
              borderRadius: AppRadius.brPill,
              border: Border.all(color: AppColors.hairlineStrong),
            ),
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.xxl,
              vertical: AppSpacing.md,
            ),
            child: Row(
              mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min,
              mainAxisAlignment: trailingArrow
                  ? MainAxisAlignment.spaceBetween
                  : MainAxisAlignment.center,
              children: <Widget>[
                if (trailingArrow) const SizedBox(width: AppSpacing.xxl),
                Flexible(
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      if (icon != null) ...<Widget>[
                        Icon(icon, size: 18, color: AppColors.ivory),
                        const SizedBox(width: AppSpacing.sm),
                      ],
                      Flexible(
                        child: Text(
                          label,
                          overflow: TextOverflow.ellipsis,
                          textAlign: TextAlign.center,
                          style: AppTypography.labelLarge.copyWith(
                            fontSize: 15.5,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                if (trailingArrow)
                  const Icon(
                    Icons.arrow_forward,
                    size: 20,
                    color: AppColors.ivory,
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Circular icon button with a gold hairline ring and a 48dp tap target.
class AstroIconButton extends StatelessWidget {
  const AstroIconButton({
    required this.icon,
    required this.onPressed,
    required this.semanticLabel,
    super.key,
    this.size = 44,
    this.iconSize = 20,
    this.filled = false,
    this.badge = false,
    this.badgeCount,
  });

  final IconData icon;
  final VoidCallback? onPressed;
  final String semanticLabel;
  final double size;
  final double iconSize;
  final bool filled;
  final bool badge;

  /// A number on the icon (unread count). Shown when above zero; "9+" past 9.
  final int? badgeCount;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: semanticLabel,
      child: Tooltip(
        message: semanticLabel,
        child: SizedBox(
          width: AppSpacing.minTapTarget.clamp(size, double.infinity),
          height: AppSpacing.minTapTarget.clamp(size, double.infinity),
          child: Center(
            child: Material(
              color: filled
                  ? AppColors.gold
                  : AppColors.surface.withValues(alpha: 0.55),
              shape: CircleBorder(
                side: BorderSide(
                  color: filled ? Colors.transparent : AppColors.hairlineStrong,
                ),
              ),
              clipBehavior: Clip.antiAlias,
              child: InkWell(
                onTap: onPressed,
                child: SizedBox(
                  width: size,
                  height: size,
                  child: Stack(
                    alignment: Alignment.center,
                    children: <Widget>[
                      Icon(
                        icon,
                        size: iconSize,
                        color: filled ? AppColors.onGold : AppColors.ivory,
                      ),
                      if ((badgeCount ?? 0) > 0)
                        Positioned(
                          top: 2,
                          right: 0,
                          child: Container(
                            constraints: const BoxConstraints(minWidth: 16),
                            padding: const EdgeInsets.symmetric(
                              horizontal: 4,
                              vertical: 1,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.goldBright,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              badgeCount! > 9 ? '9+' : '$badgeCount',
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                color: AppColors.onGold,
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        )
                      else if (badge)
                        Positioned(
                          top: size * 0.22,
                          right: size * 0.22,
                          child: Container(
                            width: 7,
                            height: 7,
                            decoration: const BoxDecoration(
                              color: AppColors.goldBright,
                              shape: BoxShape.circle,
                            ),
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
