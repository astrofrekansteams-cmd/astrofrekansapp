// The session drives push registration; push must never depend on the
// session. A provider cycle here (session -> push -> ... -> session) only
// throws in debug builds, so it is pinned by a test.

import 'dart:async';

import 'package:astrofrekans/core/config/firebase_client.dart';
import 'package:astrofrekans/core/network/api_config.dart';
import 'package:astrofrekans/core/storage/app_preferences.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/features/auth/application/session_controller.dart';
import 'package:astrofrekans/features/auth/domain/auth_repository.dart';
import 'package:astrofrekans/features/consultation/data/consultation_models.dart';
import 'package:astrofrekans/features/consultation/data/consultation_repository.dart';
import 'package:astrofrekans/features/consultation/data/push_service.dart';
import 'package:astrofrekans/features/profile/domain/user_profile.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';

class _Auth extends Fake implements AuthRepository {
  UserProfile? stored;
  Completer<void>? restoring;
  @override
  Future<UserProfile?> restoreSession() async {
    await restoring?.future;
    return stored;
  }

  @override
  Future<UserProfile> signIn({
    required String email,
    required String password,
  }) async => stored = testUser;
  @override
  Future<void> signOut() async => stored = null;
}

class _Gateway implements PushGateway {
  _Gateway({this.granted = true});
  final bool granted;
  bool deleted = false;
  @override
  Future<bool> permissionGranted() async => granted;
  @override
  Future<bool> requestPermission() async => granted;
  @override
  Future<String?> token() async => List.filled(40, 'f').join();
  @override
  Stream<String> get tokenRefresh => const Stream.empty();
  @override
  Stream<Map<String, dynamic>> get opened => const Stream.empty();
  @override
  Stream<Map<String, dynamic>> get foreground => const Stream.empty();
  @override
  Future<Map<String, dynamic>?> initialMessage() async => null;
  @override
  Future<void> deleteToken() async => deleted = true;
}

class _Devices implements PushDeviceApi {
  final registered = <String>[];
  final removed = <String>[];
  @override
  Future<PushDevice> registerDevice({
    required String token,
    required String platform,
    String? deviceId,
    String? appVersion,
  }) async {
    registered.add(platform);
    // The server upserts by token: the same token is the same device.
    return PushDevice({'id': 'device-1', 'token_fingerprint': 'fp'});
  }

  @override
  Future<void> unregisterDevice(String id) async => removed.add(id);
}

const _api = AppEnvironment(
  environment: AppEnvironmentName.development,
  apiBaseUrl: 'http://10.0.2.2:8000',
  dataSource: AppDataSource.api,
  enableDebugTools: false,
);

Future<(ProviderContainer, _Auth)> _container({
  _Devices? devices,
  _Gateway? gateway,
}) async {
  final env = await TestEnv.create();
  final auth = _Auth();
  final container = ProviderContainer.test(
    overrides: [
      appPreferencesProvider.overrideWithValue(env.preferences),
      secureStoreProvider.overrideWithValue(env.store),
      appEnvironmentProvider.overrideWithValue(_api),
      authRepositoryProvider.overrideWithValue(auth),
      pushGatewayProvider.overrideWithValue(gateway ?? _Gateway()),
      firebaseBootstrapProvider.overrideWith(
        (ref) async =>
            const FirebaseAvailability(FirebaseBootstrapStatus.ready),
      ),
      if (devices != null) pushDeviceApiProvider.overrideWithValue(devices),
    ],
  );
  return (container, auth);
}

Future<void> _settle() => Future<void>.delayed(Duration.zero);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('login, restore, logout and login again never form a cycle', () async {
    // The real device API and repositories: only the platform edges are fake.
    final (container, auth) = await _container(
      gateway: _Gateway(granted: false),
    );
    final session = container.read(sessionProvider.notifier);
    // Something already watches push (the app shell does) when auth changes.
    container.listen(pushServiceProvider, (_, _) {});

    await session.signIn(email: 'a@b.co', password: 'secret-pass');
    expect(container.read(sessionProvider).isAuthenticated, isTrue);

    await session.bootstrap(); // restart with a stored session
    expect(container.read(sessionProvider).isAuthenticated, isTrue);

    await session.signOut();
    expect(container.read(sessionProvider).isAuthenticated, isFalse);
    expect(auth.stored, isNull);

    await session.signIn(email: 'a@b.co', password: 'secret-pass');
    await _settle();
    expect(container.read(sessionProvider).isAuthenticated, isTrue);
  });

  test(
    'the device is registered after sign-in and removed on sign-out',
    () async {
      final devices = _Devices();
      final gateway = _Gateway();
      final (container, _) = await _container(
        devices: devices,
        gateway: gateway,
      );
      final session = container.read(sessionProvider.notifier);

      await session.signIn(email: 'a@b.co', password: 'secret-pass');
      await _settle();
      expect(devices.registered, ['android']);

      // The same service instance survives the session change.
      final before = container.read(pushServiceProvider);
      await session.bootstrap();
      await _settle();
      expect(identical(container.read(pushServiceProvider), before), isTrue);

      await session.signOut();
      expect(devices.removed, ['device-1']);
      expect(gateway.deleted, isTrue);

      await session.signIn(email: 'a@b.co', password: 'secret-pass');
      await _settle();
      expect(devices.registered.length, 3);
    },
  );

  test('a restore in progress is not a signed-out session', () async {
    final (container, auth) = await _container(
      gateway: _Gateway(granted: false),
    );
    final session = container.read(sessionProvider.notifier);
    await session.signIn(email: 'a@b.co', password: 'secret-pass');

    auth.restoring = Completer<void>();
    final restoring = session.bootstrap();
    // The router keeps the splash: it must not redirect to login yet.
    expect(container.read(sessionProvider).isResolved, isFalse);
    auth.restoring!.complete();
    await restoring;
    expect(container.read(sessionProvider).isResolved, isTrue);
    expect(container.read(sessionProvider).isAuthenticated, isTrue);
  });
}
