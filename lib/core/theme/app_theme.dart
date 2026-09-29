import 'package:flutter/cupertino.dart' show CupertinoPageTransitionsBuilder;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'app_colors.dart';
import 'app_radius.dart';
import 'app_spacing.dart';
import 'app_typography.dart';

/// The single [ThemeData] used by the app. Astrofrekans is a dark-only,
/// cosmic-premium product; a light theme would break the visual identity.
abstract final class AppTheme {
  static ThemeData get dark {
    const ColorScheme scheme = ColorScheme.dark(
      primary: AppColors.gold,
      onPrimary: AppColors.onGold,
      secondary: AppColors.goldBright,
      onSecondary: AppColors.onGold,
      surface: AppColors.surface,
      onSurface: AppColors.ivory,
      surfaceContainerHighest: AppColors.surfaceElevated,
      error: AppColors.danger,
      onError: AppColors.ivory,
      outline: AppColors.hairlineStrong,
      outlineVariant: AppColors.hairline,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: AppColors.night,
      canvasColor: AppColors.night,
      fontFamily: AppTypography.sans,
      textTheme: AppTypography.textTheme,
      splashFactory: InkSparkle.splashFactory,
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: AppTypography.titleLarge,
        iconTheme: IconThemeData(color: AppColors.ivory),
        systemOverlayStyle: SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.light,
          statusBarBrightness: Brightness.dark,
          systemNavigationBarColor: Colors.transparent,
          systemNavigationBarIconBrightness: Brightness.light,
        ),
      ),
      iconTheme: const IconThemeData(color: AppColors.ivoryMuted, size: 22),
      dividerTheme: const DividerThemeData(
        color: AppColors.hairline,
        thickness: 1,
        space: 1,
      ),
      pageTransitionsTheme: const PageTransitionsTheme(
        builders: <TargetPlatform, PageTransitionsBuilder>{
          // Keeps the Android 14+ predictive back gesture working.
          TargetPlatform.android: PredictiveBackPageTransitionsBuilder(),
          // Keeps the iOS interactive back swipe.
          TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
          TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
        },
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surfaceMuted.withValues(alpha: 0.72),
        hintStyle: AppTypography.bodyMedium.copyWith(
          color: AppColors.textSubtle,
        ),
        labelStyle: AppTypography.labelMedium,
        floatingLabelStyle: AppTypography.labelMedium.copyWith(
          color: AppColors.gold,
        ),
        errorStyle: AppTypography.bodySmall.copyWith(color: AppColors.danger),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.lg,
        ),
        border: const OutlineInputBorder(
          borderRadius: AppRadius.brMd,
          borderSide: BorderSide(color: AppColors.hairline),
        ),
        enabledBorder: const OutlineInputBorder(
          borderRadius: AppRadius.brMd,
          borderSide: BorderSide(color: AppColors.hairline),
        ),
        focusedBorder: const OutlineInputBorder(
          borderRadius: AppRadius.brMd,
          borderSide: BorderSide(color: AppColors.gold, width: 1.4),
        ),
        errorBorder: const OutlineInputBorder(
          borderRadius: AppRadius.brMd,
          borderSide: BorderSide(color: AppColors.danger),
        ),
        focusedErrorBorder: const OutlineInputBorder(
          borderRadius: AppRadius.brMd,
          borderSide: BorderSide(color: AppColors.danger, width: 1.4),
        ),
      ),
      textSelectionTheme: const TextSelectionThemeData(
        cursorColor: AppColors.gold,
        selectionColor: AppColors.hairlineStrong,
        selectionHandleColor: AppColors.gold,
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.surfaceElevated,
        surfaceTintColor: Colors.transparent,
        showDragHandle: true,
        dragHandleColor: AppColors.hairlineStrong,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(AppRadius.xl),
          ),
        ),
      ),
      dialogTheme: const DialogThemeData(
        backgroundColor: AppColors.surfaceElevated,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: AppTypography.titleLarge,
        contentTextStyle: AppTypography.bodyMedium,
        shape: RoundedRectangleBorder(borderRadius: AppRadius.brLg),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.surfaceElevated,
        contentTextStyle: AppTypography.bodyMedium.copyWith(
          color: AppColors.ivory,
        ),
        behavior: SnackBarBehavior.floating,
        shape: const RoundedRectangleBorder(borderRadius: AppRadius.brMd),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.gold,
        linearTrackColor: AppColors.surfaceMuted,
        circularTrackColor: Colors.transparent,
      ),
      checkboxTheme: CheckboxThemeData(
        side: const BorderSide(color: AppColors.hairlineStrong, width: 1.2),
        fillColor: WidgetStateProperty.resolveWith(
          (Set<WidgetState> states) => states.contains(WidgetState.selected)
              ? AppColors.gold
              : Colors.transparent,
        ),
        checkColor: const WidgetStatePropertyAll<Color>(AppColors.onGold),
        shape: const RoundedRectangleBorder(borderRadius: AppRadius.brXs),
      ),
      datePickerTheme: const DatePickerThemeData(
        backgroundColor: AppColors.surfaceElevated,
        surfaceTintColor: Colors.transparent,
        headerBackgroundColor: AppColors.navy,
        headerForegroundColor: AppColors.ivory,
      ),
      timePickerTheme: const TimePickerThemeData(
        backgroundColor: AppColors.surfaceElevated,
        dialBackgroundColor: AppColors.navy,
      ),
      tooltipTheme: const TooltipThemeData(
        decoration: BoxDecoration(
          color: AppColors.surfaceElevated,
          borderRadius: AppRadius.brXs,
        ),
        textStyle: AppTypography.bodySmall,
      ),
    );
  }

  /// System bar styling for full-bleed cosmic screens.
  static const SystemUiOverlayStyle overlayStyle = SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
    statusBarBrightness: Brightness.dark,
    systemNavigationBarColor: Colors.transparent,
    systemNavigationBarDividerColor: Colors.transparent,
    systemNavigationBarIconBrightness: Brightness.light,
  );
}
