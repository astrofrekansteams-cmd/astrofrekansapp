import '../../../core/storage/secure_storage.dart';
import '../../profile/domain/user_profile.dart';
import '../domain/auth_repository.dart';

/// Local-only auth used until the backend exists.
///
/// It persists the profile in secure storage so session restore, sign-out and
/// the routing guards can be developed and tested for real. It does not talk to
/// any server and every screen using it shows the demo notice.
class MockAuthRepository implements AuthRepository {
  MockAuthRepository({
    required this._store,
    this.latency = const Duration(milliseconds: 400),
  });

  final SecureStore _store;
  final Duration latency;

  final Map<String, String> _passwords = <String, String>{};

  Future<void> _wait() async {
    if (latency > Duration.zero) await Future<void>.delayed(latency);
  }

  @override
  Future<UserProfile?> restoreSession() async {
    final String? token = await _store.read(SecureKeys.authToken);
    if (token == null || token.isEmpty) return null;
    final Map<String, dynamic>? json = await _store.readJson(
      SecureKeys.userProfile,
    );
    if (json == null) return null;
    return UserProfile.fromJson(json);
  }

  @override
  Future<UserProfile> signIn({
    required String email,
    required String password,
  }) async {
    await _wait();
    final String normalized = email.trim().toLowerCase();
    final String? known = _passwords[normalized];
    if (known != null && known != password) {
      throw const AuthException(AuthFailureKind.invalidCredentials);
    }
    if (password.length < 8) {
      throw const AuthException(AuthFailureKind.invalidCredentials);
    }

    final Map<String, dynamic>? cached = await _store.readJson(
      SecureKeys.userProfile,
    );
    final UserProfile profile =
        cached != null &&
            (cached['email'] as String?)?.toLowerCase() == normalized
        ? UserProfile.fromJson(cached)
        : UserProfile(
            id: 'demo-${normalized.hashCode.abs()}',
            name: _nameFromEmail(normalized),
            email: normalized,
            birthDate: DateTime(1995, 3, 12),
            birthTime: '09:41',
            birthPlace: 'İstanbul, Türkiye',
          );

    await _persist(profile);
    return profile;
  }

  @override
  Future<UserProfile> register(RegistrationRequest request) async {
    await _wait();
    final String normalized = request.email.trim().toLowerCase();
    if (_passwords.containsKey(normalized)) {
      throw const AuthException(AuthFailureKind.emailInUse);
    }
    _passwords[normalized] = request.password;

    final UserProfile profile = UserProfile(
      id: 'demo-${normalized.hashCode.abs()}',
      name: request.name.trim(),
      email: normalized,
      birthDate: request.birthDate,
      birthTime: request.birthTime,
      birthPlace: request.birthPlace,
    );
    await _persist(profile);
    return profile;
  }

  @override
  Future<void> signOut() async {
    await _store.clearSession();
  }

  @override
  Future<UserProfile> updateProfile(UserProfile profile) async {
    await _store.writeJson(SecureKeys.userProfile, profile.toJson());
    return profile;
  }

  @override
  Future<UserProfile> updateBirthData(UserProfile profile) =>
      updateProfile(profile);

  @override
  Future<UserProfile> customizeProfile(Map<String, Object?> patch) async {
    final Map<String, dynamic>? cached = await _store.readJson(
      SecureKeys.userProfile,
    );
    if (cached == null) throw StateError('No signed-in profile.');
    var profile = UserProfile.fromJson(cached);
    profile = profile.copyWith(
      name: patch['name'] as String? ?? profile.name,
      bio: patch.containsKey('bio') ? patch['bio'] as String? : profile.bio,
      avatarPreset: patch.containsKey('avatar_preset')
          ? ((patch['avatar_preset'] as String?)?.isEmpty ?? true
                ? null
                : patch['avatar_preset'] as String?)
          : profile.avatarPreset,
      coverTheme: patch['cover_theme'] as String? ?? profile.coverTheme,
      language: patch['language'] as String? ?? profile.language,
      timezone: patch['timezone'] as String? ?? profile.timezone,
      privacy: {
        ...profile.privacy,
        ...?(patch['privacy'] as Map<String, bool>?),
      },
      notificationPrefs: {
        ...profile.notificationPrefs,
        ...?(patch['notification_prefs'] as Map<String, bool>?),
      },
    );
    return updateProfile(profile);
  }

  Future<void> _persist(UserProfile profile) async {
    await _store.write(SecureKeys.authToken, 'mock.${profile.id}');
    await _store.writeJson(SecureKeys.userProfile, profile.toJson());
  }

  static String _nameFromEmail(String email) {
    final String local = email
        .split('@')
        .first
        .replaceAll(RegExp(r'[._-]'), ' ');
    return local
        .split(' ')
        .where((String part) => part.isNotEmpty)
        .map(
          (String part) =>
              part[0].toUpperCase() + part.substring(1).toLowerCase(),
        )
        .join(' ');
  }
}
