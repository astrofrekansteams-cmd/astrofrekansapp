/// Ptolemaic aspects used by the engine and by the UI glyphs.
enum AspectType {
  conjunction(0),
  sextile(60),
  square(90),
  trine(120),
  opposition(180);

  const AspectType(this.angle);

  final int angle;

  /// Harmonious aspects read as supportive, hard aspects as challenging.
  AspectNature get nature => switch (this) {
    AspectType.trine || AspectType.sextile => AspectNature.harmonious,
    AspectType.square || AspectType.opposition => AspectNature.hard,
    AspectType.conjunction => AspectNature.neutral,
  };
}

enum AspectNature { harmonious, hard, neutral }

/// How an influence should be framed to the user.
enum InfluenceNature { supportive, challenging, emotional, lesson, neutral }
