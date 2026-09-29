import 'dart:io';

import 'package:astrofrekans/core/astrology/data/api_contract_dto.dart';
import 'package:astrofrekans/features/auth/data/auth_dto.dart';
import 'package:dio/dio.dart';

/// Manual only: dart run tool/api_smoke.dart
/// ASTRO_API_BASE_URL is required; ASTRO_EMAIL and ASTRO_PASSWORD enable auth.
/// ASTRO_REGISTER=1 explicitly opts into creating a disposable test account.
Future<void> main() => runApiSmoke(
  origin: Platform.environment['ASTRO_API_BASE_URL'],
  email: Platform.environment['ASTRO_EMAIL'],
  password: Platform.environment['ASTRO_PASSWORD'],
  register: Platform.environment['ASTRO_REGISTER'] == '1',
);

/// Also callable by the isolated live-validation test without passing secrets
/// through process arguments or environment variables.
Future<void> runApiSmoke({
  required String? origin,
  String? email,
  String? password,
  bool register = false,
  bool throwOnFailure = false,
}) async {
  if (origin == null || Uri.tryParse(origin)?.hasAuthority != true) {
    if (throwOnFailure) throw const FormatException('Missing local API URL.');
    stderr.writeln('Set ASTRO_API_BASE_URL to a running development backend.');
    exitCode = 2;
    return;
  }
  final Uri target = Uri.parse(origin);
  if (!<String>{'127.0.0.1', 'localhost', '::1'}.contains(target.host)) {
    if (throwOnFailure) throw const FormatException('Non-loopback API URL.');
    stderr.writeln('Smoke harness accepts only a loopback development API.');
    exitCode = 2;
    return;
  }
  final Dio dio = Dio(
    BaseOptions(
      baseUrl: '${origin.replaceFirst(RegExp(r'/+$'), '')}/',
      connectTimeout: const Duration(seconds: 5),
      receiveTimeout: const Duration(seconds: 30),
    ),
  );

  Future<Map<String, dynamic>> get(
    String path, [
    Map<String, dynamic>? query,
  ]) async {
    final Response<dynamic> response = await dio.get<dynamic>(
      path,
      queryParameters: query,
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  void ok(String label) => stdout.writeln('OK $label');

  try {
    final Map<String, dynamic> health = await get('health');
    if (health['environment'] != 'local') {
      throw const FormatException('Refusing non-local backend.');
    }
    ok('/health');
    await get('ready');
    ok('/ready');

    if (email == null || password == null) {
      stdout.writeln(
        'SKIP authenticated checks (ASTRO_EMAIL/PASSWORD absent).',
      );
      return;
    }
    final String authPath = register
        ? 'api/v1/auth/register'
        : 'api/v1/auth/login';
    final Map<String, dynamic> auth = Map<String, dynamic>.from(
      (await dio.post<dynamic>(
            authPath,
            data: <String, dynamic>{
              'email': email,
              'password': password,
              if (register)
                'name': Platform.environment['ASTRO_NAME'] ?? 'Smoke Test',
            },
          )).data
          as Map,
    );
    final AuthTokenDto tokens = AuthTokenDto.fromJson(auth);
    dio.options.headers['Authorization'] = 'Bearer ${tokens.accessToken}';
    ok(authPath);

    final Map<String, dynamic> birth = await get('api/v1/birth-profiles/me');
    BirthProfileDto.fromJson(birth).toDomain();
    ok('/birth-profiles/me');
    NatalChartDto.fromJson(
      await get('api/v1/astrology/natal-chart/me'),
    ).toDomain();
    ok('/astrology/natal-chart/me');
    TransitListDto.fromJson(await get('api/v1/astrology/transits')).toDomain();
    ok('/astrology/transits');
    DailyFrequencyDto.fromJson(
      await get('api/v1/astrology/daily-frequency'),
    ).toDomain();
    ok('/astrology/daily-frequency');
    CosmicCalendarDto.fromJson(await get('api/v1/calendar/events')).toDomain();
    ok('/calendar/events');
  } on DioException catch (error) {
    if (throwOnFailure) rethrow;
    stderr.writeln(
      'HTTP smoke failed: ${error.requestOptions.path} '
      '(${error.response?.statusCode ?? error.type.name}).',
    );
    exitCode = 1;
  } on Object catch (error) {
    if (throwOnFailure) rethrow;
    stderr.writeln('Contract smoke failed: ${error.runtimeType}.');
    exitCode = 1;
  } finally {
    dio.close();
  }
}
