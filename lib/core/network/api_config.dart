import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

enum AppEnvironmentName { development, staging, production }

enum AppDataSource { mock, api }

enum AuthMode { localJwt, firebase, hybrid }

@immutable
class AppEnvironment {
  const AppEnvironment({
    required this.environment,
    required this.apiBaseUrl,
    required this.dataSource,
    required this.enableDebugTools,
    this.authMode = AuthMode.localJwt,
    this.enableAppleSignIn = false,
  });

  final AppEnvironmentName environment;
  final String apiBaseUrl;
  final AppDataSource dataSource;
  final bool enableDebugTools;
  final AuthMode authMode;

  /// `ENABLE_APPLE_SIGN_IN`: production release switch for Sign in with Apple.
  final bool enableAppleSignIn;

  bool get useMocks => dataSource == AppDataSource.mock;

  bool get isProduction => environment == AppEnvironmentName.production;

  /// Google sign-in is off for the first production release: the button is
  /// not shown at all (no "coming soon"). The integration seam stays
  /// (`SocialAuthService`); development and staging still show it.
  bool get googleSignInEnabled => !isProduction;

  /// Sign in with Apple stays wired (entitlement, `SocialAuthService`), but a
  /// production build shows it only when switched on with
  /// `--dart-define=ENABLE_APPLE_SIGN_IN=true` - after the Apple provider is
  /// enabled in the production Firebase project, the App ID has the
  /// capability, and account deletion revokes Apple tokens (App Store
  /// 5.1.1(v)). Development and staging keep it.
  bool get appleSignInEnabled => !isProduction || enableAppleSignIn;

  /// API mode must be explicit, including its origin. This prevents a release
  /// binary from silently pointing at a developer machine.
  void validate() {
    if (useMocks &&
        (environment == AppEnvironmentName.production || kReleaseMode)) {
      throw StateError('Release builds cannot use APP_DATA_SOURCE=mock.');
    }
    if (dataSource == AppDataSource.api &&
        (apiBaseUrl.isEmpty ||
            Uri.tryParse(apiBaseUrl)?.hasAuthority != true)) {
      throw StateError('API_BASE_URL must be an absolute URL in API mode.');
    }
    if (environment == AppEnvironmentName.production &&
        dataSource == AppDataSource.api &&
        Uri.parse(apiBaseUrl).scheme != 'https') {
      throw StateError('Production API_BASE_URL must use HTTPS.');
    }
    final Uri? uri = Uri.tryParse(apiBaseUrl);
    if (environment == AppEnvironmentName.production &&
        !useMocks &&
        isLocalHost(uri!.host)) {
      throw StateError(
        'Production API_BASE_URL cannot use a local or private address.',
      );
    }
    if (environment == AppEnvironmentName.production && enableDebugTools) {
      throw StateError('Production builds cannot enable ENABLE_DEBUG_TOOLS.');
    }
    // Release decision: production serves Firebase accounts and server
    // (local JWT) accounts alike.
    if (environment == AppEnvironmentName.production &&
        authMode != AuthMode.hybrid) {
      throw StateError('Production AUTH_MODE must be hybrid.');
    }
  }

  /// Reachable only from a developer's machine or LAN: loopback, the
  /// Android emulator's host alias (10.0.2.2, Genymotion 10.0.3.2), private
  /// and link-local ranges, and reserved local names.
  static bool isLocalHost(String rawHost) {
    String host = rawHost.toLowerCase();
    if (host.startsWith('[') && host.endsWith(']')) {
      host = host.substring(1, host.length - 1);
    }
    if (host.isEmpty) return false;
    if (host == 'localhost' ||
        host == '0.0.0.0' ||
        host == 'host.docker.internal' ||
        host.endsWith('.localhost') ||
        host.endsWith('.local') ||
        host.endsWith('.test') ||
        host.endsWith('.internal')) {
      return true;
    }
    if (host.contains(':')) {
      // IPv6: loopback, link-local (fe80::/10), unique-local (fc00::/7).
      return host == '::1' ||
          host == '::' ||
          host.startsWith('fe8') ||
          host.startsWith('fe9') ||
          host.startsWith('fea') ||
          host.startsWith('feb') ||
          host.startsWith('fc') ||
          host.startsWith('fd');
    }
    final List<int>? ip = _ipv4(host);
    if (ip == null) return false;
    return ip[0] == 127 ||
        ip[0] == 10 ||
        (ip[0] == 172 && ip[1] >= 16 && ip[1] <= 31) ||
        (ip[0] == 192 && ip[1] == 168) ||
        (ip[0] == 169 && ip[1] == 254) ||
        ip.every((part) => part == 0);
  }

  static List<int>? _ipv4(String host) {
    final List<String> parts = host.split('.');
    if (parts.length != 4) return null;
    final List<int> numbers = <int>[];
    for (final String part in parts) {
      final int? value = int.tryParse(part);
      if (value == null || value < 0 || value > 255) return null;
      numbers.add(value);
    }
    return numbers;
  }

  static AppEnvironment fromDefines() {
    const String environmentName = String.fromEnvironment(
      'APP_ENVIRONMENT',
      defaultValue: 'development',
    );
    const String sourceName = String.fromEnvironment(
      'APP_DATA_SOURCE',
      defaultValue: 'mock',
    );
    const String baseUrl = String.fromEnvironment('API_BASE_URL');
    const bool debugTools = bool.fromEnvironment(
      'ENABLE_DEBUG_TOOLS',
      defaultValue: false,
    );
    const bool appleSignIn = bool.fromEnvironment(
      'ENABLE_APPLE_SIGN_IN',
      defaultValue: false,
    );
    return parse(
      environment: environmentName,
      dataSource: sourceName,
      apiBaseUrl: baseUrl,
      enableDebugTools: debugTools,
      enableAppleSignIn: appleSignIn,
      authMode: const String.fromEnvironment(
        'AUTH_MODE',
        defaultValue: 'local_jwt',
      ),
    );
  }

  static AppEnvironment parse({
    required String environment,
    required String dataSource,
    required String apiBaseUrl,
    bool enableDebugTools = false,
    String authMode = 'local_jwt',
    bool enableAppleSignIn = false,
  }) {
    final AppEnvironmentName? parsedEnvironment = AppEnvironmentName.values
        .where((value) => value.name == environment)
        .firstOrNull;
    final AppDataSource? parsedSource = AppDataSource.values
        .where((value) => value.name == dataSource)
        .firstOrNull;
    if (parsedEnvironment == null || parsedSource == null) {
      throw const FormatException(
        'Invalid APP_ENVIRONMENT or APP_DATA_SOURCE value.',
      );
    }
    final AppEnvironment config = AppEnvironment(
      environment: parsedEnvironment,
      apiBaseUrl: apiBaseUrl,
      dataSource: parsedSource,
      enableDebugTools: enableDebugTools,
      enableAppleSignIn: enableAppleSignIn,
      authMode: switch (authMode) {
        'local_jwt' => AuthMode.localJwt,
        'firebase' => AuthMode.firebase,
        'hybrid' => AuthMode.hybrid,
        _ => throw const FormatException('Invalid AUTH_MODE'),
      },
    );
    config.validate();
    return config;
  }
}

final Provider<AppEnvironment> appEnvironmentProvider =
    Provider<AppEnvironment>((Ref ref) => AppEnvironment.fromDefines());

/// Presentation may show a demo badge, but never switches repositories.
final Provider<bool> showDemoNoticeProvider = Provider<bool>(
  (Ref ref) => ref.watch(appEnvironmentProvider).useMocks,
);
