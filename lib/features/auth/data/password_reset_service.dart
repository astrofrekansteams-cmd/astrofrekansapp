import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/firebase_client.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_exception.dart';

/// What asking for a reset link produced. Deliberately not "sent to you":
/// the answer is the same whether or not the address has an account.
enum PasswordResetRequestResult {
  /// The server accepted the request; a link goes out if the account is
  /// eligible.
  requested,

  /// No mail provider is configured. Nothing was or will be sent.
  unavailable,

  /// Hybrid: Firebase accounts were sent a link (if the account exists);
  /// server accounts cannot be, because the server has no mail provider.
  /// Depends only on configuration, never on the address.
  requestedFirebaseOnly,
}

/// Where a reset link stands before and after the new password is chosen.
enum ResetLinkState { valid, expired, used, invalid }

class PasswordResetException implements Exception {
  const PasswordResetException(this.state);
  final ResetLinkState state;
  @override
  String toString() => 'PasswordResetException(${state.name})';
}

abstract interface class PasswordResetService {
  /// Whether this build finishes the reset inside the app (local accounts),
  /// or the email's own link does it (Firebase-hosted page).
  bool get completesInApp;

  Future<PasswordResetRequestResult> requestReset(String email);

  Future<ResetLinkState> checkLink(String token);

  /// Throws [PasswordResetException] for an expired, used or invalid link.
  Future<void> resetPassword(String token, String newPassword);
}

ResetLinkState _linkState(ApiException error) => switch (error.code) {
  'token_expired' => ResetLinkState.expired,
  'token_used' => ResetLinkState.used,
  _ => ResetLinkState.invalid,
};

/// Local (email + password) accounts: the backend issues a single-use,
/// expiring token and mails a link that opens [ResetPasswordScreen].
class ApiPasswordResetService implements PasswordResetService {
  const ApiPasswordResetService(this.api);
  final ApiClient api;

  @override
  bool get completesInApp => true;

  @override
  Future<PasswordResetRequestResult> requestReset(String email) async {
    try {
      await api.postMap(
        'auth/forgot-password',
        data: <String, dynamic>{'email': email.trim()},
      );
      return PasswordResetRequestResult.requested;
    } on ApiException catch (error) {
      if (error.code == 'password_reset_unavailable') {
        return PasswordResetRequestResult.unavailable;
      }
      rethrow;
    }
  }

  @override
  Future<ResetLinkState> checkLink(String token) async {
    try {
      await api.postMap(
        'auth/reset-password/check',
        data: <String, dynamic>{'token': token},
      );
      return ResetLinkState.valid;
    } on ApiException catch (error) {
      if (error.kind == ApiErrorKind.unauthorized ||
          error.kind == ApiErrorKind.validation) {
        return _linkState(error);
      }
      rethrow;
    }
  }

  @override
  Future<void> resetPassword(String token, String newPassword) async {
    try {
      await api.postMap(
        'auth/reset-password',
        data: <String, dynamic>{'token': token, 'new_password': newPassword},
      );
    } on ApiException catch (error) {
      if (error.kind == ApiErrorKind.unauthorized) {
        throw PasswordResetException(_linkState(error));
      }
      rethrow;
    }
  }
}

/// Firebase accounts: Firebase mails its own link and hosts the new-password
/// page. The app only starts the request.
class FirebasePasswordResetService implements PasswordResetService {
  const FirebasePasswordResetService(this.client);
  final FirebaseClient client;

  @override
  bool get completesInApp => false;

  @override
  Future<PasswordResetRequestResult> requestReset(String email) async {
    try {
      await (await client.auth()).sendPasswordResetEmail(email: email.trim());
      return PasswordResetRequestResult.requested;
    } on FirebaseAuthException catch (error) {
      return switch (error.code) {
        // Same answer as for a real account: no enumeration.
        'user-not-found' ||
        'invalid-email' => PasswordResetRequestResult.requested,
        'operation-not-allowed' ||
        'configuration-not-found' => PasswordResetRequestResult.unavailable,
        'network-request-failed' => throw const ApiException(
          kind: ApiErrorKind.network,
        ),
        _ => throw const ApiException(kind: ApiErrorKind.unknown),
      };
    }
  }

  @override
  Future<ResetLinkState> checkLink(String token) async =>
      ResetLinkState.invalid;

  @override
  Future<void> resetPassword(String token, String newPassword) async =>
      throw const PasswordResetException(ResetLinkState.invalid);
}

/// Hybrid (production): an address may belong to a Firebase account (Firebase
/// mails its own link and hosts the page) or to a server account (the
/// backend mails a link that opens [ResetPasswordScreen]). The app cannot and
/// must not know which, so it asks both; each sends only to its own
/// accounts. Server links complete in the app.
class HybridPasswordResetService implements PasswordResetService {
  const HybridPasswordResetService(this.firebase, this.server);
  final PasswordResetService firebase;
  final PasswordResetService server;

  @override
  bool get completesInApp => true;

  @override
  Future<PasswordResetRequestResult> requestReset(String email) async {
    final List<PasswordResetRequestResult> results = await Future.wait(
      <Future<PasswordResetRequestResult>>[
        firebase.requestReset(email),
        server.requestReset(email),
      ],
    );
    final bool firebaseSent =
        results[0] == PasswordResetRequestResult.requested;
    final bool serverSent = results[1] == PasswordResetRequestResult.requested;
    if (serverSent) return PasswordResetRequestResult.requested;
    return firebaseSent
        ? PasswordResetRequestResult.requestedFirebaseOnly
        : PasswordResetRequestResult.unavailable;
  }

  @override
  Future<ResetLinkState> checkLink(String token) => server.checkLink(token);

  @override
  Future<void> resetPassword(String token, String newPassword) =>
      server.resetPassword(token, newPassword);
}

/// Demo builds have no server to mail from; they say so instead of
/// pretending a link went out.
class UnavailablePasswordResetService implements PasswordResetService {
  const UnavailablePasswordResetService();
  @override
  bool get completesInApp => true;
  @override
  Future<PasswordResetRequestResult> requestReset(String email) async =>
      PasswordResetRequestResult.unavailable;
  @override
  Future<ResetLinkState> checkLink(String token) async =>
      ResetLinkState.invalid;
  @override
  Future<void> resetPassword(String token, String newPassword) async =>
      throw const PasswordResetException(ResetLinkState.invalid);
}

final Provider<PasswordResetService> passwordResetServiceProvider =
    Provider<PasswordResetService>((Ref ref) {
      final AppEnvironment config = ref.watch(appEnvironmentProvider);
      if (config.useMocks) return const UnavailablePasswordResetService();
      final PasswordResetService server = ApiPasswordResetService(
        ApiClient(ref.watch(dioProvider)),
      );
      final PasswordResetService firebase = FirebasePasswordResetService(
        ref.watch(firebaseClientProvider),
      );
      // Firebase accounts reset in Firebase, server accounts on the server;
      // hybrid has both kinds.
      if (config.authMode == AuthMode.hybrid) {
        return HybridPasswordResetService(firebase, server);
      }
      if (config.authMode == AuthMode.firebase) return firebase;
      return server;
    });
