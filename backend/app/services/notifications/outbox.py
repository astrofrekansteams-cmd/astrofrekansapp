"""The notification outbox.

Push is **not** on the critical path of a business transaction. FCM being down
must not roll back an order somebody paid for, or lose a message that was
successfully stored. So a request writes a row and returns; a worker delivers
it.

Two properties this buys, both of which matter more than the indirection costs:

* **The business transaction stays atomic.** The outbox row is written in the
  same transaction as the message or the booking, so there is no state where
  the thing happened but nothing will ever be sent, and none where a
  notification promises something that was rolled back.
* **One event, one notification.** `dedupe_key` is a unique constraint, so a
  retried request, a replayed webhook or a worker that restarts mid-flight all
  converge on a single row.

## What a payload may contain

A lock screen is a public surface. Somebody else can read it while the phone is
on a table. So a payload carries an id and a generic line - never a message
body, never birth data, never a horary question, never an amount. The app
fetches the detail after the user opens it, by which point they have
authenticated.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.chat import NotificationOutbox
from app.domain.chat import CALL_EVENTS, OutboxStatus, PushEvent
from app.services.notifications.messages import push_text, user_language

logger = get_logger(__name__)

_CALL_EVENT_TYPES = frozenset(event.value for event in CALL_EVENTS)

# What a notification *says* lives in `messages.py`, in the recipient's
# language (TR/EN). This file owns the event, its data and its dedupe key -
# none of which depend on language.

# A reminder dropped because its appointment was cancelled. The inbox hides
# these: "your appointment is in an hour" for a cancelled one is noise.
APPOINTMENT_CANCELLED_NOTE = "appointment cancelled"

# Reminder offsets before an appointment. Each becomes one scheduled outbox
# row, which is why this phase needs no separate scheduler: the worker's
# "what is due" query is the scheduler.
REMINDER_OFFSETS = (
    timedelta(hours=24),
    timedelta(hours=1),
    timedelta(minutes=15),
)


class OutboxService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------------------------------------------------------- enqueue

    async def enqueue(
        self,
        *,
        event: PushEvent,
        user_id: uuid.UUID,
        dedupe_key: str,
        data: dict[str, str] | None = None,
        conversation_id: uuid.UUID | None = None,
        order_id: uuid.UUID | None = None,
        appointment_id: uuid.UUID | None = None,
        scheduled_for: datetime | None = None,
        variant: str | None = None,
        expires_at: datetime | None = None,
    ) -> NotificationOutbox | None:
        """Queue one notification. Returns None when it is already queued.

        Never raises on a duplicate: an event arriving twice is normal (a
        retry, a replay), and the correct response is to do nothing rather than
        to fail the caller's transaction.
        """
        # Rendered in the recipient's language now, and again at delivery
        # (see NotificationSender) in case the language changed in between.
        language = await user_language(self.session, user_id)
        title, body = push_text(event, language=language, variant=variant)

        payload = {
            "title": title,
            "body": body,
            "language": language,
            # `data` is for the client to route on. Ids only.
            "data": {"event": event.value, **(data or {})},
        }
        if variant:
            # From a fixed list (e.g. audio/video), never free text.
            payload["variant"] = variant

        key = dedupe_key[:160]

        # Checked first, so the ordinary duplicate costs a SELECT rather than a
        # failed INSERT. The constraint is still what guarantees it.
        already = await self.session.scalar(
            select(NotificationOutbox.id).where(
                NotificationOutbox.dedupe_key == key
            )
        )
        if already is not None:
            logger.info(
                "push_enqueue_deduped",
                event_type=event.value,
                dedupe_key=key[:80],
            )
            return None

        row = NotificationOutbox(
            event_type=event.value,
            user_id=user_id,
            conversation_id=conversation_id,
            order_id=order_id,
            appointment_id=appointment_id,
            dedupe_key=key,
            payload=payload,
            status=OutboxStatus.PENDING.value,
            max_attempts=settings.push_outbox_max_attempts,
            scheduled_for=scheduled_for,
            expires_at=expires_at,
        )

        # A savepoint, not the transaction. Enqueuing is a side effect of
        # somebody else's business transaction - a booking, a message - and a
        # duplicate notification must not roll that back. `session.rollback()`
        # here would discard the caller's work and expire every object they
        # still hold.
        try:
            async with self.session.begin_nested():
                self.session.add(row)
                await self.session.flush()
        except IntegrityError:
            # Lost a race for the same dedupe key. The constraint held, which
            # is the point: one event, one notification.
            logger.info(
                "push_enqueue_deduped",
                event_type=event.value,
                dedupe_key=key[:80],
            )
            return None

        logger.info(
            "push_enqueued",
            outbox_id=str(row.id),
            event_type=event.value,
            user_id=str(user_id),
            scheduled=scheduled_for.isoformat() if scheduled_for else None,
        )
        return row

    async def enqueue_chat_message(
        self,
        *,
        recipient_user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: str,
    ) -> NotificationOutbox | None:
        """Notify the other party about a message.

        The message id is the dedupe key: one message, one notification,
        however many times delivery is attempted. The body is **not** in the
        payload - only the conversation to open.
        """
        return await self.enqueue(
            event=PushEvent.NEW_CHAT_MESSAGE,
            user_id=recipient_user_id,
            dedupe_key=f"chat:{message_id}:{recipient_user_id}",
            data={"conversation_id": str(conversation_id)},
            conversation_id=conversation_id,
        )

    async def enqueue_appointment_reminders(
        self,
        *,
        user_id: uuid.UUID,
        appointment_id: uuid.UUID,
        starts_at_utc: datetime,
    ) -> list[NotificationOutbox]:
        """One scheduled row per reminder offset.

        Reminders already in the past are skipped rather than fired late: a
        "your appointment is in 24 hours" notification sent an hour beforehand
        is worse than none.
        """
        now = datetime.now(UTC)
        created: list[NotificationOutbox] = []

        for offset in REMINDER_OFFSETS:
            due = starts_at_utc - offset
            if due <= now:
                continue
            row = await self.enqueue(
                event=PushEvent.APPOINTMENT_REMINDER,
                user_id=user_id,
                dedupe_key=f"reminder:{appointment_id}:{int(offset.total_seconds())}",
                data={
                    "appointment_id": str(appointment_id),
                    "minutes_before": str(int(offset.total_seconds() // 60)),
                },
                appointment_id=appointment_id,
                scheduled_for=due,
            )
            if row is not None:
                created.append(row)
        return created

    async def cancel_for_appointment(self, appointment_id: uuid.UUID) -> int:
        """Drop pending reminders for an appointment that is no longer happening."""
        result = await self.session.execute(
            update(NotificationOutbox)
            .where(
                NotificationOutbox.appointment_id == appointment_id,
                NotificationOutbox.status == OutboxStatus.PENDING.value,
                NotificationOutbox.event_type == PushEvent.APPOINTMENT_REMINDER.value,
            )
            .values(
                status=OutboxStatus.SKIPPED.value,
                notes=APPOINTMENT_CANCELLED_NOTE,
                processed_at=datetime.now(UTC),
            )
        )
        return result.rowcount or 0

    async def skip_pending_with_prefix(self, prefix: str, *, reason: str) -> int:
        """Drop queued notifications whose moment has passed.

        An "incoming call" that is delivered after the call was answered,
        missed or cancelled makes a phone ring for nothing. Matched on the
        dedupe key, which for calls is `<event>:<call id>:<recipient>`.
        """
        result = await self.session.execute(
            update(NotificationOutbox)
            .where(
                NotificationOutbox.dedupe_key.like(f"{prefix}%"),
                NotificationOutbox.status == OutboxStatus.PENDING.value,
            )
            .values(
                status=OutboxStatus.SKIPPED.value,
                notes=reason[:200],
                processed_at=datetime.now(UTC),
            )
        )
        return result.rowcount or 0

    # ------------------------------------------------------------ claim

    async def claim_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int | None = None,
        event_types: frozenset[str] | None = None,
    ) -> NotificationOutbox | None:
        """Take one due notification, atomically.

        `SELECT ... FOR UPDATE SKIP LOCKED` on Postgres: the standard way to
        hand one row to exactly one worker. Without it, two workers both read
        the same pending row and the user gets two notifications.
        """
        now = datetime.now(UTC)

        statement = (
            select(NotificationOutbox)
            .where(
                NotificationOutbox.status == OutboxStatus.PENDING.value,
                (NotificationOutbox.scheduled_for.is_(None))
                | (NotificationOutbox.scheduled_for <= now),
            )
            .order_by(NotificationOutbox.created_at)
            .limit(1)
        )
        if event_types is not None:
            # A worker that can deliver only some transports (APNs without
            # Firebase) takes only the events it can do something with, and
            # leaves the rest queued.
            statement = statement.where(NotificationOutbox.event_type.in_(sorted(event_types)))
        if (
            self.session.bind is not None
            and self.session.bind.dialect.name != "sqlite"
        ):
            statement = statement.with_for_update(skip_locked=True)

        row = await self.session.scalar(statement)
        if row is None:
            return None

        if lease_seconds is not None:
            lease = lease_seconds
        elif row.event_type in _CALL_EVENT_TYPES:
            # Call events are claimed for a few seconds, not two minutes: a
            # ring outlives a crashed worker only if another takes over while
            # the phone could still ring. Generic notifications keep B9's lease.
            lease = settings.call_push_lease_seconds
        else:
            lease = settings.push_outbox_lease_seconds
        row.status = OutboxStatus.SENDING.value
        row.worker_id = worker_id
        row.lease_expires_at = now + timedelta(seconds=lease)
        row.attempts += 1
        await self.session.commit()
        return row

    async def recover_stale(self, *, limit: int = 20) -> int:
        """Return notifications whose worker died to the queue.

        A `sending` row with an expired lease has no live owner. It goes back to
        `pending` if attempts remain, and to `failed` if not - a notification
        that keeps killing its worker should stop being tried.
        """
        now = datetime.now(UTC)
        rows = list(
            await self.session.scalars(
                select(NotificationOutbox)
                .where(
                    NotificationOutbox.status == OutboxStatus.SENDING.value,
                    NotificationOutbox.lease_expires_at.is_not(None),
                    NotificationOutbox.lease_expires_at < now,
                )
                .limit(limit)
            )
        )
        for row in rows:
            if row.attempts >= row.max_attempts:
                row.status = OutboxStatus.FAILED.value
                row.error_code = row.error_code or "worker_lost"
                row.processed_at = now
            else:
                row.status = OutboxStatus.PENDING.value
            row.worker_id = None
            row.lease_expires_at = None

        if rows:
            await self.session.commit()
            logger.warning("push_outbox_recovered", count=len(rows))
        return len(rows)

    # ----------------------------------------------------------- finish

    async def mark_sent(
        self, row: NotificationOutbox, *, delivered: int, failed: int
    ) -> None:
        row.status = OutboxStatus.SENT.value
        row.processed_at = datetime.now(UTC)
        row.worker_id = None
        row.lease_expires_at = None
        row.error_code = None
        await self.session.commit()
        logger.info(
            "push_sent",
            outbox_id=str(row.id),
            event_type=row.event_type,
            delivered=delivered,
            failed=failed,
        )

    async def mark_expired(self, row: NotificationOutbox) -> None:
        """Past its moment - an incoming call that has stopped ringing.

        Skipped, not failed and not retried: sending it now would ring a phone
        for a call that no longer exists.
        """
        await self.mark_skipped(row, reason="skipped_expired")

    async def mark_skipped(self, row: NotificationOutbox, *, reason: str) -> None:
        """Nothing to send - no enabled devices, for instance. Not a failure."""
        row.status = OutboxStatus.SKIPPED.value
        row.processed_at = datetime.now(UTC)
        row.notes = reason[:200]
        row.worker_id = None
        row.lease_expires_at = None
        await self.session.commit()
        logger.info("push_skipped", outbox_id=str(row.id), reason=reason)

    async def mark_failed(
        self, row: NotificationOutbox, *, error_code: str, retryable: bool
    ) -> None:
        """Retry a transient failure, give up on a permanent one."""
        row.error_code = error_code[:60]
        row.worker_id = None
        row.lease_expires_at = None

        if retryable and row.attempts < row.max_attempts:
            row.status = OutboxStatus.PENDING.value
            await self.session.commit()
            logger.warning(
                "push_retry",
                outbox_id=str(row.id),
                attempts=row.attempts,
                max_attempts=row.max_attempts,
                error_code=error_code,
            )
            return

        row.status = OutboxStatus.FAILED.value
        row.processed_at = datetime.now(UTC)
        await self.session.commit()
        logger.warning(
            "push_failed",
            outbox_id=str(row.id),
            attempts=row.attempts,
            error_code=error_code,
            retryable=retryable,
        )

    async def depth(self) -> dict[str, int]:
        depth: dict[str, int] = {}
        for status in (OutboxStatus.PENDING, OutboxStatus.SENDING, OutboxStatus.FAILED):
            rows = await self.session.scalars(
                select(NotificationOutbox.id).where(
                    NotificationOutbox.status == status.value
                )
            )
            depth[status.value] = len(list(rows))
        return depth
