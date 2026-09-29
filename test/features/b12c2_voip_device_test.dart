import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/features/calls/data/voip_device_service.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeTokens implements VoipTokenGateway {
  VoipCredential? value;
  bool invalidated = false;
  void Function(String)? callback;

  @override
  Future<VoipCredential?> currentToken() async => value;
  @override
  Future<bool> consumeInvalidation() async {
    final result = invalidated;
    invalidated = false;
    return result;
  }

  @override
  void listen(void Function(String event) onEvent) => callback = onEvent;
  @override
  void dispose() => callback = null;
}

class FakeDevices implements VoipDeviceApi {
  final registered = <VoipCredential>[];
  final deleted = <String>[];
  bool failDelete = false;

  @override
  Future<String> register(VoipCredential credential) async {
    registered.add(credential);
    return 'device-${registered.length}';
  }

  @override
  Future<void> unregister(String id) async {
    if (failDelete) throw StateError('network');
    deleted.add(id);
  }
}

void main() {
  final token1 = 'ab' * 32;
  final token2 = 'cd' * 32;

  test('register, rotate and logout keep only opaque device ID', () async {
    final store = InMemorySecureStore();
    final gateway = FakeTokens()..value = VoipCredential(token1, 'sandbox');
    final api = FakeDevices();
    final service = VoipDeviceService(api, store, gateway);
    await service.startAfterAuth();
    expect(api.registered.single.token, token1);
    expect(await store.read('b12c2_voip_device_id'), 'device-1');
    expect(await store.read(token1), isNull);

    gateway.value = VoipCredential(token2, 'sandbox');
    await service.sync();
    expect(api.deleted, ['device-1']);
    expect(await store.read('b12c2_voip_device_id'), 'device-2');
    await service.unregister();
    expect(api.deleted, ['device-1', 'device-2']);
    expect(await store.read('b12c2_voip_device_id'), isNull);
    service.dispose();
  });

  test('invalidation deletes registered device without a new token', () async {
    final store = InMemorySecureStore();
    final gateway = FakeTokens()..value = VoipCredential(token1, 'production');
    final api = FakeDevices();
    final service = VoipDeviceService(api, store, gateway);
    await service.startAfterAuth();
    gateway
      ..value = null
      ..invalidated = true;
    await service.sync();
    expect(api.deleted, ['device-1']);
    expect(await store.read('b12c2_voip_device_id'), isNull);
    service.dispose();
  });

  test('invalid token and unauthenticated update never register', () async {
    final gateway = FakeTokens()
      ..value = const VoipCredential('bad', 'sandbox');
    final api = FakeDevices();
    final service = VoipDeviceService(api, InMemorySecureStore(), gateway);
    gateway.callback?.call('tokenUpdated');
    expect(api.registered, isEmpty);
    await service.startAfterAuth();
    expect(api.registered, isEmpty);
    service.dispose();
  });

  test('logout clears local ID even if backend cleanup fails', () async {
    final store = InMemorySecureStore();
    final gateway = FakeTokens()..value = VoipCredential(token1, 'sandbox');
    final api = FakeDevices();
    final service = VoipDeviceService(api, store, gateway);
    await service.startAfterAuth();
    api.failDelete = true;
    await expectLater(service.unregister(), throwsStateError);
    expect(await store.read('b12c2_voip_device_id'), isNull);
    service.dispose();
  });
}
