import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/storage/app_preferences.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/features/auth/application/session_controller.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _TenRequestAdapter implements HttpClientAdapter {
  _TenRequestAdapter({required this.refreshSucceeds});

  final bool refreshSucceeds;
  final Completer<void> _allFirstAttempts = Completer<void>();
  int firstAttempts = 0;
  int retries = 0;
  int refreshes = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (options.uri.path.endsWith('/auth/refresh')) {
      refreshes++;
      await Future<void>.delayed(const Duration(milliseconds: 20));
      return _json(
        refreshSucceeds
            ? <String, String>{
                'access_token': 'new-access',
                'refresh_token': 'new-refresh',
              }
            : <String, Object>{
                'error': <String, String>{'code': 'token_reused'},
              },
        refreshSucceeds ? 200 : 401,
      );
    }
    final String? authorization = options.headers['Authorization'] as String?;
    if (authorization == 'Bearer new-access') {
      retries++;
      return _json(<String, bool>{'ok': true}, 200);
    }
    firstAttempts++;
    if (firstAttempts == 10) _allFirstAttempts.complete();
    await _allFirstAttempts.future;
    return _json(<String, Object>{
      'error': <String, String>{'code': 'token_expired'},
    }, 401);
  }

  ResponseBody _json(Object value, int status) => ResponseBody.fromString(
    jsonEncode(value),
    status,
    headers: <String, List<String>>{
      Headers.contentTypeHeader: <String>['application/json'],
    },
  );

  @override
  void close({bool force = false}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('default expiry callback invalidates the app session', () async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    final SharedPreferences preferences = await SharedPreferences.getInstance();
    final InMemorySecureStore store = InMemorySecureStore(<String, String>{
      SecureKeys.authToken: 'mock.test-user',
      SecureKeys.userProfile:
          '{"id":"test-user","name":"Defne","email":"defne@test.local",'
          '"language":"tr","subscription_tier":"free"}',
    });
    final ProviderContainer container = ProviderContainer(
      overrides: [
        secureStoreProvider.overrideWithValue(store),
        appPreferencesProvider.overrideWithValue(AppPreferences(preferences)),
      ],
    );
    addTearDown(container.dispose);

    await container.read(sessionProvider.notifier).bootstrap();
    expect(container.read(sessionProvider).status, SessionStatus.authenticated);

    await container.read(sessionExpiredCallbackProvider)();

    expect(
      container.read(sessionProvider).status,
      SessionStatus.unauthenticated,
    );
    expect(await store.read(SecureKeys.authToken), isNull);
  });

  for (final bool succeeds in <bool>[true, false]) {
    test('10 concurrent 401s share one refresh; success=$succeeds', () async {
      final InMemorySecureStore store = InMemorySecureStore(<String, String>{
        SecureKeys.authToken: 'old-access',
        SecureKeys.refreshToken: 'old-refresh',
      });
      final _TenRequestAdapter adapter = _TenRequestAdapter(
        refreshSucceeds: succeeds,
      );
      final Dio refreshDio = Dio(
        BaseOptions(
          baseUrl: 'http://example.test/api/v1/',
          headers: <String, String>{'Accept': 'application/json'},
        ),
      )..httpClientAdapter = adapter;
      int invalidations = 0;
      final Dio dio = buildDio(
        store: store,
        baseUrl: 'http://example.test',
        refreshDio: refreshDio,
        onSessionExpired: () async => invalidations++,
      )..httpClientAdapter = adapter;

      final List<Future<Response<dynamic>>> requests =
          <Future<Response<dynamic>>>[
            for (int i = 0; i < 10; i++) dio.get<dynamic>('protected/$i'),
          ];
      final List<Object> outcomes = await Future.wait<Object>(<Future<Object>>[
        for (final Future<Response<dynamic>> request in requests)
          request.then<Object>(
            (Response<dynamic> value) => value,
            onError: (Object error) => error,
          ),
      ]);

      expect(adapter.firstAttempts, 10);
      expect(adapter.refreshes, 1);
      if (succeeds) {
        expect(adapter.retries, 10);
        expect(outcomes.whereType<Response<dynamic>>().length, 10);
        expect(await store.read(SecureKeys.authToken), 'new-access');
        expect(await store.read(SecureKeys.refreshToken), 'new-refresh');
        expect(invalidations, 0);
      } else {
        expect(adapter.retries, 0);
        expect(outcomes.whereType<DioException>().length, 10);
        expect(await store.read(SecureKeys.authToken), isNull);
        expect(await store.read(SecureKeys.refreshToken), isNull);
        expect(invalidations, 1);
      }
    });
  }
}
