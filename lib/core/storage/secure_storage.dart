import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Keys stored in the platform keystore/keychain.
abstract final class SecureKeys {
  static const String authToken = 'auth_token';
  static const String refreshToken = 'refresh_token';

  /// The cached profile contains birth data, which is personal - it never goes
  /// into shared_preferences.
  static const String userProfile = 'user_profile';
}

/// Secure key/value storage contract so features never talk to the plugin
/// directly (and so it can be faked in tests).
abstract interface class SecureStore {
  Future<String?> read(String key);

  Future<void> write(String key, String value);

  Future<void> delete(String key);

  Future<Map<String, dynamic>?> readJson(String key);

  Future<void> writeJson(String key, Map<String, dynamic> value);

  Future<void> clearSession();
}

mixin _JsonSecureStore implements SecureStore {
  @override
  Future<Map<String, dynamic>?> readJson(String key) async {
    final String? raw = await read(key);
    if (raw == null || raw.isEmpty) return null;
    final Object? decoded = jsonDecode(raw);
    return decoded is Map<String, dynamic> ? decoded : null;
  }

  @override
  Future<void> writeJson(String key, Map<String, dynamic> value) =>
      write(key, jsonEncode(value));

  @override
  Future<void> clearSession() async {
    await delete(SecureKeys.authToken);
    await delete(SecureKeys.refreshToken);
    await delete(SecureKeys.userProfile);
  }
}

/// Keystore (Android) / Keychain (iOS) backed implementation.
class PlatformSecureStore with _JsonSecureStore implements SecureStore {
  PlatformSecureStore([FlutterSecureStorage? storage])
    : _storage =
          storage ??
          const FlutterSecureStorage(
            // Defaults in v11 already use AES-GCM with RSA key wrapping.
            aOptions: AndroidOptions(),
            iOptions: IOSOptions(
              accessibility: KeychainAccessibility.first_unlock,
            ),
          );

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) =>
      _storage.write(key: key, value: value);

  @override
  Future<void> delete(String key) => _storage.delete(key: key);
}

/// In-memory implementation used by tests.
class InMemorySecureStore with _JsonSecureStore implements SecureStore {
  InMemorySecureStore([Map<String, String>? seed])
    : _values = <String, String>{...?seed};

  final Map<String, String> _values;

  @override
  Future<String?> read(String key) async => _values[key];

  @override
  Future<void> write(String key, String value) async => _values[key] = value;

  @override
  Future<void> delete(String key) async {
    _values.remove(key);
  }
}

final Provider<SecureStore> secureStoreProvider = Provider<SecureStore>(
  (Ref ref) => PlatformSecureStore(),
);
