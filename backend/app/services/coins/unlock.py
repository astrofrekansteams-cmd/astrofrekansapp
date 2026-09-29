"""One use of a plan-gated feature, paid with AstroCoins.

A route that would answer `premium_required` accepts the header
`X-Coin-Consumer-Ref` instead. The flow keeps coins safe:

1. ``gate = await coin_gate(...)`` - before the work: passes when the plan
   includes the feature, refuses with `premium_required` when no coins were
   offered, and with `insufficient_coins` when the balance is short.
2. The route does its work.
3. ``await gate.charge()`` then commit - after the work succeeded. A failure
   in step 2 never reaches the charge; a retry with the same reference is
   never charged twice (the ledger key is the reference).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationFailed
from app.db.models.user import User
from app.services.coins.catalog import spend_item
from app.services.coins.service import CoinService, InsufficientCoins
from app.services.features import (
    FEATURE_COIN_ITEMS,
    Feature,
    ensure_feature,
    has_feature,
)

COIN_REF_HEADER = "X-Coin-Consumer-Ref"
_REF = re.compile(r"^[A-Za-z0-9._:-]{8,80}$")


def coin_ref(request: Request | None) -> str | None:
    if request is None:
        return None
    ref = request.headers.get(COIN_REF_HEADER)
    if ref is None:
        return None
    if not _REF.match(ref):
        raise ValidationFailed(
            "Invalid coin reference.", details={"header": COIN_REF_HEADER}
        )
    return ref


@dataclass(slots=True)
class CoinGate:
    session: AsyncSession
    user: User
    feature: Feature
    item: str | None = None
    ref: str | None = None
    charged: int = 0

    @property
    def paid(self) -> bool:
        return self.item is not None

    async def charge(self) -> int:
        """Take the coins (idempotent per reference). Call after the work."""
        if self.item is None or self.ref is None or self.charged:
            return self.charged
        row = await CoinService(self.session).spend(
            self.user.id,
            items=[self.item],
            consumer_ref=f"feature:{self.feature.value}:{self.ref}",
            reference_id=self.feature.value,
        )
        self.charged = -row.amount
        return self.charged


async def coin_gate(
    session: AsyncSession,
    user: User,
    feature: Feature,
    request: Request | None,
) -> CoinGate:
    """Decide before the work whether it may run, and on what payment."""
    if has_feature(user.tier, feature):
        return CoinGate(session, user, feature)
    ref = coin_ref(request)
    item = FEATURE_COIN_ITEMS.get(feature)
    if ref is None or item is None:
        ensure_feature(user.tier, feature)  # raises premium_required
    price = spend_item(item).price  # type: ignore[union-attr]
    service = CoinService(session)
    if not await service.already_spent(user.id, f"feature:{feature.value}:{ref}"):
        wallet = await service.wallet(user.id)
        if wallet.balance < price:
            raise InsufficientCoins(
                details={"balance": wallet.balance, "required": price, "item": item}
            )
    return CoinGate(session, user, feature, item=item, ref=ref)
