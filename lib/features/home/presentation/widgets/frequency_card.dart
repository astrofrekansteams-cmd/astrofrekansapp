import 'package:flutter/material.dart';

import '../../../../core/assets/app_assets.dart';
import '../../../../core/astrology/domain/daily_frequency.dart';
import '../../../../core/extensions/context_extensions.dart';
import '../../../../core/localization/astro_labels.dart';
import '../../../../core/localization/b12_copy.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/utils/text_case.dart';
import '../../../../core/widgets/widgets.dart';
import '../../../../l10n/generated/app_localizations.dart';
import 'frequency_ring.dart';

/// "Bugünün Frekansı" - the hero card of the Home screen.
class FrequencyCard extends StatelessWidget {
  const FrequencyCard({required this.frequency, super.key, this.onDetails});

  final DailyFrequency frequency;
  final VoidCallback? onDetails;

  static const List<FrequencyCategory> _primary = <FrequencyCategory>[
    FrequencyCategory.love,
    FrequencyCategory.career,
    FrequencyCategory.money,
    FrequencyCategory.mood,
  ];

  Color _colorFor(FrequencyCategory category) => switch (category) {
    FrequencyCategory.love => AppColors.love,
    FrequencyCategory.career => AppColors.career,
    FrequencyCategory.money => AppColors.money,
    FrequencyCategory.mood => AppColors.mood,
    FrequencyCategory.generalEnergy => AppColors.energy,
    FrequencyCategory.health => AppColors.health,
    FrequencyCategory.luck => AppColors.luck,
  };

  String _levelLabel(AppLocalizations l10n) => switch (frequency.level) {
    FrequencyLevel.high => l10n.homeFrequencyHigh,
    FrequencyLevel.balanced => l10n.homeFrequencyBalanced,
    FrequencyLevel.calm => l10n.homeFrequencyCalm,
  };

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;

    final List<Widget> metrics = <Widget>[
      for (final FrequencyCategory category in _primary)
        if (frequency.metric(category) case final FrequencyMetric metric)
          AstroMetric(
            label: l10n.frequencyCategory(category),
            value: metric.score,
            color: _colorFor(category),
            leading: AstroImage(category.asset, width: 22, height: 22),
          ),
    ];

    final Widget ring = FrequencyRing(
      score: frequency.overallScore,
      caption: _levelLabel(l10n),
    );

    return AstroCard(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        AppSpacing.lg,
        AppSpacing.lg,
        AppSpacing.xl,
      ),
      child: Stack(
        children: <Widget>[
          // Restrained decorative planet in the corner, like the reference.
          Positioned(
            top: -34,
            right: -42,
            child: IgnorePointer(
              child: AstroImage(
                AppAssets.planets['moon']!,
                width: 180,
                height: 180,
                opacity: 0.32,
              ),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              // Motto lives in the page footer; the card keeps one title.
              Text(
                l10n.homeFrequencyTitle,
                style: AppTypography.displayMedium.copyWith(fontSize: 30),
              ),
              const SizedBox(height: AppSpacing.md),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  key: const ValueKey('frequency-score-help'),
                  icon: const Icon(Icons.info_outline, size: 18),
                  label: Text(b12(context, 'home_score_help')),
                  onPressed: () => showDialog<void>(
                    context: context,
                    builder: (dialogContext) => AlertDialog(
                      title: Text(b12(context, 'home_score_help')),
                      content: SingleChildScrollView(
                        child: Text(b12(context, 'home_score_explanation')),
                      ),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(dialogContext),
                          child: const Text('OK'),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              LayoutBuilder(
                builder: (BuildContext context, BoxConstraints constraints) {
                  final bool sideBySide = constraints.maxWidth >= 300;
                  if (!sideBySide) {
                    return Column(
                      children: <Widget>[
                        ring,
                        const SizedBox(height: AppSpacing.lg),
                        ...metrics,
                      ],
                    );
                  }
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: <Widget>[
                      SizedBox(width: constraints.maxWidth * 0.36, child: ring),
                      const SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: metrics,
                        ),
                      ),
                    ],
                  );
                },
              ),
              if (frequency.message?.body case final String message
                  when message.isNotEmpty) ...<Widget>[
                const SizedBox(height: AppSpacing.md),
                Text(message, style: AppTypography.bodyMedium),
              ],
              if (onDetails != null) ...<Widget>[
                const SizedBox(height: AppSpacing.lg),
                Row(
                  children: <Widget>[
                    Expanded(
                      child: Text(
                        l10n.homeFrequencyEveryDay,
                        style: AppTypography.titleLarge.copyWith(
                          fontSize: 17,
                          color: AppColors.ivoryMuted,
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                    ),
                    AstroIconButton(
                      icon: Icons.arrow_forward,
                      semanticLabel: l10n.commonSeeAll.toUpperCaseFor(
                        context.languageCode,
                      ),
                      onPressed: onDetails,
                    ),
                  ],
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}
