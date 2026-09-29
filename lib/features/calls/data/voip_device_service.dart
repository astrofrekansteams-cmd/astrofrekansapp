import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/storage/secure_storage.dart';

const _deviceKey = 'b12c2_voip_device_id';

class VoipCredential {
  const VoipCredential(this.token, this.environment);
  final String token;
  final String environment;

  bool get valid =>
      token.length >= 32 &&
      token.length.isEven &&
      RegExp(r'^[0-9a-fA-F]+$').hasMatch(token) &&
      (environment == 'sandbox' || environment == 'production');
}

abstract interface class VoipTokenGateway {
  Future<VoipCredential?> currentToken();
  Future<bool> consumeInvalidation();
  void listen(void Function(String event) onEvent);
  void dispose();
}

class PlatformVoipTokenGateway implements VoipTokenGateway {
  static const _channel = MethodChannel('astrofrekans/voip_tokens');

  @override
  Future<VoipCredential?> currentToken() async {
    final raw = await _channel.invokeMethod<Object?>('currentToken');
    if (raw is! Map) return null;
    final token = raw['token'];
    final environment = raw['environment'];
    return token is String && environment is String
        ? VoipCredential(token, environment)
        : null;
  }

  @override
  Future<bool> consumeInvalidation() async =>
      await _channel.invokeMethod<bool>('consumeInvalidation') ?? false;

  @override
  void listen(void Function(String event) onEvent) {
    _channel.setMethodCallHandler((call) async => onEvent(call.method));
  }

  @override
  void dispose() => _channel.setMethodCallHandler(null);
}

abstract interface class VoipDeviceApi {
  Future<String> register(VoipCredential credential);
  Future<void> unregister(String id);
}

class ApiVoipDeviceApi implements VoipDeviceApi {
  const ApiVoipDeviceApi(this.client);
  final ApiClient client;

  @override
  Future<String> register(VoipCredential credential) async {
    final response = await client.postMap(
      'devices/voip',
      data: {'token': credential.token, 'environment': credential.environment},
    );
    final id = response['id'];
    if (id is! String || id.isEmpty) {
      throw const FormatException('VoIP registration response has no id');
    }
    return id;
  }

  @override
  Future<void> unregister(String id) => client.delete('devices/voip/$id');
}

/// Keeps the PushKit token in memory only. The backend returns an opaque device
/// ID, which is the sole VoIP value persisted locally for cleanup.
class VoipDeviceService {
  VoipDeviceService(this.api, this.store, this.gateway) {
    gateway.listen((event) {
      if (!_active) return;
      if (event == 'tokenUpdated' || event == 'tokenInvalidated') {
        unawaited(sync().catchError((Object _) {}));
      }
    });
  }

  final VoipDeviceApi api;
  final SecureStore store;
  final VoipTokenGateway gateway;
  bool _active = false;
  bool _resyncRequested = false;
  Future<void>? _syncing;

  Future<void> startAfterAuth() {
    _active = true;
    return sync();
  }

  Future<void> sync() {
    _resyncRequested = true;
    return _syncing ??= _drainSync().whenComplete(() => _syncing = null);
  }

  Future<void> _drainSync() async {
    while (_active && _resyncRequested) {
      _resyncRequested = false;
      await _sync();
    }
  }

  Future<void> _sync() async {
    if (!_active) return;
    final oldId = await store.read(_deviceKey);
    if (await gateway.consumeInvalidation()) {
      if (oldId != null) await api.unregister(oldId);
      await store.delete(_deviceKey);
      return;
    }
    final credential = await gateway.currentToken();
    if (credential == null || !credential.valid) return;
    final newId = await api.register(credential);
    await store.write(_deviceKey, newId);
    if (oldId != null && oldId != newId) {
      try {
        await api.unregister(oldId);
      } on Object {
        // The new credential is already registered; cleanup can be retried.
      }
    }
  }

  Future<void> unregister() async {
    _active = false;
    _resyncRequested = false;
    final pending = _syncing;
    if (pending != null) {
      try {
        await pending;
      } on Object {
        /* Cleanup still proceeds. */
      }
    }
    final id = await store.read(_deviceKey);
    try {
      if (id != null) await api.unregister(id);
    } finally {
      await store.delete(_deviceKey);
    }
  }

  void dispose() => gateway.dispose();
}

final voipDeviceServiceProvider = Provider<VoipDeviceService?>((ref) {
  final config = ref.watch(appEnvironmentProvider);
  if (kIsWeb ||
      defaultTargetPlatform != TargetPlatform.iOS ||
      config.useMocks) {
    return null;
  }
  final service = VoipDeviceService(
    ApiVoipDeviceApi(ApiClient(ref.watch(dioProvider))),
    ref.watch(secureStoreProvider),
    PlatformVoipTokenGateway(),
  );
  ref.onDispose(service.dispose);
  return service;
});
