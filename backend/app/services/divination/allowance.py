"""Daily Tarot/Rune/Katina allowance, and paying for more with coins.

The plan decides how many draws a day are included and which spreads. A draw
beyond the allowance, or a spread the plan does not include, can be paid with
AstroCoins - charged in the same transaction that creates the session, so a
failed creation never keeps the coins.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.db.models.divination import DivinationDrawSession, DivinationReading
from app.db.models.user import User
from app.domain.divination import DeckType
from app.domain.enums import SubscriptionTier
from app.services.coins.catalog import ADVANCED_SPREAD, EXTRA_DRAW, spend_item
from app.services.coins.service import CoinService
from app.services.features import (
    daily_draw_limits,
    ensure_feature,
    has_feature,
    required_tier,
    spread_feature,
)


class DailyDrawLimitReached(AppError):
    status_code = 429
    code = "daily_draw_limit_reached"
    message = "Today's included readings are used up."


@dataclass(slots=True, frozen=True)
class Allowance:
    tier: SubscriptionTier
    enforced: bool
    daily_limit: int
    used_today: int

    @property
    def remaining(self) -> int:
        return max(self.daily_limit - self.used_today, 0)


def _today() -> datetime:
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


async def allowance(session: AsyncSession, user: User) -> Allowance:
    start = _today()
    sessions = await session.scalar(
        select(func.count()).select_from(DivinationDrawSession).where(
            DivinationDrawSession.user_id == user.id,
            DivinationDrawSession.created_at >= start,
        )
    )
    # Legacy auto-draws (no session) count too.
    legacy = await session.scalar(
        select(func.count()).select_from(DivinationReading).where(
            DivinationReading.user_id == user.id,
            DivinationReading.draw_session_id.is_(None),
            DivinationReading.created_at >= start,
        )
    )
    tier = user.tier
    return Allowance(
        tier=tier,
        enforced=settings.premium_gating_enabled,
        daily_limit=daily_draw_limits()[tier],
        used_today=int(sessions or 0) + int(legacy or 0),
    )


async def charge_for_draw(
    session: AsyncSession,
    user: User,
    *,
    deck_type: DeckType,
    spread_code: str,
    consumer_ref: str,
    pay_with_coins: bool,
) -> int:
    """Check plan + allowance; charge coins when asked. Returns coins spent.

    Raises `premium_required` / `daily_draw_limit_reached` when the draw is
    not covered and coins were not offered, `insufficient_coins` when they
    were but the balance is short.
    """
    items: list[str] = []
    feature = spread_feature(deck_type, spread_code)
    if not has_feature(user.tier, feature):
        if not pay_with_coins:
            ensure_feature(user.tier, feature)
        items.append(ADVANCED_SPREAD)

    current = await allowance(session, user)
    if current.enforced and current.remaining <= 0:
        if not pay_with_coins:
            raise DailyDrawLimitReached(
                details={
                    "daily_limit": current.daily_limit,
                    "extra_draw_price": spend_item(EXTRA_DRAW).price,
                    "tier": current.tier.value,
                    "upgrade_tier": _next_tier(current.tier),
                    "required_tier": required_tier(feature).value,
                }
            )
        items.append(EXTRA_DRAW)

    if not items:
        return 0
    row = await CoinService(session).spend(
        user.id, items=items, consumer_ref=f"draw:{consumer_ref}"
    )
    return -row.amount


def _next_tier(tier: SubscriptionTier) -> str | None:
    order = list(SubscriptionTier)
    index = order.index(tier)
    return order[index + 1].value if index + 1 < len(order) else None
