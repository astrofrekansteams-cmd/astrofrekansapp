import 'dart:async';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/firebase_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/routing/notification_routes.dart';
import '../../../core/storage/secure_storage.dart';
import 'consultation_repository.dart';

const _pushDeviceKey = 'b12b_push_device_id';

/// Where a tapped push leads: the same answer as the notification centre.
String? routeForPush(Map<String, dynamic> data) {
  final event = data['event'];
  return routeForNotification(event is String ? event : null, data);
}

abstract interface class PushGateway {
  Future<bool> permissionGranted();
  Future<bool> requestPermission();
  Future<String?> token();
  Stream<String> get tokenRefresh;
  Stream<Map<String, dynamic>> get opened;
  Stream<Map<String, dynamic>> get foreground;
  Future<Map<String, dynamic>?> initialMessage();
  Future<void> deleteToken();
}

class FirebasePushGateway implements PushGateway {
  FirebaseMessaging get _messaging => FirebaseMessaging.instance;
  @override
  Future<bool> permissionGranted() async {
    final status =
        (await _messaging.getNotificationSettings()).authorizationStatus;
    return status == AuthorizationStatus.authorized ||
        status == AuthorizationStatus.provisional;
  }

  @override
  Future<bool> requestPermission() async {
    final status = (await _messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    )).authorizationStatus;
    return status == AuthorizationStatus.authorized ||
        status == AuthorizationStatus.provisional;
  }

  @override
  Future<String?> token() => _messaging.getToken();
  @override
  Stream<String> get tokenRefresh => _messaging.onTokenRefresh;
  @override
  Stream<Map<String, dynamic>> get opened =>
      FirebaseMessaging.onMessageOpenedApp.map((m) => m.data);
  @override
  Stream<Map<String, dynamic>> get foreground =>
      FirebaseMessaging.onMessage.map((m) => m.data);
  @override
  Future<Map<String, dynamic>?> initialMessage() async =>
      (await _messaging.getInitialMessage())?.data;
  @override
  Future<void> deleteToken() => _messaging.deleteToken();
}

abstract interface class PushService {
  Stream<String> get routes;

  /// Inbox records whose push was opened (`notification_id`), so the app
  /// marks the same record read that the notification centre shows.
  Stream<String> get openedNotificationIds;
  Stream<Map<String, dynamic>> get foregroundEvents;
  Future<void> startAfterAuth();
  Future<bool> requestPermissionExplicit();
  Future<void> unregister();
  void dispose();
}

class FirebasePushService implements PushService {
  FirebasePushService(this.api, this.store, this.gateway, this.availability);
  final PushDeviceApi api;
  final SecureStore store;
  final PushGateway gateway;
  final Future<FirebaseAvailability> availability;
  final _routes = StreamController<String>.broadcast();
  final _foregroundEvents = StreamController<Map<String, dynamic>>.broadcast();
  final _openedIds = StreamController<String>.broadcast();
  StreamSubscription<String>? _refresh;
  StreamSubscription<Map<String, dynamic>>? _openedSubscription;
  StreamSubscription<Map<String, dynamic>>? _foreground;
  Future<void>? _starting;
  @override
  Stream<String> get routes => _routes.stream;
  @override
  Stream<Map<String, dynamic>> get foregroundEvents => _foregroundEvents.stream;
  @override
  Stream<String> get openedNotificationIds => _openedIds.stream;

  void _opened(Map<String, dynamic> data) {
    final route = routeForPush(data);
    if (route != null) _routes.add(route);
    if (notificationIdOf(data) case final id?) _openedIds.add(id);
    if (data['event'] == 'call_cancelled' || data['event'] == 'call_missed') {
      _foregroundEvents.add(data);
    }
  }

  @override
  Future<void> startAfterAuth() =>
      _starting ??= _activate().whenComplete(() => _starting = null);
  Future<void> _activate() async {
    if (!(await availability).ready || !(await gateway.permissionGranted())) {
      return;
    }
    await _registerCurrentToken();
    _refresh ??= gateway.tokenRefresh.listen((_) {
      unawaited(_registerCurrentToken().catchError((Object _) {}));
    });
    _openedSubscription ??= gateway.opened.listen(_opened);
    _foreground ??= gateway.foreground.listen((data) {
      _foregroundEvents.add(data);
    });
    final initial = await gateway.initialMessage();
    if (initial != null) _opened(initial);
  }

  Future<void> _registerCurrentToken() async {
    final token = await gateway.token();
    if (token == null || token.length < 32) return;
    final platform = kIsWeb
        ? 'web'
        : switch (defaultTargetPlatform) {
            TargetPlatform.iOS => 'ios',
            _ => 'android',
          };
    final registered = await api.registerDevice(
      token: token,
      platform: platform,
    );
    final old = await store.read(_pushDeviceKey);
    await store.write(_pushDeviceKey, registered.id);
    if (old != null && old != registered.id) {
      try {
        await api.unregisterDevice(old);
      } on Object {
        /* Old-account ownership may have moved. */
      }
    }
  }

  @override
  Future<bool> requestPermissionExplicit() async {
    if (!(await availability).ready) return false;
    final granted = await gateway.requestPermission();
    if (granted) await startAfterAuth();
    return granted;
  }

  @override
  Future<void> unregister() async {
    await _refresh?.cancel();
    _refresh = null;
    await _openedSubscription?.cancel();
    _openedSubscription = null;
    await _foreground?.cancel();
    _foreground = null;
    final id = await store.read(_pushDeviceKey);
    if (id != null) {
      try {
        await api.unregisterDevice(id);
      } on Object {
        /* Deleting the FCM token still invalidates this address. */
      }
    }
    try {
      if ((await availability).ready) await gateway.deleteToken();
    } finally {
      await store.delete(_pushDeviceKey);
    }
  }

  @override
  void dispose() {
    _refresh?.cancel();
    _openedSubscription?.cancel();
    _foreground?.cancel();
    _routes.close();
    _foregroundEvents.close();
    _openedIds.close();
  }
}

class UnavailablePushService implements PushService {
  const UnavailablePushService();
  @override
  Stream<String> get routes => const Stream<String>.empty();
  @override
  Stream<Map<String, dynamic>> get foregroundEvents =>
      const Stream<Map<String, dynamic>>.empty();
  @override
  Stream<String> get openedNotificationIds => const Stream<String>.empty();
  @override
  Future<void> startAfterAuth() async {}
  @override
  Future<bool> requestPermissionExplicit() async => false;
  @override
  Future<void> unregister() async {}
  @override
  void dispose() {}
}

final pushGatewayProvider = Provider<PushGateway>(
  (ref) => FirebasePushGateway(),
);
final pushServiceProvider = Provider<PushService>((ref) {
  if (ref.watch(appEnvironmentProvider).useMocks) {
    return const UnavailablePushService();
  }
  final service = FirebasePushService(
    ref.watch(pushDeviceApiProvider),
    ref.watch(secureStoreProvider),
    ref.watch(pushGatewayProvider),
    ref.watch(firebaseBootstrapProvider.future),
  );
  ref.onDispose(service.dispose);
  return service;
});
final pushDeviceCleanupProvider = Provider<Future<void> Function()>(
  (ref) =>
      () => ref.read(pushServiceProvider).unregister(),
);
