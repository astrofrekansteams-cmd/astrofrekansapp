// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'birth_data.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_BirthData _$BirthDataFromJson(Map<String, dynamic> json) => _BirthData(
  date: DateTime.parse(json['date'] as String),
  time: json['time'] as String?,
  place: json['place'] as String?,
  latitude: (json['latitude'] as num?)?.toDouble(),
  longitude: (json['longitude'] as num?)?.toDouble(),
  timezone: json['timezone'] as String?,
);

Map<String, dynamic> _$BirthDataToJson(_BirthData instance) =>
    <String, dynamic>{
      'date': instance.date.toIso8601String(),
      'time': ?instance.time,
      'place': ?instance.place,
      'latitude': ?instance.latitude,
      'longitude': ?instance.longitude,
      'timezone': ?instance.timezone,
    };
