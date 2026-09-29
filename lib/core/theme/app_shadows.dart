import 'package:flutter/widgets.dart';

import 'app_colors.dart';

/// Shadow and glow tokens. Glows stay restrained on purpose.
abstract final class AppShadows {
  static const List<BoxShadow> card = <BoxShadow>[
    BoxShadow(color: Color(0x66000000), blurRadius: 24, offset: Offset(0, 10)),
  ];

  static const List<BoxShadow> raised = <BoxShadow>[
    BoxShadow(color: Color(0x80000000), blurRadius: 32, offset: Offset(0, 14)),
  ];

  /// Soft champagne halo used behind the score ring and the Astro AI orb.
  static List<BoxShadow> goldGlow({double strength = 1}) => <BoxShadow>[
    BoxShadow(
      color: AppColors.glow.withValues(alpha: 0.22 * strength),
      blurRadius: 28 * strength,
      spreadRadius: 2 * strength,
    ),
  ];
}
