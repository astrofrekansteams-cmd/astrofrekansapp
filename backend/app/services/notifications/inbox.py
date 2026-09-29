"""The in-app notification centre, read from the push outbox.

One event, one row: whatever the backend queues for push (a booking, a
message, a refund, a ready report) is what the notification centre lists, so
the two can never disagree and nothing is invented for the inbox alone.

What the inbox shows is a subset of the outbox:

* only events a person reads later - not the call signalling (incoming,
  answered, cancelled) that exists to ring or stop ringing a phone;
* only what is due - a reminder scheduled for tomorrow is not news today;
* not reminders dropped because their appointment was cancelled.

Push delivery status does not matter here: a notification that found no
device to push to (`skipped`) is exactly the one the inbox must still show.
Text comes from the client, localised from `event` and `data`; the stored
push title/body is a generic Turkish fallback for a lock screen.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.db.models.chat import NotificationOutbox
from app.domain.chat import OutboxStatus, PushEvent
from app.services.notifications.outbox import APPOINTMENT_CANCELLED_NOTE

# Event -> inbox category. Events not listed never appear in the inbox.
INBOX_CATEGORY: dict[str, str] = {
    PushEvent.AI_REPORT_READY.value: "astro_ai",
    PushEvent.APPOINTMENT_BOOKED.value: "appointment",
    PushEvent.APPOINTMENT_CANCELLED.value: "appointment",
    PushEvent.APPOINTMENT_REMINDER.value: "appointment",
    PushEvent.ORDER_STATUS_CHANGED.value: "appointment",
    PushEvent.CALL_MISSED.value: "appointment",
    PushEvent.NEW_CHAT_MESSAGE.value: "expert_message",
    PushEvent.PAYMENT_SUCCEEDED.value: "payment",
    PushEvent.PAYMENT_FAILED.value: "payment",
    PushEvent.REFUND_PROCESSED.value: "payment",
    PushEvent.SUBSCRIPTION_RENEWED.value: "payment",
    PushEvent.SUBSCRIPTION_EXPIRED.value: "payment",
    PushEvent.DAILY_CONTENT.value: "system",
    PushEvent.PROMOTION.value: "promotion",
}
CATEGORIES = ("astro_ai", "appointment", "expert_message", "payment", "system", "promotion")


class InboxService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _visible(self, user_id: uuid.UUID, now: datetime):  # noqa: ANN202
        return (
            NotificationOutbox.user_id == user_id,
            NotificationOutbox.event_type.in_(sorted(INBOX_CATEGORY)),
            or_(
                NotificationOutbox.scheduled_for.is_(None),
                NotificationOutbox.scheduled_for <= now,
            ),
            or_(
                NotificationOutbox.status != OutboxStatus.SKIPPED.value,
                NotificationOutbox.notes.is_(None),
                NotificationOutbox.notes != APPOINTMENT_CANCELLED_NOTE,
            ),
        )

    async def list(
        self,
        user_id: uuid.UUID,
        *,
        limit: int = 30,
        before: datetime | None = None,
        category: str | None = None,
        unread_only: bool = False,
    ) -> list[NotificationOutbox]:
        now = datetime.now(UTC)
        statement = select(NotificationOutbox).where(*self._visible(user_id, now))
        if before is not None:
            statement = statement.where(NotificationOutbox.created_at < before)
        if category is not None:
            events = [event for event, cat in INBOX_CATEGORY.items() if cat == category]
            statement = statement.where(NotificationOutbox.event_type.in_(events))
        if unread_only:
            statement = statement.where(NotificationOutbox.read_at.is_(None))
        return list(
            await self.session.scalars(
                statement.order_by(NotificationOutbox.created_at.desc()).limit(limit)
            )
        )

    async def unread_count(self, user_id: uuid.UUID) -> int:
        now = datetime.now(UTC)
        return int(
            await self.session.scalar(
                select(func.count(NotificationOutbox.id)).where(
                    *self._visible(user_id, now), NotificationOutbox.read_at.is_(None)
                )
            )
            or 0
        )

    async def set_read(self, user_id: uuid.UUID, notification_id: uuid.UUID, *, read: bool) -> NotificationOutbox:
        now = datetime.now(UTC)
        row = await self.session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.id == notification_id, *self._visible(user_id, now)
            )
        )
        if row is None:
            raise NotFound("Notification not found.")
        row.read_at = (row.read_at or now) if read else None
        await self.session.flush()
        return row

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        now = datetime.now(UTC)
        result = await self.session.execute(
            update(NotificationOutbox)
            .where(*self._visible(user_id, now), NotificationOutbox.read_at.is_(None))
            .values(read_at=now)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount or 0


def to_item(row: NotificationOutbox) -> dict:
    data = dict((row.payload or {}).get("data") or {})
    data.pop("event", None)
    # Ids only, as strings: the client routes on them.
    safe = {key: str(value) for key, value in data.items() if key.endswith("_id") or key == "minutes_before"}
    return {
        "id": row.id,
        "event": row.event_type,
        "category": INBOX_CATEGORY.get(row.event_type, "system"),
        "created_at": row.scheduled_for or row.created_at,
        "read": row.read_at is not None,
        "data": safe,
    }
