import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/network/api_config.dart';
import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/core/network/token_provider.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/features/astro_ai/data/api_astro_ai_repository.dart';
import 'package:astrofrekans/features/astro_ai/domain/astro_ai_repository.dart';

class HandlerAdapter implements HttpClientAdapter {
  HandlerAdapter(this.handler);
  final Future<ResponseBody> Function(RequestOptions, Future<void>?) handler;
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? request,
    Future<void>? cancel,
  ) => handler(options, cancel);
  @override
  void close({bool force = false}) {}
}

ResponseBody body(Object value, int status) => ResponseBody.fromString(
  jsonEncode(value),
  status,
  headers: {
    'content-type': ['application/json'],
  },
);

void main() {
  test(
    'production refuses HTTP and HTTPS loopback and rejects bad auth mode',
    () {
      for (final url in [
        'http://api.example.com',
        'https://localhost',
        'https://127.0.0.1',
        'https://[::1]',
      ]) {
        expect(
          () => AppEnvironment.parse(
            environment: 'production',
            authMode: 'hybrid',
            dataSource: 'api',
            apiBaseUrl: url,
          ),
          throwsStateError,
        );
      }
      expect(
        () => AppEnvironment.parse(
          environment: 'development',
          dataSource: 'mock',
          apiBaseUrl: '',
          authMode: 'invalid',
        ),
        throwsFormatException,
      );
    },
  );
  for (final success in [true, false]) {
    test(
      '10 Firebase 401s: one SDK force refresh, zero backend refresh; success=$success',
      () async {
        String? token = 'expired';
        int refreshes = 0,
            backendRefreshes = 0,
            first = 0,
            retries = 0,
            invalidations = 0;
        final barrier = Completer<void>();
        final provider = FirebaseIdTokenProvider(
          readIdToken: (force) async {
            if (force) {
              refreshes++;
              await Future<void>.delayed(const Duration(milliseconds: 20));
              if (!success) throw StateError('expired');
              token = 'fresh';
            }
            return token;
          },
          signOut: () async {
            token = null;
          },
        );
        final dio = buildDio(
          store: InMemorySecureStore(),
          baseUrl: 'https://example.test',
          tokenProvider: provider,
          onSessionExpired: () async {
            invalidations++;
          },
        );
        dio.httpClientAdapter = HandlerAdapter((options, _) async {
          if (options.path == 'auth/refresh') backendRefreshes++;
          if (options.headers['Authorization'] == 'Bearer fresh') {
            retries++;
            return body({'ok': true}, 200);
          }
          first++;
          if (first == 10) barrier.complete();
          await barrier.future;
          return body({
            'error': {'code': 'firebase_token_expired'},
          }, 401);
        });
        final results = await Future.wait([
          for (int i = 0; i < 10; i++)
            dio
                .get<dynamic>('protected/$i')
                .then<Object>((r) => r, onError: (Object e) => e),
        ]);
        expect(refreshes, 1);
        expect(backendRefreshes, 0);
        expect(first, 10);
        expect(retries, success ? 10 : 0);
        expect(invalidations, success ? 0 : 1);
        expect(results.whereType<Response<dynamic>>().length, success ? 10 : 0);
        if (!success) expect(token, isNull);
        dio.close();
      },
    );
  }
  test('backend SSE parses split Turkish UTF8 CRLF and multiline data', () async {
    final input = utf8.encode(
      ': heartbeat\r\nevent: text_delta\r\ndata: {"text":\r\ndata: "Gökyüzü"}\r\n\r\nevent: message_complete\ndata: {"conversation_id":"c"}\n\n',
    );
    final events = await parseBackendSse(
      Stream.fromIterable(input.map((v) => [v])),
    ).toList();
    expect(events.map((e) => e.name), ['text_delta', 'message_complete']);
    expect(events.first.data['text'], 'Gökyüzü');
  });
  test('SSE unexpected EOF is an incomplete response, not completed', () async {
    final dio = Dio(BaseOptions(baseUrl: 'https://example.test'))
      ..httpClientAdapter = HandlerAdapter(
        (_, _) async => ResponseBody.fromString(
          'event: text_delta\ndata: {"text":"partial"}\n\n',
          200,
          headers: {
            'content-type': ['text/event-stream'],
          },
        ),
      );
    final repo = ApiAstroAIRepository(ApiClient(dio));
    final seen = <AstroAIEvent>[];
    try {
      await for (final event in repo.streamChat('hello')) {
        seen.add(event);
      }
      fail('Expected incomplete error');
    } on ApiException catch (e) {
      expect(e.code, 'stream_incomplete');
    }
    expect(seen.whereType<AstroAICompleted>(), isEmpty);
    expect(seen.whereType<AstroAITextDelta>().single.text, 'partial');
  });
  test(
    'job polling stops at terminal states and has a hard request budget',
    () async {
      int calls = 0;
      final dio = Dio(BaseOptions(baseUrl: 'https://example.test'))
        ..httpClientAdapter = HandlerAdapter((_, _) async {
          calls++;
          return body({'id': 'job', 'status': 'running'}, 200);
        });
      final repo = ApiAstroAIRepository(ApiClient(dio));
      await expectLater(
        repo
            .pollJob('job', interval: Duration.zero, maxAttempts: 3)
            .drain<void>(),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'report_poll_timeout',
          ),
        ),
      );
      expect(calls, 3);
      calls = 0;
      dio.httpClientAdapter = HandlerAdapter((_, _) async {
        calls++;
        return body({'id': 'job', 'status': 'cancelled'}, 200);
      });
      expect(
        (await repo.pollJob('job', interval: Duration.zero).toList()).length,
        1,
      );
      expect(calls, 1);
    },
  );
}
