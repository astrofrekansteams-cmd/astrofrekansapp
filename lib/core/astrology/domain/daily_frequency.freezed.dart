// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'daily_frequency.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$AreaScore {

 LifeArea get area; int get score; ScoreTrend get trend; int get strength; List<String> get factorIds; String? get rawArea; String? get rawTrend;
/// Create a copy of AreaScore
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$AreaScoreCopyWith<AreaScore> get copyWith => _$AreaScoreCopyWithImpl<AreaScore>(this as AreaScore, _$identity);

  /// Serializes this AreaScore to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is AreaScore&&(identical(other.area, area) || other.area == area)&&(identical(other.score, score) || other.score == score)&&(identical(other.trend, trend) || other.trend == trend)&&(identical(other.strength, strength) || other.strength == strength)&&const DeepCollectionEquality().equals(other.factorIds, factorIds)&&(identical(other.rawArea, rawArea) || other.rawArea == rawArea)&&(identical(other.rawTrend, rawTrend) || other.rawTrend == rawTrend));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,area,score,trend,strength,const DeepCollectionEquality().hash(factorIds),rawArea,rawTrend);

@override
String toString() {
  return 'AreaScore(area: $area, score: $score, trend: $trend, strength: $strength, factorIds: $factorIds, rawArea: $rawArea, rawTrend: $rawTrend)';
}


}

/// @nodoc
abstract mixin class $AreaScoreCopyWith<$Res>  {
  factory $AreaScoreCopyWith(AreaScore value, $Res Function(AreaScore) _then) = _$AreaScoreCopyWithImpl;
@useResult
$Res call({
 LifeArea area, int score, ScoreTrend trend, int strength, List<String> factorIds, String? rawArea, String? rawTrend
});




}
/// @nodoc
class _$AreaScoreCopyWithImpl<$Res>
    implements $AreaScoreCopyWith<$Res> {
  _$AreaScoreCopyWithImpl(this._self, this._then);

  final AreaScore _self;
  final $Res Function(AreaScore) _then;

/// Create a copy of AreaScore
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? area = null,Object? score = null,Object? trend = null,Object? strength = null,Object? factorIds = null,Object? rawArea = freezed,Object? rawTrend = freezed,}) {
  return _then(_self.copyWith(
area: null == area ? _self.area : area // ignore: cast_nullable_to_non_nullable
as LifeArea,score: null == score ? _self.score : score // ignore: cast_nullable_to_non_nullable
as int,trend: null == trend ? _self.trend : trend // ignore: cast_nullable_to_non_nullable
as ScoreTrend,strength: null == strength ? _self.strength : strength // ignore: cast_nullable_to_non_nullable
as int,factorIds: null == factorIds ? _self.factorIds : factorIds // ignore: cast_nullable_to_non_nullable
as List<String>,rawArea: freezed == rawArea ? _self.rawArea : rawArea // ignore: cast_nullable_to_non_nullable
as String?,rawTrend: freezed == rawTrend ? _self.rawTrend : rawTrend // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

}


/// Adds pattern-matching-related methods to [AreaScore].
extension AreaScorePatterns on AreaScore {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _AreaScore value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _AreaScore() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _AreaScore value)  $default,){
final _that = this;
switch (_that) {
case _AreaScore():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _AreaScore value)?  $default,){
final _that = this;
switch (_that) {
case _AreaScore() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( LifeArea area,  int score,  ScoreTrend trend,  int strength,  List<String> factorIds,  String? rawArea,  String? rawTrend)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _AreaScore() when $default != null:
return $default(_that.area,_that.score,_that.trend,_that.strength,_that.factorIds,_that.rawArea,_that.rawTrend);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( LifeArea area,  int score,  ScoreTrend trend,  int strength,  List<String> factorIds,  String? rawArea,  String? rawTrend)  $default,) {final _that = this;
switch (_that) {
case _AreaScore():
return $default(_that.area,_that.score,_that.trend,_that.strength,_that.factorIds,_that.rawArea,_that.rawTrend);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( LifeArea area,  int score,  ScoreTrend trend,  int strength,  List<String> factorIds,  String? rawArea,  String? rawTrend)?  $default,) {final _that = this;
switch (_that) {
case _AreaScore() when $default != null:
return $default(_that.area,_that.score,_that.trend,_that.strength,_that.factorIds,_that.rawArea,_that.rawTrend);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _AreaScore implements AreaScore {
  const _AreaScore({required this.area, required this.score, required this.trend, required this.strength, final  List<String> factorIds = const <String>[], this.rawArea, this.rawTrend}): _factorIds = factorIds;
  factory _AreaScore.fromJson(Map<String, dynamic> json) => _$AreaScoreFromJson(json);

@override final  LifeArea area;
@override final  int score;
@override final  ScoreTrend trend;
@override final  int strength;
 final  List<String> _factorIds;
@override@JsonKey() List<String> get factorIds {
  if (_factorIds is EqualUnmodifiableListView) return _factorIds;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_factorIds);
}

@override final  String? rawArea;
@override final  String? rawTrend;

/// Create a copy of AreaScore
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$AreaScoreCopyWith<_AreaScore> get copyWith => __$AreaScoreCopyWithImpl<_AreaScore>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$AreaScoreToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _AreaScore&&(identical(other.area, area) || other.area == area)&&(identical(other.score, score) || other.score == score)&&(identical(other.trend, trend) || other.trend == trend)&&(identical(other.strength, strength) || other.strength == strength)&&const DeepCollectionEquality().equals(other._factorIds, _factorIds)&&(identical(other.rawArea, rawArea) || other.rawArea == rawArea)&&(identical(other.rawTrend, rawTrend) || other.rawTrend == rawTrend));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,area,score,trend,strength,const DeepCollectionEquality().hash(_factorIds),rawArea,rawTrend);

@override
String toString() {
  return 'AreaScore(area: $area, score: $score, trend: $trend, strength: $strength, factorIds: $factorIds, rawArea: $rawArea, rawTrend: $rawTrend)';
}


}

/// @nodoc
abstract mixin class _$AreaScoreCopyWith<$Res> implements $AreaScoreCopyWith<$Res> {
  factory _$AreaScoreCopyWith(_AreaScore value, $Res Function(_AreaScore) _then) = __$AreaScoreCopyWithImpl;
@override @useResult
$Res call({
 LifeArea area, int score, ScoreTrend trend, int strength, List<String> factorIds, String? rawArea, String? rawTrend
});




}
/// @nodoc
class __$AreaScoreCopyWithImpl<$Res>
    implements _$AreaScoreCopyWith<$Res> {
  __$AreaScoreCopyWithImpl(this._self, this._then);

  final _AreaScore _self;
  final $Res Function(_AreaScore) _then;

/// Create a copy of AreaScore
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? area = null,Object? score = null,Object? trend = null,Object? strength = null,Object? factorIds = null,Object? rawArea = freezed,Object? rawTrend = freezed,}) {
  return _then(_AreaScore(
area: null == area ? _self.area : area // ignore: cast_nullable_to_non_nullable
as LifeArea,score: null == score ? _self.score : score // ignore: cast_nullable_to_non_nullable
as int,trend: null == trend ? _self.trend : trend // ignore: cast_nullable_to_non_nullable
as ScoreTrend,strength: null == strength ? _self.strength : strength // ignore: cast_nullable_to_non_nullable
as int,factorIds: null == factorIds ? _self._factorIds : factorIds // ignore: cast_nullable_to_non_nullable
as List<String>,rawArea: freezed == rawArea ? _self.rawArea : rawArea // ignore: cast_nullable_to_non_nullable
as String?,rawTrend: freezed == rawTrend ? _self.rawTrend : rawTrend // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}


}


/// @nodoc
mixin _$ImportantHour {

 DateTime get start; DateTime get end; String get type; int get strength; String get reason; List<String> get factorIds;
/// Create a copy of ImportantHour
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$ImportantHourCopyWith<ImportantHour> get copyWith => _$ImportantHourCopyWithImpl<ImportantHour>(this as ImportantHour, _$identity);

  /// Serializes this ImportantHour to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is ImportantHour&&(identical(other.start, start) || other.start == start)&&(identical(other.end, end) || other.end == end)&&(identical(other.type, type) || other.type == type)&&(identical(other.strength, strength) || other.strength == strength)&&(identical(other.reason, reason) || other.reason == reason)&&const DeepCollectionEquality().equals(other.factorIds, factorIds));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,start,end,type,strength,reason,const DeepCollectionEquality().hash(factorIds));

@override
String toString() {
  return 'ImportantHour(start: $start, end: $end, type: $type, strength: $strength, reason: $reason, factorIds: $factorIds)';
}


}

/// @nodoc
abstract mixin class $ImportantHourCopyWith<$Res>  {
  factory $ImportantHourCopyWith(ImportantHour value, $Res Function(ImportantHour) _then) = _$ImportantHourCopyWithImpl;
@useResult
$Res call({
 DateTime start, DateTime end, String type, int strength, String reason, List<String> factorIds
});




}
/// @nodoc
class _$ImportantHourCopyWithImpl<$Res>
    implements $ImportantHourCopyWith<$Res> {
  _$ImportantHourCopyWithImpl(this._self, this._then);

  final ImportantHour _self;
  final $Res Function(ImportantHour) _then;

/// Create a copy of ImportantHour
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? start = null,Object? end = null,Object? type = null,Object? strength = null,Object? reason = null,Object? factorIds = null,}) {
  return _then(_self.copyWith(
start: null == start ? _self.start : start // ignore: cast_nullable_to_non_nullable
as DateTime,end: null == end ? _self.end : end // ignore: cast_nullable_to_non_nullable
as DateTime,type: null == type ? _self.type : type // ignore: cast_nullable_to_non_nullable
as String,strength: null == strength ? _self.strength : strength // ignore: cast_nullable_to_non_nullable
as int,reason: null == reason ? _self.reason : reason // ignore: cast_nullable_to_non_nullable
as String,factorIds: null == factorIds ? _self.factorIds : factorIds // ignore: cast_nullable_to_non_nullable
as List<String>,
  ));
}

}


/// Adds pattern-matching-related methods to [ImportantHour].
extension ImportantHourPatterns on ImportantHour {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _ImportantHour value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _ImportantHour() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _ImportantHour value)  $default,){
final _that = this;
switch (_that) {
case _ImportantHour():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _ImportantHour value)?  $default,){
final _that = this;
switch (_that) {
case _ImportantHour() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( DateTime start,  DateTime end,  String type,  int strength,  String reason,  List<String> factorIds)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _ImportantHour() when $default != null:
return $default(_that.start,_that.end,_that.type,_that.strength,_that.reason,_that.factorIds);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( DateTime start,  DateTime end,  String type,  int strength,  String reason,  List<String> factorIds)  $default,) {final _that = this;
switch (_that) {
case _ImportantHour():
return $default(_that.start,_that.end,_that.type,_that.strength,_that.reason,_that.factorIds);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( DateTime start,  DateTime end,  String type,  int strength,  String reason,  List<String> factorIds)?  $default,) {final _that = this;
switch (_that) {
case _ImportantHour() when $default != null:
return $default(_that.start,_that.end,_that.type,_that.strength,_that.reason,_that.factorIds);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _ImportantHour implements ImportantHour {
  const _ImportantHour({required this.start, required this.end, required this.type, required this.strength, required this.reason, final  List<String> factorIds = const <String>[]}): _factorIds = factorIds;
  factory _ImportantHour.fromJson(Map<String, dynamic> json) => _$ImportantHourFromJson(json);

@override final  DateTime start;
@override final  DateTime end;
@override final  String type;
@override final  int strength;
@override final  String reason;
 final  List<String> _factorIds;
@override@JsonKey() List<String> get factorIds {
  if (_factorIds is EqualUnmodifiableListView) return _factorIds;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_factorIds);
}


/// Create a copy of ImportantHour
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$ImportantHourCopyWith<_ImportantHour> get copyWith => __$ImportantHourCopyWithImpl<_ImportantHour>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$ImportantHourToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _ImportantHour&&(identical(other.start, start) || other.start == start)&&(identical(other.end, end) || other.end == end)&&(identical(other.type, type) || other.type == type)&&(identical(other.strength, strength) || other.strength == strength)&&(identical(other.reason, reason) || other.reason == reason)&&const DeepCollectionEquality().equals(other._factorIds, _factorIds));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,start,end,type,strength,reason,const DeepCollectionEquality().hash(_factorIds));

@override
String toString() {
  return 'ImportantHour(start: $start, end: $end, type: $type, strength: $strength, reason: $reason, factorIds: $factorIds)';
}


}

/// @nodoc
abstract mixin class _$ImportantHourCopyWith<$Res> implements $ImportantHourCopyWith<$Res> {
  factory _$ImportantHourCopyWith(_ImportantHour value, $Res Function(_ImportantHour) _then) = __$ImportantHourCopyWithImpl;
@override @useResult
$Res call({
 DateTime start, DateTime end, String type, int strength, String reason, List<String> factorIds
});




}
/// @nodoc
class __$ImportantHourCopyWithImpl<$Res>
    implements _$ImportantHourCopyWith<$Res> {
  __$ImportantHourCopyWithImpl(this._self, this._then);

  final _ImportantHour _self;
  final $Res Function(_ImportantHour) _then;

/// Create a copy of ImportantHour
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? start = null,Object? end = null,Object? type = null,Object? strength = null,Object? reason = null,Object? factorIds = null,}) {
  return _then(_ImportantHour(
start: null == start ? _self.start : start // ignore: cast_nullable_to_non_nullable
as DateTime,end: null == end ? _self.end : end // ignore: cast_nullable_to_non_nullable
as DateTime,type: null == type ? _self.type : type // ignore: cast_nullable_to_non_nullable
as String,strength: null == strength ? _self.strength : strength // ignore: cast_nullable_to_non_nullable
as int,reason: null == reason ? _self.reason : reason // ignore: cast_nullable_to_non_nullable
as String,factorIds: null == factorIds ? _self._factorIds : factorIds // ignore: cast_nullable_to_non_nullable
as List<String>,
  ));
}


}


/// @nodoc
mixin _$SourceFactor {

 String get id; String get kind; String get label; double get contribution; List<LifeArea> get areas; DateTime? get at; Map<String, dynamic> get detail;
/// Create a copy of SourceFactor
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$SourceFactorCopyWith<SourceFactor> get copyWith => _$SourceFactorCopyWithImpl<SourceFactor>(this as SourceFactor, _$identity);

  /// Serializes this SourceFactor to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is SourceFactor&&(identical(other.id, id) || other.id == id)&&(identical(other.kind, kind) || other.kind == kind)&&(identical(other.label, label) || other.label == label)&&(identical(other.contribution, contribution) || other.contribution == contribution)&&const DeepCollectionEquality().equals(other.areas, areas)&&(identical(other.at, at) || other.at == at)&&const DeepCollectionEquality().equals(other.detail, detail));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,kind,label,contribution,const DeepCollectionEquality().hash(areas),at,const DeepCollectionEquality().hash(detail));

@override
String toString() {
  return 'SourceFactor(id: $id, kind: $kind, label: $label, contribution: $contribution, areas: $areas, at: $at, detail: $detail)';
}


}

/// @nodoc
abstract mixin class $SourceFactorCopyWith<$Res>  {
  factory $SourceFactorCopyWith(SourceFactor value, $Res Function(SourceFactor) _then) = _$SourceFactorCopyWithImpl;
@useResult
$Res call({
 String id, String kind, String label, double contribution, List<LifeArea> areas, DateTime? at, Map<String, dynamic> detail
});




}
/// @nodoc
class _$SourceFactorCopyWithImpl<$Res>
    implements $SourceFactorCopyWith<$Res> {
  _$SourceFactorCopyWithImpl(this._self, this._then);

  final SourceFactor _self;
  final $Res Function(SourceFactor) _then;

/// Create a copy of SourceFactor
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? id = null,Object? kind = null,Object? label = null,Object? contribution = null,Object? areas = null,Object? at = freezed,Object? detail = null,}) {
  return _then(_self.copyWith(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,kind: null == kind ? _self.kind : kind // ignore: cast_nullable_to_non_nullable
as String,label: null == label ? _self.label : label // ignore: cast_nullable_to_non_nullable
as String,contribution: null == contribution ? _self.contribution : contribution // ignore: cast_nullable_to_non_nullable
as double,areas: null == areas ? _self.areas : areas // ignore: cast_nullable_to_non_nullable
as List<LifeArea>,at: freezed == at ? _self.at : at // ignore: cast_nullable_to_non_nullable
as DateTime?,detail: null == detail ? _self.detail : detail // ignore: cast_nullable_to_non_nullable
as Map<String, dynamic>,
  ));
}

}


/// Adds pattern-matching-related methods to [SourceFactor].
extension SourceFactorPatterns on SourceFactor {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _SourceFactor value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _SourceFactor() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _SourceFactor value)  $default,){
final _that = this;
switch (_that) {
case _SourceFactor():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _SourceFactor value)?  $default,){
final _that = this;
switch (_that) {
case _SourceFactor() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String id,  String kind,  String label,  double contribution,  List<LifeArea> areas,  DateTime? at,  Map<String, dynamic> detail)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _SourceFactor() when $default != null:
return $default(_that.id,_that.kind,_that.label,_that.contribution,_that.areas,_that.at,_that.detail);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String id,  String kind,  String label,  double contribution,  List<LifeArea> areas,  DateTime? at,  Map<String, dynamic> detail)  $default,) {final _that = this;
switch (_that) {
case _SourceFactor():
return $default(_that.id,_that.kind,_that.label,_that.contribution,_that.areas,_that.at,_that.detail);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String id,  String kind,  String label,  double contribution,  List<LifeArea> areas,  DateTime? at,  Map<String, dynamic> detail)?  $default,) {final _that = this;
switch (_that) {
case _SourceFactor() when $default != null:
return $default(_that.id,_that.kind,_that.label,_that.contribution,_that.areas,_that.at,_that.detail);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _SourceFactor implements SourceFactor {
  const _SourceFactor({required this.id, required this.kind, required this.label, required this.contribution, final  List<LifeArea> areas = const <LifeArea>[], this.at, final  Map<String, dynamic> detail = const <String, dynamic>{}}): _areas = areas,_detail = detail;
  factory _SourceFactor.fromJson(Map<String, dynamic> json) => _$SourceFactorFromJson(json);

@override final  String id;
@override final  String kind;
@override final  String label;
@override final  double contribution;
 final  List<LifeArea> _areas;
@override@JsonKey() List<LifeArea> get areas {
  if (_areas is EqualUnmodifiableListView) return _areas;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_areas);
}

@override final  DateTime? at;
 final  Map<String, dynamic> _detail;
@override@JsonKey() Map<String, dynamic> get detail {
  if (_detail is EqualUnmodifiableMapView) return _detail;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableMapView(_detail);
}


/// Create a copy of SourceFactor
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$SourceFactorCopyWith<_SourceFactor> get copyWith => __$SourceFactorCopyWithImpl<_SourceFactor>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$SourceFactorToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _SourceFactor&&(identical(other.id, id) || other.id == id)&&(identical(other.kind, kind) || other.kind == kind)&&(identical(other.label, label) || other.label == label)&&(identical(other.contribution, contribution) || other.contribution == contribution)&&const DeepCollectionEquality().equals(other._areas, _areas)&&(identical(other.at, at) || other.at == at)&&const DeepCollectionEquality().equals(other._detail, _detail));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,kind,label,contribution,const DeepCollectionEquality().hash(_areas),at,const DeepCollectionEquality().hash(_detail));

@override
String toString() {
  return 'SourceFactor(id: $id, kind: $kind, label: $label, contribution: $contribution, areas: $areas, at: $at, detail: $detail)';
}


}

/// @nodoc
abstract mixin class _$SourceFactorCopyWith<$Res> implements $SourceFactorCopyWith<$Res> {
  factory _$SourceFactorCopyWith(_SourceFactor value, $Res Function(_SourceFactor) _then) = __$SourceFactorCopyWithImpl;
@override @useResult
$Res call({
 String id, String kind, String label, double contribution, List<LifeArea> areas, DateTime? at, Map<String, dynamic> detail
});




}
/// @nodoc
class __$SourceFactorCopyWithImpl<$Res>
    implements _$SourceFactorCopyWith<$Res> {
  __$SourceFactorCopyWithImpl(this._self, this._then);

  final _SourceFactor _self;
  final $Res Function(_SourceFactor) _then;

/// Create a copy of SourceFactor
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? id = null,Object? kind = null,Object? label = null,Object? contribution = null,Object? areas = null,Object? at = freezed,Object? detail = null,}) {
  return _then(_SourceFactor(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,kind: null == kind ? _self.kind : kind // ignore: cast_nullable_to_non_nullable
as String,label: null == label ? _self.label : label // ignore: cast_nullable_to_non_nullable
as String,contribution: null == contribution ? _self.contribution : contribution // ignore: cast_nullable_to_non_nullable
as double,areas: null == areas ? _self._areas : areas // ignore: cast_nullable_to_non_nullable
as List<LifeArea>,at: freezed == at ? _self.at : at // ignore: cast_nullable_to_non_nullable
as DateTime?,detail: null == detail ? _self._detail : detail // ignore: cast_nullable_to_non_nullable
as Map<String, dynamic>,
  ));
}


}


/// @nodoc
mixin _$FrequencyMetric {

 FrequencyCategory get category;/// 0-100.
 int get score;
/// Create a copy of FrequencyMetric
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$FrequencyMetricCopyWith<FrequencyMetric> get copyWith => _$FrequencyMetricCopyWithImpl<FrequencyMetric>(this as FrequencyMetric, _$identity);

  /// Serializes this FrequencyMetric to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is FrequencyMetric&&(identical(other.category, category) || other.category == category)&&(identical(other.score, score) || other.score == score));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,category,score);

@override
String toString() {
  return 'FrequencyMetric(category: $category, score: $score)';
}


}

/// @nodoc
abstract mixin class $FrequencyMetricCopyWith<$Res>  {
  factory $FrequencyMetricCopyWith(FrequencyMetric value, $Res Function(FrequencyMetric) _then) = _$FrequencyMetricCopyWithImpl;
@useResult
$Res call({
 FrequencyCategory category, int score
});




}
/// @nodoc
class _$FrequencyMetricCopyWithImpl<$Res>
    implements $FrequencyMetricCopyWith<$Res> {
  _$FrequencyMetricCopyWithImpl(this._self, this._then);

  final FrequencyMetric _self;
  final $Res Function(FrequencyMetric) _then;

/// Create a copy of FrequencyMetric
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? category = null,Object? score = null,}) {
  return _then(_self.copyWith(
category: null == category ? _self.category : category // ignore: cast_nullable_to_non_nullable
as FrequencyCategory,score: null == score ? _self.score : score // ignore: cast_nullable_to_non_nullable
as int,
  ));
}

}


/// Adds pattern-matching-related methods to [FrequencyMetric].
extension FrequencyMetricPatterns on FrequencyMetric {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _FrequencyMetric value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _FrequencyMetric() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _FrequencyMetric value)  $default,){
final _that = this;
switch (_that) {
case _FrequencyMetric():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _FrequencyMetric value)?  $default,){
final _that = this;
switch (_that) {
case _FrequencyMetric() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( FrequencyCategory category,  int score)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _FrequencyMetric() when $default != null:
return $default(_that.category,_that.score);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( FrequencyCategory category,  int score)  $default,) {final _that = this;
switch (_that) {
case _FrequencyMetric():
return $default(_that.category,_that.score);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( FrequencyCategory category,  int score)?  $default,) {final _that = this;
switch (_that) {
case _FrequencyMetric() when $default != null:
return $default(_that.category,_that.score);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _FrequencyMetric implements FrequencyMetric {
  const _FrequencyMetric({required this.category, required this.score});
  factory _FrequencyMetric.fromJson(Map<String, dynamic> json) => _$FrequencyMetricFromJson(json);

@override final  FrequencyCategory category;
/// 0-100.
@override final  int score;

/// Create a copy of FrequencyMetric
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$FrequencyMetricCopyWith<_FrequencyMetric> get copyWith => __$FrequencyMetricCopyWithImpl<_FrequencyMetric>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$FrequencyMetricToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _FrequencyMetric&&(identical(other.category, category) || other.category == category)&&(identical(other.score, score) || other.score == score));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,category,score);

@override
String toString() {
  return 'FrequencyMetric(category: $category, score: $score)';
}


}

/// @nodoc
abstract mixin class _$FrequencyMetricCopyWith<$Res> implements $FrequencyMetricCopyWith<$Res> {
  factory _$FrequencyMetricCopyWith(_FrequencyMetric value, $Res Function(_FrequencyMetric) _then) = __$FrequencyMetricCopyWithImpl;
@override @useResult
$Res call({
 FrequencyCategory category, int score
});




}
/// @nodoc
class __$FrequencyMetricCopyWithImpl<$Res>
    implements _$FrequencyMetricCopyWith<$Res> {
  __$FrequencyMetricCopyWithImpl(this._self, this._then);

  final _FrequencyMetric _self;
  final $Res Function(_FrequencyMetric) _then;

/// Create a copy of FrequencyMetric
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? category = null,Object? score = null,}) {
  return _then(_FrequencyMetric(
category: null == category ? _self.category : category // ignore: cast_nullable_to_non_nullable
as FrequencyCategory,score: null == score ? _self.score : score // ignore: cast_nullable_to_non_nullable
as int,
  ));
}


}


/// @nodoc
mixin _$QuickInsight {

 String get id; String get title; String get body; FrequencyCategory? get category;
/// Create a copy of QuickInsight
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$QuickInsightCopyWith<QuickInsight> get copyWith => _$QuickInsightCopyWithImpl<QuickInsight>(this as QuickInsight, _$identity);

  /// Serializes this QuickInsight to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is QuickInsight&&(identical(other.id, id) || other.id == id)&&(identical(other.title, title) || other.title == title)&&(identical(other.body, body) || other.body == body)&&(identical(other.category, category) || other.category == category));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,title,body,category);

@override
String toString() {
  return 'QuickInsight(id: $id, title: $title, body: $body, category: $category)';
}


}

/// @nodoc
abstract mixin class $QuickInsightCopyWith<$Res>  {
  factory $QuickInsightCopyWith(QuickInsight value, $Res Function(QuickInsight) _then) = _$QuickInsightCopyWithImpl;
@useResult
$Res call({
 String id, String title, String body, FrequencyCategory? category
});




}
/// @nodoc
class _$QuickInsightCopyWithImpl<$Res>
    implements $QuickInsightCopyWith<$Res> {
  _$QuickInsightCopyWithImpl(this._self, this._then);

  final QuickInsight _self;
  final $Res Function(QuickInsight) _then;

/// Create a copy of QuickInsight
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? id = null,Object? title = null,Object? body = null,Object? category = freezed,}) {
  return _then(_self.copyWith(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,title: null == title ? _self.title : title // ignore: cast_nullable_to_non_nullable
as String,body: null == body ? _self.body : body // ignore: cast_nullable_to_non_nullable
as String,category: freezed == category ? _self.category : category // ignore: cast_nullable_to_non_nullable
as FrequencyCategory?,
  ));
}

}


/// Adds pattern-matching-related methods to [QuickInsight].
extension QuickInsightPatterns on QuickInsight {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _QuickInsight value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _QuickInsight() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _QuickInsight value)  $default,){
final _that = this;
switch (_that) {
case _QuickInsight():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _QuickInsight value)?  $default,){
final _that = this;
switch (_that) {
case _QuickInsight() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String id,  String title,  String body,  FrequencyCategory? category)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _QuickInsight() when $default != null:
return $default(_that.id,_that.title,_that.body,_that.category);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String id,  String title,  String body,  FrequencyCategory? category)  $default,) {final _that = this;
switch (_that) {
case _QuickInsight():
return $default(_that.id,_that.title,_that.body,_that.category);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String id,  String title,  String body,  FrequencyCategory? category)?  $default,) {final _that = this;
switch (_that) {
case _QuickInsight() when $default != null:
return $default(_that.id,_that.title,_that.body,_that.category);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _QuickInsight implements QuickInsight {
  const _QuickInsight({required this.id, required this.title, required this.body, this.category});
  factory _QuickInsight.fromJson(Map<String, dynamic> json) => _$QuickInsightFromJson(json);

@override final  String id;
@override final  String title;
@override final  String body;
@override final  FrequencyCategory? category;

/// Create a copy of QuickInsight
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$QuickInsightCopyWith<_QuickInsight> get copyWith => __$QuickInsightCopyWithImpl<_QuickInsight>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$QuickInsightToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _QuickInsight&&(identical(other.id, id) || other.id == id)&&(identical(other.title, title) || other.title == title)&&(identical(other.body, body) || other.body == body)&&(identical(other.category, category) || other.category == category));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,title,body,category);

@override
String toString() {
  return 'QuickInsight(id: $id, title: $title, body: $body, category: $category)';
}


}

/// @nodoc
abstract mixin class _$QuickInsightCopyWith<$Res> implements $QuickInsightCopyWith<$Res> {
  factory _$QuickInsightCopyWith(_QuickInsight value, $Res Function(_QuickInsight) _then) = __$QuickInsightCopyWithImpl;
@override @useResult
$Res call({
 String id, String title, String body, FrequencyCategory? category
});




}
/// @nodoc
class __$QuickInsightCopyWithImpl<$Res>
    implements _$QuickInsightCopyWith<$Res> {
  __$QuickInsightCopyWithImpl(this._self, this._then);

  final _QuickInsight _self;
  final $Res Function(_QuickInsight) _then;

/// Create a copy of QuickInsight
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? id = null,Object? title = null,Object? body = null,Object? category = freezed,}) {
  return _then(_QuickInsight(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,title: null == title ? _self.title : title // ignore: cast_nullable_to_non_nullable
as String,body: null == body ? _self.body : body // ignore: cast_nullable_to_non_nullable
as String,category: freezed == category ? _self.category : category // ignore: cast_nullable_to_non_nullable
as FrequencyCategory?,
  ));
}


}


/// @nodoc
mixin _$DailyFrequency {

 DateTime get date;/// 0-100 overall score.
 int get overallScore; List<FrequencyMetric> get metrics; List<AreaScore> get scores; List<ImportantHour> get importantHours; List<SourceFactor> get influences; Map<String, dynamic> get messageContext; String? get timezone; String? get engineVersion; String? get scoringVersion; bool? get cached; List<TransitSummary> get transits; MoonPhaseSummary? get moon; QuickInsight? get message; List<String> get suggestedPrompts;
/// Create a copy of DailyFrequency
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$DailyFrequencyCopyWith<DailyFrequency> get copyWith => _$DailyFrequencyCopyWithImpl<DailyFrequency>(this as DailyFrequency, _$identity);

  /// Serializes this DailyFrequency to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is DailyFrequency&&(identical(other.date, date) || other.date == date)&&(identical(other.overallScore, overallScore) || other.overallScore == overallScore)&&const DeepCollectionEquality().equals(other.metrics, metrics)&&const DeepCollectionEquality().equals(other.scores, scores)&&const DeepCollectionEquality().equals(other.importantHours, importantHours)&&const DeepCollectionEquality().equals(other.influences, influences)&&const DeepCollectionEquality().equals(other.messageContext, messageContext)&&(identical(other.timezone, timezone) || other.timezone == timezone)&&(identical(other.engineVersion, engineVersion) || other.engineVersion == engineVersion)&&(identical(other.scoringVersion, scoringVersion) || other.scoringVersion == scoringVersion)&&(identical(other.cached, cached) || other.cached == cached)&&const DeepCollectionEquality().equals(other.transits, transits)&&(identical(other.moon, moon) || other.moon == moon)&&(identical(other.message, message) || other.message == message)&&const DeepCollectionEquality().equals(other.suggestedPrompts, suggestedPrompts));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,date,overallScore,const DeepCollectionEquality().hash(metrics),const DeepCollectionEquality().hash(scores),const DeepCollectionEquality().hash(importantHours),const DeepCollectionEquality().hash(influences),const DeepCollectionEquality().hash(messageContext),timezone,engineVersion,scoringVersion,cached,const DeepCollectionEquality().hash(transits),moon,message,const DeepCollectionEquality().hash(suggestedPrompts));

@override
String toString() {
  return 'DailyFrequency(date: $date, overallScore: $overallScore, metrics: $metrics, scores: $scores, importantHours: $importantHours, influences: $influences, messageContext: $messageContext, timezone: $timezone, engineVersion: $engineVersion, scoringVersion: $scoringVersion, cached: $cached, transits: $transits, moon: $moon, message: $message, suggestedPrompts: $suggestedPrompts)';
}


}

/// @nodoc
abstract mixin class $DailyFrequencyCopyWith<$Res>  {
  factory $DailyFrequencyCopyWith(DailyFrequency value, $Res Function(DailyFrequency) _then) = _$DailyFrequencyCopyWithImpl;
@useResult
$Res call({
 DateTime date, int overallScore, List<FrequencyMetric> metrics, List<AreaScore> scores, List<ImportantHour> importantHours, List<SourceFactor> influences, Map<String, dynamic> messageContext, String? timezone, String? engineVersion, String? scoringVersion, bool? cached, List<TransitSummary> transits, MoonPhaseSummary? moon, QuickInsight? message, List<String> suggestedPrompts
});


$MoonPhaseSummaryCopyWith<$Res>? get moon;$QuickInsightCopyWith<$Res>? get message;

}
/// @nodoc
class _$DailyFrequencyCopyWithImpl<$Res>
    implements $DailyFrequencyCopyWith<$Res> {
  _$DailyFrequencyCopyWithImpl(this._self, this._then);

  final DailyFrequency _self;
  final $Res Function(DailyFrequency) _then;

/// Create a copy of DailyFrequency
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? date = null,Object? overallScore = null,Object? metrics = null,Object? scores = null,Object? importantHours = null,Object? influences = null,Object? messageContext = null,Object? timezone = freezed,Object? engineVersion = freezed,Object? scoringVersion = freezed,Object? cached = freezed,Object? transits = null,Object? moon = freezed,Object? message = freezed,Object? suggestedPrompts = null,}) {
  return _then(_self.copyWith(
date: null == date ? _self.date : date // ignore: cast_nullable_to_non_nullable
as DateTime,overallScore: null == overallScore ? _self.overallScore : overallScore // ignore: cast_nullable_to_non_nullable
as int,metrics: null == metrics ? _self.metrics : metrics // ignore: cast_nullable_to_non_nullable
as List<FrequencyMetric>,scores: null == scores ? _self.scores : scores // ignore: cast_nullable_to_non_nullable
as List<AreaScore>,importantHours: null == importantHours ? _self.importantHours : importantHours // ignore: cast_nullable_to_non_nullable
as List<ImportantHour>,influences: null == influences ? _self.influences : influences // ignore: cast_nullable_to_non_nullable
as List<SourceFactor>,messageContext: null == messageContext ? _self.messageContext : messageContext // ignore: cast_nullable_to_non_nullable
as Map<String, dynamic>,timezone: freezed == timezone ? _self.timezone : timezone // ignore: cast_nullable_to_non_nullable
as String?,engineVersion: freezed == engineVersion ? _self.engineVersion : engineVersion // ignore: cast_nullable_to_non_nullable
as String?,scoringVersion: freezed == scoringVersion ? _self.scoringVersion : scoringVersion // ignore: cast_nullable_to_non_nullable
as String?,cached: freezed == cached ? _self.cached : cached // ignore: cast_nullable_to_non_nullable
as bool?,transits: null == transits ? _self.transits : transits // ignore: cast_nullable_to_non_nullable
as List<TransitSummary>,moon: freezed == moon ? _self.moon : moon // ignore: cast_nullable_to_non_nullable
as MoonPhaseSummary?,message: freezed == message ? _self.message : message // ignore: cast_nullable_to_non_nullable
as QuickInsight?,suggestedPrompts: null == suggestedPrompts ? _self.suggestedPrompts : suggestedPrompts // ignore: cast_nullable_to_non_nullable
as List<String>,
  ));
}
/// Create a copy of DailyFrequency
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$MoonPhaseSummaryCopyWith<$Res>? get moon {
    if (_self.moon == null) {
    return null;
  }

  return $MoonPhaseSummaryCopyWith<$Res>(_self.moon!, (value) {
    return _then(_self.copyWith(moon: value));
  });
}/// Create a copy of DailyFrequency
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$QuickInsightCopyWith<$Res>? get message {
    if (_self.message == null) {
    return null;
  }

  return $QuickInsightCopyWith<$Res>(_self.message!, (value) {
    return _then(_self.copyWith(message: value));
  });
}
}


/// Adds pattern-matching-related methods to [DailyFrequency].
extension DailyFrequencyPatterns on DailyFrequency {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _DailyFrequency value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _DailyFrequency() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _DailyFrequency value)  $default,){
final _that = this;
switch (_that) {
case _DailyFrequency():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _DailyFrequency value)?  $default,){
final _that = this;
switch (_that) {
case _DailyFrequency() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( DateTime date,  int overallScore,  List<FrequencyMetric> metrics,  List<AreaScore> scores,  List<ImportantHour> importantHours,  List<SourceFactor> influences,  Map<String, dynamic> messageContext,  String? timezone,  String? engineVersion,  String? scoringVersion,  bool? cached,  List<TransitSummary> transits,  MoonPhaseSummary? moon,  QuickInsight? message,  List<String> suggestedPrompts)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _DailyFrequency() when $default != null:
return $default(_that.date,_that.overallScore,_that.metrics,_that.scores,_that.importantHours,_that.influences,_that.messageContext,_that.timezone,_that.engineVersion,_that.scoringVersion,_that.cached,_that.transits,_that.moon,_that.message,_that.suggestedPrompts);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( DateTime date,  int overallScore,  List<FrequencyMetric> metrics,  List<AreaScore> scores,  List<ImportantHour> importantHours,  List<SourceFactor> influences,  Map<String, dynamic> messageContext,  String? timezone,  String? engineVersion,  String? scoringVersion,  bool? cached,  List<TransitSummary> transits,  MoonPhaseSummary? moon,  QuickInsight? message,  List<String> suggestedPrompts)  $default,) {final _that = this;
switch (_that) {
case _DailyFrequency():
return $default(_that.date,_that.overallScore,_that.metrics,_that.scores,_that.importantHours,_that.influences,_that.messageContext,_that.timezone,_that.engineVersion,_that.scoringVersion,_that.cached,_that.transits,_that.moon,_that.message,_that.suggestedPrompts);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( DateTime date,  int overallScore,  List<FrequencyMetric> metrics,  List<AreaScore> scores,  List<ImportantHour> importantHours,  List<SourceFactor> influences,  Map<String, dynamic> messageContext,  String? timezone,  String? engineVersion,  String? scoringVersion,  bool? cached,  List<TransitSummary> transits,  MoonPhaseSummary? moon,  QuickInsight? message,  List<String> suggestedPrompts)?  $default,) {final _that = this;
switch (_that) {
case _DailyFrequency() when $default != null:
return $default(_that.date,_that.overallScore,_that.metrics,_that.scores,_that.importantHours,_that.influences,_that.messageContext,_that.timezone,_that.engineVersion,_that.scoringVersion,_that.cached,_that.transits,_that.moon,_that.message,_that.suggestedPrompts);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _DailyFrequency extends DailyFrequency {
  const _DailyFrequency({required this.date, required this.overallScore, required final  List<FrequencyMetric> metrics, final  List<AreaScore> scores = const <AreaScore>[], final  List<ImportantHour> importantHours = const <ImportantHour>[], final  List<SourceFactor> influences = const <SourceFactor>[], final  Map<String, dynamic> messageContext = const <String, dynamic>{}, this.timezone, this.engineVersion, this.scoringVersion, this.cached, final  List<TransitSummary> transits = const <TransitSummary>[], this.moon, this.message, final  List<String> suggestedPrompts = const <String>[]}): _metrics = metrics,_scores = scores,_importantHours = importantHours,_influences = influences,_messageContext = messageContext,_transits = transits,_suggestedPrompts = suggestedPrompts,super._();
  factory _DailyFrequency.fromJson(Map<String, dynamic> json) => _$DailyFrequencyFromJson(json);

@override final  DateTime date;
/// 0-100 overall score.
@override final  int overallScore;
 final  List<FrequencyMetric> _metrics;
@override List<FrequencyMetric> get metrics {
  if (_metrics is EqualUnmodifiableListView) return _metrics;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_metrics);
}

 final  List<AreaScore> _scores;
@override@JsonKey() List<AreaScore> get scores {
  if (_scores is EqualUnmodifiableListView) return _scores;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_scores);
}

 final  List<ImportantHour> _importantHours;
@override@JsonKey() List<ImportantHour> get importantHours {
  if (_importantHours is EqualUnmodifiableListView) return _importantHours;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_importantHours);
}

 final  List<SourceFactor> _influences;
@override@JsonKey() List<SourceFactor> get influences {
  if (_influences is EqualUnmodifiableListView) return _influences;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_influences);
}

 final  Map<String, dynamic> _messageContext;
@override@JsonKey() Map<String, dynamic> get messageContext {
  if (_messageContext is EqualUnmodifiableMapView) return _messageContext;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableMapView(_messageContext);
}

@override final  String? timezone;
@override final  String? engineVersion;
@override final  String? scoringVersion;
@override final  bool? cached;
 final  List<TransitSummary> _transits;
@override@JsonKey() List<TransitSummary> get transits {
  if (_transits is EqualUnmodifiableListView) return _transits;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_transits);
}

@override final  MoonPhaseSummary? moon;
@override final  QuickInsight? message;
 final  List<String> _suggestedPrompts;
@override@JsonKey() List<String> get suggestedPrompts {
  if (_suggestedPrompts is EqualUnmodifiableListView) return _suggestedPrompts;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_suggestedPrompts);
}


/// Create a copy of DailyFrequency
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$DailyFrequencyCopyWith<_DailyFrequency> get copyWith => __$DailyFrequencyCopyWithImpl<_DailyFrequency>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$DailyFrequencyToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _DailyFrequency&&(identical(other.date, date) || other.date == date)&&(identical(other.overallScore, overallScore) || other.overallScore == overallScore)&&const DeepCollectionEquality().equals(other._metrics, _metrics)&&const DeepCollectionEquality().equals(other._scores, _scores)&&const DeepCollectionEquality().equals(other._importantHours, _importantHours)&&const DeepCollectionEquality().equals(other._influences, _influences)&&const DeepCollectionEquality().equals(other._messageContext, _messageContext)&&(identical(other.timezone, timezone) || other.timezone == timezone)&&(identical(other.engineVersion, engineVersion) || other.engineVersion == engineVersion)&&(identical(other.scoringVersion, scoringVersion) || other.scoringVersion == scoringVersion)&&(identical(other.cached, cached) || other.cached == cached)&&const DeepCollectionEquality().equals(other._transits, _transits)&&(identical(other.moon, moon) || other.moon == moon)&&(identical(other.message, message) || other.message == message)&&const DeepCollectionEquality().equals(other._suggestedPrompts, _suggestedPrompts));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,date,overallScore,const DeepCollectionEquality().hash(_metrics),const DeepCollectionEquality().hash(_scores),const DeepCollectionEquality().hash(_importantHours),const DeepCollectionEquality().hash(_influences),const DeepCollectionEquality().hash(_messageContext),timezone,engineVersion,scoringVersion,cached,const DeepCollectionEquality().hash(_transits),moon,message,const DeepCollectionEquality().hash(_suggestedPrompts));

@override
String toString() {
  return 'DailyFrequency(date: $date, overallScore: $overallScore, metrics: $metrics, scores: $scores, importantHours: $importantHours, influences: $influences, messageContext: $messageContext, timezone: $timezone, engineVersion: $engineVersion, scoringVersion: $scoringVersion, cached: $cached, transits: $transits, moon: $moon, message: $message, suggestedPrompts: $suggestedPrompts)';
}


}

/// @nodoc
abstract mixin class _$DailyFrequencyCopyWith<$Res> implements $DailyFrequencyCopyWith<$Res> {
  factory _$DailyFrequencyCopyWith(_DailyFrequency value, $Res Function(_DailyFrequency) _then) = __$DailyFrequencyCopyWithImpl;
@override @useResult
$Res call({
 DateTime date, int overallScore, List<FrequencyMetric> metrics, List<AreaScore> scores, List<ImportantHour> importantHours, List<SourceFactor> influences, Map<String, dynamic> messageContext, String? timezone, String? engineVersion, String? scoringVersion, bool? cached, List<TransitSummary> transits, MoonPhaseSummary? moon, QuickInsight? message, List<String> suggestedPrompts
});


@override $MoonPhaseSummaryCopyWith<$Res>? get moon;@override $QuickInsightCopyWith<$Res>? get message;

}
/// @nodoc
class __$DailyFrequencyCopyWithImpl<$Res>
    implements _$DailyFrequencyCopyWith<$Res> {
  __$DailyFrequencyCopyWithImpl(this._self, this._then);

  final _DailyFrequency _self;
  final $Res Function(_DailyFrequency) _then;

/// Create a copy of DailyFrequency
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? date = null,Object? overallScore = null,Object? metrics = null,Object? scores = null,Object? importantHours = null,Object? influences = null,Object? messageContext = null,Object? timezone = freezed,Object? engineVersion = freezed,Object? scoringVersion = freezed,Object? cached = freezed,Object? transits = null,Object? moon = freezed,Object? message = freezed,Object? suggestedPrompts = null,}) {
  return _then(_DailyFrequency(
date: null == date ? _self.date : date // ignore: cast_nullable_to_non_nullable
as DateTime,overallScore: null == overallScore ? _self.overallScore : overallScore // ignore: cast_nullable_to_non_nullable
as int,metrics: null == metrics ? _self._metrics : metrics // ignore: cast_nullable_to_non_nullable
as List<FrequencyMetric>,scores: null == scores ? _self._scores : scores // ignore: cast_nullable_to_non_nullable
as List<AreaScore>,importantHours: null == importantHours ? _self._importantHours : importantHours // ignore: cast_nullable_to_non_nullable
as List<ImportantHour>,influences: null == influences ? _self._influences : influences // ignore: cast_nullable_to_non_nullable
as List<SourceFactor>,messageContext: null == messageContext ? _self._messageContext : messageContext // ignore: cast_nullable_to_non_nullable
as Map<String, dynamic>,timezone: freezed == timezone ? _self.timezone : timezone // ignore: cast_nullable_to_non_nullable
as String?,engineVersion: freezed == engineVersion ? _self.engineVersion : engineVersion // ignore: cast_nullable_to_non_nullable
as String?,scoringVersion: freezed == scoringVersion ? _self.scoringVersion : scoringVersion // ignore: cast_nullable_to_non_nullable
as String?,cached: freezed == cached ? _self.cached : cached // ignore: cast_nullable_to_non_nullable
as bool?,transits: null == transits ? _self._transits : transits // ignore: cast_nullable_to_non_nullable
as List<TransitSummary>,moon: freezed == moon ? _self.moon : moon // ignore: cast_nullable_to_non_nullable
as MoonPhaseSummary?,message: freezed == message ? _self.message : message // ignore: cast_nullable_to_non_nullable
as QuickInsight?,suggestedPrompts: null == suggestedPrompts ? _self._suggestedPrompts : suggestedPrompts // ignore: cast_nullable_to_non_nullable
as List<String>,
  ));
}

/// Create a copy of DailyFrequency
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$MoonPhaseSummaryCopyWith<$Res>? get moon {
    if (_self.moon == null) {
    return null;
  }

  return $MoonPhaseSummaryCopyWith<$Res>(_self.moon!, (value) {
    return _then(_self.copyWith(moon: value));
  });
}/// Create a copy of DailyFrequency
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$QuickInsightCopyWith<$Res>? get message {
    if (_self.message == null) {
    return null;
  }

  return $QuickInsightCopyWith<$Res>(_self.message!, (value) {
    return _then(_self.copyWith(message: value));
  });
}
}

// dart format on
