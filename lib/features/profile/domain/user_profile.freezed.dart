// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'user_profile.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$UserProfile {

 String get id; String get name; String get email; String? get avatarUrl;/// A bundled zodiac avatar (e.g. `pisces`), used without a photo.
 String? get avatarPreset; String? get bio; String get coverTheme;/// What others may see (sun/moon/rising sign, birth date, bio).
 Map<String, bool> get privacy; Map<String, bool> get notificationPrefs; DateTime? get birthDate;/// Local birth time as `HH:mm`.
 String? get birthTime; String? get birthPlace; double? get latitude; double? get longitude;/// Where the person lives now (IANA). Drives "today", local times,
/// appointments and notifications. Never used for the birth chart.
 String? get timezone;/// The zone of the birth place (IANA), used only for the birth chart. It
/// changes only when the birth data is edited - moving city does not move
/// the chart.
 String? get birthTimezone; String get language; SubscriptionTier get subscriptionTier;
/// Create a copy of UserProfile
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$UserProfileCopyWith<UserProfile> get copyWith => _$UserProfileCopyWithImpl<UserProfile>(this as UserProfile, _$identity);

  /// Serializes this UserProfile to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is UserProfile&&(identical(other.id, id) || other.id == id)&&(identical(other.name, name) || other.name == name)&&(identical(other.email, email) || other.email == email)&&(identical(other.avatarUrl, avatarUrl) || other.avatarUrl == avatarUrl)&&(identical(other.avatarPreset, avatarPreset) || other.avatarPreset == avatarPreset)&&(identical(other.bio, bio) || other.bio == bio)&&(identical(other.coverTheme, coverTheme) || other.coverTheme == coverTheme)&&const DeepCollectionEquality().equals(other.privacy, privacy)&&const DeepCollectionEquality().equals(other.notificationPrefs, notificationPrefs)&&(identical(other.birthDate, birthDate) || other.birthDate == birthDate)&&(identical(other.birthTime, birthTime) || other.birthTime == birthTime)&&(identical(other.birthPlace, birthPlace) || other.birthPlace == birthPlace)&&(identical(other.latitude, latitude) || other.latitude == latitude)&&(identical(other.longitude, longitude) || other.longitude == longitude)&&(identical(other.timezone, timezone) || other.timezone == timezone)&&(identical(other.birthTimezone, birthTimezone) || other.birthTimezone == birthTimezone)&&(identical(other.language, language) || other.language == language)&&(identical(other.subscriptionTier, subscriptionTier) || other.subscriptionTier == subscriptionTier));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,name,email,avatarUrl,avatarPreset,bio,coverTheme,const DeepCollectionEquality().hash(privacy),const DeepCollectionEquality().hash(notificationPrefs),birthDate,birthTime,birthPlace,latitude,longitude,timezone,birthTimezone,language,subscriptionTier);

@override
String toString() {
  return 'UserProfile(id: $id, name: $name, email: $email, avatarUrl: $avatarUrl, avatarPreset: $avatarPreset, bio: $bio, coverTheme: $coverTheme, privacy: $privacy, notificationPrefs: $notificationPrefs, birthDate: $birthDate, birthTime: $birthTime, birthPlace: $birthPlace, latitude: $latitude, longitude: $longitude, timezone: $timezone, birthTimezone: $birthTimezone, language: $language, subscriptionTier: $subscriptionTier)';
}


}

/// @nodoc
abstract mixin class $UserProfileCopyWith<$Res>  {
  factory $UserProfileCopyWith(UserProfile value, $Res Function(UserProfile) _then) = _$UserProfileCopyWithImpl;
@useResult
$Res call({
 String id, String name, String email, String? avatarUrl, String? avatarPreset, String? bio, String coverTheme, Map<String, bool> privacy, Map<String, bool> notificationPrefs, DateTime? birthDate, String? birthTime, String? birthPlace, double? latitude, double? longitude, String? timezone, String? birthTimezone, String language, SubscriptionTier subscriptionTier
});




}
/// @nodoc
class _$UserProfileCopyWithImpl<$Res>
    implements $UserProfileCopyWith<$Res> {
  _$UserProfileCopyWithImpl(this._self, this._then);

  final UserProfile _self;
  final $Res Function(UserProfile) _then;

/// Create a copy of UserProfile
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? id = null,Object? name = null,Object? email = null,Object? avatarUrl = freezed,Object? avatarPreset = freezed,Object? bio = freezed,Object? coverTheme = null,Object? privacy = null,Object? notificationPrefs = null,Object? birthDate = freezed,Object? birthTime = freezed,Object? birthPlace = freezed,Object? latitude = freezed,Object? longitude = freezed,Object? timezone = freezed,Object? birthTimezone = freezed,Object? language = null,Object? subscriptionTier = null,}) {
  return _then(_self.copyWith(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,name: null == name ? _self.name : name // ignore: cast_nullable_to_non_nullable
as String,email: null == email ? _self.email : email // ignore: cast_nullable_to_non_nullable
as String,avatarUrl: freezed == avatarUrl ? _self.avatarUrl : avatarUrl // ignore: cast_nullable_to_non_nullable
as String?,avatarPreset: freezed == avatarPreset ? _self.avatarPreset : avatarPreset // ignore: cast_nullable_to_non_nullable
as String?,bio: freezed == bio ? _self.bio : bio // ignore: cast_nullable_to_non_nullable
as String?,coverTheme: null == coverTheme ? _self.coverTheme : coverTheme // ignore: cast_nullable_to_non_nullable
as String,privacy: null == privacy ? _self.privacy : privacy // ignore: cast_nullable_to_non_nullable
as Map<String, bool>,notificationPrefs: null == notificationPrefs ? _self.notificationPrefs : notificationPrefs // ignore: cast_nullable_to_non_nullable
as Map<String, bool>,birthDate: freezed == birthDate ? _self.birthDate : birthDate // ignore: cast_nullable_to_non_nullable
as DateTime?,birthTime: freezed == birthTime ? _self.birthTime : birthTime // ignore: cast_nullable_to_non_nullable
as String?,birthPlace: freezed == birthPlace ? _self.birthPlace : birthPlace // ignore: cast_nullable_to_non_nullable
as String?,latitude: freezed == latitude ? _self.latitude : latitude // ignore: cast_nullable_to_non_nullable
as double?,longitude: freezed == longitude ? _self.longitude : longitude // ignore: cast_nullable_to_non_nullable
as double?,timezone: freezed == timezone ? _self.timezone : timezone // ignore: cast_nullable_to_non_nullable
as String?,birthTimezone: freezed == birthTimezone ? _self.birthTimezone : birthTimezone // ignore: cast_nullable_to_non_nullable
as String?,language: null == language ? _self.language : language // ignore: cast_nullable_to_non_nullable
as String,subscriptionTier: null == subscriptionTier ? _self.subscriptionTier : subscriptionTier // ignore: cast_nullable_to_non_nullable
as SubscriptionTier,
  ));
}

}


/// Adds pattern-matching-related methods to [UserProfile].
extension UserProfilePatterns on UserProfile {
/// A variant of `map` that fallback to returning `orElse`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _UserProfile value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _UserProfile() when $default != null:
return $default(_that);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// Callbacks receives the raw object, upcasted.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case final Subclass2 value:
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _UserProfile value)  $default,){
final _that = this;
switch (_that) {
case _UserProfile():
return $default(_that);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `map` that fallback to returning `null`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _UserProfile value)?  $default,){
final _that = this;
switch (_that) {
case _UserProfile() when $default != null:
return $default(_that);case _:
  return null;

}
}
/// A variant of `when` that fallback to an `orElse` callback.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String id,  String name,  String email,  String? avatarUrl,  String? avatarPreset,  String? bio,  String coverTheme,  Map<String, bool> privacy,  Map<String, bool> notificationPrefs,  DateTime? birthDate,  String? birthTime,  String? birthPlace,  double? latitude,  double? longitude,  String? timezone,  String? birthTimezone,  String language,  SubscriptionTier subscriptionTier)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _UserProfile() when $default != null:
return $default(_that.id,_that.name,_that.email,_that.avatarUrl,_that.avatarPreset,_that.bio,_that.coverTheme,_that.privacy,_that.notificationPrefs,_that.birthDate,_that.birthTime,_that.birthPlace,_that.latitude,_that.longitude,_that.timezone,_that.birthTimezone,_that.language,_that.subscriptionTier);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// As opposed to `map`, this offers destructuring.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case Subclass2(:final field2):
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String id,  String name,  String email,  String? avatarUrl,  String? avatarPreset,  String? bio,  String coverTheme,  Map<String, bool> privacy,  Map<String, bool> notificationPrefs,  DateTime? birthDate,  String? birthTime,  String? birthPlace,  double? latitude,  double? longitude,  String? timezone,  String? birthTimezone,  String language,  SubscriptionTier subscriptionTier)  $default,) {final _that = this;
switch (_that) {
case _UserProfile():
return $default(_that.id,_that.name,_that.email,_that.avatarUrl,_that.avatarPreset,_that.bio,_that.coverTheme,_that.privacy,_that.notificationPrefs,_that.birthDate,_that.birthTime,_that.birthPlace,_that.latitude,_that.longitude,_that.timezone,_that.birthTimezone,_that.language,_that.subscriptionTier);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `when` that fallback to returning `null`
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String id,  String name,  String email,  String? avatarUrl,  String? avatarPreset,  String? bio,  String coverTheme,  Map<String, bool> privacy,  Map<String, bool> notificationPrefs,  DateTime? birthDate,  String? birthTime,  String? birthPlace,  double? latitude,  double? longitude,  String? timezone,  String? birthTimezone,  String language,  SubscriptionTier subscriptionTier)?  $default,) {final _that = this;
switch (_that) {
case _UserProfile() when $default != null:
return $default(_that.id,_that.name,_that.email,_that.avatarUrl,_that.avatarPreset,_that.bio,_that.coverTheme,_that.privacy,_that.notificationPrefs,_that.birthDate,_that.birthTime,_that.birthPlace,_that.latitude,_that.longitude,_that.timezone,_that.birthTimezone,_that.language,_that.subscriptionTier);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _UserProfile extends UserProfile {
  const _UserProfile({required this.id, required this.name, required this.email, this.avatarUrl, this.avatarPreset, this.bio, this.coverTheme = 'cosmic_night', final  Map<String, bool> privacy = const <String, bool>{}, final  Map<String, bool> notificationPrefs = const <String, bool>{}, this.birthDate, this.birthTime, this.birthPlace, this.latitude, this.longitude, this.timezone, this.birthTimezone, this.language = 'tr', this.subscriptionTier = SubscriptionTier.free}): _privacy = privacy,_notificationPrefs = notificationPrefs,super._();
  factory _UserProfile.fromJson(Map<String, dynamic> json) => _$UserProfileFromJson(json);

@override final  String id;
@override final  String name;
@override final  String email;
@override final  String? avatarUrl;
/// A bundled zodiac avatar (e.g. `pisces`), used without a photo.
@override final  String? avatarPreset;
@override final  String? bio;
@override@JsonKey() final  String coverTheme;
/// What others may see (sun/moon/rising sign, birth date, bio).
 final  Map<String, bool> _privacy;
/// What others may see (sun/moon/rising sign, birth date, bio).
@override@JsonKey() Map<String, bool> get privacy {
  if (_privacy is EqualUnmodifiableMapView) return _privacy;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableMapView(_privacy);
}

 final  Map<String, bool> _notificationPrefs;
@override@JsonKey() Map<String, bool> get notificationPrefs {
  if (_notificationPrefs is EqualUnmodifiableMapView) return _notificationPrefs;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableMapView(_notificationPrefs);
}

@override final  DateTime? birthDate;
/// Local birth time as `HH:mm`.
@override final  String? birthTime;
@override final  String? birthPlace;
@override final  double? latitude;
@override final  double? longitude;
/// Where the person lives now (IANA). Drives "today", local times,
/// appointments and notifications. Never used for the birth chart.
@override final  String? timezone;
/// The zone of the birth place (IANA), used only for the birth chart. It
/// changes only when the birth data is edited - moving city does not move
/// the chart.
@override final  String? birthTimezone;
@override@JsonKey() final  String language;
@override@JsonKey() final  SubscriptionTier subscriptionTier;

/// Create a copy of UserProfile
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$UserProfileCopyWith<_UserProfile> get copyWith => __$UserProfileCopyWithImpl<_UserProfile>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$UserProfileToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _UserProfile&&(identical(other.id, id) || other.id == id)&&(identical(other.name, name) || other.name == name)&&(identical(other.email, email) || other.email == email)&&(identical(other.avatarUrl, avatarUrl) || other.avatarUrl == avatarUrl)&&(identical(other.avatarPreset, avatarPreset) || other.avatarPreset == avatarPreset)&&(identical(other.bio, bio) || other.bio == bio)&&(identical(other.coverTheme, coverTheme) || other.coverTheme == coverTheme)&&const DeepCollectionEquality().equals(other._privacy, _privacy)&&const DeepCollectionEquality().equals(other._notificationPrefs, _notificationPrefs)&&(identical(other.birthDate, birthDate) || other.birthDate == birthDate)&&(identical(other.birthTime, birthTime) || other.birthTime == birthTime)&&(identical(other.birthPlace, birthPlace) || other.birthPlace == birthPlace)&&(identical(other.latitude, latitude) || other.latitude == latitude)&&(identical(other.longitude, longitude) || other.longitude == longitude)&&(identical(other.timezone, timezone) || other.timezone == timezone)&&(identical(other.birthTimezone, birthTimezone) || other.birthTimezone == birthTimezone)&&(identical(other.language, language) || other.language == language)&&(identical(other.subscriptionTier, subscriptionTier) || other.subscriptionTier == subscriptionTier));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,name,email,avatarUrl,avatarPreset,bio,coverTheme,const DeepCollectionEquality().hash(_privacy),const DeepCollectionEquality().hash(_notificationPrefs),birthDate,birthTime,birthPlace,latitude,longitude,timezone,birthTimezone,language,subscriptionTier);

@override
String toString() {
  return 'UserProfile(id: $id, name: $name, email: $email, avatarUrl: $avatarUrl, avatarPreset: $avatarPreset, bio: $bio, coverTheme: $coverTheme, privacy: $privacy, notificationPrefs: $notificationPrefs, birthDate: $birthDate, birthTime: $birthTime, birthPlace: $birthPlace, latitude: $latitude, longitude: $longitude, timezone: $timezone, birthTimezone: $birthTimezone, language: $language, subscriptionTier: $subscriptionTier)';
}


}

/// @nodoc
abstract mixin class _$UserProfileCopyWith<$Res> implements $UserProfileCopyWith<$Res> {
  factory _$UserProfileCopyWith(_UserProfile value, $Res Function(_UserProfile) _then) = __$UserProfileCopyWithImpl;
@override @useResult
$Res call({
 String id, String name, String email, String? avatarUrl, String? avatarPreset, String? bio, String coverTheme, Map<String, bool> privacy, Map<String, bool> notificationPrefs, DateTime? birthDate, String? birthTime, String? birthPlace, double? latitude, double? longitude, String? timezone, String? birthTimezone, String language, SubscriptionTier subscriptionTier
});




}
/// @nodoc
class __$UserProfileCopyWithImpl<$Res>
    implements _$UserProfileCopyWith<$Res> {
  __$UserProfileCopyWithImpl(this._self, this._then);

  final _UserProfile _self;
  final $Res Function(_UserProfile) _then;

/// Create a copy of UserProfile
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? id = null,Object? name = null,Object? email = null,Object? avatarUrl = freezed,Object? avatarPreset = freezed,Object? bio = freezed,Object? coverTheme = null,Object? privacy = null,Object? notificationPrefs = null,Object? birthDate = freezed,Object? birthTime = freezed,Object? birthPlace = freezed,Object? latitude = freezed,Object? longitude = freezed,Object? timezone = freezed,Object? birthTimezone = freezed,Object? language = null,Object? subscriptionTier = null,}) {
  return _then(_UserProfile(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,name: null == name ? _self.name : name // ignore: cast_nullable_to_non_nullable
as String,email: null == email ? _self.email : email // ignore: cast_nullable_to_non_nullable
as String,avatarUrl: freezed == avatarUrl ? _self.avatarUrl : avatarUrl // ignore: cast_nullable_to_non_nullable
as String?,avatarPreset: freezed == avatarPreset ? _self.avatarPreset : avatarPreset // ignore: cast_nullable_to_non_nullable
as String?,bio: freezed == bio ? _self.bio : bio // ignore: cast_nullable_to_non_nullable
as String?,coverTheme: null == coverTheme ? _self.coverTheme : coverTheme // ignore: cast_nullable_to_non_nullable
as String,privacy: null == privacy ? _self._privacy : privacy // ignore: cast_nullable_to_non_nullable
as Map<String, bool>,notificationPrefs: null == notificationPrefs ? _self._notificationPrefs : notificationPrefs // ignore: cast_nullable_to_non_nullable
as Map<String, bool>,birthDate: freezed == birthDate ? _self.birthDate : birthDate // ignore: cast_nullable_to_non_nullable
as DateTime?,birthTime: freezed == birthTime ? _self.birthTime : birthTime // ignore: cast_nullable_to_non_nullable
as String?,birthPlace: freezed == birthPlace ? _self.birthPlace : birthPlace // ignore: cast_nullable_to_non_nullable
as String?,latitude: freezed == latitude ? _self.latitude : latitude // ignore: cast_nullable_to_non_nullable
as double?,longitude: freezed == longitude ? _self.longitude : longitude // ignore: cast_nullable_to_non_nullable
as double?,timezone: freezed == timezone ? _self.timezone : timezone // ignore: cast_nullable_to_non_nullable
as String?,birthTimezone: freezed == birthTimezone ? _self.birthTimezone : birthTimezone // ignore: cast_nullable_to_non_nullable
as String?,language: null == language ? _self.language : language // ignore: cast_nullable_to_non_nullable
as String,subscriptionTier: null == subscriptionTier ? _self.subscriptionTier : subscriptionTier // ignore: cast_nullable_to_non_nullable
as SubscriptionTier,
  ));
}


}

// dart format on
