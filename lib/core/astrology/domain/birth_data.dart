import 'package:freezed_annotation/freezed_annotation.dart';

part 'birth_data.freezed.dart';
part 'birth_data.g.dart';

/// Everything the astrology engine needs to erect a chart.
///
/// [time] is `HH:mm` local time and may be null when the user does not know it
/// (the engine then falls back to a solar chart). [latitude]/[longitude]/
/// [timezone] are resolved from [place] by the backend geocoder; they stay null
/// until then.
@freezed
abstract class BirthData with _$BirthData {
  const factory BirthData({
    required DateTime date,
    String? time,
    String? place,
    double? latitude,
    double? longitude,
    String? timezone,
  }) = _BirthData;

  const BirthData._();

  factory BirthData.fromJson(Map<String, dynamic> json) =>
      _$BirthDataFromJson(json);

  bool get hasExactTime => time != null && time!.isNotEmpty;

  bool get hasCoordinates => latitude != null && longitude != null;

  /// A chart can only be trusted when time and place are both known.
  bool get isComplete => hasExactTime && hasCoordinates;
}
