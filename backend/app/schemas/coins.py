from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import APIModel


class CoinTransactionResponse(APIModel):
    id: uuid.UUID
    amount: int
    balance_after: int
    kind: str
    reason: str
    reference_id: str | None = None
    created_at: datetime


class WalletResponse(APIModel):
    balance: int
    lifetime_earned: int
    lifetime_spent: int
    tier: str
    monthly_bonus: int
    ads_enabled: bool
    ads_watched_today: int
    ads_daily_limit: int
    ad_reward_coins: int
    # Set when opening the wallet granted this month's plan bonus just now.
    bonus_granted: int = 0


class SpendItemResponse(APIModel):
    code: str
    price: int
    available: bool


class CoinPackResponse(APIModel):
    product_code: str
    coins: int


class PlanResponse(APIModel):
    tier: str
    products: list[str]
    daily_draws: int
    monthly_coins: int
    ad_free: bool
    ad_rewards: bool
    features: list[str]
    includes_paid_reports: bool


class ComparisonRowResponse(APIModel):
    key: str
    # tier -> "included" | "coins" | "none"
    cells: dict[str, str]
    # tier -> a number worth showing (daily draws, monthly coins)
    values: dict[str, int] = Field(default_factory=dict)
    coin_item: str | None = None


class CoinCatalogResponse(APIModel):
    spend_items: list[SpendItemResponse]
    coin_packs: list[CoinPackResponse]
    plans: list[PlanResponse]
    comparison: list[ComparisonRowResponse] = Field(default_factory=list)


class AdRewardRequest(APIModel):
    token: str = Field(
        min_length=8,
        max_length=200,
        description=(
            "The ad network's reward token / transaction id for this view. "
            "Verified server side; the same token never pays twice."
        ),
    )


class AdRewardResponse(APIModel):
    transaction: CoinTransactionResponse
    wallet: WalletResponse
