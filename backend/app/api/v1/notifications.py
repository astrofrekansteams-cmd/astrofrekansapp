"""The in-app notification centre.

Same event stream as push (see services/notifications/inbox.py): the list is
the user's own queued notifications, with a read state. Nothing here creates
a notification.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import ValidationFailed
from app.schemas.notifications import (
    InboxItem,
    InboxPage,
    MarkReadRequest,
    UnreadCount,
)
from app.services.notifications.inbox import CATEGORIES, InboxService, to_item

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=InboxPage, summary="Your notifications, newest first")
async def list_notifications(
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=30, ge=1, le=100),
    before: datetime | None = Query(default=None, description="Cursor: `next_before` of the previous page."),
    category: str | None = Query(default=None),
    unread: bool = Query(default=False),
) -> InboxPage:
    if category is not None and category not in CATEGORIES:
        raise ValidationFailed("Unknown category.", details={"supported": list(CATEGORIES)})
    service = InboxService(session)
    rows = await service.list(
        user.id, limit=limit + 1, before=before, category=category, unread_only=unread
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    return InboxPage(
        items=[InboxItem(**to_item(row)) for row in rows],
        unread_count=await service.unread_count(user.id),
        next_before=rows[-1].created_at if has_more and rows else None,
    )


@router.get("/unread-count", response_model=UnreadCount, summary="Unread notifications")
async def unread_count(user: CurrentUser, session: DbSession) -> UnreadCount:
    return UnreadCount(unread_count=await InboxService(session).unread_count(user.id))


@router.patch(
    "/{notification_id}",
    response_model=InboxItem,
    summary="Mark one notification read or unread",
)
async def mark(
    notification_id: uuid.UUID,
    payload: MarkReadRequest,
    user: CurrentUser,
    session: DbSession,
) -> InboxItem:
    row = await InboxService(session).set_read(user.id, notification_id, read=payload.read)
    await session.commit()
    return InboxItem(**to_item(row))


@router.post("/read-all", response_model=UnreadCount, summary="Mark everything read")
async def read_all(user: CurrentUser, session: DbSession) -> UnreadCount:
    await InboxService(session).mark_all_read(user.id)
    await session.commit()
    return UnreadCount(unread_count=0)
