// Phase 2: the user app, completed. Account centre, notification centre,
// language, settings rollback, midnight, time zones, premium states, saved
// people, expert search and the profile menu.
import 'dart:convert';
import 'dart:typed_data';

import 'package:astrofrekans/core/astrology/astrology_providers.dart';
import 'package:astrofrekans/core/astrology/data/mock_astrology_service.dart';
import 'package:astrofrekans/core/astrology/data/api_contract_dto.dart';
import 'package:astrofrekans/core/astrology/data/production_models.dart';
import 'package:astrofrekans/core/astrology/data/production_repository.dart';
import 'package:astrofrekans/core/astrology/domain/saved_person.dart';
import 'package:astrofrekans/core/localization/locale_controller.dart';
import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/network/auth_interceptor.dart';
import 'package:astrofrekans/core/network/token_storage.dart';
import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/core/storage/app_preferences.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/features/auth/application/session_controller.dart';
import 'package:astrofrekans/features/auth/data/api_auth_repository.dart';
import 'package:astrofrekans/features/auth/data/auth_dto.dart';
import 'package:astrofrekans/features/auth/domain/auth_repository.dart';
import 'package:astrofrekans/features/billing/application/entitlement_controller.dart';
import 'package:astrofrekans/features/billing/data/billing_models.dart';
import 'package:astrofrekans/features/billing/data/billing_repository.dart';
import 'package:astrofrekans/features/billing/data/billing_service.dart';
import 'package:astrofrekans/features/billing/data/coin_repository.dart';
import 'package:astrofrekans/features/billing/presentation/premium_screen.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_models.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_repository.dart';
import 'package:astrofrekans/features/notifications/data/notification_repository.dart';
import 'package:astrofrekans/features/notifications/presentation/notification_center_screen.dart';
import 'package:astrofrekans/features/production/presentation/profile_data_screens.dart';
import 'package:astrofrekans/features/profile/data/account_repository.dart';
import 'package:astrofrekans/features/profile/domain/user_profile.dart';
import 'package:astrofrekans/features/profile/presentation/account_center_screens.dart';
import 'package:astrofrekans/features/profile/presentation/profile_screen.dart';
import 'package:astrofrekans/features/profile/presentation/profile_settings_screens.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';

final _user = UserProfile(
  id: 'u1',
  name: 'Nova Star',
  email: 'nova@example.com',
  birthDate: DateTime(1992, 5, 14),
  birthTime: '14:30',
  birthPlace: 'İstanbul',
  timezone: 'Asia/Baku',
  birthTimezone: 'Europe/Istanbul',
);

Future<void> _pump(
  WidgetTester tester,
  Widget child, {
  List<Object> overrides = const [],
  UserProfile? user,
  Size size = const Size(420, 2600),
}) async {
  tester.view.physicalSize = size * tester.view.devicePixelRatio;
  addTearDown(tester.view.reset);
  disableAnimations(tester);
  final env = await TestEnv.create(user: user ?? _user);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        appPreferencesProvider.overrideWithValue(env.preferences),
        secureStoreProvider.overrideWithValue(env.store),
        astrologyServiceProvider.overrideWithValue(
          MockAstrologyService(latency: Duration.zero),
        ),
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

/// A signed-in session whose saves can be made to fail.
class _Session extends SignedInSessionController {
  _Session({this.failures = 0}) : super(_user);
  int failures;
  final patches = <Map<String, Object?>>[];
  final languages = <String>[];
  @override
  Future<void> customizeProfile(Map<String, Object?> patch) async {
    patches.add(patch);
    if (failures > 0) {
      failures--;
      throw const ApiException(kind: ApiErrorKind.network);
    }
  }

  @override
  Future<void> setLanguage(Locale locale) async =>
      languages.add(locale.languageCode);
}

void main() {
  // ============================================================ midnight
  group('day rollover', () {
    testWidgets('23:59 -> 00:00 moves "today" and reloads daily content', (
      tester,
    ) async {
      var now = DateTime(2026, 9, 27, 23, 59, 58);
      var loads = 0;
      final dailyContent = FutureProvider<String>((ref) async {
        loads++;
        return ref.watch(todayProvider).toIso8601String().substring(0, 10);
      });
      await tester.pumpWidget(
        ProviderScope(
          overrides: [clockProvider.overrideWithValue(() => now)],
          child: MaterialApp(
            home: Consumer(
              builder: (context, ref, _) => Text(
                ref.watch(dailyContent).asData?.value ?? '…',
                textDirection: TextDirection.ltr,
              ),
            ),
          ),
        ),
      );
      await tester.pump();
      expect(find.text('2026-09-27'), findsOneWidget);

      now = DateTime(2026, 9, 28, 0, 0, 3);
      await tester.pump(const Duration(seconds: 5)); // the midnight timer
      await tester.pump();
      expect(find.text('2026-09-28'), findsOneWidget);
      expect(loads, 2);

      // The phone slept through the next midnight: resume checks the date.
      now = DateTime(2026, 9, 29, 8);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();
      await tester.pump();
      expect(find.text('2026-09-29'), findsOneWidget);
      expect(loads, 3);
      await tester.pumpWidget(const SizedBox.shrink());
    });
  });

  // ============================================================ settings
  group('settings rollback', () {
    testWidgets('a toggle that fails to save goes back and offers retry', (
      tester,
    ) async {
      final session = _Session(failures: 1);
      await _pump(
        tester,
        const NotificationSettingsScreen(),
        overrides: [sessionProvider.overrideWith(() => session)],
      );
      SwitchListTile tile() => tester.widget<SwitchListTile>(
        find.byKey(const ValueKey('flag-ai_reports')),
      );
      expect(tile().value, isTrue);
      await tester.tap(find.byKey(const ValueKey('flag-ai_reports')));
      await tester.pumpAndSettle();
      // Not saved: the switch shows what the server has.
      expect(tile().value, isTrue);
      expect(find.byKey(const ValueKey('flag-save-error')), findsOneWidget);
      expect(
        session.patches.single['notification_prefs'],
        containsPair('ai_reports', false),
      );

      await tester.tap(find.text('Tekrar dene'));
      await tester.pumpAndSettle();
      expect(tile().value, isFalse);
      expect(session.patches, hasLength(2));
      expect(find.byKey(const ValueKey('flag-save-error')), findsNothing);
    });
  });

  // ============================================================ language
  group('language', () {
    testWidgets('only supported languages are offered', (tester) async {
      await _pump(
        tester,
        const ProfileCustomizeScreen(),
        overrides: [sessionProvider.overrideWith(_Session.new)],
      );
      expect(find.text('Türkçe'), findsOneWidget);
      expect(find.text('English'), findsOneWidget);
      expect(find.text('Azərbaycan'), findsNothing);
    });

    test(
      'app and account language move together; a failed save reverts',
      () async {
        final env = await TestEnv.create(user: _user);
        final auth = _Auth()..user = _user.copyWith(language: 'tr');
        final container = ProviderContainer.test(
          overrides: [
            appPreferencesProvider.overrideWithValue(env.preferences),
            secureStoreProvider.overrideWithValue(env.store),
            authRepositoryProvider.overrideWithValue(auth),
          ],
        );
        final session = container.read(sessionProvider.notifier);
        await session.signIn(email: 'nova@example.com', password: 'x');
        await Future<void>.delayed(Duration.zero);
        expect(container.read(localeControllerProvider).languageCode, 'tr');

        await session.setLanguage(const Locale('en'));
        expect(container.read(localeControllerProvider).languageCode, 'en');
        expect(auth.patches.last, {'language': 'en'});
        expect(container.read(currentUserProvider)!.language, 'en');

        auth.fail = true;
        await expectLater(
          session.setLanguage(const Locale('tr')),
          throwsA(isA<ApiException>()),
        );
        expect(container.read(localeControllerProvider).languageCode, 'en');

        // Signing in applies the account's language to the app.
        auth
          ..fail = false
          ..user = _user.copyWith(language: 'tr');
        await session.signIn(email: 'nova@example.com', password: 'x');
        await Future<void>.delayed(Duration.zero);
        expect(container.read(localeControllerProvider).languageCode, 'tr');
      },
    );
  });

  // ============================================================ time zones
  group('time zones', () {
    test('the birth zone and the zone the person lives in stay apart', () {
      final profile =
          UserDto.fromJson({
            'id': 'u1',
            'email': 'nova@example.com',
            'name': 'Nova',
            'subscription_tier': 'free',
            'timezone': 'Asia/Baku',
            'language': 'tr',
          }).toDomain(
            birth: BirthProfileDto.fromJson({
              'id': 'b1',
              'birth_date': '1992-05-14',
              'birth_time': '14:30:00',
              'birth_time_known': true,
              'birth_place': 'İstanbul',
              'latitude': 41.0,
              'longitude': 29.0,
              'timezone': 'Europe/Istanbul',
              'house_system': 'placidus',
              'is_primary': true,
              'can_compute_houses': true,
              'updated_at': '2026-09-01T00:00:00Z',
            }),
          );
      expect(profile.timezone, 'Asia/Baku');
      expect(profile.birthTimezone, 'Europe/Istanbul');
      expect(profile.birthData!.timezone, 'Europe/Istanbul');
    });

    test('editing birth data never touches the account zone', () async {
      final requests = <RequestOptions>[];
      final dio = Dio(BaseOptions(baseUrl: 'http://api.test/api/v1/'))
        ..httpClientAdapter = _Adapter((options) async {
          requests.add(options);
          if (options.path.endsWith('users/me')) {
            return _json({
              'id': 'u1',
              'email': 'nova@example.com',
              'name': 'Nova',
              'subscription_tier': 'free',
              'timezone': 'Asia/Baku',
            });
          }
          return _json({
            'id': 'b1',
            'birth_date': '1992-05-14',
            'birth_time': '14:30:00',
            'birth_time_known': true,
            'birth_place': 'Ankara',
            'timezone': 'Europe/Istanbul',
            'house_system': 'placidus',
            'is_primary': true,
            'can_compute_houses': true,
            'updated_at': '2026-09-01T00:00:00Z',
          });
        });
      final repo = ApiAuthRepository(ApiClient(dio), InMemorySecureStore({}));
      final updated = await repo.updateBirthData(
        _user.copyWith(birthPlace: 'Ankara', birthTimezone: 'Europe/Istanbul'),
      );
      final writes = requests.where((r) => r.method != 'GET').toList();
      expect(writes.map((r) => '${r.method} ${r.path}'), [
        'PUT birth-profiles/me',
      ]);
      expect((writes.single.data as Map)['timezone'], 'Europe/Istanbul');
      expect(updated.timezone, 'Asia/Baku');
    });

    testWidgets('the birth form shows the birth zone, not the current one', (
      tester,
    ) async {
      await _pump(
        tester,
        const ProfileEditScreen(),
        overrides: [sessionProvider.overrideWith(_Session.new)],
      );
      expect(find.byKey(const ValueKey('birth-data-form')), findsOneWidget);
      expect(find.text('Europe/Istanbul', skipOffstage: false), findsWidgets);
      expect(find.text('Asia/Baku', skipOffstage: false), findsNothing);
    });
  });

  // ============================================================ premium
  group('premium catalogue', () {
    Future<void> pumpPremium(WidgetTester tester, Object catalog) async {
      final controller = EntitlementController(
        _FreeBilling(),
        const DisabledBillingService(),
      );
      await controller.start();
      addTearDown(controller.dispose);
      await _pump(
        tester,
        const PremiumScreen(),
        overrides: [
          entitlementControllerProvider.overrideWithValue(controller),
          catalog,
        ],
      );
    }

    testWidgets('a failed catalogue says so and retries', (tester) async {
      var failing = true;
      await pumpPremium(
        tester,
        coinCatalogProvider.overrideWith((ref) async {
          if (failing) throw const ApiException(kind: ApiErrorKind.network);
          return null;
        }),
      );
      expect(find.byKey(const ValueKey('plans-error')), findsOneWidget);
      expect(find.text('Planlar yüklenemedi.'), findsOneWidget);
      expect(find.byKey(const ValueKey('plans-loading')), findsNothing);
      failing = false;
      await tester.ensureVisible(find.byKey(const ValueKey('plans-retry')));
      await tester.tap(find.byKey(const ValueKey('plans-retry')));
      await tester.pumpAndSettle();
      // The retry answered with nothing: an empty state, not a skeleton.
      expect(find.byKey(const ValueKey('plans-empty')), findsOneWidget);
    });
  });

  // ============================================================ people
  group('saved people', () {
    testWidgets('a saved person can be edited, including "time unknown"', (
      tester,
    ) async {
      final repo = _Production();
      await _pump(
        tester,
        const SavedPeopleScreen(),
        overrides: [productionRepositoryProvider.overrideWithValue(repo)],
      );
      expect(find.textContaining('düzenleme desteklen'), findsNothing);
      await tester.tap(find.byKey(const ValueKey('edit-p1')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('edit-person-p1')), findsOneWidget);
      expect(find.text('Deniz'), findsOneWidget);
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Deniz'),
        'Deniz Y.',
      );
      await tester.tap(find.byType(Switch).first);
      await tester.pump();
      final save = find.descendant(
        of: find.byKey(const ValueKey('edit-person-p1')),
        matching: find.text('Kaydet'),
      );
      await tester.ensureVisible(save);
      await tester.tap(save);
      await tester.pumpAndSettle();
      final change = repo.updates.single;
      expect(change.$1, 'p1');
      expect(change.$2['name'], 'Deniz Y.');
      expect(change.$2.containsKey('birth_time'), isTrue);
      expect(change.$2['birth_time'], isNull);
      expect(change.$2['birth_date'], '1994-08-21');
    });
  });

  // ============================================================ notifications
  group('notification centre', () {
    testWidgets('lists, marks read/unread, reads all and filters', (
      tester,
    ) async {
      final repo = _Inbox();
      await _pump(
        tester,
        const NotificationCenterScreen(),
        overrides: [notificationRepositoryProvider.overrideWithValue(repo)],
      );
      expect(find.text('Randevun oluşturuldu'), findsOneWidget);
      expect(find.text('İaden işlendi'), findsOneWidget);
      expect(find.byKey(const ValueKey('unread-n1')), findsOneWidget);
      expect(find.byKey(const ValueKey('unread-n2')), findsNothing);

      await tester.tap(find.byKey(const ValueKey('toggle-read-n1')));
      await tester.pumpAndSettle();
      expect(repo.marks, ['n1:true']);
      expect(find.byKey(const ValueKey('unread-n1')), findsNothing);
      await tester.tap(find.byKey(const ValueKey('toggle-read-n2')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('unread-n2')), findsOneWidget);

      await tester.tap(find.byKey(const ValueKey('notifications-read-all')));
      await tester.pumpAndSettle();
      expect(repo.readAllCalls, 1);
      expect(find.byKey(const ValueKey('unread-n2')), findsNothing);

      await tester.ensureVisible(
        find.byKey(const ValueKey('notif-filter-payment')),
      );
      await tester.tap(find.byKey(const ValueKey('notif-filter-payment')));
      await tester.pumpAndSettle();
      expect(repo.categories.last, NotificationCategory.payment);
    });

    test('a notification leads to its screen by id', () {
      // Real ids are UUIDs; the inbox validates them like a push does.
      const id = '55555555-5555-4555-8555-555555555555';
      InboxNotification n(String event, Map<String, String> data) =>
          InboxNotification({
            'id': 'x',
            'event': event,
            'category': 'appointment',
            'created_at': '2026-09-27T10:00:00Z',
            'read': false,
            'data': data,
          });
      expect(
        notificationRoute(n('appointment_booked', {'appointment_id': id})),
        '/appointments/$id',
      );
      expect(
        notificationRoute(n('refund_processed', {'order_id': id})),
        '/orders/$id',
      );
      expect(
        notificationRoute(n('new_chat_message', {'conversation_id': id})),
        '/consultations/$id',
      );
      expect(
        notificationRoute(n('ai_report_ready', {'report_id': id})),
        '/astro-ai/reports/$id',
      );
      expect(notificationRoute(n('subscription_expired', {})), '/premium');
    });
  });

  // ============================================================ account centre
  group('account centre', () {
    testWidgets('deletion is blocked while services are open', (tester) async {
      final repo = _Account()
        ..check = {
          'allowed': false,
          'requires_password': true,
          'live_appointments': 1,
          'open_orders': 1,
        };
      await _pump(
        tester,
        const DeleteAccountScreen(),
        overrides: [accountRepositoryProvider.overrideWithValue(repo)],
      );
      expect(find.byKey(const ValueKey('delete-blocked')), findsOneWidget);
      expect(find.textContaining('1 aktif randevu'), findsOneWidget);
      expect(find.byKey(const ValueKey('delete-submit')), findsNothing);
    });

    testWidgets('deletion needs the password, a tick and a confirmation', (
      tester,
    ) async {
      final repo = _Account();
      final session = _DeletingSession();
      await _pump(
        tester,
        const DeleteAccountScreen(),
        overrides: [
          accountRepositoryProvider.overrideWithValue(repo),
          sessionProvider.overrideWith(() => session),
        ],
      );
      FilledButton submit() => tester.widget<FilledButton>(
        find.byKey(const ValueKey('delete-submit')),
      );
      expect(submit().onPressed, isNull);
      await tester.enterText(
        find.byKey(const ValueKey('delete-secret')),
        'Str0ngPassphrase!',
      );
      await tester.pump();
      expect(submit().onPressed, isNull);
      await tester.tap(find.byKey(const ValueKey('delete-understood')));
      await tester.pump();
      await tester.tap(find.byKey(const ValueKey('delete-submit')));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('delete-confirm-dialog')),
        findsOneWidget,
      );
      expect(repo.deletions, isEmpty);
      await tester.tap(find.byKey(const ValueKey('delete-confirm-yes')));
      await tester.pumpAndSettle();
      expect(repo.deletions, ['password:Str0ngPassphrase!']);
      expect(session.deleted, isTrue);
    });

    testWidgets('a wrong current password is said plainly', (tester) async {
      final repo = _Account()
        ..passwordFailure = PasswordChangeFailure.wrongCurrent;
      await _pump(
        tester,
        const ChangePasswordScreen(),
        overrides: [
          accountRepositoryProvider.overrideWithValue(repo),
          sessionProvider.overrideWith(_Session.new),
        ],
      );
      await tester.enterText(
        find.byKey(const ValueKey('password-current')),
        'old-password',
      );
      await tester.enterText(
        find.byKey(const ValueKey('password-new')),
        'NewPassword99',
      );
      await tester.enterText(
        find.byKey(const ValueKey('password-confirm')),
        'NewPassword99',
      );
      await tester.tap(find.byKey(const ValueKey('password-submit')));
      await tester.pumpAndSettle();
      expect(find.text('Mevcut şifre hatalı.'), findsOneWidget);
    });

    testWidgets('a changed password signs straight back in', (tester) async {
      final repo = _Account();
      final session = _DeletingSession();
      await _pump(
        tester,
        const ChangePasswordScreen(),
        overrides: [
          accountRepositoryProvider.overrideWithValue(repo),
          sessionProvider.overrideWith(() => session),
        ],
      );
      await tester.enterText(
        find.byKey(const ValueKey('password-current')),
        'old-password',
      );
      await tester.enterText(
        find.byKey(const ValueKey('password-new')),
        'NewPassword99',
      );
      await tester.enterText(
        find.byKey(const ValueKey('password-confirm')),
        'NewPassword99',
      );
      await tester.tap(find.byKey(const ValueKey('password-submit')));
      await tester.pumpAndSettle();
      expect(repo.passwordChanges, ['old-password->NewPassword99']);
      expect(session.reauth, 'NewPassword99');
      expect(find.byKey(const ValueKey('password-changed')), findsOneWidget);
    });

    testWidgets('sessions: this device is marked, others can be signed out', (
      tester,
    ) async {
      final repo = _Account();
      await _pump(
        tester,
        const SessionsScreen(),
        overrides: [accountRepositoryProvider.overrideWithValue(repo)],
      );
      expect(find.textContaining('Bu cihaz'), findsOneWidget);
      expect(find.byKey(const ValueKey('revoke-s1')), findsNothing);
      await tester.tap(find.byKey(const ValueKey('revoke-s2')));
      await tester.pumpAndSettle();
      expect(repo.revoked, ['s2']);
    });

    testWidgets('account centre sections, each on its own screen', (
      tester,
    ) async {
      await _pump(tester, const AccountCenterScreen());
      for (final key in [
        'account-info',
        'account-birth',
        'account-password',
        'account-sessions',
        'account-privacy',
        'account-delete',
      ]) {
        expect(find.byKey(ValueKey(key)), findsOneWidget, reason: key);
      }
    });
  });

  // ============================================================ re-auth
  group('re-authentication over the real transport', () {
    test('a wrong current password is an error, never a sign-out', () async {
      var expired = 0;
      final requests = <String>[];
      final dio = Dio(BaseOptions(baseUrl: 'http://api.test/api/v1/'));
      final store = InMemorySecureStore({
        'auth_token': 'access-1',
        'refresh_token': 'refresh-1',
      });
      dio
        ..interceptors.add(
          AuthInterceptor(
            dio,
            Dio(BaseOptions(baseUrl: 'http://api.test/api/v1/')),
            SecureTokenStorage(store),
            () async => expired++,
          ),
        )
        ..httpClientAdapter = _Adapter((options) async {
          requests.add('${options.method} ${options.path}');
          return ResponseBody.fromString(
            jsonEncode({
              'error': {
                'code': 'current_password_incorrect',
                'message': 'The current password is incorrect.',
              },
            }),
            403,
            headers: {
              'content-type': ['application/json'],
            },
          );
        });
      final repo = ApiAccountRepository(ApiClient(dio));
      await expectLater(
        repo.changePassword(
          current: 'typo',
          next: 'NewPassword99',
          email: 'a@b.c',
        ),
        throwsA(
          isA<PasswordChangeException>().having(
            (e) => e.reason,
            'reason',
            PasswordChangeFailure.wrongCurrent,
          ),
        ),
      );
      await expectLater(
        repo.deleteAccount(password: 'typo'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'current_password_incorrect',
          ),
        ),
      );
      // No refresh attempt, no retry, no session expiry.
      expect(requests, ['POST auth/change-password', 'POST users/me/delete']);
      expect(expired, 0);
      expect(await store.read('auth_token'), 'access-1');
    });
  });

  // ============================================================ profile menu
  group('profile menu', () {
    Future<List<String>> order(WidgetTester tester) async => [
      for (final key in [
        'menu-plan',
        'menu-profile',
        'menu-account-center',
        'menu-birth',
        'menu-privacy',
        'menu-appointments',
        'menu-orders',
        'menu-messages',
        'menu-reports',
        'menu-coins',
        'menu-notifications',
        'menu-settings',
        'menu-sign-out',
      ])
        if (find.byKey(ValueKey(key)).evaluate().isNotEmpty) key,
    ];

    testWidgets('grouped, sign-out last, no expert row for a user', (
      tester,
    ) async {
      await _pump(
        tester,
        const ProfileScreen(),
        overrides: [
          marketplaceRepositoryProvider.overrideWithValue(
            _Market(expert: false),
          ),
          sessionProvider.overrideWith(_Session.new),
        ],
      );
      final keys = await order(tester);
      expect(keys.length, 13);
      double y(String key) => tester.getTopLeft(find.byKey(ValueKey(key))).dy;
      for (var i = 1; i < keys.length; i++) {
        expect(y(keys[i]), greaterThan(y(keys[i - 1])), reason: keys[i]);
      }
      expect(find.text('HESABIM'), findsOneWidget);
      expect(find.text('HİZMETLERİM'), findsOneWidget);
      expect(find.byKey(const ValueKey('menu-expert')), findsNothing);
    });

    testWidgets('an expert sees the workspace in its own section', (
      tester,
    ) async {
      await _pump(
        tester,
        const ProfileScreen(),
        overrides: [
          marketplaceRepositoryProvider.overrideWithValue(
            _Market(expert: true),
          ),
          sessionProvider.overrideWith(_Session.new),
        ],
      );
      expect(find.byKey(const ValueKey('menu-expert')), findsOneWidget);
      expect(
        tester.getTopLeft(find.byKey(const ValueKey('menu-expert'))).dy,
        lessThan(
          tester.getTopLeft(find.byKey(const ValueKey('menu-sign-out'))).dy,
        ),
      );
    });
  });
}

// ------------------------------------------------------------------ fakes

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

ResponseBody _json(Object value) => ResponseBody.fromString(
  jsonEncode(value),
  200,
  headers: {
    'content-type': ['application/json'],
  },
);

class _Auth extends Fake implements AuthRepository {
  UserProfile? user;
  bool fail = false;
  final patches = <Map<String, Object?>>[];
  @override
  Future<UserProfile> signIn({
    required String email,
    required String password,
  }) async => user!;
  @override
  Future<UserProfile> customizeProfile(Map<String, Object?> patch) async {
    patches.add(patch);
    if (fail) throw const ApiException(kind: ApiErrorKind.network);
    user = user!.copyWith(
      language: patch['language'] as String? ?? user!.language,
    );
    return user!;
  }
}

class _DeletingSession extends SignedInSessionController {
  _DeletingSession() : super(_user);
  bool deleted = false;
  String? reauth;
  @override
  Future<void> afterAccountDeleted() async => deleted = true;
  @override
  Future<void> afterPasswordChange({
    required bool sessionsRevoked,
    required String newPassword,
  }) async {
    if (sessionsRevoked) reauth = newPassword;
  }
}

class _Account extends Fake implements AccountRepository {
  Map<String, Object?> check = {'allowed': true, 'requires_password': true};
  PasswordChangeFailure? passwordFailure;
  final deletions = <String>[],
      passwordChanges = <String>[],
      revoked = <String>[];
  @override
  Future<DeletionCheck> deletionCheck() async =>
      DeletionCheck(Map<String, dynamic>.of(check));
  @override
  Future<void> deleteAccount({String? password, String? confirmEmail}) async =>
      deletions.add(
        password != null ? 'password:$password' : 'email:$confirmEmail',
      );
  @override
  Future<bool> changePassword({
    required String current,
    required String next,
    required String email,
  }) async {
    if (passwordFailure case final failure?) {
      throw PasswordChangeException(failure);
    }
    passwordChanges.add('$current->$next');
    return true;
  }

  @override
  Future<List<AccountSession>> sessions() async => [
    AccountSession({
      'id': 's1',
      'current': true,
      'user_agent': 'Astrofrekans/1.0 (Android 15)',
      'ip_hint': '85.105.x.x',
      'last_used_at': '2026-09-27T10:00:00Z',
      'created_at': '2026-09-20T10:00:00Z',
    }),
    AccountSession({
      'id': 's2',
      'current': false,
      'user_agent': 'Astrofrekans/1.0 (iPad)',
      'last_used_at': '2026-09-26T10:00:00Z',
      'created_at': '2026-09-10T10:00:00Z',
    }),
  ];
  @override
  Future<void> revokeSession(String id) async => revoked.add(id);
  @override
  Future<List<AccountDevice>> devices() async => [];
}

class _Inbox implements NotificationRepository {
  final marks = <String>[];
  final categories = <NotificationCategory?>[];
  int readAllCalls = 0;
  Map<String, dynamic> _item(
    String id,
    String event,
    String category,
    bool read,
  ) => {
    'id': id,
    'event': event,
    'category': category,
    'created_at': '2026-09-27T10:00:00Z',
    'read': read,
    'data': {'order_id': 'o1'},
  };
  @override
  Future<InboxPage> list({
    String? before,
    NotificationCategory? category,
  }) async {
    categories.add(category);
    return InboxPage({
      'items': [
        _item('n1', 'appointment_booked', 'appointment', false),
        _item('n2', 'refund_processed', 'payment', true),
      ],
      'unread_count': 1,
    });
  }

  @override
  Future<int> unreadCount() async => 1;
  @override
  Future<InboxNotification> setRead(String id, {required bool read}) async {
    marks.add('$id:$read');
    return InboxNotification({
      ..._item(
        id,
        id == 'n1' ? 'appointment_booked' : 'refund_processed',
        'appointment',
        read,
      ),
    });
  }

  @override
  Future<void> readAll() async => readAllCalls++;
}

class _Production extends Fake implements ProductionRepository {
  final updates = <(String, Json)>[];
  @override
  Future<List<SavedPerson>> savedPeople() async => [
    SavedPerson(
      id: 'p1',
      name: 'Deniz',
      relationship: 'partner',
      birthDate: DateTime(1994, 8, 21),
      birthTime: '09:45',
      birthTimeKnown: true,
      birthPlace: 'London',
      timezone: 'Europe/London',
      houseSystem: 'placidus',
      createdAt: DateTime(2026, 9, 1),
    ),
  ];
  @override
  Future<SavedPerson> updatePerson(String id, Json changes) async {
    updates.add((id, changes));
    return (await savedPeople()).single;
  }
}

class _Market extends Fake implements MarketplaceRepository {
  _Market({required this.expert});
  final bool expert;
  @override
  Future<Expert> ownProfile() async {
    if (!expert) throw const ApiException(kind: ApiErrorKind.notFound);
    return Expert({'id': 'e1', 'display_name': 'Nova Astro'});
  }
}

class _FreeBilling extends Fake implements BillingRepository {
  @override
  Future<EntitlementSummary> entitlements() async => EntitlementSummary({
    'tier': 'free',
    'premium': false,
    'credits': <String, dynamic>{},
    'items': <dynamic>[],
  });
  @override
  Future<BillingAvailability> availability() async => BillingAvailability({
    'apple_configured': false,
    'google_configured': false,
    'external_marketplace_configured': false,
  });
}
