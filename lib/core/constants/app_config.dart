/// Build-time configuration.
///
/// Nothing secret lives in the app binary. The AI/astrology backend is reached
/// through our own API; provider keys (OpenAI/Claude/ephemeris) stay server
/// side. Pass the base URL at build time:
///
/// ```
/// flutter build apk --dart-define=API_BASE_URL=https://api.astrofrekans.com
/// ```
abstract final class AppConfig {
  static const String appName = 'Astrofrekans';

  static const String apiBaseUrl = String.fromEnvironment('API_BASE_URL');

  static const Duration connectTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 30);

  /// When no backend is configured the app runs on mock services.
  /// Every mock surface must say so in the UI - never fake a live backend.
  static bool get useMocks => apiBaseUrl.isEmpty;
}
