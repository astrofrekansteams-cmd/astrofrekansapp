import 'package:flutter/material.dart';

import '../../../../core/astrology/domain/aspect.dart';
import '../../../../core/astrology/domain/transit.dart';
import '../../../../core/localization/b12_copy.dart';
import '../../../../core/extensions/context_extensions.dart';
import '../../../../core/localization/astro_labels.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/utils/text_case.dart';
import '../../../../core/widgets/widgets.dart';

/// One "Bugün seni etkileyen" card.
class TransitCard extends StatelessWidget {
  const TransitCard({required this.summary, super.key, this.onTap});

  final TransitSummary summary;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final (String natureKey, Color natureColor) = _nature(summary);
    return AstroCard(
      onTap: onTap,
      padding: const EdgeInsets.all(AppSpacing.cardPadding),
      semanticLabel:
          '${context.l10n.transitTitle(summary)}, ${b12(context, natureKey)}',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          _Glyphs(summary: summary),
          const SizedBox(height: AppSpacing.md),
          TransitTitle(
            summary: summary,
            style: AppTypography.titleLarge.copyWith(fontSize: 18),
          ),
          const SizedBox(height: AppSpacing.sm),
          // Aspect named in words next to the nature tag: at card size the
          // opposition glyph alone can read like an infinity sign.
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.xs,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: <Widget>[
              if (summary.aspect case final AspectType aspect)
                Text(
                  _sentence(context.l10n.aspect(aspect), context.languageCode),
                  style: AppTypography.labelLarge.copyWith(
                    color: AppColors.goldBright,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              AstroBadge(label: b12(context, natureKey), color: natureColor),
            ],
          ),
          if (summary.headline case final String headline
              when headline.isNotEmpty) ...<Widget>[
            const SizedBox(height: AppSpacing.sm),
            Text(
              headline,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: AppTypography.bodySmall.copyWith(
                color: AppColors.ivoryMuted,
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.md),
          Row(
            children: <Widget>[
              Flexible(
                child: Text(
                  context.l10n.commonMoreInfo.toUpperCaseFor(
                    context.languageCode,
                  ),
                  overflow: TextOverflow.ellipsis,
                  style: AppTypography.labelSmall.copyWith(
                    color: AppColors.gold,
                    letterSpacing: 1,
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.xs),
              const Icon(Icons.arrow_forward, size: 13, color: AppColors.gold),
            ],
          ),
        ],
      ),
    );
  }
}

/// Planet artwork plus the aspect glyph, sized small and decoded small.
class _Glyphs extends StatelessWidget {
  const _Glyphs({required this.summary});

  final TransitSummary summary;

  @override
  Widget build(BuildContext context) {
    const double planetSize = 46;
    return SizedBox(
      height: planetSize,
      child: Row(
        children: <Widget>[
          AstroImage(
            summary.transitingPlanet.asset,
            width: planetSize,
            height: planetSize,
          ),
          if (summary.aspect != null &&
              summary.natalPlanet != null) ...<Widget>[
            const SizedBox(width: AppSpacing.xs),
            AspectGlyph(type: summary.aspect!, size: 20, strokeWidth: 1.6),
            const SizedBox(width: AppSpacing.xs),
            AstroImage(
              summary.natalPlanet!.asset,
              width: planetSize * 0.78,
              height: planetSize * 0.78,
            ),
          ] else if (summary.isRetrograde) ...<Widget>[
            const SizedBox(width: AppSpacing.sm),
            Text(
              context.l10n.retrogradeShort,
              style: AppTypography.titleLarge.copyWith(
                color: AppColors.gold,
                fontSize: 20,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Short nature tag: the engine's contribution sign when present, otherwise
/// the aspect's own nature.
(String, Color) _nature(TransitSummary summary) {
  final String? raw = summary.rawNature;
  if (raw == 'supportive') return ('nature_supportive', AppColors.success);
  if (raw == 'challenging') return ('nature_challenging', AppColors.warning);
  return switch (summary.aspect?.nature) {
    AspectNature.harmonious => ('nature_supportive', AppColors.success),
    AspectNature.hard => ('nature_challenging', AppColors.warning),
    _ => ('nature_prominent', AppColors.gold),
  };
}

String _sentence(String text, String language) => text.isEmpty
    ? text
    : text.substring(0, 1).toUpperCaseFor(language) + text.substring(1);
