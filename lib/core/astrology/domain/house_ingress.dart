import 'planet.dart';

class HouseIngress {
  const HouseIngress({
    required this.id,
    required this.planet,
    required this.fromHouse,
    required this.toHouse,
    required this.enteredAt,
    required this.retrograde,
    required this.reEntry,
    this.estimatedExitAt,
  });

  final String id;
  final Planet planet;
  final int fromHouse;
  final int toHouse;
  final DateTime enteredAt;
  final DateTime? estimatedExitAt;
  final bool retrograde;
  final bool reEntry;
}
