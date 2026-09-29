"""Voice and video call sessions.

**FastAPI + Postgres decide who may join. LiveKit carries the media.**

So these tables hold authorisation, lifecycle and audit - and nothing that
would let somebody reading them join a call. No join token and no API secret is
ever stored: a token is minted per request, returned once, and forgotten.

What is deliberately absent:

* **Names.** A participant's LiveKit identity is an opaque random string, and a
  room's name is `call_<random>`. Neither a provider dashboard nor a webhook log
  shows who was talking to whom.
* **Media or its metadata.** No recording, no transcript, no track list, no
  mute history. `recording_enabled` exists only so that turning recording on
  later is a migration and a decision rather than a flag somebody flips - the
  check constraint holds it at false.
* **Raw provider payloads.** `call_provider_events` keeps what idempotency and
  audit need: the event id, its type, the opaque identities and a hash.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import UtcDateTime

# Kept in one place so the partial index, the check constraint and the service
# cannot disagree about which statuses count as "live".
LIVE_STATUS_SQL = "status IN ('scheduled', 'waiting', 'ringing', 'active')"
ALL_STATUS_SQL = (
    "status IN ('scheduled', 'waiting', 'ringing', 'active', "
    "'ended', 'missed', 'cancelled', 'failed')"
)


class CallSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One attempt at a live consultation.

    A call exists because an order does - the entitlement is the order's, never
    the room's metadata. Reconnecting is the same session; a new attempt after
    a call ended is a new session, so each attempt keeps its own audit trail.

    `uq_call_sessions_live_order` is the one-live-call rule: a partial unique
    index over the live statuses. Two simultaneous "start call" taps both
    insert, and the database, not an application-level SELECT, decides which
    one wins.
    """

    __tablename__ = "call_sessions"
    __table_args__ = (
        Index(
            "uq_call_sessions_live_order",
            "order_id",
            unique=True,
            postgresql_where=text(LIVE_STATUS_SQL),
            sqlite_where=text(LIVE_STATUS_SQL),
        ),
        UniqueConstraint("provider_room_name", name="uq_call_sessions_room"),
        Index("ix_call_sessions_order", "order_id"),
        Index("ix_call_sessions_appointment", "appointment_id"),
        Index("ix_call_sessions_conversation", "conversation_id"),
        Index("ix_call_sessions_status", "status"),
        Index("ix_call_sessions_created_at", "created_at"),
        Index("ix_call_sessions_user", "user_id", "created_at"),
        Index("ix_call_sessions_expert", "expert_id", "created_at"),
        CheckConstraint(ALL_STATUS_SQL, name="ck_call_sessions_status"),
        CheckConstraint(
            "call_type IN ('audio', 'video')", name="ck_call_sessions_type"
        ),
        CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="ck_call_sessions_times",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_call_sessions_duration",
        ),
        # Recording is off, and turning it on is a schema change - consent,
        # retention and jurisdiction have to be decided first.
        CheckConstraint(
            "recording_enabled = false", name="ck_call_sessions_no_recording"
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True
    )
    # The B9 thread for the same order, if one exists. The source of truth for
    # "which calls belong to this conversation" is this column - a single
    # pointer on the conversation could only ever hold one of them.
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("expert_conversations.id", ondelete="SET NULL"), nullable=True
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experts.id", ondelete="CASCADE"), nullable=False
    )
    # The expert's account. Authorisation is about who signed in; an expert
    # profile id is not a credential.
    expert_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    call_type: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    # Opaque: `call_<random hex>`. Never derived from a name, an order or a
    # service, so it tells a provider dashboard nothing.
    provider_room_name: Mapped[str] = mapped_column(String(64), nullable=False)
    room_provisioned_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    provider_error_code: Mapped[str | None] = mapped_column(
        String(60), nullable=True
    )

    # The appointment's window, snapshotted, so a join check does not depend
    # on reading an appointment that may since have moved or been cancelled.
    scheduled_start_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    scheduled_end_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )

    ringing_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    # The first moment both parties were in the room together. Derived from
    # provider events, never from a client saying "we started".
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    ended_by: Mapped[str | None] = mapped_column(String(20), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # When provider state was last compared with ours. Webhooks are not
    # guaranteed to arrive, so the worker re-reads the room for calls it has
    # not looked at recently.
    last_reconciled_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )

    recording_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )


class CallParticipant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One of the two people a call is for.

    Created with the session, so the set of people allowed in the room is fixed
    before anybody joins. A webhook naming an identity not in this table is an
    intruder, not a new participant.
    """

    __tablename__ = "call_participants"
    __table_args__ = (
        UniqueConstraint(
            "call_session_id", "role", name="uq_call_participants_role"
        ),
        UniqueConstraint(
            "provider_identity", name="uq_call_participants_identity"
        ),
        CheckConstraint(
            "role IN ('user', 'expert')", name="ck_call_participants_role"
        ),
        CheckConstraint(
            "status IN ('invited', 'joining', 'joined', 'left', 'disconnected')",
            name="ck_call_participants_status",
        ),
        CheckConstraint(
            "connection_count >= 0", name="ck_call_participants_connections"
        ),
    )

    call_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("call_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)

    # What LiveKit calls this person: `p_<random hex>`. Not the user id, not a
    # name, not an email - an identity that means nothing outside this table.
    provider_identity: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False)
    first_joined_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    last_joined_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    last_left_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    connection_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    # The provider timestamp of the newest event applied to this participant.
    # Webhooks can arrive late; an event older than this one is history, and
    # applying it would move the participant backwards.
    last_event_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    token_issued_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    last_token_issued_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )


class CallProviderEvent(Base, UUIDPrimaryKeyMixin):
    """A webhook we have already seen.

    Exists for idempotency - LiveKit retries, and the same event applied twice
    must not produce two transitions - and for audit. Deliberately *not* the
    raw payload: that carries names, metadata and track details this table has
    no business keeping. A hash is enough to tell a replay from a collision.
    """

    __tablename__ = "call_provider_events"
    __table_args__ = (
        UniqueConstraint(
            "provider", "event_id", name="uq_call_provider_events_event"
        ),
        Index("ix_call_provider_events_session", "call_session_id"),
        Index("ix_call_provider_events_received", "received_at"),
    )

    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    event_id: Mapped[str] = mapped_column(String(80), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    call_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("call_sessions.id", ondelete="SET NULL"), nullable=True
    )
    # Opaque values only - see the module docstring.
    room_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    participant_identity: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    provider_created_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    received_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # What handling decided: applied / ignored_unknown_room / intruder / ...
    outcome: Mapped[str | None] = mapped_column(String(40), nullable=True)
