import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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

/// Personal stone guide: the stone of the day or a personal stone, chosen by
/// the server from element balance, placements, transits, the Moon and the
/// intent. Short tags up front, every astrological reason one tap away.
/// Symbolic only; no health claims.
class StoneGuideScreen extends ConsumerStatefulWidget {
  const StoneGuideScreen({super.key});
  @override
  ConsumerState<StoneGuideScreen> createState() => _StoneGuideState();
}

class _StoneGuideState extends ConsumerState<StoneGuideScreen> {
  StoneMode mode = StoneMode.today;
  StoneIntent? intent;

  @override
  Widget build(BuildContext context) {
    final provider = stoneProvider((mode, intent));
    return CorePage(
      title: 'stone_guide',
      children: [
        AstroSegmentedControl<StoneMode>(
          selected: mode,
          segments: [
            AstroSegment(
              value: StoneMode.today,
              label: b12(context, 'stone_today'),
              icon: Icons.wb_sunny_outlined,
            ),
            AstroSegment(
              value: StoneMode.personal,
              label: b12(context, 'stone_personal'),
              icon: Icons.person_outline,
            ),
          ],
          onChanged: (value) => setState(() => mode = value),
        ),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              b12(context, 'stone_intent').toUpperCase(),
              style: AppTypography.overline.copyWith(color: AppColors.gold),
            ),
            const SizedBox(height: AppSpacing.sm),
            // One scrollable row instead of three wrapped lines.
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              clipBehavior: Clip.none,
              child: Row(
                children: [
                  for (final value in <StoneIntent?>[
                    null,
                    ...StoneIntent.values,
                  ])
                    Padding(
                      padding: const EdgeInsets.only(right: AppSpacing.sm),
                      child: AstroChip(
                        label: b12(
                          context,
                          value == null ? 'intent_any' : 'intent_${value.name}',
                        ),
                        selected: intent == value,
                        onTap: () => setState(() => intent = value),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
        ApiStateView(
          value: ref.watch(provider),
          onRetry: () => ref.invalidate(provider),
          loading: const Column(
            children: [
              AstroSkeletonCard(media: true, mediaSize: 96, lines: 3),
              SizedBox(height: AppSpacing.cardGap),
              AstroSkeletonCard(media: true, mediaSize: 48, lines: 1),
            ],
          ),
          builder: (result) => _Result(result: result),
        ),
      ],
    );
  }
}

class _Result extends StatelessWidget {
  const _Result({required this.result});
  final StoneRecommendation result;

  @override
  Widget build(BuildContext context) {
    if (result.suggestions.isEmpty) {
      return AstroEmptyState(
        kind: AstroEmptyStateKind.noResults,
        title: b12(context, 'empty'),
      );
    }
    final others = result.suggestions.skip(1).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _HeroStone(suggestion: result.suggestions.first),
        if (others.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.sectionGap),
          AstroSectionTitle(title: b12(context, 'stone_alternatives')),
          const SizedBox(height: AppSpacing.md),
          for (var i = 0; i < others.length; i++) ...[
            if (i > 0) const SizedBox(height: AppSpacing.cardGap),
            _CompactStone(suggestion: others[i]),
          ],
        ],
        const SizedBox(height: AppSpacing.sectionGap),
        _ElementBalance(result: result),
        const SizedBox(height: AppSpacing.lg),
        Text(
          result.disclaimer,
          textAlign: TextAlign.center,
          style: AppTypography.bodySmall,
        ),
      ],
    );
  }
}

/// Short semantic tag for a reason kind; the full sentence stays in the
/// expandable "why" section.
(String, IconData) _tag(StoneReason reason) => switch (reason.kind) {
  'intent' => ('reason_intent', Icons.favorite_border),
  'element' => ('reason_element', Icons.balance),
  'placement' => ('reason_placement', Icons.person_pin_circle_outlined),
  'planet' => ('reason_planet', Icons.public),
  'moon' => ('reason_moon', Icons.nightlight_round),
  'transit' => ('reason_transit', Icons.sync_alt),
  _ => ('reason_other', Icons.auto_awesome),
};

List<StoneReason> _topReasons(StoneSuggestion s, int count) {
  final seen = <String>{};
  final sorted = [...s.reasons]..sort((a, b) => b.weight.compareTo(a.weight));
  return [
    for (final r in sorted)
      if (seen.add(r.kind)) r,
  ].take(count).toList();
}

class _ReasonTags extends StatelessWidget {
  const _ReasonTags({required this.reasons});
  final List<StoneReason> reasons;
  @override
  Widget build(BuildContext context) => Wrap(
    alignment: WrapAlignment.center,
    spacing: AppSpacing.xs + 2,
    runSpacing: AppSpacing.xs + 2,
    children: [
      for (final r in reasons)
        // Short word on the tag; the full phrase for screen readers and the
        // full astrological sentence in "Neden önerildi?".
        Semantics(
          label: b12(context, _tag(r).$1),
          excludeSemantics: true,
          child: Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.sm + 2,
              vertical: AppSpacing.xs + 2,
            ),
            decoration: BoxDecoration(
              color: AppColors.gold.withValues(alpha: 0.10),
              borderRadius: AppRadius.badge,
              border: Border.all(color: AppColors.hairlineStrong),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(_tag(r).$2, size: 14, color: AppColors.gold),
                const SizedBox(width: AppSpacing.xs),
                Flexible(
                  child: Text(
                    b12(context, '${_tag(r).$1}_short'),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTypography.labelMedium.copyWith(
                      color: AppColors.ivory,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
    ],
  );
}

/// "Neden önerildi?" - every astrological reason, verbatim from the server.
class _WhyDetails extends StatelessWidget {
  const _WhyDetails({required this.suggestion});
  final StoneSuggestion suggestion;

  @override
  Widget build(BuildContext context) {
    final stone = suggestion.stone;
    final l10n = context.l10n;
    return Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: EdgeInsets.zero,
        childrenPadding: const EdgeInsets.only(bottom: AppSpacing.sm),
        iconColor: AppColors.gold,
        collapsedIconColor: AppColors.gold,
        minTileHeight: AppSpacing.minTapTarget,
        title: Text(
          b12(context, 'why_suggested'),
          style: AppTypography.labelLarge.copyWith(color: AppColors.goldBright),
        ),
        expandedCrossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final reason in suggestion.reasons)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Icon(
                      _tag(reason).$2,
                      size: 14,
                      color: AppColors.gold,
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(reason.text, style: AppTypography.bodyMedium),
                  ),
                ],
              ),
            ),
          const SizedBox(height: AppSpacing.xs),
          Wrap(
            spacing: AppSpacing.xs,
            runSpacing: AppSpacing.xs,
            children: [
              for (final planet in stone.planets)
                AstroBadge(label: l10n.planet(planet)),
              for (final element in stone.elements)
                AstroBadge(label: b12(context, 'element_$element')),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            '${b12(context, 'stone_intents')}: '
            '${stone.intents.map((i) => b12(context, 'intent_${i.name}')).join(', ')}',
            style: AppTypography.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _HeroStone extends StatelessWidget {
  const _HeroStone({required this.suggestion});
  final StoneSuggestion suggestion;

  @override
  Widget build(BuildContext context) {
    final stone = suggestion.stone;
    return AstroCard(
      borderColor: AppColors.gold,
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Center(
            child: GemIllustration(color: Color(stone.colorValue), size: 112),
          ),
          const SizedBox(height: AppSpacing.lg),
          Text(
            b12(context, 'stone_best_match').toUpperCase(),
            textAlign: TextAlign.center,
            style: AppTypography.overline.copyWith(color: AppColors.gold),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            stone.name,
            textAlign: TextAlign.center,
            style: AppTypography.displayMedium.copyWith(fontSize: 30),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            stone.note,
            textAlign: TextAlign.center,
            style: AppTypography.bodyMedium,
          ),
          const SizedBox(height: AppSpacing.lg),
          Center(child: _ReasonTags(reasons: _topReasons(suggestion, 3))),
          const SizedBox(height: AppSpacing.sm),
          _WhyDetails(suggestion: suggestion),
        ],
      ),
    );
  }
}

class _CompactStone extends StatelessWidget {
  const _CompactStone({required this.suggestion});
  final StoneSuggestion suggestion;

  @override
  Widget build(BuildContext context) {
    final stone = suggestion.stone;
    return AstroCard(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.cardPadding,
        AppSpacing.cardPadding,
        AppSpacing.cardPadding,
        AppSpacing.xs,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              GemIllustration(color: Color(stone.colorValue), size: 52),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(stone.name, style: AppTypography.titleLarge),
                    const SizedBox(height: AppSpacing.xxs),
                    Text(
                      stone.note,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: AppTypography.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          _ReasonTags(reasons: _topReasons(suggestion, 2)),
          _WhyDetails(suggestion: suggestion),
        ],
      ),
    );
  }
}

class _ElementBalance extends StatelessWidget {
  const _ElementBalance({required this.result});
  final StoneRecommendation result;

  @override
  Widget build(BuildContext context) => AstroCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(b12(context, 'element_balance'), style: AppTypography.titleLarge),
        const SizedBox(height: AppSpacing.md),
        for (final entry in result.elementBalance.entries)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: Row(
              children: [
                SizedBox(
                  width: 76,
                  child: Text(
                    b12(context, 'element_${entry.key}'),
                    style: AppTypography.bodyMedium,
                  ),
                ),
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: entry.value / 10,
                      minHeight: 6,
                      backgroundColor: AppColors.surfaceMuted,
                      color: result.weakestElements.contains(entry.key)
                          ? AppColors.warning
                          : AppColors.gold,
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                SizedBox(
                  width: 20,
                  child: Text(
                    '${entry.value}',
                    textAlign: TextAlign.end,
                    style: AppTypography.labelMedium,
                  ),
                ),
              ],
            ),
          ),
      ],
    ),
  );
}

/// A faceted gem drawn in the stone's catalogue colour. No bitmap asset
/// exists per stone, so the illustration is vector and colour-driven.
class GemIllustration extends StatelessWidget {
  const GemIllustration({super.key, required this.color, this.size = 64});
  final Color color;
  final double size;
  @override
  Widget build(BuildContext context) => SizedBox.square(
    dimension: size,
    child: CustomPaint(painter: _GemPainter(color)),
  );
}

class _GemPainter extends CustomPainter {
  _GemPainter(this.color);
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    final top = Path()
      ..moveTo(w * .25, h * .18)
      ..lineTo(w * .75, h * .18)
      ..lineTo(w * .95, h * .4)
      ..lineTo(w * .05, h * .4)
      ..close();
    final bottom = Path()
      ..moveTo(w * .05, h * .4)
      ..lineTo(w * .95, h * .4)
      ..lineTo(w * .5, h * .92)
      ..close();
    final light = Color.lerp(color, Colors.white, .45)!;
    final dark = Color.lerp(color, Colors.black, .35)!;
    canvas.drawCircle(
      Offset(w / 2, h / 2),
      w * .5,
      Paint()
        ..color = color.withValues(alpha: .14)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 12),
    );
    canvas.drawPath(top, Paint()..color = light);
    canvas.drawPath(
      bottom,
      Paint()
        ..shader = LinearGradient(
          colors: [color, dark],
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
        ).createShader(Offset.zero & size),
    );
    final edge = Paint()
      ..color = AppColors.goldBright.withValues(alpha: .8)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    canvas.drawPath(top, edge);
    canvas.drawPath(bottom, edge);
    canvas.drawLine(Offset(w * .35, h * .4), Offset(w * .5, h * .92), edge);
    canvas.drawLine(Offset(w * .65, h * .4), Offset(w * .5, h * .92), edge);
    canvas.drawLine(Offset(w * .25, h * .18), Offset(w * .35, h * .4), edge);
    canvas.drawLine(Offset(w * .75, h * .18), Offset(w * .65, h * .4), edge);
  }

  @override
  bool shouldRepaint(covariant _GemPainter old) => old.color != color;
}
