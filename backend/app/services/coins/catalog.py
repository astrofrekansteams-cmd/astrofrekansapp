"""What coins buy, and what the plans include.

The spend catalogue is code: prices in coins are a product decision that
ships with the app version that honours them. Every listed item is enforced
server side; the client never hard-codes a price.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.domain.enums import SubscriptionTier
from app.services.features import FEATURE_COIN_ITEMS, FEATURE_TIERS, Feature, daily_draw_limits
from app.services.payments.catalog import CATALOG, StoreProductType


@dataclass(slots=True, frozen=True)
class SpendItem:
    code: str
    price: int
    available: bool


EXTRA_DRAW = "extra_draw"
ADVANCED_SPREAD = "advanced_spread"
AI_DEEP_READING = "ai_deep_reading"
SPECIAL_ANALYSIS = "special_analysis"
SINGLE_PREMIUM_CONTENT = "single_premium_content"

SPEND_ITEMS: tuple[SpendItem, ...] = (
    # A Tarot/Rune/Katina draw beyond the plan's daily allowance.
    SpendItem(EXTRA_DRAW, 10, True),
    # One advanced spread without the plan that includes it.
    SpendItem(ADVANCED_SPREAD, 25, True),
    # "Astro AI ile Derinleştir" on a Tarot/Rune/Katina reading (Kozmik+
    # includes it).
    SpendItem(AI_DEEP_READING, 40, True),
    # A long AI report otherwise sold as a store credit (natal, synastry,
    # yearly forecast).
    SpendItem(SPECIAL_ANALYSIS, 60, True),
    # One use of a plan-gated calculation (monthly/yearly forecast, returns,
    # relationship charts, extended transits).
    SpendItem(SINGLE_PREMIUM_CONTENT, 30, True),
)


def spend_item(code: str) -> SpendItem | None:
    return next((item for item in SPEND_ITEMS if item.code == code), None)


def monthly_bonus(tier: SubscriptionTier) -> int:
    tier = SubscriptionTier(tier)
    if tier.includes(SubscriptionTier.COSMIC_PLUS):
        return settings.monthly_coins_cosmic_plus
    if tier.includes(SubscriptionTier.PREMIUM):
        return settings.monthly_coins_premium
    return 0


def coin_packs() -> list[dict]:
    return [
        {"product_code": d.code, "coins": d.coins}
        for d in CATALOG
        if d.product_type is StoreProductType.CONSUMABLE and d.coins > 0
    ]


def plans() -> list[dict]:
    """The three plans, as data the client lays out. No prices: the stores
    own them; the client shows the store's localised price per product."""
    limits = daily_draw_limits()
    features = {
        tier: sorted(
            f.value for f, needed in FEATURE_TIERS.items() if tier.includes(needed)
        )
        for tier in SubscriptionTier
    }
    return [
        {
            "tier": SubscriptionTier.FREE.value,
            "products": [],
            "daily_draws": limits[SubscriptionTier.FREE],
            "monthly_coins": 0,
            "ad_free": False,
            "ad_rewards": True,
            "features": features[SubscriptionTier.FREE],
            "includes_paid_reports": False,
        },
        {
            "tier": SubscriptionTier.PREMIUM.value,
            "products": ["premium_monthly", "premium_yearly"],
            "daily_draws": limits[SubscriptionTier.PREMIUM],
            "monthly_coins": monthly_bonus(SubscriptionTier.PREMIUM),
            "ad_free": True,
            "ad_rewards": False,
            "features": features[SubscriptionTier.PREMIUM],
            "includes_paid_reports": settings.paid_reports_included_in_premium,
        },
        {
            "tier": SubscriptionTier.COSMIC_PLUS.value,
            "products": ["cosmic_plus_monthly", "cosmic_plus_yearly"],
            "daily_draws": limits[SubscriptionTier.COSMIC_PLUS],
            "monthly_coins": monthly_bonus(SubscriptionTier.COSMIC_PLUS),
            "ad_free": True,
            "ad_rewards": False,
            "features": features[SubscriptionTier.COSMIC_PLUS],
            "includes_paid_reports": settings.paid_reports_included_in_cosmic_plus,
        },
    ]


# Rows of the plan comparison, in display order: (row key, feature or None).
# A row without a feature is plan-level (ads, daily allowance, bonus).
_COMPARISON_ROWS: tuple[tuple[str, Feature | None], ...] = (
    ("daily_basics", None),
    ("daily_draws", None),
    ("advanced_spreads", Feature.ADVANCED_TAROT),
    ("ai_deep_reading", Feature.ADVANCED_AI),
    ("monthly_forecast", Feature.MONTHLY_FORECAST),
    ("advanced_transits", Feature.ADVANCED_TRANSITS),
    ("relationships", Feature.SYNASTRY),
    ("yearly_forecast", Feature.YEARLY_FORECAST),
    ("returns", Feature.SOLAR_RETURN),
    ("special_reports", None),
    ("ad_free", None),
    ("monthly_coins", None),
)


def comparison() -> list[dict]:
    """The plan table: each cell is "included", "coins" or "none".

    "coins" means the plan does not include it but one use can be bought with
    AstroCoins (`coin_item` names the spend item; its price is in this
    catalogue). Plan-level rows carry a `value` per tier where a number helps.
    """
    limits = daily_draw_limits()
    rows: list[dict] = []
    for key, feature in _COMPARISON_ROWS:
        cells: dict[str, str] = {}
        values: dict[str, int] = {}
        coin_item: str | None = None
        for tier in SubscriptionTier:
            if feature is not None:
                included = tier.includes(FEATURE_TIERS.get(feature, SubscriptionTier.FREE))
                coin_item = FEATURE_COIN_ITEMS.get(feature)
                cells[tier.value] = (
                    "included" if included else "coins" if coin_item else "none"
                )
            elif key == "daily_basics":
                cells[tier.value] = "included"
            elif key == "daily_draws":
                cells[tier.value] = "included"
                values[tier.value] = limits[tier]
            elif key == "special_reports":
                included = (
                    tier is SubscriptionTier.COSMIC_PLUS
                    and settings.paid_reports_included_in_cosmic_plus
                ) or (
                    tier is SubscriptionTier.PREMIUM
                    and settings.paid_reports_included_in_premium
                )
                coin_item = SPECIAL_ANALYSIS
                cells[tier.value] = "included" if included else "coins"
            elif key == "ad_free":
                cells[tier.value] = "included" if tier.is_paid else "none"
            elif key == "monthly_coins":
                bonus = monthly_bonus(tier)
                cells[tier.value] = "included" if bonus else "none"
                values[tier.value] = bonus
        rows.append(
            {"key": key, "cells": cells, "values": values, "coin_item": coin_item}
        )
    return rows
