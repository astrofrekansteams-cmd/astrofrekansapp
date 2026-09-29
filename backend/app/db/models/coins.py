"""AstroCoin: a small in-app balance, kept as an append-only ledger.

* `coin_wallets` holds one balance per user. It is a cache of the ledger,
  updated in the same transaction as each ledger row, under a row lock.
* `coin_transactions` is the ledger. Rows are never updated or deleted. Each
  carries an idempotency key that is unique per user, so a retried request -
  a double tap, a replayed store notification, an ad callback delivered
  twice - lands at most once.

What earns coins is decided on the server only: a verified store purchase, a
verified rewarded ad, the monthly plan bonus, or a refund of a spend whose
work failed. A client can never say "add coins".
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

JSONType = JSON().with_variant(JSONB(), "postgresql")


class CoinWallet(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "coin_wallets"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_coin_wallets_user"),
        CheckConstraint("balance >= 0", name="ck_coin_wallets_balance"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lifetime_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lifetime_spent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CoinTransaction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "coin_transactions"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "idempotency_key", name="uq_coin_transactions_idempotency"
        ),
        CheckConstraint("amount <> 0", name="ck_coin_transactions_amount"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Positive = credit, negative = debit.
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    # purchase / ad_reward / monthly_bonus / spend / refund / purchase_reversal
    kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # What it was for: a product code, a spend item code, "YYYY-MM", ...
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
