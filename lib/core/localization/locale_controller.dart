import 'dart:ui';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../storage/app_preferences.dart';

/// Supported locales. Turkish ships first; Azerbaijani is planned and only
/// needs an `app_az.arb` plus one entry here.
abstract final class AppLocales {
  static const Locale turkish = Locale('tr');
  static const Locale english = Locale('en');

  static const List<Locale> supported = <Locale>[turkish, english];
}

/// App locale, persisted in (non-sensitive) preferences.
class LocaleController extends Notifier<Locale> {
  @override
  Locale build() {
    final String? code = ref.read(appPreferencesProvider).localeCode;
    return _resolve(code);
  }

  Future<void> setLocale(Locale locale) async {
    if (state == locale) return;
    state = locale;
    await ref.read(appPreferencesProvider).setLocaleCode(locale.languageCode);
  }

  static Locale _resolve(String? code) {
    for (final Locale locale in AppLocales.supported) {
      if (locale.languageCode == code) return locale;
    }
    // Fall back to the device language when it is supported, else Turkish.
    final String deviceCode = PlatformDispatcher.instance.locale.languageCode;
    for (final Locale locale in AppLocales.supported) {
      if (locale.languageCode == deviceCode) return locale;
    }
    return AppLocales.turkish;
  }
}

final NotifierProvider<LocaleController, Locale> localeControllerProvider =
    NotifierProvider<LocaleController, Locale>(LocaleController.new);
