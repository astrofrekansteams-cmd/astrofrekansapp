import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_shadows.dart';
import '../theme/app_spacing.dart';
import 'astro_motion.dart';

/// The standard content surface: deep navy fill, gold hairline, soft shadow.
class AstroCard extends StatelessWidget {
  const AstroCard({
    required this.child,
    super.key,
    this.padding = const EdgeInsets.all(AppSpacing.lg),
    this.borderRadius = AppRadius.brLg,
    this.onTap,
    this.borderColor = AppColors.hairline,
    this.gradient = AppColors.cardGradient,
    this.showShadow = true,
    this.semanticLabel,
    this.clipBehavior = Clip.antiAlias,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final BorderRadius borderRadius;
  final VoidCallback? onTap;
  final Color borderColor;
  final Gradient gradient;
  final bool showShadow;
  final String? semanticLabel;
  final Clip clipBehavior;

  @override
  Widget build(BuildContext context) {
    Widget content = DecoratedBox(
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: borderRadius,
        border: Border.all(color: borderColor),
        boxShadow: showShadow ? AppShadows.card : null,
      ),
      child: ClipRRect(
        clipBehavior: clipBehavior,
        borderRadius: borderRadius,
        child: Padding(padding: padding, child: child),
      ),
    );

    if (onTap != null) {
      content = Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: borderRadius,
          splashColor: AppColors.hairline,
          highlightColor: AppColors.hairline,
          child: content,
        ),
      );
    }

    if (semanticLabel != null) {
      content = Semantics(
        label: semanticLabel,
        button: onTap != null,
        container: true,
        child: content,
      );
    }
    return onTap == null ? content : AstroPress(child: content);
  }
}

/// Lighter, translucent surface for overlays on top of artwork.
///
/// Deliberately does not use a heavy backdrop blur: on large cosmic artwork a
/// blur is expensive and reads as cheap glassmorphism.
class AstroGlassCard extends StatelessWidget {
  const AstroGlassCard({
    required this.child,
    super.key,
    this.padding = const EdgeInsets.all(AppSpacing.lg),
    this.borderRadius = AppRadius.brLg,
    this.onTap,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final BorderRadius borderRadius;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => AstroCard(
    padding: padding,
    borderRadius: borderRadius,
    onTap: onTap,
    borderColor: AppColors.hairlineStrong,
    gradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: <Color>[
        AppColors.surfaceElevated.withValues(alpha: 0.72),
        AppColors.navy.withValues(alpha: 0.58),
      ],
    ),
    showShadow: false,
    child: child,
  );
}
