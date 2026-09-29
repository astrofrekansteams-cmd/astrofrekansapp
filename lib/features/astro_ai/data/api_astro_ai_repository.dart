import 'dart:async';
import 'dart:convert';
import 'package:dio/dio.dart';

import '../../../core/astrology/data/production_models.dart';
import '../../../core/astrology/domain/natal_chart.dart';
import '../../../core/astrology/domain/transit.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_error.dart';
import '../../../core/network/api_exception.dart';
import '../../profile/domain/user_profile.dart';
import '../domain/astro_ai_repository.dart';
import '../domain/chat_message.dart';
import '../../billing/application/paid_report_service.dart';
import 'ai_models.dart';

class SseEvent {
  const SseEvent(this.name, this.data);
  final String name;
  final Json data;
}

/// The server frames every event as `{"type": ..., "text": ..., "data": {...}}`
/// (`text` on `text_delta`, `data` on the rest). The app reads one flat map,
/// so both are folded together; a flat payload passes through unchanged.
Json _payload(Map<String, dynamic> frame) {
  final inner = frame['data'];
  if (inner is! Map<String, dynamic>) return frame;
  return {
    ...inner,
    if (frame['text'] is String) 'text': frame['text'],
    if (frame['type'] is String) 'type': frame['type'],
  };
}

/// Chunk boundaries may split UTF-8 characters, fields or CRLF separators.
Stream<SseEvent> parseBackendSse(Stream<List<int>> bytes) async* {
  String name = 'message';
  final data = <String>[];
  await for (final line
      in bytes.transform(utf8.decoder).transform(const LineSplitter())) {
    if (line.isEmpty) {
      if (data.isNotEmpty) {
        final value = jsonDecode(data.join('\n'));
        if (value is! Map<String, dynamic>) {
          throw const FormatException('Invalid SSE data');
        }
        yield SseEvent(name, _payload(value));
      }
      name = 'message';
      data.clear();
    } else if (line.startsWith('event:')) {
      name = line.substring(6).trim();
    } else if (line.startsWith('data:')) {
      data.add(line.substring(5).replaceFirst(RegExp(r'^ '), ''));
    }
  }
  // An unterminated event is not a complete SSE frame; never mark it complete.
}

class ApiAstroAIRepository implements AstroAIRepository, ReportGenerator {
  ApiAstroAIRepository(this.api, {this.locale = 'tr'});
  final ApiClient api;
  final String locale;
  String? conversationId;

  Future<Json> status() => api.getMap('ai/status');
  Future<AIConversation> createConversation({String? title}) async {
    final result = AIConversation(
      await api.postMap(
        'ai/conversations',
        data: {'title': title, 'locale': locale},
      ),
    );
    conversationId = result.id;
    return result;
  }

  Future<List<AIConversation>> conversations() async =>
      (await api.getList('ai/conversations')).map(AIConversation.new).toList();
  Future<List<AIMessage>> messages(String id) async => (await api.getList(
    'ai/conversations/${Uri.encodeComponent(id)}/messages',
  )).map(AIMessage.new).toList();
  Future<Json> chat(String message) async {
    final result = await api.postMap(
      'ai/chat',
      data: {
        'message': message,
        'conversation_id': conversationId,
        'locale': locale,
      },
    );
    conversationId = result['conversation_id'] as String;
    return result;
  }

  Future<List<AIReport>> reports() async =>
      (await api.getList('ai/reports')).map(AIReport.new).toList();
  Future<AIReport> report(String id) async =>
      AIReport(await api.getMap('ai/reports/${Uri.encodeComponent(id)}'));
  @override
  Future<PaidReportDelivery> createReport(
    String type, {
    String? sourceId,
    required String consumerRef,
    bool payWithCoins = false,
  }) async {
    try {
      final response = await api.transport.post<dynamic>(
        'ai/reports',
        data: {
          'report_type': type,
          'source_id': sourceId,
          'locale': locale,
          'background': false,
          'consumer_ref': consumerRef,
          if (payWithCoins) 'pay_with_coins': true,
        },
      );
      final raw = response.data;
      if (raw is! Map) throw const FormatException('Invalid report response');
      final body = Map<String, dynamic>.from(raw);
      return switch (response.statusCode) {
        200 => PaidReportReady(AIReport(body)),
        202 => PaidReportQueued(AIReportJob(body)),
        _ => throw const FormatException('Unexpected report response'),
      };
    } on DioException catch (error) {
      throw mapDioException(error);
    }
  }

  Future<AIReportJob> createJob(String type, {String? sourceId}) async =>
      AIReportJob(
        await api.postMap(
          'ai/report-jobs',
          data: {'report_type': type, 'source_id': sourceId, 'locale': locale},
        ),
      );
  Future<AIReportJob> job(String id) async => AIReportJob(
    await api.getMap('ai/report-jobs/${Uri.encodeComponent(id)}'),
  );
  Future<AIReportJob> cancelJob(String id) async => AIReportJob(
    await api.postMap('ai/report-jobs/${Uri.encodeComponent(id)}/cancel'),
  );

  /// Bounded polling; cancellation interrupts both the timer and active HTTP.
  Stream<AIReportJob> pollJob(
    String id, {
    Duration interval = const Duration(seconds: 3),
    int maxAttempts = 40,
  }) async* {
    if (maxAttempts < 1 || maxAttempts > 100 || interval.isNegative) {
      throw ArgumentError('Invalid polling budget');
    }
    for (int i = 0; i < maxAttempts; i++) {
      final result = await job(id);
      yield result;
      if (result.terminal) return;
      if (i + 1 < maxAttempts) await Future<void>.delayed(interval);
    }
    throw const ApiException(
      kind: ApiErrorKind.timeout,
      code: 'report_poll_timeout',
    );
  }

  Stream<AstroAIEvent> streamChat(String message) {
    final cancel = CancelToken();
    late StreamController<AstroAIEvent> output;
    output = StreamController<AstroAIEvent>(
      onListen: () async {
        bool completed = false;
        try {
          final response = await api.transport.post<ResponseBody>(
            'ai/chat/stream',
            data: {
              'message': message,
              'conversation_id': conversationId,
              'locale': locale,
            },
            options: Options(
              responseType: ResponseType.stream,
              headers: {'Accept': 'text/event-stream'},
            ),
            cancelToken: cancel,
          );
          final body = response.data;
          if (body == null) throw const FormatException('Missing SSE body');
          await for (final event in parseBackendSse(
            body.stream.cast<List<int>>(),
          ).timeout(const Duration(seconds: 45))) {
            if (cancel.isCancelled) break;
            switch (event.name) {
              case 'message_start':
                conversationId = event.data['conversation_id'] as String;
              case 'text_delta':
                output.add(AstroAITextDelta(event.data['text'] as String));
              case 'metadata':
                output.add(
                  AstroAIMetadata(
                    warnings: (event.data['warnings'] as List? ?? [])
                        .cast<String>(),
                    availableFactorIds:
                        (event.data['available_factor_ids'] as List? ?? [])
                            .cast<String>(),
                    influenceLabels: [
                      for (final item
                          in (event.data['influences'] as List? ?? []))
                        if (item is Map && item['label'] is String)
                          item['label'] as String,
                    ],
                  ),
                );
              case 'message_complete':
                completed = true;
                conversationId =
                    event.data['conversation_id'] as String? ?? conversationId;
                output.add(const AstroAICompleted());
              case 'error':
                throw ApiException(
                  kind: ApiErrorKind.server,
                  code: event.data['code'] as String?,
                );
            }
          }
          if (!completed && !cancel.isCancelled) {
            throw const ApiException(
              kind: ApiErrorKind.network,
              code: 'stream_incomplete',
            );
          }
        } on Object catch (error, stack) {
          if (!cancel.isCancelled) {
            output.addError(
              error is DioException ? mapDioException(error) : error,
              stack,
            );
          }
        } finally {
          cancel.cancel();
          if (!output.isClosed) await output.close();
        }
      },
      onCancel: () => cancel.cancel('screen_left'),
    );
    return output.stream;
  }

  @override
  Stream<AstroAIEvent> sendMessage({
    required String message,
    required UserProfile userProfile,
    required NatalChart natalChart,
    required List<Transit> activeTransits,
    List<ChatMessage> history = const [],
  }) => streamChat(message);
}
