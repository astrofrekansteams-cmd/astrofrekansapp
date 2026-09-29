import 'dart:async';
import 'dart:ui' show Locale;
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/api_auth_repository.dart';
import '../../../core/localization/locale_controller.dart';
import '../../../core/storage/app_preferences.dart';
import '../../profile/domain/user_profile.dart';
import '../domain/auth_repository.dart';
import '../../consultation/data/push_service.dart';
import '../../../core/storage/secure_storage.dart';
import '../../../core/network/api_config.dart';
import '../data/identity_session.dart';
import '../../calls/data/voip_device_service.dart';
import '../../calls/application/incoming_call_presentation.dart';

final Provider<AuthRepository> authRepositoryProvider =
    Provider<AuthRepository>((Ref ref) {
      return ref.watch(configuredAuthRepositoryProvider);
    });

final Provider<SocialAuthService> socialAuthServiceProvider =
    Provider<SocialAuthService>((Ref ref) {
      final config = ref.watch(appEnvironmentProvider);
      final repo = ref.watch(authRepositoryProvider);
      return !config.useMocks && repo is FirebaseAuthAdapter
          ? FirebaseSocialAuthService(repo)
          : const UnconfiguredSocialAuthService();
    });

enum SessionStatus { unknown, loading, unauthenticated, authenticated, error }

@immutable
class SessionState {
  const SessionState({
    this.status = SessionStatus.unknown,
    this.user,
    this.onboardingSeen = false,
    this.error,
  });

  final SessionStatus status;
  final UserProfile? user;
  final bool onboardingSeen;
  final Object? error;

  bool get isAuthenticated => status == SessionStatus.authenticated;

  /// Storage has been read. `loading` is not resolved: while a stored
  /// session is being restored the router must not send the user to login.
  bool get isResolved =>
      status != SessionStatus.unknown && status != SessionStatus.loading;

  SessionState copyWith({
    SessionStatus? status,
    UserProfile? user,
    bool? onboardingSeen,
    bool clearUser = false,
  }) => SessionState(
    status: status ?? this.status,
    user: clearUser ? null : (user ?? this.user),
    onboardingSeen: onboardingSeen ?? this.onboardingSeen,
  );
}

/// Owns "who is signed in" for the whole app; the router listens to it.
class SessionController extends Notifier<SessionState> {
  @override
  SessionState build() => SessionState(
    onboardingSeen: ref.read(appPreferencesProvider).onboardingSeen,
  );

  AuthRepository get _repository => ref.read(authRepositoryProvider);

  /// The account's language is the app's language: one flow, both ways.
  /// Signing in (or any profile save) applies the server's choice; choosing a
  /// language in the app saves it to the account (see [setLanguage]).
  void _applyLanguage(UserProfile? user) {
    final String? code = user?.language;
    for (final locale in AppLocales.supported) {
      if (locale.languageCode == code) {
        unawaited(
          ref.read(localeControllerProvider.notifier).setLocale(locale),
        );
        return;
      }
    }
  }

  /// Switch the app language and, when signed in, the account's. If the
  /// account cannot be saved the app language goes back and the error is
  /// rethrown, so the two never disagree.
  Future<void> setLanguage(Locale locale) async {
    final locales = ref.read(localeControllerProvider.notifier);
    final Locale previous = ref.read(localeControllerProvider);
    await locales.setLocale(locale);
    final UserProfile? user = state.user;
    if (!state.isAuthenticated || user == null) return;
    if (user.language == locale.languageCode) return;
    try {
      final updated = await _repository.customizeProfile({
        'language': locale.languageCode,
      });
      state = state.copyWith(user: updated);
    } on Object {
      await locales.setLocale(previous);
      rethrow;
    }
  }

  void _resumePush() {
    unawaited(
      ref.read(pushServiceProvider).startAfterAuth().catchError((Object _) {}),
    );
    final voip = ref.read(voipDeviceServiceProvider);
    if (voip != null) {
      unawaited(voip.startAfterAuth().catchError((Object _) {}));
    }
  }

  /// Called once by the splash screen. No artificial delay: the app moves on as
  /// soon as storage has been read.
  Future<void> bootstrap() async {
    state = state.copyWith(status: SessionStatus.loading);
    final AppPreferences prefs = ref.read(appPreferencesProvider);
    UserProfile? user;
    try {
      user = await _repository.restoreSession();
    } on Object catch (error) {
      state = SessionState(
        status: SessionStatus.error,
        error: error,
        onboardingSeen: prefs.onboardingSeen,
      );
      return;
    }
    state = SessionState(
      status: user == null
          ? SessionStatus.unauthenticated
          : SessionStatus.authenticated,
      user: user,
      onboardingSeen: prefs.onboardingSeen,
    );
    if (user != null) {
      _applyLanguage(user);
      _resumePush();
    }
  }

  Future<void> completeOnboarding() async {
    await ref.read(appPreferencesProvider).setOnboardingSeen(value: true);
    state = state.copyWith(onboardingSeen: true);
  }

  Future<void> signIn({required String email, required String password}) async {
    final UserProfile user = await _repository.signIn(
      email: email,
      password: password,
    );
    state = state.copyWith(status: SessionStatus.authenticated, user: user);
    _applyLanguage(user);
    _resumePush();
  }

  Future<void> signInWithSocial(SocialProvider provider) async {
    final user = await ref
        .read(socialAuthServiceProvider)
        .authenticate(provider);
    state = state.copyWith(status: SessionStatus.authenticated, user: user);
    _resumePush();
  }

  Future<void> register(RegistrationRequest request) async {
    final UserProfile user = await _repository.register(request);
    state = state.copyWith(status: SessionStatus.authenticated, user: user);
    // A new account takes the language the person has been using the app
    // in, rather than the server's default.
    try {
      await setLanguage(ref.read(localeControllerProvider));
    } on Object {
      /* The account keeps its default; the app language is unchanged. */
    }
    _resumePush();
  }

  Future<void> signOut() async {
    try {
      // Native pending actions contain no credentials and can be cleared even
      // after transport logout; a missing platform channel must not hold the
      // authenticated session open indefinitely.
      unawaited(
        ref
            .read(incomingCallPresentationProvider)
            .clearPending()
            .catchError((Object _) {}),
      );
      try {
        await ref.read(voipDeviceServiceProvider)?.unregister();
      } on Object {
        /* Best effort: logout must still continue. */
      }
      try {
        await ref.read(pushDeviceCleanupProvider)();
      } on Object {
        /* Preserve local logout if the push backend is down. */
      }
      await _repository.signOut();
    } finally {
      await invalidate();
    }
  }

  Future<void> invalidate() async {
    await ref.read(secureStoreProvider).clearSession();
    state = state.copyWith(
      status: SessionStatus.unauthenticated,
      clearUser: true,
    );
  }

  Future<void> updateProfile(UserProfile profile) async {
    final user = await _repository.updateProfile(profile);
    state = state.copyWith(user: user);
    _applyLanguage(user);
  }

  /// Birth data only; the account's current zone and language are untouched.
  Future<void> updateBirthData(UserProfile profile) async {
    final user = await _repository.updateBirthData(profile);
    state = state.copyWith(user: user);
  }

  Future<void> customizeProfile(Map<String, Object?> patch) async {
    final user = await _repository.customizeProfile(patch);
    state = state.copyWith(user: user);
    if (patch.containsKey('language')) _applyLanguage(user);
  }

  /// After a backend password change every session is revoked, this one
  /// included: sign straight back in with the new password. If that fails
  /// (a hybrid account signed in another way) the person signs in again.
  Future<void> afterPasswordChange({
    required bool sessionsRevoked,
    required String newPassword,
  }) async {
    final UserProfile? user = state.user;
    if (!sessionsRevoked || user == null) return;
    try {
      await signIn(email: user.email, password: newPassword);
    } on Object {
      await invalidate();
    }
  }

  /// The account is gone on the server: drop everything local.
  Future<void> afterAccountDeleted() async {
    try {
      await _repository.signOut();
    } on Object {
      /* The server already revoked every session. */
    } finally {
      await invalidate();
    }
  }
}

final NotifierProvider<SessionController, SessionState> sessionProvider =
    NotifierProvider<SessionController, SessionState>(SessionController.new);

/// Convenience for screens that need the signed-in user.
final Provider<UserProfile?> currentUserProvider = Provider<UserProfile?>(
  (Ref ref) => ref.watch(sessionProvider).user,
);
