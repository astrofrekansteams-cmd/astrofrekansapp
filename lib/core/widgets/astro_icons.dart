import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// Astrofrekans' own icon set, drawn with a painter: fine gold lines with a
/// few small "star" dots, the same at every size on every device. Used instead
/// of emoji (which each phone draws differently, in colour, out of keeping
/// with the app) and of glyph characters that some fonts do not have.
enum AstroIconData {
  sparkle,
  heart,
  chat,
  moon,
  flame,
  wall,
  sprout,
  crystalBall,
  check,
  star,
  sun,
  calendar,
  eclipse,
  retrograde,
  hourglass,
  key,
  eye,
  compass,
  lightning,
  scales,
  coin,
  book,
  gem,
  path,
  house,
  clock,
  question,
  infinity,
  leaf,
  hand,
}

class AstroIcon extends StatelessWidget {
  const AstroIcon(
    this.icon, {
    super.key,
    this.size = 24,
    this.color = AppColors.gold,
    this.strokeWidth,
    this.filled = false,
  });

  final AstroIconData icon;
  final double size;
  final Color color;

  /// Line weight at 24 px scale; defaults to a weight that stays legible from
  /// 14 to 48 px.
  final double? strokeWidth;

  /// Solid fill for the main shape (ratings, "done").
  final bool filled;

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _IconPainter(icon, color, strokeWidth ?? 1.6, filled),
      ),
    ),
  );
}

class _IconPainter extends CustomPainter {
  _IconPainter(this.icon, this.color, this.stroke, this.filled);
  final AstroIconData icon;
  final Color color;
  final double stroke;
  final bool filled;

  @override
  void paint(Canvas canvas, Size size) {
    final double u = size.shortestSide / 24;
    canvas.scale(u);
    final line = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..isAntiAlias = true;
    final fill = Paint()
      ..color = color
      ..style = PaintingStyle.fill
      ..isAntiAlias = true;
    final soft = Paint()
      ..color = color.withValues(alpha: 0.22)
      ..style = PaintingStyle.fill
      ..isAntiAlias = true;

    void dot(double x, double y, [double r = 1.1]) =>
        canvas.drawCircle(Offset(x, y), r, fill);
    void shape(Path p) {
      if (filled) canvas.drawPath(p, fill);
      canvas.drawPath(p, line);
    }

    Path star4(double cx, double cy, double r, [double inner = 0.28]) {
      final p = Path();
      for (var i = 0; i < 8; i++) {
        final a = -math.pi / 2 + i * math.pi / 4;
        final rad = i.isEven ? r : r * inner;
        final pt = Offset(cx + rad * math.cos(a), cy + rad * math.sin(a));
        i == 0 ? p.moveTo(pt.dx, pt.dy) : p.lineTo(pt.dx, pt.dy);
      }
      return p..close();
    }

    switch (icon) {
      case AstroIconData.sparkle:
        shape(star4(11, 12, 8.5));
        dot(19.5, 4.5);
        dot(4.5, 19.5, 0.9);
      case AstroIconData.heart:
        final p = Path()
          ..moveTo(12, 20.5)
          ..cubicTo(3, 14.5, 2.5, 9.5, 5.5, 6.8)
          ..cubicTo(8, 4.6, 11, 5.6, 12, 8)
          ..cubicTo(13, 5.6, 16, 4.6, 18.5, 6.8)
          ..cubicTo(21.5, 9.5, 21, 14.5, 12, 20.5)
          ..close();
        shape(p);
        dot(17.5, 9.5, 0.9);
      case AstroIconData.chat:
        final p = Path()
          ..moveTo(5, 5)
          ..lineTo(19, 5)
          ..quadraticBezierTo(21, 5, 21, 7)
          ..lineTo(21, 14)
          ..quadraticBezierTo(21, 16, 19, 16)
          ..lineTo(11, 16)
          ..lineTo(6.5, 20)
          ..lineTo(6.5, 16)
          ..lineTo(5, 16)
          ..quadraticBezierTo(3, 16, 3, 14)
          ..lineTo(3, 7)
          ..quadraticBezierTo(3, 5, 5, 5)
          ..close();
        shape(p);
        dot(8, 10.5, 0.9);
        dot(12, 10.5, 0.9);
        dot(16, 10.5, 0.9);
      case AstroIconData.moon:
        final p = Path()
          ..moveTo(16.5, 3.8)
          ..arcToPoint(
            const Offset(16.5, 20.2),
            radius: const Radius.circular(8.4),
            clockwise: false,
          )
          ..arcToPoint(
            const Offset(16.5, 3.8),
            radius: const Radius.circular(6.2),
            clockwise: true,
          )
          ..close();
        shape(p);
        dot(19.5, 8.5, 0.9);
        dot(21, 13, 0.7);
      case AstroIconData.flame:
        final p = Path()
          ..moveTo(12, 21)
          ..cubicTo(6.5, 21, 4.8, 16, 7.8, 11.5)
          ..cubicTo(8.6, 13, 9.4, 13.4, 10.2, 13.2)
          ..cubicTo(9.6, 9.5, 11, 5.5, 14, 3)
          ..cubicTo(14.4, 7, 19.5, 9.5, 18.4, 15.5)
          ..cubicTo(17.8, 19, 15, 21, 12, 21)
          ..close();
        shape(p);
        canvas.drawPath(
          Path()
            ..moveTo(12, 21)
            ..cubicTo(9.8, 21, 9.2, 18.2, 10.8, 16.4)
            ..cubicTo(11.4, 17.2, 12.2, 17.2, 12.8, 16.6)
            ..cubicTo(13.4, 18, 14.6, 20.4, 12, 21),
          soft,
        );
      case AstroIconData.wall:
        final r = RRect.fromRectAndRadius(
          const Rect.fromLTWH(3, 5, 18, 14),
          const Radius.circular(1.5),
        );
        if (filled) canvas.drawRRect(r, fill);
        canvas.drawRRect(r, line);
        canvas.drawLine(const Offset(3, 9.7), const Offset(21, 9.7), line);
        canvas.drawLine(const Offset(3, 14.4), const Offset(21, 14.4), line);
        canvas.drawLine(const Offset(9, 5), const Offset(9, 9.7), line);
        canvas.drawLine(const Offset(15, 9.7), const Offset(15, 14.4), line);
        canvas.drawLine(const Offset(9, 14.4), const Offset(9, 19), line);
      case AstroIconData.sprout:
        canvas.drawLine(const Offset(12, 21), const Offset(12, 11), line);
        shape(
          Path()
            ..moveTo(12, 13)
            ..cubicTo(6, 13.5, 3.5, 10, 3.5, 5.5)
            ..cubicTo(8.5, 5.5, 12, 8, 12, 13)
            ..close(),
        );
        shape(
          Path()
            ..moveTo(12, 10.5)
            ..cubicTo(12, 6, 15, 3.5, 20.5, 3.5)
            ..cubicTo(20.5, 8, 17.5, 10.5, 12, 10.5)
            ..close(),
        );
        canvas.drawLine(const Offset(8, 21), const Offset(16, 21), line);
      case AstroIconData.crystalBall:
        canvas.drawCircle(const Offset(12, 10.5), 7.5, line);
        if (filled) canvas.drawCircle(const Offset(12, 10.5), 7.5, fill);
        canvas.drawPath(
          Path()
            ..moveTo(6.5, 18.5)
            ..lineTo(5, 21)
            ..lineTo(19, 21)
            ..lineTo(17.5, 18.5),
          line,
        );
        dot(9, 8, 1);
        dot(14.5, 12.5, 0.8);
        canvas.drawPath(star4(15, 7.5, 2, 0.3), fill);
      case AstroIconData.check:
        canvas.drawCircle(const Offset(12, 12), 9, line);
        if (filled) canvas.drawCircle(const Offset(12, 12), 9, soft);
        canvas.drawPath(
          Path()
            ..moveTo(7.8, 12.4)
            ..lineTo(10.7, 15.2)
            ..lineTo(16.4, 9),
          line,
        );
      case AstroIconData.star:
        final p = Path();
        for (var i = 0; i < 10; i++) {
          final a = -math.pi / 2 + i * math.pi / 5;
          final rad = i.isEven ? 9.0 : 4.0;
          final pt = Offset(12 + rad * math.cos(a), 12.5 + rad * math.sin(a));
          i == 0 ? p.moveTo(pt.dx, pt.dy) : p.lineTo(pt.dx, pt.dy);
        }
        shape(p..close());
      case AstroIconData.sun:
        canvas.drawCircle(const Offset(12, 12), 4.2, line);
        if (filled) canvas.drawCircle(const Offset(12, 12), 4.2, fill);
        for (var i = 0; i < 8; i++) {
          final a = i * math.pi / 4;
          final long = i.isEven;
          canvas.drawLine(
            Offset(12 + 6.8 * math.cos(a), 12 + 6.8 * math.sin(a)),
            Offset(
              12 + (long ? 10 : 8.8) * math.cos(a),
              12 + (long ? 10 : 8.8) * math.sin(a),
            ),
            line,
          );
        }
      case AstroIconData.calendar:
        final r = RRect.fromRectAndRadius(
          const Rect.fromLTWH(3.5, 5, 17, 15.5),
          const Radius.circular(2.5),
        );
        canvas.drawRRect(r, line);
        canvas.drawLine(const Offset(3.5, 10), const Offset(20.5, 10), line);
        canvas.drawLine(const Offset(8, 3), const Offset(8, 7), line);
        canvas.drawLine(const Offset(16, 3), const Offset(16, 7), line);
        canvas.drawPath(star4(12, 15, 2.6, 0.32), fill);
      case AstroIconData.eclipse:
        canvas.drawCircle(const Offset(12, 12), 8.5, line);
        canvas.drawCircle(const Offset(12, 12), 6.3, fill);
        canvas.drawCircle(
          const Offset(15, 10),
          6.3,
          Paint()..color = const Color(0xFF05070F),
        );
        canvas.drawCircle(
          const Offset(15, 10),
          6.3,
          line..strokeWidth = stroke * 0.7,
        );
      case AstroIconData.retrograde:
        // A path turning back on itself: an arrow with a U-turn.
        canvas.drawPath(
          Path()
            ..moveTo(20, 17)
            ..lineTo(9, 17)
            ..cubicTo(4.5, 17, 4.5, 8, 9, 8)
            ..lineTo(19, 8),
          line,
        );
        canvas.drawPath(
          Path()
            ..moveTo(15.5, 4.5)
            ..lineTo(19.5, 8)
            ..lineTo(15.5, 11.5),
          line,
        );
        dot(20, 17, 1.2);
      case AstroIconData.hourglass:
        canvas.drawPath(
          Path()
            ..moveTo(6.5, 3.5)
            ..lineTo(17.5, 3.5)
            ..lineTo(17.5, 6.5)
            ..lineTo(12, 12)
            ..lineTo(17.5, 17.5)
            ..lineTo(17.5, 20.5)
            ..lineTo(6.5, 20.5)
            ..lineTo(6.5, 17.5)
            ..lineTo(12, 12)
            ..lineTo(6.5, 6.5)
            ..close(),
          line,
        );
        canvas.drawPath(
          Path()
            ..moveTo(9, 19)
            ..lineTo(15, 19)
            ..lineTo(12, 15.5)
            ..close(),
          fill,
        );
      case AstroIconData.key:
        canvas.drawCircle(const Offset(8, 10), 4.6, line);
        canvas.drawLine(const Offset(11.3, 13.3), const Offset(20.5, 22), line);
        canvas.drawLine(const Offset(16.5, 17.5), const Offset(19, 15), line);
        dot(8, 10, 1);
      case AstroIconData.eye:
        canvas.drawPath(
          Path()
            ..moveTo(2.5, 12)
            ..quadraticBezierTo(12, 2.5, 21.5, 12)
            ..quadraticBezierTo(12, 21.5, 2.5, 12)
            ..close(),
          line,
        );
        canvas.drawCircle(const Offset(12, 12), 3.2, line);
        dot(12, 12, 1.2);
      case AstroIconData.compass:
        canvas.drawCircle(const Offset(12, 12), 9, line);
        shape(
          Path()
            ..moveTo(15.5, 8.5)
            ..lineTo(13.4, 13.4)
            ..lineTo(8.5, 15.5)
            ..lineTo(10.6, 10.6)
            ..close(),
        );
        dot(12, 12, 0.9);
      case AstroIconData.lightning:
        shape(
          Path()
            ..moveTo(13.5, 2.5)
            ..lineTo(5.5, 13.5)
            ..lineTo(11.5, 13.5)
            ..lineTo(10.5, 21.5)
            ..lineTo(18.5, 10.5)
            ..lineTo(12.5, 10.5)
            ..close(),
        );
      case AstroIconData.scales:
        canvas.drawLine(const Offset(12, 4), const Offset(12, 20), line);
        canvas.drawLine(const Offset(7, 20.5), const Offset(17, 20.5), line);
        canvas.drawLine(const Offset(4.5, 7), const Offset(19.5, 7), line);
        canvas.drawPath(
          Path()
            ..moveTo(4.5, 7)
            ..lineTo(2.5, 13)
            ..arcToPoint(
              const Offset(6.5, 13),
              radius: const Radius.circular(2),
            )
            ..close(),
          line,
        );
        canvas.drawPath(
          Path()
            ..moveTo(19.5, 7)
            ..lineTo(17.5, 13)
            ..arcToPoint(
              const Offset(21.5, 13),
              radius: const Radius.circular(2),
            )
            ..close(),
          line,
        );
        dot(12, 4, 1.2);
      case AstroIconData.coin:
        canvas.drawCircle(const Offset(12, 12), 9, line);
        canvas.drawCircle(
          const Offset(12, 12),
          6.2,
          line..strokeWidth = stroke * 0.6,
        );
        canvas.drawPath(star4(12, 12, 3.6, 0.3), fill);
      case AstroIconData.book:
        canvas.drawPath(
          Path()
            ..moveTo(12, 6)
            ..cubicTo(9.5, 4, 6, 4, 3.5, 5)
            ..lineTo(3.5, 19)
            ..cubicTo(6, 18, 9.5, 18, 12, 20)
            ..cubicTo(14.5, 18, 18, 18, 20.5, 19)
            ..lineTo(20.5, 5)
            ..cubicTo(18, 4, 14.5, 4, 12, 6)
            ..close(),
          line,
        );
        canvas.drawLine(const Offset(12, 6), const Offset(12, 20), line);
        dot(16.5, 9, 0.9);
      case AstroIconData.gem:
        shape(
          Path()
            ..moveTo(7, 4)
            ..lineTo(17, 4)
            ..lineTo(21.5, 9.5)
            ..lineTo(12, 21)
            ..lineTo(2.5, 9.5)
            ..close(),
        );
        canvas.drawPath(
          Path()
            ..moveTo(2.5, 9.5)
            ..lineTo(21.5, 9.5)
            ..moveTo(9, 4)
            ..lineTo(7.5, 9.5)
            ..lineTo(12, 21)
            ..moveTo(15, 4)
            ..lineTo(16.5, 9.5)
            ..lineTo(12, 21),
          line..strokeWidth = stroke * 0.75,
        );
      case AstroIconData.path:
        canvas.drawPath(
          Path()
            ..moveTo(5, 21)
            ..cubicTo(5, 15, 19, 17, 19, 11)
            ..cubicTo(19, 7, 12, 8, 12, 4),
          line,
        );
        dot(5, 21, 1.3);
        canvas.drawPath(star4(12, 4.5, 2.6, 0.3), fill);
      case AstroIconData.house:
        shape(
          Path()
            ..moveTo(3.5, 11)
            ..lineTo(12, 3.5)
            ..lineTo(20.5, 11)
            ..lineTo(20.5, 20.5)
            ..lineTo(3.5, 20.5)
            ..close(),
        );
        canvas.drawLine(const Offset(9.5, 20.5), const Offset(9.5, 14), line);
        canvas.drawLine(const Offset(14.5, 20.5), const Offset(14.5, 14), line);
        canvas.drawLine(const Offset(9.5, 14), const Offset(14.5, 14), line);
      case AstroIconData.clock:
        canvas.drawCircle(const Offset(12, 12), 9, line);
        canvas.drawPath(
          Path()
            ..moveTo(12, 6.5)
            ..lineTo(12, 12)
            ..lineTo(16, 14.4),
          line,
        );
        dot(12, 12, 1);
      case AstroIconData.question:
        canvas.drawPath(
          Path()
            ..moveTo(8.5, 8.8)
            ..cubicTo(8.5, 4.5, 15.5, 4.5, 15.5, 8.8)
            ..cubicTo(15.5, 11.8, 12, 11.6, 12, 15),
          line,
        );
        dot(12, 19.2, 1.3);
      case AstroIconData.infinity:
        canvas.drawPath(
          Path()
            ..moveTo(12, 12)
            ..cubicTo(14, 8, 21, 8, 21, 12)
            ..cubicTo(21, 16, 14, 16, 12, 12)
            ..cubicTo(10, 8, 3, 8, 3, 12)
            ..cubicTo(3, 16, 10, 16, 12, 12),
          line,
        );
      case AstroIconData.leaf:
        shape(
          Path()
            ..moveTo(5, 19)
            ..cubicTo(3, 9, 10, 4, 20, 4)
            ..cubicTo(20, 14, 14, 21, 5, 19)
            ..close(),
        );
        canvas.drawLine(const Offset(5, 19), const Offset(14, 10), line);
      case AstroIconData.hand:
        canvas.drawPath(
          Path()
            ..moveTo(8, 21)
            ..lineTo(5.5, 14)
            ..lineTo(5.5, 9.5)
            ..moveTo(9, 13)
            ..lineTo(9, 4.5)
            ..moveTo(12.5, 13)
            ..lineTo(12.5, 3.5)
            ..moveTo(16, 13)
            ..lineTo(16, 5)
            ..moveTo(19.5, 13.5)
            ..lineTo(19.5, 8.5)
            ..moveTo(19.5, 13.5)
            ..cubicTo(19.5, 19, 17, 21, 13.5, 21)
            ..lineTo(8, 21),
          line,
        );
    }
  }

  @override
  bool shouldRepaint(_IconPainter old) =>
      old.icon != icon ||
      old.color != color ||
      old.stroke != stroke ||
      old.filled != filled;
}
