import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:astrofrekans/features/consultation/data/consultation_models.dart';
import 'package:astrofrekans/core/config/firebase_client.dart';
import 'package:astrofrekans/features/consultation/data/push_service.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_models.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

void main() {
  test(
    'Firebase capability exposes initializing and ready separately',
    () async {
      final pending = Completer<FirebaseAvailability>();
      final container = ProviderContainer(
        overrides: [
          firebaseBootstrapProvider.overrideWith((ref) => pending.future),
        ],
      );
      addTearDown(container.dispose);
      expect(
        container.read(firebaseAvailabilityProvider).status,
        FirebaseBootstrapStatus.initializing,
      );
      pending.complete(
        const FirebaseAvailability(FirebaseBootstrapStatus.ready),
      );
      await container.read(firebaseBootstrapProvider.future);
      expect(container.read(firebaseAvailabilityProvider).ready, isTrue);
    },
  );
  final fixture =
      jsonDecode(
            File('test/fixtures/b12b_schema_samples.json').readAsStringSync(),
          )
          as Map<String, dynamic>;

  test('expert DTO keeps public metadata and service capability', () {
    final expert = Expert(fixture['expert'] as Map<String, dynamic>);
    expect(expert.name, 'Ayşe Demir');
    expect(expert.verified, isTrue);
    expect(expert.rating, 4.8);
    expect(expert.services.single.supportsChat, isTrue);
    expect(expert.services.single.supportsVoice, isFalse);
    expect(expert.fromPrice!.minor, 1999);
    expect(expert.json.containsKey('email'), isFalse);
    expect(() => expert.json['email'] = 'x', throwsUnsupportedError);
  });

  test('slots and appointments retain canonical UTC through DST', () {
    final slot = SlotPage(
      fixture['slots'] as Map<String, dynamic>,
    ).slots.single;
    final appointment = Appointment(
      fixture['appointment'] as Map<String, dynamic>,
    );
    expect(slot.startsUtc.isUtc, isTrue);
    expect(slot.startsUtc.toIso8601String(), '2026-10-25T01:30:00.000Z');
    expect(appointment.startsUtc, slot.startsUtc);
    expect(appointment.timezone, 'Europe/Istanbul');
  });

  test('order paid state is not inferred and review is gated', () {
    final order = Order(fixture['order'] as Map<String, dynamic>);
    expect(order.status, OrderStatus.pendingPayment);
    expect(order.reviewEligible, isFalse);
    expect(
      Order({...order.json, 'status': 'completed'}).reviewEligible,
      isTrue,
    );
    expect(order.total.minor, 1999);
    expect(
      Order({...order.json, 'status': 'new_future_state'}).status,
      OrderStatus.unknown,
    );
  });

  test(
    'booking retry retains key and payload while intentional booking differs',
    () {
      final first = BookingIntent(
        serviceId: 'service',
        startsUtc: DateTime.utc(2026, 10, 25, 1, 30),
      );
      final retryKey = first.idempotencyKey;
      expect(first.idempotencyKey, retryKey);
      expect(first.payload['starts_at_utc'], startsWith('2026-10-25T01:30:00'));
      expect(
        BookingIntent(serviceId: 'service').idempotencyKey,
        isNot(retryKey),
      );
    },
  );

  test('consent, conversation, messages, attachment and device parse', () {
    final consent = OrderConsent(
      (fixture['consents'] as List).single as Map<String, dynamic>,
    );
    expect(consent.active, isTrue);
    expect(consentScopes, contains('share_previous_readings'));
    final conversation = Conversation(
      fixture['conversation'] as Map<String, dynamic>,
    );
    expect(conversation.canRead, isTrue);
    expect(conversation.canWrite, isTrue);
    final message = ConsultationMessage(
      fixture['message'] as Map<String, dynamic>,
    );
    expect(message.isMine(conversation.myRole), isTrue);
    expect(message.clientMessageId, isNotNull);
    final intent = AttachmentIntent(
      fixture['attachment_intent'] as Map<String, dynamic>,
    );
    expect(intent.maxBytes, 8 * 1024 * 1024);
    expect(intent.storageKey, startsWith('chat/${conversation.id}/'));
    final device = PushDevice(fixture['device'] as Map<String, dynamic>);
    expect(device.json.containsKey('token'), isFalse);
  });

  test('notification routes are generic and allowlisted', () {
    const id = '66666666-6666-4666-8666-666666666666';
    expect(
      routeForPush({'event': 'new_chat_message', 'conversation_id': id}),
      '/consultations/$id',
    );
    expect(
      routeForPush({
        'event': 'new_chat_message',
        'conversation_id': '../../private',
        'body': 'private',
      }),
      isNull,
    );
    expect(
      routeForPush({'event': 'call_started', 'conversation_id': id}),
      isNull,
    );
  });
}
