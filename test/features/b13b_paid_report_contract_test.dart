import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/features/astro_ai/data/api_astro_ai_repository.dart';
import 'package:astrofrekans/features/billing/application/paid_report_service.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('backend-owned paid report contract', () {
    for (final status in [200, 202]) {
      test(
        '$status response sends consumer_ref and parses report/job',
        () async {
          Map<String, dynamic>? sent;
          final dio =
              Dio(BaseOptions(baseUrl: 'https://api.example.test/api/v1/'))
                ..interceptors.add(
                  InterceptorsWrapper(
                    onRequest: (options, handler) {
                      expect(options.path, 'ai/reports');
                      sent = Map<String, dynamic>.from(options.data as Map);
                      handler.resolve(
                        Response<dynamic>(
                          requestOptions: options,
                          statusCode: status,
                          data: status == 200
                              ? {
                                  'id': 'report-1',
                                  'report_type': 'natal',
                                  'status': 'completed',
                                }
                              : {'id': 'job-1', 'status': 'queued'},
                        ),
                      );
                    },
                  ),
                );
          final repository = ApiAstroAIRepository(ApiClient(dio));
          final result = await repository.createReport(
            'natal',
            consumerRef: 'report-0123456789abcdef',
          );
          expect(
            result,
            status == 200 ? isA<PaidReportReady>() : isA<PaidReportQueued>(),
          );
          expect(sent?['consumer_ref'], 'report-0123456789abcdef');
          expect(sent?['background'], false);
          expect(sent?['report_type'], 'natal');
          dio.close();
        },
      );
    }

    for (final (status, code) in [
      (402, 'report_payment_required'),
      (409, 'report_credit_conflict'),
      (409, 'report_credit_unavailable'),
    ]) {
      test('$status $code remains a typed API error', () async {
        final dio =
            Dio(BaseOptions(baseUrl: 'https://api.example.test/api/v1/'))
              ..interceptors.add(
                InterceptorsWrapper(
                  onRequest: (options, handler) {
                    handler.reject(
                      DioException(
                        requestOptions: options,
                        type: DioExceptionType.badResponse,
                        response: Response<dynamic>(
                          requestOptions: options,
                          statusCode: status,
                          data: {
                            'error': {'code': code},
                          },
                        ),
                      ),
                    );
                  },
                ),
              );
        final repository = ApiAstroAIRepository(ApiClient(dio));
        await expectLater(
          repository.createReport(
            'natal',
            consumerRef: 'report-0123456789abcdef',
          ),
          throwsA(isA<ApiException>().having((e) => e.code, 'code', code)),
        );
        dio.close();
      });
    }
  });
}
