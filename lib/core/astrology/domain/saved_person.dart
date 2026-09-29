/// Stable saved-person profile from the users API, independent of B5 matching.
class SavedPerson {
  const SavedPerson({
    required this.id,
    required this.name,
    required this.relationship,
    required this.birthDate,
    required this.birthTimeKnown,
    required this.createdAt,
    required this.houseSystem,
    this.birthTime,
    this.birthPlace,
    this.latitude,
    this.longitude,
    this.timezone,
    this.note,
  });

  final String id;
  final String name;
  final String relationship;
  final DateTime birthDate;
  final String? birthTime;
  final bool birthTimeKnown;
  final String? birthPlace;
  final double? latitude;
  final double? longitude;
  final String? timezone;
  final String houseSystem;
  final String? note;
  final DateTime createdAt;

  // SavedPersonResponse has no updated_at field; do not synthesize one.
}
