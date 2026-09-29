"""Prove paid-report atomicity against a real Postgres.

    python -m scripts.report_payment_concurrency_check

SQLite serialises writers, so the unit suite proves the state machine and
nothing about races. Here the real endpoints run in-process (ASGI) against
Postgres, many requests at once:

1. **Same `consumer_ref`, 10 concurrent synchronous `POST /ai/reports`** with
   two credits available -> one job, one consumed credit, one report; the
   other credit untouched.
2. **Same `consumer_ref`, 10 concurrent background requests** -> one job, one
   reservation; the worker delivers once.
3. **10 distinct references, one credit** -> exactly one request succeeds,
   nine get `report_payment_required`, one credit consumed.

The AI provider is the fake (no model calls) and the store is the fake Apple
verifier (Apple's real `SignedDataVerifier`, throwaway root). Rate limiting is
switched off in-process. Every row belongs to marker accounts and is deleted
at the end. Refuses SQLite and production.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from collections import Counter

import httpx
from sqlalchemy import delete, func, select, text

from app.core.config import settings
from app.db.models.ai import AIReport, AIReportJob
from app.db.models.chat import NotificationOutbox
from app.db.models.payments import (
    LedgerEntry,
    PaymentTransaction,
    StorePurchase,
    UserEntitlement,
)
from app.db.models.subscription import Subscription
from app.db.models.user import User
from app.db.session import get_session_factory
from app.services.ai import factory as ai_factory
from app.services.ai.fake_provider import FakeAIProvider
from app.services.ai.queue import claim_next_job
from app.services.payments.providers.fakes import FakeAppleStoreProvider
from app.services.payments.purchases import StorePurchaseService
from app.workers.ai_report_worker import AIReportWorker

MARKER = "report-payment-check"
API = "/api/v1"
NATAL_PRODUCT = "com.check.report.natal"
CONCURRENCY = 10


async def register(client: httpx.AsyncClient) -> tuple[uuid.UUID, dict]:
    response = await client.post(
        f"{API}/auth/register",
        json={
            "email": f"{MARKER}-{uuid.uuid4().hex[:8]}@example.com",
            "password": "Str0ngPassphrase!",
            "name": "Check",
            "birth_date": "1990-04-04",
            "birth_time": "11:00:00",
            "birth_place": "Istanbul",
        },
    )
    response.raise_for_status()
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    me = (await client.get(f"{API}/auth/me", headers=headers)).json()
    return uuid.UUID(me["id"]), headers


async def buy_credit(factory, apple: FakeAppleStoreProvider, user_id: uuid.UUID) -> None:
    jws = apple.transaction(
        product_id=NATAL_PRODUCT,
        type_="Consumable",
        expires_in=None,
        transaction_id=f"{MARKER}-{uuid.uuid4().hex[:10]}",
        app_account_token=str(user_id),
    )
    async with factory() as session:
        await StorePurchaseService(session).verify_apple(
            user_id,
            product_code="natal_report",
            signed_transaction=jws,
            transaction_id=None,
            provider=apple,
        )
        await session.commit()


async def state(factory, user_id: uuid.UUID) -> dict:
    async with factory() as session:
        jobs = await session.scalar(
            select(func.count()).select_from(AIReportJob).where(AIReportJob.user_id == user_id)
        )
        reports = await session.scalar(
            select(func.count()).select_from(AIReport).where(
                AIReport.user_id == user_id, AIReport.status == "completed"
            )
        )
        credits = Counter(
            await session.scalars(
                select(UserEntitlement.status).where(
                    UserEntitlement.user_id == user_id,
                    UserEntitlement.kind == "credit",
                )
            )
        )
    return {"jobs": jobs, "completed_reports": reports, "credits": dict(credits)}


async def fire(client, headers, bodies) -> Counter:
    responses = await asyncio.gather(
        *(client.post(f"{API}/ai/reports", headers=headers, json=body) for body in bodies)
    )
    outcome = Counter()
    for response in responses:
        code = response.json().get("error", {}).get("code") if response.status_code >= 400 else None
        outcome[f"{response.status_code}{':' + code if code else ''}"] += 1
    return outcome


async def check_same_ref_sync(client, factory, apple) -> bool:
    print("--- same consumer_ref, 10 concurrent synchronous requests --------")
    user_id, headers = await register(client)
    await buy_credit(factory, apple, user_id)
    await buy_credit(factory, apple, user_id)
    body = {"report_type": "natal", "consumer_ref": "same-ref-sync-01"}
    outcome = await fire(client, headers, [body] * CONCURRENCY)
    found = await state(factory, user_id)
    print(f"  responses: {dict(outcome)}")
    print(f"  {found}")
    ok = (
        found == {"jobs": 1, "completed_reports": 1, "credits": {"consumed": 1, "active": 1}}
        and set(outcome) <= {"200", "202"}
    )
    print("PASS: one job, one report, one credit consumed" if ok else "FAIL")
    return ok


async def check_same_ref_background(client, factory, apple) -> bool:
    print("\n--- same consumer_ref, 10 concurrent background requests ---------")
    user_id, headers = await register(client)
    await buy_credit(factory, apple, user_id)
    body = {"report_type": "natal", "consumer_ref": "same-ref-bg-0001", "background": True}
    outcome = await fire(client, headers, [body] * CONCURRENCY)
    queued = await state(factory, user_id)
    async with factory() as session:
        job = await claim_next_job(session, worker_id=f"{MARKER}-worker")
        if job is not None:
            await AIReportWorker(worker_id=f"{MARKER}-worker").process(session, job)
    found = await state(factory, user_id)
    print(f"  responses: {dict(outcome)}")
    print(f"  queued : {queued}")
    print(f"  after  : {found}")
    ok = (
        queued == {"jobs": 1, "completed_reports": 0, "credits": {"reserved": 1}}
        and found == {"jobs": 1, "completed_reports": 1, "credits": {"consumed": 1}}
        and set(outcome) == {"202"}
    )
    print("PASS: one reservation, delivered once" if ok else "FAIL")
    return ok


async def check_distinct_refs_one_credit(client, factory, apple) -> bool:
    print("\n--- 10 distinct references, one credit ---------------------------")
    user_id, headers = await register(client)
    await buy_credit(factory, apple, user_id)
    bodies = [
        {"report_type": "natal", "consumer_ref": f"distinct-ref-{index:03d}"}
        for index in range(CONCURRENCY)
    ]
    outcome = await fire(client, headers, bodies)
    found = await state(factory, user_id)
    print(f"  responses: {dict(outcome)}")
    print(f"  {found}")
    succeeded = outcome["200"] + outcome["202"]
    ok = (
        succeeded == 1
        and outcome["402:report_payment_required"] == CONCURRENCY - 1
        and found == {"jobs": 1, "completed_reports": 1, "credits": {"consumed": 1}}
    )
    print("PASS: exactly one operation paid and succeeded" if ok else "FAIL")
    return ok


async def cleanup(factory) -> None:
    async with factory() as session:
        await session.execute(text("SET LOCAL astro.ledger_maintenance = 'on'"))
        users = list(await session.scalars(select(User.id).where(User.email.like(f"{MARKER}-%"))))
        if users:
            txns = select(PaymentTransaction.id).where(PaymentTransaction.user_id.in_(users))
            await session.execute(delete(LedgerEntry).where(LedgerEntry.payment_transaction_id.in_(txns)))
            await session.execute(delete(PaymentTransaction).where(PaymentTransaction.user_id.in_(users)))
            await session.execute(delete(AIReportJob).where(AIReportJob.user_id.in_(users)))
            await session.execute(delete(AIReport).where(AIReport.user_id.in_(users)))
            await session.execute(delete(UserEntitlement).where(UserEntitlement.user_id.in_(users)))
            await session.execute(delete(StorePurchase).where(StorePurchase.user_id.in_(users)))
            await session.execute(delete(NotificationOutbox).where(NotificationOutbox.user_id.in_(users)))
            await session.execute(delete(Subscription).where(Subscription.user_id.in_(users)))
            await session.execute(delete(User).where(User.id.in_(users)))
        await session.commit()


async def main() -> int:
    if settings.database_url.startswith("sqlite"):
        print("SKIPPED: meaningless on SQLite.")
        return 2
    if settings.is_production:
        print("REFUSED: writes test rows.")
        return 1

    # In-process only.
    settings.ai_provider = "fake"
    settings.rate_limit_enabled = False
    settings.store_provider = "fake"
    settings.store_product_ids = json.dumps({"natal_report": {"apple": NATAL_PRODUCT}})
    ai_factory.set_ai_provider(FakeAIProvider())

    from app.main import app

    factory = get_session_factory()
    apple = FakeAppleStoreProvider()
    print(f"dialect : {settings.database_url.split('://', 1)[0]}\n")
    await cleanup(factory)
    ok = True
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://check") as client:
            ok &= await check_same_ref_sync(client, factory, apple)
            ok &= await check_same_ref_background(client, factory, apple)
            ok &= await check_distinct_refs_one_credit(client, factory, apple)
    finally:
        await cleanup(factory)
        print("\ncleaned up")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
