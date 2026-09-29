import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../extensions/context_extensions.dart';
import '../theme/app_colors.dart';
import 'astro_image.dart';
import 'effects_budget.dart';
import '../assets/app_assets.dart';

/// The cosmic ground used by every screen.
///
/// Default variant paints a deterministic star field plus two restrained gold
/// glows - cheap, resolution independent and identical on every device.
/// [AstroBackground.image] layers one of the production backdrops under a scrim
/// for the splash / auth screens.
class AstroBackground extends StatefulWidget {
  const AstroBackground({
    super.key,
    this.child,
    this.starCount = 70,
    this.twinkle = true,
    this.asset,
    this.assetAspectRatio = 9 / 16,
    this.scrimOpacity = 0.55,
    this.alignment = Alignment.center,
  });

  /// Backdrop image variant (splash, onboarding, auth).
  const AstroBackground.image({
    Key? key,
    required String asset,
    Widget? child,
    double assetAspectRatio = 9 / 16,
    double scrimOpacity = 0.55,
    Alignment alignment = Alignment.center,
  }) : this(
         key: key,
         asset: asset,
         child: child,
         assetAspectRatio: assetAspectRatio,
         scrimOpacity: scrimOpacity,
         alignment: alignment,
         starCount: 0,
         twinkle: false,
       );

  final Widget? child;
  final int starCount;
  final bool twinkle;
  final String? asset;
  final double assetAspectRatio;
  final double scrimOpacity;
  final Alignment alignment;

  @override
  State<AstroBackground> createState() => _AstroBackgroundState();
}

class _AstroBackgroundState extends State<AstroBackground>
    with WidgetsBindingObserver {
  /// Twinkle updates per second. The cycle is 9 s and a star's opacity moves
  /// by at most ~0.03 between updates at this rate - indistinguishable from
  /// 60 fps - while each update redraws (re-rasters) the whole screen. A
  /// vsync ticker here kept the device drawing ~60 full frames a second.
  static const int _updatesPerSecond = 8;
  static const int _cycleMs = 9000;

  final ValueNotifier<double> _phase = ValueNotifier<double>(0);
  Timer? _timer;
  bool _resumed = true;
  bool _visible = true;
  bool _reduceMotion = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    final AppLifecycleState? state = WidgetsBinding.instance.lifecycleState;
    _resumed = state == null || state == AppLifecycleState.resumed;
    EffectsBudget.reduced.addListener(_sync);
    EffectsBudget.watch();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Covered routes and inactive tabs have tickers disabled; the twinkle
    // follows the same signal so only the visible screen moves.
    _visible = TickerMode.valuesOf(context).enabled;
    _reduceMotion = context.reduceMotion;
    _sync();
  }

  @override
  void didUpdateWidget(AstroBackground oldWidget) {
    super.didUpdateWidget(oldWidget);
    _sync();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _resumed = state == AppLifecycleState.resumed;
    _sync();
  }

  void _sync() {
    final bool run =
        widget.twinkle &&
        widget.starCount > 0 &&
        !_reduceMotion &&
        _visible &&
        _resumed &&
        !EffectsBudget.reduced.value;
    if (run && _timer == null) {
      const int stepMs = 1000 ~/ _updatesPerSecond;
      _timer = Timer.periodic(
        const Duration(milliseconds: stepMs),
        (_) => _phase.value = (_phase.value + stepMs / _cycleMs) % 1,
      );
    } else if (!run && _timer != null) {
      _timer!.cancel();
      _timer = null;
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    EffectsBudget.reduced.removeListener(_sync);
    WidgetsBinding.instance.removeObserver(this);
    _phase.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(gradient: AppColors.nightGradient),
      child: Stack(
        fit: StackFit.expand,
        children: <Widget>[
          ...<Widget>[
            AstroCoverImage(
              asset: widget.asset ?? AppAssets.splashBackground,
              aspectRatio: widget.asset == null
                  ? 1080 / 1920
                  : widget.assetAspectRatio,
              alignment: widget.alignment,
            ),
            DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: <Color>[
                    AppColors.night.withValues(
                      alpha:
                          (widget.asset == null ? .32 : widget.scrimOpacity) *
                          0.7,
                    ),
                    AppColors.night.withValues(
                      alpha: widget.asset == null ? .38 : widget.scrimOpacity,
                    ),
                    AppColors.night.withValues(
                      alpha: math.min(1, widget.scrimOpacity + 0.35),
                    ),
                  ],
                ),
              ),
            ),
          ],
          if (widget.starCount > 0)
            RepaintBoundary(
              child: CustomPaint(
                painter: _StarFieldPainter(
                  starCount: widget.starCount,
                  phase: _phase,
                ),
              ),
            ),
          if (widget.child != null) widget.child!,
        ],
      ),
    );
  }
}

class _StarFieldPainter extends CustomPainter {
  _StarFieldPainter({required this.starCount, required this.phase})
    : super(repaint: phase);

  final int starCount;

  /// Twinkle position in the cycle, 0..1; repaints without a rebuild.
  final ValueListenable<double> phase;

  @override
  void paint(Canvas canvas, Size size) {
    // Two restrained gold glows instead of random gradients.
    final Paint glow = Paint()
      ..shader =
          RadialGradient(
            colors: <Color>[
              AppColors.gold.withValues(alpha: 0.12),
              Colors.transparent,
            ],
          ).createShader(
            Rect.fromCircle(
              center: Offset(size.width * 0.82, size.height * 0.12),
              radius: size.width * 0.55,
            ),
          );
    canvas.drawRect(Offset.zero & size, glow);

    final Paint deepGlow = Paint()
      ..shader =
          RadialGradient(
            colors: <Color>[
              AppColors.navySoft.withValues(alpha: 0.55),
              Colors.transparent,
            ],
          ).createShader(
            Rect.fromCircle(
              center: Offset(size.width * 0.1, size.height * 0.78),
              radius: size.width * 0.75,
            ),
          );
    canvas.drawRect(Offset.zero & size, deepGlow);

    final math.Random random = math.Random(20260322);
    final Paint star = Paint()..color = AppColors.ivory;
    for (int i = 0; i < starCount; i++) {
      final double dx = random.nextDouble() * size.width;
      final double dy = random.nextDouble() * size.height;
      final double baseRadius = 0.4 + random.nextDouble() * 1.1;
      final double offset = random.nextDouble();
      final double twinkle =
          0.35 +
          0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * (phase.value + offset)));
      star.color = (i % 7 == 0 ? AppColors.goldBright : AppColors.ivory)
          .withValues(alpha: 0.18 + 0.4 * twinkle);
      canvas.drawCircle(Offset(dx, dy), baseRadius, star);
    }
  }

  @override
  bool shouldRepaint(_StarFieldPainter oldDelegate) =>
      oldDelegate.phase != phase || oldDelegate.starCount != starCount;
}
