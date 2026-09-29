import 'package:flutter/material.dart';

import '../extensions/context_extensions.dart';
import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import 'astro_card.dart';

/// Branded loading placeholder: soft navy blocks with a slow champagne sheen.
///
/// Replaces bare spinners so a loading screen keeps the page's shape instead
/// of going blank. Honours reduce-motion (and widget tests), where the sheen
/// is static.
class AstroSkeleton extends StatefulWidget {
  const AstroSkeleton({
    super.key,
    this.width,
    this.height = 14,
    this.borderRadius = AppRadius.brXs,
    this.circle = false,
  });

  const AstroSkeleton.circle({super.key, required double size})
    : width = size,
      height = size,
      borderRadius = AppRadius.brPill,
      circle = true;

  final double? width;
  final double height;
  final BorderRadius borderRadius;
  final bool circle;

  @override
  State<AstroSkeleton> createState() => _AstroSkeletonState();
}

class _AstroSkeletonState extends State<AstroSkeleton>
    with SingleTickerProviderStateMixin {
  AnimationController? _controller;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!context.reduceMotion && _controller == null) {
      _controller = AnimationController(
        vsync: this,
        duration: const Duration(milliseconds: 1600),
      )..repeat();
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  Widget _block(double t) => Container(
    width: widget.width,
    height: widget.height,
    decoration: BoxDecoration(
      shape: widget.circle ? BoxShape.circle : BoxShape.rectangle,
      borderRadius: widget.circle ? null : widget.borderRadius,
      gradient: LinearGradient(
        begin: Alignment(-1.6 + 3.2 * t, 0),
        end: Alignment(-0.6 + 3.2 * t, 0),
        colors: <Color>[
          AppColors.surfaceMuted.withValues(alpha: 0.7),
          AppColors.gold.withValues(alpha: 0.10),
          AppColors.surfaceMuted.withValues(alpha: 0.7),
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    if (controller == null) return _block(0.3);
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) => _block(controller.value),
    );
  }
}

/// A card-shaped placeholder: optional round media, a title bar and lines.
class AstroSkeletonCard extends StatelessWidget {
  const AstroSkeletonCard({
    super.key,
    this.lines = 3,
    this.media = false,
    this.mediaSize = 56,
    this.centered = false,
  });

  final int lines;
  final bool media;
  final double mediaSize;
  final bool centered;

  @override
  Widget build(BuildContext context) => AstroCard(
    padding: const EdgeInsets.all(AppSpacing.cardPadding),
    child: Column(
      crossAxisAlignment: centered
          ? CrossAxisAlignment.center
          : CrossAxisAlignment.start,
      children: <Widget>[
        if (media) ...<Widget>[
          AstroSkeleton.circle(size: mediaSize),
          const SizedBox(height: AppSpacing.lg),
        ],
        const AstroSkeleton(width: 160, height: 20),
        for (var i = 0; i < lines; i++) ...<Widget>[
          const SizedBox(height: AppSpacing.md),
          FractionallySizedBox(
            widthFactor: i == lines - 1 ? 0.6 : 1,
            child: const AstroSkeleton(),
          ),
        ],
      ],
    ),
  );
}

/// Default page-loading layout: a hero card and two content cards, spaced on
/// the card rhythm. Screens may pass their own shape to [ApiStateView].
class AstroSkeletonPage extends StatelessWidget {
  const AstroSkeletonPage({super.key, this.label});

  /// Read by screen readers ("Gökyüzün hazırlanıyor…").
  final String? label;

  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    label: label,
    child: const Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        AstroSkeletonCard(media: true, mediaSize: 96, centered: true),
        SizedBox(height: AppSpacing.cardGap),
        AstroSkeletonCard(lines: 4),
        SizedBox(height: AppSpacing.cardGap),
        AstroSkeletonCard(lines: 2),
      ],
    ),
  );
}
