import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../../core/extensions/context_extensions.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_typography.dart';

/// The score ring from the reference: a champagne arc with a soft halo and the
/// score set in the serif face.
class FrequencyRing extends StatelessWidget {
  const FrequencyRing({
    required this.score,
    required this.caption,
    super.key,
    this.size = 132,
    this.maxScore = 100,
  });

  final int score;
  final String caption;
  final double size;
  final int maxScore;

  @override
  Widget build(BuildContext context) {
    final double fraction = (score / maxScore).clamp(0, 1).toDouble();

    return Semantics(
      label: context.l10n.homeScoreSemantics(score),
      excludeSemantics: true,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          SizedBox(
            width: size,
            height: size,
            child: CustomPaint(
              painter: _RingPainter(fraction: fraction),
              child: Padding(
                // Keep the number inside the ring at any text scale.
                padding: EdgeInsets.all(size * 0.16),
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Text(
                        '$score',
                        style: AppTypography.score.copyWith(
                          fontSize: size * 0.34,
                        ),
                      ),
                      Text(
                        '/$maxScore',
                        style: AppTypography.bodySmall.copyWith(
                          fontSize: (size * 0.1).clamp(
                            AppTypography.minFontSize,
                            18,
                          ),
                          color: AppColors.ivoryMuted,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            caption,
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: AppTypography.titleMedium.copyWith(fontSize: 15),
          ),
        ],
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  _RingPainter({required this.fraction});

  final double fraction;

  @override
  void paint(Canvas canvas, Size size) {
    final Offset center = size.center(Offset.zero);
    final double stroke = size.shortestSide * 0.075;
    final double radius = (size.shortestSide - stroke) / 2;
    final Rect rect = Rect.fromCircle(center: center, radius: radius);

    final Paint track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..color = AppColors.surfaceMuted;
    canvas.drawCircle(center, radius, track);

    if (fraction <= 0) return;

    final Paint halo = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke * 1.7
      ..strokeCap = StrokeCap.round
      ..color = AppColors.gold.withValues(alpha: 0.16)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);

    final Paint arc = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round
      ..shader = const SweepGradient(
        startAngle: -math.pi / 2,
        endAngle: 3 * math.pi / 2,
        colors: <Color>[
          AppColors.goldWarm,
          AppColors.goldBright,
          AppColors.gold,
          AppColors.goldWarm,
        ],
      ).createShader(rect);

    const double start = -math.pi / 2;
    final double sweep = 2 * math.pi * fraction;
    canvas
      ..drawArc(rect, start, sweep, false, halo)
      ..drawArc(rect, start, sweep, false, arc);
  }

  @override
  bool shouldRepaint(_RingPainter oldDelegate) =>
      oldDelegate.fraction != fraction;
}
