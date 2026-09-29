import 'package:flutter/material.dart';

import 'app_colors.dart';

/// Typography tokens.
///
/// Display / headline text uses the bundled serif (Cormorant Garamond) to match
/// the premium editorial tone of the reference screens; all UI text uses the
/// bundled geometric sans (Jost). Both faces cover the Turkish alphabet.
abstract final class AppTypography {
  static const String serif = 'CormorantGaramond';
  static const String sans = 'Jost';

  /// Smallest size any user-facing text may use (readability floor).
  static const double minFontSize = 12;

  /// Wide-tracked uppercase label, e.g. `DAHA BİLİNÇLİ • DAHA DENGELİ`.
  static const TextStyle overline = TextStyle(
    fontFamily: sans,
    fontSize: 12,
    height: 1.4,
    fontWeight: FontWeight.w500,
    letterSpacing: 1.6,
    color: AppColors.ivoryMuted,
  );

  static const TextStyle displayLarge = TextStyle(
    fontFamily: serif,
    fontSize: 40,
    height: 1.12,
    fontWeight: FontWeight.w600,
    color: AppColors.ivory,
  );

  static const TextStyle displayMedium = TextStyle(
    fontFamily: serif,
    fontSize: 32,
    height: 1.16,
    fontWeight: FontWeight.w600,
    color: AppColors.ivory,
  );

  static const TextStyle headlineLarge = TextStyle(
    fontFamily: serif,
    fontSize: 28,
    height: 1.2,
    fontWeight: FontWeight.w600,
    color: AppColors.ivory,
  );

  static const TextStyle headlineMedium = TextStyle(
    fontFamily: serif,
    fontSize: 24,
    height: 1.24,
    fontWeight: FontWeight.w600,
    color: AppColors.ivory,
  );

  static const TextStyle titleLarge = TextStyle(
    fontFamily: serif,
    fontSize: 20,
    height: 1.28,
    fontWeight: FontWeight.w600,
    color: AppColors.ivory,
  );

  static const TextStyle titleMedium = TextStyle(
    fontFamily: sans,
    fontSize: 16,
    height: 1.32,
    fontWeight: FontWeight.w500,
    color: AppColors.ivory,
  );

  static const TextStyle bodyLarge = TextStyle(
    fontFamily: sans,
    fontSize: 15,
    height: 1.5,
    fontWeight: FontWeight.w400,
    color: AppColors.ivory,
  );

  static const TextStyle bodyMedium = TextStyle(
    fontFamily: sans,
    fontSize: 14,
    height: 1.5,
    fontWeight: FontWeight.w400,
    color: AppColors.ivoryMuted,
  );

  static const TextStyle bodySmall = TextStyle(
    fontFamily: sans,
    fontSize: 13,
    height: 1.45,
    fontWeight: FontWeight.w400,
    color: AppColors.textSubtle,
  );

  static const TextStyle labelLarge = TextStyle(
    fontFamily: sans,
    fontSize: 15,
    height: 1.2,
    fontWeight: FontWeight.w500,
    letterSpacing: 0.2,
    color: AppColors.ivory,
  );

  static const TextStyle labelMedium = TextStyle(
    fontFamily: sans,
    fontSize: 13,
    height: 1.2,
    fontWeight: FontWeight.w500,
    letterSpacing: 0.4,
    color: AppColors.ivoryMuted,
  );

  static const TextStyle labelSmall = TextStyle(
    fontFamily: sans,
    fontSize: 12,
    height: 1.25,
    fontWeight: FontWeight.w500,
    letterSpacing: 0.6,
    color: AppColors.textSubtle,
  );

  /// Numeric display used by the frequency score.
  static const TextStyle score = TextStyle(
    fontFamily: serif,
    fontSize: 46,
    height: 1.0,
    fontWeight: FontWeight.w600,
    color: AppColors.goldBright,
  );

  static const TextTheme textTheme = TextTheme(
    displayLarge: displayLarge,
    displayMedium: displayMedium,
    displaySmall: headlineLarge,
    headlineLarge: headlineLarge,
    headlineMedium: headlineMedium,
    headlineSmall: titleLarge,
    titleLarge: titleLarge,
    titleMedium: titleMedium,
    titleSmall: labelLarge,
    bodyLarge: bodyLarge,
    bodyMedium: bodyMedium,
    bodySmall: bodySmall,
    labelLarge: labelLarge,
    labelMedium: labelMedium,
    labelSmall: labelSmall,
  );
}
