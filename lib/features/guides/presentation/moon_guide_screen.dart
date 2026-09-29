import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/astrology/domain/planet.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/localization/astro_labels.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../application/guides_providers.dart';
import '../domain/guide_models.dart';
import 'guide_widgets.dart';

/// Moon guide: sign, phase, aspects, the natal house it crosses, and what the
/// day suits - all computed by the server's ephemeris.
class MoonGuideScreen extends ConsumerWidget {
  const MoonGuideScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) => CorePage(
    title: 'moon_guide',
    children: [
      ApiStateView(
        value: ref.watch(moonGuideProvider),
        onRetry: () => ref.invalidate(moonGuideProvider),
        loading: const _MoonGuideSkeleton(),
        builder: (guide) => _MoonGuideBody(guide: guide),
      ),
    ],
  );
}

/// Same shape as the loaded page, so nothing jumps when data arrives.
class _MoonGuideSkeleton extends StatelessWidget {
  const _MoonGuideSkeleton();

  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    label: b12(context, 'loading'),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const AstroCard(
          child: Column(
            children: [
              AstroSkeleton.circle(size: 120),
              SizedBox(height: AppSpacing.lg),
              AstroSkeleton(width: 140, height: 26),
              SizedBox(height: AppSpacing.sm),
              AstroSkeleton(width: 110, height: 16),
              SizedBox(height: AppSpacing.lg),
              AstroSkeleton(),
              SizedBox(height: AppSpacing.sm),
              AstroSkeleton(width: 220),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.cardGap),
        Row(
          children: [
            for (var i = 0; i < 2; i++) ...[
              if (i > 0) const SizedBox(width: AppSpacing.md),
              const Expanded(child: AstroSkeletonCard(lines: 1)),
            ],
          ],
        ),
        const SizedBox(height: AppSpacing.cardGap),
        const AstroSkeletonCard(lines: 3),
      ],
    ),
  );
}

class _MoonGuideBody extends StatelessWidget {
  const _MoonGuideBody({required this.guide});
  final MoonGuide guide;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final nextPhase = guide.nextPhase;
    // The engine's "next phase" is the exact instant of the next named phase.
    // While the Moon is already in that phase, it is the exact moment of the
    // current one ("Tam Dolunay anı"), not a next phase.
    final phaseLabel = nextPhase == null
        ? null
        : nextPhase == guide.phase
        ? b12(
            context,
            'exact_phase_moment',
          ).replaceFirst('%s', l10n.moonPhase(nextPhase))
        : '${b12(context, 'next_phase')}: ${l10n.moonPhase(nextPhase)}';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Hero: phase, sign, one-line summary.
        AstroCard(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            children: [
              AstroImage(guide.phase.asset, width: 128, height: 128),
              const SizedBox(height: AppSpacing.lg),
              Text(
                l10n.moonPhase(guide.phase),
                textAlign: TextAlign.center,
                style: AppTypography.headlineLarge,
              ),
              const SizedBox(height: AppSpacing.xs),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  AstroImage(guide.sign.asset, width: 24, height: 24),
                  const SizedBox(width: AppSpacing.sm),
                  Flexible(
                    child: Text(
                      '${b12(context, 'moon')} ${l10n.sign(guide.sign)} '
                      '${guide.degree.toStringAsFixed(1)}°',
                      style: AppTypography.titleMedium.copyWith(
                        color: AppColors.goldBright,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.lg),
              Text(
                guide.summary,
                textAlign: TextAlign.center,
                style: AppTypography.bodyLarge.copyWith(
                  color: AppColors.ivoryMuted,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.cardGap),
        // Information grid.
        LayoutBuilder(
          builder: (context, constraints) {
            const gap = AppSpacing.md;
            final width = (constraints.maxWidth - gap) / 2;
            final tiles = <Widget>[
              _InfoTile(
                icon: Icons.brightness_2_outlined,
                label: b12(context, 'illumination'),
                value: '${(guide.illumination * 100).round()}%',
              ),
              if (guide.natalHouse != null)
                _InfoTile(
                  icon: Icons.home_outlined,
                  label: b12(context, 'moon_natal_house'),
                  value: '${guide.natalHouse}. ${b12(context, 'house')}',
                ),
              if (phaseLabel != null)
                _InfoTile(
                  icon: Icons.schedule,
                  label: phaseLabel,
                  value: formatLocalMoment(context, guide.nextPhaseAt),
                ),
              _InfoTile(
                icon: Icons.east,
                label:
                    '${b12(context, 'moon_enters')} ${l10n.sign(guide.nextSign)}',
                value: formatLocalMoment(context, guide.nextSignAt),
              ),
            ];
            return Wrap(
              spacing: gap,
              runSpacing: gap,
              children: [
                for (final tile in tiles) SizedBox(width: width, child: tile),
              ],
            );
          },
        ),
        const SizedBox(height: AppSpacing.sectionGap),
        GuideSection(
          title: b12(context, 'good_for_today'),
          icon: Icons.wb_twilight,
          accent: AppColors.success,
          children: [
            for (final line in guide.goodFor)
              BulletLine(line, color: AppColors.success),
          ],
        ),
        const SizedBox(height: AppSpacing.cardGap),
        GuideSection(
          title: b12(context, 'careful_today'),
          icon: Icons.visibility_outlined,
          accent: AppColors.warning,
          children: [
            for (final line in guide.carefulWith)
              BulletLine(line, color: AppColors.warning),
            if (guide.carefulWith.isEmpty)
              Text(
                b12(context, 'nothing_notable'),
                style: AppTypography.bodyMedium,
              ),
          ],
        ),
        const SizedBox(height: AppSpacing.sectionGap),
        GuideSection(
          title: b12(context, 'moon_aspects_sky'),
          icon: Icons.nightlight_round,
          children: [
            for (final a in guide.skyAspects)
              AspectLine(
                first: Planet.moon,
                aspect: a.aspect,
                second: a.body,
                orb: a.orb,
                applying: a.applying,
              ),
            if (guide.skyAspects.isEmpty)
              Text(
                b12(context, 'nothing_notable'),
                style: AppTypography.bodyMedium,
              ),
          ],
        ),
        const SizedBox(height: AppSpacing.cardGap),
        GuideSection(
          title: b12(context, 'moon_aspects_natal'),
          icon: Icons.person_pin_circle_outlined,
          children: [
            for (final a in guide.natalAspects)
              AspectLine(
                first: Planet.moon,
                aspect: a.aspect,
                second: a.body,
                orb: a.orb,
              ),
            if (guide.natalAspects.isEmpty)
              Text(
                b12(context, 'nothing_notable'),
                style: AppTypography.bodyMedium,
              ),
          ],
        ),
      ],
    );
  }
}

class _InfoTile extends StatelessWidget {
  const _InfoTile({
    required this.icon,
    required this.label,
    required this.value,
  });
  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => AstroCard(
    padding: const EdgeInsets.all(AppSpacing.md),
    borderRadius: AppRadius.card,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 18, color: AppColors.gold),
        const SizedBox(height: AppSpacing.sm),
        Text(label, style: AppTypography.bodySmall),
        const SizedBox(height: AppSpacing.xxs),
        Text(value, style: AppTypography.titleMedium),
      ],
    ),
  );
}
