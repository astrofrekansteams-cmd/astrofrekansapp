import 'package:firebase_auth/firebase_auth.dart';

import '../../../core/config/firebase_client.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/storage/secure_storage.dart';
import '../../profile/domain/user_profile.dart';
import '../domain/auth_repository.dart';
import 'api_auth_repository.dart';

/// UI-facing identity contract, independent of the bearer-token issuer.
abstract interface class IdentitySession implements AuthRepository {}

class LocalJwtAuthAdapter extends ApiAuthRepository implements IdentitySession {
  const LocalJwtAuthAdapter(super.api, super.store);
}

class FirebaseAuthAdapter implements IdentitySession {
  const FirebaseAuthAdapter(this.client, this.api, this.store);
  final FirebaseClient client;
  final ApiClient api;
  final SecureStore store;
  ApiAuthRepository get _profiles => ApiAuthRepository(api, store);

  Future<UserProfile> _mapUser() async {
    final capabilities = await api.getMap('auth/capabilities');
    if (capabilities['accepts_firebase_token'] != true ||
        capabilities['firebase_configured'] != true ||
        capabilities['firebase_project_id'] !=
            (await client.auth()).app.options.projectId) {
      throw const AuthException(AuthFailureKind.notConfigured);
    }
    final String? token = await client.token(false);
    if (token == null) {
      throw const AuthException(AuthFailureKind.invalidCredentials);
    }
    // B9 accepts this request body and the same token as Bearer. It returns a
    // local user mapping, NOT an access/refresh token pair.
    await api.postMap('auth/firebase/session', data: {'id_token': token});
    return _profiles.loadProfile();
  }

  @override
  Future<UserProfile?> restoreSession() async {
    if ((await client.auth()).currentUser == null) return null;
    return _mapUser();
  }

  @override
  Future<UserProfile> signIn({
    required String email,
    required String password,
  }) async {
    try {
      await (await client.auth()).signInWithEmailAndPassword(
        email: email.trim(),
        password: password,
      );
      await store.clearSession();
      return await _mapUser();
    } on FirebaseAuthException catch (e) {
      throw _failure(e);
    } on ApiException catch (e) {
      if (e.code != _linkRequired) rethrow;
      // Firebase knows this address, but the Astrofrekans account behind it
      // was created another way and is not linked. Never half-signed-in.
      await client.signOut();
      throw const AuthException(AuthFailureKind.emailInUse);
    }
  }

  @override
  Future<UserProfile> register(RegistrationRequest request) async {
    try {
      await (await client.auth()).createUserWithEmailAndPassword(
        email: request.email.trim(),
        password: request.password,
      );
      await store.clearSession();
      final UserProfile profile;
      try {
        profile = await _mapUser();
      } on ApiException catch (e) {
        if (e.code != _linkRequired) rethrow;
        // The address already has an Astrofrekans account (created on the
        // server). Remove the Firebase user just made so no orphan identity
        // is left behind, and say the address is taken - never a second
        // profile for the same email.
        await _discardNewFirebaseUser();
        throw const AuthException(AuthFailureKind.emailInUse);
      }
      return updateProfile(
        profile.copyWith(
          name: request.name,
          birthDate: request.birthDate,
          birthTime: request.birthTime,
          birthPlace: request.birthPlace,
        ),
      );
    } on FirebaseAuthException catch (e) {
      throw _failure(e);
    }
  }

  /// Provider configuration is owned by Firebase Console/native targets.
  /// Callers must explicitly opt in after their platform setup is verified.
  Future<UserProfile> signInWithProvider(SocialProvider provider) async {
    if (provider == SocialProvider.google) {
      // Official native Google flow requires google_sign_in and platform SHA1
      // setup; this architecture seam is disabled until that setup exists.
      throw const AuthException(AuthFailureKind.notConfigured);
    }
    try {
      await (await client.auth()).signInWithProvider(AppleAuthProvider());
      await store.clearSession();
      return await _mapUser();
    } on FirebaseAuthException catch (e) {
      throw _failure(e);
    }
  }

  @override
  Future<UserProfile> updateProfile(UserProfile profile) =>
      _profiles.updateProfile(profile);
  @override
  Future<UserProfile> updateBirthData(UserProfile profile) =>
      _profiles.updateBirthData(profile);
  @override
  Future<UserProfile> customizeProfile(Map<String, Object?> patch) =>
      _profiles.customizeProfile(patch);
  @override
  Future<void> signOut() async {
    try {
      await client.signOut();
    } finally {
      await store.clearSession();
    }
  }

  Future<void> _discardNewFirebaseUser() async {
    try {
      await (await client.auth()).currentUser?.delete();
    } on Object {
      // Deletion is best effort; signing out is not.
    } finally {
      await client.signOut();
    }
  }

  static const String _linkRequired = 'account_link_required';

  static AuthException _failure(FirebaseAuthException e) =>
      AuthException(switch (e.code) {
        'email-already-in-use' => AuthFailureKind.emailInUse,
        'network-request-failed' => AuthFailureKind.network,
        'operation-not-allowed' ||
        'configuration-not-found' => AuthFailureKind.notConfigured,
        'invalid-credential' ||
        'wrong-password' ||
        'user-not-found' => AuthFailureKind.invalidCredentials,
        _ => AuthFailureKind.unknown,
      });
}

class FirebaseSocialAuthService implements SocialAuthService {
  const FirebaseSocialAuthService(this.adapter);
  final FirebaseAuthAdapter adapter;
  @override
  bool isAvailable(SocialProvider provider) => provider == SocialProvider.apple;
  @override
  Future<UserProfile> authenticate(SocialProvider provider) =>
      adapter.signInWithProvider(provider);
}

/// Production mode. New accounts are Firebase email/password accounts;
/// accounts created on the server (backend email + password - e.g. expert
/// accounts, or accounts from before Firebase) keep signing in with the
/// backend. Firebase is asked first; only when it does not accept the
/// credentials (or the address belongs to an unlinked server account) is the
/// backend asked. Either way a failure reads the same, so the answer never
/// reveals which kind of account an address has.
class HybridAuthAdapter extends FirebaseAuthAdapter {
  const HybridAuthAdapter(super.client, super.api, super.store);

  @override
  Future<UserProfile> signIn({
    required String email,
    required String password,
  }) async {
    try {
      return await super.signIn(email: email, password: password);
    } on AuthException catch (e) {
      if (e.kind != AuthFailureKind.invalidCredentials &&
          e.kind != AuthFailureKind.emailInUse) {
        rethrow; // network, rate limit, not configured: not a credential
      }
    }
    try {
      return await LocalJwtAuthAdapter(
        api,
        store,
      ).signIn(email: email, password: password);
    } on AuthException catch (e) {
      if (e.kind == AuthFailureKind.emailInUse) {
        throw const AuthException(AuthFailureKind.invalidCredentials);
      }
      rethrow;
    }
  }

  @override
  Future<UserProfile?> restoreSession() async {
    if (await store.read(SecureKeys.authToken) != null ||
        await store.read(SecureKeys.refreshToken) != null) {
      return LocalJwtAuthAdapter(api, store).restoreSession();
    }
    return super.restoreSession();
  }

  @override
  Future<void> signOut() async {
    try {
      await LocalJwtAuthAdapter(api, store).signOut();
    } finally {
      await super.signOut();
    }
  }
}
