import '../../profile/domain/user_profile.dart';

/// Reasons a sign-in or sign-up can fail, mapped to localized copy by the UI.
enum AuthFailureKind {
  invalidCredentials,
  emailInUse,
  network,
  notConfigured,
  unknown,
}

class AuthException implements Exception {
  const AuthException(this.kind);

  final AuthFailureKind kind;

  @override
  String toString() => 'AuthException(${kind.name})';
}

/// Registration payload. Birth data is required at sign-up because the whole
/// product is built on the user's own chart.
class RegistrationRequest {
  const RegistrationRequest({
    required this.name,
    required this.email,
    required this.password,
    required this.birthDate,
    this.birthTime,
    this.birthPlace,
  });

  final String name;
  final String email;
  final String password;
  final DateTime birthDate;
  final String? birthTime;
  final String? birthPlace;
}

abstract interface class AuthRepository {
  /// Restores a previously persisted session, or null.
  Future<UserProfile?> restoreSession();

  Future<UserProfile> signIn({required String email, required String password});

  Future<UserProfile> register(RegistrationRequest request);

  Future<void> signOut();

  Future<UserProfile> updateProfile(UserProfile profile);

  /// Birth data only (date, time, place, birth-place zone). The account's
  /// name, language and current zone are left alone.
  Future<UserProfile> updateBirthData(UserProfile profile);

  /// Profile customisation (avatar preset, bio, cover theme, language,
  /// privacy, notification preferences). Only the given keys change.
  Future<UserProfile> customizeProfile(Map<String, Object?> patch);
}

/// Social providers we intend to support. No credentials exist yet, so the
/// implementation stays disabled instead of faking a successful login.
enum SocialProvider { google, apple }

abstract interface class SocialAuthService {
  bool isAvailable(SocialProvider provider);

  Future<UserProfile> authenticate(SocialProvider provider);
}

/// Placeholder implementation: reports every provider as unavailable and throws
/// [AuthFailureKind.notConfigured] if called anyway.
class UnconfiguredSocialAuthService implements SocialAuthService {
  const UnconfiguredSocialAuthService();

  @override
  bool isAvailable(SocialProvider provider) => false;

  @override
  Future<UserProfile> authenticate(SocialProvider provider) async =>
      throw const AuthException(AuthFailureKind.notConfigured);
}
