import 'package:dio/dio.dart';

import 'api_config.dart';
import 'api_error.dart';

class ApiHealthService {
  ApiHealthService({required AppEnvironment environment, Dio? dio})
    : _dio = dio ?? Dio(BaseOptions(baseUrl: environment.apiBaseUrl));

  final Dio _dio;

  Future<bool> isAlive() async {
    try {
      final Response<dynamic> response = await _dio.get<dynamic>('/health');
      return response.statusCode == 200;
    } on DioException catch (error) {
      throw mapDioException(error);
    }
  }

  Future<Map<String, dynamic>> readiness() async {
    try {
      final Response<dynamic> response = await _dio.get<dynamic>('/ready');
      return Map<String, dynamic>.from(response.data as Map);
    } on DioException catch (error) {
      throw mapDioException(error);
    }
  }
}
