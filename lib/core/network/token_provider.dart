import 'package:dio/dio.dart';

import 'token_storage.dart';

/// The transport asks the active identity to renew itself. Only local JWT
/// identities use the backend refresh-token endpoint.
abstract interface class TokenProvider {
  Future<String?> getToken();
  Future<String?> refreshToken();
  Future<void> clear();
}

class LocalJwtTokenProvider implements TokenProvider {
  const LocalJwtTokenProvider(this.storage, this.refreshDio);
  final TokenStorage storage;
  final Dio refreshDio;
  @override
  Future<String?> getToken() => storage.readAccessToken();
  @override
  Future<String?> refreshToken() async {
    final String? refresh = await storage.readRefreshToken();
    if (refresh == null || refresh.isEmpty) return null;
    final Response<dynamic> response = await refreshDio.post<dynamic>(
      'auth/refresh',
      data: <String, String>{'refresh_token': refresh},
    );
    final Object? body = response.data;
    if (body is! Map ||
        body['access_token'] is! String ||
        body['refresh_token'] is! String) {
      return null;
    }
    final String access = body['access_token'] as String;
    if (access.isEmpty) return null;
    await storage.saveTokens(
      accessToken: access,
      refreshToken: body['refresh_token'] as String,
    );
    return access;
  }

  @override
  Future<void> clear() => storage.clearSession();
}

/// Restores legacy sessions in hybrid deployments; new Firebase sessions never
/// call the JWT refresh route. Selection is tied to stored legacy credentials.
class HybridTokenProvider implements TokenProvider {
  HybridTokenProvider(this.local, this.firebase, this.storage);
  final TokenProvider local;
  final TokenProvider firebase;
  final TokenStorage storage;
  Future<TokenProvider> _active() async =>
      await storage.readAccessToken() != null ||
          await storage.readRefreshToken() != null
      ? local
      : firebase;
  @override
  Future<String?> getToken() async => (await _active()).getToken();
  @override
  Future<String?> refreshToken() async => (await _active()).refreshToken();
  @override
  Future<void> clear() async {
    try {
      await firebase.clear();
    } finally {
      await local.clear();
    }
  }
}

class FirebaseIdTokenProvider implements TokenProvider {
  const FirebaseIdTokenProvider({
    required this.readIdToken,
    required this.signOut,
  });
  final Future<String?> Function(bool forceRefresh) readIdToken;
  final Future<void> Function() signOut;
  @override
  Future<String?> getToken() => readIdToken(false);
  @override
  Future<String?> refreshToken() => readIdToken(true);
  @override
  Future<void> clear() => signOut();
}
