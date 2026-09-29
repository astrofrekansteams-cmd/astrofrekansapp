"""The user's notification preferences, applied at delivery time.

Checked when a notification is about to be sent - not when it is queued - so a
reminder scheduled a day ahead still honours a switch turned off since.

Some notifications are never optional:

* call lifecycle (incoming, cancelled, missed, answered) - the call flow and
  its safety depend on them; they do not even take this path;
* payments, refunds, subscriptions and order status - transactional notices
  about the user's money and purchases.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import UserProfile
from app.domain.chat import PushEvent
from app.schemas.user import NotificationPreferences

# Event -> the preference that controls it. Events not listed always send.
EVENT_PREFERENCE: dict[str, str] = {
    PushEvent.NEW_CHAT_MESSAGE.value: "expert_messages",
    PushEvent.APPOINTMENT_BOOKED.value: "appointment_reminders",
    PushEvent.APPOINTMENT_CANCELLED.value: "appointment_reminders",
    PushEvent.APPOINTMENT_REMINDER.value: "appointment_reminders",
    PushEvent.AI_REPORT_READY.value: "ai_reports",
    PushEvent.DAILY_CONTENT.value: "daily_horoscope",
    PushEvent.PROMOTION.value: "promotions",
}


async def notification_allowed(
    session: AsyncSession, user_id: uuid.UUID, event_type: str
) -> bool:
    key = EVENT_PREFERENCE.get(event_type)
    if key is None:
        return True
    stored = await session.scalar(
        select(UserProfile.notification_prefs).where(UserProfile.user_id == user_id)
    )
    prefs = NotificationPreferences(**(stored or {}))
    return bool(getattr(prefs, key, True))
