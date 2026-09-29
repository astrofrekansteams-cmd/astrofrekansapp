import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/astrology/data/production_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../auth/application/session_controller.dart';
import '../../profile/domain/user_profile.dart';
import 'entitlement_controller.dart';

/// Premium features, as named by the server's catalogue (`/billing/features`).
enum PremiumFeature {
  advancedTarot('advanced_tarot'),
  advancedRune('advanced_rune'),
  advancedKatina('advanced_katina'),
  synastry('synastry'),
  composite('composite'),
  davison('davison'),
  monthlyForecast('monthly_forecast'),
  yearlyForecast('yearly_forecast'),
  solarReturn('solar_return'),
  lunarReturn('lunar_return'),
  advancedTransits('advanced_transits'),
  advancedAi('advanced_ai'),
  astrocartography('astrocartography');

  const PremiumFeature(this.code);
  final String code;

  static PremiumFeature forDeck(DeckType deck) => switch (deck) {
    DeckType.tarot => advancedTarot,
    DeckType.rune => advancedRune,
    DeckType.katina => advancedKatina,
  };
}

/// The server's feature catalogue. The client mirrors it; it never decides on
/// its own that something is premium.
@immutable
class FeatureCatalogue {
  const FeatureCatalogue({
    required this.gatingEnabled,
    required this.premiumFeatures,
    required this.freeSpreads,
    required this.premiumTransitRanges,
    this.featureTiers = const {},
    this.dailyDrawLimits = const {},
  });

  factory FeatureCatalogue.fromJson(Json json) => FeatureCatalogue(
    featureTiers: {
      for (final entry in (json['feature_tiers'] as Map? ?? {}).entries)
        if (entry.key is String && entry.value is String)
          entry.key as String: SubscriptionTier.fromWire(entry.value as String),
    },
    dailyDrawLimits: {
      for (final entry in (json['daily_draw_limits'] as Map? ?? {}).entries)
        if (entry.value is int)
          SubscriptionTier.fromWire(entry.key as String): entry.value as int,
    },
    gatingEnabled: json['gating_enabled'] as bool? ?? true,
    premiumFeatures: {
      for (final code in (json['premium_features'] as List? ?? []))
        code as String,
    },
    freeSpreads: {
      for (final entry in (json['free_spreads'] as Map? ?? {}).entries)
        entry.key as String: {
          for (final code in entry.value as List) code as String,
        },
    },
    premiumTransitRanges: {
      for (final code in (json['premium_transit_ranges'] as List? ?? []))
        code as String,
    },
  );

  final bool gatingEnabled;
  final Set<String> premiumFeatures;
  final Map<String, Set<String>> freeSpreads;
  final Set<String> premiumTransitRanges;

  /// The lowest plan that includes each feature (server `feature_tiers`).
  final Map<String, SubscriptionTier> featureTiers;
  final Map<SubscriptionTier, int> dailyDrawLimits;
}

/// One answer to "may this user use X", for every screen.
///
/// Until the catalogue has loaded nothing is shown as locked: the server
/// enforces the same catalogue and answers `premium_required`, which the
/// screens render as an upgrade prompt.
@immutable
class EntitlementService {
  const EntitlementService({
    required this.catalogue,
    required this.premium,
    SubscriptionTier? tier,
    // ignore: prefer_initializing_formals
  }) : _tier = tier;

  final FeatureCatalogue? catalogue;

  /// Any paid plan is active.
  final bool premium;
  final SubscriptionTier? _tier;

  /// The active plan. Without an explicit tier, `premium` means every plan
  /// feature is open (the pre-Kozmik+ behaviour).
  SubscriptionTier get tier =>
      _tier ?? (premium ? SubscriptionTier.cosmicPlus : SubscriptionTier.free);

  bool get gatingKnown => catalogue != null;

  bool isPremiumFeature(PremiumFeature feature) {
    final c = catalogue;
    return c != null &&
        c.gatingEnabled &&
        c.premiumFeatures.contains(feature.code);
  }

  /// The plan that unlocks [feature] (free when it is not gated).
  SubscriptionTier requiredTier(PremiumFeature feature) {
    if (!isPremiumFeature(feature)) return SubscriptionTier.free;
    return catalogue!.featureTiers[feature.code] ?? SubscriptionTier.premium;
  }

  bool canUse(PremiumFeature feature) => tier.includes(requiredTier(feature));

  int? get dailyDrawLimit => catalogue?.dailyDrawLimits[tier];

  bool isPremiumSpread(DeckType deck, String spreadCode) {
    final c = catalogue;
    if (c == null || !c.gatingEnabled) return false;
    final free = c.freeSpreads[deck.name] ?? const <String>{};
    return !free.contains(spreadCode) &&
        isPremiumFeature(PremiumFeature.forDeck(deck));
  }

  bool canUseSpread(DeckType deck, DivinationSpread spread) =>
      !isPremiumSpread(deck, spread.code) ||
      canUse(PremiumFeature.forDeck(deck));

  bool canUseTransitRange(String range) {
    final c = catalogue;
    if (c == null || !c.gatingEnabled) return true;
    return !c.premiumTransitRanges.contains(range) ||
        canUse(PremiumFeature.advancedTransits);
  }
}

final featureCatalogueProvider = FutureProvider<FeatureCatalogue?>((ref) async {
  ref.watch(currentUserProvider)?.id;
  if (ref.watch(appEnvironmentProvider).useMocks) return null;
  final api = ApiClient(ref.watch(dioProvider));
  return FeatureCatalogue.fromJson(await api.getMap('billing/features'));
});

/// Bridges the entitlement controller (a ChangeNotifier) into Riverpod.
final premiumUnlockedProvider = Provider<bool>((ref) {
  final controller = ref.watch(entitlementControllerProvider);
  void listener() => ref.invalidateSelf();
  controller.addListener(listener);
  ref.onDispose(() => controller.removeListener(listener));
  return controller.state.premiumUnlocked;
});

/// The active plan: the verified entitlement summary, else the profile.
final subscriptionTierProvider = Provider<SubscriptionTier>((ref) {
  final controller = ref.watch(entitlementControllerProvider);
  void listener() => ref.invalidateSelf();
  controller.addListener(listener);
  ref.onDispose(() => controller.removeListener(listener));
  final snapshot = controller.state;
  if (snapshot.premiumUnlocked) {
    final tier = SubscriptionTier.fromWire(snapshot.summary?.tier);
    return tier.isPaid ? tier : SubscriptionTier.premium;
  }
  if (snapshot.summary != null) return SubscriptionTier.free;
  return ref.watch(currentUserProvider)?.subscriptionTier ??
      SubscriptionTier.free;
});

final entitlementServiceProvider = Provider<EntitlementService>(
  (ref) => EntitlementService(
    catalogue: ref.watch(featureCatalogueProvider).asData?.value,
    premium: ref.watch(premiumUnlockedProvider),
    tier: ref.watch(subscriptionTierProvider),
  ),
);
