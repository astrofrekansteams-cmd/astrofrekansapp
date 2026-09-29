import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../theme/app_theme.dart';
import '../theme/app_colors.dart';
import 'astro_background.dart';

/// Scaffold with the cosmic ground already in place.
///
/// Screens deal with content; the background, system bar styling and safe areas
/// are handled here once.
class AstroScaffold extends StatelessWidget {
  const AstroScaffold({
    required this.body,
    super.key,
    this.backgroundAsset,
    this.backgroundAspectRatio = 9 / 16,
    this.scrimOpacity = 0.55,
    this.appBar,
    this.bottomNavigationBar,
    this.floatingActionButton,
    this.safeAreaTop = true,
    this.safeAreaBottom = true,
    this.resizeToAvoidBottomInset = true,
    this.starCount = 70,
    this.extendBody = false,
  });

  final Widget body;
  final String? backgroundAsset;
  final double backgroundAspectRatio;
  final double scrimOpacity;
  final PreferredSizeWidget? appBar;
  final Widget? bottomNavigationBar;
  final Widget? floatingActionButton;
  final bool safeAreaTop;
  final bool safeAreaBottom;
  final bool resizeToAvoidBottomInset;
  final int starCount;

  /// When true the body paints behind [bottomNavigationBar]. Keep it false for
  /// screens with bottom-anchored controls (the chat composer would end up
  /// under the navigation bar).
  final bool extendBody;

  @override
  Widget build(BuildContext context) {
    final Widget background = backgroundAsset == null
        ? AstroBackground(starCount: starCount)
        : AstroBackground.image(
            asset: backgroundAsset!,
            assetAspectRatio: backgroundAspectRatio,
            scrimOpacity: scrimOpacity,
          );

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: AppTheme.overlayStyle,
      child: ColoredBox(
        color: AppColors.night,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 620),
            child: Stack(
              children: <Widget>[
                Positioned.fill(child: background),
                Scaffold(
                  backgroundColor: Colors.transparent,
                  extendBody: extendBody,
                  extendBodyBehindAppBar: true,
                  resizeToAvoidBottomInset: resizeToAvoidBottomInset,
                  appBar: appBar,
                  bottomNavigationBar: bottomNavigationBar,
                  floatingActionButton: floatingActionButton,
                  body: SafeArea(
                    top: safeAreaTop,
                    bottom: safeAreaBottom,
                    child: body,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
