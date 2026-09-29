import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../core/astrology/domain/aspect.dart';
import '../../../core/astrology/domain/natal_chart.dart';
import '../../../core/astrology/domain/planet.dart';
import '../../../core/astrology/domain/zodiac_sign.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/localization/astro_labels.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/widgets.dart';

/// Chart presentation shared by natal, return, composite and Davison charts.
///
/// Only plots and tabulates the server's longitudes. No ephemeris, midpoint
/// or house calculation happens here.

const planetGlyphs = <Planet, String>{
  Planet.sun: '☉',
  Planet.moon: '☽',
  Planet.mercury: '☿',
  Planet.venus: '♀',
  Planet.mars: '♂',
  Planet.jupiter: '♃',
  Planet.saturn: '♄',
  Planet.uranus: '♅',
  Planet.neptune: '♆',
  Planet.pluto: '♇',
  Planet.northNode: '☊',
  Planet.southNode: '☋',
};

const signGlyphs = ['♈', '♉', '♊', '♋', '♌', '♍', '♎', '♏', '♐', '♑', '♒', '♓'];

String formatDegree(double longitude) {
  final inSign = longitude % 30;
  final degree = inSign.floor();
  final minute = ((inSign - degree) * 60).floor();
  return '$degree°${minute.toString().padLeft(2, '0')}′';
}

/// Table name: the lunar nodes use their short form so a row never truncates.
String planetTableName(BuildContext context, Planet planet) => switch (planet) {
  Planet.northNode => b12(context, 'north_node_short'),
  Planet.southNode => b12(context, 'south_node_short'),
  _ => context.l10n.planet(planet),
};

class ChartView extends StatelessWidget {
  const ChartView({super.key, required this.chart, this.showEngine = true});
  final NatalChart chart;
  final bool showEngine;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final asc = chart.ascendantLongitude;
    final mc = chart.midheavenLongitude;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // The wheel stays the focal point.
        AstroCard(
          padding: const EdgeInsets.all(AppSpacing.sm),
          child: Semantics(
            label: b12(context, 'natal'),
            image: true,
            child: AspectRatio(
              aspectRatio: 1,
              child: CustomPaint(painter: ChartWheelPainter(chart)),
            ),
          ),
        ),
        if (chart.warnings.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          AstroCard(
            borderColor: AppColors.warning.withValues(alpha: .5),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final w in chart.warnings)
                  Text(
                    w.startsWith('birth_time_unknown')
                        ? b12(context, 'birth_time_unknown_note')
                        : w,
                    style: AppTypography.bodyMedium,
                  ),
              ],
            ),
          ),
        ],
        if (asc != null || mc != null) ...[
          const SizedBox(height: AppSpacing.cardGap),
          Row(
            children: [
              if (asc != null)
                Expanded(
                  child: _AngleTile(label: 'ASC', longitude: asc),
                ),
              if (asc != null && mc != null)
                const SizedBox(width: AppSpacing.md),
              if (mc != null)
                Expanded(
                  child: _AngleTile(label: 'MC', longitude: mc),
                ),
            ],
          ),
        ],
        const SizedBox(height: AppSpacing.sectionGap),
        AstroSectionTitle(title: b12(context, 'planets')),
        const SizedBox(height: AppSpacing.md),
        AstroCard(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.cardPadding,
            vertical: AppSpacing.xs,
          ),
          child: Column(
            children: [
              for (var i = 0; i < chart.planets.length; i++)
                _PlanetRow(
                  position: chart.planets[i],
                  label: planetTableName(context, chart.planets[i].planet),
                  divider: i > 0,
                ),
            ],
          ),
        ),
        if (chart.houses.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.sectionGap),
          AstroSectionTitle(title: b12(context, 'houses_title')),
          const SizedBox(height: AppSpacing.md),
          AstroCard(
            child: LayoutBuilder(
              builder: (context, constraints) {
                const gap = AppSpacing.md;
                final cell = (constraints.maxWidth - gap) / 2;
                return Wrap(
                  spacing: gap,
                  runSpacing: AppSpacing.md,
                  children: [
                    for (final h in chart.houses)
                      SizedBox(
                        width: cell,
                        child: _HouseCell(house: h),
                      ),
                  ],
                );
              },
            ),
          ),
        ],
        const SizedBox(height: AppSpacing.sectionGap),
        AstroSectionTitle(title: b12(context, 'aspects')),
        const SizedBox(height: AppSpacing.md),
        AstroCard(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.cardPadding,
            vertical: AppSpacing.sm,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (final a in chart.aspects)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
                  child: Row(
                    children: [
                      _Glyph(planetGlyphs[a.first] ?? ''),
                      const SizedBox(width: AppSpacing.xs),
                      AspectGlyph(type: a.type, size: 16),
                      const SizedBox(width: AppSpacing.xs),
                      _Glyph(planetGlyphs[a.second] ?? ''),
                      const SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: Text(
                          '${planetTableName(context, a.first)} '
                          '${l10n.aspect(a.type)} '
                          '${planetTableName(context, a.second)}',
                          style: AppTypography.bodyMedium.copyWith(
                            color: AppColors.ivory,
                          ),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Text(
                        '${a.orb.toStringAsFixed(1)}°',
                        style: AppTypography.labelMedium,
                      ),
                    ],
                  ),
                ),
              if (chart.aspects.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
                  child: Text(
                    b12(context, 'empty'),
                    style: AppTypography.bodyMedium,
                  ),
                ),
            ],
          ),
        ),
        if (showEngine && chart.engineVersion != null) ...[
          const SizedBox(height: AppSpacing.lg),
          Text(
            '${chart.houseSystem.displayName} · ${chart.engineVersion}',
            textAlign: TextAlign.center,
            style: AppTypography.labelSmall,
          ),
        ],
      ],
    );
  }
}

class _Glyph extends StatelessWidget {
  const _Glyph(this.glyph);
  final String glyph;
  @override
  Widget build(BuildContext context) => SizedBox(
    width: 20,
    child: Text(
      glyph,
      textAlign: TextAlign.center,
      style: const TextStyle(color: AppColors.goldBright, fontSize: 18),
    ),
  );
}

class _AngleTile extends StatelessWidget {
  const _AngleTile({required this.label, required this.longitude});
  final String label;
  final double longitude;
  @override
  Widget build(BuildContext context) {
    final sign = ZodiacSign.fromLongitude(longitude);
    return AstroCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        children: [
          AstroImage(sign.asset, width: 32, height: 32),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: AppTypography.overline.copyWith(color: AppColors.gold),
                ),
                Text(
                  context.l10n.sign(sign),
                  style: AppTypography.titleMedium,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(formatDegree(longitude), style: AppTypography.bodyMedium),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _HouseCell extends StatelessWidget {
  const _HouseCell({required this.house});
  final HousePosition house;
  @override
  Widget build(BuildContext context) => Row(
    children: [
      Container(
        width: 30,
        height: 30,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: AppColors.hairlineStrong),
        ),
        child: Text(
          '${house.number}',
          style: AppTypography.labelMedium.copyWith(color: AppColors.gold),
        ),
      ),
      const SizedBox(width: AppSpacing.sm),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${signGlyphs[house.sign.index]} ${context.l10n.sign(house.sign)}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTypography.bodyMedium.copyWith(color: AppColors.ivory),
            ),
            Text(
              formatDegree(house.cuspLongitude),
              style: AppTypography.bodySmall,
            ),
          ],
        ),
      ),
    ],
  );
}

/// Two-line planet row for phones: name (+ retro badge) and house on the
/// first line, sign and degree on the second - nothing is squeezed.
class _PlanetRow extends StatelessWidget {
  const _PlanetRow({
    required this.position,
    required this.label,
    required this.divider,
  });
  final PlanetPosition position;
  final String label;
  final bool divider;

  @override
  Widget build(BuildContext context) {
    final sign = context.l10n.sign(position.sign);
    final degree = formatDegree(position.longitude);
    final house = position.house;
    return Semantics(
      label:
          '$label, $sign $degree'
          '${house == null ? '' : ', $house. ${b12(context, 'house')}'}'
          '${position.isRetrograde ? ', ${b12(context, 'retrograde')}' : ''}',
      excludeSemantics: true,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
        decoration: divider
            ? const BoxDecoration(
                border: Border(top: BorderSide(color: AppColors.hairline)),
              )
            : null,
        child: Row(
          children: [
            AstroImage(position.planet.asset, width: 30, height: 30),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Wrap lets the retro badge drop below the name on
                  // narrow phones instead of overflowing.
                  Wrap(
                    spacing: AppSpacing.sm,
                    runSpacing: AppSpacing.xs,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Text(
                        label,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTypography.titleMedium,
                      ),
                      if (position.isRetrograde)
                        AstroBadge(
                          label: '℞ ${b12(context, 'retro_short')}',
                          color: AppColors.warning,
                        ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.xxs),
                  Text(
                    '${signGlyphs[position.sign.index]}  $sign · $degree',
                    style: AppTypography.bodyMedium,
                  ),
                ],
              ),
            ),
            if (house != null) ...[
              const SizedBox(width: AppSpacing.sm),
              Container(
                constraints: const BoxConstraints(minWidth: 52),
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.sm,
                  vertical: AppSpacing.xs + 2,
                ),
                decoration: BoxDecoration(
                  borderRadius: AppRadius.badge,
                  border: Border.all(color: AppColors.hairlineStrong),
                ),
                child: Text(
                  '$house. ${b12(context, 'house')}',
                  textAlign: TextAlign.center,
                  style: AppTypography.labelMedium.copyWith(
                    color: AppColors.goldBright,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// The wheel: zodiac ring, house cusps, planets and aspect lines. The
/// Ascendant sits on the left, as charts are conventionally drawn.
///
/// Crowded planets are spread over two rings (and nudged apart within a
/// ring), with a hairline back to their true degree, so glyphs never stack.
class ChartWheelPainter extends CustomPainter {
  ChartWheelPainter(this.chart);
  final NatalChart chart;

  static const double _minGap = 9; // degrees between glyphs on one ring

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    // Leave room for the ASC / MC labels inside the canvas.
    final radius = size.shortestSide * .44;
    final gold = Paint()
      ..color = AppColors.gold
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    final faint = Paint()
      ..color = AppColors.gold.withValues(alpha: .28)
      ..style = PaintingStyle.stroke
      ..strokeWidth = .8;

    Offset point(double longitude, double r) {
      final angle =
          (180 - longitude + (chart.ascendantLongitude ?? 0)) * math.pi / 180;
      return center + Offset(math.cos(angle), math.sin(angle)) * r;
    }

    canvas.drawCircle(center, radius, gold);
    canvas.drawCircle(center, radius * .84, gold);
    canvas.drawCircle(center, radius * .44, faint);

    for (var i = 0; i < 12; i++) {
      canvas.drawLine(
        point(i * 30.0, radius * .84),
        point(i * 30.0, radius),
        gold,
      );
      _text(
        canvas,
        signGlyphs[i],
        point(i * 30.0 + 15, radius * .92),
        TextStyle(color: AppColors.goldBright, fontSize: radius * .1),
      );
    }

    for (final h in chart.houses) {
      final angular =
          h.number == 1 || h.number == 4 || h.number == 7 || h.number == 10;
      canvas.drawLine(
        point(h.cuspLongitude, radius * .44),
        point(h.cuspLongitude, radius * .84),
        angular ? gold : faint,
      );
      final next = chart.houses.firstWhere(
        (x) => x.number == h.number % 12 + 1,
        orElse: () => h,
      );
      final span = (next.cuspLongitude - h.cuspLongitude) % 360;
      _text(
        canvas,
        '${h.number}',
        point(h.cuspLongitude + span / 2, radius * .49),
        TextStyle(color: AppColors.textSubtle, fontSize: radius * .06),
      );
    }

    for (final a in chart.aspects) {
      final first = chart.positionOf(a.first);
      final second = chart.positionOf(a.second);
      if (first == null || second == null) continue;
      final color = switch (a.type.nature) {
        AspectNature.harmonious => AppColors.success,
        AspectNature.hard => AppColors.danger,
        AspectNature.neutral => AppColors.gold,
      };
      canvas.drawLine(
        point(first.longitude, radius * .42),
        point(second.longitude, radius * .42),
        Paint()
          ..color = color.withValues(alpha: .4)
          ..strokeWidth = .8,
      );
    }

    // Two-ring placement: walk the planets in zodiac order; a planet too
    // close to the last one on the outer ring goes to the inner ring, and
    // only if both rings are crowded is it nudged along its ring.
    const rings = <double>[.73, .6];
    final lastOnRing = <double?>[null, null];
    final sorted = [...chart.planets]
      ..sort((a, b) => a.longitude.compareTo(b.longitude));
    double gapTo(double at, double? other) =>
        other == null ? 360 : ((at - other + 540) % 360 - 180).abs();
    for (final p in sorted) {
      var ring = 0;
      var at = p.longitude;
      if (gapTo(at, lastOnRing[0]) < _minGap) {
        ring = gapTo(at, lastOnRing[1]) < _minGap ? 0 : 1;
      }
      final previous = lastOnRing[ring];
      if (previous != null && gapTo(at, previous) < _minGap) {
        at = previous + _minGap;
      }
      lastOnRing[ring] = at;

      final r = radius * rings[ring];
      canvas.drawCircle(
        point(p.longitude, radius * .84),
        2.4,
        Paint()..color = AppColors.gold,
      );
      canvas.drawLine(
        point(p.longitude, radius * .84),
        point(at, r + radius * .06),
        faint,
      );
      _text(
        canvas,
        planetGlyphs[p.planet] ?? '',
        point(at, r),
        TextStyle(
          color: p.isRetrograde ? AppColors.warning : AppColors.ivory,
          fontSize: radius * .105,
        ),
      );
    }

    final labelStyle = TextStyle(
      color: AppColors.gold,
      fontSize: math.max(12, radius * .06),
      fontWeight: FontWeight.w600,
    );
    final asc = chart.ascendantLongitude;
    if (asc != null) {
      _text(canvas, 'ASC', point(asc, radius * 1.1), labelStyle);
    }
    final mc = chart.midheavenLongitude;
    if (mc != null) {
      canvas.drawLine(
        point(mc, radius * .44),
        point(mc, radius),
        Paint()
          ..color = AppColors.gold
          ..strokeWidth = 1.4,
      );
      _text(canvas, 'MC', point(mc, radius * 1.1), labelStyle);
    }
  }

  void _text(Canvas canvas, String text, Offset at, TextStyle style) {
    final painter = TextPainter(
      text: TextSpan(text: text, style: style),
      textDirection: TextDirection.ltr,
    )..layout();
    painter.paint(canvas, at - Offset(painter.width / 2, painter.height / 2));
  }

  @override
  bool shouldRepaint(covariant ChartWheelPainter old) => old.chart != chart;
}
