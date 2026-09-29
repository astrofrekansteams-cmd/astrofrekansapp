"""The ledger: where money went, balanced and immutable.

Double-entry, per currency. Every posting is a set of lines under one
`journal_key` whose debits equal its credits; the service refuses to write an
unbalanced one and, on Postgres, a deferred constraint trigger refuses to
commit one. Rows are never updated or deleted - a reversal is a new journal.

Accounts and what their balance means (credit - debit for liabilities and
revenue, debit - credit for assets):

    STORE_CLEARING               asset      owed to us by a store
    EXTERNAL_PROVIDER_CLEARING   asset      held for us by the external provider
    PLATFORM_RECEIVABLE          asset      owed to us, not yet collected
    PLATFORM_REVENUE             revenue    ours: commission, digital sales
    EXPERT_PAYABLE_PENDING       liability  an expert's share, still on hold
    EXPERT_PAYABLE_AVAILABLE     liability  an expert's share, releasable
    REFUND_LIABILITY             liability  refunds approved but not yet paid out

There is no cross-currency netting anywhere: every balance is per currency,
and no journal mixes currencies. Converting currencies is out of scope.

Store fees are not posted. What Apple or Google keeps is not the platform's
commission, is not known at purchase time, and is not guessed from a published
rate: store revenue is posted gross and reconciled against the stores'
financial reports, which is a separate job.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.payments import LedgerEntry
from app.domain.payments import LedgerAccount, LedgerDirection, TransactionType

logger = get_logger(__name__)

DEBIT = LedgerDirection.DEBIT
CREDIT = LedgerDirection.CREDIT


class UnbalancedJournal(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class Posting:
    account: LedgerAccount
    direction: LedgerDirection
    amount_minor: int
    account_id: uuid.UUID | None = None


def split_proportionally(
    *, amount: int, already: int, gross: int, share: int
) -> int:
    """How much of `amount` belongs to a `share` of `gross`, cumulatively.

    Computed on the running total so that refunding a charge in several parts
    reverses its split *exactly* once everything is refunded: the parts can
    never drift from the whole by a rounding cent. Truncation favours the
    expert, as the original B8 split does.
    """
    if gross <= 0:
        return 0
    before = already * share // gross
    after = (already + amount) * share // gross
    return after - before


class LedgerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def post(
        self,
        *,
        journal_key: str,
        entry_type: TransactionType,
        currency: str,
        postings: list[Posting],
        payment_transaction_id: uuid.UUID | None = None,
        order_id: uuid.UUID | None = None,
        occurred_at: datetime | None = None,
    ) -> bool:
        """Write one balanced journal. Returns False if it was already written.

        Idempotent on `journal_key`: a replayed webhook, a retried request or
        two racing workers all converge on one posting.
        """
        lines = [p for p in postings if p.amount_minor != 0]
        for line in lines:
            if not isinstance(line.amount_minor, int) or line.amount_minor < 0:
                raise UnbalancedJournal(f"{journal_key}: amounts are positive integers")
        debits = sum(p.amount_minor for p in lines if p.direction is DEBIT)
        credits = sum(p.amount_minor for p in lines if p.direction is CREDIT)
        if debits != credits:
            raise UnbalancedJournal(f"{journal_key}: debits {debits} != credits {credits}")
        if not lines:
            return False

        if await self.session.scalar(
            select(LedgerEntry.id).where(LedgerEntry.journal_key == journal_key).limit(1)
        ):
            return False

        now = datetime.now(UTC)
        try:
            async with self.session.begin_nested():
                for number, line in enumerate(lines, start=1):
                    self.session.add(
                        LedgerEntry(
                            journal_key=journal_key,
                            line_no=number,
                            entry_type=entry_type.value,
                            payment_transaction_id=payment_transaction_id,
                            order_id=order_id,
                            account_type=line.account.value,
                            account_id=line.account_id,
                            direction=line.direction.value,
                            amount_minor=line.amount_minor,
                            currency=currency.upper(),
                            occurred_at=occurred_at or now,
                            created_at=now,
                        )
                    )
                await self.session.flush()
        except IntegrityError:
            # Somebody posted this journal between our check and our insert.
            return False

        logger.info(
            "ledger_posted",
            journal=journal_key.split(":", 1)[0],
            entry_type=entry_type.value,
            lines=len(lines),
            currency=currency.upper(),
            amount_minor=debits,
        )
        return True

    async def has_journal(self, journal_key: str) -> bool:
        return bool(
            await self.session.scalar(
                select(LedgerEntry.id).where(LedgerEntry.journal_key == journal_key).limit(1)
            )
        )

    async def balance(
        self,
        account: LedgerAccount,
        *,
        account_id: uuid.UUID | None = None,
        currency: str,
        order_id: uuid.UUID | None = None,
    ) -> int:
        """Credit-positive balance (liabilities, revenue).

        Negate for asset accounts.
        """
        signed = case(
            (LedgerEntry.direction == CREDIT.value, LedgerEntry.amount_minor),
            else_=-LedgerEntry.amount_minor,
        )
        statement = select(func.coalesce(func.sum(signed), 0)).where(
            LedgerEntry.account_type == account.value,
            LedgerEntry.currency == currency.upper(),
        )
        if account_id is not None:
            statement = statement.where(LedgerEntry.account_id == account_id)
        if order_id is not None:
            statement = statement.where(LedgerEntry.order_id == order_id)
        return int(await self.session.scalar(statement) or 0)

    async def expert_balances(self, expert_id: uuid.UUID) -> dict[str, dict[str, int]]:
        """Per currency: pending, available, and paid out.

        `available` may be negative: a refund or chargeback after the money
        was released is a debt the expert's next earnings net off. No
        collection is attempted - see docs/marketplace_settlement.md.
        """
        rows = await self.session.execute(
            select(
                LedgerEntry.currency,
                LedgerEntry.account_type,
                LedgerEntry.entry_type,
                LedgerEntry.direction,
                func.sum(LedgerEntry.amount_minor),
            )
            .where(
                LedgerEntry.account_id == expert_id,
                LedgerEntry.account_type.in_(
                    [
                        LedgerAccount.EXPERT_PAYABLE_PENDING.value,
                        LedgerAccount.EXPERT_PAYABLE_AVAILABLE.value,
                    ]
                ),
            )
            .group_by(
                LedgerEntry.currency,
                LedgerEntry.account_type,
                LedgerEntry.entry_type,
                LedgerEntry.direction,
            )
        )
        result: dict[str, dict[str, int]] = defaultdict(
            lambda: {"pending": 0, "available": 0, "paid": 0}
        )
        for currency, account, entry_type, direction, total in rows.all():
            signed = int(total) if direction == CREDIT.value else -int(total)
            bucket = "pending" if account == LedgerAccount.EXPERT_PAYABLE_PENDING.value else "available"
            result[currency][bucket] += signed
            if entry_type == TransactionType.PAYOUT.value and direction == DEBIT.value:
                result[currency]["paid"] += int(total)
        return dict(result)

    async def journal_is_balanced(self, journal_key: str) -> bool:
        rows = await self.session.execute(
            select(
                LedgerEntry.currency,
                func.sum(
                    case((LedgerEntry.direction == DEBIT.value, LedgerEntry.amount_minor), else_=0)
                ),
                func.sum(
                    case((LedgerEntry.direction == CREDIT.value, LedgerEntry.amount_minor), else_=0)
                ),
            )
            .where(LedgerEntry.journal_key == journal_key)
            .group_by(LedgerEntry.currency)
        )
        return all(int(d) == int(c) for _, d, c in rows.all())
