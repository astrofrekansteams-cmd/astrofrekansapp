// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'user_profile.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_UserProfile _$UserProfileFromJson(Map<String, dynamic> json) => _UserProfile(
  id: json['id'] as String,
  name: json['name'] as String,
  email: json['email'] as String,
  avatarUrl: json['avatar_url'] as String?,
  avatarPreset: json['avatar_preset'] as String?,
  bio: json['bio'] as String?,
  coverTheme: json['cover_theme'] as String? ?? 'cosmic_night',
  privacy:
      (json['privacy'] as Map<String, dynamic>?)?.map(
        (k, e) => MapEntry(k, e as bool),
      ) ??
      const <String, bool>{},
  notificationPrefs:
      (json['notification_prefs'] as Map<String, dynamic>?)?.map(
        (k, e) => MapEntry(k, e as bool),
      ) ??
      const <String, bool>{},
  birthDate: json['birth_date'] == null
      ? null
      : DateTime.parse(json['birth_date'] as String),
  birthTime: json['birth_time'] as String?,
  birthPlace: json['birth_place'] as String?,
  latitude: (json['latitude'] as num?)?.toDouble(),
  longitude: (json['longitude'] as num?)?.toDouble(),
  timezone: json['timezone'] as String?,
  birthTimezone: json['birth_timezone'] as String?,
  language: json['language'] as String? ?? 'tr',
  subscriptionTier:
      $enumDecodeNullable(
        _$SubscriptionTierEnumMap,
        json['subscription_tier'],
      ) ??
      SubscriptionTier.free,
);

Map<String, dynamic> _$UserProfileToJson(
  _UserProfile instance,
) => <String, dynamic>{
  'id': instance.id,
  'name': instance.name,
  'email': instance.email,
  'avatar_url': ?instance.avatarUrl,
  'avatar_preset': ?instance.avatarPreset,
  'bio': ?instance.bio,
  'cover_theme': instance.coverTheme,
  'privacy': instance.privacy,
  'notification_prefs': instance.notificationPrefs,
  'birth_date': ?instance.birthDate?.toIso8601String(),
  'birth_time': ?instance.birthTime,
  'birth_place': ?instance.birthPlace,
  'latitude': ?instance.latitude,
  'longitude': ?instance.longitude,
  'timezone': ?instance.timezone,
  'birth_timezone': ?instance.birthTimezone,
  'language': instance.language,
  'subscription_tier': _$SubscriptionTierEnumMap[instance.subscriptionTier]!,
};

const _$SubscriptionTierEnumMap = {
  SubscriptionTier.free: 'free',
  SubscriptionTier.premium: 'premium',
  SubscriptionTier.cosmicPlus: 'cosmicPlus',
};
