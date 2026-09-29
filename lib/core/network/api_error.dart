import 'package:dio/dio.dart';

import 'api_exception.dart';
import '../../features/auth/domain/auth_repository.dart';

/// Converts FastAPI's stable error envelope into a UI-safe failure kind.
ApiException mapDioException(DioException error) {
  if (error.error case AuthException(kind: AuthFailureKind.notConfigured)) {
    return const ApiException(
      kind: ApiErrorKind.server,
      code: 'firebase_not_configured',
    );
  }
  switch (error.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.receiveTimeout:
      return const ApiException(kind: ApiErrorKind.timeout);
    case DioExceptionType.connectionError:
    case DioExceptionType.badCertificate:
      return const ApiException(kind: ApiErrorKind.network);
    case DioExceptionType.cancel:
      return const ApiException(kind: ApiErrorKind.cancelled);
    // ignore: deprecated_member_use
    case DioExceptionType.transformTimeout:
      return const ApiException(kind: ApiErrorKind.timeout);
    case DioExceptionType.badResponse:
    case DioExceptionType.unknown:
      final int? status = error.response?.statusCode;
      final Object? body = error.response?.data;
      final Map<String, dynamic>? envelope = body is Map
          ? Map<String, dynamic>.from(body)
          : null;
      final Object? rawError = envelope?['error'];
      final Map<String, dynamic>? apiError = rawError is Map
          ? Map<String, dynamic>.from(rawError)
          : null;
      final String? code = apiError?['code'] as String?;
      final Object? details = apiError?['details'];
      final List<ApiFieldError> fields = <ApiFieldError>[];
      final Object? rawFields = details is Map ? details['fields'] : null;
      // Also accept FastAPI's native 422 detail list if middleware missed it.
      final Object? nativeFields = envelope?['detail'];
      for (final Object? item
          in rawFields is List
              ? rawFields
              : nativeFields is List
              ? nativeFields
              : const <Object>[]) {
        if (item is! Map) continue;
        final Object? location = item['loc'];
        fields.add(
          ApiFieldError(
            path: location is List ? location.join('.') : '$location',
            message: '${item['message'] ?? item['msg'] ?? 'Invalid value'}',
          ),
        );
      }
      final ApiErrorKind kind = switch (status) {
        401 => ApiErrorKind.unauthorized,
        403 => ApiErrorKind.forbidden,
        404 => ApiErrorKind.notFound,
        422 => ApiErrorKind.validation,
        429 => ApiErrorKind.rateLimited,
        final int value when value >= 500 => ApiErrorKind.server,
        _ => ApiErrorKind.unknown,
      };
      return ApiException(
        kind: kind,
        statusCode: status,
        code: code,
        fieldErrors: fields,
        retryAfterSeconds: int.tryParse(
          error.response?.headers.value('retry-after') ?? '',
        ),
      );
  }
}
