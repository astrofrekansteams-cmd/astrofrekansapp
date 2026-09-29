"""Call API contracts.

Two rules these schemas hold:

* **A join token appears in exactly one response** - `POST /calls/{id}/join` -
  and that response is sent `Cache-Control: no-store`. Every other call
  response is safe to cache, log or show in a support tool.
* **Nothing provider-internal is exposed.** Not the room name (the token already
  names the room), not the other party's LiveKit identity, not an error message
  from LiveKit.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.domain.calls import (
    CallEndReason,
    CallStatus,
    CallType,
    ParticipantRole,
    ParticipantStatus,
)
from app.schemas.common import APIModel


class CallStatusResponse(APIModel):
    """Whether calls work on this server. Never a URL, never a key."""

    configured: bool
    provider: str


class CallCreateRequest(APIModel):
    order_id: uuid.UUID = Field(
        description=(
            "A call exists because an order does. Nobody opens a call with an "
            "arbitrary expert."
        )
    )
    appointment_id: uuid.UUID | None = Field(
        default=None,
        description="Optional. When given it must be the order's appointment.",
    )
    call_type: CallType


class CallParticipantResponse(APIModel):
    role: ParticipantRole
    status: ParticipantStatus
    is_me: bool
    first_joined_at: datetime | None = None
    last_left_at: datetime | None = None


class CallResponse(APIModel):
    """A call's state. Carries no token and nothing that could obtain one."""

    id: uuid.UUID
    order_id: uuid.UUID
    appointment_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None

    call_type: CallType
    status: CallStatus
    my_role: ParticipantRole

    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    join_opens_at: datetime | None = Field(
        default=None, description="Before this, joining is `call_too_early`."
    )
    join_closes_at: datetime | None = Field(
        default=None, description="After this, joining is `call_window_closed`."
    )

    ringing_at: datetime | None = None
    started_at: datetime | None = Field(
        default=None,
        description=(
            "The first moment both parties were in the room, from provider "
            "events. Never from a client."
        ),
    )
    ended_at: datetime | None = None
    end_reason: CallEndReason | None = None
    duration_seconds: int | None = None

    participants: list[CallParticipantResponse]
    recording_enabled: bool = Field(
        default=False, description="Always false. Recording is not implemented."
    )
    created_at: datetime


class CallSummary(APIModel):
    id: uuid.UUID
    order_id: uuid.UUID
    call_type: CallType
    status: CallStatus
    my_role: ParticipantRole
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    end_reason: CallEndReason | None = None
    created_at: datetime


class CallPageResponse(APIModel):
    items: list[CallSummary]
    next_cursor: datetime | None = Field(
        default=None, description="Pass back as `before` for the next page."
    )


class RoomOptions(APIModel):
    audio: bool
    video: bool


class CallJoinResponse(APIModel):
    """Everything the LiveKit client needs to connect. Nothing more.

    Sensitive: sent with `Cache-Control: no-store`, never logged. The token
    admits exactly one opaque identity to exactly one room, may publish only
    the sources the call type allows, may not publish data, and holds no room
    administration grant. It expires quickly; an expired token only matters for
    a *new* connection - a connected client is refreshed by LiveKit itself.
    """

    call_id: uuid.UUID
    call_type: CallType
    livekit_url: str
    token: str
    token_expires_at: datetime
    participant_identity: str = Field(
        description="Opaque. Not a user id, not a name."
    )
    role: ParticipantRole
    room_options: RoomOptions
