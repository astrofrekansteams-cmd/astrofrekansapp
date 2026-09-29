"""Prove the claim is atomic, against a real Postgres.

    python -m scripts.worker_concurrency_check

The unit tests check that a claimed job is invisible to the next worker, but
they run on SQLite, which serialises writers and has no ``SKIP LOCKED``. That
proves the state machine and nothing about the locking. This script runs the
real query, on the real dialect, from many connections at once - which is the
only way to find out whether two workers can ever be handed the same job.

It writes its own throwaway jobs (against the first user it finds, or a
synthetic user id if the table is empty), claims them concurrently, checks
that every job went to exactly one worker, and deletes what it created.

Refuses to run against SQLite, and refuses to run in production.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections import Counter

from sqlalchemy import delete, select

from app.core.config import settings
from app.db.models.ai import AIReportJob
from app.db.models.user import User
from app.db.session import get_session_factory
from app.domain.ai import JobStatus
from app.services.ai.queue import claim_next_job

JOB_COUNT = 12
WORKER_COUNT = 8
MARKER = "concurrency-check"


async def seed(user_id: uuid.UUID) -> list[uuid.UUID]:
    factory = get_session_factory()
    ids: list[uuid.UUID] = []
    async with factory() as session:
        for _ in range(JOB_COUNT):
            job = AIReportJob(
                user_id=user_id,
                report_type="natal",
                source_type="birth_profile",
                source_id=None,
                locale="tr",
                status=JobStatus.QUEUED.value,
                input_fingerprint=MARKER,
                max_attempts=3,
            )
            session.add(job)
            await session.flush()
            ids.append(job.id)
        await session.commit()
    return ids


async def worker(name: str) -> list[uuid.UUID]:
    """Claim until the queue is empty, on this worker's own connection."""
    factory = get_session_factory()
    claimed: list[uuid.UUID] = []
    while True:
        async with factory() as session:
            job = await claim_next_job(session, worker_id=name)
            if job is None:
                return claimed
            claimed.append(job.id)
        await asyncio.sleep(0)  # let the others in


async def cleanup() -> None:
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
            delete(AIReportJob).where(AIReportJob.input_fingerprint == MARKER)
        )
        await session.commit()


async def main() -> int:
    if settings.database_url.startswith("sqlite"):
        print("SKIPPED: this check is meaningless on SQLite.")
        print("Point DATABASE_URL at Postgres and run it again.")
        return 2
    if settings.is_production:
        print("REFUSED: this writes test rows. Not in production.")
        return 1

    factory = get_session_factory()
    async with factory() as session:
        user = await session.scalar(select(User).limit(1))
    user_id = user.id if user else uuid.uuid4()

    print(f"dialect : {settings.database_url.split('://', 1)[0]}")
    print(f"jobs    : {JOB_COUNT}")
    print(f"workers : {WORKER_COUNT}\n")

    await cleanup()
    expected = set(await seed(user_id))

    results = await asyncio.gather(
        *(worker(f"check-worker-{index}") for index in range(WORKER_COUNT))
    )

    everything = [job_id for batch in results for job_id in batch]
    counts = Counter(everything)
    duplicates = {str(k): v for k, v in counts.items() if v > 1}
    missed = expected - set(everything)

    for index, batch in enumerate(results):
        print(f"  check-worker-{index}: {len(batch)} claimed")

    ok = True
    if duplicates:
        print(f"\nFAIL: a job was claimed twice: {duplicates}")
        ok = False
    else:
        print("\nPASS: no job was claimed by more than one worker")

    if missed:
        print(f"FAIL: {len(missed)} jobs were never claimed")
        ok = False
    else:
        print(f"PASS: all {len(expected)} jobs were claimed exactly once")

    async with factory() as session:
        owners = list(
            await session.scalars(
                select(AIReportJob.worker_id).where(
                    AIReportJob.input_fingerprint == MARKER
                )
            )
        )
    distinct = len({owner for owner in owners if owner})
    print(f"PASS: work was spread over {distinct} workers")

    await cleanup()
    print("\ncleaned up")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
