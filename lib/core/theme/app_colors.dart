import 'package:flutter/material.dart';

/// Astrofrekans colour tokens.
///
/// The palette is sampled from the UI reference screens in
/// `assets/references/ui_screens`: deep navy / near-black grounds, champagne
/// gold accents and ivory text. No neon, no random gradients.
abstract final class AppColors {
  // Grounds
  static const Color night = Color(0xFF05070F);
  static const Color deepNavy = Color(0xFF0A0E1C);
  static const Color navy = Color(0xFF111730);
  static const Color navySoft = Color(0xFF18203C);

  // Surfaces
  static const Color surface = Color(0xFF090F1A);
  static const Color surfaceElevated = Color(0xFF141C2B);
  static const Color surfaceMuted = Color(0xFF1A2231);

  // Gold family
  static const Color gold = Color(0xFFD9B979);
  static const Color goldBright = Color(0xFFF0D7A0);
  static const Color goldWarm = Color(0xFFC79B58);
  static const Color goldDeep = Color(0xFF8E6C33);

  // Text
  static const Color ivory = Color(0xFFF4EEE3);
  static const Color ivoryMuted = Color(0xFFC9C3B8);
  static const Color textSubtle = Color(0xFF8F94A8);
  static const Color onGold = Color(0xFF14101F);

  // Accent (primary CTA in the reference is a pale ivory-lavender pill)
  static const Color ctaSurface = Color(0xFFEDE9F7);
  static const Color ctaLabel = Color(0xFF14101F);

  // Category accents for the daily frequency metrics
  static const Color love = Color(0xFFE38FA3);
  static const Color career = Color(0xFFE6B45F);
  static const Color money = Color(0xFF79C6A0);
  static const Color mood = Color(0xFF9B8CF0);
  static const Color energy = Color(0xFFF0C878);
  static const Color health = Color(0xFF6FC3D8);
  static const Color luck = Color(0xFFA9D07A);

  // Feedback
  static const Color success = Color(0xFF7FC8A0);
  static const Color warning = Color(0xFFE6B45F);
  static const Color danger = Color(0xFFE07A7A);

  // Hairlines & glows
  static const Color hairline = Color(0x33D9B979);
  static const Color hairlineStrong = Color(0x66D9B979);
  static const Color glow = Color(0x40D9B979);
  static const Color scrim = Color(0xB305070F);

  /// Vertical ground gradient used by [AstroBackground].
  static const LinearGradient nightGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: <Color>[deepNavy, night, Color(0xFF080B17)],
    stops: <double>[0.0, 0.55, 1.0],
  );

  /// Subtle gold sweep used on rings, dividers and progress bars.
  static const LinearGradient goldGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: <Color>[goldWarm, goldBright, gold],
  );

  /// Card fill: a barely-there lift from the ground, never a cheap glass blur.
  static const LinearGradient cardGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: <Color>[Color(0xE0121926), Color(0xEC040A12)],
  );

  static const LinearGradient glassGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: <Color>[Color(0x4DE9E3F5), Color(0x1A8F94A8)],
  );
}
