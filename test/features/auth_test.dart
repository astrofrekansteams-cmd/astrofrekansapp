import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/features/auth/application/session_controller.dart';
import 'package:astrofrekans/features/auth/data/mock_auth_repository.dart';
import 'package:astrofrekans/features/auth/domain/auth_repository.dart';
import 'package:astrofrekans/features/auth/presentation/login_screen.dart';
import 'package:astrofrekans/features/profile/domain/user_profile.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('MockAuthRepository', () {
    late InMemorySecureStore store;
    late MockAuthRepository repository;

    setUp(() {
      store = InMemorySecureStore();
      repository = MockAuthRepository(store: store, latency: Duration.zero);
    });

    test('register persists a session and the profile', () async {
      final UserProfile profile = await repository.register(
        RegistrationRequest(
          name: 'Defne Yıldız',
          email: 'Defne@Astrofrekans.test',
          password: 'cok-gizli-123',
          birthDate: DateTime(1995, 3, 12),
          birthTime: '09:41',
          birthPlace: 'İstanbul',
        ),
      );

      expect(profile.email, 'defne@astrofrekans.test');
      expect(profile.birthTime, '09:41');
      expect(await store.read(SecureKeys.authToken), isNotNull);

      final UserProfile? restored = await repository.restoreSession();
      expect(restored?.id, profile.id);
      expect(restored?.birthPlace, 'İstanbul');
    });

    test('a wrong password for a known account is rejected', () async {
      await repository.register(
        RegistrationRequest(
          name: 'Defne',
          email: 'defne@astrofrekans.test',
          password: 'cok-gizli-123',
          birthDate: DateTime(1995, 3, 12),
        ),
      );

      expect(
        () => repository.signIn(
          email: 'defne@astrofrekans.test',
          password: 'yanlis-sifre',
        ),
        throwsA(
          isA<AuthException>().having(
            (AuthException e) => e.kind,
            'kind',
            AuthFailureKind.invalidCredentials,
          ),
        ),
      );
    });

    test('sign out clears the stored session', () async {
      await repository.register(
        RegistrationRequest(
          name: 'Defne',
          email: 'defne@astrofrekans.test',
          password: 'cok-gizli-123',
          birthDate: DateTime(1995, 3, 12),
        ),
      );
      await repository.signOut();

      expect(await store.read(SecureKeys.authToken), isNull);
      expect(await repository.restoreSession(), isNull);
    });
  });

  test('social auth stays disabled until credentials exist', () async {
    const SocialAuthService service = UnconfiguredSocialAuthService();
    expect(service.isAvailable(SocialProvider.google), isFalse);
    expect(service.isAvailable(SocialProvider.apple), isFalse);
    expect(
      () => service.authenticate(SocialProvider.google),
      throwsA(isA<AuthException>()),
    );
  });

  testWidgets('login validates the form before calling the repository', (
    WidgetTester tester,
  ) async {
    final TestEnv env = await TestEnv.create(
      preferences: <String, Object>{'onboarding_seen': true},
    );
    await pumpScreen(tester, const LoginScreen(), env: env);

    await tester.enterText(find.byType(TextFormField).first, 'not-an-email');
    await tester.enterText(find.byType(TextFormField).last, '123');
    await tester.tap(find.text('Giriş Yap'));
    await tester.pumpAndSettle();

    expect(find.text('Geçerli bir e-posta gir.'), findsOneWidget);
    expect(find.text('Şifre en az 8 karakter olmalı.'), findsOneWidget);
  });

  testWidgets('a valid sign-in flips the session to authenticated', (
    WidgetTester tester,
  ) async {
    final TestEnv env = await TestEnv.create(
      preferences: <String, Object>{'onboarding_seen': true},
    );
    late WidgetRef capturedRef;

    await pumpScreen(
      tester,
      Consumer(
        builder: (BuildContext context, WidgetRef ref, Widget? _) {
          capturedRef = ref;
          return const LoginScreen();
        },
      ),
      env: env,
    );

    await tester.enterText(
      find.byType(TextFormField).first,
      'defne@astrofrekans.test',
    );
    await tester.enterText(find.byType(TextFormField).last, 'cok-gizli-123');
    await tester.tap(find.text('Giriş Yap'));
    await tester.pumpAndSettle();

    final SessionState session = capturedRef.read(sessionProvider);
    expect(session.status, SessionStatus.authenticated);
    expect(session.user?.email, 'defne@astrofrekans.test');
  });
}
