import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/astrology/data/api_contract_dto.dart';
import '../../../core/astrology/data/production_models.dart';
import '../../../core/config/firebase_client.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_exception.dart';
import '../../auth/application/session_controller.dart';

/// One signed-in session: an email-and-password login this server holds
/// (revocable), or this device's Firebase sign-in (managed by Firebase, not
/// revocable here).
class AccountSession extends ContractRecord {
  AccountSession(super.value) {
    text('id');
  }
  String get id => text('id');
  bool get isFirebase => optionalText('kind') == 'firebase';
  bool get revocable => json['revocable'] != false && !isFirebase;
  String? get signInProvider => optionalText('sign_in_provider');
  String? get userAgent => optionalText('user_agent');
  String? get ipHint => optionalText('ip_hint');
  bool get current => json['current'] == true;
  DateTime get lastUsedAt => ContractJson.date(json, 'last_used_at').toLocal();
  DateTime get createdAt => ContractJson.date(json, 'created_at').toLocal();
}

/// A device registered for push notifications.
class AccountDevice extends ContractRecord {
  AccountDevice(super.value) {
    text('id');
  }
  String get id => text('id');
  String get platform => optionalText('platform') ?? 'unknown';
  String? get appVersion => optionalText('app_version');
  bool get enabled => json['enabled'] == true;
  DateTime? get lastSeenAt =>
      ContractJson.optionalDate(json, 'last_seen_at')?.toLocal();
}

/// What `GET /users/me/deletion-check` says about deleting now.
class DeletionCheck extends ContractRecord {
  DeletionCheck(super.value);
  bool get allowed => json['allowed'] == true;
  bool get requiresPassword => json['requires_password'] == true;
  int count(String key) => json[key] as int? ?? 0;
  int get openOrders => count('open_orders');
  int get liveAppointments => count('live_appointments');
  int get openRefunds => count('open_refunds');
  int get expertOpenOrders => count('expert_open_orders');
}

/// Why a password change failed, in terms the screen can say.
enum PasswordChangeFailure {
  wrongCurrent,
  weak,
  rateLimited,
  needsRecentLogin,
  network,
  unsupported,
}

/// Whether this account has a password to change, and where it lives.
enum PasswordKind {
  /// An email-and-password account held by this server.
  local,

  /// A Firebase email-and-password account: changed in Firebase.
  firebase,

  /// Signs in through a provider (Google, Apple): no password here at all.
  external,
}

class PasswordCapability {
  const PasswordCapability(this.kind, {this.provider});
  final PasswordKind kind;

  /// For [PasswordKind.external]: `google.com`, `apple.com`, ...
  final String? provider;
  bool get canChange => kind != PasswordKind.external;
}

/// The Firebase side of a password change, behind an interface so the flow
/// is testable without a Firebase project.
abstract interface class FirebasePasswordOps {
  /// Provider ids of the signed-in Firebase user (`password`, `google.com`,
  /// ...), or null when nobody is signed in to Firebase on this device.
  Future<List<String>?> providerIds();

  /// Re-authenticate with the current password, then set the new one.
  /// Throws [PasswordChangeException] with the reason.
  Future<void> changePassword({
    required String email,
    required String current,
    required String next,
  });
}

class FirebaseClientPasswordOps implements FirebasePasswordOps {
  const FirebaseClientPasswordOps(this.client);
  final FirebaseClient client;

  @override
  Future<List<String>?> providerIds() async {
    try {
      final user = (await client.auth()).currentUser;
      return user?.providerData.map((p) => p.providerId).toList();
    } on Object {
      return null; // Firebase not initialised: not a Firebase session.
    }
  }

  @override
  Future<void> changePassword({
    required String email,
    required String current,
    required String next,
  }) async {
    final user = (await client.auth()).currentUser;
    if (user == null) {
      throw const PasswordChangeException(PasswordChangeFailure.unsupported);
    }
    try {
      // Firebase requires a recent sign-in for a password change; proving the
      // current password is that sign-in.
      await user.reauthenticateWithCredential(
        EmailAuthProvider.credential(email: email, password: current),
      );
      await user.updatePassword(next);
      // Firebase revokes the other devices' sessions on a password change;
      // this device takes a fresh ID token so the backend sees a current one.
      await user.getIdToken(true);
    } on FirebaseAuthException catch (error) {
      throw PasswordChangeException(firebasePasswordFailure(error.code));
    }
  }
}

/// Firebase's error codes, in the screen's terms.
PasswordChangeFailure firebasePasswordFailure(String code) => switch (code) {
  'wrong-password' ||
  'invalid-credential' => PasswordChangeFailure.wrongCurrent,
  'weak-password' => PasswordChangeFailure.weak,
  'too-many-requests' => PasswordChangeFailure.rateLimited,
  'requires-recent-login' ||
  'user-token-expired' => PasswordChangeFailure.needsRecentLogin,
  'network-request-failed' => PasswordChangeFailure.network,
  _ => PasswordChangeFailure.unsupported,
};

class PasswordChangeException implements Exception {
  const PasswordChangeException(this.reason);
  final PasswordChangeFailure reason;
}

abstract interface class AccountRepository {
  /// Whether "change password" applies to this account, and where.
  Future<PasswordCapability> passwordCapability();

  /// Returns true when the server signed out every session (a backend
  /// password): the caller signs in again with the new password.
  Future<bool> changePassword({
    required String current,
    required String next,
    required String email,
  });
  Future<List<AccountSession>> sessions();
  Future<void> revokeSession(String id);
  Future<List<AccountDevice>> devices();
  Future<void> removeDevice(String id);
  Future<DeletionCheck> deletionCheck();

  /// Throws [ApiException] `account_has_active_services` (409) with counts,
  /// `current_password_incorrect` (403) or `deletion_confirmation_required`
  /// (422). Never 401: a wrong confirmation must not look like a dead
  /// session and sign the person out.
  Future<void> deleteAccount({String? password, String? confirmEmail});
}

class ApiAccountRepository implements AccountRepository {
  const ApiAccountRepository(this.api, {this.firebase});
  final ApiClient api;

  /// Set in Firebase/hybrid builds. A Firebase sign-in's password lives in
  /// Firebase and is changed there - never as a backend password.
  final FirebasePasswordOps? firebase;

  String _id(String id) => Uri.encodeComponent(id);

  @override
  Future<PasswordCapability> passwordCapability() async {
    final providers = await firebase?.providerIds();
    if (providers != null) {
      if (providers.contains('password')) {
        return const PasswordCapability(PasswordKind.firebase);
      }
      return PasswordCapability(
        PasswordKind.external,
        provider: providers.where((p) => p != 'firebase').firstOrNull,
      );
    }
    final me = await api.getMap('users/me');
    if (me['has_local_password'] == true) {
      return const PasswordCapability(PasswordKind.local);
    }
    return const PasswordCapability(PasswordKind.external);
  }

  @override
  Future<bool> changePassword({
    required String current,
    required String next,
    required String email,
  }) async {
    final providers = await firebase?.providerIds();
    if (providers != null) {
      // Signed in with Firebase: the password is Firebase's.
      if (!providers.contains('password')) {
        throw const PasswordChangeException(PasswordChangeFailure.unsupported);
      }
      await firebase!.changePassword(
        email: email,
        current: current,
        next: next,
      );
      return false;
    }
    try {
      await api.postMap(
        'auth/change-password',
        data: {'current_password': current, 'new_password': next},
      );
      return true;
    } on ApiException catch (error) {
      if (error.code == 'current_password_incorrect') {
        throw const PasswordChangeException(PasswordChangeFailure.wrongCurrent);
      }
      throw switch (error.kind) {
        ApiErrorKind.validation => const PasswordChangeException(
          PasswordChangeFailure.weak,
        ),
        ApiErrorKind.rateLimited => const PasswordChangeException(
          PasswordChangeFailure.rateLimited,
        ),
        _ => error,
      };
    }
  }

  @override
  Future<List<AccountSession>> sessions() async =>
      (await api.getList('auth/sessions')).map(AccountSession.new).toList();

  @override
  Future<void> revokeSession(String id) =>
      api.delete('auth/sessions/${_id(id)}');

  @override
  Future<List<AccountDevice>> devices() async =>
      (await api.getList('devices/push')).map(AccountDevice.new).toList();

  @override
  Future<void> removeDevice(String id) => api.delete('devices/push/${_id(id)}');

  @override
  Future<DeletionCheck> deletionCheck() async =>
      DeletionCheck(await api.getMap('users/me/deletion-check'));

  @override
  Future<void> deleteAccount({String? password, String? confirmEmail}) async {
    await api.postMap(
      'users/me/delete',
      data: {'password': ?password, 'confirm_email': ?confirmEmail},
    );
  }
}

class UnavailableAccountRepository implements AccountRepository {
  const UnavailableAccountRepository();
  static const _unavailable = ApiException(
    kind: ApiErrorKind.server,
    code: 'demo_unavailable',
  );
  @override
  Future<PasswordCapability> passwordCapability() async =>
      const PasswordCapability(PasswordKind.external);
  @override
  Future<bool> changePassword({
    required String current,
    required String next,
    required String email,
  }) async => throw _unavailable;
  @override
  Future<List<AccountSession>> sessions() async => throw _unavailable;
  @override
  Future<void> revokeSession(String id) async => throw _unavailable;
  @override
  Future<List<AccountDevice>> devices() async => throw _unavailable;
  @override
  Future<void> removeDevice(String id) async => throw _unavailable;
  @override
  Future<DeletionCheck> deletionCheck() async => throw _unavailable;
  @override
  Future<void> deleteAccount({String? password, String? confirmEmail}) async =>
      throw _unavailable;
}

final accountRepositoryProvider = Provider<AccountRepository>((ref) {
  ref.watch(currentUserProvider)?.id;
  final config = ref.watch(appEnvironmentProvider);
  if (config.useMocks) return const UnavailableAccountRepository();
  return ApiAccountRepository(
    ApiClient(ref.watch(dioProvider)),
    firebase: config.authMode == AuthMode.localJwt
        ? null
        : FirebaseClientPasswordOps(ref.watch(firebaseClientProvider)),
  );
});
