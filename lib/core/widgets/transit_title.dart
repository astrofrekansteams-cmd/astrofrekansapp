import 'package:flutter/material.dart';

import '../astrology/domain/transit.dart';
import '../extensions/context_extensions.dart';
import '../localization/astro_labels.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'aspect_glyph.dart';

/// Renders "Jüpiter △ Venüs", "Ay → 5. Ev" or "Satürn Rx" from structured
/// transit data, in the current language, with painted aspect glyphs.
class TransitTitle extends StatelessWidget {
  const TransitTitle({
    required this.summary,
    super.key,
    this.style,
    this.glyphSize = 15,
    this.maxLines = 2,
  });

  final TransitSummary summary;
  final TextStyle? style;
  final double glyphSize;
  final int maxLines;

  @override
  Widget build(BuildContext context) {
    final TextStyle effective =
        style ?? AppTypography.titleLarge.copyWith(fontSize: 18);
    final String semantics = context.l10n.transitTitle(summary);

    final List<InlineSpan> spans = <InlineSpan>[];
    switch (summary.shape) {
      case TransitShape.aspect:
        spans.addAll(<InlineSpan>[
          TextSpan(text: context.l10n.planet(summary.transitingPlanet)),
          WidgetSpan(
            alignment: PlaceholderAlignment.middle,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 6),
              child: AspectGlyph(
                type: summary.aspect!,
                size: glyphSize,
                color: effective.color ?? AppColors.gold,
              ),
            ),
          ),
          TextSpan(text: context.l10n.planet(summary.natalPlanet!)),
        ]);
      case TransitShape.houseIngress:
        spans.addAll(<InlineSpan>[
          TextSpan(text: context.l10n.planet(summary.transitingPlanet)),
          WidgetSpan(
            alignment: PlaceholderAlignment.middle,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 5),
              child: Icon(
                Icons.arrow_forward,
                size: glyphSize,
                color: effective.color ?? AppColors.gold,
              ),
            ),
          ),
          TextSpan(text: context.l10n.houseOrdinal(summary.house!)),
        ]);
      case TransitShape.retrograde:
        spans.addAll(<InlineSpan>[
          TextSpan(text: context.l10n.planet(summary.transitingPlanet)),
          TextSpan(
            text: '  ${context.l10n.retrogradeShort}',
            style: effective.copyWith(color: AppColors.gold),
          ),
        ]);
      case TransitShape.planetary:
        spans.add(
          TextSpan(text: context.l10n.planet(summary.transitingPlanet)),
        );
    }

    return Semantics(
      label: semantics,
      excludeSemantics: true,
      child: Text.rich(
        TextSpan(children: spans),
        style: effective,
        maxLines: maxLines,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }
}
