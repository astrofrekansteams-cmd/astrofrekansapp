// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'astro_ai_context.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$AstroAIContext {

 NatalChart get natalChart; List<Transit> get activeTransits; MoonPhase? get moon; DateTime? get generatedAt;
/// Create a copy of AstroAIContext
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$AstroAIContextCopyWith<AstroAIContext> get copyWith => _$AstroAIContextCopyWithImpl<AstroAIContext>(this as AstroAIContext, _$identity);

  /// Serializes this AstroAIContext to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is AstroAIContext&&(identical(other.natalChart, natalChart) || other.natalChart == natalChart)&&const DeepCollectionEquality().equals(other.activeTransits, activeTransits)&&(identical(other.moon, moon) || other.moon == moon)&&(identical(other.generatedAt, generatedAt) || other.generatedAt == generatedAt));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,natalChart,const DeepCollectionEquality().hash(activeTransits),moon,generatedAt);

@override
String toString() {
  return 'AstroAIContext(natalChart: $natalChart, activeTransits: $activeTransits, moon: $moon, generatedAt: $generatedAt)';
}


}

/// @nodoc
abstract mixin class $AstroAIContextCopyWith<$Res>  {
  factory $AstroAIContextCopyWith(AstroAIContext value, $Res Function(AstroAIContext) _then) = _$AstroAIContextCopyWithImpl;
@useResult
$Res call({
 NatalChart natalChart, List<Transit> activeTransits, MoonPhase? moon, DateTime? generatedAt
});


$NatalChartCopyWith<$Res> get natalChart;$MoonPhaseCopyWith<$Res>? get moon;

}
/// @nodoc
class _$AstroAIContextCopyWithImpl<$Res>
    implements $AstroAIContextCopyWith<$Res> {
  _$AstroAIContextCopyWithImpl(this._self, this._then);

  final AstroAIContext _self;
  final $Res Function(AstroAIContext) _then;

/// Create a copy of AstroAIContext
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? natalChart = null,Object? activeTransits = null,Object? moon = freezed,Object? generatedAt = freezed,}) {
  return _then(_self.copyWith(
natalChart: null == natalChart ? _self.natalChart : natalChart // ignore: cast_nullable_to_non_nullable
as NatalChart,activeTransits: null == activeTransits ? _self.activeTransits : activeTransits // ignore: cast_nullable_to_non_nullable
as List<Transit>,moon: freezed == moon ? _self.moon : moon // ignore: cast_nullable_to_non_nullable
as MoonPhase?,generatedAt: freezed == generatedAt ? _self.generatedAt : generatedAt // ignore: cast_nullable_to_non_nullable
as DateTime?,
  ));
}
/// Create a copy of AstroAIContext
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$NatalChartCopyWith<$Res> get natalChart {
  
  return $NatalChartCopyWith<$Res>(_self.natalChart, (value) {
    return _then(_self.copyWith(natalChart: value));
  });
}/// Create a copy of AstroAIContext
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$MoonPhaseCopyWith<$Res>? get moon {
    if (_self.moon == null) {
    return null;
  }

  return $MoonPhaseCopyWith<$Res>(_self.moon!, (value) {
    return _then(_self.copyWith(moon: value));
  });
}
}


/// Adds pattern-matching-related methods to [AstroAIContext].
extension AstroAIContextPatterns on AstroAIContext {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _AstroAIContext value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _AstroAIContext() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _AstroAIContext value)  $default,){
final _that = this;
switch (_that) {
case _AstroAIContext():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _AstroAIContext value)?  $default,){
final _that = this;
switch (_that) {
case _AstroAIContext() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( NatalChart natalChart,  List<Transit> activeTransits,  MoonPhase? moon,  DateTime? generatedAt)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _AstroAIContext() when $default != null:
return $default(_that.natalChart,_that.activeTransits,_that.moon,_that.generatedAt);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( NatalChart natalChart,  List<Transit> activeTransits,  MoonPhase? moon,  DateTime? generatedAt)  $default,) {final _that = this;
switch (_that) {
case _AstroAIContext():
return $default(_that.natalChart,_that.activeTransits,_that.moon,_that.generatedAt);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( NatalChart natalChart,  List<Transit> activeTransits,  MoonPhase? moon,  DateTime? generatedAt)?  $default,) {final _that = this;
switch (_that) {
case _AstroAIContext() when $default != null:
return $default(_that.natalChart,_that.activeTransits,_that.moon,_that.generatedAt);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _AstroAIContext implements AstroAIContext {
  const _AstroAIContext({required this.natalChart, final  List<Transit> activeTransits = const <Transit>[], this.moon, this.generatedAt}): _activeTransits = activeTransits;
  factory _AstroAIContext.fromJson(Map<String, dynamic> json) => _$AstroAIContextFromJson(json);

@override final  NatalChart natalChart;
 final  List<Transit> _activeTransits;
@override@JsonKey() List<Transit> get activeTransits {
  if (_activeTransits is EqualUnmodifiableListView) return _activeTransits;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_activeTransits);
}

@override final  MoonPhase? moon;
@override final  DateTime? generatedAt;

/// Create a copy of AstroAIContext
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$AstroAIContextCopyWith<_AstroAIContext> get copyWith => __$AstroAIContextCopyWithImpl<_AstroAIContext>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$AstroAIContextToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _AstroAIContext&&(identical(other.natalChart, natalChart) || other.natalChart == natalChart)&&const DeepCollectionEquality().equals(other._activeTransits, _activeTransits)&&(identical(other.moon, moon) || other.moon == moon)&&(identical(other.generatedAt, generatedAt) || other.generatedAt == generatedAt));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,natalChart,const DeepCollectionEquality().hash(_activeTransits),moon,generatedAt);

@override
String toString() {
  return 'AstroAIContext(natalChart: $natalChart, activeTransits: $activeTransits, moon: $moon, generatedAt: $generatedAt)';
}


}

/// @nodoc
abstract mixin class _$AstroAIContextCopyWith<$Res> implements $AstroAIContextCopyWith<$Res> {
  factory _$AstroAIContextCopyWith(_AstroAIContext value, $Res Function(_AstroAIContext) _then) = __$AstroAIContextCopyWithImpl;
@override @useResult
$Res call({
 NatalChart natalChart, List<Transit> activeTransits, MoonPhase? moon, DateTime? generatedAt
});


@override $NatalChartCopyWith<$Res> get natalChart;@override $MoonPhaseCopyWith<$Res>? get moon;

}
/// @nodoc
class __$AstroAIContextCopyWithImpl<$Res>
    implements _$AstroAIContextCopyWith<$Res> {
  __$AstroAIContextCopyWithImpl(this._self, this._then);

  final _AstroAIContext _self;
  final $Res Function(_AstroAIContext) _then;

/// Create a copy of AstroAIContext
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? natalChart = null,Object? activeTransits = null,Object? moon = freezed,Object? generatedAt = freezed,}) {
  return _then(_AstroAIContext(
natalChart: null == natalChart ? _self.natalChart : natalChart // ignore: cast_nullable_to_non_nullable
as NatalChart,activeTransits: null == activeTransits ? _self._activeTransits : activeTransits // ignore: cast_nullable_to_non_nullable
as List<Transit>,moon: freezed == moon ? _self.moon : moon // ignore: cast_nullable_to_non_nullable
as MoonPhase?,generatedAt: freezed == generatedAt ? _self.generatedAt : generatedAt // ignore: cast_nullable_to_non_nullable
as DateTime?,
  ));
}

/// Create a copy of AstroAIContext
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$NatalChartCopyWith<$Res> get natalChart {
  
  return $NatalChartCopyWith<$Res>(_self.natalChart, (value) {
    return _then(_self.copyWith(natalChart: value));
  });
}/// Create a copy of AstroAIContext
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$MoonPhaseCopyWith<$Res>? get moon {
    if (_self.moon == null) {
    return null;
  }

  return $MoonPhaseCopyWith<$Res>(_self.moon!, (value) {
    return _then(_self.copyWith(moon: value));
  });
}
}

// dart format on
