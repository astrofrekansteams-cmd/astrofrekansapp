import '../storage/secure_storage.dart';

abstract interface class TokenStorage {
  Future<String?> readAccessToken();
  Future<String?> readRefreshToken();
  Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  });
  Future<void> clearSession();
}

class SecureTokenStorage implements TokenStorage {
  const SecureTokenStorage(this._store);

  final SecureStore _store;

  @override
  Future<String?> readAccessToken() => _store.read(SecureKeys.authToken);

  @override
  Future<String?> readRefreshToken() => _store.read(SecureKeys.refreshToken);

  @override
  Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _store.write(SecureKeys.refreshToken, refreshToken);
    await _store.write(SecureKeys.authToken, accessToken);
  }

  @override
  Future<void> clearSession() => _store.clearSession();
}
