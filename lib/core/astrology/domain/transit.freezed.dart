// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'transit.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$TransitSummary {

 String get id; Planet get transitingPlanet;/// Set when the influence is an aspect to a natal body.
 AspectType? get aspect; Planet? get natalPlanet; ChartAngle? get natalAngle; String? get rawTargetAngle; String? get rawTargetType; TransitTargetType? get backendTargetType;/// Set when the influence is an ingress into a natal house (1-12).
 int? get house; bool get isRetrograde; InfluenceNature get nature; String? get rawNature;/// Short, already-localized interpretation coming from the content layer.
 String? get headline;
/// Create a copy of TransitSummary
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$TransitSummaryCopyWith<TransitSummary> get copyWith => _$TransitSummaryCopyWithImpl<TransitSummary>(this as TransitSummary, _$identity);

  /// Serializes this TransitSummary to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is TransitSummary&&(identical(other.id, id) || other.id == id)&&(identical(other.transitingPlanet, transitingPlanet) || other.transitingPlanet == transitingPlanet)&&(identical(other.aspect, aspect) || other.aspect == aspect)&&(identical(other.natalPlanet, natalPlanet) || other.natalPlanet == natalPlanet)&&(identical(other.natalAngle, natalAngle) || other.natalAngle == natalAngle)&&(identical(other.rawTargetAngle, rawTargetAngle) || other.rawTargetAngle == rawTargetAngle)&&(identical(other.rawTargetType, rawTargetType) || other.rawTargetType == rawTargetType)&&(identical(other.backendTargetType, backendTargetType) || other.backendTargetType == backendTargetType)&&(identical(other.house, house) || other.house == house)&&(identical(other.isRetrograde, isRetrograde) || other.isRetrograde == isRetrograde)&&(identical(other.nature, nature) || other.nature == nature)&&(identical(other.rawNature, rawNature) || other.rawNature == rawNature)&&(identical(other.headline, headline) || other.headline == headline));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,transitingPlanet,aspect,natalPlanet,natalAngle,rawTargetAngle,rawTargetType,backendTargetType,house,isRetrograde,nature,rawNature,headline);

@override
String toString() {
  return 'TransitSummary(id: $id, transitingPlanet: $transitingPlanet, aspect: $aspect, natalPlanet: $natalPlanet, natalAngle: $natalAngle, rawTargetAngle: $rawTargetAngle, rawTargetType: $rawTargetType, backendTargetType: $backendTargetType, house: $house, isRetrograde: $isRetrograde, nature: $nature, rawNature: $rawNature, headline: $headline)';
}


}

/// @nodoc
abstract mixin class $TransitSummaryCopyWith<$Res>  {
  factory $TransitSummaryCopyWith(TransitSummary value, $Res Function(TransitSummary) _then) = _$TransitSummaryCopyWithImpl;
@useResult
$Res call({
 String id, Planet transitingPlanet, AspectType? aspect, Planet? natalPlanet, ChartAngle? natalAngle, String? rawTargetAngle, String? rawTargetType, TransitTargetType? backendTargetType, int? house, bool isRetrograde, InfluenceNature nature, String? rawNature, String? headline
});




}
/// @nodoc
class _$TransitSummaryCopyWithImpl<$Res>
    implements $TransitSummaryCopyWith<$Res> {
  _$TransitSummaryCopyWithImpl(this._self, this._then);

  final TransitSummary _self;
  final $Res Function(TransitSummary) _then;

/// Create a copy of TransitSummary
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? id = null,Object? transitingPlanet = null,Object? aspect = freezed,Object? natalPlanet = freezed,Object? natalAngle = freezed,Object? rawTargetAngle = freezed,Object? rawTargetType = freezed,Object? backendTargetType = freezed,Object? house = freezed,Object? isRetrograde = null,Object? nature = null,Object? rawNature = freezed,Object? headline = freezed,}) {
  return _then(_self.copyWith(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,transitingPlanet: null == transitingPlanet ? _self.transitingPlanet : transitingPlanet // ignore: cast_nullable_to_non_nullable
as Planet,aspect: freezed == aspect ? _self.aspect : aspect // ignore: cast_nullable_to_non_nullable
as AspectType?,natalPlanet: freezed == natalPlanet ? _self.natalPlanet : natalPlanet // ignore: cast_nullable_to_non_nullable
as Planet?,natalAngle: freezed == natalAngle ? _self.natalAngle : natalAngle // ignore: cast_nullable_to_non_nullable
as ChartAngle?,rawTargetAngle: freezed == rawTargetAngle ? _self.rawTargetAngle : rawTargetAngle // ignore: cast_nullable_to_non_nullable
as String?,rawTargetType: freezed == rawTargetType ? _self.rawTargetType : rawTargetType // ignore: cast_nullable_to_non_nullable
as String?,backendTargetType: freezed == backendTargetType ? _self.backendTargetType : backendTargetType // ignore: cast_nullable_to_non_nullable
as TransitTargetType?,house: freezed == house ? _self.house : house // ignore: cast_nullable_to_non_nullable
as int?,isRetrograde: null == isRetrograde ? _self.isRetrograde : isRetrograde // ignore: cast_nullable_to_non_nullable
as bool,nature: null == nature ? _self.nature : nature // ignore: cast_nullable_to_non_nullable
as InfluenceNature,rawNature: freezed == rawNature ? _self.rawNature : rawNature // ignore: cast_nullable_to_non_nullable
as String?,headline: freezed == headline ? _self.headline : headline // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

}


/// Adds pattern-matching-related methods to [TransitSummary].
extension TransitSummaryPatterns on TransitSummary {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _TransitSummary value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _TransitSummary() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _TransitSummary value)  $default,){
final _that = this;
switch (_that) {
case _TransitSummary():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _TransitSummary value)?  $default,){
final _that = this;
switch (_that) {
case _TransitSummary() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String id,  Planet transitingPlanet,  AspectType? aspect,  Planet? natalPlanet,  ChartAngle? natalAngle,  String? rawTargetAngle,  String? rawTargetType,  TransitTargetType? backendTargetType,  int? house,  bool isRetrograde,  InfluenceNature nature,  String? rawNature,  String? headline)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _TransitSummary() when $default != null:
return $default(_that.id,_that.transitingPlanet,_that.aspect,_that.natalPlanet,_that.natalAngle,_that.rawTargetAngle,_that.rawTargetType,_that.backendTargetType,_that.house,_that.isRetrograde,_that.nature,_that.rawNature,_that.headline);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String id,  Planet transitingPlanet,  AspectType? aspect,  Planet? natalPlanet,  ChartAngle? natalAngle,  String? rawTargetAngle,  String? rawTargetType,  TransitTargetType? backendTargetType,  int? house,  bool isRetrograde,  InfluenceNature nature,  String? rawNature,  String? headline)  $default,) {final _that = this;
switch (_that) {
case _TransitSummary():
return $default(_that.id,_that.transitingPlanet,_that.aspect,_that.natalPlanet,_that.natalAngle,_that.rawTargetAngle,_that.rawTargetType,_that.backendTargetType,_that.house,_that.isRetrograde,_that.nature,_that.rawNature,_that.headline);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String id,  Planet transitingPlanet,  AspectType? aspect,  Planet? natalPlanet,  ChartAngle? natalAngle,  String? rawTargetAngle,  String? rawTargetType,  TransitTargetType? backendTargetType,  int? house,  bool isRetrograde,  InfluenceNature nature,  String? rawNature,  String? headline)?  $default,) {final _that = this;
switch (_that) {
case _TransitSummary() when $default != null:
return $default(_that.id,_that.transitingPlanet,_that.aspect,_that.natalPlanet,_that.natalAngle,_that.rawTargetAngle,_that.rawTargetType,_that.backendTargetType,_that.house,_that.isRetrograde,_that.nature,_that.rawNature,_that.headline);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _TransitSummary extends TransitSummary {
  const _TransitSummary({required this.id, required this.transitingPlanet, this.aspect, this.natalPlanet, this.natalAngle, this.rawTargetAngle, this.rawTargetType, this.backendTargetType, this.house, this.isRetrograde = false, this.nature = InfluenceNature.neutral, this.rawNature, this.headline}): super._();
  factory _TransitSummary.fromJson(Map<String, dynamic> json) => _$TransitSummaryFromJson(json);

@override final  String id;
@override final  Planet transitingPlanet;
/// Set when the influence is an aspect to a natal body.
@override final  AspectType? aspect;
@override final  Planet? natalPlanet;
@override final  ChartAngle? natalAngle;
@override final  String? rawTargetAngle;
@override final  String? rawTargetType;
@override final  TransitTargetType? backendTargetType;
/// Set when the influence is an ingress into a natal house (1-12).
@override final  int? house;
@override@JsonKey() final  bool isRetrograde;
@override@JsonKey() final  InfluenceNature nature;
@override final  String? rawNature;
/// Short, already-localized interpretation coming from the content layer.
@override final  String? headline;

/// Create a copy of TransitSummary
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$TransitSummaryCopyWith<_TransitSummary> get copyWith => __$TransitSummaryCopyWithImpl<_TransitSummary>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$TransitSummaryToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _TransitSummary&&(identical(other.id, id) || other.id == id)&&(identical(other.transitingPlanet, transitingPlanet) || other.transitingPlanet == transitingPlanet)&&(identical(other.aspect, aspect) || other.aspect == aspect)&&(identical(other.natalPlanet, natalPlanet) || other.natalPlanet == natalPlanet)&&(identical(other.natalAngle, natalAngle) || other.natalAngle == natalAngle)&&(identical(other.rawTargetAngle, rawTargetAngle) || other.rawTargetAngle == rawTargetAngle)&&(identical(other.rawTargetType, rawTargetType) || other.rawTargetType == rawTargetType)&&(identical(other.backendTargetType, backendTargetType) || other.backendTargetType == backendTargetType)&&(identical(other.house, house) || other.house == house)&&(identical(other.isRetrograde, isRetrograde) || other.isRetrograde == isRetrograde)&&(identical(other.nature, nature) || other.nature == nature)&&(identical(other.rawNature, rawNature) || other.rawNature == rawNature)&&(identical(other.headline, headline) || other.headline == headline));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,transitingPlanet,aspect,natalPlanet,natalAngle,rawTargetAngle,rawTargetType,backendTargetType,house,isRetrograde,nature,rawNature,headline);

@override
String toString() {
  return 'TransitSummary(id: $id, transitingPlanet: $transitingPlanet, aspect: $aspect, natalPlanet: $natalPlanet, natalAngle: $natalAngle, rawTargetAngle: $rawTargetAngle, rawTargetType: $rawTargetType, backendTargetType: $backendTargetType, house: $house, isRetrograde: $isRetrograde, nature: $nature, rawNature: $rawNature, headline: $headline)';
}


}

/// @nodoc
abstract mixin class _$TransitSummaryCopyWith<$Res> implements $TransitSummaryCopyWith<$Res> {
  factory _$TransitSummaryCopyWith(_TransitSummary value, $Res Function(_TransitSummary) _then) = __$TransitSummaryCopyWithImpl;
@override @useResult
$Res call({
 String id, Planet transitingPlanet, AspectType? aspect, Planet? natalPlanet, ChartAngle? natalAngle, String? rawTargetAngle, String? rawTargetType, TransitTargetType? backendTargetType, int? house, bool isRetrograde, InfluenceNature nature, String? rawNature, String? headline
});




}
/// @nodoc
class __$TransitSummaryCopyWithImpl<$Res>
    implements _$TransitSummaryCopyWith<$Res> {
  __$TransitSummaryCopyWithImpl(this._self, this._then);

  final _TransitSummary _self;
  final $Res Function(_TransitSummary) _then;

/// Create a copy of TransitSummary
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? id = null,Object? transitingPlanet = null,Object? aspect = freezed,Object? natalPlanet = freezed,Object? natalAngle = freezed,Object? rawTargetAngle = freezed,Object? rawTargetType = freezed,Object? backendTargetType = freezed,Object? house = freezed,Object? isRetrograde = null,Object? nature = null,Object? rawNature = freezed,Object? headline = freezed,}) {
  return _then(_TransitSummary(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,transitingPlanet: null == transitingPlanet ? _self.transitingPlanet : transitingPlanet // ignore: cast_nullable_to_non_nullable
as Planet,aspect: freezed == aspect ? _self.aspect : aspect // ignore: cast_nullable_to_non_nullable
as AspectType?,natalPlanet: freezed == natalPlanet ? _self.natalPlanet : natalPlanet // ignore: cast_nullable_to_non_nullable
as Planet?,natalAngle: freezed == natalAngle ? _self.natalAngle : natalAngle // ignore: cast_nullable_to_non_nullable
as ChartAngle?,rawTargetAngle: freezed == rawTargetAngle ? _self.rawTargetAngle : rawTargetAngle // ignore: cast_nullable_to_non_nullable
as String?,rawTargetType: freezed == rawTargetType ? _self.rawTargetType : rawTargetType // ignore: cast_nullable_to_non_nullable
as String?,backendTargetType: freezed == backendTargetType ? _self.backendTargetType : backendTargetType // ignore: cast_nullable_to_non_nullable
as TransitTargetType?,house: freezed == house ? _self.house : house // ignore: cast_nullable_to_non_nullable
as int?,isRetrograde: null == isRetrograde ? _self.isRetrograde : isRetrograde // ignore: cast_nullable_to_non_nullable
as bool,nature: null == nature ? _self.nature : nature // ignore: cast_nullable_to_non_nullable
as InfluenceNature,rawNature: freezed == rawNature ? _self.rawNature : rawNature // ignore: cast_nullable_to_non_nullable
as String?,headline: freezed == headline ? _self.headline : headline // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}


}


/// @nodoc
mixin _$TransitPass {

 int get number; DateTime get exactAt; TransitPassDirection get direction; double get speed; String? get rawDirection;
/// Create a copy of TransitPass
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$TransitPassCopyWith<TransitPass> get copyWith => _$TransitPassCopyWithImpl<TransitPass>(this as TransitPass, _$identity);

  /// Serializes this TransitPass to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is TransitPass&&(identical(other.number, number) || other.number == number)&&(identical(other.exactAt, exactAt) || other.exactAt == exactAt)&&(identical(other.direction, direction) || other.direction == direction)&&(identical(other.speed, speed) || other.speed == speed)&&(identical(other.rawDirection, rawDirection) || other.rawDirection == rawDirection));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,number,exactAt,direction,speed,rawDirection);

@override
String toString() {
  return 'TransitPass(number: $number, exactAt: $exactAt, direction: $direction, speed: $speed, rawDirection: $rawDirection)';
}


}

/// @nodoc
abstract mixin class $TransitPassCopyWith<$Res>  {
  factory $TransitPassCopyWith(TransitPass value, $Res Function(TransitPass) _then) = _$TransitPassCopyWithImpl;
@useResult
$Res call({
 int number, DateTime exactAt, TransitPassDirection direction, double speed, String? rawDirection
});




}
/// @nodoc
class _$TransitPassCopyWithImpl<$Res>
    implements $TransitPassCopyWith<$Res> {
  _$TransitPassCopyWithImpl(this._self, this._then);

  final TransitPass _self;
  final $Res Function(TransitPass) _then;

/// Create a copy of TransitPass
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? number = null,Object? exactAt = null,Object? direction = null,Object? speed = null,Object? rawDirection = freezed,}) {
  return _then(_self.copyWith(
number: null == number ? _self.number : number // ignore: cast_nullable_to_non_nullable
as int,exactAt: null == exactAt ? _self.exactAt : exactAt // ignore: cast_nullable_to_non_nullable
as DateTime,direction: null == direction ? _self.direction : direction // ignore: cast_nullable_to_non_nullable
as TransitPassDirection,speed: null == speed ? _self.speed : speed // ignore: cast_nullable_to_non_nullable
as double,rawDirection: freezed == rawDirection ? _self.rawDirection : rawDirection // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

}


/// Adds pattern-matching-related methods to [TransitPass].
extension TransitPassPatterns on TransitPass {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _TransitPass value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _TransitPass() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _TransitPass value)  $default,){
final _that = this;
switch (_that) {
case _TransitPass():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _TransitPass value)?  $default,){
final _that = this;
switch (_that) {
case _TransitPass() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( int number,  DateTime exactAt,  TransitPassDirection direction,  double speed,  String? rawDirection)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _TransitPass() when $default != null:
return $default(_that.number,_that.exactAt,_that.direction,_that.speed,_that.rawDirection);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( int number,  DateTime exactAt,  TransitPassDirection direction,  double speed,  String? rawDirection)  $default,) {final _that = this;
switch (_that) {
case _TransitPass():
return $default(_that.number,_that.exactAt,_that.direction,_that.speed,_that.rawDirection);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( int number,  DateTime exactAt,  TransitPassDirection direction,  double speed,  String? rawDirection)?  $default,) {final _that = this;
switch (_that) {
case _TransitPass() when $default != null:
return $default(_that.number,_that.exactAt,_that.direction,_that.speed,_that.rawDirection);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _TransitPass implements TransitPass {
  const _TransitPass({required this.number, required this.exactAt, required this.direction, required this.speed, this.rawDirection});
  factory _TransitPass.fromJson(Map<String, dynamic> json) => _$TransitPassFromJson(json);

@override final  int number;
@override final  DateTime exactAt;
@override final  TransitPassDirection direction;
@override final  double speed;
@override final  String? rawDirection;

/// Create a copy of TransitPass
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$TransitPassCopyWith<_TransitPass> get copyWith => __$TransitPassCopyWithImpl<_TransitPass>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$TransitPassToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _TransitPass&&(identical(other.number, number) || other.number == number)&&(identical(other.exactAt, exactAt) || other.exactAt == exactAt)&&(identical(other.direction, direction) || other.direction == direction)&&(identical(other.speed, speed) || other.speed == speed)&&(identical(other.rawDirection, rawDirection) || other.rawDirection == rawDirection));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,number,exactAt,direction,speed,rawDirection);

@override
String toString() {
  return 'TransitPass(number: $number, exactAt: $exactAt, direction: $direction, speed: $speed, rawDirection: $rawDirection)';
}


}

/// @nodoc
abstract mixin class _$TransitPassCopyWith<$Res> implements $TransitPassCopyWith<$Res> {
  factory _$TransitPassCopyWith(_TransitPass value, $Res Function(_TransitPass) _then) = __$TransitPassCopyWithImpl;
@override @useResult
$Res call({
 int number, DateTime exactAt, TransitPassDirection direction, double speed, String? rawDirection
});




}
/// @nodoc
class __$TransitPassCopyWithImpl<$Res>
    implements _$TransitPassCopyWith<$Res> {
  __$TransitPassCopyWithImpl(this._self, this._then);

  final _TransitPass _self;
  final $Res Function(_TransitPass) _then;

/// Create a copy of TransitPass
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? number = null,Object? exactAt = null,Object? direction = null,Object? speed = null,Object? rawDirection = freezed,}) {
  return _then(_TransitPass(
number: null == number ? _self.number : number // ignore: cast_nullable_to_non_nullable
as int,exactAt: null == exactAt ? _self.exactAt : exactAt // ignore: cast_nullable_to_non_nullable
as DateTime,direction: null == direction ? _self.direction : direction // ignore: cast_nullable_to_non_nullable
as TransitPassDirection,speed: null == speed ? _self.speed : speed // ignore: cast_nullable_to_non_nullable
as double,rawDirection: freezed == rawDirection ? _self.rawDirection : rawDirection // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}


}


/// @nodoc
mixin _$Transit {

 TransitSummary get summary; DateTime? get startAt; DateTime? get exactAt; DateTime? get endAt;/// Distance from exactness in degrees.
 double get orb;/// 0..1 relative weight used for ordering and emphasis.
 double get strength; int? get strengthScore; TransitStatus get status; String? get rawStatus; List<TransitPass> get passes; List<int> get affectedHouses; bool get windowClipped; double? get maximumOrb; bool? get applying; String? get engineVersion; String? get scoringVersion; Map<String, dynamic> get metadata;/// IANA timezone the [startAt]/[exactAt]/[endAt] instants were computed
/// for. The instants themselves are stored in UTC.
 String? get timezone; String? get interpretation;/// "What to do with it" copy shown in the detail screen.
 String? get guidance;
/// Create a copy of Transit
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$TransitCopyWith<Transit> get copyWith => _$TransitCopyWithImpl<Transit>(this as Transit, _$identity);

  /// Serializes this Transit to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is Transit&&(identical(other.summary, summary) || other.summary == summary)&&(identical(other.startAt, startAt) || other.startAt == startAt)&&(identical(other.exactAt, exactAt) || other.exactAt == exactAt)&&(identical(other.endAt, endAt) || other.endAt == endAt)&&(identical(other.orb, orb) || other.orb == orb)&&(identical(other.strength, strength) || other.strength == strength)&&(identical(other.strengthScore, strengthScore) || other.strengthScore == strengthScore)&&(identical(other.status, status) || other.status == status)&&(identical(other.rawStatus, rawStatus) || other.rawStatus == rawStatus)&&const DeepCollectionEquality().equals(other.passes, passes)&&const DeepCollectionEquality().equals(other.affectedHouses, affectedHouses)&&(identical(other.windowClipped, windowClipped) || other.windowClipped == windowClipped)&&(identical(other.maximumOrb, maximumOrb) || other.maximumOrb == maximumOrb)&&(identical(other.applying, applying) || other.applying == applying)&&(identical(other.engineVersion, engineVersion) || other.engineVersion == engineVersion)&&(identical(other.scoringVersion, scoringVersion) || other.scoringVersion == scoringVersion)&&const DeepCollectionEquality().equals(other.metadata, metadata)&&(identical(other.timezone, timezone) || other.timezone == timezone)&&(identical(other.interpretation, interpretation) || other.interpretation == interpretation)&&(identical(other.guidance, guidance) || other.guidance == guidance));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hashAll([runtimeType,summary,startAt,exactAt,endAt,orb,strength,strengthScore,status,rawStatus,const DeepCollectionEquality().hash(passes),const DeepCollectionEquality().hash(affectedHouses),windowClipped,maximumOrb,applying,engineVersion,scoringVersion,const DeepCollectionEquality().hash(metadata),timezone,interpretation,guidance]);

@override
String toString() {
  return 'Transit(summary: $summary, startAt: $startAt, exactAt: $exactAt, endAt: $endAt, orb: $orb, strength: $strength, strengthScore: $strengthScore, status: $status, rawStatus: $rawStatus, passes: $passes, affectedHouses: $affectedHouses, windowClipped: $windowClipped, maximumOrb: $maximumOrb, applying: $applying, engineVersion: $engineVersion, scoringVersion: $scoringVersion, metadata: $metadata, timezone: $timezone, interpretation: $interpretation, guidance: $guidance)';
}


}

/// @nodoc
abstract mixin class $TransitCopyWith<$Res>  {
  factory $TransitCopyWith(Transit value, $Res Function(Transit) _then) = _$TransitCopyWithImpl;
@useResult
$Res call({
 TransitSummary summary, DateTime? startAt, DateTime? exactAt, DateTime? endAt, double orb, double strength, int? strengthScore, TransitStatus status, String? rawStatus, List<TransitPass> passes, List<int> affectedHouses, bool windowClipped, double? maximumOrb, bool? applying, String? engineVersion, String? scoringVersion, Map<String, dynamic> metadata, String? timezone, String? interpretation, String? guidance
});


$TransitSummaryCopyWith<$Res> get summary;

}
/// @nodoc
class _$TransitCopyWithImpl<$Res>
    implements $TransitCopyWith<$Res> {
  _$TransitCopyWithImpl(this._self, this._then);

  final Transit _self;
  final $Res Function(Transit) _then;

/// Create a copy of Transit
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? summary = null,Object? startAt = freezed,Object? exactAt = freezed,Object? endAt = freezed,Object? orb = null,Object? strength = null,Object? strengthScore = freezed,Object? status = null,Object? rawStatus = freezed,Object? passes = null,Object? affectedHouses = null,Object? windowClipped = null,Object? maximumOrb = freezed,Object? applying = freezed,Object? engineVersion = freezed,Object? scoringVersion = freezed,Object? metadata = null,Object? timezone = freezed,Object? interpretation = freezed,Object? guidance = freezed,}) {
  return _then(_self.copyWith(
summary: null == summary ? _self.summary : summary // ignore: cast_nullable_to_non_nullable
as TransitSummary,startAt: freezed == startAt ? _self.startAt : startAt // ignore: cast_nullable_to_non_nullable
as DateTime?,exactAt: freezed == exactAt ? _self.exactAt : exactAt // ignore: cast_nullable_to_non_nullable
as DateTime?,endAt: freezed == endAt ? _self.endAt : endAt // ignore: cast_nullable_to_non_nullable
as DateTime?,orb: null == orb ? _self.orb : orb // ignore: cast_nullable_to_non_nullable
as double,strength: null == strength ? _self.strength : strength // ignore: cast_nullable_to_non_nullable
as double,strengthScore: freezed == strengthScore ? _self.strengthScore : strengthScore // ignore: cast_nullable_to_non_nullable
as int?,status: null == status ? _self.status : status // ignore: cast_nullable_to_non_nullable
as TransitStatus,rawStatus: freezed == rawStatus ? _self.rawStatus : rawStatus // ignore: cast_nullable_to_non_nullable
as String?,passes: null == passes ? _self.passes : passes // ignore: cast_nullable_to_non_nullable
as List<TransitPass>,affectedHouses: null == affectedHouses ? _self.affectedHouses : affectedHouses // ignore: cast_nullable_to_non_nullable
as List<int>,windowClipped: null == windowClipped ? _self.windowClipped : windowClipped // ignore: cast_nullable_to_non_nullable
as bool,maximumOrb: freezed == maximumOrb ? _self.maximumOrb : maximumOrb // ignore: cast_nullable_to_non_nullable
as double?,applying: freezed == applying ? _self.applying : applying // ignore: cast_nullable_to_non_nullable
as bool?,engineVersion: freezed == engineVersion ? _self.engineVersion : engineVersion // ignore: cast_nullable_to_non_nullable
as String?,scoringVersion: freezed == scoringVersion ? _self.scoringVersion : scoringVersion // ignore: cast_nullable_to_non_nullable
as String?,metadata: null == metadata ? _self.metadata : metadata // ignore: cast_nullable_to_non_nullable
as Map<String, dynamic>,timezone: freezed == timezone ? _self.timezone : timezone // ignore: cast_nullable_to_non_nullable
as String?,interpretation: freezed == interpretation ? _self.interpretation : interpretation // ignore: cast_nullable_to_non_nullable
as String?,guidance: freezed == guidance ? _self.guidance : guidance // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}
/// Create a copy of Transit
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$TransitSummaryCopyWith<$Res> get summary {
  
  return $TransitSummaryCopyWith<$Res>(_self.summary, (value) {
    return _then(_self.copyWith(summary: value));
  });
}
}


/// Adds pattern-matching-related methods to [Transit].
extension TransitPatterns on Transit {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _Transit value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _Transit() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _Transit value)  $default,){
final _that = this;
switch (_that) {
case _Transit():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _Transit value)?  $default,){
final _that = this;
switch (_that) {
case _Transit() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( TransitSummary summary,  DateTime? startAt,  DateTime? exactAt,  DateTime? endAt,  double orb,  double strength,  int? strengthScore,  TransitStatus status,  String? rawStatus,  List<TransitPass> passes,  List<int> affectedHouses,  bool windowClipped,  double? maximumOrb,  bool? applying,  String? engineVersion,  String? scoringVersion,  Map<String, dynamic> metadata,  String? timezone,  String? interpretation,  String? guidance)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _Transit() when $default != null:
return $default(_that.summary,_that.startAt,_that.exactAt,_that.endAt,_that.orb,_that.strength,_that.strengthScore,_that.status,_that.rawStatus,_that.passes,_that.affectedHouses,_that.windowClipped,_that.maximumOrb,_that.applying,_that.engineVersion,_that.scoringVersion,_that.metadata,_that.timezone,_that.interpretation,_that.guidance);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( TransitSummary summary,  DateTime? startAt,  DateTime? exactAt,  DateTime? endAt,  double orb,  double strength,  int? strengthScore,  TransitStatus status,  String? rawStatus,  List<TransitPass> passes,  List<int> affectedHouses,  bool windowClipped,  double? maximumOrb,  bool? applying,  String? engineVersion,  String? scoringVersion,  Map<String, dynamic> metadata,  String? timezone,  String? interpretation,  String? guidance)  $default,) {final _that = this;
switch (_that) {
case _Transit():
return $default(_that.summary,_that.startAt,_that.exactAt,_that.endAt,_that.orb,_that.strength,_that.strengthScore,_that.status,_that.rawStatus,_that.passes,_that.affectedHouses,_that.windowClipped,_that.maximumOrb,_that.applying,_that.engineVersion,_that.scoringVersion,_that.metadata,_that.timezone,_that.interpretation,_that.guidance);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( TransitSummary summary,  DateTime? startAt,  DateTime? exactAt,  DateTime? endAt,  double orb,  double strength,  int? strengthScore,  TransitStatus status,  String? rawStatus,  List<TransitPass> passes,  List<int> affectedHouses,  bool windowClipped,  double? maximumOrb,  bool? applying,  String? engineVersion,  String? scoringVersion,  Map<String, dynamic> metadata,  String? timezone,  String? interpretation,  String? guidance)?  $default,) {final _that = this;
switch (_that) {
case _Transit() when $default != null:
return $default(_that.summary,_that.startAt,_that.exactAt,_that.endAt,_that.orb,_that.strength,_that.strengthScore,_that.status,_that.rawStatus,_that.passes,_that.affectedHouses,_that.windowClipped,_that.maximumOrb,_that.applying,_that.engineVersion,_that.scoringVersion,_that.metadata,_that.timezone,_that.interpretation,_that.guidance);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _Transit extends Transit {
  const _Transit({required this.summary, this.startAt, this.exactAt, this.endAt, this.orb = 0, this.strength = 0.5, this.strengthScore, this.status = TransitStatus.active, this.rawStatus, final  List<TransitPass> passes = const <TransitPass>[], final  List<int> affectedHouses = const <int>[], this.windowClipped = false, this.maximumOrb, this.applying, this.engineVersion, this.scoringVersion, final  Map<String, dynamic> metadata = const <String, dynamic>{}, this.timezone, this.interpretation, this.guidance}): _passes = passes,_affectedHouses = affectedHouses,_metadata = metadata,super._();
  factory _Transit.fromJson(Map<String, dynamic> json) => _$TransitFromJson(json);

@override final  TransitSummary summary;
@override final  DateTime? startAt;
@override final  DateTime? exactAt;
@override final  DateTime? endAt;
/// Distance from exactness in degrees.
@override@JsonKey() final  double orb;
/// 0..1 relative weight used for ordering and emphasis.
@override@JsonKey() final  double strength;
@override final  int? strengthScore;
@override@JsonKey() final  TransitStatus status;
@override final  String? rawStatus;
 final  List<TransitPass> _passes;
@override@JsonKey() List<TransitPass> get passes {
  if (_passes is EqualUnmodifiableListView) return _passes;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_passes);
}

 final  List<int> _affectedHouses;
@override@JsonKey() List<int> get affectedHouses {
  if (_affectedHouses is EqualUnmodifiableListView) return _affectedHouses;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_affectedHouses);
}

@override@JsonKey() final  bool windowClipped;
@override final  double? maximumOrb;
@override final  bool? applying;
@override final  String? engineVersion;
@override final  String? scoringVersion;
 final  Map<String, dynamic> _metadata;
@override@JsonKey() Map<String, dynamic> get metadata {
  if (_metadata is EqualUnmodifiableMapView) return _metadata;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableMapView(_metadata);
}

/// IANA timezone the [startAt]/[exactAt]/[endAt] instants were computed
/// for. The instants themselves are stored in UTC.
@override final  String? timezone;
@override final  String? interpretation;
/// "What to do with it" copy shown in the detail screen.
@override final  String? guidance;

/// Create a copy of Transit
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$TransitCopyWith<_Transit> get copyWith => __$TransitCopyWithImpl<_Transit>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$TransitToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _Transit&&(identical(other.summary, summary) || other.summary == summary)&&(identical(other.startAt, startAt) || other.startAt == startAt)&&(identical(other.exactAt, exactAt) || other.exactAt == exactAt)&&(identical(other.endAt, endAt) || other.endAt == endAt)&&(identical(other.orb, orb) || other.orb == orb)&&(identical(other.strength, strength) || other.strength == strength)&&(identical(other.strengthScore, strengthScore) || other.strengthScore == strengthScore)&&(identical(other.status, status) || other.status == status)&&(identical(other.rawStatus, rawStatus) || other.rawStatus == rawStatus)&&const DeepCollectionEquality().equals(other._passes, _passes)&&const DeepCollectionEquality().equals(other._affectedHouses, _affectedHouses)&&(identical(other.windowClipped, windowClipped) || other.windowClipped == windowClipped)&&(identical(other.maximumOrb, maximumOrb) || other.maximumOrb == maximumOrb)&&(identical(other.applying, applying) || other.applying == applying)&&(identical(other.engineVersion, engineVersion) || other.engineVersion == engineVersion)&&(identical(other.scoringVersion, scoringVersion) || other.scoringVersion == scoringVersion)&&const DeepCollectionEquality().equals(other._metadata, _metadata)&&(identical(other.timezone, timezone) || other.timezone == timezone)&&(identical(other.interpretation, interpretation) || other.interpretation == interpretation)&&(identical(other.guidance, guidance) || other.guidance == guidance));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hashAll([runtimeType,summary,startAt,exactAt,endAt,orb,strength,strengthScore,status,rawStatus,const DeepCollectionEquality().hash(_passes),const DeepCollectionEquality().hash(_affectedHouses),windowClipped,maximumOrb,applying,engineVersion,scoringVersion,const DeepCollectionEquality().hash(_metadata),timezone,interpretation,guidance]);

@override
String toString() {
  return 'Transit(summary: $summary, startAt: $startAt, exactAt: $exactAt, endAt: $endAt, orb: $orb, strength: $strength, strengthScore: $strengthScore, status: $status, rawStatus: $rawStatus, passes: $passes, affectedHouses: $affectedHouses, windowClipped: $windowClipped, maximumOrb: $maximumOrb, applying: $applying, engineVersion: $engineVersion, scoringVersion: $scoringVersion, metadata: $metadata, timezone: $timezone, interpretation: $interpretation, guidance: $guidance)';
}


}

/// @nodoc
abstract mixin class _$TransitCopyWith<$Res> implements $TransitCopyWith<$Res> {
  factory _$TransitCopyWith(_Transit value, $Res Function(_Transit) _then) = __$TransitCopyWithImpl;
@override @useResult
$Res call({
 TransitSummary summary, DateTime? startAt, DateTime? exactAt, DateTime? endAt, double orb, double strength, int? strengthScore, TransitStatus status, String? rawStatus, List<TransitPass> passes, List<int> affectedHouses, bool windowClipped, double? maximumOrb, bool? applying, String? engineVersion, String? scoringVersion, Map<String, dynamic> metadata, String? timezone, String? interpretation, String? guidance
});


@override $TransitSummaryCopyWith<$Res> get summary;

}
/// @nodoc
class __$TransitCopyWithImpl<$Res>
    implements _$TransitCopyWith<$Res> {
  __$TransitCopyWithImpl(this._self, this._then);

  final _Transit _self;
  final $Res Function(_Transit) _then;

/// Create a copy of Transit
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? summary = null,Object? startAt = freezed,Object? exactAt = freezed,Object? endAt = freezed,Object? orb = null,Object? strength = null,Object? strengthScore = freezed,Object? status = null,Object? rawStatus = freezed,Object? passes = null,Object? affectedHouses = null,Object? windowClipped = null,Object? maximumOrb = freezed,Object? applying = freezed,Object? engineVersion = freezed,Object? scoringVersion = freezed,Object? metadata = null,Object? timezone = freezed,Object? interpretation = freezed,Object? guidance = freezed,}) {
  return _then(_Transit(
summary: null == summary ? _self.summary : summary // ignore: cast_nullable_to_non_nullable
as TransitSummary,startAt: freezed == startAt ? _self.startAt : startAt // ignore: cast_nullable_to_non_nullable
as DateTime?,exactAt: freezed == exactAt ? _self.exactAt : exactAt // ignore: cast_nullable_to_non_nullable
as DateTime?,endAt: freezed == endAt ? _self.endAt : endAt // ignore: cast_nullable_to_non_nullable
as DateTime?,orb: null == orb ? _self.orb : orb // ignore: cast_nullable_to_non_nullable
as double,strength: null == strength ? _self.strength : strength // ignore: cast_nullable_to_non_nullable
as double,strengthScore: freezed == strengthScore ? _self.strengthScore : strengthScore // ignore: cast_nullable_to_non_nullable
as int?,status: null == status ? _self.status : status // ignore: cast_nullable_to_non_nullable
as TransitStatus,rawStatus: freezed == rawStatus ? _self.rawStatus : rawStatus // ignore: cast_nullable_to_non_nullable
as String?,passes: null == passes ? _self._passes : passes // ignore: cast_nullable_to_non_nullable
as List<TransitPass>,affectedHouses: null == affectedHouses ? _self._affectedHouses : affectedHouses // ignore: cast_nullable_to_non_nullable
as List<int>,windowClipped: null == windowClipped ? _self.windowClipped : windowClipped // ignore: cast_nullable_to_non_nullable
as bool,maximumOrb: freezed == maximumOrb ? _self.maximumOrb : maximumOrb // ignore: cast_nullable_to_non_nullable
as double?,applying: freezed == applying ? _self.applying : applying // ignore: cast_nullable_to_non_nullable
as bool?,engineVersion: freezed == engineVersion ? _self.engineVersion : engineVersion // ignore: cast_nullable_to_non_nullable
as String?,scoringVersion: freezed == scoringVersion ? _self.scoringVersion : scoringVersion // ignore: cast_nullable_to_non_nullable
as String?,metadata: null == metadata ? _self._metadata : metadata // ignore: cast_nullable_to_non_nullable
as Map<String, dynamic>,timezone: freezed == timezone ? _self.timezone : timezone // ignore: cast_nullable_to_non_nullable
as String?,interpretation: freezed == interpretation ? _self.interpretation : interpretation // ignore: cast_nullable_to_non_nullable
as String?,guidance: freezed == guidance ? _self.guidance : guidance // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

/// Create a copy of Transit
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$TransitSummaryCopyWith<$Res> get summary {
  
  return $TransitSummaryCopyWith<$Res>(_self.summary, (value) {
    return _then(_self.copyWith(summary: value));
  });
}
}

// dart format on
