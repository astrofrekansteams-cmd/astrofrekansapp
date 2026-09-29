import 'package:flutter/material.dart';

import '../assets/app_assets.dart';
import '../extensions/context_extensions.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';
import 'astro_image.dart';

/// Breathing orb loader. Honours reduce-motion (and widget tests, which set
/// `disableAnimations`), where it renders a static orb instead.
class AstroLoading extends StatefulWidget {
  const AstroLoading({super.key, this.message, this.size = 72});

  final String? message;
  final double size;

  @override
  State<AstroLoading> createState() => _AstroLoadingState();
}

class _AstroLoadingState extends State<AstroLoading>
    with SingleTickerProviderStateMixin {
  AnimationController? _controller;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!context.reduceMotion && _controller == null) {
      _controller = AnimationController(
        vsync: this,
        duration: const Duration(milliseconds: 2200),
      )..repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final Widget orb = AstroImage(
      AppAssets.astroAiOrb,
      width: widget.size,
      height: widget.size,
      semanticLabel: null,
    );

    return Semantics(
      label: widget.message,
      liveRegion: true,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          if (_controller == null)
            orb
          else
            AnimatedBuilder(
              animation: _controller!,
              builder: (BuildContext context, Widget? child) {
                final double t = Curves.easeInOut.transform(_controller!.value);
                return Transform.scale(
                  scale: 0.94 + 0.06 * t,
                  child: Opacity(opacity: 0.78 + 0.22 * t, child: child),
                );
              },
              child: orb,
            ),
          if (widget.message != null) ...<Widget>[
            const SizedBox(height: AppSpacing.md),
            Text(
              widget.message!,
              textAlign: TextAlign.center,
              style: AppTypography.bodySmall.copyWith(
                color: AppColors.ivoryMuted,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
