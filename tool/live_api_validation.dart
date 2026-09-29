import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:astrofrekans/core/astrology/data/api_contract_dto.dart';
import 'package:astrofrekans/core/astrology/data/api_astrology_service.dart';
import 'package:astrofrekans/core/astrology/domain/birth_data.dart';
import 'package:astrofrekans/features/profile/domain/user_profile.dart';
import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/features/auth/data/api_auth_repository.dart';
import 'package:astrofrekans/features/auth/domain/auth_repository.dart';
import 'package:astrofrekans/features/auth/data/auth_dto.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'api_smoke.dart' as smoke;

/// Manual only: flutter test tool/live_api_validation.dart
/// Never put account credentials in source or CLI arguments.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'local live B1-B4 API validation',
    _runValidation,
    timeout: const Timeout(Duration(minutes: 15)),
  );
}

Future<void> _runValidation() async {
  // This manually invoked test is the only suite allowed to use real HTTP.
  // flutter_test installs a 400-response HttpClient override by default.
  HttpOverrides.global = null;
  final String origin =
      Platform.environment['ASTRO_API_BASE_URL'] ?? 'http://127.0.0.1:8000';
  final Uri target = Uri.parse(origin);
  if (!<String>{'127.0.0.1', 'localhost', '::1'}.contains(target.host)) {
    throw StateError('Refusing non-loopback API.');
  }

  final Dio probe = Dio(
    BaseOptions(
      baseUrl: '$origin/',
      connectTimeout: const Duration(seconds: 5),
    ),
  );
  final Response<dynamic> health;
  try {
    health = await probe.get<dynamic>('health');
    if (health.statusCode != 200 ||
        (health.data as Map)['environment'] != 'local') {
      throw const FormatException('Backend is not local development.');
    }
    await probe.get<dynamic>('ready');
  } on Object catch (error) {
    stderr.writeln('Local backend preflight failed: ${error.runtimeType}.');
    probe.close();
    rethrow;
  }
  probe.close();

  final Random random = Random.secure();
  String randomText(int count) => List<String>.generate(
    count,
    (_) => random.nextInt(16).toRadixString(16),
  ).join();
  final String email = 'codex-live-${randomText(12)}@example.com';
  final String password = '${randomText(24)}Aa9!';
  final InMemorySecureStore store = InMemorySecureStore();
  final Dio dio = buildDio(store: store, baseUrl: origin)
    ..options.receiveTimeout = const Duration(seconds: 90);
  final ApiClient api = ApiClient(dio);
  final ApiAuthRepository auth = ApiAuthRepository(api, store);
  final Map<String, Object?> captured = <String, Object?>{};
  final Map<String, double> latencyMs = <String, double>{};
  bool accountCreated = false;
  bool accountDeleted = false;
  bool registrationAttempted = false;

  Future<Map<String, dynamic>> fetch(
    String label,
    String path, {
    Map<String, dynamic>? query,
  }) async {
    final Stopwatch watch = Stopwatch()..start();
    final Map<String, dynamic> value = await api.getMap(
      path,
      queryParameters: query,
    );
    watch.stop();
    latencyMs[label] = watch.elapsedMicroseconds / 1000;
    stdout.writeln('OK $label ${latencyMs[label]!.toStringAsFixed(1)}ms');
    return value;
  }

  Future<void> negative(
    String label,
    Future<Object?> Function() request,
  ) async {
    try {
      await request();
      stdout.writeln('NEGATIVE $label unexpectedly succeeded');
    } on ApiException catch (error) {
      stdout.writeln(
        'NEGATIVE $label status=${error.statusCode} '
        'kind=${error.kind.name} code=${error.code ?? "none"}',
      );
    } on DioException catch (error) {
      stdout.writeln('NEGATIVE $label status=${error.response?.statusCode}');
    }
  }

  try {
    final Stopwatch registration = Stopwatch()..start();
    registrationAttempted = true;
    await auth.register(
      RegistrationRequest(
        name: 'Disposable Contract Test',
        email: email,
        password: password,
        birthDate: DateTime(1992, 5, 14),
        birthTime: '14:30',
      ),
    );
    accountCreated = true;
    registration.stop();
    stdout.writeln(
      'OK register ${registration.elapsedMilliseconds}ms '
      '(AuthTokenDto + ApiAuthRepository)',
    );

    await auth.signOut();
    stdout.writeln('OK logout');
    await auth.signIn(email: email, password: password);
    stdout.writeln('OK login (AuthTokenDto + ApiAuthRepository)');

    final Map<String, dynamic> user = await fetch('users_me', 'users/me');
    UserDto.fromJson(user).toDomain();

    // One real 401 -> refresh -> retry. The rotated secrets never leave memory.
    await store.write(SecureKeys.authToken, 'invalid-disposable-access');
    await fetch('refresh_retry', 'users/me');
    if (await store.read(SecureKeys.authToken) == 'invalid-disposable-access' ||
        await store.read(SecureKeys.refreshToken) == null) {
      throw StateError('Real refresh/retry did not rotate credentials.');
    }
    stdout.writeln('OK real refresh/retry (no token output)');

    final Map<String, dynamic> birth = await api.putMap(
      'birth-profiles/me',
      data: <String, dynamic>{
        'birth_date': '1992-05-14',
        'birth_time': '14:30:00',
        'birth_place': 'Istanbul',
        'latitude': 41.0082,
        'longitude': 28.9784,
        'timezone': 'Europe/Istanbul',
        'house_system': 'placidus',
      },
    );
    BirthProfileDto.fromJson(birth).toDomain();
    captured['birth_profile'] = await fetch(
      'birth_profile',
      'birth-profiles/me',
    );
    BirthProfileDto.fromJson(
      captured['birth_profile']! as Map<String, dynamic>,
    ).toDomain();

    final Map<String, dynamic> natal = await fetch(
      'natal',
      'astrology/natal-chart/me',
    );
    final chart = NatalChartDto.fromJson(natal).toDomain();
    captured['natal_chart'] = natal;
    stdout.writeln(
      'NATAL planets=${chart.planets.length} '
      'houses=${chart.houses.length} aspects=${chart.aspects.length} '
      'warnings=${chart.warnings.length} rulers=${chart.houseRulers.length} '
      'angles=${natal['angles'] == null ? 0 : 1}',
    );

    final Map<String, dynamic> moon = await fetch(
      'moon_phase',
      'astrology/moon-phase',
    );
    MoonPhaseDto.fromJson(moon).toDomain();
    captured['moon_phase'] = moon;

    for (final String range in <String>['day', 'week', 'month']) {
      final Map<String, dynamic> response = await fetch(
        'transits_$range',
        'astrology/transits',
        query: <String, dynamic>{'range': range},
      );
      final window = TransitListDto.fromJson(response).toWindow();
      captured['transits_$range'] = response;
      final int nullDates = window.all
          .where(
            (t) => t.exactAt == null || t.startAt == null || t.endAt == null,
          )
          .length;
      stdout.writeln(
        'TRANSITS $range count=${window.all.length} '
        'ingresses=${window.ingresses.length} '
        'passes=${window.all.fold<int>(0, (n, t) => n + t.passes.length)} '
        'nullDates=$nullDates',
      );
    }

    final Map<String, dynamic> daily = await fetch(
      'daily_frequency',
      'astrology/daily-frequency',
    );
    final frequency = DailyFrequencyDto.fromJson(daily).toDomain();
    captured['daily_frequency'] = daily;
    stdout.writeln(
      'DAILY scores=${frequency.scores.length} '
      'hours=${frequency.importantHours.length} '
      'factors=${frequency.influences.length}',
    );

    final DateTime now = DateTime.now();
    String day(DateTime date) =>
        '${date.year.toString().padLeft(4, '0')}-'
        '${date.month.toString().padLeft(2, '0')}-'
        '${date.day.toString().padLeft(2, '0')}';
    final Map<String, dynamic> calendar = await fetch(
      'calendar',
      'calendar/events',
      query: <String, dynamic>{
        'start': day(now),
        'end': day(now.add(const Duration(days: 31))),
      },
    );
    final events = CosmicCalendarDto.fromJson(calendar).toWindow();
    captured['calendar'] = calendar;
    stdout.writeln(
      'CALENDAR events=${events.events.length} '
      'types=${events.events.map((e) => e.rawType).toSet().join(",")}',
    );

    for (final (String key, String path) in <(String, String)>[
      ('daily_horoscope', 'horoscope/daily'),
      ('weekly_horoscope', 'horoscope/weekly'),
      ('monthly_forecast', 'forecasts/monthly'),
      ('annual_forecast', 'forecasts/yearly'),
    ]) {
      try {
        final Map<String, dynamic> response = await fetch(key, path);
        final ForecastDto dto = switch (key) {
          'monthly_forecast' => ForecastDto.monthly(response),
          'annual_forecast' => ForecastDto.annual(response),
          _ => ForecastDto.daily(response),
        };
        switch (key) {
          case 'monthly_forecast':
            dto.toMonthly();
          case 'annual_forecast':
            dto.toAnnual();
          default:
            dto.toHoroscope();
        }
        captured[key] = response;
        stdout.writeln('FORECAST $key parsed');
      } on Object catch (error) {
        stdout.writeln('FORECAST $key FAILED ${error.runtimeType}');
      }
    }

    final Map<String, dynamic> person = await api.postMap(
      'saved-people',
      data: <String, dynamic>{
        'name': 'Disposable Friend',
        'relation': 'friend',
        'birth_date': '1991-04-10',
        'birth_time': null,
        'birth_place': 'Istanbul',
        'latitude': 41.0082,
        'longitude': 28.9784,
        'timezone': 'Europe/Istanbul',
        'house_system': 'placidus',
      },
    );
    final saved = SavedPersonDto.fromJson(person).toDomain();
    captured['saved_person'] = person;
    final Response<dynamic> people = await dio.get<dynamic>('saved-people');
    final List<Map<String, dynamic>> list = (people.data as List<dynamic>)
        .map((dynamic item) => Map<String, dynamic>.from(item as Map))
        .toList();
    for (final Map<String, dynamic> item in list) {
      SavedPersonDto.fromJson(item).toDomain();
    }
    stdout.writeln('SAVED create/list parsed count=${list.length}');
    await dio.delete<dynamic>('saved-people/${saved.id}');
    stdout.writeln('SAVED delete OK; GET by id/update unsupported by schema');

    final ApiAstrologyService service = ApiAstrologyService(api);
    final UserProfile profile =
        await auth.restoreSession() ??
        (throw StateError('Live session did not restore.'));
    final BirthData birthData =
        profile.birthData ??
        (throw StateError('Live profile did not expose birth data.'));
    final serviceChart = await service.getNatalChart(birthData);
    final DateTime serviceNow = DateTime.now();
    final serviceTransits = await service.getTransits(
      natalChart: serviceChart,
      from: serviceNow,
      to: serviceNow.add(const Duration(days: 7)),
    );
    final serviceDaily = await service.getDailyFrequency(
      profile: profile,
      date: serviceNow,
    );
    final serviceMoon = await service.getMoonPhase(date: serviceNow);
    final serviceCalendar = await service.getCosmicCalendar(
      from: serviceNow,
      to: serviceNow.add(const Duration(days: 31)),
    );
    stdout.writeln(
      'API_ASTROLOGY_SERVICE natal=${serviceChart.planets.length} '
      'transits=${serviceTransits.length} '
      'scores=${serviceDaily.scores.length} '
      'moon=${serviceMoon.type.name} '
      'events=${serviceCalendar.length}',
    );

    await negative(
      'invalid_login',
      () => api.postMap(
        'auth/login',
        data: <String, dynamic>{'email': email, 'password': 'Wrong-Pass-1'},
      ),
    );
    await negative(
      'invalid_range',
      () => api.getMap(
        'astrology/transits',
        queryParameters: <String, dynamic>{'range': 'invalid'},
      ),
    );
    final ApiClient anonymous = ApiClient(
      Dio(BaseOptions(baseUrl: '$origin/api/v1/')),
    );
    await negative('unauthorized', () => anonymous.getMap('users/me'));
    await negative('not_found', () => api.getMap('not-a-real-resource'));

    await smoke.runApiSmoke(
      origin: origin,
      email: email,
      password: password,
      throwOnFailure: true,
    );
    stdout.writeln('SMOKE_HARNESS passed');

    final Map<String, String> uuidReplacements = <String, String>{};
    final RegExp uuid = RegExp(r'^[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}$');
    Object? sanitize(Object? value) {
      if (value is Map) {
        final Map<String, Object?> result = <String, Object?>{};
        for (final MapEntry<dynamic, dynamic> entry in value.entries) {
          final String key = entry.key.toString();
          if (<String>{
            'access_token',
            'refresh_token',
            'password',
            'email',
            'authorization',
            'secret',
          }.contains(key.toLowerCase())) {
            continue;
          }
          result[key] = sanitize(entry.value);
        }
        return result;
      }
      if (value is List) return value.map(sanitize).toList();
      if (value is String && uuid.hasMatch(value)) {
        return uuidReplacements.putIfAbsent(
          value,
          () =>
              '00000000-0000-4000-8000-'
              '${(uuidReplacements.length + 1).toString().padLeft(12, '0')}',
        );
      }
      if (value is String &&
          (RegExp(r'^[A-Za-z]:\\').hasMatch(value) ||
              value.startsWith('/home/'))) {
        return '[redacted-path]';
      }
      return value;
    }

    final Map<String, Object?> fixture = <String, Object?>{
      'source': 'local_live_backend',
      'captured_at': DateTime.now().toUtc().toIso8601String(),
      'engine_version': chart.engineVersion,
      'sanitized': true,
      ...captured,
    };
    final String encoded = const JsonEncoder.withIndent(
      '  ',
    ).convert(sanitize(fixture));
    if (RegExp(
          r'access_token|refresh_token|password|authorization|codex-live-',
          caseSensitive: false,
        ).hasMatch(encoded) ||
        encoded.contains('C:\\Users\\')) {
      throw StateError('Sanitized fixture failed sensitive-data gate.');
    }
    await File(
      'test/fixtures/live_b1_b4_contract_samples.json',
    ).writeAsString('$encoded\n');
    stdout.writeln(
      'CAPTURE sanitized=true sections=${captured.length} '
      'bytes=${encoded.length}',
    );
  } on Object catch (error) {
    stderr.writeln('VALIDATION FAILED ${error.runtimeType}');
    rethrow;
  } finally {
    if (registrationAttempted && !accountCreated) {
      try {
        await auth.signIn(email: email, password: password);
        accountCreated = true;
      } on Object {
        // Registration may have failed before the backend created an account.
      }
    }
    bool cleanupFailed = false;
    if (accountCreated) {
      try {
        if (await store.read(SecureKeys.authToken) == null) {
          await auth.signIn(email: email, password: password);
        }
        await dio.delete<dynamic>('users/me');
        accountDeleted = true;
      } on Object catch (error) {
        stderr.writeln('DISPOSABLE USER CLEANUP FAILED ${error.runtimeType}');
        cleanupFailed = true;
      }
    }
    stdout.writeln('DISPOSABLE_USER_DELETED=$accountDeleted');
    dio.close();
    if (cleanupFailed) throw StateError('Disposable user cleanup failed.');
  }
}
