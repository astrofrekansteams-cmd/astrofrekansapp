import 'package:flutter/services.dart';
import 'app_assets.dart';

/// Only paths actually bundled by Flutter's manifest may be rendered.
class DivinationAssetResolver {
  DivinationAssetResolver(Iterable<String> assets)
    : _assets = Set.unmodifiable(assets);
  final Set<String> _assets;
  static Future<DivinationAssetResolver> load() async =>
      DivinationAssetResolver(
        (await AssetManifest.loadFromAssetBundle(rootBundle)).listAssets(),
      );
  String? resolve(String deck, String key, {bool stone = false}) {
    if (!RegExp(r'^[a-zA-Z0-9_-]+$').hasMatch(key)) return null;
    final path = switch (deck) {
      'tarot' => AppAssets.tarotCard(key),
      'katina' => AppAssets.katinaCard(key),
      'rune' => stone ? AppAssets.runeStone(key) : AppAssets.runeCard(key),
      _ => '',
    };
    return _assets.contains(path) ? path : null;
  }
}
