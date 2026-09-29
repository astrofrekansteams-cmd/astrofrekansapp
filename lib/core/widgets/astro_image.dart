import 'package:flutter/material.dart';

/// Asset image that always decodes at (roughly) its display size.
///
/// The production art is 1024px+ per file; decoding a 1024x1024 PNG for a 32px
/// icon costs ~4MB of image cache each. [AstroImage] passes `cacheWidth`/
/// `cacheHeight` so the decode matches the physical pixels actually needed.
class AstroImage extends StatelessWidget {
  const AstroImage(
    this.asset, {
    super.key,
    this.width,
    this.height,
    this.fit = BoxFit.contain,
    this.opacity,
    this.color,
    this.semanticLabel,
    this.alignment = Alignment.center,
    this.decodeWidth,
  }) : assert(
         width != null || height != null,
         'Give AstroImage a width or a height so it can size its decode',
       );

  final String asset;
  final double? width;
  final double? height;
  final BoxFit fit;
  final double? opacity;
  final Color? color;
  final String? semanticLabel;
  final Alignment alignment;

  /// Decode at this logical width instead of [width]. Lets one decode serve
  /// the same art shown at two sizes (e.g. a small preview of a large card).
  final double? decodeWidth;

  static (int?, int?) _cacheSize(
    BuildContext context,
    double? width,
    double? height,
  ) {
    final double ratio = MediaQuery.devicePixelRatioOf(context);
    // Cap the decode: text scaling / huge screens should not blow up memory.
    final int? cacheWidth = width == null
        ? null
        : (width * ratio).round().clamp(1, 2048);
    final int? cacheHeight = width == null && height != null
        ? (height * ratio).round().clamp(1, 2048)
        : null;
    return (cacheWidth, cacheHeight);
  }

  /// Decodes [asset] into the image cache exactly as an [AstroImage] of the
  /// same [width]/[height] would, so that widget paints on its first frame.
  /// Never throws: a missing asset simply stays uncached.
  static Future<void> precache(
    BuildContext context,
    String asset, {
    double? width,
    double? height,
  }) {
    final (cacheWidth, cacheHeight) = _cacheSize(context, width, height);
    return precacheImage(
      ResizeImage.resizeIfNeeded(cacheWidth, cacheHeight, AssetImage(asset)),
      context,
      onError: (_, _) {},
    );
  }

  @override
  Widget build(BuildContext context) {
    final (cacheWidth, cacheHeight) = _cacheSize(
      context,
      decodeWidth ?? width,
      height,
    );

    Widget image = Image.asset(
      asset,
      width: width,
      height: height,
      fit: fit,
      alignment: alignment,
      cacheWidth: cacheWidth,
      cacheHeight: cacheHeight,
      color: color,
      filterQuality: FilterQuality.medium,
      isAntiAlias: true,
      gaplessPlayback: true,
      excludeFromSemantics: semanticLabel == null,
      semanticLabel: semanticLabel,
    );

    if (opacity != null) {
      image = Opacity(opacity: opacity!, child: image);
    }
    return image;
  }
}

/// Full-bleed decorative art (backgrounds, hero panels).
///
/// Decodes against the *limiting* axis for [BoxFit.cover] so the bitmap is
/// never larger than the screen needs.
class AstroCoverImage extends StatelessWidget {
  const AstroCoverImage({
    required this.asset,
    super.key,
    this.aspectRatio = 9 / 16,
    this.alignment = Alignment.center,
    this.opacity = 1,
  });

  final String asset;

  /// Intrinsic width / height of the artwork.
  final double aspectRatio;
  final Alignment alignment;
  final double opacity;

  @override
  Widget build(BuildContext context) {
    final double ratio = MediaQuery.devicePixelRatioOf(context);
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final double width = constraints.maxWidth.isFinite
            ? constraints.maxWidth
            : MediaQuery.sizeOf(context).width;
        final double height = constraints.maxHeight.isFinite
            ? constraints.maxHeight
            : MediaQuery.sizeOf(context).height;
        final bool widthIsLimiting = width / height > aspectRatio;

        return Image(
          image: ResizeImage(
            AssetImage(asset),
            width: widthIsLimiting ? (width * ratio).round() : null,
            height: widthIsLimiting ? null : (height * ratio).round(),
            policy: ResizeImagePolicy.fit,
          ),
          fit: BoxFit.cover,
          alignment: alignment,
          opacity: AlwaysStoppedAnimation<double>(opacity),
          filterQuality: FilterQuality.medium,
          excludeFromSemantics: true,
        );
      },
    );
  }
}
