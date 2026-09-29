import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../astrology/domain/aspect.dart';
import '../theme/app_colors.dart';

/// Aspect symbols drawn with a painter.
///
/// The astrological glyphs (☌ ⚹ □ △ ☍) are missing from most shipped fonts on
/// Android and iOS, so relying on text would produce tofu boxes on some
/// devices. Painting them keeps the look identical everywhere.
class AspectGlyph extends StatelessWidget {
  const AspectGlyph({
    required this.type,
    super.key,
    this.size = 16,
    this.color = AppColors.gold,
    this.strokeWidth = 1.4,
  });

  final AspectType type;
  final double size;
  final Color color;
  final double strokeWidth;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: size,
    height: size,
    child: CustomPaint(
      painter: _AspectGlyphPainter(
        type: type,
        color: color,
        strokeWidth: strokeWidth,
      ),
    ),
  );
}

class _AspectGlyphPainter extends CustomPainter {
  _AspectGlyphPainter({
    required this.type,
    required this.color,
    required this.strokeWidth,
  });

  final AspectType type;
  final Color color;
  final double strokeWidth;

  @override
  void paint(Canvas canvas, Size size) {
    final Paint paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeJoin = StrokeJoin.round
      ..strokeCap = StrokeCap.round
      ..isAntiAlias = true;

    final Offset center = size.center(Offset.zero);
    final double r = size.shortestSide / 2 - strokeWidth;

    switch (type) {
      case AspectType.conjunction:
        // Circle with a radius stroke: ☌
        canvas.drawCircle(center + Offset(0, r * 0.28), r * 0.55, paint);
        canvas.drawLine(
          center + Offset(r * 0.38, -r * 0.1),
          center + Offset(r * 0.95, -r * 0.85),
          paint,
        );
      case AspectType.sextile:
        // Six-spoke asterisk: ⚹
        for (int i = 0; i < 3; i++) {
          final double angle = math.pi * i / 3;
          final Offset delta = Offset(math.cos(angle), math.sin(angle)) * r;
          canvas.drawLine(center - delta, center + delta, paint);
        }
      case AspectType.square:
        canvas.drawRect(
          Rect.fromCenter(center: center, width: r * 1.7, height: r * 1.7),
          paint,
        );
      case AspectType.trine:
        final Path path = Path()
          ..moveTo(center.dx, center.dy - r)
          ..lineTo(center.dx + r * 0.92, center.dy + r * 0.72)
          ..lineTo(center.dx - r * 0.92, center.dy + r * 0.72)
          ..close();
        canvas.drawPath(path, paint);
      case AspectType.opposition:
        // Two circles joined by a line: ☍
        canvas.drawCircle(center + Offset(-r * 0.62, 0), r * 0.36, paint);
        canvas.drawCircle(center + Offset(r * 0.62, 0), r * 0.36, paint);
        canvas.drawLine(
          center + Offset(-r * 0.26, 0),
          center + Offset(r * 0.26, 0),
          paint,
        );
    }
  }

  @override
  bool shouldRepaint(_AspectGlyphPainter oldDelegate) =>
      oldDelegate.type != type ||
      oldDelegate.color != color ||
      oldDelegate.strokeWidth != strokeWidth;
}
