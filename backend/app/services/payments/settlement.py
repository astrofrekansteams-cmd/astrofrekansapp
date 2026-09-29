"""Expert settlement: pending -> available -> paid out. Nothing here sends money.

An expert's share of a verified live-session payment is credited to
EXPERT_PAYABLE_PENDING when the payment is verified. It moves to
EXPERT_PAYABLE_AVAILABLE when the consultation is COMPLETED **and** the
settlement hold has passed - a window in which refunds and chargebacks are
most likely. The hold (`EXPERT_SETTLEMENT_HOLD_DAYS`) has no default: it is a
business decision, and until it is made nothing is released automatically.
An administrator can release by hand.

Payouts are records of an intent to pay. No payout provider exists, so:

* an **expert** can see their balances and payouts, and cannot create,
  approve or mark one paid;
* an **administrator** (service methods only - there is no admin surface yet)
  creates, approves, and marks paid or failed once a provider or a bank says
  so. Only PAID posts to the ledger.

Balances are derived from the ledger, never stored. `available` may go
negative: a refund or chargeback after release is a debt that future earnings
net off. There is no collection process - see docs/marketplace_settlement.md.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, NotFound
from app.core.logging import get_logger
from app.db.models.marketplace import Expert, ServiceOrder
from app.db.models.payments import ExpertPayout, LedgerEntry
from app.domain.marketplace import OrderStatus
from app.domain.payments import (
    PAYOUT_TRANSITIONS,
    LedgerAccount,
    PayoutStatus,
    TransactionType,
)
from app.services.payments.ledger import CREDIT, DEBIT, LedgerService, Posting

logger = get_logger(__name__)


class PayoutNotAllowed(AppError):
    status_code = 409
    code = "payout_not_allowed"
    message = "That payout change is not allowed."


class SettlementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ledger = LedgerService(session)

    @property
    def _locks(self) -> bool:
        bind = self.session.bind
        return bind is not None and bind.dialect.name != "sqlite"

    # ============================================================ release

    async def _pending_by_order(self, expert_id: uuid.UUID) -> dict[tuple[uuid.UUID, str], int]:
        rows = await self.session.execute(
            select(LedgerEntry.order_id, LedgerEntry.currency, LedgerEntry.direction, LedgerEntry.amount_minor)
            .where(
                LedgerEntry.account_id == expert_id,
                LedgerEntry.account_type == LedgerAccount.EXPERT_PAYABLE_PENDING.value,
                LedgerEntry.order_id.is_not(None),
            )
        )
        totals: dict[tuple[uuid.UUID, str], int] = {}
        for order_id, currency, direction, amount in rows.all():
            signed = amount if direction == CREDIT.value else -amount
            totals[(order_id, currency)] = totals.get((order_id, currency), 0) + signed
        return totals

    async def release_order(self, order: ServiceOrder, *, force: bool = False, now: datetime | None = None) -> int:
        """Move an order's pending share to available, if it is due. Idempotent."""
        now = now or datetime.now(UTC)
        if order.expert_id is None:
            return 0
        if not force:
            if order.status != OrderStatus.COMPLETED.value or order.completed_at is None:
                return 0
            hold = settings.expert_settlement_hold_days
            if hold is None:
                return 0  # no business decision yet: nothing releases by itself
            completed = order.completed_at if order.completed_at.tzinfo else order.completed_at.replace(tzinfo=UTC)
            if completed + timedelta(days=hold) > now:
                return 0
        released = 0
        pending = await self._pending_by_order(order.expert_id)
        for (order_id, currency), amount in pending.items():
            if order_id != order.id or amount <= 0:
                continue
            if await self.ledger.post(
                journal_key=f"release:{order.id}:{currency}",
                entry_type=TransactionType.SETTLEMENT_RELEASE,
                currency=currency,
                order_id=order.id,
                postings=[
                    Posting(LedgerAccount.EXPERT_PAYABLE_PENDING, DEBIT, amount, account_id=order.expert_id),
                    Posting(LedgerAccount.EXPERT_PAYABLE_AVAILABLE, CREDIT, amount, account_id=order.expert_id),
                ],
            ):
                released += amount
        if released:
            logger.info("settlement_released", order_id=str(order.id), expert_id=str(order.expert_id))
        return released

    async def release_due(self, expert_id: uuid.UUID, *, now: datetime | None = None) -> int:
        """Release every completed order of this expert whose hold has passed."""
        order_ids = {order_id for (order_id, _), amount in (await self._pending_by_order(expert_id)).items() if amount > 0}
        total = 0
        for order_id in order_ids:
            order = await self.session.get(ServiceOrder, order_id)
            if order is not None:
                total += await self.release_order(order, now=now)
        return total

    # ============================================================ reading

    async def balances(self, expert_id: uuid.UUID) -> dict[str, dict[str, int]]:
        await self.release_due(expert_id)
        return await self.ledger.expert_balances(expert_id)

    async def payouts(self, expert_id: uuid.UUID) -> list[ExpertPayout]:
        return list(
            await self.session.scalars(
                select(ExpertPayout)
                .where(ExpertPayout.expert_id == expert_id)
                .order_by(ExpertPayout.created_at.desc())
            )
        )

    # ============================================================== admin
    #
    # No route calls these. They are the surface a future admin tool uses.

    async def create_payout(
        self, expert_id: uuid.UUID, *, amount_minor: int, currency: str, created_by: str
    ) -> ExpertPayout:
        # Serialise payouts per expert so two cannot both spend one balance.
        statement = select(Expert).where(Expert.id == expert_id)
        if self._locks:
            statement = statement.with_for_update()
        if await self.session.scalar(statement) is None:
            raise NotFound("Expert not found.")
        if not isinstance(amount_minor, int) or amount_minor <= 0:
            raise PayoutNotAllowed("A payout must be a positive amount.")
        available = (await self.ledger.expert_balances(expert_id)).get(currency.upper(), {}).get("available", 0)
        committed = sum(
            await self.session.scalars(
                select(ExpertPayout.amount_minor).where(
                    ExpertPayout.expert_id == expert_id,
                    ExpertPayout.currency == currency.upper(),
                    ExpertPayout.status.in_(
                        [PayoutStatus.PENDING.value, PayoutStatus.APPROVED.value, PayoutStatus.PROCESSING.value]
                    ),
                )
            )
        )
        if amount_minor > available - committed:
            raise PayoutNotAllowed(
                "The payout exceeds the available balance.",
                details={"available_minor": max(available - committed, 0)},
            )
        payout = ExpertPayout(
            expert_id=expert_id,
            amount_minor=amount_minor,
            currency=currency.upper(),
            status=PayoutStatus.PENDING.value,
            created_by=created_by[:40],
        )
        self.session.add(payout)
        await self.session.flush()
        logger.info("payout_created", payout_id=str(payout.id), expert_id=str(expert_id))
        return payout

    async def _transition(self, payout_id: uuid.UUID, target: PayoutStatus) -> ExpertPayout:
        statement = select(ExpertPayout).where(ExpertPayout.id == payout_id)
        if self._locks:
            statement = statement.with_for_update()
        payout = await self.session.scalar(statement)
        if payout is None:
            raise NotFound("Payout not found.")
        current = PayoutStatus(payout.status)
        if target not in PAYOUT_TRANSITIONS[current]:
            raise PayoutNotAllowed(details={"from": current.value, "to": target.value})
        payout.status = target.value
        return payout

    async def approve(self, payout_id: uuid.UUID, *, admin: str) -> ExpertPayout:
        payout = await self._transition(payout_id, PayoutStatus.APPROVED)
        payout.approved_by = admin[:40]
        payout.approved_at = datetime.now(UTC)
        await self.session.flush()
        return payout

    async def start_processing(self, payout_id: uuid.UUID, *, provider: str) -> ExpertPayout:
        payout = await self._transition(payout_id, PayoutStatus.PROCESSING)
        payout.provider = provider[:30]
        await self.session.flush()
        return payout

    async def mark_paid(self, payout_id: uuid.UUID, *, external_reference: str) -> ExpertPayout:
        """Only when a provider or a bank confirms. Posts to the ledger once."""
        payout = await self._transition(payout_id, PayoutStatus.PAID)
        payout.external_reference = external_reference[:128]
        payout.paid_at = datetime.now(UTC)
        await self.session.flush()
        await self.ledger.post(
            journal_key=f"payout:{payout.id}",
            entry_type=TransactionType.PAYOUT,
            currency=payout.currency,
            postings=[
                Posting(LedgerAccount.EXPERT_PAYABLE_AVAILABLE, DEBIT, payout.amount_minor, account_id=payout.expert_id),
                Posting(LedgerAccount.EXTERNAL_PROVIDER_CLEARING, CREDIT, payout.amount_minor),
            ],
        )
        return payout

    async def mark_failed(self, payout_id: uuid.UUID, *, reason: str) -> ExpertPayout:
        payout = await self._transition(payout_id, PayoutStatus.FAILED)
        payout.failure_reason = reason[:120]
        await self.session.flush()
        return payout

    async def cancel(self, payout_id: uuid.UUID) -> ExpertPayout:
        payout = await self._transition(payout_id, PayoutStatus.CANCELLED)
        await self.session.flush()
        return payout
