import 'package:flutter/widgets.dart';

/// Spacing scale (4pt based) for Astrofrekans.
abstract final class AppSpacing {
  static const double xxs = 2;
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double xxl = 24;
  static const double xxxl = 32;
  static const double huge = 40;

  /// Horizontal page gutter. Slightly tighter on very small phones.
  static double pageGutter(double width) => width < 360 ? md : lg;

  /// Content column cap so the layout never stretches on tablets/foldables.
  static const double contentMaxWidth = 560;

  /// Minimum interactive target (accessibility).
  static const double minTapTarget = 48;

  /// Layout rhythm: inside a card, between cards, between sections.
  static const double cardPadding = lg;
  static const double cardGap = xl;
  static const double sectionGap = xxxl;

  /// Chip / segmented-control height (at least the 44 px touch minimum).
  static const double chipHeight = 44;

  static const SizedBox gapXs = SizedBox(height: xs, width: xs);
  static const SizedBox gapSm = SizedBox(height: sm, width: sm);
  static const SizedBox gapMd = SizedBox(height: md, width: md);
  static const SizedBox gapLg = SizedBox(height: lg, width: lg);
  static const SizedBox gapXl = SizedBox(height: xl, width: xl);
  static const SizedBox gapCard = SizedBox(height: cardGap, width: cardGap);
  static const SizedBox gapSection = SizedBox(
    height: sectionGap,
    width: sectionGap,
  );
}
