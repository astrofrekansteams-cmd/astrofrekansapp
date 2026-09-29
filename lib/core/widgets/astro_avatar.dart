import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'astro_image.dart';

/// Circular avatar with the signature gold ring. Falls back to initials, which
/// is what every freshly registered user gets.
class AstroAvatar extends StatelessWidget {
  const AstroAvatar({
    required this.size,
    super.key,
    this.assetPath,
    this.initials,
    this.ringWidth = 1.6,
    this.glow = true,
    this.semanticLabel,
  });

  final double size;
  final String? assetPath;
  final String? initials;
  final double ringWidth;
  final bool glow;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: semanticLabel,
      image: assetPath != null,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: AppColors.gold, width: ringWidth),
          color: AppColors.navy,
          boxShadow: glow
              ? <BoxShadow>[
                  BoxShadow(
                    color: AppColors.gold.withValues(alpha: 0.18),
                    blurRadius: size * 0.28,
                  ),
                ]
              : null,
        ),
        clipBehavior: Clip.antiAlias,
        child: assetPath != null
            ? AstroImage(
                assetPath!,
                width: size,
                height: size,
                fit: BoxFit.cover,
              )
            : Center(
                child: Text(
                  initials ?? '★',
                  style: AppTypography.titleLarge.copyWith(
                    fontSize: size * 0.36,
                    color: AppColors.goldBright,
                  ),
                ),
              ),
      ),
    );
  }
}
