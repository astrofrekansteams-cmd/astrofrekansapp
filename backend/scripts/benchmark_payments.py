"""What the payment domain's own work costs.

    python -m scripts.benchmark_payments [--iterations 100]

Store and provider latency is excluded on purpose: App Store Server API,
Play Developer API and the external provider are remote, regional and not
ours. What is measured is ours, on real Postgres:

* Apple JWS verification (Apple's library, chain + signature, OCSP off)
* purchase normalisation + apply (the idempotent write path)
* entitlement read (the `/billing/entitlements` query)
* ledger posting (a balanced three-line journal)
* order payment evaluation
* refund split calculation
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import statistics
import sys
import time
import uuid

import structlog
from sqlalchemy import delete, select, text

from app.core.config import settings
from app.db.models.payments import (
    LedgerEntry,
    PaymentTransaction,
    StorePurchase,
    UserEntitlement,
)
from app.db.models.subscription import Subscription
from app.db.models.user import User, UserProfile
from app.db.session import get_session_factory
from app.domain.payments import LedgerAccount, TransactionType
from app.services.payments.entitlements import EntitlementService
from app.services.payments.ledger import CREDIT, DEBIT, LedgerService, Posting, split_proportionally
from app.services.payments.providers.fakes import FakeAppleStoreProvider
from app.services.payments.purchases import StorePurchaseService

MARKER = "payment-benchmark"
PRODUCTS = {"premium_monthly": {"apple": "com.bench.premium.monthly"}}


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(int(len(ordered) * q), len(ordered) - 1)]


def report(label: str, samples: list[float]) -> None:
    print(f"  {label:<40} mean {statistics.mean(samples) * 1000:7.2f} ms   "
          f"p50 {pct(samples, 0.5) * 1000:7.2f}   p95 {pct(samples, 0.95) * 1000:7.2f}")


async def cleanup(factory) -> None:
    async with factory() as session:
        await session.execute(text("SET LOCAL astro.ledger_maintenance = 'on'"))
        users = list(await session.scalars(select(User.id).where(User.email.like(f"{MARKER}-%"))))
        await session.execute(delete(LedgerEntry).where(LedgerEntry.journal_key.like(f"{MARKER}:%")))
        if users:
            txns = select(PaymentTransaction.id).where(PaymentTransaction.user_id.in_(users))
            await session.execute(delete(LedgerEntry).where(LedgerEntry.payment_transaction_id.in_(txns)))
            await session.execute(delete(PaymentTransaction).where(PaymentTransaction.user_id.in_(users)))
            await session.execute(delete(UserEntitlement).where(UserEntitlement.user_id.in_(users)))
            await session.execute(delete(StorePurchase).where(StorePurchase.user_id.in_(users)))
            await session.execute(delete(Subscription).where(Subscription.user_id.in_(users)))
            await session.execute(delete(UserProfile).where(UserProfile.user_id.in_(users)))
            await session.execute(delete(User).where(User.id.in_(users)))
        await session.commit()


async def main(iterations: int) -> int:
    if settings.database_url.startswith("sqlite") or settings.is_production:
        print("Needs a non-production Postgres.")
        return 2
    logging.getLogger().setLevel(logging.WARNING)
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))
    settings.store_product_ids = json.dumps(PRODUCTS)
    settings.store_provider = "fake"

    factory = get_session_factory()
    apple = FakeAppleStoreProvider()
    await cleanup(factory)
    try:
        async with factory() as session:
            user = User(email=f"{MARKER}-{uuid.uuid4().hex[:6]}@example.com", password_hash=None,
                        is_active=True, is_email_verified=True)
            session.add(user)
            await session.flush()
            session.add(UserProfile(user_id=user.id, name="Bench"))
            await session.commit()
            user_id = user.id

        print(f"dialect    : {settings.database_url.split('://', 1)[0]}")
        print("stores     : fake transport, Apple's real verifier (OCSP off)")
        print(f"iterations : {iterations}\n")

        jws = [apple.transaction(product_id=PRODUCTS["premium_monthly"]["apple"]) for _ in range(iterations)]
        verify: list[float] = []
        for signed in jws:
            started = time.perf_counter()
            apple.verify_signed_transaction(signed)
            verify.append(time.perf_counter() - started)

        apply: list[float] = []
        for signed in jws:
            async with factory() as session:
                started = time.perf_counter()
                await StorePurchaseService(session).verify_apple(
                    user_id, product_code="premium_monthly", signed_transaction=signed,
                    transaction_id=None, provider=apple)
                await session.commit()
                apply.append(time.perf_counter() - started)

        reads: list[float] = []
        for _ in range(iterations):
            async with factory() as session:
                service = EntitlementService(session)
                started = time.perf_counter()
                rows = await service.for_user(user_id)
                [service.policy.grants_access(row) for row in rows]
                reads.append(time.perf_counter() - started)

        posts: list[float] = []
        for index in range(iterations):
            async with factory() as session:
                started = time.perf_counter()
                await LedgerService(session).post(
                    journal_key=f"{MARKER}:{index}", entry_type=TransactionType.CHARGE, currency="TRY",
                    postings=[Posting(LedgerAccount.EXTERNAL_PROVIDER_CLEARING, DEBIT, 999),
                              Posting(LedgerAccount.PLATFORM_REVENUE, CREDIT, 199),
                              Posting(LedgerAccount.EXPERT_PAYABLE_PENDING, CREDIT, 800, account_id=uuid.uuid4())])
                await session.commit()
                posts.append(time.perf_counter() - started)

        splits: list[float] = []
        for index in range(iterations * 100):
            started = time.perf_counter()
            split_proportionally(amount=333, already=index % 600, gross=999, share=800)
            splits.append(time.perf_counter() - started)

        print("provider-independent")
        report("Apple JWS verification (chain + ES256)", verify)
        report("verify + apply purchase (idempotent write)", apply)
        report("entitlement read + policy", reads)
        report("ledger posting (3 lines, balanced)", posts)
        report("refund split calculation", splits)
        print("\nExcluded: App Store Server API, Play Developer API and the external\n"
              "provider - remote, regional, and not this service's latency.")
        return 0
    finally:
        await cleanup(factory)
        print("\ncleaned up")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=100)
    sys.exit(asyncio.run(main(parser.parse_args().iterations)))
