// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'natal_chart.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$ChartSubject {

 String get kind; DateTime get momentUtc; double? get latitude; double? get longitude; String? get timezone; String? get locationName;
/// Create a copy of ChartSubject
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$ChartSubjectCopyWith<ChartSubject> get copyWith => _$ChartSubjectCopyWithImpl<ChartSubject>(this as ChartSubject, _$identity);

  /// Serializes this ChartSubject to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is ChartSubject&&(identical(other.kind, kind) || other.kind == kind)&&(identical(other.momentUtc, momentUtc) || other.momentUtc == momentUtc)&&(identical(other.latitude, latitude) || other.latitude == latitude)&&(identical(other.longitude, longitude) || other.longitude == longitude)&&(identical(other.timezone, timezone) || other.timezone == timezone)&&(identical(other.locationName, locationName) || other.locationName == locationName));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,kind,momentUtc,latitude,longitude,timezone,locationName);

@override
String toString() {
  return 'ChartSubject(kind: $kind, momentUtc: $momentUtc, latitude: $latitude, longitude: $longitude, timezone: $timezone, locationName: $locationName)';
}


}

/// @nodoc
abstract mixin class $ChartSubjectCopyWith<$Res>  {
  factory $ChartSubjectCopyWith(ChartSubject value, $Res Function(ChartSubject) _then) = _$ChartSubjectCopyWithImpl;
@useResult
$Res call({
 String kind, DateTime momentUtc, double? latitude, double? longitude, String? timezone, String? locationName
});




}
/// @nodoc
class _$ChartSubjectCopyWithImpl<$Res>
    implements $ChartSubjectCopyWith<$Res> {
  _$ChartSubjectCopyWithImpl(this._self, this._then);

  final ChartSubject _self;
  final $Res Function(ChartSubject) _then;

/// Create a copy of ChartSubject
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? kind = null,Object? momentUtc = null,Object? latitude = freezed,Object? longitude = freezed,Object? timezone = freezed,Object? locationName = freezed,}) {
  return _then(_self.copyWith(
kind: null == kind ? _self.kind : kind // ignore: cast_nullable_to_non_nullable
as String,momentUtc: null == momentUtc ? _self.momentUtc : momentUtc // ignore: cast_nullable_to_non_nullable
as DateTime,latitude: freezed == latitude ? _self.latitude : latitude // ignore: cast_nullable_to_non_nullable
as double?,longitude: freezed == longitude ? _self.longitude : longitude // ignore: cast_nullable_to_non_nullable
as double?,timezone: freezed == timezone ? _self.timezone : timezone // ignore: cast_nullable_to_non_nullable
as String?,locationName: freezed == locationName ? _self.locationName : locationName // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

}


/// Adds pattern-matching-related methods to [ChartSubject].
extension ChartSubjectPatterns on ChartSubject {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _ChartSubject value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _ChartSubject() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _ChartSubject value)  $default,){
final _that = this;
switch (_that) {
case _ChartSubject():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _ChartSubject value)?  $default,){
final _that = this;
switch (_that) {
case _ChartSubject() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String kind,  DateTime momentUtc,  double? latitude,  double? longitude,  String? timezone,  String? locationName)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _ChartSubject() when $default != null:
return $default(_that.kind,_that.momentUtc,_that.latitude,_that.longitude,_that.timezone,_that.locationName);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String kind,  DateTime momentUtc,  double? latitude,  double? longitude,  String? timezone,  String? locationName)  $default,) {final _that = this;
switch (_that) {
case _ChartSubject():
return $default(_that.kind,_that.momentUtc,_that.latitude,_that.longitude,_that.timezone,_that.locationName);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String kind,  DateTime momentUtc,  double? latitude,  double? longitude,  String? timezone,  String? locationName)?  $default,) {final _that = this;
switch (_that) {
case _ChartSubject() when $default != null:
return $default(_that.kind,_that.momentUtc,_that.latitude,_that.longitude,_that.timezone,_that.locationName);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _ChartSubject implements ChartSubject {
  const _ChartSubject({required this.kind, required this.momentUtc, this.latitude, this.longitude, this.timezone, this.locationName});
  factory _ChartSubject.fromJson(Map<String, dynamic> json) => _$ChartSubjectFromJson(json);

@override final  String kind;
@override final  DateTime momentUtc;
@override final  double? latitude;
@override final  double? longitude;
@override final  String? timezone;
@override final  String? locationName;

/// Create a copy of ChartSubject
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$ChartSubjectCopyWith<_ChartSubject> get copyWith => __$ChartSubjectCopyWithImpl<_ChartSubject>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$ChartSubjectToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _ChartSubject&&(identical(other.kind, kind) || other.kind == kind)&&(identical(other.momentUtc, momentUtc) || other.momentUtc == momentUtc)&&(identical(other.latitude, latitude) || other.latitude == latitude)&&(identical(other.longitude, longitude) || other.longitude == longitude)&&(identical(other.timezone, timezone) || other.timezone == timezone)&&(identical(other.locationName, locationName) || other.locationName == locationName));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,kind,momentUtc,latitude,longitude,timezone,locationName);

@override
String toString() {
  return 'ChartSubject(kind: $kind, momentUtc: $momentUtc, latitude: $latitude, longitude: $longitude, timezone: $timezone, locationName: $locationName)';
}


}

/// @nodoc
abstract mixin class _$ChartSubjectCopyWith<$Res> implements $ChartSubjectCopyWith<$Res> {
  factory _$ChartSubjectCopyWith(_ChartSubject value, $Res Function(_ChartSubject) _then) = __$ChartSubjectCopyWithImpl;
@override @useResult
$Res call({
 String kind, DateTime momentUtc, double? latitude, double? longitude, String? timezone, String? locationName
});




}
/// @nodoc
class __$ChartSubjectCopyWithImpl<$Res>
    implements _$ChartSubjectCopyWith<$Res> {
  __$ChartSubjectCopyWithImpl(this._self, this._then);

  final _ChartSubject _self;
  final $Res Function(_ChartSubject) _then;

/// Create a copy of ChartSubject
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? kind = null,Object? momentUtc = null,Object? latitude = freezed,Object? longitude = freezed,Object? timezone = freezed,Object? locationName = freezed,}) {
  return _then(_ChartSubject(
kind: null == kind ? _self.kind : kind // ignore: cast_nullable_to_non_nullable
as String,momentUtc: null == momentUtc ? _self.momentUtc : momentUtc // ignore: cast_nullable_to_non_nullable
as DateTime,latitude: freezed == latitude ? _self.latitude : latitude // ignore: cast_nullable_to_non_nullable
as double?,longitude: freezed == longitude ? _self.longitude : longitude // ignore: cast_nullable_to_non_nullable
as double?,timezone: freezed == timezone ? _self.timezone : timezone // ignore: cast_nullable_to_non_nullable
as String?,locationName: freezed == locationName ? _self.locationName : locationName // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}


}


/// @nodoc
mixin _$PlanetPosition {

 Planet get planet; ZodiacSign get sign;/// Ecliptic longitude in degrees (0-360).
 double get longitude;/// House number 1-12. Null when the birth time is unknown.
 int? get house; bool get isRetrograde; double? get latitude; double? get speedLongitude; int? get reportedDegree; int? get reportedMinute;
/// Create a copy of PlanetPosition
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$PlanetPositionCopyWith<PlanetPosition> get copyWith => _$PlanetPositionCopyWithImpl<PlanetPosition>(this as PlanetPosition, _$identity);

  /// Serializes this PlanetPosition to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is PlanetPosition&&(identical(other.planet, planet) || other.planet == planet)&&(identical(other.sign, sign) || other.sign == sign)&&(identical(other.longitude, longitude) || other.longitude == longitude)&&(identical(other.house, house) || other.house == house)&&(identical(other.isRetrograde, isRetrograde) || other.isRetrograde == isRetrograde)&&(identical(other.latitude, latitude) || other.latitude == latitude)&&(identical(other.speedLongitude, speedLongitude) || other.speedLongitude == speedLongitude)&&(identical(other.reportedDegree, reportedDegree) || other.reportedDegree == reportedDegree)&&(identical(other.reportedMinute, reportedMinute) || other.reportedMinute == reportedMinute));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,planet,sign,longitude,house,isRetrograde,latitude,speedLongitude,reportedDegree,reportedMinute);

@override
String toString() {
  return 'PlanetPosition(planet: $planet, sign: $sign, longitude: $longitude, house: $house, isRetrograde: $isRetrograde, latitude: $latitude, speedLongitude: $speedLongitude, reportedDegree: $reportedDegree, reportedMinute: $reportedMinute)';
}


}

/// @nodoc
abstract mixin class $PlanetPositionCopyWith<$Res>  {
  factory $PlanetPositionCopyWith(PlanetPosition value, $Res Function(PlanetPosition) _then) = _$PlanetPositionCopyWithImpl;
@useResult
$Res call({
 Planet planet, ZodiacSign sign, double longitude, int? house, bool isRetrograde, double? latitude, double? speedLongitude, int? reportedDegree, int? reportedMinute
});




}
/// @nodoc
class _$PlanetPositionCopyWithImpl<$Res>
    implements $PlanetPositionCopyWith<$Res> {
  _$PlanetPositionCopyWithImpl(this._self, this._then);

  final PlanetPosition _self;
  final $Res Function(PlanetPosition) _then;

/// Create a copy of PlanetPosition
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? planet = null,Object? sign = null,Object? longitude = null,Object? house = freezed,Object? isRetrograde = null,Object? latitude = freezed,Object? speedLongitude = freezed,Object? reportedDegree = freezed,Object? reportedMinute = freezed,}) {
  return _then(_self.copyWith(
planet: null == planet ? _self.planet : planet // ignore: cast_nullable_to_non_nullable
as Planet,sign: null == sign ? _self.sign : sign // ignore: cast_nullable_to_non_nullable
as ZodiacSign,longitude: null == longitude ? _self.longitude : longitude // ignore: cast_nullable_to_non_nullable
as double,house: freezed == house ? _self.house : house // ignore: cast_nullable_to_non_nullable
as int?,isRetrograde: null == isRetrograde ? _self.isRetrograde : isRetrograde // ignore: cast_nullable_to_non_nullable
as bool,latitude: freezed == latitude ? _self.latitude : latitude // ignore: cast_nullable_to_non_nullable
as double?,speedLongitude: freezed == speedLongitude ? _self.speedLongitude : speedLongitude // ignore: cast_nullable_to_non_nullable
as double?,reportedDegree: freezed == reportedDegree ? _self.reportedDegree : reportedDegree // ignore: cast_nullable_to_non_nullable
as int?,reportedMinute: freezed == reportedMinute ? _self.reportedMinute : reportedMinute // ignore: cast_nullable_to_non_nullable
as int?,
  ));
}

}


/// Adds pattern-matching-related methods to [PlanetPosition].
extension PlanetPositionPatterns on PlanetPosition {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _PlanetPosition value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _PlanetPosition() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _PlanetPosition value)  $default,){
final _that = this;
switch (_that) {
case _PlanetPosition():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _PlanetPosition value)?  $default,){
final _that = this;
switch (_that) {
case _PlanetPosition() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( Planet planet,  ZodiacSign sign,  double longitude,  int? house,  bool isRetrograde,  double? latitude,  double? speedLongitude,  int? reportedDegree,  int? reportedMinute)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _PlanetPosition() when $default != null:
return $default(_that.planet,_that.sign,_that.longitude,_that.house,_that.isRetrograde,_that.latitude,_that.speedLongitude,_that.reportedDegree,_that.reportedMinute);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( Planet planet,  ZodiacSign sign,  double longitude,  int? house,  bool isRetrograde,  double? latitude,  double? speedLongitude,  int? reportedDegree,  int? reportedMinute)  $default,) {final _that = this;
switch (_that) {
case _PlanetPosition():
return $default(_that.planet,_that.sign,_that.longitude,_that.house,_that.isRetrograde,_that.latitude,_that.speedLongitude,_that.reportedDegree,_that.reportedMinute);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( Planet planet,  ZodiacSign sign,  double longitude,  int? house,  bool isRetrograde,  double? latitude,  double? speedLongitude,  int? reportedDegree,  int? reportedMinute)?  $default,) {final _that = this;
switch (_that) {
case _PlanetPosition() when $default != null:
return $default(_that.planet,_that.sign,_that.longitude,_that.house,_that.isRetrograde,_that.latitude,_that.speedLongitude,_that.reportedDegree,_that.reportedMinute);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _PlanetPosition extends PlanetPosition {
  const _PlanetPosition({required this.planet, required this.sign, required this.longitude, this.house, this.isRetrograde = false, this.latitude, this.speedLongitude, this.reportedDegree, this.reportedMinute}): super._();
  factory _PlanetPosition.fromJson(Map<String, dynamic> json) => _$PlanetPositionFromJson(json);

@override final  Planet planet;
@override final  ZodiacSign sign;
/// Ecliptic longitude in degrees (0-360).
@override final  double longitude;
/// House number 1-12. Null when the birth time is unknown.
@override final  int? house;
@override@JsonKey() final  bool isRetrograde;
@override final  double? latitude;
@override final  double? speedLongitude;
@override final  int? reportedDegree;
@override final  int? reportedMinute;

/// Create a copy of PlanetPosition
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$PlanetPositionCopyWith<_PlanetPosition> get copyWith => __$PlanetPositionCopyWithImpl<_PlanetPosition>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$PlanetPositionToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _PlanetPosition&&(identical(other.planet, planet) || other.planet == planet)&&(identical(other.sign, sign) || other.sign == sign)&&(identical(other.longitude, longitude) || other.longitude == longitude)&&(identical(other.house, house) || other.house == house)&&(identical(other.isRetrograde, isRetrograde) || other.isRetrograde == isRetrograde)&&(identical(other.latitude, latitude) || other.latitude == latitude)&&(identical(other.speedLongitude, speedLongitude) || other.speedLongitude == speedLongitude)&&(identical(other.reportedDegree, reportedDegree) || other.reportedDegree == reportedDegree)&&(identical(other.reportedMinute, reportedMinute) || other.reportedMinute == reportedMinute));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,planet,sign,longitude,house,isRetrograde,latitude,speedLongitude,reportedDegree,reportedMinute);

@override
String toString() {
  return 'PlanetPosition(planet: $planet, sign: $sign, longitude: $longitude, house: $house, isRetrograde: $isRetrograde, latitude: $latitude, speedLongitude: $speedLongitude, reportedDegree: $reportedDegree, reportedMinute: $reportedMinute)';
}


}

/// @nodoc
abstract mixin class _$PlanetPositionCopyWith<$Res> implements $PlanetPositionCopyWith<$Res> {
  factory _$PlanetPositionCopyWith(_PlanetPosition value, $Res Function(_PlanetPosition) _then) = __$PlanetPositionCopyWithImpl;
@override @useResult
$Res call({
 Planet planet, ZodiacSign sign, double longitude, int? house, bool isRetrograde, double? latitude, double? speedLongitude, int? reportedDegree, int? reportedMinute
});




}
/// @nodoc
class __$PlanetPositionCopyWithImpl<$Res>
    implements _$PlanetPositionCopyWith<$Res> {
  __$PlanetPositionCopyWithImpl(this._self, this._then);

  final _PlanetPosition _self;
  final $Res Function(_PlanetPosition) _then;

/// Create a copy of PlanetPosition
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? planet = null,Object? sign = null,Object? longitude = null,Object? house = freezed,Object? isRetrograde = null,Object? latitude = freezed,Object? speedLongitude = freezed,Object? reportedDegree = freezed,Object? reportedMinute = freezed,}) {
  return _then(_PlanetPosition(
planet: null == planet ? _self.planet : planet // ignore: cast_nullable_to_non_nullable
as Planet,sign: null == sign ? _self.sign : sign // ignore: cast_nullable_to_non_nullable
as ZodiacSign,longitude: null == longitude ? _self.longitude : longitude // ignore: cast_nullable_to_non_nullable
as double,house: freezed == house ? _self.house : house // ignore: cast_nullable_to_non_nullable
as int?,isRetrograde: null == isRetrograde ? _self.isRetrograde : isRetrograde // ignore: cast_nullable_to_non_nullable
as bool,latitude: freezed == latitude ? _self.latitude : latitude // ignore: cast_nullable_to_non_nullable
as double?,speedLongitude: freezed == speedLongitude ? _self.speedLongitude : speedLongitude // ignore: cast_nullable_to_non_nullable
as double?,reportedDegree: freezed == reportedDegree ? _self.reportedDegree : reportedDegree // ignore: cast_nullable_to_non_nullable
as int?,reportedMinute: freezed == reportedMinute ? _self.reportedMinute : reportedMinute // ignore: cast_nullable_to_non_nullable
as int?,
  ));
}


}


/// @nodoc
mixin _$HousePosition {

 int get number; ZodiacSign get sign; double get cuspLongitude; int? get degree; int? get minute;
/// Create a copy of HousePosition
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$HousePositionCopyWith<HousePosition> get copyWith => _$HousePositionCopyWithImpl<HousePosition>(this as HousePosition, _$identity);

  /// Serializes this HousePosition to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is HousePosition&&(identical(other.number, number) || other.number == number)&&(identical(other.sign, sign) || other.sign == sign)&&(identical(other.cuspLongitude, cuspLongitude) || other.cuspLongitude == cuspLongitude)&&(identical(other.degree, degree) || other.degree == degree)&&(identical(other.minute, minute) || other.minute == minute));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,number,sign,cuspLongitude,degree,minute);

@override
String toString() {
  return 'HousePosition(number: $number, sign: $sign, cuspLongitude: $cuspLongitude, degree: $degree, minute: $minute)';
}


}

/// @nodoc
abstract mixin class $HousePositionCopyWith<$Res>  {
  factory $HousePositionCopyWith(HousePosition value, $Res Function(HousePosition) _then) = _$HousePositionCopyWithImpl;
@useResult
$Res call({
 int number, ZodiacSign sign, double cuspLongitude, int? degree, int? minute
});




}
/// @nodoc
class _$HousePositionCopyWithImpl<$Res>
    implements $HousePositionCopyWith<$Res> {
  _$HousePositionCopyWithImpl(this._self, this._then);

  final HousePosition _self;
  final $Res Function(HousePosition) _then;

/// Create a copy of HousePosition
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? number = null,Object? sign = null,Object? cuspLongitude = null,Object? degree = freezed,Object? minute = freezed,}) {
  return _then(_self.copyWith(
number: null == number ? _self.number : number // ignore: cast_nullable_to_non_nullable
as int,sign: null == sign ? _self.sign : sign // ignore: cast_nullable_to_non_nullable
as ZodiacSign,cuspLongitude: null == cuspLongitude ? _self.cuspLongitude : cuspLongitude // ignore: cast_nullable_to_non_nullable
as double,degree: freezed == degree ? _self.degree : degree // ignore: cast_nullable_to_non_nullable
as int?,minute: freezed == minute ? _self.minute : minute // ignore: cast_nullable_to_non_nullable
as int?,
  ));
}

}


/// Adds pattern-matching-related methods to [HousePosition].
extension HousePositionPatterns on HousePosition {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _HousePosition value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _HousePosition() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _HousePosition value)  $default,){
final _that = this;
switch (_that) {
case _HousePosition():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _HousePosition value)?  $default,){
final _that = this;
switch (_that) {
case _HousePosition() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( int number,  ZodiacSign sign,  double cuspLongitude,  int? degree,  int? minute)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _HousePosition() when $default != null:
return $default(_that.number,_that.sign,_that.cuspLongitude,_that.degree,_that.minute);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( int number,  ZodiacSign sign,  double cuspLongitude,  int? degree,  int? minute)  $default,) {final _that = this;
switch (_that) {
case _HousePosition():
return $default(_that.number,_that.sign,_that.cuspLongitude,_that.degree,_that.minute);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( int number,  ZodiacSign sign,  double cuspLongitude,  int? degree,  int? minute)?  $default,) {final _that = this;
switch (_that) {
case _HousePosition() when $default != null:
return $default(_that.number,_that.sign,_that.cuspLongitude,_that.degree,_that.minute);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _HousePosition extends HousePosition {
  const _HousePosition({required this.number, required this.sign, required this.cuspLongitude, this.degree, this.minute}): super._();
  factory _HousePosition.fromJson(Map<String, dynamic> json) => _$HousePositionFromJson(json);

@override final  int number;
@override final  ZodiacSign sign;
@override final  double cuspLongitude;
@override final  int? degree;
@override final  int? minute;

/// Create a copy of HousePosition
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$HousePositionCopyWith<_HousePosition> get copyWith => __$HousePositionCopyWithImpl<_HousePosition>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$HousePositionToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _HousePosition&&(identical(other.number, number) || other.number == number)&&(identical(other.sign, sign) || other.sign == sign)&&(identical(other.cuspLongitude, cuspLongitude) || other.cuspLongitude == cuspLongitude)&&(identical(other.degree, degree) || other.degree == degree)&&(identical(other.minute, minute) || other.minute == minute));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,number,sign,cuspLongitude,degree,minute);

@override
String toString() {
  return 'HousePosition(number: $number, sign: $sign, cuspLongitude: $cuspLongitude, degree: $degree, minute: $minute)';
}


}

/// @nodoc
abstract mixin class _$HousePositionCopyWith<$Res> implements $HousePositionCopyWith<$Res> {
  factory _$HousePositionCopyWith(_HousePosition value, $Res Function(_HousePosition) _then) = __$HousePositionCopyWithImpl;
@override @useResult
$Res call({
 int number, ZodiacSign sign, double cuspLongitude, int? degree, int? minute
});




}
/// @nodoc
class __$HousePositionCopyWithImpl<$Res>
    implements _$HousePositionCopyWith<$Res> {
  __$HousePositionCopyWithImpl(this._self, this._then);

  final _HousePosition _self;
  final $Res Function(_HousePosition) _then;

/// Create a copy of HousePosition
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? number = null,Object? sign = null,Object? cuspLongitude = null,Object? degree = freezed,Object? minute = freezed,}) {
  return _then(_HousePosition(
number: null == number ? _self.number : number // ignore: cast_nullable_to_non_nullable
as int,sign: null == sign ? _self.sign : sign // ignore: cast_nullable_to_non_nullable
as ZodiacSign,cuspLongitude: null == cuspLongitude ? _self.cuspLongitude : cuspLongitude // ignore: cast_nullable_to_non_nullable
as double,degree: freezed == degree ? _self.degree : degree // ignore: cast_nullable_to_non_nullable
as int?,minute: freezed == minute ? _self.minute : minute // ignore: cast_nullable_to_non_nullable
as int?,
  ));
}


}


/// @nodoc
mixin _$NatalAspect {

 Planet get first; Planet get second; AspectType get type; double get orb;/// True when the faster body is still moving towards exactness.
 bool get applying; String? get rawNature;
/// Create a copy of NatalAspect
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$NatalAspectCopyWith<NatalAspect> get copyWith => _$NatalAspectCopyWithImpl<NatalAspect>(this as NatalAspect, _$identity);

  /// Serializes this NatalAspect to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is NatalAspect&&(identical(other.first, first) || other.first == first)&&(identical(other.second, second) || other.second == second)&&(identical(other.type, type) || other.type == type)&&(identical(other.orb, orb) || other.orb == orb)&&(identical(other.applying, applying) || other.applying == applying)&&(identical(other.rawNature, rawNature) || other.rawNature == rawNature));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,first,second,type,orb,applying,rawNature);

@override
String toString() {
  return 'NatalAspect(first: $first, second: $second, type: $type, orb: $orb, applying: $applying, rawNature: $rawNature)';
}


}

/// @nodoc
abstract mixin class $NatalAspectCopyWith<$Res>  {
  factory $NatalAspectCopyWith(NatalAspect value, $Res Function(NatalAspect) _then) = _$NatalAspectCopyWithImpl;
@useResult
$Res call({
 Planet first, Planet second, AspectType type, double orb, bool applying, String? rawNature
});




}
/// @nodoc
class _$NatalAspectCopyWithImpl<$Res>
    implements $NatalAspectCopyWith<$Res> {
  _$NatalAspectCopyWithImpl(this._self, this._then);

  final NatalAspect _self;
  final $Res Function(NatalAspect) _then;

/// Create a copy of NatalAspect
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? first = null,Object? second = null,Object? type = null,Object? orb = null,Object? applying = null,Object? rawNature = freezed,}) {
  return _then(_self.copyWith(
first: null == first ? _self.first : first // ignore: cast_nullable_to_non_nullable
as Planet,second: null == second ? _self.second : second // ignore: cast_nullable_to_non_nullable
as Planet,type: null == type ? _self.type : type // ignore: cast_nullable_to_non_nullable
as AspectType,orb: null == orb ? _self.orb : orb // ignore: cast_nullable_to_non_nullable
as double,applying: null == applying ? _self.applying : applying // ignore: cast_nullable_to_non_nullable
as bool,rawNature: freezed == rawNature ? _self.rawNature : rawNature // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

}


/// Adds pattern-matching-related methods to [NatalAspect].
extension NatalAspectPatterns on NatalAspect {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _NatalAspect value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _NatalAspect() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _NatalAspect value)  $default,){
final _that = this;
switch (_that) {
case _NatalAspect():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _NatalAspect value)?  $default,){
final _that = this;
switch (_that) {
case _NatalAspect() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( Planet first,  Planet second,  AspectType type,  double orb,  bool applying,  String? rawNature)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _NatalAspect() when $default != null:
return $default(_that.first,_that.second,_that.type,_that.orb,_that.applying,_that.rawNature);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( Planet first,  Planet second,  AspectType type,  double orb,  bool applying,  String? rawNature)  $default,) {final _that = this;
switch (_that) {
case _NatalAspect():
return $default(_that.first,_that.second,_that.type,_that.orb,_that.applying,_that.rawNature);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( Planet first,  Planet second,  AspectType type,  double orb,  bool applying,  String? rawNature)?  $default,) {final _that = this;
switch (_that) {
case _NatalAspect() when $default != null:
return $default(_that.first,_that.second,_that.type,_that.orb,_that.applying,_that.rawNature);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _NatalAspect extends NatalAspect {
  const _NatalAspect({required this.first, required this.second, required this.type, required this.orb, this.applying = false, this.rawNature}): super._();
  factory _NatalAspect.fromJson(Map<String, dynamic> json) => _$NatalAspectFromJson(json);

@override final  Planet first;
@override final  Planet second;
@override final  AspectType type;
@override final  double orb;
/// True when the faster body is still moving towards exactness.
@override@JsonKey() final  bool applying;
@override final  String? rawNature;

/// Create a copy of NatalAspect
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$NatalAspectCopyWith<_NatalAspect> get copyWith => __$NatalAspectCopyWithImpl<_NatalAspect>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$NatalAspectToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _NatalAspect&&(identical(other.first, first) || other.first == first)&&(identical(other.second, second) || other.second == second)&&(identical(other.type, type) || other.type == type)&&(identical(other.orb, orb) || other.orb == orb)&&(identical(other.applying, applying) || other.applying == applying)&&(identical(other.rawNature, rawNature) || other.rawNature == rawNature));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,first,second,type,orb,applying,rawNature);

@override
String toString() {
  return 'NatalAspect(first: $first, second: $second, type: $type, orb: $orb, applying: $applying, rawNature: $rawNature)';
}


}

/// @nodoc
abstract mixin class _$NatalAspectCopyWith<$Res> implements $NatalAspectCopyWith<$Res> {
  factory _$NatalAspectCopyWith(_NatalAspect value, $Res Function(_NatalAspect) _then) = __$NatalAspectCopyWithImpl;
@override @useResult
$Res call({
 Planet first, Planet second, AspectType type, double orb, bool applying, String? rawNature
});




}
/// @nodoc
class __$NatalAspectCopyWithImpl<$Res>
    implements _$NatalAspectCopyWith<$Res> {
  __$NatalAspectCopyWithImpl(this._self, this._then);

  final _NatalAspect _self;
  final $Res Function(_NatalAspect) _then;

/// Create a copy of NatalAspect
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? first = null,Object? second = null,Object? type = null,Object? orb = null,Object? applying = null,Object? rawNature = freezed,}) {
  return _then(_NatalAspect(
first: null == first ? _self.first : first // ignore: cast_nullable_to_non_nullable
as Planet,second: null == second ? _self.second : second // ignore: cast_nullable_to_non_nullable
as Planet,type: null == type ? _self.type : type // ignore: cast_nullable_to_non_nullable
as AspectType,orb: null == orb ? _self.orb : orb // ignore: cast_nullable_to_non_nullable
as double,applying: null == applying ? _self.applying : applying // ignore: cast_nullable_to_non_nullable
as bool,rawNature: freezed == rawNature ? _self.rawNature : rawNature // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}


}


/// @nodoc
mixin _$NatalChart {

 BirthData get birthData; List<PlanetPosition> get planets; List<HousePosition> get houses; List<NatalAspect> get aspects; ZodiacSign? get ascendant; ZodiacSign? get midheaven;/// Ecliptic longitude of the ascendant; drives the wheel rotation.
 double? get ascendantLongitude; double? get midheavenLongitude; HouseSystem get houseSystem; HouseSystem? get requestedHouseSystem; List<String> get warnings; Map<int, Planet> get houseRulers; String? get engine; String? get engineVersion; DateTime? get computedAt; String? get chartKind; ChartSubject? get subject; Map<String, dynamic> get sourceMetadata;/// True while the chart comes from [MockAstrologyService] instead of a real
/// ephemeris. Surfaced in the UI so mock output is never mistaken for a
/// real reading.
 bool get isMock;
/// Create a copy of NatalChart
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$NatalChartCopyWith<NatalChart> get copyWith => _$NatalChartCopyWithImpl<NatalChart>(this as NatalChart, _$identity);

  /// Serializes this NatalChart to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is NatalChart&&(identical(other.birthData, birthData) || other.birthData == birthData)&&const DeepCollectionEquality().equals(other.planets, planets)&&const DeepCollectionEquality().equals(other.houses, houses)&&const DeepCollectionEquality().equals(other.aspects, aspects)&&(identical(other.ascendant, ascendant) || other.ascendant == ascendant)&&(identical(other.midheaven, midheaven) || other.midheaven == midheaven)&&(identical(other.ascendantLongitude, ascendantLongitude) || other.ascendantLongitude == ascendantLongitude)&&(identical(other.midheavenLongitude, midheavenLongitude) || other.midheavenLongitude == midheavenLongitude)&&(identical(other.houseSystem, houseSystem) || other.houseSystem == houseSystem)&&(identical(other.requestedHouseSystem, requestedHouseSystem) || other.requestedHouseSystem == requestedHouseSystem)&&const DeepCollectionEquality().equals(other.warnings, warnings)&&const DeepCollectionEquality().equals(other.houseRulers, houseRulers)&&(identical(other.engine, engine) || other.engine == engine)&&(identical(other.engineVersion, engineVersion) || other.engineVersion == engineVersion)&&(identical(other.computedAt, computedAt) || other.computedAt == computedAt)&&(identical(other.chartKind, chartKind) || other.chartKind == chartKind)&&(identical(other.subject, subject) || other.subject == subject)&&const DeepCollectionEquality().equals(other.sourceMetadata, sourceMetadata)&&(identical(other.isMock, isMock) || other.isMock == isMock));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hashAll([runtimeType,birthData,const DeepCollectionEquality().hash(planets),const DeepCollectionEquality().hash(houses),const DeepCollectionEquality().hash(aspects),ascendant,midheaven,ascendantLongitude,midheavenLongitude,houseSystem,requestedHouseSystem,const DeepCollectionEquality().hash(warnings),const DeepCollectionEquality().hash(houseRulers),engine,engineVersion,computedAt,chartKind,subject,const DeepCollectionEquality().hash(sourceMetadata),isMock]);

@override
String toString() {
  return 'NatalChart(birthData: $birthData, planets: $planets, houses: $houses, aspects: $aspects, ascendant: $ascendant, midheaven: $midheaven, ascendantLongitude: $ascendantLongitude, midheavenLongitude: $midheavenLongitude, houseSystem: $houseSystem, requestedHouseSystem: $requestedHouseSystem, warnings: $warnings, houseRulers: $houseRulers, engine: $engine, engineVersion: $engineVersion, computedAt: $computedAt, chartKind: $chartKind, subject: $subject, sourceMetadata: $sourceMetadata, isMock: $isMock)';
}


}

/// @nodoc
abstract mixin class $NatalChartCopyWith<$Res>  {
  factory $NatalChartCopyWith(NatalChart value, $Res Function(NatalChart) _then) = _$NatalChartCopyWithImpl;
@useResult
$Res call({
 BirthData birthData, List<PlanetPosition> planets, List<HousePosition> houses, List<NatalAspect> aspects, ZodiacSign? ascendant, ZodiacSign? midheaven, double? ascendantLongitude, double? midheavenLongitude, HouseSystem houseSystem, HouseSystem? requestedHouseSystem, List<String> warnings, Map<int, Planet> houseRulers, String? engine, String? engineVersion, DateTime? computedAt, String? chartKind, ChartSubject? subject, Map<String, dynamic> sourceMetadata, bool isMock
});


$BirthDataCopyWith<$Res> get birthData;$ChartSubjectCopyWith<$Res>? get subject;

}
/// @nodoc
class _$NatalChartCopyWithImpl<$Res>
    implements $NatalChartCopyWith<$Res> {
  _$NatalChartCopyWithImpl(this._self, this._then);

  final NatalChart _self;
  final $Res Function(NatalChart) _then;

/// Create a copy of NatalChart
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? birthData = null,Object? planets = null,Object? houses = null,Object? aspects = null,Object? ascendant = freezed,Object? midheaven = freezed,Object? ascendantLongitude = freezed,Object? midheavenLongitude = freezed,Object? houseSystem = null,Object? requestedHouseSystem = freezed,Object? warnings = null,Object? houseRulers = null,Object? engine = freezed,Object? engineVersion = freezed,Object? computedAt = freezed,Object? chartKind = freezed,Object? subject = freezed,Object? sourceMetadata = null,Object? isMock = null,}) {
  return _then(_self.copyWith(
birthData: null == birthData ? _self.birthData : birthData // ignore: cast_nullable_to_non_nullable
as BirthData,planets: null == planets ? _self.planets : planets // ignore: cast_nullable_to_non_nullable
as List<PlanetPosition>,houses: null == houses ? _self.houses : houses // ignore: cast_nullable_to_non_nullable
as List<HousePosition>,aspects: null == aspects ? _self.aspects : aspects // ignore: cast_nullable_to_non_nullable
as List<NatalAspect>,ascendant: freezed == ascendant ? _self.ascendant : ascendant // ignore: cast_nullable_to_non_nullable
as ZodiacSign?,midheaven: freezed == midheaven ? _self.midheaven : midheaven // ignore: cast_nullable_to_non_nullable
as ZodiacSign?,ascendantLongitude: freezed == ascendantLongitude ? _self.ascendantLongitude : ascendantLongitude // ignore: cast_nullable_to_non_nullable
as double?,midheavenLongitude: freezed == midheavenLongitude ? _self.midheavenLongitude : midheavenLongitude // ignore: cast_nullable_to_non_nullable
as double?,houseSystem: null == houseSystem ? _self.houseSystem : houseSystem // ignore: cast_nullable_to_non_nullable
as HouseSystem,requestedHouseSystem: freezed == requestedHouseSystem ? _self.requestedHouseSystem : requestedHouseSystem // ignore: cast_nullable_to_non_nullable
as HouseSystem?,warnings: null == warnings ? _self.warnings : warnings // ignore: cast_nullable_to_non_nullable
as List<String>,houseRulers: null == houseRulers ? _self.houseRulers : houseRulers // ignore: cast_nullable_to_non_nullable
as Map<int, Planet>,engine: freezed == engine ? _self.engine : engine // ignore: cast_nullable_to_non_nullable
as String?,engineVersion: freezed == engineVersion ? _self.engineVersion : engineVersion // ignore: cast_nullable_to_non_nullable
as String?,computedAt: freezed == computedAt ? _self.computedAt : computedAt // ignore: cast_nullable_to_non_nullable
as DateTime?,chartKind: freezed == chartKind ? _self.chartKind : chartKind // ignore: cast_nullable_to_non_nullable
as String?,subject: freezed == subject ? _self.subject : subject // ignore: cast_nullable_to_non_nullable
as ChartSubject?,sourceMetadata: null == sourceMetadata ? _self.sourceMetadata : sourceMetadata // ignore: cast_nullable_to_non_nullable
as Map<String, dynamic>,isMock: null == isMock ? _self.isMock : isMock // ignore: cast_nullable_to_non_nullable
as bool,
  ));
}
/// Create a copy of NatalChart
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$BirthDataCopyWith<$Res> get birthData {
  
  return $BirthDataCopyWith<$Res>(_self.birthData, (value) {
    return _then(_self.copyWith(birthData: value));
  });
}/// Create a copy of NatalChart
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$ChartSubjectCopyWith<$Res>? get subject {
    if (_self.subject == null) {
    return null;
  }

  return $ChartSubjectCopyWith<$Res>(_self.subject!, (value) {
    return _then(_self.copyWith(subject: value));
  });
}
}


/// Adds pattern-matching-related methods to [NatalChart].
extension NatalChartPatterns on NatalChart {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _NatalChart value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _NatalChart() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _NatalChart value)  $default,){
final _that = this;
switch (_that) {
case _NatalChart():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _NatalChart value)?  $default,){
final _that = this;
switch (_that) {
case _NatalChart() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( BirthData birthData,  List<PlanetPosition> planets,  List<HousePosition> houses,  List<NatalAspect> aspects,  ZodiacSign? ascendant,  ZodiacSign? midheaven,  double? ascendantLongitude,  double? midheavenLongitude,  HouseSystem houseSystem,  HouseSystem? requestedHouseSystem,  List<String> warnings,  Map<int, Planet> houseRulers,  String? engine,  String? engineVersion,  DateTime? computedAt,  String? chartKind,  ChartSubject? subject,  Map<String, dynamic> sourceMetadata,  bool isMock)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _NatalChart() when $default != null:
return $default(_that.birthData,_that.planets,_that.houses,_that.aspects,_that.ascendant,_that.midheaven,_that.ascendantLongitude,_that.midheavenLongitude,_that.houseSystem,_that.requestedHouseSystem,_that.warnings,_that.houseRulers,_that.engine,_that.engineVersion,_that.computedAt,_that.chartKind,_that.subject,_that.sourceMetadata,_that.isMock);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( BirthData birthData,  List<PlanetPosition> planets,  List<HousePosition> houses,  List<NatalAspect> aspects,  ZodiacSign? ascendant,  ZodiacSign? midheaven,  double? ascendantLongitude,  double? midheavenLongitude,  HouseSystem houseSystem,  HouseSystem? requestedHouseSystem,  List<String> warnings,  Map<int, Planet> houseRulers,  String? engine,  String? engineVersion,  DateTime? computedAt,  String? chartKind,  ChartSubject? subject,  Map<String, dynamic> sourceMetadata,  bool isMock)  $default,) {final _that = this;
switch (_that) {
case _NatalChart():
return $default(_that.birthData,_that.planets,_that.houses,_that.aspects,_that.ascendant,_that.midheaven,_that.ascendantLongitude,_that.midheavenLongitude,_that.houseSystem,_that.requestedHouseSystem,_that.warnings,_that.houseRulers,_that.engine,_that.engineVersion,_that.computedAt,_that.chartKind,_that.subject,_that.sourceMetadata,_that.isMock);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( BirthData birthData,  List<PlanetPosition> planets,  List<HousePosition> houses,  List<NatalAspect> aspects,  ZodiacSign? ascendant,  ZodiacSign? midheaven,  double? ascendantLongitude,  double? midheavenLongitude,  HouseSystem houseSystem,  HouseSystem? requestedHouseSystem,  List<String> warnings,  Map<int, Planet> houseRulers,  String? engine,  String? engineVersion,  DateTime? computedAt,  String? chartKind,  ChartSubject? subject,  Map<String, dynamic> sourceMetadata,  bool isMock)?  $default,) {final _that = this;
switch (_that) {
case _NatalChart() when $default != null:
return $default(_that.birthData,_that.planets,_that.houses,_that.aspects,_that.ascendant,_that.midheaven,_that.ascendantLongitude,_that.midheavenLongitude,_that.houseSystem,_that.requestedHouseSystem,_that.warnings,_that.houseRulers,_that.engine,_that.engineVersion,_that.computedAt,_that.chartKind,_that.subject,_that.sourceMetadata,_that.isMock);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _NatalChart extends NatalChart {
  const _NatalChart({required this.birthData, required final  List<PlanetPosition> planets, final  List<HousePosition> houses = const <HousePosition>[], final  List<NatalAspect> aspects = const <NatalAspect>[], this.ascendant, this.midheaven, this.ascendantLongitude, this.midheavenLongitude, this.houseSystem = HouseSystem.placidus, this.requestedHouseSystem, final  List<String> warnings = const <String>[], final  Map<int, Planet> houseRulers = const <int, Planet>{}, this.engine, this.engineVersion, this.computedAt, this.chartKind, this.subject, final  Map<String, dynamic> sourceMetadata = const <String, dynamic>{}, this.isMock = false}): _planets = planets,_houses = houses,_aspects = aspects,_warnings = warnings,_houseRulers = houseRulers,_sourceMetadata = sourceMetadata,super._();
  factory _NatalChart.fromJson(Map<String, dynamic> json) => _$NatalChartFromJson(json);

@override final  BirthData birthData;
 final  List<PlanetPosition> _planets;
@override List<PlanetPosition> get planets {
  if (_planets is EqualUnmodifiableListView) return _planets;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_planets);
}

 final  List<HousePosition> _houses;
@override@JsonKey() List<HousePosition> get houses {
  if (_houses is EqualUnmodifiableListView) return _houses;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_houses);
}

 final  List<NatalAspect> _aspects;
@override@JsonKey() List<NatalAspect> get aspects {
  if (_aspects is EqualUnmodifiableListView) return _aspects;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_aspects);
}

@override final  ZodiacSign? ascendant;
@override final  ZodiacSign? midheaven;
/// Ecliptic longitude of the ascendant; drives the wheel rotation.
@override final  double? ascendantLongitude;
@override final  double? midheavenLongitude;
@override@JsonKey() final  HouseSystem houseSystem;
@override final  HouseSystem? requestedHouseSystem;
 final  List<String> _warnings;
@override@JsonKey() List<String> get warnings {
  if (_warnings is EqualUnmodifiableListView) return _warnings;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_warnings);
}

 final  Map<int, Planet> _houseRulers;
@override@JsonKey() Map<int, Planet> get houseRulers {
  if (_houseRulers is EqualUnmodifiableMapView) return _houseRulers;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableMapView(_houseRulers);
}

@override final  String? engine;
@override final  String? engineVersion;
@override final  DateTime? computedAt;
@override final  String? chartKind;
@override final  ChartSubject? subject;
 final  Map<String, dynamic> _sourceMetadata;
@override@JsonKey() Map<String, dynamic> get sourceMetadata {
  if (_sourceMetadata is EqualUnmodifiableMapView) return _sourceMetadata;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableMapView(_sourceMetadata);
}

/// True while the chart comes from [MockAstrologyService] instead of a real
/// ephemeris. Surfaced in the UI so mock output is never mistaken for a
/// real reading.
@override@JsonKey() final  bool isMock;

/// Create a copy of NatalChart
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$NatalChartCopyWith<_NatalChart> get copyWith => __$NatalChartCopyWithImpl<_NatalChart>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$NatalChartToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _NatalChart&&(identical(other.birthData, birthData) || other.birthData == birthData)&&const DeepCollectionEquality().equals(other._planets, _planets)&&const DeepCollectionEquality().equals(other._houses, _houses)&&const DeepCollectionEquality().equals(other._aspects, _aspects)&&(identical(other.ascendant, ascendant) || other.ascendant == ascendant)&&(identical(other.midheaven, midheaven) || other.midheaven == midheaven)&&(identical(other.ascendantLongitude, ascendantLongitude) || other.ascendantLongitude == ascendantLongitude)&&(identical(other.midheavenLongitude, midheavenLongitude) || other.midheavenLongitude == midheavenLongitude)&&(identical(other.houseSystem, houseSystem) || other.houseSystem == houseSystem)&&(identical(other.requestedHouseSystem, requestedHouseSystem) || other.requestedHouseSystem == requestedHouseSystem)&&const DeepCollectionEquality().equals(other._warnings, _warnings)&&const DeepCollectionEquality().equals(other._houseRulers, _houseRulers)&&(identical(other.engine, engine) || other.engine == engine)&&(identical(other.engineVersion, engineVersion) || other.engineVersion == engineVersion)&&(identical(other.computedAt, computedAt) || other.computedAt == computedAt)&&(identical(other.chartKind, chartKind) || other.chartKind == chartKind)&&(identical(other.subject, subject) || other.subject == subject)&&const DeepCollectionEquality().equals(other._sourceMetadata, _sourceMetadata)&&(identical(other.isMock, isMock) || other.isMock == isMock));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hashAll([runtimeType,birthData,const DeepCollectionEquality().hash(_planets),const DeepCollectionEquality().hash(_houses),const DeepCollectionEquality().hash(_aspects),ascendant,midheaven,ascendantLongitude,midheavenLongitude,houseSystem,requestedHouseSystem,const DeepCollectionEquality().hash(_warnings),const DeepCollectionEquality().hash(_houseRulers),engine,engineVersion,computedAt,chartKind,subject,const DeepCollectionEquality().hash(_sourceMetadata),isMock]);

@override
String toString() {
  return 'NatalChart(birthData: $birthData, planets: $planets, houses: $houses, aspects: $aspects, ascendant: $ascendant, midheaven: $midheaven, ascendantLongitude: $ascendantLongitude, midheavenLongitude: $midheavenLongitude, houseSystem: $houseSystem, requestedHouseSystem: $requestedHouseSystem, warnings: $warnings, houseRulers: $houseRulers, engine: $engine, engineVersion: $engineVersion, computedAt: $computedAt, chartKind: $chartKind, subject: $subject, sourceMetadata: $sourceMetadata, isMock: $isMock)';
}


}

/// @nodoc
abstract mixin class _$NatalChartCopyWith<$Res> implements $NatalChartCopyWith<$Res> {
  factory _$NatalChartCopyWith(_NatalChart value, $Res Function(_NatalChart) _then) = __$NatalChartCopyWithImpl;
@override @useResult
$Res call({
 BirthData birthData, List<PlanetPosition> planets, List<HousePosition> houses, List<NatalAspect> aspects, ZodiacSign? ascendant, ZodiacSign? midheaven, double? ascendantLongitude, double? midheavenLongitude, HouseSystem houseSystem, HouseSystem? requestedHouseSystem, List<String> warnings, Map<int, Planet> houseRulers, String? engine, String? engineVersion, DateTime? computedAt, String? chartKind, ChartSubject? subject, Map<String, dynamic> sourceMetadata, bool isMock
});


@override $BirthDataCopyWith<$Res> get birthData;@override $ChartSubjectCopyWith<$Res>? get subject;

}
/// @nodoc
class __$NatalChartCopyWithImpl<$Res>
    implements _$NatalChartCopyWith<$Res> {
  __$NatalChartCopyWithImpl(this._self, this._then);

  final _NatalChart _self;
  final $Res Function(_NatalChart) _then;

/// Create a copy of NatalChart
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? birthData = null,Object? planets = null,Object? houses = null,Object? aspects = null,Object? ascendant = freezed,Object? midheaven = freezed,Object? ascendantLongitude = freezed,Object? midheavenLongitude = freezed,Object? houseSystem = null,Object? requestedHouseSystem = freezed,Object? warnings = null,Object? houseRulers = null,Object? engine = freezed,Object? engineVersion = freezed,Object? computedAt = freezed,Object? chartKind = freezed,Object? subject = freezed,Object? sourceMetadata = null,Object? isMock = null,}) {
  return _then(_NatalChart(
birthData: null == birthData ? _self.birthData : birthData // ignore: cast_nullable_to_non_nullable
as BirthData,planets: null == planets ? _self._planets : planets // ignore: cast_nullable_to_non_nullable
as List<PlanetPosition>,houses: null == houses ? _self._houses : houses // ignore: cast_nullable_to_non_nullable
as List<HousePosition>,aspects: null == aspects ? _self._aspects : aspects // ignore: cast_nullable_to_non_nullable
as List<NatalAspect>,ascendant: freezed == ascendant ? _self.ascendant : ascendant // ignore: cast_nullable_to_non_nullable
as ZodiacSign?,midheaven: freezed == midheaven ? _self.midheaven : midheaven // ignore: cast_nullable_to_non_nullable
as ZodiacSign?,ascendantLongitude: freezed == ascendantLongitude ? _self.ascendantLongitude : ascendantLongitude // ignore: cast_nullable_to_non_nullable
as double?,midheavenLongitude: freezed == midheavenLongitude ? _self.midheavenLongitude : midheavenLongitude // ignore: cast_nullable_to_non_nullable
as double?,houseSystem: null == houseSystem ? _self.houseSystem : houseSystem // ignore: cast_nullable_to_non_nullable
as HouseSystem,requestedHouseSystem: freezed == requestedHouseSystem ? _self.requestedHouseSystem : requestedHouseSystem // ignore: cast_nullable_to_non_nullable
as HouseSystem?,warnings: null == warnings ? _self._warnings : warnings // ignore: cast_nullable_to_non_nullable
as List<String>,houseRulers: null == houseRulers ? _self._houseRulers : houseRulers // ignore: cast_nullable_to_non_nullable
as Map<int, Planet>,engine: freezed == engine ? _self.engine : engine // ignore: cast_nullable_to_non_nullable
as String?,engineVersion: freezed == engineVersion ? _self.engineVersion : engineVersion // ignore: cast_nullable_to_non_nullable
as String?,computedAt: freezed == computedAt ? _self.computedAt : computedAt // ignore: cast_nullable_to_non_nullable
as DateTime?,chartKind: freezed == chartKind ? _self.chartKind : chartKind // ignore: cast_nullable_to_non_nullable
as String?,subject: freezed == subject ? _self.subject : subject // ignore: cast_nullable_to_non_nullable
as ChartSubject?,sourceMetadata: null == sourceMetadata ? _self._sourceMetadata : sourceMetadata // ignore: cast_nullable_to_non_nullable
as Map<String, dynamic>,isMock: null == isMock ? _self.isMock : isMock // ignore: cast_nullable_to_non_nullable
as bool,
  ));
}

/// Create a copy of NatalChart
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$BirthDataCopyWith<$Res> get birthData {
  
  return $BirthDataCopyWith<$Res>(_self.birthData, (value) {
    return _then(_self.copyWith(birthData: value));
  });
}/// Create a copy of NatalChart
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$ChartSubjectCopyWith<$Res>? get subject {
    if (_self.subject == null) {
    return null;
  }

  return $ChartSubjectCopyWith<$Res>(_self.subject!, (value) {
    return _then(_self.copyWith(subject: value));
  });
}
}

// dart format on
