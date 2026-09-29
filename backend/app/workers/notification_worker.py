"""The notification delivery worker.

    python -m app.workers.notification_worker

Reuses the shape that the AI report worker already proved: recover work whose
owner died, claim one row atomically, deliver it, repeat. Several of these can
run at once - the claim uses `SELECT ... FOR UPDATE SKIP LOCKED`, so the same
notification is never sent twice.

Without Firebase credentials the worker starts, says so once, and consumes
nothing. Draining the queue only to fail every row would turn a missing service
account into a pile of permanently failed notifications; leaving them pending
means they go out as soon as the credential arrives.
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
from app.domain.chat import CALL_EVENTS
from app.services.firebase.factory import firebase_available, get_firebase
from app.services.notifications.apns import get_voip_provider
from app.services.notifications.outbox import OutboxService
from app.services.notifications.sender import NotificationSender

CALL_EVENT_TYPES = frozenset(event.value for event in CALL_EVENTS)
IDLE = "idle"


def claim_scope(*, fcm_ready: bool, voip_ready: bool) -> frozenset[str] | None | str:
    """What this worker may claim, given which transports are configured.

    Firebase: everything (None = no filter). APNs only: call events - their
    iOS VoIP targets can be delivered, their FCM targets are skipped as not
    configured - and ordinary notifications stay queued for Firebase. Neither:
    `IDLE`, and the queue is left untouched.
    """
    if fcm_ready:
        return None
    if voip_ready:
        return CALL_EVENT_TYPES
    return IDLE

logger = get_logger(__name__)


def worker_identity() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"


class NotificationWorker:
    def __init__(self, *, worker_id: str | None = None) -> None:
        self.worker_id = worker_id or worker_identity()
        self.running = True
        self._stop = asyncio.Event()
        self.processed = 0

    def request_stop(self, *_: object) -> None:
        """Finish the notification in hand, then stop."""
        if self.running:
            logger.info("notification_worker_stopping", worker_id=self.worker_id)
        self.running = False
        self._stop.set()

    async def _sleep(self, seconds: float) -> None:
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._stop.wait(), seconds)

    async def run_forever(self) -> None:
        factory = get_session_factory()
        idle_since = datetime.now(UTC)
        warned = False

        logger.info(
            "notification_worker_started",
            worker_id=self.worker_id,
            poll_seconds=settings.push_worker_poll_seconds,
            lease_seconds=settings.push_outbox_lease_seconds,
        )

        while self.running:
            event_types = claim_scope(
                fcm_ready=firebase_available(), voip_ready=get_voip_provider().available
            )
            if event_types == IDLE:
                if not warned:
                    logger.warning(
                        "notification_worker_idle_unconfigured",
                        worker_id=self.worker_id,
                        reason="no Firebase and no APNs credentials; notifications stay queued",
                    )
                    warned = True
                await self._sleep(settings.push_worker_poll_seconds)
                continue
            warned = False

            async with factory() as session:
                outbox = OutboxService(session)
                try:
                    await outbox.recover_stale()
                    row = await outbox.claim_next(
                        worker_id=self.worker_id, event_types=event_types
                    )
                except Exception:  # noqa: BLE001 - a poll must not kill the loop
                    logger.exception("notification_claim_failed")
                    await session.rollback()
                    await self._sleep(settings.push_worker_poll_seconds)
                    continue

                if row is None:
                    if (
                        datetime.now(UTC) - idle_since
                    ).total_seconds() >= settings.push_worker_idle_log_seconds:
                        logger.info(
                            "notification_worker_idle",
                            worker_id=self.worker_id,
                            **await outbox.depth(),
                        )
                        idle_since = datetime.now(UTC)
                    await self._sleep(settings.push_worker_poll_seconds)
                    continue

                idle_since = datetime.now(UTC)
                try:
                    sender = NotificationSender(session, get_firebase())
                    await sender.deliver(row)
                    self.processed += 1
                except Exception:  # noqa: BLE001 - logged, loop continues
                    logger.exception(
                        "notification_delivery_crashed", outbox_id=str(row.id)
                    )
                    await session.rollback()
                    # The lease expires and another worker picks it up.

        await self._shutdown()

    async def _shutdown(self) -> None:
        await close_cache()
        logger.info(
            "notification_worker_stopped",
            worker_id=self.worker_id,
            processed=self.processed,
        )


async def main() -> None:
    configure_logging()
    await init_cache()

    worker = NotificationWorker()
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
