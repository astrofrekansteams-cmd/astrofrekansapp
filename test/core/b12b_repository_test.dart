import 'dart:convert';
import 'dart:typed_data';

import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/features/consultation/data/consultation_models.dart';
import 'package:astrofrekans/features/consultation/data/consultation_repository.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_repository.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

class _Adapter implements HttpClientAdapter {
  _Adapter(this.reply);
  final Future<ResponseBody> Function(RequestOptions) reply;
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? request,
    Future<void>? cancel,
  ) => reply(options);
  @override
  void close({bool force = false}) {}
}

ResponseBody _body(Object value) => ResponseBody.fromString(
  jsonEncode(value),
  200,
  headers: {
    'content-type': ['application/json'],
  },
);

void main() {
  test(
    'marketplace sends only supported filters and stable booking key',
    () async {
      final paths = <String>[];
      final headers = <String>[];
      final dio = Dio(BaseOptions(baseUrl: 'https://example.test/api/v1/'));
      dio.httpClientAdapter = _Adapter((request) async {
        paths.add(request.uri.toString());
        if (request.path == 'orders') {
          headers.add('${request.headers['Idempotency-Key']}');
          return _body({
            'id': 'order',
            'service_code': 'astro_chat',
            'status': 'pending_payment',
            'payment_status': 'unpaid',
            'total': {'amount_minor': 1999, 'currency': 'TRY'},
          });
        }
        return _body({
          'items': <Map<String, dynamic>>[],
          'total': 0,
          'limit': 20,
          'offset': 0,
        });
      });
      final repo = ApiMarketplaceRepository(ApiClient(dio));
      await repo.search(
        const ExpertQuery(
          search: 'Ayşe',
          specialty: 'astrology',
          verified: true,
          ratingMin: 4.5,
        ),
      );
      expect(paths.single, contains('specialty=astrology'));
      expect(paths.single, contains('verified=true'));
      expect(paths.single, isNot(contains('search=')));
      final intent = BookingIntent(serviceId: 'service-id');
      await repo.createOrder(intent);
      await repo.createOrder(intent);
      expect(headers, [intent.idempotencyKey, intent.idempotencyKey]);
    },
  );

  test('consent uses complete-set PUT and parses list response', () async {
    String? method;
    String? path;
    Object? body;
    final dio = Dio(BaseOptions(baseUrl: 'https://example.test/api/v1/'));
    dio.httpClientAdapter = _Adapter((request) async {
      method = request.method;
      path = request.path;
      body = request.data;
      return _body([
        {
          'scope': 'share_birth_profile',
          'active': true,
          'granted_at': '2026-09-24T10:00:00Z',
        },
      ]);
    });
    final result = await ApiMarketplaceRepository(
      ApiClient(dio),
    ).setConsents('order-id', {'share_birth_profile'});
    expect(method, 'PUT');
    expect(path, 'orders/order-id/consents');
    expect(body, {
      'scopes': ['share_birth_profile'],
    });
    expect(result.single.active, isTrue);
  });

  test(
    'chat message sends backend-only client id and preserves reply',
    () async {
      String? method;
      String? path;
      Object? body;
      final dio = Dio(BaseOptions(baseUrl: 'https://example.test/api/v1/'));
      dio.httpClientAdapter = _Adapter((request) async {
        method = request.method;
        path = request.path;
        body = request.data;
        return _body({
          'message_id': 'm1',
          'sender_role': 'user',
          'message_type': 'text',
          'text': 'Hello',
          'client_message_id': 'same-id',
          'created_at': '2026-09-24T10:00:00Z',
        });
      });
      final message = await ApiConsultationRepository(ApiClient(dio)).send(
        'conversation-id',
        const OutgoingMessage(clientMessageId: 'same-id', text: 'Hello'),
      );
      expect(method, 'POST');
      expect(path, 'conversations/conversation-id/messages');
      expect(body, {'client_message_id': 'same-id', 'text': 'Hello'});
      expect(message.clientMessageId, 'same-id');
      expect((body as Map).containsKey('sender_uid'), isFalse);
    },
  );

  test(
    'review create, update and delete use their distinct backend routes',
    () async {
      final calls = <String>[];
      final dio = Dio(BaseOptions(baseUrl: 'https://example.test/api/v1/'));
      dio.httpClientAdapter = _Adapter((request) async {
        calls.add('${request.method} ${request.path}');
        return _body({
          'id': 'review-id',
          'order_id': 'order-id',
          'rating': 5,
          'comment': 'Useful',
        });
      });
      final repository = ApiMarketplaceRepository(ApiClient(dio));
      final created = await repository.createReview('order-id', 5, 'Useful');
      expect(created.orderId, 'order-id');
      await repository.updateReview(created.id, 4, 'Updated');
      await repository.deleteReview(created.id);
      expect(calls, [
        'POST orders/order-id/review',
        'PATCH reviews/review-id',
        'DELETE reviews/review-id',
      ]);
    },
  );
}
