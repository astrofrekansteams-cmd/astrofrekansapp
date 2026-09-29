import 'package:flutter/material.dart';

import '../../l10n/generated/app_localizations.dart';
import '../theme/app_spacing.dart';

extension AstroBuildContext on BuildContext {
  AppLocalizations get l10n => AppLocalizations.of(this);

  ThemeData get theme => Theme.of(this);

  TextTheme get texts => Theme.of(this).textTheme;

  String get languageCode => Localizations.localeOf(this).languageCode;

  Size get screenSize => MediaQuery.sizeOf(this);

  /// True when the user asked the platform to reduce motion, or when the
  /// widget tree disabled animations (widget tests do this).
  bool get reduceMotion =>
      MediaQuery.disableAnimationsOf(this) ||
      MediaQuery.maybeOf(this)?.disableAnimations == true;

  /// Horizontal page gutter for the current width.
  double get gutter => AppSpacing.pageGutter(MediaQuery.sizeOf(this).width);

  /// Compact phones (iPhone SE class) need tighter layouts.
  bool get isCompactHeight => MediaQuery.sizeOf(this).height < 700;

  bool get isNarrow => MediaQuery.sizeOf(this).width < 360;
}
