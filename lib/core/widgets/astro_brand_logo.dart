import 'package:flutter/material.dart';
import '../assets/app_assets.dart';
import 'astro_image.dart';

/// Full supplied lockup; preserve its lettering and transparent silhouette.
class AstroBrandLogo extends StatelessWidget {
  const AstroBrandLogo({super.key, this.width = 280});
  final double width;
  @override
  Widget build(BuildContext context) => AstroImage(
    AppAssets.entryLogo,
    width: width,
    semanticLabel: 'Astrofrekans — Kendi gökyüzünü keşfet',
  );
}
