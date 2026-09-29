import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Non-sensitive preferences only. Personal/birth data belongs in
/// [SecureStore].
class AppPreferences {
  AppPreferences(this._prefs);

  final SharedPreferences _prefs;

  static const String _kOnboardingSeen = 'onboarding_seen';
  static const String _kLocale = 'locale_code';
  static const String _kCoinUnlocks = 'coin_unlocks';

  bool get onboardingSeen => _prefs.getBool(_kOnboardingSeen) ?? false;

  Future<void> setOnboardingSeen({required bool value}) =>
      _prefs.setBool(_kOnboardingSeen, value);

  String? get localeCode => _prefs.getString(_kLocale);

  Future<void> setLocaleCode(String? code) async {
    if (code == null) {
      await _prefs.remove(_kLocale);
      return;
    }
    await _prefs.setString(_kLocale, code);
  }

  /// Content opened with AstroCoins, per account: `{content key: reference}`.
  /// The references are not secrets - only the account can redeem them.
  String? coinUnlocks(String userId) =>
      _prefs.getString('$_kCoinUnlocks:$userId');

  Future<void> setCoinUnlocks(String userId, String json) =>
      _prefs.setString('$_kCoinUnlocks:$userId', json);
}

/// Overridden in `main()` (and in tests) with a resolved instance.
final Provider<AppPreferences> appPreferencesProvider =
    Provider<AppPreferences>(
      (Ref ref) => throw UnimplementedError(
        'appPreferencesProvider must be overridden in ProviderScope',
      ),
    );
