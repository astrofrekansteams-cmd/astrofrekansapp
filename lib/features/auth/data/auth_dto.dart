import '../../../core/astrology/data/api_contract_dto.dart';
import '../../profile/domain/user_profile.dart';

class AuthTokenDto {
  const AuthTokenDto({required this.accessToken, required this.refreshToken});

  final String accessToken;
  final String refreshToken;

  factory AuthTokenDto.fromJson(Map<String, dynamic> json) {
    final String access = json['access_token'] as String;
    final String refresh = json['refresh_token'] as String;
    DateTime.parse(json['expires_at'] as String);
    DateTime.parse(json['refresh_expires_at'] as String);
    if (json['token_type'] != 'Bearer') {
      throw const FormatException('Unsupported token type.');
    }
    return AuthTokenDto(accessToken: access, refreshToken: refresh);
  }
}

class UserDto {
  const UserDto(this.json);

  final Map<String, dynamic> json;

  factory UserDto.fromJson(Map<String, dynamic> json) {
    ContractJson.string(json, 'id');
    ContractJson.string(json, 'email');
    ContractJson.string(json, 'name');
    ContractJson.string(json, 'subscription_tier');
    return UserDto(json);
  }

  UserProfile toDomain({BirthProfileDto? birth}) {
    final Map<String, dynamic>? birthJson = birth?.json;
    return UserProfile(
      id: json['id'] as String,
      name: json['name'] as String,
      email: json['email'] as String,
      avatarUrl: json['avatar_url'] as String?,
      avatarPreset: json['avatar_preset'] as String?,
      bio: json['bio'] as String?,
      coverTheme: json['cover_theme'] as String? ?? 'cosmic_night',
      privacy: _flags(json['privacy']),
      notificationPrefs: _flags(json['notification_prefs']),
      language: json['language'] as String? ?? 'tr',
      // Two different zones: where the person lives (the account) and where
      // they were born (the birth profile). Never one standing in for the
      // other.
      timezone: json['timezone'] as String?,
      birthTimezone: birthJson?['timezone'] as String?,
      subscriptionTier: SubscriptionTier.fromWire(
        json['subscription_tier'] as String?,
      ),
      birthDate: birthJson?['birth_date'] == null
          ? null
          : DateTime.parse(birthJson!['birth_date'] as String),
      birthTime: (birthJson?['birth_time'] as String?)?.substring(0, 5),
      birthPlace: birthJson?['birth_place'] as String?,
      latitude: (birthJson?['latitude'] as num?)?.toDouble(),
      longitude: (birthJson?['longitude'] as num?)?.toDouble(),
    );
  }
}

/// `{"key": bool}` maps from the API; anything else is ignored.
Map<String, bool> _flags(Object? raw) => {
  if (raw is Map)
    for (final entry in raw.entries)
      if (entry.key is String && entry.value is bool)
        entry.key as String: entry.value as bool,
};
