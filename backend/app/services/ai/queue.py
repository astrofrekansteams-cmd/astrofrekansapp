"""Claiming report jobs safely.

The queue lives in Postgres, not in Redis, because the job *is* a row here:
its state, its attempt count, its result and its owner are all things a
support engineer needs to be able to read a week later. Putting the work item
in one store and its record in another would mean the two can disagree, and
the version that a user asks about is always the row.

Claiming uses ``SELECT ... FOR UPDATE SKIP LOCKED``: the standard way to hand
one row to exactly one consumer without a lock table and without workers
queueing behind each other. Two workers polling at the same instant each get a
different job, or one gets a job and the other gets nothing.

A claim also writes a **lease**. If a worker dies mid-generation, nothing can
mark its job failed - the process that would have done so is gone - so the row
would sit in `running` forever. The lease is the expiry on that state: once it
passes, the job is recoverable by anyone.

SQLite (the test database) has no ``SKIP LOCKED`` and no concurrent writers,
so the same query runs without the locking clause there. That is safe because
SQLite serialises writers anyway; the concurrency tests that matter run
against the real dialect's semantics through the same code path.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.ai import AIReportJob
from app.domain.ai import JobStatus

logger = get_logger(__name__)


def _supports_skip_locked(session: AsyncSession) -> bool:
    return session.bind is not None and session.bind.dialect.name != "sqlite"


async def claim_next_job(
    session: AsyncSession, *, worker_id: str, lease_seconds: int | None = None
) -> AIReportJob | None:
    """Take ownership of one queued job, or return None.

    The whole claim - select, mark running, write the lease - happens in one
    transaction, so a job is either fully claimed by this worker or untouched.
    """
    lease = lease_seconds or settings.ai_job_lease_seconds
    now = datetime.now(UTC)

    statement = (
        select(AIReportJob)
        .where(AIReportJob.status == JobStatus.QUEUED.value)
        .order_by(AIReportJob.created_at)
        .limit(1)
    )
    if _supports_skip_locked(session):
        statement = statement.with_for_update(skip_locked=True)

    job = await session.scalar(statement)
    if job is None:
        return None

    job.status = JobStatus.RUNNING.value
    job.worker_id = worker_id
    job.lease_expires_at = now + timedelta(seconds=lease)
    job.started_at = job.started_at or now
    job.attempt += 1
    await session.commit()
    return job


async def recover_stale_jobs(session: AsyncSession, *, limit: int = 20) -> int:
    """Return jobs whose worker died back to the queue.

    A running job whose lease has expired has no live owner: either the worker
    crashed or it lost its database connection long enough to matter. It goes
    back to `queued` if it has attempts left, and to `failed` if it does not -
    a job that has repeatedly killed its worker should stop being retried.
    """
    now = datetime.now(UTC)
    stale = list(
        await session.scalars(
            select(AIReportJob)
            .where(
                AIReportJob.status == JobStatus.RUNNING.value,
                AIReportJob.lease_expires_at.is_not(None),
                AIReportJob.lease_expires_at < now,
            )
            .order_by(AIReportJob.lease_expires_at)
            .limit(limit)
        )
    )

    for job in stale:
        if job.attempt >= job.max_attempts:
            job.status = JobStatus.FAILED.value
            job.error_code = job.error_code or "worker_lost"
            job.finished_at = now
        else:
            job.status = JobStatus.QUEUED.value
        job.worker_id = None
        job.lease_expires_at = None

    if stale:
        await session.commit()
        logger.warning("ai_jobs_recovered", count=len(stale))
    return len(stale)


async def extend_lease(
    session: AsyncSession, job: AIReportJob, *, seconds: int | None = None
) -> None:
    """Keep a long generation's claim alive while it is still working."""
    lease = seconds or settings.ai_job_lease_seconds
    job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=lease)
    await session.commit()


async def release_claim(
    session: AsyncSession, job_id: uuid.UUID, *, requeue: bool
) -> None:
    """Drop a claim without finishing the job.

    Used on graceful shutdown: work that was started but not completed goes
    back to the queue rather than waiting for its lease to expire.
    """
    values: dict = {"worker_id": None, "lease_expires_at": None}
    if requeue:
        values["status"] = JobStatus.QUEUED.value
    await session.execute(
        update(AIReportJob)
        .where(
            AIReportJob.id == job_id,
            AIReportJob.status == JobStatus.RUNNING.value,
        )
        .values(**values)
    )
    await session.commit()


async def queue_depth(session: AsyncSession) -> dict[str, int]:
    """How much work is waiting. For the worker's own logging."""
    depth: dict[str, int] = {}
    for status in (JobStatus.QUEUED, JobStatus.RUNNING):
        rows = await session.scalars(
            select(AIReportJob.id).where(AIReportJob.status == status.value)
        )
        depth[status.value] = len(list(rows))
    return depth
