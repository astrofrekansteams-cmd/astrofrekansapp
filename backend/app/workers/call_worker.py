"""The call lifecycle worker.

    python -m app.workers.call_worker

Calls have a clock: a ring times out, a dropped participant's reconnect grace
runs out, a join window closes, the hard duration ceiling arrives. Those are
applied lazily whenever somebody reads the call or a webhook arrives - but a
call nobody is looking at must still end, so this loop sweeps live calls.

It also reconciles. LiveKit's webhooks are not guaranteed to arrive, so a live
call nobody has heard about recently is re-read from the provider: who is in
the room, really.

Several can run: calls are claimed with `FOR UPDATE SKIP LOCKED`. Without
LiveKit credentials it starts, says so once, and does nothing - there is no
room to reconcile and nobody can have joined one.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import socket
import uuid
from datetime import UTC, datetime

from app.core.cache import close_cache, init_cache
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import get_session_factory
from app.services.calls.factory import (
    calls_available,
    close_call_provider,
    get_call_provider,
)
from app.services.calls.service import CallService

logger = get_logger(__name__)


def worker_identity() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"


class CallWorker:
    def __init__(self, *, worker_id: str | None = None) -> None:
        self.worker_id = worker_id or worker_identity()
        self.running = True
        self._stop = asyncio.Event()
        self.passes = 0

    def request_stop(self, *_: object) -> None:
        """Finish the pass in hand, then stop."""
        if self.running:
            logger.info("call_worker_stopping", worker_id=self.worker_id)
        self.running = False
        self._stop.set()

    async def _sleep(self, seconds: float) -> None:
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._stop.wait(), seconds)

    async def run_once(self) -> int:
        """One sweep. Returns how many live calls it looked at."""
        factory = get_session_factory()
        async with factory() as session:
            try:
                seen = await CallService(session, get_call_provider()).sweep()
                await session.commit()
            except Exception:  # noqa: BLE001 - a pass must not kill the loop
                logger.exception("call_sweep_failed", worker_id=self.worker_id)
                await session.rollback()
                return 0
        self.passes += 1
        return seen

    async def run_forever(self) -> None:
        idle_since = datetime.now(UTC)
        warned = False
        logger.info(
            "call_worker_started",
            worker_id=self.worker_id,
            poll_seconds=settings.call_worker_poll_seconds,
        )

        while self.running:
            if not calls_available():
                if not warned:
                    logger.warning(
                        "call_worker_idle_unconfigured",
                        worker_id=self.worker_id,
                        reason="no LiveKit credentials; no calls can exist",
                    )
                    warned = True
                await self._sleep(settings.call_worker_poll_seconds)
                continue
            warned = False

            seen = await self.run_once()
            if seen:
                idle_since = datetime.now(UTC)
            elif (
                datetime.now(UTC) - idle_since
            ).total_seconds() >= settings.call_worker_idle_log_seconds:
                logger.info("call_worker_idle", worker_id=self.worker_id)
                idle_since = datetime.now(UTC)
            await self._sleep(settings.call_worker_poll_seconds)

        await close_call_provider()
        await close_cache()
        logger.info(
            "call_worker_stopped", worker_id=self.worker_id, passes=self.passes
        )


async def main() -> None:
    configure_logging()
    await init_cache()

    worker = CallWorker()
    loop = asyncio.get_running_loop()
    for name in ("SIGINT", "SIGTERM"):
        number = getattr(signal, name, None)
        if number is None:
            continue
        try:
            loop.add_signal_handler(number, worker.request_stop)
        except NotImplementedError:
            signal.signal(number, worker.request_stop)

    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
