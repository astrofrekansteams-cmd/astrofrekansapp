import 'package:astrofrekans/core/network/api_error.dart';
import 'package:astrofrekans/features/auth/domain/auth_repository.dart';
import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('FastAPI validation fields are parsed without exposing raw body', () {
    final RequestOptions request = RequestOptions(path: '/auth/register');
    final DioException error = DioException(
      requestOptions: request,
      type: DioExceptionType.badResponse,
      response: Response<dynamic>(
        requestOptions: request,
        statusCode: 422,
        data: <String, dynamic>{
          'error': <String, dynamic>{
            'code': 'validation_error',
            'details': <String, dynamic>{
              'fields': <Map<String, dynamic>>[
                <String, dynamic>{
                  'loc': <String>['body', 'birth_date'],
                  'type': 'date_from_datetime_parsing',
                  'message': 'Invalid date',
                },
              ],
            },
          },
        },
      ),
    );
    final ApiException mapped = mapDioException(error);
    expect(mapped.kind, ApiErrorKind.validation);
    expect(mapped.code, 'validation_error');
    expect(mapped.fieldErrors.single.path, 'body.birth_date');
    expect(mapped.toString(), isNot(contains('Invalid date')));
  });

  test('403, 404 and 429 remain distinct', () {
    for (final (int status, ApiErrorKind kind) in <(int, ApiErrorKind)>[
      (403, ApiErrorKind.forbidden),
      (404, ApiErrorKind.notFound),
      (429, ApiErrorKind.rateLimited),
    ]) {
      final RequestOptions request = RequestOptions(path: '/test');
      final DioException error = DioException(
        requestOptions: request,
        type: DioExceptionType.badResponse,
        response: Response<dynamic>(
          requestOptions: request,
          statusCode: status,
        ),
      );
      expect(mapDioException(error).kind, kind);
    }
  });

  test('missing Firebase native configuration remains a clear API state', () {
    final error = DioException(
      requestOptions: RequestOptions(path: '/users/me'),
      error: const AuthException(AuthFailureKind.notConfigured),
    );
    final mapped = mapDioException(error);
    expect(mapped.code, 'firebase_not_configured');
    expect(mapped.toString(), isNot(contains('AuthException')));
  });
}
