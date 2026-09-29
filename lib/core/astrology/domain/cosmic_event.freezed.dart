// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'cosmic_event.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$CosmicEvent {

 String get id; CosmicEventType get type; String? get rawType;/// The moment the event peaks.
 DateTime get exactAt;/// Window for events that last (retrogrades, long transits).
 DateTime? get startAt; DateTime? get endAt; Planet? get planet; Planet? get secondaryPlanet; AspectType? get aspectType; String? get eclipseSubtype; double? get eclipseMagnitude; double? get nodeDistance; double? get longitude; int? get degree; Map<String, dynamic> get metadata; ZodiacSign? get sign; MoonPhaseType? get moonPhase;/// Natal house the event lands in, when the chart is known.
 int? get affectedHouse; String? get title; String? get description;/// Extra line explaining why it matters for this user.
 String? get personalNote; bool get isPersonal; String? get timezone;
/// Create a copy of CosmicEvent
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$CosmicEventCopyWith<CosmicEvent> get copyWith => _$CosmicEventCopyWithImpl<CosmicEvent>(this as CosmicEvent, _$identity);

  /// Serializes this CosmicEvent to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is CosmicEvent&&(identical(other.id, id) || other.id == id)&&(identical(other.type, type) || other.type == type)&&(identical(other.rawType, rawType) || other.rawType == rawType)&&(identical(other.exactAt, exactAt) || other.exactAt == exactAt)&&(identical(other.startAt, startAt) || other.startAt == startAt)&&(identical(other.endAt, endAt) || other.endAt == endAt)&&(identical(other.planet, planet) || other.planet == planet)&&(identical(other.secondaryPlanet, secondaryPlanet) || other.secondaryPlanet == secondaryPlanet)&&(identical(other.aspectType, aspectType) || other.aspectType == aspectType)&&(identical(other.eclipseSubtype, eclipseSubtype) || other.eclipseSubtype == eclipseSubtype)&&(identical(other.eclipseMagnitude, eclipseMagnitude) || other.eclipseMagnitude == eclipseMagnitude)&&(identical(other.nodeDistance, nodeDistance) || other.nodeDistance == nodeDistance)&&(identical(other.longitude, longitude) || other.longitude == longitude)&&(identical(other.degree, degree) || other.degree == degree)&&const DeepCollectionEquality().equals(other.metadata, metadata)&&(identical(other.sign, sign) || other.sign == sign)&&(identical(other.moonPhase, moonPhase) || other.moonPhase == moonPhase)&&(identical(other.affectedHouse, affectedHouse) || other.affectedHouse == affectedHouse)&&(identical(other.title, title) || other.title == title)&&(identical(other.description, description) || other.description == description)&&(identical(other.personalNote, personalNote) || other.personalNote == personalNote)&&(identical(other.isPersonal, isPersonal) || other.isPersonal == isPersonal)&&(identical(other.timezone, timezone) || other.timezone == timezone));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hashAll([runtimeType,id,type,rawType,exactAt,startAt,endAt,planet,secondaryPlanet,aspectType,eclipseSubtype,eclipseMagnitude,nodeDistance,longitude,degree,const DeepCollectionEquality().hash(metadata),sign,moonPhase,affectedHouse,title,description,personalNote,isPersonal,timezone]);

@override
String toString() {
  return 'CosmicEvent(id: $id, type: $type, rawType: $rawType, exactAt: $exactAt, startAt: $startAt, endAt: $endAt, planet: $planet, secondaryPlanet: $secondaryPlanet, aspectType: $aspectType, eclipseSubtype: $eclipseSubtype, eclipseMagnitude: $eclipseMagnitude, nodeDistance: $nodeDistance, longitude: $longitude, degree: $degree, metadata: $metadata, sign: $sign, moonPhase: $moonPhase, affectedHouse: $affectedHouse, title: $title, description: $description, personalNote: $personalNote, isPersonal: $isPersonal, timezone: $timezone)';
}


}

/// @nodoc
abstract mixin class $CosmicEventCopyWith<$Res>  {
  factory $CosmicEventCopyWith(CosmicEvent value, $Res Function(CosmicEvent) _then) = _$CosmicEventCopyWithImpl;
@useResult
$Res call({
 String id, CosmicEventType type, String? rawType, DateTime exactAt, DateTime? startAt, DateTime? endAt, Planet? planet, Planet? secondaryPlanet, AspectType? aspectType, String? eclipseSubtype, double? eclipseMagnitude, double? nodeDistance, double? longitude, int? degree, Map<String, dynamic> metadata, ZodiacSign? sign, MoonPhaseType? moonPhase, int? affectedHouse, String? title, String? description, String? personalNote, bool isPersonal, String? timezone
});




}
/// @nodoc
class _$CosmicEventCopyWithImpl<$Res>
    implements $CosmicEventCopyWith<$Res> {
  _$CosmicEventCopyWithImpl(this._self, this._then);

  final CosmicEvent _self;
  final $Res Function(CosmicEvent) _then;

/// Create a copy of CosmicEvent
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? id = null,Object? type = null,Object? rawType = freezed,Object? exactAt = null,Object? startAt = freezed,Object? endAt = freezed,Object? planet = freezed,Object? secondaryPlanet = freezed,Object? aspectType = freezed,Object? eclipseSubtype = freezed,Object? eclipseMagnitude = freezed,Object? nodeDistance = freezed,Object? longitude = freezed,Object? degree = freezed,Object? metadata = null,Object? sign = freezed,Object? moonPhase = freezed,Object? affectedHouse = freezed,Object? title = freezed,Object? description = freezed,Object? personalNote = freezed,Object? isPersonal = null,Object? timezone = freezed,}) {
  return _then(_self.copyWith(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,type: null == type ? _self.type : type // ignore: cast_nullable_to_non_nullable
as CosmicEventType,rawType: freezed == rawType ? _self.rawType : rawType // ignore: cast_nullable_to_non_nullable
as String?,exactAt: null == exactAt ? _self.exactAt : exactAt // ignore: cast_nullable_to_non_nullable
as DateTime,startAt: freezed == startAt ? _self.startAt : startAt // ignore: cast_nullable_to_non_nullable
as DateTime?,endAt: freezed == endAt ? _self.endAt : endAt // ignore: cast_nullable_to_non_nullable
as DateTime?,planet: freezed == planet ? _self.planet : planet // ignore: cast_nullable_to_non_nullable
as Planet?,secondaryPlanet: freezed == secondaryPlanet ? _self.secondaryPlanet : secondaryPlanet // ignore: cast_nullable_to_non_nullable
as Planet?,aspectType: freezed == aspectType ? _self.aspectType : aspectType // ignore: cast_nullable_to_non_nullable
as AspectType?,eclipseSubtype: freezed == eclipseSubtype ? _self.eclipseSubtype : eclipseSubtype // ignore: cast_nullable_to_non_nullable
as String?,eclipseMagnitude: freezed == eclipseMagnitude ? _self.eclipseMagnitude : eclipseMagnitude // ignore: cast_nullable_to_non_nullable
as double?,nodeDistance: freezed == nodeDistance ? _self.nodeDistance : nodeDistance // ignore: cast_nullable_to_non_nullable
as double?,longitude: freezed == longitude ? _self.longitude : longitude // ignore: cast_nullable_to_non_nullable
as double?,degree: freezed == degree ? _self.degree : degree // ignore: cast_nullable_to_non_nullable
as int?,metadata: null == metadata ? _self.metadata : metadata // ignore: cast_nullable_to_non_nullable
as Map<String, dynamic>,sign: freezed == sign ? _self.sign : sign // ignore: cast_nullable_to_non_nullable
as ZodiacSign?,moonPhase: freezed == moonPhase ? _self.moonPhase : moonPhase // ignore: cast_nullable_to_non_nullable
as MoonPhaseType?,affectedHouse: freezed == affectedHouse ? _self.affectedHouse : affectedHouse // ignore: cast_nullable_to_non_nullable
as int?,title: freezed == title ? _self.title : title // ignore: cast_nullable_to_non_nullable
as String?,description: freezed == description ? _self.description : description // ignore: cast_nullable_to_non_nullable
as String?,personalNote: freezed == personalNote ? _self.personalNote : personalNote // ignore: cast_nullable_to_non_nullable
as String?,isPersonal: null == isPersonal ? _self.isPersonal : isPersonal // ignore: cast_nullable_to_non_nullable
as bool,timezone: freezed == timezone ? _self.timezone : timezone // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

}


/// Adds pattern-matching-related methods to [CosmicEvent].
extension CosmicEventPatterns on CosmicEvent {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _CosmicEvent value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _CosmicEvent() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _CosmicEvent value)  $default,){
final _that = this;
switch (_that) {
case _CosmicEvent():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _CosmicEvent value)?  $default,){
final _that = this;
switch (_that) {
case _CosmicEvent() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String id,  CosmicEventType type,  String? rawType,  DateTime exactAt,  DateTime? startAt,  DateTime? endAt,  Planet? planet,  Planet? secondaryPlanet,  AspectType? aspectType,  String? eclipseSubtype,  double? eclipseMagnitude,  double? nodeDistance,  double? longitude,  int? degree,  Map<String, dynamic> metadata,  ZodiacSign? sign,  MoonPhaseType? moonPhase,  int? affectedHouse,  String? title,  String? description,  String? personalNote,  bool isPersonal,  String? timezone)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _CosmicEvent() when $default != null:
return $default(_that.id,_that.type,_that.rawType,_that.exactAt,_that.startAt,_that.endAt,_that.planet,_that.secondaryPlanet,_that.aspectType,_that.eclipseSubtype,_that.eclipseMagnitude,_that.nodeDistance,_that.longitude,_that.degree,_that.metadata,_that.sign,_that.moonPhase,_that.affectedHouse,_that.title,_that.description,_that.personalNote,_that.isPersonal,_that.timezone);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String id,  CosmicEventType type,  String? rawType,  DateTime exactAt,  DateTime? startAt,  DateTime? endAt,  Planet? planet,  Planet? secondaryPlanet,  AspectType? aspectType,  String? eclipseSubtype,  double? eclipseMagnitude,  double? nodeDistance,  double? longitude,  int? degree,  Map<String, dynamic> metadata,  ZodiacSign? sign,  MoonPhaseType? moonPhase,  int? affectedHouse,  String? title,  String? description,  String? personalNote,  bool isPersonal,  String? timezone)  $default,) {final _that = this;
switch (_that) {
case _CosmicEvent():
return $default(_that.id,_that.type,_that.rawType,_that.exactAt,_that.startAt,_that.endAt,_that.planet,_that.secondaryPlanet,_that.aspectType,_that.eclipseSubtype,_that.eclipseMagnitude,_that.nodeDistance,_that.longitude,_that.degree,_that.metadata,_that.sign,_that.moonPhase,_that.affectedHouse,_that.title,_that.description,_that.personalNote,_that.isPersonal,_that.timezone);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String id,  CosmicEventType type,  String? rawType,  DateTime exactAt,  DateTime? startAt,  DateTime? endAt,  Planet? planet,  Planet? secondaryPlanet,  AspectType? aspectType,  String? eclipseSubtype,  double? eclipseMagnitude,  double? nodeDistance,  double? longitude,  int? degree,  Map<String, dynamic> metadata,  ZodiacSign? sign,  MoonPhaseType? moonPhase,  int? affectedHouse,  String? title,  String? description,  String? personalNote,  bool isPersonal,  String? timezone)?  $default,) {final _that = this;
switch (_that) {
case _CosmicEvent() when $default != null:
return $default(_that.id,_that.type,_that.rawType,_that.exactAt,_that.startAt,_that.endAt,_that.planet,_that.secondaryPlanet,_that.aspectType,_that.eclipseSubtype,_that.eclipseMagnitude,_that.nodeDistance,_that.longitude,_that.degree,_that.metadata,_that.sign,_that.moonPhase,_that.affectedHouse,_that.title,_that.description,_that.personalNote,_that.isPersonal,_that.timezone);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _CosmicEvent extends CosmicEvent {
  const _CosmicEvent({required this.id, required this.type, this.rawType, required this.exactAt, this.startAt, this.endAt, this.planet, this.secondaryPlanet, this.aspectType, this.eclipseSubtype, this.eclipseMagnitude, this.nodeDistance, this.longitude, this.degree, final  Map<String, dynamic> metadata = const <String, dynamic>{}, this.sign, this.moonPhase, this.affectedHouse, this.title, this.description, this.personalNote, this.isPersonal = false, this.timezone}): _metadata = metadata,super._();
  factory _CosmicEvent.fromJson(Map<String, dynamic> json) => _$CosmicEventFromJson(json);

@override final  String id;
@override final  CosmicEventType type;
@override final  String? rawType;
/// The moment the event peaks.
@override final  DateTime exactAt;
/// Window for events that last (retrogrades, long transits).
@override final  DateTime? startAt;
@override final  DateTime? endAt;
@override final  Planet? planet;
@override final  Planet? secondaryPlanet;
@override final  AspectType? aspectType;
@override final  String? eclipseSubtype;
@override final  double? eclipseMagnitude;
@override final  double? nodeDistance;
@override final  double? longitude;
@override final  int? degree;
 final  Map<String, dynamic> _metadata;
@override@JsonKey() Map<String, dynamic> get metadata {
  if (_metadata is EqualUnmodifiableMapView) return _metadata;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableMapView(_metadata);
}

@override final  ZodiacSign? sign;
@override final  MoonPhaseType? moonPhase;
/// Natal house the event lands in, when the chart is known.
@override final  int? affectedHouse;
@override final  String? title;
@override final  String? description;
/// Extra line explaining why it matters for this user.
@override final  String? personalNote;
@override@JsonKey() final  bool isPersonal;
@override final  String? timezone;

/// Create a copy of CosmicEvent
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$CosmicEventCopyWith<_CosmicEvent> get copyWith => __$CosmicEventCopyWithImpl<_CosmicEvent>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$CosmicEventToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _CosmicEvent&&(identical(other.id, id) || other.id == id)&&(identical(other.type, type) || other.type == type)&&(identical(other.rawType, rawType) || other.rawType == rawType)&&(identical(other.exactAt, exactAt) || other.exactAt == exactAt)&&(identical(other.startAt, startAt) || other.startAt == startAt)&&(identical(other.endAt, endAt) || other.endAt == endAt)&&(identical(other.planet, planet) || other.planet == planet)&&(identical(other.secondaryPlanet, secondaryPlanet) || other.secondaryPlanet == secondaryPlanet)&&(identical(other.aspectType, aspectType) || other.aspectType == aspectType)&&(identical(other.eclipseSubtype, eclipseSubtype) || other.eclipseSubtype == eclipseSubtype)&&(identical(other.eclipseMagnitude, eclipseMagnitude) || other.eclipseMagnitude == eclipseMagnitude)&&(identical(other.nodeDistance, nodeDistance) || other.nodeDistance == nodeDistance)&&(identical(other.longitude, longitude) || other.longitude == longitude)&&(identical(other.degree, degree) || other.degree == degree)&&const DeepCollectionEquality().equals(other._metadata, _metadata)&&(identical(other.sign, sign) || other.sign == sign)&&(identical(other.moonPhase, moonPhase) || other.moonPhase == moonPhase)&&(identical(other.affectedHouse, affectedHouse) || other.affectedHouse == affectedHouse)&&(identical(other.title, title) || other.title == title)&&(identical(other.description, description) || other.description == description)&&(identical(other.personalNote, personalNote) || other.personalNote == personalNote)&&(identical(other.isPersonal, isPersonal) || other.isPersonal == isPersonal)&&(identical(other.timezone, timezone) || other.timezone == timezone));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hashAll([runtimeType,id,type,rawType,exactAt,startAt,endAt,planet,secondaryPlanet,aspectType,eclipseSubtype,eclipseMagnitude,nodeDistance,longitude,degree,const DeepCollectionEquality().hash(_metadata),sign,moonPhase,affectedHouse,title,description,personalNote,isPersonal,timezone]);

@override
String toString() {
  return 'CosmicEvent(id: $id, type: $type, rawType: $rawType, exactAt: $exactAt, startAt: $startAt, endAt: $endAt, planet: $planet, secondaryPlanet: $secondaryPlanet, aspectType: $aspectType, eclipseSubtype: $eclipseSubtype, eclipseMagnitude: $eclipseMagnitude, nodeDistance: $nodeDistance, longitude: $longitude, degree: $degree, metadata: $metadata, sign: $sign, moonPhase: $moonPhase, affectedHouse: $affectedHouse, title: $title, description: $description, personalNote: $personalNote, isPersonal: $isPersonal, timezone: $timezone)';
}


}

/// @nodoc
abstract mixin class _$CosmicEventCopyWith<$Res> implements $CosmicEventCopyWith<$Res> {
  factory _$CosmicEventCopyWith(_CosmicEvent value, $Res Function(_CosmicEvent) _then) = __$CosmicEventCopyWithImpl;
@override @useResult
$Res call({
 String id, CosmicEventType type, String? rawType, DateTime exactAt, DateTime? startAt, DateTime? endAt, Planet? planet, Planet? secondaryPlanet, AspectType? aspectType, String? eclipseSubtype, double? eclipseMagnitude, double? nodeDistance, double? longitude, int? degree, Map<String, dynamic> metadata, ZodiacSign? sign, MoonPhaseType? moonPhase, int? affectedHouse, String? title, String? description, String? personalNote, bool isPersonal, String? timezone
});




}
/// @nodoc
class __$CosmicEventCopyWithImpl<$Res>
    implements _$CosmicEventCopyWith<$Res> {
  __$CosmicEventCopyWithImpl(this._self, this._then);

  final _CosmicEvent _self;
  final $Res Function(_CosmicEvent) _then;

/// Create a copy of CosmicEvent
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? id = null,Object? type = null,Object? rawType = freezed,Object? exactAt = null,Object? startAt = freezed,Object? endAt = freezed,Object? planet = freezed,Object? secondaryPlanet = freezed,Object? aspectType = freezed,Object? eclipseSubtype = freezed,Object? eclipseMagnitude = freezed,Object? nodeDistance = freezed,Object? longitude = freezed,Object? degree = freezed,Object? metadata = null,Object? sign = freezed,Object? moonPhase = freezed,Object? affectedHouse = freezed,Object? title = freezed,Object? description = freezed,Object? personalNote = freezed,Object? isPersonal = null,Object? timezone = freezed,}) {
  return _then(_CosmicEvent(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,type: null == type ? _self.type : type // ignore: cast_nullable_to_non_nullable
as CosmicEventType,rawType: freezed == rawType ? _self.rawType : rawType // ignore: cast_nullable_to_non_nullable
as String?,exactAt: null == exactAt ? _self.exactAt : exactAt // ignore: cast_nullable_to_non_nullable
as DateTime,startAt: freezed == startAt ? _self.startAt : startAt // ignore: cast_nullable_to_non_nullable
as DateTime?,endAt: freezed == endAt ? _self.endAt : endAt // ignore: cast_nullable_to_non_nullable
as DateTime?,planet: freezed == planet ? _self.planet : planet // ignore: cast_nullable_to_non_nullable
as Planet?,secondaryPlanet: freezed == secondaryPlanet ? _self.secondaryPlanet : secondaryPlanet // ignore: cast_nullable_to_non_nullable
as Planet?,aspectType: freezed == aspectType ? _self.aspectType : aspectType // ignore: cast_nullable_to_non_nullable
as AspectType?,eclipseSubtype: freezed == eclipseSubtype ? _self.eclipseSubtype : eclipseSubtype // ignore: cast_nullable_to_non_nullable
as String?,eclipseMagnitude: freezed == eclipseMagnitude ? _self.eclipseMagnitude : eclipseMagnitude // ignore: cast_nullable_to_non_nullable
as double?,nodeDistance: freezed == nodeDistance ? _self.nodeDistance : nodeDistance // ignore: cast_nullable_to_non_nullable
as double?,longitude: freezed == longitude ? _self.longitude : longitude // ignore: cast_nullable_to_non_nullable
as double?,degree: freezed == degree ? _self.degree : degree // ignore: cast_nullable_to_non_nullable
as int?,metadata: null == metadata ? _self._metadata : metadata // ignore: cast_nullable_to_non_nullable
as Map<String, dynamic>,sign: freezed == sign ? _self.sign : sign // ignore: cast_nullable_to_non_nullable
as ZodiacSign?,moonPhase: freezed == moonPhase ? _self.moonPhase : moonPhase // ignore: cast_nullable_to_non_nullable
as MoonPhaseType?,affectedHouse: freezed == affectedHouse ? _self.affectedHouse : affectedHouse // ignore: cast_nullable_to_non_nullable
as int?,title: freezed == title ? _self.title : title // ignore: cast_nullable_to_non_nullable
as String?,description: freezed == description ? _self.description : description // ignore: cast_nullable_to_non_nullable
as String?,personalNote: freezed == personalNote ? _self.personalNote : personalNote // ignore: cast_nullable_to_non_nullable
as String?,isPersonal: null == isPersonal ? _self.isPersonal : isPersonal // ignore: cast_nullable_to_non_nullable
as bool,timezone: freezed == timezone ? _self.timezone : timezone // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}


}

// dart format on
