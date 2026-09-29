"""Prove the payment invariants that only a real database can settle.

    python -m scripts.payment_concurrency_check

SQLite serialises writers, so the unit suite proves the state machine and
nothing about races. On Postgres, from many connections at once:

1. **The same verified purchase, verified 10 times at once** -> one purchase,
   one entitlement, one charge, one ledger journal.
2. **Client verifications racing App Store notifications** for one
   transaction -> the same single purchase, entitlement and ledger effect.
3. **One refund approved 5 times at once** -> refunded once: one provider
   refund, one reversal, `refunded_minor` equal to the amount.
4. **One credit, 10 concurrent consumers** -> exactly one consumes it; and the
   same consumer reference used 10 times -> one consumption.
5. **The ledger triggers**: an UPDATE of an amount and an unbalanced journal
   are both refused by Postgres itself.

Uses the fake store (Apple's real verifier with a throwaway root) and the fake
external provider. Writes its own tagged rows and deletes exactly those.
Refuses SQLite and production.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, text

from app.core.config import settings
from app.db.models.payments import (
    LedgerEntry,
    PaymentIntent,
    PaymentProviderEvent,
    PaymentTransaction,
    RefundRequest,
    StorePurchase,
    UserEntitlement,
)
from app.db.models.chat import NotificationOutbox
from app.db.models.subscription import Subscription
from app.db.models.user import User, UserProfile
from app.db.session import get_session_factory
from app.domain.payments import (
    LedgerAccount,
    PaymentIntentStatus,
    RefundStatus,
    TransactionType,
)
from app.services.payments.entitlements import EntitlementService, NoCreditAvailable
from app.services.payments.ledger import CREDIT, DEBIT, LedgerService, Posting
from app.services.payments.providers.external import FakeExternalMarketplacePaymentProvider
from app.services.payments.providers.fakes import FakeAppleStoreProvider
from app.services.payments.purchases import StorePurchaseService
from app.services.payments.refunds import RefundNotReviewable, RefundService
from app.services.payments.store_notifications import StoreNotificationService

MARKER = "payment-concurrency-check"
PRODUCTS = {
    "premium_monthly": {"apple": "com.check.premium.monthly"},
    "natal_report": {"apple": "com.check.report.natal"},
}


async def make_user(factory) -> uuid.UUID:
    async with factory() as session:
        user = User(email=f"{MARKER}-{uuid.uuid4().hex[:8]}@example.com", password_hash=None,
                    is_active=True, is_email_verified=True)
        session.add(user)
        await session.flush()
        session.add(UserProfile(user_id=user.id, name="Check"))
        await session.commit()
        return user.id


async def counts(factory, user_id) -> dict[str, int]:
    async with factory() as session:
        purchases = await session.scalar(select(func.count()).select_from(StorePurchase).where(StorePurchase.user_id == user_id))
        entitlements = await session.scalar(select(func.count()).select_from(UserEntitlement).where(UserEntitlement.user_id == user_id))
        charges = await session.scalar(select(func.count()).select_from(PaymentTransaction).where(
            PaymentTransaction.user_id == user_id, PaymentTransaction.type == "charge"))
        journals = await session.scalar(
            select(func.count(func.distinct(LedgerEntry.journal_key))).where(
                LedgerEntry.payment_transaction_id.in_(
                    select(PaymentTransaction.id).where(PaymentTransaction.user_id == user_id))))
    return {"purchases": purchases, "entitlements": entitlements, "charges": charges, "journals": journals}


async def check_parallel_verify(factory, apple) -> bool:
    print("--- the same purchase verified 10 times at once ------------------")
    user_id = await make_user(factory)
    jws = apple.transaction(product_id=PRODUCTS["premium_monthly"]["apple"], app_account_token=str(user_id))

    async def verify():
        async with factory() as session:
            result = await StorePurchaseService(session).verify_apple(
                user_id, product_code="premium_monthly", signed_transaction=jws,
                transaction_id=None, provider=apple)
            await session.commit()
            return result.purchase.id

    ids = await asyncio.gather(*(verify() for _ in range(10)), return_exceptions=True)
    errors = [e for e in ids if isinstance(e, Exception)]
    found = await counts(factory, user_id)
    print(f"  results: {len(ids) - len(errors)} ok, {len(errors)} errors {Counter(type(e).__name__ for e in errors)}")
    print(f"  {found}")
    ok = found == {"purchases": 1, "entitlements": 1, "charges": 1, "journals": 1} and not errors
    print("PASS: one purchase, one entitlement, one ledger effect" if ok else "FAIL")
    return ok


async def check_notification_race(factory, apple) -> bool:
    print("\n--- client verifications racing App Store notifications ---------")
    user_id = await make_user(factory)
    jws = apple.transaction(product_id=PRODUCTS["premium_monthly"]["apple"], app_account_token=str(user_id))

    async def client_verify():
        async with factory() as session:
            await StorePurchaseService(session).verify_apple(
                user_id, product_code="premium_monthly", signed_transaction=jws,
                transaction_id=None, provider=apple)
            await session.commit()
            return "client"

    async def notification():
        payload = apple.notification(notification_type="SUBSCRIBED", signed_transaction=jws,
                                     notification_uuid=f"{MARKER}-{uuid.uuid4()}")
        async with factory() as session:
            outcome = await StoreNotificationService(session).apply_apple(
                apple.verify_notification(payload), payload.encode())
            await session.commit()
            return outcome

    results = await asyncio.gather(*([client_verify() for _ in range(5)] + [notification() for _ in range(5)]),
                                   return_exceptions=True)
    errors = [r for r in results if isinstance(r, Exception)]
    found = await counts(factory, user_id)
    print(f"  outcomes: {Counter(r if isinstance(r, str) else type(r).__name__ for r in results)}")
    print(f"  {found}")
    ok = found == {"purchases": 1, "entitlements": 1, "charges": 1, "journals": 1} and not errors
    print("PASS: converged on one purchase and one ledger effect" if ok else "FAIL")
    return ok


async def check_refund_once(factory) -> bool:
    print("\n--- one refund approved 5 times at once ---------------------------")
    user_id = await make_user(factory)
    provider = FakeExternalMarketplacePaymentProvider()
    expert_account = uuid.uuid4()
    async with factory() as session:
        intent = PaymentIntent(user_id=user_id, provider=provider.name, rail="external_marketplace",
                               classification="live_person_to_person", amount_minor=999, currency="TRY",
                               status=PaymentIntentStatus.PAID.value, idempotency_key=f"{MARKER}-intent",
                               external_reference=f"{MARKER}-ref-{uuid.uuid4().hex[:8]}")
        session.add(intent)
        await session.flush()
        now = datetime.now(UTC)
        charge = PaymentTransaction(provider=provider.name, rail="external_marketplace", user_id=user_id,
                                    payment_intent_id=intent.id, external_transaction_ref=f"{MARKER}-tx-{intent.id}",
                                    type="charge", amount_minor=999, currency="TRY", status="succeeded",
                                    occurred_at=now, created_at=now)
        session.add(charge)
        await session.flush()
        await LedgerService(session).post(
            journal_key=f"charge:{charge.id}", entry_type=TransactionType.CHARGE, currency="TRY",
            payment_transaction_id=charge.id,
            postings=[Posting(LedgerAccount.EXTERNAL_PROVIDER_CLEARING, DEBIT, 999),
                      Posting(LedgerAccount.PLATFORM_REVENUE, CREDIT, 199),
                      Posting(LedgerAccount.EXPERT_PAYABLE_PENDING, CREDIT, 800, account_id=expert_account)])
        request = RefundRequest(user_id=user_id, payment_intent_id=intent.id, amount_minor=999, currency="TRY",
                                reason="goodwill", actor="user", status=RefundStatus.MANUAL_REVIEW.value,
                                idempotency_key=f"{MARKER}-refund")
        session.add(request)
        await session.commit()
        intent_id, refund_id = intent.id, request.id

    async def approve():
        async with factory() as session:
            try:
                await RefundService(session).approve(refund_id, reviewer="check", provider=provider)
                await session.commit()
                return "approved"
            except RefundNotReviewable:
                return "not_reviewable"

    outcomes = Counter(await asyncio.gather(*(approve() for _ in range(5))))
    async with factory() as session:
        intent = await session.get(PaymentIntent, intent_id)
        reversals = await session.scalar(select(func.count()).select_from(PaymentTransaction).where(
            PaymentTransaction.payment_intent_id == intent_id, PaymentTransaction.type == "refund"))
    print(f"  outcomes: {dict(outcomes)}; provider refunds: {len(provider.refunds)}; "
          f"reversal rows: {reversals}; refunded_minor: {intent.refunded_minor}")
    ok = outcomes.get("approved") == 1 and len(provider.refunds) == 1 and reversals == 1 and intent.refunded_minor == 999
    print("PASS: refunded exactly once" if ok else "FAIL")
    return ok


async def check_credit(factory, apple) -> bool:
    print("\n--- one credit, 10 concurrent consumers ---------------------------")
    user_id = await make_user(factory)
    jws = apple.transaction(product_id=PRODUCTS["natal_report"]["apple"], type_="Consumable", expires_in=None)
    async with factory() as session:
        await StorePurchaseService(session).verify_apple(user_id, product_code="natal_report",
                                                         signed_transaction=jws, transaction_id=None, provider=apple)
        await session.commit()

    async def consume(ref: str):
        async with factory() as session:
            try:
                row = await EntitlementService(session).consume(user_id, "natal_report_credit", ref)
                await session.commit()
                return str(row.id)
            except NoCreditAvailable:
                return "none"

    distinct = Counter(await asyncio.gather(*(consume(f"{MARKER}-ref-{i}") for i in range(10))))

    # A second, fresh credit - so the same-reference race has something to
    # consume, and the answer is not vacuously "none".
    second = apple.transaction(product_id=PRODUCTS["natal_report"]["apple"], type_="Consumable", expires_in=None)
    async with factory() as session:
        await StorePurchaseService(session).verify_apple(user_id, product_code="natal_report",
                                                         signed_transaction=second, transaction_id=None,
                                                         provider=apple)
        await session.commit()
    same = Counter(await asyncio.gather(*(consume(f"{MARKER}-same") for _ in range(10))))
    print(f"  distinct refs: {dict(distinct)}")
    print(f"  same ref:      {dict(same)}")
    ok = (
        distinct.get("none") == 9 and len(distinct) == 2
        and len(same) == 1 and "none" not in same and sum(same.values()) == 10
    )
    print("PASS: one credit, consumed once" if ok else "FAIL")
    return ok


async def check_triggers(factory) -> bool:
    print("\n--- ledger triggers ------------------------------------------------")
    ok = True
    async with factory() as session:
        try:
            await session.execute(text(
                "UPDATE ledger_entries SET amount_minor = amount_minor + 1 "
                "WHERE id = (SELECT id FROM ledger_entries LIMIT 1)"))
            await session.commit()
            print("FAIL: an amount was rewritten")
            ok = False
        except Exception:  # noqa: BLE001
            await session.rollback()
            print("PASS: UPDATE of an amount refused")
    async with factory() as session:
        try:
            await session.execute(text(
                "INSERT INTO ledger_entries (id, journal_key, line_no, entry_type, account_type, direction, "
                "amount_minor, currency, occurred_at, created_at) VALUES "
                f"(gen_random_uuid(), '{MARKER}:unbalanced', 1, 'adjustment', 'platform_revenue', 'credit', "
                "1, 'TRY', now(), now())"))
            await session.commit()
            print("FAIL: an unbalanced journal committed")
            ok = False
        except Exception:  # noqa: BLE001
            await session.rollback()
            print("PASS: unbalanced journal refused at commit")
    return ok


async def cleanup(factory) -> None:
    async with factory() as session:
        await session.execute(text("SET LOCAL astro.ledger_maintenance = 'on'"))
        users = list(await session.scalars(select(User.id).where(User.email.like(f"{MARKER}-%"))))
        if users:
            txns = select(PaymentTransaction.id).where(PaymentTransaction.user_id.in_(users))
            await session.execute(delete(LedgerEntry).where(LedgerEntry.payment_transaction_id.in_(txns)))
            await session.execute(delete(RefundRequest).where(RefundRequest.user_id.in_(users)))
            await session.execute(delete(PaymentTransaction).where(PaymentTransaction.user_id.in_(users)))
            await session.execute(delete(PaymentIntent).where(PaymentIntent.user_id.in_(users)))
            await session.execute(delete(UserEntitlement).where(UserEntitlement.user_id.in_(users)))
            await session.execute(delete(StorePurchase).where(StorePurchase.user_id.in_(users)))
            await session.execute(delete(NotificationOutbox).where(NotificationOutbox.user_id.in_(users)))
            await session.execute(delete(Subscription).where(Subscription.user_id.in_(users)))
            await session.execute(delete(UserProfile).where(UserProfile.user_id.in_(users)))
            await session.execute(delete(User).where(User.id.in_(users)))
        await session.execute(delete(PaymentProviderEvent).where(PaymentProviderEvent.external_event_id.like(f"{MARKER}-%")))
        await session.commit()


async def main() -> int:
    if settings.database_url.startswith("sqlite"):
        print("SKIPPED: meaningless on SQLite.")
        return 2
    if settings.is_production:
        print("REFUSED: writes test rows.")
        return 1
    # In-process only: the fake store's product ids for this run.
    settings.store_product_ids = json.dumps(PRODUCTS)
    settings.store_provider = "fake"
    factory = get_session_factory()
    apple = FakeAppleStoreProvider()
    print(f"dialect : {settings.database_url.split('://', 1)[0]}\n")
    await cleanup(factory)
    ok = True
    try:
        ok &= await check_parallel_verify(factory, apple)
        ok &= await check_notification_race(factory, apple)
        ok &= await check_refund_once(factory)
        ok &= await check_credit(factory, apple)
        ok &= await check_triggers(factory)
    finally:
        await cleanup(factory)
        print("\ncleaned up")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
