// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'moon_phase.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$MoonPhase {

 DateTime get date; MoonPhaseType get type;/// 0..1 lit fraction of the disc.
 double get illumination;/// 0..1 position in the synodic cycle.
 double? get cycleProgress; double? get ageDays; double? get elongation; MoonPhaseType? get nextPhase; DateTime? get nextPhaseAt; ZodiacSign? get sign;/// Natal house the Moon is currently transiting, when the chart allows it.
 int? get house; String? get message;
/// Create a copy of MoonPhase
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$MoonPhaseCopyWith<MoonPhase> get copyWith => _$MoonPhaseCopyWithImpl<MoonPhase>(this as MoonPhase, _$identity);

  /// Serializes this MoonPhase to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is MoonPhase&&(identical(other.date, date) || other.date == date)&&(identical(other.type, type) || other.type == type)&&(identical(other.illumination, illumination) || other.illumination == illumination)&&(identical(other.cycleProgress, cycleProgress) || other.cycleProgress == cycleProgress)&&(identical(other.ageDays, ageDays) || other.ageDays == ageDays)&&(identical(other.elongation, elongation) || other.elongation == elongation)&&(identical(other.nextPhase, nextPhase) || other.nextPhase == nextPhase)&&(identical(other.nextPhaseAt, nextPhaseAt) || other.nextPhaseAt == nextPhaseAt)&&(identical(other.sign, sign) || other.sign == sign)&&(identical(other.house, house) || other.house == house)&&(identical(other.message, message) || other.message == message));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,date,type,illumination,cycleProgress,ageDays,elongation,nextPhase,nextPhaseAt,sign,house,message);

@override
String toString() {
  return 'MoonPhase(date: $date, type: $type, illumination: $illumination, cycleProgress: $cycleProgress, ageDays: $ageDays, elongation: $elongation, nextPhase: $nextPhase, nextPhaseAt: $nextPhaseAt, sign: $sign, house: $house, message: $message)';
}


}

/// @nodoc
abstract mixin class $MoonPhaseCopyWith<$Res>  {
  factory $MoonPhaseCopyWith(MoonPhase value, $Res Function(MoonPhase) _then) = _$MoonPhaseCopyWithImpl;
@useResult
$Res call({
 DateTime date, MoonPhaseType type, double illumination, double? cycleProgress, double? ageDays, double? elongation, MoonPhaseType? nextPhase, DateTime? nextPhaseAt, ZodiacSign? sign, int? house, String? message
});




}
/// @nodoc
class _$MoonPhaseCopyWithImpl<$Res>
    implements $MoonPhaseCopyWith<$Res> {
  _$MoonPhaseCopyWithImpl(this._self, this._then);

  final MoonPhase _self;
  final $Res Function(MoonPhase) _then;

/// Create a copy of MoonPhase
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? date = null,Object? type = null,Object? illumination = null,Object? cycleProgress = freezed,Object? ageDays = freezed,Object? elongation = freezed,Object? nextPhase = freezed,Object? nextPhaseAt = freezed,Object? sign = freezed,Object? house = freezed,Object? message = freezed,}) {
  return _then(_self.copyWith(
date: null == date ? _self.date : date // ignore: cast_nullable_to_non_nullable
as DateTime,type: null == type ? _self.type : type // ignore: cast_nullable_to_non_nullable
as MoonPhaseType,illumination: null == illumination ? _self.illumination : illumination // ignore: cast_nullable_to_non_nullable
as double,cycleProgress: freezed == cycleProgress ? _self.cycleProgress : cycleProgress // ignore: cast_nullable_to_non_nullable
as double?,ageDays: freezed == ageDays ? _self.ageDays : ageDays // ignore: cast_nullable_to_non_nullable
as double?,elongation: freezed == elongation ? _self.elongation : elongation // ignore: cast_nullable_to_non_nullable
as double?,nextPhase: freezed == nextPhase ? _self.nextPhase : nextPhase // ignore: cast_nullable_to_non_nullable
as MoonPhaseType?,nextPhaseAt: freezed == nextPhaseAt ? _self.nextPhaseAt : nextPhaseAt // ignore: cast_nullable_to_non_nullable
as DateTime?,sign: freezed == sign ? _self.sign : sign // ignore: cast_nullable_to_non_nullable
as ZodiacSign?,house: freezed == house ? _self.house : house // ignore: cast_nullable_to_non_nullable
as int?,message: freezed == message ? _self.message : message // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

}


/// Adds pattern-matching-related methods to [MoonPhase].
extension MoonPhasePatterns on MoonPhase {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _MoonPhase value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _MoonPhase() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _MoonPhase value)  $default,){
final _that = this;
switch (_that) {
case _MoonPhase():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _MoonPhase value)?  $default,){
final _that = this;
switch (_that) {
case _MoonPhase() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( DateTime date,  MoonPhaseType type,  double illumination,  double? cycleProgress,  double? ageDays,  double? elongation,  MoonPhaseType? nextPhase,  DateTime? nextPhaseAt,  ZodiacSign? sign,  int? house,  String? message)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _MoonPhase() when $default != null:
return $default(_that.date,_that.type,_that.illumination,_that.cycleProgress,_that.ageDays,_that.elongation,_that.nextPhase,_that.nextPhaseAt,_that.sign,_that.house,_that.message);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( DateTime date,  MoonPhaseType type,  double illumination,  double? cycleProgress,  double? ageDays,  double? elongation,  MoonPhaseType? nextPhase,  DateTime? nextPhaseAt,  ZodiacSign? sign,  int? house,  String? message)  $default,) {final _that = this;
switch (_that) {
case _MoonPhase():
return $default(_that.date,_that.type,_that.illumination,_that.cycleProgress,_that.ageDays,_that.elongation,_that.nextPhase,_that.nextPhaseAt,_that.sign,_that.house,_that.message);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( DateTime date,  MoonPhaseType type,  double illumination,  double? cycleProgress,  double? ageDays,  double? elongation,  MoonPhaseType? nextPhase,  DateTime? nextPhaseAt,  ZodiacSign? sign,  int? house,  String? message)?  $default,) {final _that = this;
switch (_that) {
case _MoonPhase() when $default != null:
return $default(_that.date,_that.type,_that.illumination,_that.cycleProgress,_that.ageDays,_that.elongation,_that.nextPhase,_that.nextPhaseAt,_that.sign,_that.house,_that.message);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _MoonPhase implements MoonPhase {
  const _MoonPhase({required this.date, required this.type, required this.illumination, this.cycleProgress, this.ageDays, this.elongation, this.nextPhase, this.nextPhaseAt, this.sign, this.house, this.message});
  factory _MoonPhase.fromJson(Map<String, dynamic> json) => _$MoonPhaseFromJson(json);

@override final  DateTime date;
@override final  MoonPhaseType type;
/// 0..1 lit fraction of the disc.
@override final  double illumination;
/// 0..1 position in the synodic cycle.
@override final  double? cycleProgress;
@override final  double? ageDays;
@override final  double? elongation;
@override final  MoonPhaseType? nextPhase;
@override final  DateTime? nextPhaseAt;
@override final  ZodiacSign? sign;
/// Natal house the Moon is currently transiting, when the chart allows it.
@override final  int? house;
@override final  String? message;

/// Create a copy of MoonPhase
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$MoonPhaseCopyWith<_MoonPhase> get copyWith => __$MoonPhaseCopyWithImpl<_MoonPhase>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$MoonPhaseToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _MoonPhase&&(identical(other.date, date) || other.date == date)&&(identical(other.type, type) || other.type == type)&&(identical(other.illumination, illumination) || other.illumination == illumination)&&(identical(other.cycleProgress, cycleProgress) || other.cycleProgress == cycleProgress)&&(identical(other.ageDays, ageDays) || other.ageDays == ageDays)&&(identical(other.elongation, elongation) || other.elongation == elongation)&&(identical(other.nextPhase, nextPhase) || other.nextPhase == nextPhase)&&(identical(other.nextPhaseAt, nextPhaseAt) || other.nextPhaseAt == nextPhaseAt)&&(identical(other.sign, sign) || other.sign == sign)&&(identical(other.house, house) || other.house == house)&&(identical(other.message, message) || other.message == message));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,date,type,illumination,cycleProgress,ageDays,elongation,nextPhase,nextPhaseAt,sign,house,message);

@override
String toString() {
  return 'MoonPhase(date: $date, type: $type, illumination: $illumination, cycleProgress: $cycleProgress, ageDays: $ageDays, elongation: $elongation, nextPhase: $nextPhase, nextPhaseAt: $nextPhaseAt, sign: $sign, house: $house, message: $message)';
}


}

/// @nodoc
abstract mixin class _$MoonPhaseCopyWith<$Res> implements $MoonPhaseCopyWith<$Res> {
  factory _$MoonPhaseCopyWith(_MoonPhase value, $Res Function(_MoonPhase) _then) = __$MoonPhaseCopyWithImpl;
@override @useResult
$Res call({
 DateTime date, MoonPhaseType type, double illumination, double? cycleProgress, double? ageDays, double? elongation, MoonPhaseType? nextPhase, DateTime? nextPhaseAt, ZodiacSign? sign, int? house, String? message
});




}
/// @nodoc
class __$MoonPhaseCopyWithImpl<$Res>
    implements _$MoonPhaseCopyWith<$Res> {
  __$MoonPhaseCopyWithImpl(this._self, this._then);

  final _MoonPhase _self;
  final $Res Function(_MoonPhase) _then;

/// Create a copy of MoonPhase
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? date = null,Object? type = null,Object? illumination = null,Object? cycleProgress = freezed,Object? ageDays = freezed,Object? elongation = freezed,Object? nextPhase = freezed,Object? nextPhaseAt = freezed,Object? sign = freezed,Object? house = freezed,Object? message = freezed,}) {
  return _then(_MoonPhase(
date: null == date ? _self.date : date // ignore: cast_nullable_to_non_nullable
as DateTime,type: null == type ? _self.type : type // ignore: cast_nullable_to_non_nullable
as MoonPhaseType,illumination: null == illumination ? _self.illumination : illumination // ignore: cast_nullable_to_non_nullable
as double,cycleProgress: freezed == cycleProgress ? _self.cycleProgress : cycleProgress // ignore: cast_nullable_to_non_nullable
as double?,ageDays: freezed == ageDays ? _self.ageDays : ageDays // ignore: cast_nullable_to_non_nullable
as double?,elongation: freezed == elongation ? _self.elongation : elongation // ignore: cast_nullable_to_non_nullable
as double?,nextPhase: freezed == nextPhase ? _self.nextPhase : nextPhase // ignore: cast_nullable_to_non_nullable
as MoonPhaseType?,nextPhaseAt: freezed == nextPhaseAt ? _self.nextPhaseAt : nextPhaseAt // ignore: cast_nullable_to_non_nullable
as DateTime?,sign: freezed == sign ? _self.sign : sign // ignore: cast_nullable_to_non_nullable
as ZodiacSign?,house: freezed == house ? _self.house : house // ignore: cast_nullable_to_non_nullable
as int?,message: freezed == message ? _self.message : message // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}


}


/// @nodoc
mixin _$MoonPhaseSummary {

 MoonPhaseType get type; ZodiacSign? get sign; String? get message;
/// Create a copy of MoonPhaseSummary
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$MoonPhaseSummaryCopyWith<MoonPhaseSummary> get copyWith => _$MoonPhaseSummaryCopyWithImpl<MoonPhaseSummary>(this as MoonPhaseSummary, _$identity);

  /// Serializes this MoonPhaseSummary to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is MoonPhaseSummary&&(identical(other.type, type) || other.type == type)&&(identical(other.sign, sign) || other.sign == sign)&&(identical(other.message, message) || other.message == message));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,type,sign,message);

@override
String toString() {
  return 'MoonPhaseSummary(type: $type, sign: $sign, message: $message)';
}


}

/// @nodoc
abstract mixin class $MoonPhaseSummaryCopyWith<$Res>  {
  factory $MoonPhaseSummaryCopyWith(MoonPhaseSummary value, $Res Function(MoonPhaseSummary) _then) = _$MoonPhaseSummaryCopyWithImpl;
@useResult
$Res call({
 MoonPhaseType type, ZodiacSign? sign, String? message
});




}
/// @nodoc
class _$MoonPhaseSummaryCopyWithImpl<$Res>
    implements $MoonPhaseSummaryCopyWith<$Res> {
  _$MoonPhaseSummaryCopyWithImpl(this._self, this._then);

  final MoonPhaseSummary _self;
  final $Res Function(MoonPhaseSummary) _then;

/// Create a copy of MoonPhaseSummary
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? type = null,Object? sign = freezed,Object? message = freezed,}) {
  return _then(_self.copyWith(
type: null == type ? _self.type : type // ignore: cast_nullable_to_non_nullable
as MoonPhaseType,sign: freezed == sign ? _self.sign : sign // ignore: cast_nullable_to_non_nullable
as ZodiacSign?,message: freezed == message ? _self.message : message // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

}


/// Adds pattern-matching-related methods to [MoonPhaseSummary].
extension MoonPhaseSummaryPatterns on MoonPhaseSummary {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _MoonPhaseSummary value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _MoonPhaseSummary() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _MoonPhaseSummary value)  $default,){
final _that = this;
switch (_that) {
case _MoonPhaseSummary():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _MoonPhaseSummary value)?  $default,){
final _that = this;
switch (_that) {
case _MoonPhaseSummary() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( MoonPhaseType type,  ZodiacSign? sign,  String? message)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _MoonPhaseSummary() when $default != null:
return $default(_that.type,_that.sign,_that.message);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( MoonPhaseType type,  ZodiacSign? sign,  String? message)  $default,) {final _that = this;
switch (_that) {
case _MoonPhaseSummary():
return $default(_that.type,_that.sign,_that.message);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( MoonPhaseType type,  ZodiacSign? sign,  String? message)?  $default,) {final _that = this;
switch (_that) {
case _MoonPhaseSummary() when $default != null:
return $default(_that.type,_that.sign,_that.message);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _MoonPhaseSummary implements MoonPhaseSummary {
  const _MoonPhaseSummary({required this.type, this.sign, this.message});
  factory _MoonPhaseSummary.fromJson(Map<String, dynamic> json) => _$MoonPhaseSummaryFromJson(json);

@override final  MoonPhaseType type;
@override final  ZodiacSign? sign;
@override final  String? message;

/// Create a copy of MoonPhaseSummary
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$MoonPhaseSummaryCopyWith<_MoonPhaseSummary> get copyWith => __$MoonPhaseSummaryCopyWithImpl<_MoonPhaseSummary>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$MoonPhaseSummaryToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _MoonPhaseSummary&&(identical(other.type, type) || other.type == type)&&(identical(other.sign, sign) || other.sign == sign)&&(identical(other.message, message) || other.message == message));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,type,sign,message);

@override
String toString() {
  return 'MoonPhaseSummary(type: $type, sign: $sign, message: $message)';
}


}

/// @nodoc
abstract mixin class _$MoonPhaseSummaryCopyWith<$Res> implements $MoonPhaseSummaryCopyWith<$Res> {
  factory _$MoonPhaseSummaryCopyWith(_MoonPhaseSummary value, $Res Function(_MoonPhaseSummary) _then) = __$MoonPhaseSummaryCopyWithImpl;
@override @useResult
$Res call({
 MoonPhaseType type, ZodiacSign? sign, String? message
});




}
/// @nodoc
class __$MoonPhaseSummaryCopyWithImpl<$Res>
    implements _$MoonPhaseSummaryCopyWith<$Res> {
  __$MoonPhaseSummaryCopyWithImpl(this._self, this._then);

  final _MoonPhaseSummary _self;
  final $Res Function(_MoonPhaseSummary) _then;

/// Create a copy of MoonPhaseSummary
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? type = null,Object? sign = freezed,Object? message = freezed,}) {
  return _then(_MoonPhaseSummary(
type: null == type ? _self.type : type // ignore: cast_nullable_to_non_nullable
as MoonPhaseType,sign: freezed == sign ? _self.sign : sign // ignore: cast_nullable_to_non_nullable
as ZodiacSign?,message: freezed == message ? _self.message : message // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}


}

// dart format on
