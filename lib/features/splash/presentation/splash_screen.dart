import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/assets/app_assets.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/widgets/widgets.dart';
import '../../auth/application/session_controller.dart';
import '../../../core/config/firebase_client.dart';

/// Brand moment while storage is read.
///
/// There is no artificial delay: [SessionController.bootstrap] resolves the
/// session and the router immediately redirects. The fade/scale is purely
/// decorative and is skipped when the user asked for reduced motion.
class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  );

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (!context.reduceMotion) _controller.forward();
      unawaited(ref.read(firebaseBootstrapProvider.future));
      final SessionState session = ref.read(sessionProvider);
      if (session.status == SessionStatus.unknown) {
        unawaited(ref.read(sessionProvider.notifier).bootstrap());
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bool animate = !context.reduceMotion;
    final Animation<double> fade = CurvedAnimation(
      parent: _controller,
      curve: Curves.easeOutCubic,
    );

    return AstroScaffold(
      backgroundAsset: AppAssets.splashBackground,
      backgroundAspectRatio: 1080 / 1920,
      scrimOpacity: 0.35,
      body: Center(
        child: AnimatedBuilder(
          animation: fade,
          builder: (BuildContext context, Widget? child) {
            final double t = animate ? fade.value : 1;
            return Opacity(
              opacity: t,
              child: Transform.scale(scale: 0.92 + 0.08 * t, child: child),
            );
          },
          child: const Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[AstroBrandLogo(width: 280)],
          ),
        ),
      ),
    );
  }
}
