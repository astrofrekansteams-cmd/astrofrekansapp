"""AstroCoin: wallet, history, catalogue and rewarded ads.

There is deliberately no "add coins" endpoint. Coins arrive from a verified
store purchase (`/billing/*/verify`), a verified rewarded ad, the monthly plan
bonus, or a refund of a failed spend. Spending happens inside the feature that
costs coins (e.g. a divination draw with `pay_with_coins`), so a price is
never charged without the work it pays for.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession, UserRateLimit
from app.core.config import settings
from app.db.models.user import User
from app.schemas.coins import (
    AdRewardRequest,
    AdRewardResponse,
    CoinCatalogResponse,
    CoinPackResponse,
    CoinTransactionResponse,
    ComparisonRowResponse,
    PlanResponse,
    SpendItemResponse,
    WalletResponse,
)
from app.services.coins.ads import ad_rewards_enabled
from app.services.coins.catalog import (
    SPEND_ITEMS,
    coin_packs,
    comparison,
    monthly_bonus,
    plans,
)
from app.services.coins.service import CoinService

router = APIRouter(prefix="/coins", tags=["coins"])

_ad_limit = Depends(UserRateLimit("30/hour", scope="coins_ad", code="rate_limited"))


async def _wallet(service: CoinService, user: User, *, granted: int = 0) -> WalletResponse:
    wallet = await service.wallet(user.id)
    return WalletResponse(
        balance=wallet.balance,
        lifetime_earned=wallet.lifetime_earned,
        lifetime_spent=wallet.lifetime_spent,
        tier=user.tier.value,
        monthly_bonus=monthly_bonus(user.tier),
        # Paid plans are ad-free: no rewarded ads offered there.
        ads_enabled=ad_rewards_enabled() and not user.tier.is_paid,
        ads_watched_today=await service.ads_today(user.id),
        ads_daily_limit=settings.ad_rewards_per_day,
        ad_reward_coins=settings.ad_reward_coins,
        bonus_granted=granted,
    )


@router.get("/wallet", response_model=WalletResponse, summary="Balance and earning status")
async def get_wallet(user: CurrentUser, session: DbSession) -> WalletResponse:
    service = CoinService(session)
    bonus = await service.ensure_monthly_bonus(user)
    response = await _wallet(service, user, granted=bonus.amount if bonus else 0)
    await session.commit()
    return response


@router.get(
    "/transactions",
    response_model=list[CoinTransactionResponse],
    summary="Coin history, newest first",
)
async def transactions(
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CoinTransactionResponse]:
    rows = await CoinService(session).history(user.id, limit=limit)
    return [CoinTransactionResponse.model_validate(row, from_attributes=True) for row in rows]


@router.get("/catalog", response_model=CoinCatalogResponse, summary="What coins buy; plans; packs")
async def catalog(user: CurrentUser) -> CoinCatalogResponse:
    return CoinCatalogResponse(
        spend_items=[
            SpendItemResponse(code=i.code, price=i.price, available=i.available)
            for i in SPEND_ITEMS
        ],
        coin_packs=[CoinPackResponse(**pack) for pack in coin_packs()],
        plans=[PlanResponse(**plan) for plan in plans()],
        comparison=[ComparisonRowResponse(**row) for row in comparison()],
    )


@router.post(
    "/ads/reward",
    response_model=AdRewardResponse,
    dependencies=[_ad_limit],
    summary="Claim the coins for a completed rewarded ad",
    description=(
        "The token is verified with the ad network server side; one token "
        "pays once. Limited per day. Answers `ad_rewards_unavailable` while "
        "no ad network is configured (a dev-only mock exists outside "
        "production)."
    ),
)
async def reward_ad(
    payload: AdRewardRequest, user: CurrentUser, session: DbSession
) -> AdRewardResponse:
    service = CoinService(session)
    row = await service.reward_ad(user, token=payload.token)
    response = AdRewardResponse(
        transaction=CoinTransactionResponse.model_validate(row, from_attributes=True),
        wallet=await _wallet(service, user),
    )
    await session.commit()
    return response
