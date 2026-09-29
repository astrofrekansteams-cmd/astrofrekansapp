from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

InboxCategory = Literal["astro_ai", "appointment", "expert_message", "payment", "system", "promotion"]


class InboxItem(APIModel):
    id: uuid.UUID
    event: str = Field(description="The push event, e.g. `appointment_booked`.")
    category: InboxCategory
    created_at: datetime
    read: bool
    data: dict[str, str] = Field(
        default_factory=dict,
        description="Ids to route on (order_id, appointment_id, conversation_id, report_id). Never content.",
    )


class InboxPage(APIModel):
    items: list[InboxItem]
    unread_count: int
    next_before: datetime | None = None


class UnreadCount(APIModel):
    unread_count: int


class MarkReadRequest(APIModel):
    read: bool = True
