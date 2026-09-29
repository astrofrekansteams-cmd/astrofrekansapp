"""The premium feature catalogue - the one place that says what is paid.

Routes enforce it with `require_feature(...)`; the client reads the same
catalogue from `GET /billing/features` to draw its locks. No widget or route
decides on its own that something is premium.
"""

from __future__ import annotations

from enum import StrEnum

from app.core.config import settings
from app.core.exceptions import PermissionDenied
from app.domain.divination import DeckType
from app.domain.enums import SubscriptionTier

FEATURES_VERSION = "features_v2"


class Feature(StrEnum):
    ADVANCED_TAROT = "advanced_tarot"
    ADVANCED_RUNE = "advanced_rune"
    ADVANCED_KATINA = "advanced_katina"
    SYNASTRY = "synastry"
    COMPOSITE = "composite"
    DAVISON = "davison"
    MONTHLY_FORECAST = "monthly_forecast"
    YEARLY_FORECAST = "yearly_forecast"
    SOLAR_RETURN = "solar_return"
    LUNAR_RETURN = "lunar_return"
    ADVANCED_TRANSITS = "advanced_transits"
    ADVANCED_AI = "advanced_ai"
    ASTROCARTOGRAPHY = "astrocartography"


# The lowest plan that includes each feature. Premium is "more of the
# everyday"; Kozmik+ adds the relationship charts, the long-range forecasts,
# return charts and the advanced AI.
FEATURE_TIERS: dict[Feature, SubscriptionTier] = {
    Feature.ADVANCED_TAROT: SubscriptionTier.PREMIUM,
    Feature.ADVANCED_RUNE: SubscriptionTier.PREMIUM,
    Feature.ADVANCED_KATINA: SubscriptionTier.PREMIUM,
    Feature.MONTHLY_FORECAST: SubscriptionTier.PREMIUM,
    Feature.ADVANCED_TRANSITS: SubscriptionTier.PREMIUM,
    Feature.SYNASTRY: SubscriptionTier.COSMIC_PLUS,
    Feature.COMPOSITE: SubscriptionTier.COSMIC_PLUS,
    Feature.DAVISON: SubscriptionTier.COSMIC_PLUS,
    Feature.YEARLY_FORECAST: SubscriptionTier.COSMIC_PLUS,
    Feature.SOLAR_RETURN: SubscriptionTier.COSMIC_PLUS,
    Feature.LUNAR_RETURN: SubscriptionTier.COSMIC_PLUS,
    Feature.ADVANCED_AI: SubscriptionTier.COSMIC_PLUS,
    Feature.ASTROCARTOGRAPHY: SubscriptionTier.COSMIC_PLUS,
}

PREMIUM_FEATURES: frozenset[Feature] = frozenset(FEATURE_TIERS)

# What a plan-gated feature costs in AstroCoins for one use, as a spend item
# code (prices live in the coin catalogue). A feature missing here cannot be
# bought with coins.
FEATURE_COIN_ITEMS: dict[Feature, str] = {
    Feature.ADVANCED_TAROT: "advanced_spread",
    Feature.ADVANCED_RUNE: "advanced_spread",
    Feature.ADVANCED_KATINA: "advanced_spread",
    Feature.ADVANCED_AI: "ai_deep_reading",
    Feature.MONTHLY_FORECAST: "single_premium_content",
    Feature.YEARLY_FORECAST: "single_premium_content",
    Feature.ADVANCED_TRANSITS: "single_premium_content",
    Feature.SOLAR_RETURN: "single_premium_content",
    Feature.LUNAR_RETURN: "single_premium_content",
    Feature.SYNASTRY: "single_premium_content",
    Feature.COMPOSITE: "single_premium_content",
    Feature.DAVISON: "single_premium_content",
}

# Spreads anyone can deal. Every other spread is the deck's advanced feature.
FREE_SPREADS: dict[DeckType, frozenset[str]] = {
    DeckType.TAROT: frozenset(
        {"single_card", "three_card", "past_present_future", "situation_obstacle_advice", "question_insight"}
    ),
    DeckType.RUNE: frozenset(
        {"single_rune", "three_rune", "past_present_future", "problem_hidden_solution", "question_rune"}
    ),
    DeckType.KATINA: frozenset({"single_card", "three_card", "relationship_three", "question_katina"}),
}

DECK_FEATURE: dict[DeckType, Feature] = {
    DeckType.TAROT: Feature.ADVANCED_TAROT,
    DeckType.RUNE: Feature.ADVANCED_RUNE,
    DeckType.KATINA: Feature.ADVANCED_KATINA,
}

# Transit ranges beyond the week are the advanced transit analysis.
PREMIUM_TRANSIT_RANGES: frozenset[str] = frozenset({"month", "year"})


def daily_draw_limits() -> dict[SubscriptionTier, int]:
    """Tarot/Rune/Katina draws per day by plan. Beyond it a draw costs coins."""
    return {
        SubscriptionTier.FREE: settings.daily_draws_free,
        SubscriptionTier.PREMIUM: settings.daily_draws_premium,
        SubscriptionTier.COSMIC_PLUS: settings.daily_draws_cosmic_plus,
    }


def spread_feature(deck: DeckType, spread_code: str) -> Feature | None:
    """The feature a spread needs, or None when it is free."""
    if spread_code in FREE_SPREADS[deck]:
        return None
    return DECK_FEATURE[deck]


def required_tier(feature: Feature | None) -> SubscriptionTier:
    if feature is None:
        return SubscriptionTier.FREE
    return FEATURE_TIERS.get(feature, SubscriptionTier.FREE)


def has_feature(tier: SubscriptionTier, feature: Feature | None) -> bool:
    if feature is None or not settings.premium_gating_enabled:
        return True
    return SubscriptionTier(tier).includes(required_tier(feature))


def ensure_feature(tier: SubscriptionTier, feature: Feature | None) -> None:
    if not has_feature(tier, feature):
        needed = required_tier(feature)
        raise PermissionDenied(
            "This feature requires a higher Astrofrekans plan.",
            code="premium_required",
            details={
                "feature": feature.value if feature else None,
                "required_tier": needed.value,
                # Set when one use can be bought with AstroCoins instead;
                # the price is in `/coins/catalog`.
                "coin_item": FEATURE_COIN_ITEMS.get(feature) if feature else None,
            },
        )


def catalogue() -> dict:
    """What the client mirrors. Deterministic and cheap."""
    return {
        "version": FEATURES_VERSION,
        "gating_enabled": settings.premium_gating_enabled,
        "premium_features": sorted(f.value for f in PREMIUM_FEATURES),
        # Which plan unlocks what; `premium_features` stays for older clients.
        "feature_tiers": {f.value: t.value for f, t in sorted(FEATURE_TIERS.items())},
        "daily_draw_limits": {
            tier.value: limit for tier, limit in daily_draw_limits().items()
        },
        "free_spreads": {deck.value: sorted(codes) for deck, codes in FREE_SPREADS.items()},
        "premium_transit_ranges": sorted(PREMIUM_TRANSIT_RANGES),
    }
