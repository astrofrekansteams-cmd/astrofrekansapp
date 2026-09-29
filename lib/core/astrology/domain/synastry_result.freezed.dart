// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'synastry_result.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$CompatibilityScore {

 CompatibilityArea get area; int get score; String? get note;
/// Create a copy of CompatibilityScore
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$CompatibilityScoreCopyWith<CompatibilityScore> get copyWith => _$CompatibilityScoreCopyWithImpl<CompatibilityScore>(this as CompatibilityScore, _$identity);

  /// Serializes this CompatibilityScore to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is CompatibilityScore&&(identical(other.area, area) || other.area == area)&&(identical(other.score, score) || other.score == score)&&(identical(other.note, note) || other.note == note));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,area,score,note);

@override
String toString() {
  return 'CompatibilityScore(area: $area, score: $score, note: $note)';
}


}

/// @nodoc
abstract mixin class $CompatibilityScoreCopyWith<$Res>  {
  factory $CompatibilityScoreCopyWith(CompatibilityScore value, $Res Function(CompatibilityScore) _then) = _$CompatibilityScoreCopyWithImpl;
@useResult
$Res call({
 CompatibilityArea area, int score, String? note
});




}
/// @nodoc
class _$CompatibilityScoreCopyWithImpl<$Res>
    implements $CompatibilityScoreCopyWith<$Res> {
  _$CompatibilityScoreCopyWithImpl(this._self, this._then);

  final CompatibilityScore _self;
  final $Res Function(CompatibilityScore) _then;

/// Create a copy of CompatibilityScore
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? area = null,Object? score = null,Object? note = freezed,}) {
  return _then(_self.copyWith(
area: null == area ? _self.area : area // ignore: cast_nullable_to_non_nullable
as CompatibilityArea,score: null == score ? _self.score : score // ignore: cast_nullable_to_non_nullable
as int,note: freezed == note ? _self.note : note // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

}


/// Adds pattern-matching-related methods to [CompatibilityScore].
extension CompatibilityScorePatterns on CompatibilityScore {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _CompatibilityScore value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _CompatibilityScore() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _CompatibilityScore value)  $default,){
final _that = this;
switch (_that) {
case _CompatibilityScore():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _CompatibilityScore value)?  $default,){
final _that = this;
switch (_that) {
case _CompatibilityScore() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( CompatibilityArea area,  int score,  String? note)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _CompatibilityScore() when $default != null:
return $default(_that.area,_that.score,_that.note);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( CompatibilityArea area,  int score,  String? note)  $default,) {final _that = this;
switch (_that) {
case _CompatibilityScore():
return $default(_that.area,_that.score,_that.note);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( CompatibilityArea area,  int score,  String? note)?  $default,) {final _that = this;
switch (_that) {
case _CompatibilityScore() when $default != null:
return $default(_that.area,_that.score,_that.note);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _CompatibilityScore implements CompatibilityScore {
  const _CompatibilityScore({required this.area, required this.score, this.note});
  factory _CompatibilityScore.fromJson(Map<String, dynamic> json) => _$CompatibilityScoreFromJson(json);

@override final  CompatibilityArea area;
@override final  int score;
@override final  String? note;

/// Create a copy of CompatibilityScore
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$CompatibilityScoreCopyWith<_CompatibilityScore> get copyWith => __$CompatibilityScoreCopyWithImpl<_CompatibilityScore>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$CompatibilityScoreToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _CompatibilityScore&&(identical(other.area, area) || other.area == area)&&(identical(other.score, score) || other.score == score)&&(identical(other.note, note) || other.note == note));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,area,score,note);

@override
String toString() {
  return 'CompatibilityScore(area: $area, score: $score, note: $note)';
}


}

/// @nodoc
abstract mixin class _$CompatibilityScoreCopyWith<$Res> implements $CompatibilityScoreCopyWith<$Res> {
  factory _$CompatibilityScoreCopyWith(_CompatibilityScore value, $Res Function(_CompatibilityScore) _then) = __$CompatibilityScoreCopyWithImpl;
@override @useResult
$Res call({
 CompatibilityArea area, int score, String? note
});




}
/// @nodoc
class __$CompatibilityScoreCopyWithImpl<$Res>
    implements _$CompatibilityScoreCopyWith<$Res> {
  __$CompatibilityScoreCopyWithImpl(this._self, this._then);

  final _CompatibilityScore _self;
  final $Res Function(_CompatibilityScore) _then;

/// Create a copy of CompatibilityScore
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? area = null,Object? score = null,Object? note = freezed,}) {
  return _then(_CompatibilityScore(
area: null == area ? _self.area : area // ignore: cast_nullable_to_non_nullable
as CompatibilityArea,score: null == score ? _self.score : score // ignore: cast_nullable_to_non_nullable
as int,note: freezed == note ? _self.note : note // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}


}


/// @nodoc
mixin _$SynastryAspect {

 Planet get personAPlanet; Planet get personBPlanet; AspectType get type; double get orb; InfluenceNature get nature;
/// Create a copy of SynastryAspect
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$SynastryAspectCopyWith<SynastryAspect> get copyWith => _$SynastryAspectCopyWithImpl<SynastryAspect>(this as SynastryAspect, _$identity);

  /// Serializes this SynastryAspect to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is SynastryAspect&&(identical(other.personAPlanet, personAPlanet) || other.personAPlanet == personAPlanet)&&(identical(other.personBPlanet, personBPlanet) || other.personBPlanet == personBPlanet)&&(identical(other.type, type) || other.type == type)&&(identical(other.orb, orb) || other.orb == orb)&&(identical(other.nature, nature) || other.nature == nature));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,personAPlanet,personBPlanet,type,orb,nature);

@override
String toString() {
  return 'SynastryAspect(personAPlanet: $personAPlanet, personBPlanet: $personBPlanet, type: $type, orb: $orb, nature: $nature)';
}


}

/// @nodoc
abstract mixin class $SynastryAspectCopyWith<$Res>  {
  factory $SynastryAspectCopyWith(SynastryAspect value, $Res Function(SynastryAspect) _then) = _$SynastryAspectCopyWithImpl;
@useResult
$Res call({
 Planet personAPlanet, Planet personBPlanet, AspectType type, double orb, InfluenceNature nature
});




}
/// @nodoc
class _$SynastryAspectCopyWithImpl<$Res>
    implements $SynastryAspectCopyWith<$Res> {
  _$SynastryAspectCopyWithImpl(this._self, this._then);

  final SynastryAspect _self;
  final $Res Function(SynastryAspect) _then;

/// Create a copy of SynastryAspect
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? personAPlanet = null,Object? personBPlanet = null,Object? type = null,Object? orb = null,Object? nature = null,}) {
  return _then(_self.copyWith(
personAPlanet: null == personAPlanet ? _self.personAPlanet : personAPlanet // ignore: cast_nullable_to_non_nullable
as Planet,personBPlanet: null == personBPlanet ? _self.personBPlanet : personBPlanet // ignore: cast_nullable_to_non_nullable
as Planet,type: null == type ? _self.type : type // ignore: cast_nullable_to_non_nullable
as AspectType,orb: null == orb ? _self.orb : orb // ignore: cast_nullable_to_non_nullable
as double,nature: null == nature ? _self.nature : nature // ignore: cast_nullable_to_non_nullable
as InfluenceNature,
  ));
}

}


/// Adds pattern-matching-related methods to [SynastryAspect].
extension SynastryAspectPatterns on SynastryAspect {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _SynastryAspect value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _SynastryAspect() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _SynastryAspect value)  $default,){
final _that = this;
switch (_that) {
case _SynastryAspect():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _SynastryAspect value)?  $default,){
final _that = this;
switch (_that) {
case _SynastryAspect() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( Planet personAPlanet,  Planet personBPlanet,  AspectType type,  double orb,  InfluenceNature nature)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _SynastryAspect() when $default != null:
return $default(_that.personAPlanet,_that.personBPlanet,_that.type,_that.orb,_that.nature);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( Planet personAPlanet,  Planet personBPlanet,  AspectType type,  double orb,  InfluenceNature nature)  $default,) {final _that = this;
switch (_that) {
case _SynastryAspect():
return $default(_that.personAPlanet,_that.personBPlanet,_that.type,_that.orb,_that.nature);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( Planet personAPlanet,  Planet personBPlanet,  AspectType type,  double orb,  InfluenceNature nature)?  $default,) {final _that = this;
switch (_that) {
case _SynastryAspect() when $default != null:
return $default(_that.personAPlanet,_that.personBPlanet,_that.type,_that.orb,_that.nature);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _SynastryAspect implements SynastryAspect {
  const _SynastryAspect({required this.personAPlanet, required this.personBPlanet, required this.type, required this.orb, this.nature = InfluenceNature.neutral});
  factory _SynastryAspect.fromJson(Map<String, dynamic> json) => _$SynastryAspectFromJson(json);

@override final  Planet personAPlanet;
@override final  Planet personBPlanet;
@override final  AspectType type;
@override final  double orb;
@override@JsonKey() final  InfluenceNature nature;

/// Create a copy of SynastryAspect
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$SynastryAspectCopyWith<_SynastryAspect> get copyWith => __$SynastryAspectCopyWithImpl<_SynastryAspect>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$SynastryAspectToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _SynastryAspect&&(identical(other.personAPlanet, personAPlanet) || other.personAPlanet == personAPlanet)&&(identical(other.personBPlanet, personBPlanet) || other.personBPlanet == personBPlanet)&&(identical(other.type, type) || other.type == type)&&(identical(other.orb, orb) || other.orb == orb)&&(identical(other.nature, nature) || other.nature == nature));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,personAPlanet,personBPlanet,type,orb,nature);

@override
String toString() {
  return 'SynastryAspect(personAPlanet: $personAPlanet, personBPlanet: $personBPlanet, type: $type, orb: $orb, nature: $nature)';
}


}

/// @nodoc
abstract mixin class _$SynastryAspectCopyWith<$Res> implements $SynastryAspectCopyWith<$Res> {
  factory _$SynastryAspectCopyWith(_SynastryAspect value, $Res Function(_SynastryAspect) _then) = __$SynastryAspectCopyWithImpl;
@override @useResult
$Res call({
 Planet personAPlanet, Planet personBPlanet, AspectType type, double orb, InfluenceNature nature
});




}
/// @nodoc
class __$SynastryAspectCopyWithImpl<$Res>
    implements _$SynastryAspectCopyWith<$Res> {
  __$SynastryAspectCopyWithImpl(this._self, this._then);

  final _SynastryAspect _self;
  final $Res Function(_SynastryAspect) _then;

/// Create a copy of SynastryAspect
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? personAPlanet = null,Object? personBPlanet = null,Object? type = null,Object? orb = null,Object? nature = null,}) {
  return _then(_SynastryAspect(
personAPlanet: null == personAPlanet ? _self.personAPlanet : personAPlanet // ignore: cast_nullable_to_non_nullable
as Planet,personBPlanet: null == personBPlanet ? _self.personBPlanet : personBPlanet // ignore: cast_nullable_to_non_nullable
as Planet,type: null == type ? _self.type : type // ignore: cast_nullable_to_non_nullable
as AspectType,orb: null == orb ? _self.orb : orb // ignore: cast_nullable_to_non_nullable
as double,nature: null == nature ? _self.nature : nature // ignore: cast_nullable_to_non_nullable
as InfluenceNature,
  ));
}


}


/// @nodoc
mixin _$SynastryResult {

 CompatibilityMode get mode; List<CompatibilityScore> get scores; List<SynastryAspect> get aspects; String? get summary;
/// Create a copy of SynastryResult
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$SynastryResultCopyWith<SynastryResult> get copyWith => _$SynastryResultCopyWithImpl<SynastryResult>(this as SynastryResult, _$identity);

  /// Serializes this SynastryResult to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is SynastryResult&&(identical(other.mode, mode) || other.mode == mode)&&const DeepCollectionEquality().equals(other.scores, scores)&&const DeepCollectionEquality().equals(other.aspects, aspects)&&(identical(other.summary, summary) || other.summary == summary));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,mode,const DeepCollectionEquality().hash(scores),const DeepCollectionEquality().hash(aspects),summary);

@override
String toString() {
  return 'SynastryResult(mode: $mode, scores: $scores, aspects: $aspects, summary: $summary)';
}


}

/// @nodoc
abstract mixin class $SynastryResultCopyWith<$Res>  {
  factory $SynastryResultCopyWith(SynastryResult value, $Res Function(SynastryResult) _then) = _$SynastryResultCopyWithImpl;
@useResult
$Res call({
 CompatibilityMode mode, List<CompatibilityScore> scores, List<SynastryAspect> aspects, String? summary
});




}
/// @nodoc
class _$SynastryResultCopyWithImpl<$Res>
    implements $SynastryResultCopyWith<$Res> {
  _$SynastryResultCopyWithImpl(this._self, this._then);

  final SynastryResult _self;
  final $Res Function(SynastryResult) _then;

/// Create a copy of SynastryResult
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? mode = null,Object? scores = null,Object? aspects = null,Object? summary = freezed,}) {
  return _then(_self.copyWith(
mode: null == mode ? _self.mode : mode // ignore: cast_nullable_to_non_nullable
as CompatibilityMode,scores: null == scores ? _self.scores : scores // ignore: cast_nullable_to_non_nullable
as List<CompatibilityScore>,aspects: null == aspects ? _self.aspects : aspects // ignore: cast_nullable_to_non_nullable
as List<SynastryAspect>,summary: freezed == summary ? _self.summary : summary // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

}


/// Adds pattern-matching-related methods to [SynastryResult].
extension SynastryResultPatterns on SynastryResult {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _SynastryResult value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _SynastryResult() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _SynastryResult value)  $default,){
final _that = this;
switch (_that) {
case _SynastryResult():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _SynastryResult value)?  $default,){
final _that = this;
switch (_that) {
case _SynastryResult() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( CompatibilityMode mode,  List<CompatibilityScore> scores,  List<SynastryAspect> aspects,  String? summary)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _SynastryResult() when $default != null:
return $default(_that.mode,_that.scores,_that.aspects,_that.summary);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( CompatibilityMode mode,  List<CompatibilityScore> scores,  List<SynastryAspect> aspects,  String? summary)  $default,) {final _that = this;
switch (_that) {
case _SynastryResult():
return $default(_that.mode,_that.scores,_that.aspects,_that.summary);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( CompatibilityMode mode,  List<CompatibilityScore> scores,  List<SynastryAspect> aspects,  String? summary)?  $default,) {final _that = this;
switch (_that) {
case _SynastryResult() when $default != null:
return $default(_that.mode,_that.scores,_that.aspects,_that.summary);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _SynastryResult implements SynastryResult {
  const _SynastryResult({required this.mode, required final  List<CompatibilityScore> scores, final  List<SynastryAspect> aspects = const <SynastryAspect>[], this.summary}): _scores = scores,_aspects = aspects;
  factory _SynastryResult.fromJson(Map<String, dynamic> json) => _$SynastryResultFromJson(json);

@override final  CompatibilityMode mode;
 final  List<CompatibilityScore> _scores;
@override List<CompatibilityScore> get scores {
  if (_scores is EqualUnmodifiableListView) return _scores;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_scores);
}

 final  List<SynastryAspect> _aspects;
@override@JsonKey() List<SynastryAspect> get aspects {
  if (_aspects is EqualUnmodifiableListView) return _aspects;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_aspects);
}

@override final  String? summary;

/// Create a copy of SynastryResult
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$SynastryResultCopyWith<_SynastryResult> get copyWith => __$SynastryResultCopyWithImpl<_SynastryResult>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$SynastryResultToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _SynastryResult&&(identical(other.mode, mode) || other.mode == mode)&&const DeepCollectionEquality().equals(other._scores, _scores)&&const DeepCollectionEquality().equals(other._aspects, _aspects)&&(identical(other.summary, summary) || other.summary == summary));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,mode,const DeepCollectionEquality().hash(_scores),const DeepCollectionEquality().hash(_aspects),summary);

@override
String toString() {
  return 'SynastryResult(mode: $mode, scores: $scores, aspects: $aspects, summary: $summary)';
}


}

/// @nodoc
abstract mixin class _$SynastryResultCopyWith<$Res> implements $SynastryResultCopyWith<$Res> {
  factory _$SynastryResultCopyWith(_SynastryResult value, $Res Function(_SynastryResult) _then) = __$SynastryResultCopyWithImpl;
@override @useResult
$Res call({
 CompatibilityMode mode, List<CompatibilityScore> scores, List<SynastryAspect> aspects, String? summary
});




}
/// @nodoc
class __$SynastryResultCopyWithImpl<$Res>
    implements _$SynastryResultCopyWith<$Res> {
  __$SynastryResultCopyWithImpl(this._self, this._then);

  final _SynastryResult _self;
  final $Res Function(_SynastryResult) _then;

/// Create a copy of SynastryResult
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? mode = null,Object? scores = null,Object? aspects = null,Object? summary = freezed,}) {
  return _then(_SynastryResult(
mode: null == mode ? _self.mode : mode // ignore: cast_nullable_to_non_nullable
as CompatibilityMode,scores: null == scores ? _self._scores : scores // ignore: cast_nullable_to_non_nullable
as List<CompatibilityScore>,aspects: null == aspects ? _self._aspects : aspects // ignore: cast_nullable_to_non_nullable
as List<SynastryAspect>,summary: freezed == summary ? _self.summary : summary // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}


}

// dart format on
