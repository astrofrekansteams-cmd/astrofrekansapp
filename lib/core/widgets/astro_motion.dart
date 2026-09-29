import 'package:flutter/material.dart';

import '../extensions/context_extensions.dart';

/// A finite entrance animation. Content is immediate with reduced motion.
class AstroReveal extends StatefulWidget {
  const AstroReveal({super.key, required this.child, this.order = 0});
  final Widget child;
  final int order;

  @override
  State<AstroReveal> createState() => _AstroRevealState();
}

class _AstroRevealState extends State<AstroReveal>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: Duration(milliseconds: 600 + widget.order.clamp(0, 6) * 65),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (context.reduceMotion) {
      _controller.value = 1;
    } else if (!_controller.isAnimating && _controller.value == 0) {
      _controller.forward();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final animation = _controller.drive(
      CurveTween(
        curve: Interval(
          widget.order.clamp(0, 6) * .06,
          1,
          curve: Curves.easeOutCubic,
        ),
      ),
    );
    return FadeTransition(
      opacity: animation,
      child: SlideTransition(
        position: animation.drive(
          Tween(begin: const Offset(0, .045), end: Offset.zero),
        ),
        child: widget.child,
      ),
    );
  }
}

/// Pointer feedback without taking over the child's tap or accessibility action.
class AstroPress extends StatefulWidget {
  const AstroPress({super.key, required this.child});
  final Widget child;
  @override
  State<AstroPress> createState() => _AstroPressState();
}

class _AstroPressState extends State<AstroPress> {
  bool _pressed = false;
  bool _hovered = false;
  @override
  Widget build(BuildContext context) => MouseRegion(
    onEnter: (_) => setState(() => _hovered = true),
    onExit: (_) => setState(() {
      _hovered = false;
      _pressed = false;
    }),
    child: Listener(
      onPointerDown: (_) => setState(() => _pressed = true),
      onPointerUp: (_) => setState(() => _pressed = false),
      onPointerCancel: (_) => setState(() => _pressed = false),
      child: AnimatedScale(
        scale: context.reduceMotion
            ? 1
            : (_pressed ? .98 : (_hovered ? 1.008 : 1)),
        duration: context.reduceMotion
            ? Duration.zero
            : const Duration(milliseconds: 160),
        curve: Curves.easeOutCubic,
        child: widget.child,
      ),
    ),
  );
}
