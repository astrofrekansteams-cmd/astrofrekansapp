// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'birth_data.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$BirthData {

 DateTime get date; String? get time; String? get place; double? get latitude; double? get longitude; String? get timezone;
/// Create a copy of BirthData
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$BirthDataCopyWith<BirthData> get copyWith => _$BirthDataCopyWithImpl<BirthData>(this as BirthData, _$identity);

  /// Serializes this BirthData to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is BirthData&&(identical(other.date, date) || other.date == date)&&(identical(other.time, time) || other.time == time)&&(identical(other.place, place) || other.place == place)&&(identical(other.latitude, latitude) || other.latitude == latitude)&&(identical(other.longitude, longitude) || other.longitude == longitude)&&(identical(other.timezone, timezone) || other.timezone == timezone));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,date,time,place,latitude,longitude,timezone);

@override
String toString() {
  return 'BirthData(date: $date, time: $time, place: $place, latitude: $latitude, longitude: $longitude, timezone: $timezone)';
}


}

/// @nodoc
abstract mixin class $BirthDataCopyWith<$Res>  {
  factory $BirthDataCopyWith(BirthData value, $Res Function(BirthData) _then) = _$BirthDataCopyWithImpl;
@useResult
$Res call({
 DateTime date, String? time, String? place, double? latitude, double? longitude, String? timezone
});




}
/// @nodoc
class _$BirthDataCopyWithImpl<$Res>
    implements $BirthDataCopyWith<$Res> {
  _$BirthDataCopyWithImpl(this._self, this._then);

  final BirthData _self;
  final $Res Function(BirthData) _then;

/// Create a copy of BirthData
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? date = null,Object? time = freezed,Object? place = freezed,Object? latitude = freezed,Object? longitude = freezed,Object? timezone = freezed,}) {
  return _then(_self.copyWith(
date: null == date ? _self.date : date // ignore: cast_nullable_to_non_nullable
as DateTime,time: freezed == time ? _self.time : time // ignore: cast_nullable_to_non_nullable
as String?,place: freezed == place ? _self.place : place // ignore: cast_nullable_to_non_nullable
as String?,latitude: freezed == latitude ? _self.latitude : latitude // ignore: cast_nullable_to_non_nullable
as double?,longitude: freezed == longitude ? _self.longitude : longitude // ignore: cast_nullable_to_non_nullable
as double?,timezone: freezed == timezone ? _self.timezone : timezone // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

}


/// Adds pattern-matching-related methods to [BirthData].
extension BirthDataPatterns on BirthData {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _BirthData value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _BirthData() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _BirthData value)  $default,){
final _that = this;
switch (_that) {
case _BirthData():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _BirthData value)?  $default,){
final _that = this;
switch (_that) {
case _BirthData() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( DateTime date,  String? time,  String? place,  double? latitude,  double? longitude,  String? timezone)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _BirthData() when $default != null:
return $default(_that.date,_that.time,_that.place,_that.latitude,_that.longitude,_that.timezone);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( DateTime date,  String? time,  String? place,  double? latitude,  double? longitude,  String? timezone)  $default,) {final _that = this;
switch (_that) {
case _BirthData():
return $default(_that.date,_that.time,_that.place,_that.latitude,_that.longitude,_that.timezone);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( DateTime date,  String? time,  String? place,  double? latitude,  double? longitude,  String? timezone)?  $default,) {final _that = this;
switch (_that) {
case _BirthData() when $default != null:
return $default(_that.date,_that.time,_that.place,_that.latitude,_that.longitude,_that.timezone);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _BirthData extends BirthData {
  const _BirthData({required this.date, this.time, this.place, this.latitude, this.longitude, this.timezone}): super._();
  factory _BirthData.fromJson(Map<String, dynamic> json) => _$BirthDataFromJson(json);

@override final  DateTime date;
@override final  String? time;
@override final  String? place;
@override final  double? latitude;
@override final  double? longitude;
@override final  String? timezone;

/// Create a copy of BirthData
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$BirthDataCopyWith<_BirthData> get copyWith => __$BirthDataCopyWithImpl<_BirthData>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$BirthDataToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _BirthData&&(identical(other.date, date) || other.date == date)&&(identical(other.time, time) || other.time == time)&&(identical(other.place, place) || other.place == place)&&(identical(other.latitude, latitude) || other.latitude == latitude)&&(identical(other.longitude, longitude) || other.longitude == longitude)&&(identical(other.timezone, timezone) || other.timezone == timezone));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,date,time,place,latitude,longitude,timezone);

@override
String toString() {
  return 'BirthData(date: $date, time: $time, place: $place, latitude: $latitude, longitude: $longitude, timezone: $timezone)';
}


}

/// @nodoc
abstract mixin class _$BirthDataCopyWith<$Res> implements $BirthDataCopyWith<$Res> {
  factory _$BirthDataCopyWith(_BirthData value, $Res Function(_BirthData) _then) = __$BirthDataCopyWithImpl;
@override @useResult
$Res call({
 DateTime date, String? time, String? place, double? latitude, double? longitude, String? timezone
});




}
/// @nodoc
class __$BirthDataCopyWithImpl<$Res>
    implements _$BirthDataCopyWith<$Res> {
  __$BirthDataCopyWithImpl(this._self, this._then);

  final _BirthData _self;
  final $Res Function(_BirthData) _then;

/// Create a copy of BirthData
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? date = null,Object? time = freezed,Object? place = freezed,Object? latitude = freezed,Object? longitude = freezed,Object? timezone = freezed,}) {
  return _then(_BirthData(
date: null == date ? _self.date : date // ignore: cast_nullable_to_non_nullable
as DateTime,time: freezed == time ? _self.time : time // ignore: cast_nullable_to_non_nullable
as String?,place: freezed == place ? _self.place : place // ignore: cast_nullable_to_non_nullable
as String?,latitude: freezed == latitude ? _self.latitude : latitude // ignore: cast_nullable_to_non_nullable
as double?,longitude: freezed == longitude ? _self.longitude : longitude // ignore: cast_nullable_to_non_nullable
as double?,timezone: freezed == timezone ? _self.timezone : timezone // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}


}

// dart format on
