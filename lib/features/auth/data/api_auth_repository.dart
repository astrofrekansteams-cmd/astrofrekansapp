import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/astrology/data/api_contract_dto.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/network/token_storage.dart';
import '../../../core/storage/secure_storage.dart';
import '../../profile/domain/user_profile.dart';
import '../domain/auth_repository.dart';
import 'auth_dto.dart';
import 'mock_auth_repository.dart';
import 'identity_session.dart';
import '../../../core/config/firebase_client.dart';

/// Existing FastAPI JWT flow; Firebase identity can later replace this adapter.
class ApiAuthRepository implements AuthRepository {
  const ApiAuthRepository(this._api, this._store);

  final ApiClient _api;
  final SecureStore _store;

  TokenStorage get _tokens => SecureTokenStorage(_store);

  @override
  Future<UserProfile?> restoreSession() async {
    if (await _tokens.readAccessToken() == null &&
        await _tokens.readRefreshToken() == null) {
      return null;
    }
    try {
      return await loadProfile();
    } on ApiException catch (error) {
      if (error.kind == ApiErrorKind.unauthorized) {
        await _tokens.clearSession();
        return null;
      }
      rethrow;
    }
  }

  @override
  Future<UserProfile> signIn({
    required String email,
    required String password,
  }) async {
    try {
      final Map<String, dynamic> tokenJson = await _api.postMap(
        'auth/login',
        data: <String, dynamic>{'email': email.trim(), 'password': password},
      );
      return await _saveAndLoad(tokenJson);
    } on ApiException catch (error) {
      throw _authError(error);
    }
  }

  @override
  Future<UserProfile> register(RegistrationRequest request) async {
    try {
      final Map<String, dynamic> payload = <String, dynamic>{
        'name': request.name.trim(),
        'email': request.email.trim(),
        'password': request.password,
        'birth_date': _dateOnly(request.birthDate),
        if (request.birthTime != null)
          'birth_time': request.birthTime!.length == 5
              ? '${request.birthTime}:00'
              : request.birthTime,
        if (request.birthPlace != null) 'birth_place': request.birthPlace,
      };
      final Map<String, dynamic> tokenJson = await _api.postMap(
        'auth/register',
        data: payload,
      );
      return await _saveAndLoad(tokenJson);
    } on ApiException catch (error) {
      throw _authError(error);
    }
  }

  @override
  Future<void> signOut() async {
    final String? refresh = await _tokens.readRefreshToken();
    try {
      if (refresh != null) {
        await _api.postMap(
          'auth/logout',
          data: <String, String>{'refresh_token': refresh},
        );
      }
    } finally {
      await _tokens.clearSession();
    }
  }

  @override
  Future<UserProfile> customizeProfile(Map<String, Object?> patch) async {
    await _api.patchMap('users/me', data: patch);
    return loadProfile();
  }

  /// Account fields and birth data go to their own endpoints, each with its
  /// own zone: `timezone` (where the person lives) to the account,
  /// `birthTimezone` (the birth place) to the birth profile.
  @override
  Future<UserProfile> updateProfile(UserProfile profile) async {
    await _api.patchMap(
      'users/me',
      data: <String, dynamic>{
        'name': profile.name,
        'avatar_url': profile.avatarUrl,
        'language': profile.language,
        if (profile.timezone != null) 'timezone': profile.timezone,
      },
    );
    if (profile.birthDate != null) {
      await _putBirthProfile(profile);
    }
    return loadProfile();
  }

  /// Birth data only. The account (name, language, current zone) is not
  /// touched, so editing a birth place never moves where the person lives.
  @override
  Future<UserProfile> updateBirthData(UserProfile profile) async {
    await _putBirthProfile(profile);
    return loadProfile();
  }

  Future<void> _putBirthProfile(UserProfile profile) => _api.putMap(
    'birth-profiles/me',
    data: <String, dynamic>{
      'birth_date': _dateOnly(profile.birthDate!),
      'birth_time': profile.birthTime == null
          ? null
          : profile.birthTime!.length == 5
          ? '${profile.birthTime}:00'
          : profile.birthTime,
      'birth_place': profile.birthPlace,
      'latitude': profile.latitude,
      'longitude': profile.longitude,
      'timezone': profile.birthTimezone,
    },
  );

  Future<UserProfile> _saveAndLoad(Map<String, dynamic> json) async {
    final AuthTokenDto tokens = AuthTokenDto.fromJson(json);
    await _tokens.saveTokens(
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
    );
    try {
      return await loadProfile();
    } on Object {
      await _tokens.clearSession();
      rethrow;
    }
  }

  Future<UserProfile> loadProfile() async {
    final Map<String, dynamic> user = await _api.getMap('users/me');
    BirthProfileDto? birth;
    try {
      birth = BirthProfileDto.fromJson(await _api.getMap('birth-profiles/me'));
    } on ApiException catch (error) {
      if (error.kind != ApiErrorKind.notFound &&
          error.code != 'birth_profile_missing') {
        rethrow;
      }
    }
    final UserProfile profile = UserDto.fromJson(user).toDomain(birth: birth);
    await _store.writeJson(SecureKeys.userProfile, profile.toJson());
    return profile;
  }

  static AuthException _authError(ApiException error) => switch (error.code) {
    'invalid_credentials' => const AuthException(
      AuthFailureKind.invalidCredentials,
    ),
    'email_in_use' => const AuthException(AuthFailureKind.emailInUse),
    _
        when error.kind == ApiErrorKind.network ||
            error.kind == ApiErrorKind.timeout =>
      const AuthException(AuthFailureKind.network),
    _ => const AuthException(AuthFailureKind.unknown),
  };

  static String _dateOnly(DateTime date) =>
      '${date.year.toString().padLeft(4, '0')}-'
      '${date.month.toString().padLeft(2, '0')}-'
      '${date.day.toString().padLeft(2, '0')}';
}

/// Data-source selection is centralized here; the application owner can
/// override `authRepositoryProvider` with this provider in API builds.
final Provider<AuthRepository> configuredAuthRepositoryProvider =
    Provider<AuthRepository>((Ref ref) {
      final AppEnvironment config = ref.watch(appEnvironmentProvider);
      final SecureStore store = ref.watch(secureStoreProvider);
      return config.useMocks
          ? MockAuthRepository(store: store)
          : config.authMode == AuthMode.hybrid
          ? HybridAuthAdapter(
              ref.watch(firebaseClientProvider),
              ApiClient(ref.watch(dioProvider)),
              store,
            )
          : config.authMode == AuthMode.firebase
          ? FirebaseAuthAdapter(
              ref.watch(firebaseClientProvider),
              ApiClient(ref.watch(dioProvider)),
              store,
            )
          : LocalJwtAuthAdapter(ApiClient(ref.watch(dioProvider)), store);
    });
