import '../../assets/app_assets.dart';

/// Chart bodies and points the engine can report.
enum Planet {
  sun,
  moon,
  mercury,
  venus,
  mars,
  jupiter,
  saturn,
  uranus,
  neptune,
  pluto,
  northNode,
  southNode;

  /// Key used by [AppAssets.planets] (snake_case on disk).
  String get assetKey => switch (this) {
    Planet.northNode => 'north_node',
    Planet.southNode => 'south_node',
    _ => name,
  };

  String get asset => AppAssets.planets[assetKey]!;

  /// Personal planets move fast and drive day-to-day transits.
  bool get isPersonal => index <= Planet.mars.index;
}

/// The four angles of a chart. Assets exist for all of them.
enum ChartAngle {
  asc,
  dsc,
  mc,
  ic;

  String get asset => switch (this) {
    ChartAngle.asc => AppAssets.natalAsc,
    ChartAngle.dsc => AppAssets.natalDsc,
    ChartAngle.mc => AppAssets.natalMc,
    ChartAngle.ic => AppAssets.natalIc,
  };
}
