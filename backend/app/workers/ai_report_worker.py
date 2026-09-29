"""The report job consumer.

    python -m app.workers.ai_report_worker

One process, one loop: recover jobs whose worker died, claim the oldest queued
job, run it, repeat. Several of these can run at once - the claim is atomic
(see `app/services/ai/queue.py`), so the same job is never generated twice.

Why a separate process rather than FastAPI's `BackgroundTasks`: a premium
report can take tens of seconds. Work attached to a web process dies with a
deploy, a restart or a crashed request, and it competes with request handling
for the same event loop. A worker is scaled, restarted and watched on its own.

Without a provider key the worker starts, says so once, and **consumes
nothing**. Draining the queue only to fail every job would turn a missing key
into a pile of permanently failed reports; leaving the work queued means it
runs as soon as the key is there.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import socket
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import close_cache, init_cache
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.models.ai import AIReportJob
from app.db.models.user import User
from app.db.session import get_session_factory
from app.domain.ai import JobStatus
from app.services.ai.factory import (
    ai_available,
    build_report_service,
    close_ai_provider,
)
from app.services.ai.queue import (
    claim_next_job,
    queue_depth,
    recover_stale_jobs,
    release_claim,
)

logger = get_logger(__name__)


def worker_identity() -> str:
    """Something a human can trace back to a process in a log."""
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"


class AIReportWorker:
    def __init__(self, *, worker_id: str | None = None) -> None:
        self.worker_id = worker_id or worker_identity()
        self.running = True
        self._stop = asyncio.Event()
        self._current: uuid.UUID | None = None
        self.processed = 0

    # ------------------------------------------------------------- loop

    def request_stop(self, *_: object) -> None:
        """Finish the job in hand, then stop. No work is abandoned."""
        if self.running:
            logger.info("ai_worker_stopping", worker_id=self.worker_id)
        self.running = False
        self._stop.set()

    async def run_forever(self) -> None:
        factory = get_session_factory()
        idle_since = datetime.now(UTC)
        warned_unconfigured = False

        logger.info(
            "ai_worker_started",
            worker_id=self.worker_id,
            poll_seconds=settings.ai_worker_poll_seconds,
            lease_seconds=settings.ai_job_lease_seconds,
        )

        while self.running:
            if not ai_available():
                if not warned_unconfigured:
                    # Once, not every two seconds: an operator needs to see
                    # this, not drown in it.
                    logger.warning(
                        "ai_worker_idle_unconfigured",
                        worker_id=self.worker_id,
                        reason="no provider key; jobs are left queued",
                    )
                    warned_unconfigured = True
                await self._sleep(settings.ai_worker_poll_seconds)
                continue
            warned_unconfigured = False

            async with factory() as session:
                try:
                    await recover_stale_jobs(session)
                    job = await claim_next_job(session, worker_id=self.worker_id)
                except Exception:  # noqa: BLE001 - a poll must never kill the loop
                    logger.exception("ai_worker_claim_failed")
                    await session.rollback()
                    await self._sleep(settings.ai_worker_poll_seconds)
                    continue

                if job is None:
                    if (
                        datetime.now(UTC) - idle_since
                    ).total_seconds() >= settings.ai_worker_idle_log_seconds:
                        logger.info(
                            "ai_worker_idle",
                            worker_id=self.worker_id,
                            **await queue_depth(session),
                        )
                        idle_since = datetime.now(UTC)
                    await self._sleep(settings.ai_worker_poll_seconds)
                    continue

                idle_since = datetime.now(UTC)
                await self.process(session, job)

        await self._shutdown()

    async def _sleep(self, seconds: float) -> None:
        """Interruptible wait, so a stop signal does not wait out a poll."""
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._stop.wait(), seconds)

    # ---------------------------------------------------------- one job

    async def process(self, session: AsyncSession, job: AIReportJob) -> AIReportJob:
        """Run one claimed job. Never raises: a bad job must not stop a worker."""
        self._current = job.id
        logger.info(
            "ai_job_started",
            job_id=str(job.id),
            worker_id=self.worker_id,
            report_type=job.report_type,
            attempt=job.attempt,
        )

        try:
            user = await session.scalar(select(User).where(User.id == job.user_id))
            if user is None:
                # The account went away between queueing and running.
                job.status = JobStatus.FAILED.value
                job.error_code = "user_missing"
                job.finished_at = datetime.now(UTC)
                job.worker_id = None
                job.lease_expires_at = None
                await session.commit()
                return job

            service = build_report_service(session)
            job = await service.run_job(job, user)
            await session.commit()
            self.processed += 1
        except Exception:  # noqa: BLE001 - logged, then the loop continues
            logger.exception("ai_job_crashed", job_id=str(job.id))
            await session.rollback()
            # Leave the claim to expire rather than guessing: the lease is
            # exactly the mechanism for a job whose run ended unexpectedly.
        finally:
            self._current = None
        return job

    # -------------------------------------------------------- shutdown

    async def _shutdown(self) -> None:
        if self._current is not None:
            async with get_session_factory()() as session:
                await release_claim(session, self._current, requeue=True)
                logger.info("ai_worker_requeued", job_id=str(self._current))

        await close_ai_provider()
        await close_cache()
        logger.info(
            "ai_worker_stopped", worker_id=self.worker_id, processed=self.processed
        )


async def main() -> None:
    configure_logging()
    await init_cache()

    worker = AIReportWorker()
    loop = asyncio.get_running_loop()
    for name in ("SIGINT", "SIGTERM"):
        signal_number = getattr(signal, name, None)
        if signal_number is None:
            continue
        try:
            loop.add_signal_handler(signal_number, worker.request_stop)
        except NotImplementedError:
            # Windows: signal handlers are not available on the proactor loop.
            signal.signal(signal_number, worker.request_stop)

    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
