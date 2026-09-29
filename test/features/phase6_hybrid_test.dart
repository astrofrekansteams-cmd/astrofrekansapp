// Phase 6: production is hybrid. Firebase accounts and server (local JWT)
// accounts both sign in, one email never becomes two profiles, and each kind
// of account resets its password where its password lives - with no fake
// "sent" when mail cannot go out.
import 'package:astrofrekans/core/config/firebase_client.dart';
import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/features/auth/application/session_controller.dart';
import 'package:astrofrekans/features/auth/presentation/widgets/social_auth_row.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/network/api_config.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/features/auth/data/identity_session.dart';
import 'package:astrofrekans/features/auth/data/password_reset_service.dart';
import 'package:astrofrekans/features/auth/domain/auth_repository.dart';
import 'package:astrofrekans/features/profile/domain/user_profile.dart';
import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _project = 'astrofrekans-prod';

/// The server: `auth/login` accepts only [serverPassword]; a Firebase
/// session for an address owned by a server account is refused with
/// `account_link_required` when [linkRefused].
class _Server {
  _Server({this.linkRefused = false});
  bool linkRefused;
  static const serverPassword = 'server-pass-1';
  final calls = <String>[];

  ApiClient client() {
    final dio = Dio(BaseOptions(baseUrl: 'http://api.test/api/v1/'));
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          calls.add(options.path);
          Response<dynamic> ok(Object data) => Response<dynamic>(
            requestOptions: options,
            statusCode: 200,
            data: data,
          );
          void fail(int status, String code) => handler.reject(
            DioException(
              requestOptions: options,
              type: DioExceptionType.badResponse,
              response: Response<dynamic>(
                requestOptions: options,
                statusCode: status,
                data: {
                  'error': {'code': code, 'message': code},
                },
              ),
            ),
          );
          switch (options.path) {
            case 'auth/capabilities':
              handler.resolve(
                ok({
                  'accepts_firebase_token': true,
                  'firebase_configured': true,
                  'firebase_project_id': _project,
                }),
              );
            case 'auth/firebase/session':
              linkRefused
                  ? fail(409, 'account_link_required')
                  : handler.resolve(ok({'user_id': 'u-firebase'}));
            case 'auth/login':
              (options.data as Map)['password'] == serverPassword
                  ? handler.resolve(
                      ok({
                        'access_token': 'local-access',
                        'refresh_token': 'local-refresh',
                        'token_type': 'Bearer',
                        'expires_at': '2026-09-28T12:00:00Z',
                        'refresh_expires_at': '2026-10-28T12:00:00Z',
                      }),
                    )
                  : fail(401, 'invalid_credentials');
            case 'users/me':
              handler.resolve(
                ok({
                  'id': 'u-1',
                  'email': 'nova@example.com',
                  'name': 'Nova',
                  'subscription_tier': 'free',
                }),
              );
            case 'birth-profiles/me':
              fail(404, 'birth_profile_missing');
            default:
              fail(404, 'not_found');
          }
        },
      ),
    );
    return ApiClient(dio);
  }
}

/// Firebase: [firebasePassword] signs in; anything else is
/// `invalid-credential`, or [error] when set.
class _Firebase extends FirebaseClient {
  _Firebase({this.error});
  String? error;
  static const firebasePassword = 'firebase-pass-1';
  bool signedIn = false;
  int signOuts = 0;
  int deletions = 0;
  late final _Auth _auth = _Auth(this);

  @override
  Future<FirebaseAuth> auth() async => _auth;
  @override
  Future<String?> token(bool forceRefresh) async =>
      signedIn ? 'firebase-id-token' : null;
  @override
  Future<void> signOut() async {
    signOuts++;
    signedIn = false;
  }
}

class _Auth extends Fake implements FirebaseAuth {
  _Auth(this.owner);
  final _Firebase owner;

  @override
  FirebaseApp get app => _App();

  @override
  User? get currentUser => owner.signedIn ? _User(owner) : null;

  @override
  Future<UserCredential> signInWithEmailAndPassword({
    required String email,
    required String password,
  }) async {
    if (owner.error case final code?) {
      throw FirebaseAuthException(code: code);
    }
    if (password != _Firebase.firebasePassword) {
      throw FirebaseAuthException(code: 'invalid-credential');
    }
    owner.signedIn = true;
    return _Credential();
  }

  @override
  Future<UserCredential> createUserWithEmailAndPassword({
    required String email,
    required String password,
  }) async {
    owner.signedIn = true;
    return _Credential();
  }
}

class _App extends Fake implements FirebaseApp {
  @override
  FirebaseOptions get options => const FirebaseOptions(
    apiKey: 'test',
    appId: '1:1:android:1',
    messagingSenderId: '1',
    projectId: _project,
  );
}

class _User extends Fake implements User {
  _User(this.owner);
  final _Firebase owner;
  @override
  Future<void> delete() async {
    owner.deletions++;
    owner.signedIn = false;
  }
}

class _Credential extends Fake implements UserCredential {}

void main() {
  group('hybrid sign-in', () {
    test('a Firebase account signs in with Firebase only', () async {
      final server = _Server();
      final firebase = _Firebase();
      final store = InMemorySecureStore();
      final adapter = HybridAuthAdapter(firebase, server.client(), store);
      final user = await adapter.signIn(
        email: 'nova@example.com',
        password: _Firebase.firebasePassword,
      );
      expect(user.id, 'u-1');
      expect(server.calls, isNot(contains('auth/login')));
      expect(await store.read(SecureKeys.refreshToken), isNull);
    });

    test('a server account (local JWT) signs in with the server', () async {
      final server = _Server();
      final store = InMemorySecureStore();
      final adapter = HybridAuthAdapter(_Firebase(), server.client(), store);
      final user = await adapter.signIn(
        email: 'expert@example.com',
        password: _Server.serverPassword,
      );
      expect(user.id, 'u-1');
      expect(server.calls, contains('auth/login'));
      expect(await store.read(SecureKeys.refreshToken), 'local-refresh');
    });

    test('an address owned by a server account never becomes a second '
        'profile', () async {
      // Firebase accepts the password, the server refuses to link: Firebase
      // is signed out again and the server account is the one used.
      final server = _Server(linkRefused: true);
      final firebase = _Firebase();
      final store = InMemorySecureStore();
      final adapter = HybridAuthAdapter(firebase, server.client(), store);
      await expectLater(
        adapter.signIn(
          email: 'expert@example.com',
          password: _Firebase.firebasePassword,
        ),
        throwsA(
          isA<AuthException>().having(
            (e) => e.kind,
            'kind',
            AuthFailureKind.invalidCredentials,
          ),
        ),
      );
      expect(firebase.signedIn, isFalse);
      expect(firebase.signOuts, greaterThan(0));
      expect(await store.read(SecureKeys.refreshToken), isNull);
    });

    test('wrong everywhere reads like wrong anywhere', () async {
      final server = _Server();
      final adapter = HybridAuthAdapter(
        _Firebase(),
        server.client(),
        InMemorySecureStore(),
      );
      await expectLater(
        adapter.signIn(email: 'a@b.c', password: 'nope-nope-1'),
        throwsA(
          isA<AuthException>().having(
            (e) => e.kind,
            'kind',
            AuthFailureKind.invalidCredentials,
          ),
        ),
      );
      expect(server.calls, contains('auth/login'));
    });

    test('a network failure is not a reason to try the other door', () async {
      final server = _Server();
      final adapter = HybridAuthAdapter(
        _Firebase(error: 'network-request-failed'),
        server.client(),
        InMemorySecureStore(),
      );
      await expectLater(
        adapter.signIn(email: 'a@b.c', password: 'whatever-1'),
        throwsA(
          isA<AuthException>().having(
            (e) => e.kind,
            'kind',
            AuthFailureKind.network,
          ),
        ),
      );
      expect(server.calls, isNot(contains('auth/login')));
    });

    test('registering an address that has a server account leaves no '
        'Firebase orphan and no second profile', () async {
      final firebase = _Firebase();
      final adapter = HybridAuthAdapter(
        firebase,
        _Server(linkRefused: true).client(),
        InMemorySecureStore(),
      );
      await expectLater(
        adapter.register(
          RegistrationRequest(
            name: 'Nova',
            email: 'expert@example.com',
            password: 'NewPass-2026',
            birthDate: DateTime(1991, 6, 6),
          ),
        ),
        throwsA(
          isA<AuthException>().having(
            (e) => e.kind,
            'kind',
            AuthFailureKind.emailInUse,
          ),
        ),
      );
      expect(firebase.deletions, 1);
      expect(firebase.signedIn, isFalse);
    });
  });

  group('social buttons in a production build (iOS)', () {
    Future<void> pump(WidgetTester tester, {required bool apple}) async {
      debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
      addTearDown(() => debugDefaultTargetPlatformOverride = null);
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            appEnvironmentProvider.overrideWithValue(
              AppEnvironment.parse(
                environment: 'production',
                dataSource: 'api',
                apiBaseUrl: 'https://api.astrofrekans.org',
                authMode: 'hybrid',
                enableAppleSignIn: apple,
              ),
            ),
            socialAuthServiceProvider.overrideWithValue(_Social()),
          ],
          child: MaterialApp(
            theme: AppTheme.dark,
            locale: const Locale('en'),
            supportedLocales: AppLocalizations.supportedLocales,
            localizationsDelegates: const [
              AppLocalizations.delegate,
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
            home: const Scaffold(body: SocialAuthRow()),
          ),
        ),
      );
    }

    testWidgets('Apple stays off until switched on; Google never shows', (
      tester,
    ) async {
      await pump(tester, apple: false);
      expect(find.textContaining('Apple'), findsNothing);
      expect(find.textContaining('Google'), findsNothing);

      await pump(tester, apple: true);
      expect(find.textContaining('Apple'), findsOneWidget);
      expect(find.textContaining('Google'), findsNothing);
      debugDefaultTargetPlatformOverride = null;
    });
  });

  group('password reset follows the account', () {
    test(
      'both kinds are asked; the answer depends on configuration only',
      () async {
        Future<PasswordResetRequestResult> ask(
          PasswordResetRequestResult firebase,
          PasswordResetRequestResult server,
        ) => HybridPasswordResetService(
          _Reset(firebase),
          _Reset(server),
        ).requestReset('a@b.c');

        const requested = PasswordResetRequestResult.requested;
        const unavailable = PasswordResetRequestResult.unavailable;
        expect(await ask(requested, requested), requested);
        // No SMTP: Firebase accounts still get Firebase's email; the screen
        // says server accounts cannot - never a plain "sent".
        expect(
          await ask(requested, unavailable),
          PasswordResetRequestResult.requestedFirebaseOnly,
        );
        expect(await ask(unavailable, unavailable), unavailable);
      },
    );

    test('a link in the app is a server link', () async {
      final server = _Reset(PasswordResetRequestResult.requested);
      final firebase = _Reset(PasswordResetRequestResult.requested);
      final hybrid = HybridPasswordResetService(firebase, server);
      expect(hybrid.completesInApp, isTrue);
      await hybrid.checkLink('t');
      await hybrid.resetPassword('t', 'NewPass-2026');
      expect(server.linkCalls, 2);
      expect(firebase.linkCalls, 0);
    });

    test('each build mode picks its reset path', () {
      PasswordResetService pick(String mode) {
        final container = ProviderContainer(
          overrides: [
            appEnvironmentProvider.overrideWithValue(
              AppEnvironment.parse(
                environment: 'staging',
                dataSource: 'api',
                apiBaseUrl: 'https://api.test',
                authMode: mode,
              ),
            ),
          ],
        );
        addTearDown(container.dispose);
        return container.read(passwordResetServiceProvider);
      }

      expect(pick('hybrid'), isA<HybridPasswordResetService>());
      expect(pick('firebase'), isA<FirebasePasswordResetService>());
      expect(pick('local_jwt'), isA<ApiPasswordResetService>());
    });
  });
}

class _Reset implements PasswordResetService {
  _Reset(this.result);
  final PasswordResetRequestResult result;
  int linkCalls = 0;
  @override
  bool get completesInApp => true;
  @override
  Future<PasswordResetRequestResult> requestReset(String email) async => result;
  @override
  Future<ResetLinkState> checkLink(String token) async {
    linkCalls++;
    return ResetLinkState.valid;
  }

  @override
  Future<void> resetPassword(String token, String newPassword) async =>
      linkCalls++;
}

/// Both providers configured: only the build's switches decide.
class _Social implements SocialAuthService {
  @override
  bool isAvailable(SocialProvider provider) => true;
  @override
  Future<UserProfile> authenticate(SocialProvider provider) =>
      throw UnimplementedError();
}
