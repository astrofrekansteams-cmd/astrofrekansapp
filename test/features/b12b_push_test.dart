import 'dart:async';

import 'package:astrofrekans/core/config/firebase_client.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/features/consultation/data/consultation_models.dart';
import 'package:astrofrekans/features/consultation/data/consultation_repository.dart';
import 'package:astrofrekans/features/consultation/data/push_service.dart';
import 'package:flutter_test/flutter_test.dart';

class _PushRepository extends Fake implements ConsultationRepository {
  final registered = <String>[];
  final removed = <String>[];
  @override
  Future<PushDevice> registerDevice({
    required String token,
    required String platform,
    String? deviceId,
    String? appVersion,
  }) async {
    registered.add(token);
    return PushDevice({
      'id': 'device-${registered.length}',
      'token_fingerprint': 'fingerprint',
    });
  }

  @override
  Future<void> unregisterDevice(String id) async {
    removed.add(id);
  }
}

class _Gateway implements PushGateway {
  bool granted = false;
  bool deleted = false;
  String currentToken = List.filled(40, 'a').join();
  final refresh = StreamController<String>.broadcast();
  final taps = StreamController<Map<String, dynamic>>.broadcast();
  final messages = StreamController<Map<String, dynamic>>.broadcast();
  @override
  Future<bool> permissionGranted() async => granted;
  @override
  Future<bool> requestPermission() async {
    granted = true;
    return true;
  }

  @override
  Future<String?> token() async => currentToken;
  @override
  Stream<String> get tokenRefresh => refresh.stream;
  @override
  Stream<Map<String, dynamic>> get opened => taps.stream;
  @override
  Stream<Map<String, dynamic>> get foreground => messages.stream;
  @override
  Future<Map<String, dynamic>?> initialMessage() async => null;
  @override
  Future<void> deleteToken() async {
    deleted = true;
  }

  Future<void> close() async {
    await refresh.close();
    await taps.close();
    await messages.close();
  }
}

void main() {
  test(
    'no unsolicited permission; explicit grant, refresh and logout cleanup',
    () async {
      final api = _PushRepository();
      final gateway = _Gateway();
      final store = InMemorySecureStore();
      final service = FirebasePushService(
        api,
        store,
        gateway,
        Future.value(const FirebaseAvailability(FirebaseBootstrapStatus.ready)),
      );
      await service.startAfterAuth();
      expect(api.registered, isEmpty);
      expect(await service.requestPermissionExplicit(), isTrue);
      expect(api.registered, hasLength(1));
      gateway.currentToken = List.filled(40, 'b').join();
      gateway.refresh.add(gateway.currentToken);
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(api.registered, hasLength(2));
      expect(api.removed, ['device-1']);
      final routes = <String>[];
      final sub = service.routes.listen(routes.add);
      final foregroundEvents = <Map<String, dynamic>>[];
      final foregroundSub = service.foregroundEvents.listen(
        foregroundEvents.add,
      );
      gateway.messages.add({
        'event': 'incoming_call',
        'call_id': '11111111-1111-4111-8111-111111111111',
      });
      gateway.taps.add({
        'event': 'order_status_changed',
        'order_id': '33333333-3333-4333-8333-333333333333',
        'message_body': 'never surfaced',
      });
      await Future<void>.delayed(Duration.zero);
      expect(foregroundEvents.single['event'], 'incoming_call');
      expect(routes.single, '/orders/33333333-3333-4333-8333-333333333333');
      await service.unregister();
      expect(api.removed, contains('device-2'));
      expect(gateway.deleted, isTrue);
      await sub.cancel();
      await foregroundSub.cancel();
      service.dispose();
      await gateway.close();
    },
  );

  test(
    'missing Firebase config is controlled and never prompts or registers',
    () async {
      final api = _PushRepository();
      final gateway = _Gateway();
      final service = FirebasePushService(
        api,
        InMemorySecureStore(),
        gateway,
        Future.value(
          const FirebaseAvailability(FirebaseBootstrapStatus.unconfigured),
        ),
      );
      expect(await service.requestPermissionExplicit(), isFalse);
      expect(api.registered, isEmpty);
      expect(gateway.granted, isFalse);
      service.dispose();
      await gateway.close();
    },
  );
}
