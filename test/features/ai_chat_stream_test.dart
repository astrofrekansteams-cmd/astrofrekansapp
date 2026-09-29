// The Astro AI chat stream, parsed exactly as the server sends it.
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/features/astro_ai/data/api_astro_ai_repository.dart';
import 'package:astrofrekans/features/astro_ai/domain/astro_ai_repository.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

/// Serves the recorded response in small, arbitrary chunks (as a network
/// would), splitting multi-byte characters on purpose.
class _Adapter implements HttpClientAdapter {
  _Adapter(this.bytes);
  final List<int> bytes;
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    Stream<Uint8List> chunks() async* {
      for (var i = 0; i < bytes.length; i += 37) {
        yield Uint8List.fromList(
          bytes.sublist(i, i + 37 > bytes.length ? bytes.length : i + 37),
        );
      }
    }

    return ResponseBody(
      chunks(),
      200,
      headers: {
        Headers.contentTypeHeader: ['text/event-stream'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  final sample = File(
    'test/fixtures/ai_chat_stream_sample.sse',
  ).readAsBytesSync();

  ApiAstroAIRepository repo(List<int> bytes) => ApiAstroAIRepository(
    ApiClient(
      Dio(BaseOptions(baseUrl: 'http://api.test/api/v1/'))
        ..httpClientAdapter = _Adapter(bytes),
    ),
  );

  test(
    'a real server stream becomes text, metadata and a completion',
    () async {
      final repository = repo(sample);
      final events = await repository.streamChat('merhaba').toList();
      final text = events
          .whereType<AstroAITextDelta>()
          .map((e) => e.text)
          .join();
      expect(text.length, greaterThan(200));
      expect(text, contains('ü'));
      expect(events.whereType<AstroAIMetadata>(), hasLength(1));
      expect(events.last, isA<AstroAICompleted>());
      // The conversation id from message_start is remembered for the next turn.
      expect(repository.conversationId, 'ff14f3e9-968c-48f3-b4a2-52185fa59758');
    },
  );

  test('a server error event surfaces as an error, not a silent stop', () async {
    final frames = utf8.encode(
      'event: message_start\n'
      'data: {"type": "message_start", "data": {"conversation_id": "c1"}}\n\n'
      'event: error\n'
      'data: {"type": "error", "data": {"code": "ai_provider_unavailable"}}\n\n',
    );
    await expectLater(
      repo(frames).streamChat('x').toList(),
      throwsA(predicate((e) => e.toString().contains('ApiException'))),
    );
  });
}
