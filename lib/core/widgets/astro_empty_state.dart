import 'package:flutter/material.dart';

import '../assets/app_assets.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';
import 'astro_buttons.dart';
import 'astro_image.dart';

/// Which of the production empty-state illustrations to show.
enum AstroEmptyStateKind {
  noData('no_data'),
  noBirthData('no_birth_data'),
  noResults('no_results'),
  offline('offline'),
  premiumLocked('premium_locked'),
  loading('loading');

  const AstroEmptyStateKind(this.assetKey);

  final String assetKey;

  String get asset => AppAssets.emptyStates[assetKey]!;
}

class AstroEmptyState extends StatelessWidget {
  const AstroEmptyState({
    required this.kind,
    required this.title,
    super.key,
    this.message,
    this.actionLabel,
    this.onAction,
    this.illustrationSize = 120,
  });

  final AstroEmptyStateKind kind;
  final String title;
  final String? message;
  final String? actionLabel;
  final VoidCallback? onAction;
  final double illustrationSize;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 360),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xxl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              AstroImage(
                kind.asset,
                width: illustrationSize,
                height: illustrationSize,
              ),
              const SizedBox(height: AppSpacing.xl),
              Text(
                title,
                textAlign: TextAlign.center,
                style: AppTypography.headlineMedium.copyWith(fontSize: 22),
              ),
              if (message != null) ...<Widget>[
                const SizedBox(height: AppSpacing.sm),
                Text(
                  message!,
                  textAlign: TextAlign.center,
                  style: AppTypography.bodyMedium.copyWith(
                    color: AppColors.ivoryMuted,
                  ),
                ),
              ],
              if (actionLabel != null && onAction != null) ...<Widget>[
                const SizedBox(height: AppSpacing.xl),
                AstroOutlineButton(
                  label: actionLabel!,
                  onPressed: onAction,
                  expand: false,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
