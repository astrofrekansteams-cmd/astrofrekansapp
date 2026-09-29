import 'package:dio/dio.dart';

import 'token_storage.dart';
import 'token_provider.dart';

typedef SessionExpired = Future<void> Function();

/// Attaches bearer tokens and rotates them once for concurrent 401 responses.
class AuthInterceptor extends Interceptor {
  AuthInterceptor(
    this._dio,
    Dio refreshDio,
    TokenStorage tokenStorage,
    this._onSessionExpired, {
    TokenProvider? tokenProvider,
  }) : _tokens =
           tokenProvider ?? LocalJwtTokenProvider(tokenStorage, refreshDio);

  static const String skipAuthKey = 'skipAuth';
  static const String retriedKey = 'authRetried';

  final Dio _dio;
  final TokenProvider _tokens;
  final SessionExpired _onSessionExpired;
  Future<String?>? _refreshFuture;

  bool _isPublic(RequestOptions options) =>
      options.extra[skipAuthKey] == true ||
      options.uri.path.endsWith('/auth/login') ||
      options.uri.path.endsWith('/auth/register') ||
      options.uri.path.endsWith('/auth/capabilities') ||
      options.uri.path.endsWith('/auth/refresh') ||
      // Reset links answer 401 for an expired or used token; that is about
      // the link, not the session, and must never trigger a refresh/sign-out.
      options.uri.path.endsWith('/auth/forgot-password') ||
      options.uri.path.endsWith('/auth/reset-password') ||
      options.uri.path.endsWith('/auth/reset-password/check');

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    try {
      if (!_isPublic(options)) {
        final String? token = await _tokens.getToken();
        if (token != null && token.isNotEmpty) {
          options.headers['Authorization'] = 'Bearer $token';
        }
      }
      handler.next(options);
    } on Object catch (error) {
      handler.reject(DioException(requestOptions: options, error: error));
    }
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final RequestOptions request = err.requestOptions;
    if (err.response?.statusCode == 401 && request.extra[retriedKey] == true) {
      await _expireSession();
      handler.next(err);
      return;
    }
    if (err.response?.statusCode != 401 ||
        _isPublic(request) ||
        request.extra[retriedKey] == true) {
      handler.next(err);
      return;
    }

    try {
      final String? current = await _tokens.getToken();
      final String? bearer = request.headers['Authorization'] as String?;
      final String? token =
          current != null && current.isNotEmpty && bearer != 'Bearer $current'
          ? current
          : await _refreshOnce();
      if (token == null) {
        handler.next(err);
        return;
      }
      final RequestOptions retry = request.copyWith(
        headers: <String, dynamic>{
          ...request.headers,
          'Authorization': 'Bearer $token',
        },
        extra: <String, dynamic>{...request.extra, retriedKey: true},
      );
      handler.resolve(await _dio.fetch<dynamic>(retry));
    } on DioException catch (retryError) {
      handler.next(retryError);
    } on Object {
      handler.next(err);
    }
  }

  Future<String?> _refreshOnce() async {
    final Future<String?>? ongoing = _refreshFuture;
    if (ongoing != null) return ongoing;
    final Future<String?> started = _refresh();
    _refreshFuture = started;
    try {
      return await started;
    } finally {
      if (identical(_refreshFuture, started)) _refreshFuture = null;
    }
  }

  Future<String?> _refresh() async {
    try {
      final String? access = await _tokens.refreshToken();
      if (access == null || access.isEmpty) {
        await _expireSession();
        return null;
      }
      return access;
    } on Object {
      await _expireSession();
      return null;
    }
  }

  Future<void> _expireSession() async {
    await _tokens.clear();
    await _onSessionExpired();
  }
}
