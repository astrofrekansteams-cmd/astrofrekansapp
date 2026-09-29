"""Payments, entitlements, accounting and settlement.

Shape, in one breath:

* A **store purchase** is a fact the App Store or Google Play verified. It is
  the only thing that can create a digital **entitlement**.
* An **order line item** says what was sold and under which store-policy
  classification; **payment groups** say which rail must collect which lines.
* A **payment transaction** is an immutable record of money moving (or being
  refunded) at a provider. **Ledger entries** say where it went, balanced per
  currency, and are never updated.
* **Payouts** and **refund requests** are workflows on top of the ledger, with
  every irreversible step reserved for an administrator or a provider.

What is never stored: card data (FastAPI never sees any), raw Google purchase
tokens (a SHA-256 is enough to recognise one), App Store JWS payloads, or raw
webhook bodies. See docs/payment_architecture.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import UtcDateTime

JSONType = JSON().with_variant(JSONB(), "postgresql")


# ================================================================== catalogue


class StoreProduct(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A digital product, and what it maps to on each store.

    **No price.** The App Store and Play Console own prices, per storefront and
    currency; the client shows the store's localised price. A price stored here
    would be a number that is wrong somewhere.
    """

    __tablename__ = "store_products"
    __table_args__ = (
        UniqueConstraint("code", name="uq_store_products_code"),
        UniqueConstraint("apple_product_id", name="uq_store_products_apple"),
        UniqueConstraint("google_product_id", name="uq_store_products_google"),
        CheckConstraint(
            "product_type IN ('consumable', 'non_consumable', 'subscription')",
            name="ck_store_products_type",
        ),
        CheckConstraint("units_per_purchase >= 1", name="ck_store_products_units"),
    )

    code: Mapped[str] = mapped_column(String(80), nullable=False)
    product_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entitlement_code: Mapped[str] = mapped_column(String(80), nullable=False)
    units_per_purchase: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1"), nullable=False
    )
    # The catalogue service this unlocks, when it is an automated report.
    service_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    apple_product_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    google_product_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )


# ================================================================ purchases


class StorePurchase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A purchase the store has verified, owned by exactly one account.

    `purchase_key` is the store's identity for it: Apple's
    `originalTransactionId` for a subscription (renewals keep it), Apple's
    `transactionId` otherwise, and the SHA-256 of Google's purchase token.
    Unique per provider - so the same purchase can never be attached to a
    second account, which is what stops entitlement theft by replaying
    somebody else's transaction id.
    """

    __tablename__ = "store_purchases"
    __table_args__ = (
        UniqueConstraint("provider", "purchase_key", name="uq_store_purchases_key"),
        Index("ix_store_purchases_user", "user_id", "status"),
        Index("ix_store_purchases_original", "provider", "original_transaction_id"),
        CheckConstraint("provider IN ('apple', 'google')", name="ck_store_purchases_provider"),
        CheckConstraint(
            "environment IN ('production', 'sandbox')",
            name="ck_store_purchases_environment",
        ),
        CheckConstraint("quantity >= 1", name="ck_store_purchases_quantity"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(10), nullable=False)
    store_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("store_products.id", ondelete="RESTRICT"), nullable=False
    )
    # The store's own product id, as verified - kept for audit.
    store_product_ref: Mapped[str] = mapped_column(String(200), nullable=False)

    purchase_key: Mapped[str] = mapped_column(String(128), nullable=False)
    external_transaction_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    original_transaction_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    # Google only. The token itself is never stored: a hash recognises it, and
    # RTDN and the client both bring the token when it is needed.
    purchase_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False)
    environment: Mapped[str] = mapped_column(String(12), nullable=False)
    quantity: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1"), nullable=False
    )

    purchased_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    grace_until: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    auto_renewing: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Google: acknowledged / consumed at the store. Set only after the
    # entitlement was committed - the irreversible step goes last.
    acknowledged_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    store_consumed_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )


class UserEntitlement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Something a user may do, derived from a verified purchase.

    Never written from a client's say-so. A subscription entitlement mirrors
    its purchase's state; a credit is one unit of a consumable, used once;
    a permanent entitlement is a non-consumable.

    `uq_user_entitlements_unit` makes derivation idempotent: one purchase
    yields each of its units exactly once however many times it is verified.
    `uq_user_entitlements_consumption` makes consumption idempotent: the same
    consumer reference can use a credit once.
    """

    __tablename__ = "user_entitlements"
    __table_args__ = (
        UniqueConstraint(
            "store_purchase_id", "unit_index", name="uq_user_entitlements_unit"
        ),
        Index(
            "uq_user_entitlements_consumption",
            "user_id",
            "consumed_ref",
            unique=True,
            postgresql_where=text("consumed_ref IS NOT NULL"),
            sqlite_where=text("consumed_ref IS NOT NULL"),
        ),
        Index("ix_user_entitlements_lookup", "user_id", "entitlement_code", "status"),
        CheckConstraint(
            "kind IN ('subscription', 'credit', 'permanent')",
            name="ck_user_entitlements_kind",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entitlement_code: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    store_purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("store_purchases.id", ondelete="CASCADE"), nullable=True
    )
    unit_index: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    environment: Mapped[str] = mapped_column(String(12), nullable=False)

    status: Mapped[str] = mapped_column(String(30), nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    grace_until: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    auto_renewing: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    original_transaction_ref: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    # Whatever used the credit - a report's idempotency key, say. A retry with
    # the same reference finds the same consumption.
    consumed_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)


class PaymentProviderEvent(Base, UUIDPrimaryKeyMixin):
    """A store or provider notification we have already seen.

    For once-only processing and audit. Not the payload: an App Store JWS or a
    Pub/Sub message carries transaction details this table has no business
    keeping. A hash tells a replay from a collision.
    """

    __tablename__ = "payment_provider_events"
    __table_args__ = (
        UniqueConstraint(
            "provider", "external_event_id", name="uq_payment_provider_events_event"
        ),
        Index("ix_payment_provider_events_received", "received_at"),
    )

    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    transaction_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    environment: Mapped[str | None] = mapped_column(String(12), nullable=True)
    received_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(60), nullable=True)


# =================================================================== orders


class OrderLineItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One thing an order sells, with its own store-policy classification.

    A hybrid order is two lines - an AI pre-analysis (digital) and a live
    session (person-to-person) - and they are never squashed into one
    classification, because they may not be payable on the same rail.
    """

    __tablename__ = "order_line_items"
    __table_args__ = (
        Index("ix_order_line_items_order", "order_id"),
        CheckConstraint("quantity >= 1", name="ck_order_line_items_quantity"),
        CheckConstraint(
            "unit_amount_minor IS NULL OR unit_amount_minor >= 0",
            name="ck_order_line_items_unit",
        ),
        CheckConstraint(
            "total_minor IS NULL OR total_minor >= 0", name="ck_order_line_items_total"
        ),
        CheckConstraint(
            "tax_amount_minor IS NULL OR tax_amount_minor >= 0",
            name="ck_order_line_items_tax",
        ),
        CheckConstraint(
            "platform_fee_minor >= 0 AND expert_net_minor >= 0",
            name="ck_order_line_items_split",
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False
    )
    item_type: Mapped[str] = mapped_column(String(30), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    quantity: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1"), nullable=False
    )
    # NULL when the price belongs to a store (a store product line).
    unit_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payment_classification: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_rail: Mapped[str] = mapped_column(String(30), nullable=False)
    line_status: Mapped[str] = mapped_column(String(20), nullable=False)
    store_product_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # The B8 commission snapshot, attributed to this line. Only a live expert
    # line carries an expert share; a digital line's revenue is the platform's.
    commission_basis_points: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    platform_fee_minor: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default=text("0"), nullable=False
    )
    expert_net_minor: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default=text("0"), nullable=False
    )

    # Tax is a seam, not a calculation: nothing here invents a rate.
    tax_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tax_source: Mapped[str | None] = mapped_column(String(40), nullable=True)


class OrderPaymentGroup(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The lines one rail must collect, and whether it has.

    An order is paid only when every group is satisfied or not required. A
    group that is `blocked_review` stops the order: nobody may collect money
    for something whose classification has not been decided.
    """

    __tablename__ = "order_payment_groups"
    __table_args__ = (
        UniqueConstraint(
            "order_id", "classification", name="uq_order_payment_groups_class"
        ),
        CheckConstraint(
            "amount_minor IS NULL OR amount_minor >= 0",
            name="ck_order_payment_groups_amount",
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False
    )
    classification: Mapped[str] = mapped_column(String(30), nullable=False)
    # For store groups the rail depends on the device, and is set when a
    # purchase satisfies the group.
    rail: Mapped[str] = mapped_column(String(30), nullable=False)
    amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    satisfied_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    payment_intent_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    store_purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("store_purchases.id", ondelete="SET NULL"), nullable=True
    )


class PaymentIntent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An external-rail payment we asked a provider to collect.

    Store purchases do not get a fake intent: the store runs its own flow,
    and the verified purchase is the record.
    """

    __tablename__ = "payment_intents"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_payment_intents_idem"),
        UniqueConstraint(
            "provider", "external_reference", name="uq_payment_intents_external"
        ),
        Index("ix_payment_intents_order", "order_id"),
        CheckConstraint("amount_minor > 0", name="ck_payment_intents_amount"),
        CheckConstraint(
            "refunded_minor >= 0 AND refunded_minor <= amount_minor",
            name="ck_payment_intents_refunded",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_orders.id", ondelete="SET NULL"), nullable=True
    )
    payment_group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("order_payment_groups.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    rail: Mapped[str] = mapped_column(String(30), nullable=False)
    classification: Mapped[str] = mapped_column(String(30), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Cached from the transactions, under the intent's row lock. The
    # transactions are the truth; this makes the "not more than was paid"
    # check a constraint.
    refunded_minor: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default=text("0"), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


# ============================================================== accounting


class PaymentTransaction(Base, UUIDPrimaryKeyMixin):
    """Money that moved - or was reversed - at a provider. Append-only.

    A refund is a new row pointing at its charge, never an edit of the charge.
    `amount_minor` is NULL only for a store purchase whose price the store did
    not report (Google's purchase APIs do not); such a row posts nothing to the
    ledger, and store revenue is reconciled from the store's financial reports.
    """

    __tablename__ = "payment_transactions"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_transaction_ref",
            "type",
            name="uq_payment_transactions_external",
        ),
        Index("ix_payment_transactions_order", "order_id"),
        Index("ix_payment_transactions_intent", "payment_intent_id"),
        CheckConstraint(
            "amount_minor IS NULL OR amount_minor >= 0",
            name="ck_payment_transactions_amount",
        ),
    )

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    rail: Mapped[str] = mapped_column(String(30), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_orders.id", ondelete="SET NULL"), nullable=True
    )
    payment_intent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payment_intents.id", ondelete="SET NULL"), nullable=True
    )
    store_purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("store_purchases.id", ondelete="SET NULL"), nullable=True
    )
    related_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True
    )
    external_transaction_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    # A provider's fee, if the provider reports it. Never a store commission
    # guessed from a published rate.
    provider_fee_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    # Ids and codes only. Never a token, a JWS or a card detail.
    metadata_safe: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)


class LedgerEntry(Base, UUIDPrimaryKeyMixin):
    """One side of a balanced posting. Never updated, never deleted.

    Entries sharing a `journal_key` form one posting, and within a currency
    its debits equal its credits. The service refuses to write an unbalanced
    journal, and on Postgres a deferred constraint trigger refuses to commit
    one; another trigger refuses UPDATE and DELETE outright.

    `journal_key` is also the idempotency key: `charge:<txn id>`,
    `refund:<refund id>`, `release:<order id>`... A replayed event posts
    nothing twice.
    """

    __tablename__ = "ledger_entries"
    __table_args__ = (
        UniqueConstraint("journal_key", "line_no", name="uq_ledger_entries_line"),
        Index("ix_ledger_entries_account", "account_type", "account_id", "currency"),
        Index("ix_ledger_entries_order", "order_id"),
        CheckConstraint("amount_minor > 0", name="ck_ledger_entries_amount"),
        CheckConstraint(
            "direction IN ('debit', 'credit')", name="ck_ledger_entries_direction"
        ),
    )

    journal_key: Mapped[str] = mapped_column(String(120), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payment_transactions.id", ondelete="RESTRICT"), nullable=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_orders.id", ondelete="SET NULL"), nullable=True
    )
    account_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # The expert, for the expert accounts. NULL for the platform's own.
    account_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    direction: Mapped[str] = mapped_column(String(6), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)


# ============================================================== settlement


class ExpertPayout(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Money owed to an expert, on its way out. Nothing here sends money."""

    __tablename__ = "expert_payouts"
    __table_args__ = (
        Index("ix_expert_payouts_expert", "expert_id", "status"),
        CheckConstraint("amount_minor > 0", name="ck_expert_payouts_amount"),
    )

    expert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experts.id", ondelete="RESTRICT"), nullable=False
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[str] = mapped_column(String(40), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)


class RefundRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A request to give money back, and what the policy made of it.

    The policy's answer (`decision`) is advice. Money moves only when an
    administrator approves - or when a store already moved it, which is the
    one automatic case.
    """

    __tablename__ = "refund_requests"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_refund_requests_idem"),
        Index("ix_refund_requests_order", "order_id"),
        Index("ix_refund_requests_status", "status"),
        CheckConstraint("amount_minor > 0", name="ck_refund_requests_amount"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_orders.id", ondelete="SET NULL"), nullable=True
    )
    payment_intent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payment_intents.id", ondelete="SET NULL"), nullable=True
    )
    store_purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("store_purchases.id", ondelete="SET NULL"), nullable=True
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    actor: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decision_basis: Mapped[str | None] = mapped_column(String(80), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    refund_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
