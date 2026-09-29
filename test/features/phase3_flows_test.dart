// Phase 3: one route for push and inbox, an opened push marks the same
// record read, Firebase sign-ins shown honestly, and a Firebase password
// changed in Firebase - never as a backend password.
import 'dart:async';

import 'package:astrofrekans/core/config/firebase_client.dart';
import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/core/network/retry_policy.dart';
import 'package:astrofrekans/core/storage/app_preferences.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/core/routing/notification_routes.dart';
import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/features/auth/application/session_controller.dart';
import 'package:astrofrekans/features/consultation/data/consultation_models.dart';
import 'package:astrofrekans/features/consultation/data/consultation_repository.dart';
import 'package:astrofrekans/features/consultation/data/push_service.dart';
import 'package:astrofrekans/features/notifications/data/notification_repository.dart';
import 'package:astrofrekans/features/notifications/presentation/notification_center_screen.dart';
import 'package:astrofrekans/features/profile/data/account_repository.dart';
import 'package:astrofrekans/features/profile/domain/user_profile.dart';
import 'package:astrofrekans/features/profile/presentation/account_center_screens.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';

const _id = '66666666-6666-4666-8666-666666666666';

const _user = UserProfile(id: 'u1', name: 'Nova', email: 'nova@example.com');

class _Session extends SignedInSessionController {
  _Session() : super(_user);
}

Future<void> _pump(
  WidgetTester tester,
  Widget child, {
  List<Object> overrides = const [],
}) async {
  tester.view.physicalSize =
      const Size(420, 2000) * tester.view.devicePixelRatio;
  addTearDown(tester.view.reset);
  disableAnimations(tester);
  final env = await TestEnv.create(user: _user);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        appPreferencesProvider.overrideWithValue(env.preferences),
        secureStoreProvider.overrideWithValue(env.store),
        sessionProvider.overrideWith(_Session.new),
        ...overrides.cast(),
      ],
      child: MaterialApp(
        theme: AppTheme.dark,
        locale: const Locale('tr'),
        supportedLocales: AppLocalizations.supportedLocales,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        home: Scaffold(body: child),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

class _Ops implements FirebasePasswordOps {
  _Ops(this.providers);
  List<String>? providers;
  PasswordChangeFailure? failure;
  final changes = <String>[];
  @override
  Future<List<String>?> providerIds() async => providers;
  @override
  Future<void> changePassword({
    required String email,
    required String current,
    required String next,
  }) async {
    if (failure case final reason?) throw PasswordChangeException(reason);
    changes.add('$email:$current->$next');
  }
}

/// A transport that fails the test if the backend is called at all.
ApiClient _noBackend(List<String> calls) {
  final dio = Dio(BaseOptions(baseUrl: 'http://api.test/api/v1/'));
  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) {
        calls.add('${options.method} ${options.path}');
        handler.reject(
          DioException(requestOptions: options, message: 'no backend here'),
        );
      },
    ),
  );
  return ApiClient(dio);
}

void main() {
  // ====================================================== one route
  group('push and notification centre lead to the same screen', () {
    final cases = <String, (Map<String, dynamic>, String?)>{
      'appointment_booked': ({'appointment_id': _id}, '/appointments/$_id'),
      'appointment_reminder': (
        {'appointment_id': _id, 'minutes_before': '60'},
        '/appointments/$_id',
      ),
      'appointment_cancelled': ({'appointment_id': _id}, '/appointments/$_id'),
      'order_status_changed': ({'order_id': _id}, '/orders/$_id'),
      'payment_succeeded': ({'order_id': _id}, '/orders/$_id'),
      'payment_failed': ({'order_id': _id}, '/orders/$_id'),
      'refund_processed': ({'order_id': _id}, '/orders/$_id'),
      'new_chat_message': ({'conversation_id': _id}, '/consultations/$_id'),
      'ai_report_ready': ({'report_id': _id}, '/astro-ai/reports/$_id'),
      'subscription_expired': (<String, dynamic>{}, '/premium'),
      'call_missed': ({'call_id': _id}, '/calls/$_id'),
      'call_started': ({'conversation_id': _id}, null),
      'daily_content': (<String, dynamic>{}, null),
    };
    for (final entry in cases.entries) {
      test(entry.key, () {
        final (data, expected) = entry.value;
        final push = routeForPush({
          'event': entry.key,
          'notification_id': _id,
          ...data,
        });
        final inbox = notificationRoute(
          InboxNotification({
            'id': _id,
            'event': entry.key,
            'category': 'appointment',
            'created_at': '2026-09-28T10:00:00Z',
            'read': false,
            'data': {
              for (final item in data.entries) item.key: '${item.value}',
            },
          }),
        );
        expect(push, expected);
        expect(inbox, push);
      });
    }

    test('ids are validated, never passed through', () {
      expect(
        routeForNotification('new_chat_message', {'conversation_id': '../x'}),
        isNull,
      );
      expect(notificationIdOf({'notification_id': 'not-a-uuid'}), isNull);
      expect(notificationIdOf({'notification_id': _id}), _id);
    });
  });

  // ============================================= opened push = same record
  test('an opened push yields its route and its inbox record', () async {
    final gateway = _Gateway();
    final service = FirebasePushService(
      _Devices(),
      InMemorySecureStore(),
      gateway,
      Future.value(const FirebaseAvailability(FirebaseBootstrapStatus.ready)),
    );
    final routes = <String>[];
    final ids = <String>[];
    final a = service.routes.listen(routes.add);
    final b = service.openedNotificationIds.listen(ids.add);
    await service.startAfterAuth();
    gateway.taps.add({
      'event': 'refund_processed',
      'order_id': _id,
      'notification_id': '77777777-7777-4777-8777-777777777777',
    });
    // A call push has no inbox record: route only.
    gateway.taps.add({'event': 'call_missed', 'call_id': _id});
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(routes, ['/orders/$_id', '/calls/$_id']);
    expect(ids, ['77777777-7777-4777-8777-777777777777']);
    await a.cancel();
    await b.cancel();
    service.dispose();
    await gateway.close();
  });

  // ============================================ Firebase password change
  group('password change by sign-in method', () {
    test('a Firebase email account changes it in Firebase only', () async {
      final calls = <String>[];
      final ops = _Ops(['password']);
      final repo = ApiAccountRepository(_noBackend(calls), firebase: ops);
      expect((await repo.passwordCapability()).kind, PasswordKind.firebase);
      final revoked = await repo.changePassword(
        current: 'old-pass-1',
        next: 'NewPass-2026',
        email: 'nova@example.com',
      );
      expect(revoked, isFalse, reason: 'backend sessions are not touched');
      expect(ops.changes, ['nova@example.com:old-pass-1->NewPass-2026']);
      expect(calls, isEmpty, reason: 'never as a backend password');
    });

    test('Google/Apple accounts have no password to change', () async {
      final calls = <String>[];
      final repo = ApiAccountRepository(
        _noBackend(calls),
        firebase: _Ops(['google.com']),
      );
      final capability = await repo.passwordCapability();
      expect(capability.canChange, isFalse);
      expect(capability.provider, 'google.com');
      await expectLater(
        repo.changePassword(current: 'x', next: 'NewPass-2026', email: 'a@b.c'),
        throwsA(
          isA<PasswordChangeException>().having(
            (e) => e.reason,
            'reason',
            PasswordChangeFailure.unsupported,
          ),
        ),
      );
      expect(calls, isEmpty);
    });

    test('Firebase error codes map to what the screen says', () {
      expect(
        firebasePasswordFailure('invalid-credential'),
        PasswordChangeFailure.wrongCurrent,
      );
      expect(
        firebasePasswordFailure('wrong-password'),
        PasswordChangeFailure.wrongCurrent,
      );
      expect(
        firebasePasswordFailure('requires-recent-login'),
        PasswordChangeFailure.needsRecentLogin,
      );
      expect(
        firebasePasswordFailure('user-token-expired'),
        PasswordChangeFailure.needsRecentLogin,
      );
      expect(
        firebasePasswordFailure('weak-password'),
        PasswordChangeFailure.weak,
      );
      expect(
        firebasePasswordFailure('too-many-requests'),
        PasswordChangeFailure.rateLimited,
      );
      expect(
        firebasePasswordFailure('network-request-failed'),
        PasswordChangeFailure.network,
      );
    });

    testWidgets('a Google account sees where its sign-in lives, not a form', (
      tester,
    ) async {
      await _pump(
        tester,
        const ChangePasswordScreen(),
        overrides: [
          accountRepositoryProvider.overrideWithValue(
            _Account(
              capability: const PasswordCapability(
                PasswordKind.external,
                provider: 'google.com',
              ),
            ),
          ),
        ],
      );
      expect(find.byKey(const ValueKey('password-external')), findsOneWidget);
      expect(
        find.textContaining('Google ile giriş yapıyorsun'),
        findsOneWidget,
      );
      expect(find.byKey(const ValueKey('password-current')), findsNothing);
    });

    testWidgets('a recent-login requirement is said plainly', (tester) async {
      final repo = _Account(
        capability: const PasswordCapability(PasswordKind.firebase),
        failure: PasswordChangeFailure.needsRecentLogin,
      );
      await _pump(
        tester,
        const ChangePasswordScreen(),
        overrides: [accountRepositoryProvider.overrideWithValue(repo)],
      );
      await tester.enterText(
        find.byKey(const ValueKey('password-current')),
        'old-pass-1',
      );
      await tester.enterText(
        find.byKey(const ValueKey('password-new')),
        'NewPass-2026',
      );
      await tester.enterText(
        find.byKey(const ValueKey('password-confirm')),
        'NewPass-2026',
      );
      await tester.tap(find.byKey(const ValueKey('password-submit')));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('yeniden giriş yapman gerekiyor'),
        findsOneWidget,
      );
    });
  });

  // ============================================= settled answers
  test('a missing record is not fetched again and again', () {
    for (final kind in [
      ApiErrorKind.notFound,
      ApiErrorKind.forbidden,
      ApiErrorKind.unauthorized,
      ApiErrorKind.validation,
      ApiErrorKind.rateLimited,
    ]) {
      expect(apiRetry(0, ApiException(kind: kind)), isNull, reason: kind.name);
    }
    // A dropped connection or a 5xx still backs off and retries.
    expect(
      apiRetry(0, const ApiException(kind: ApiErrorKind.network)),
      isNotNull,
    );
    expect(
      apiRetry(0, const ApiException(kind: ApiErrorKind.server)),
      isNotNull,
    );
    expect(apiRetry(10, const ApiException(kind: ApiErrorKind.server)), isNull);
  });

  // ============================================ sessions
  testWidgets(
    'a Firebase sign-in is listed, managed by Firebase, never revocable',
    (tester) async {
      final repo = _Account(
        capability: const PasswordCapability(PasswordKind.firebase),
        rows: [
          AccountSession({
            'id': 'firebase:current',
            'kind': 'firebase',
            'revocable': false,
            'sign_in_provider': 'google.com',
            'current': true,
            'created_at': '2026-09-28T08:00:00Z',
            'last_used_at': '2026-09-28T10:00:00Z',
          }),
        ],
      );
      await _pump(
        tester,
        const SessionsScreen(),
        overrides: [accountRepositoryProvider.overrideWithValue(repo)],
      );
      expect(
        find.textContaining('Firebase ile giriş · Google'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Firebase tarafından yönetiliyor'),
        findsWidgets,
      );
      expect(
        find.byKey(const ValueKey('sessions-firebase-note')),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey('revoke-firebase:current')),
        findsNothing,
      );
    },
  );
}

// ------------------------------------------------------------------ fakes

class _Account extends Fake implements AccountRepository {
  _Account({required this.capability, this.failure, this.rows = const []});
  final PasswordCapability capability;
  final PasswordChangeFailure? failure;
  final List<AccountSession> rows;
  @override
  Future<PasswordCapability> passwordCapability() async => capability;
  @override
  Future<bool> changePassword({
    required String current,
    required String next,
    required String email,
  }) async {
    if (failure case final reason?) throw PasswordChangeException(reason);
    return false;
  }

  @override
  Future<List<AccountSession>> sessions() async => rows;
  @override
  Future<List<AccountDevice>> devices() async => [];
}

class _Devices extends Fake implements ConsultationRepository {
  @override
  Future<PushDevice> registerDevice({
    required String token,
    required String platform,
    String? deviceId,
    String? appVersion,
  }) async => PushDevice({'id': 'device-1', 'token_fingerprint': 'f'});
}

class _Gateway implements PushGateway {
  final refresh = StreamController<String>.broadcast();
  final taps = StreamController<Map<String, dynamic>>.broadcast();
  final messages = StreamController<Map<String, dynamic>>.broadcast();
  @override
  Future<bool> permissionGranted() async => true;
  @override
  Future<bool> requestPermission() async => true;
  @override
  Future<String?> token() async => List.filled(40, 'a').join();
  @override
  Stream<String> get tokenRefresh => refresh.stream;
  @override
  Stream<Map<String, dynamic>> get opened => taps.stream;
  @override
  Stream<Map<String, dynamic>> get foreground => messages.stream;
  @override
  Future<Map<String, dynamic>?> initialMessage() async => null;
  @override
  Future<void> deleteToken() async {}
  Future<void> close() async {
    await refresh.close();
    await taps.close();
    await messages.close();
  }
}
