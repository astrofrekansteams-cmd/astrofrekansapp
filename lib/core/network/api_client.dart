import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/auth/application/session_controller.dart';
import '../constants/app_config.dart';
import '../storage/secure_storage.dart';
import 'api_config.dart';
import 'api_error.dart';
import 'api_exception.dart';
import 'auth_interceptor.dart';
import 'request_id_interceptor.dart';
import 'token_storage.dart';
import 'token_provider.dart';
import '../config/firebase_client.dart';

/// [baseUrl] is the API origin, excluding `/api/v1`.
Dio buildDio({
  required SecureStore store,
  String? baseUrl,
  SessionExpired? onSessionExpired,
  Dio? refreshDio,
  TokenProvider? tokenProvider,
}) {
  final String origin = baseUrl ?? AppConfig.apiBaseUrl;
  final String apiUrl = '${origin.replaceFirst(RegExp(r'/+$'), '')}/api/v1/';
  final BaseOptions options = BaseOptions(
    baseUrl: apiUrl,
    connectTimeout: AppConfig.connectTimeout,
    receiveTimeout: AppConfig.receiveTimeout,
    responseType: ResponseType.json,
    headers: <String, String>{'Accept': 'application/json'},
  );
  final Dio dio = Dio(options);
  final Dio refresh = refreshDio ?? Dio(options);
  dio.interceptors.add(RequestIdInterceptor());
  dio.interceptors.add(
    AuthInterceptor(
      dio,
      refresh,
      SecureTokenStorage(store),
      onSessionExpired ?? () async {},
      tokenProvider: tokenProvider,
    ),
  );
  return dio;
}

/// A failed refresh clears transport tokens, then invalidates the app session.
final Provider<SessionExpired> sessionExpiredCallbackProvider =
    Provider<SessionExpired>(
      (Ref ref) =>
          () => ref.read(sessionProvider.notifier).invalidate(),
    );

final Provider<Dio> dioProvider = Provider<Dio>((Ref ref) {
  final AppEnvironment environment = ref.watch(appEnvironmentProvider);
  final store = ref.watch(secureStoreProvider);
  final firebase = ref.watch(firebaseClientProvider);
  final firebaseTokens = FirebaseIdTokenProvider(
    readIdToken: firebase.token,
    signOut: () async {
      try {
        await firebase.signOut();
      } finally {
        await store.clearSession();
      }
    },
  );
  final refresh = Dio(
    BaseOptions(
      baseUrl:
          '${environment.apiBaseUrl.replaceFirst(RegExp(r'/+$'), '')}/api/v1/',
      connectTimeout: AppConfig.connectTimeout,
      receiveTimeout: AppConfig.receiveTimeout,
    ),
  );
  ref.onDispose(() => refresh.close(force: true));
  return buildDio(
    store: ref.watch(secureStoreProvider),
    baseUrl: environment.apiBaseUrl,
    onSessionExpired: ref.watch(sessionExpiredCallbackProvider),
    refreshDio: refresh,
    tokenProvider: switch (environment.authMode) {
      AuthMode.localJwt => null,
      AuthMode.firebase => firebaseTokens,
      AuthMode.hybrid => HybridTokenProvider(
        LocalJwtTokenProvider(SecureTokenStorage(store), refresh),
        firebaseTokens,
        SecureTokenStorage(store),
      ),
    },
  );
});

/// JSON transport; DTO conversion belongs to each feature's data layer.
class ApiClient {
  const ApiClient(this._dio);

  final Dio _dio;

  Dio get transport => _dio;

  Future<List<Map<String, dynamic>>> getList(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) async {
    try {
      final response = await _dio.get<dynamic>(
        path,
        queryParameters: queryParameters,
      );
      if (response.data is! List) {
        throw const ApiException(kind: ApiErrorKind.unknown);
      }
      return (response.data as List).map(_asMap).toList(growable: false);
    } on DioException catch (error) {
      throw mapDioException(error);
    }
  }

  Future<void> delete(String path) async {
    try {
      await _dio.delete<dynamic>(path);
    } on DioException catch (error) {
      throw mapDioException(error);
    }
  }

  Future<Map<String, dynamic>> deleteMap(String path) async {
    try {
      final response = await _dio.delete<dynamic>(path);
      return _asMap(response.data);
    } on DioException catch (error) {
      throw mapDioException(error);
    }
  }

  Future<Map<String, dynamic>> getMap(
    String path, {
    Map<String, dynamic>? queryParameters,
    Map<String, String>? headers,
  }) async {
    try {
      final Response<dynamic> response = await _dio.get<dynamic>(
        path,
        queryParameters: queryParameters,
        options: headers == null ? null : Options(headers: headers),
      );
      return _asMap(response.data);
    } on DioException catch (error) {
      throw mapDioException(error);
    }
  }

  Future<Map<String, dynamic>> postMap(
    String path, {
    Map<String, dynamic>? data,
    Map<String, String>? headers,
  }) async {
    try {
      final Response<dynamic> response = await _dio.post<dynamic>(
        path,
        data: data,
        options: headers == null ? null : Options(headers: headers),
      );
      return _asMap(response.data);
    } on DioException catch (error) {
      throw mapDioException(error);
    }
  }

  Future<Map<String, dynamic>> patchMap(
    String path, {
    Map<String, dynamic>? data,
  }) async {
    try {
      final Response<dynamic> response = await _dio.patch<dynamic>(
        path,
        data: data,
      );
      return _asMap(response.data);
    } on DioException catch (error) {
      throw mapDioException(error);
    }
  }

  Future<Map<String, dynamic>> putMap(
    String path, {
    Map<String, dynamic>? data,
  }) async {
    try {
      final Response<dynamic> response = await _dio.put<dynamic>(
        path,
        data: data,
      );
      return _asMap(response.data);
    } on DioException catch (error) {
      throw mapDioException(error);
    }
  }

  Future<List<Map<String, dynamic>>> putList(
    String path, {
    Map<String, dynamic>? data,
  }) async {
    try {
      final response = await _dio.put<dynamic>(path, data: data);
      if (response.data is! List) {
        throw const ApiException(kind: ApiErrorKind.unknown);
      }
      return (response.data as List).map(_asMap).toList(growable: false);
    } on DioException catch (error) {
      throw mapDioException(error);
    }
  }

  static Map<String, dynamic> _asMap(Object? value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) return Map<String, dynamic>.from(value);
    throw const ApiException(kind: ApiErrorKind.unknown);
  }
}

/// The header that pays for one use of a plan-gated route with AstroCoins.
/// The same reference is never charged twice.
Map<String, String>? coinHeader(String? coinRef) =>
    coinRef == null ? null : {'X-Coin-Consumer-Ref': coinRef};
