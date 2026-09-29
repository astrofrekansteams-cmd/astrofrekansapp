import 'package:flutter/material.dart';

import '../../../../core/assets/app_assets.dart';
import '../../../../core/extensions/context_extensions.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/widgets.dart';
import '../../../../l10n/generated/app_localizations.dart';

/// The Astro AI hero panel: guide artwork, promise lines and the three
/// capability marks from the reference screen.
class AstroAiHero extends StatelessWidget {
  const AstroAiHero({super.key});

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;

    return AstroCard(
      borderColor: AppColors.hairlineStrong,
      padding: EdgeInsets.zero,
      child: LayoutBuilder(
        builder: (BuildContext context, BoxConstraints constraints) {
          final double artWidth = (constraints.maxWidth * 0.42).clamp(
            110.0,
            190.0,
          );
          return Stack(
            children: <Widget>[
              PositionedDirectional(
                end: -artWidth * 0.12,
                top: 0,
                bottom: 0,
                child: IgnorePointer(
                  child: AstroImage(
                    AppAssets.astroAiListening,
                    width: artWidth,
                    opacity: 0.9,
                    fit: BoxFit.contain,
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(AppSpacing.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    SizedBox(
                      width: constraints.maxWidth - artWidth * 0.72,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: <Widget>[
                          Text(
                            l10n.astroAiTitle,
                            style: AppTypography.displayMedium.copyWith(
                              color: AppColors.goldBright,
                              fontSize: 34,
                            ),
                          ),
                          const SizedBox(height: AppSpacing.sm),
                          Text(
                            l10n.astroAiHeroLine1,
                            style: AppTypography.labelSmall.copyWith(
                              fontSize: 12,
                              color: AppColors.ivoryMuted,
                            ),
                          ),
                          Text(
                            l10n.astroAiHeroLine2,
                            style: AppTypography.labelSmall.copyWith(
                              fontSize: 12,
                              color: AppColors.ivoryMuted,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    SizedBox(
                      width: constraints.maxWidth - artWidth * 0.92,
                      child: Wrap(
                        spacing: AppSpacing.md,
                        runSpacing: AppSpacing.md,
                        children: <Widget>[
                          _Capability(
                            icon: Icons.menu_book_outlined,
                            label: l10n.astroAiFeaturePersonal,
                          ),
                          _Capability(
                            icon: Icons.public,
                            label: l10n.astroAiFeatureTransits,
                          ),
                          _Capability(
                            icon: Icons.auto_awesome,
                            label: l10n.astroAiFeatureAwareness,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.lg,
                        vertical: AppSpacing.md,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.night.withValues(alpha: 0.55),
                        borderRadius: AppRadius.brMd,
                        border: Border.all(color: AppColors.hairline),
                      ),
                      child: Text(
                        l10n.astroAiHeroNote,
                        textAlign: TextAlign.center,
                        style: AppTypography.bodySmall.copyWith(
                          color: AppColors.ivoryMuted,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _Capability extends StatelessWidget {
  const _Capability({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: 72,
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: AppColors.hairlineStrong),
          ),
          child: Icon(icon, size: 18, color: AppColors.gold),
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          label,
          textAlign: TextAlign.center,
          style: AppTypography.labelSmall.copyWith(
            fontSize: 12,
            letterSpacing: 0.9,
            color: AppColors.ivoryMuted,
          ),
        ),
      ],
    ),
  );
}
