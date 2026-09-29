import 'package:freezed_annotation/freezed_annotation.dart';

import '../../../core/astrology/domain/birth_data.dart';
import '../../../core/utils/text_case.dart';

part 'user_profile.freezed.dart';
part 'user_profile.g.dart';

/// Plans in ascending order; each includes everything below it.
enum SubscriptionTier {
  free('free'),
  premium('premium'),
  cosmicPlus('cosmic_plus');

  const SubscriptionTier(this.wire);
  final String wire;

  static SubscriptionTier fromWire(String? wire) => values.firstWhere(
    (tier) => tier.wire == wire,
    orElse: () => SubscriptionTier.free,
  );

  bool includes(SubscriptionTier other) => index >= other.index;
  bool get isPaid => this != SubscriptionTier.free;
}

/// The signed-in user. Birth data is personal: it is cached in secure storage
/// only and is never written to logs.
@freezed
abstract class UserProfile with _$UserProfile {
  const factory UserProfile({
    required String id,
    required String name,
    required String email,
    String? avatarUrl,

    /// A bundled zodiac avatar (e.g. `pisces`), used without a photo.
    String? avatarPreset,
    String? bio,
    @Default('cosmic_night') String coverTheme,

    /// What others may see (sun/moon/rising sign, birth date, bio).
    @Default(<String, bool>{}) Map<String, bool> privacy,
    @Default(<String, bool>{}) Map<String, bool> notificationPrefs,
    DateTime? birthDate,

    /// Local birth time as `HH:mm`.
    String? birthTime,
    String? birthPlace,
    double? latitude,
    double? longitude,

    /// Where the person lives now (IANA). Drives "today", local times,
    /// appointments and notifications. Never used for the birth chart.
    String? timezone,

    /// The zone of the birth place (IANA), used only for the birth chart. It
    /// changes only when the birth data is edited - moving city does not move
    /// the chart.
    String? birthTimezone,
    @Default('tr') String language,
    @Default(SubscriptionTier.free) SubscriptionTier subscriptionTier,
  }) = _UserProfile;

  const UserProfile._();

  factory UserProfile.fromJson(Map<String, dynamic> json) =>
      _$UserProfileFromJson(json);

  bool get isPremium => subscriptionTier.includes(SubscriptionTier.premium);

  bool get hasBirthData => birthDate != null;

  String get initials {
    final List<String> parts = name.trim().split(RegExp(r'\s+'));
    if (parts.isEmpty || parts.first.isEmpty) return '?';
    if (parts.length == 1) {
      return parts.first.substring(0, 1).toUpperCaseFor(language);
    }
    return (parts.first.substring(0, 1) + parts.last.substring(0, 1))
        .toUpperCaseFor(language);
  }

  String get firstName => name.trim().split(RegExp(r'\s+')).first;

  BirthData? get birthData => birthDate == null
      ? null
      : BirthData(
          date: birthDate!,
          time: birthTime,
          place: birthPlace,
          latitude: latitude,
          longitude: longitude,
          timezone: birthTimezone,
        );
}
