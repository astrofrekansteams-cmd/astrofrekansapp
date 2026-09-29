from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint, false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import UtcDateTime

JSONType = JSON().with_variant(JSONB(), "postgresql")


class AIConversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One Astro AI chat thread.

    The rolling summary lives here rather than in the message list: it is
    memory of the conversation, not something the user said, and it must never
    be mistaken for one. Astrological facts are never taken from it - they
    always come fresh from the engine.
    """

    __tablename__ = "ai_conversations"
    # Conversations and messages are almost always read newest-first, so the
    # recency index is declared here rather than on the shared mixin - the
    # older tables have no such query pattern.
    __table_args__ = (
        Index("ix_ai_conversations_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    locale: Mapped[str] = mapped_column(String(8), default="tr", nullable=False)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summarised_message_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    archived_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    messages: Mapped[list["AIMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


class AIMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A user-visible turn.

    System and developer instructions are never stored here: they are not
    something the user wrote or read, and keeping them in the same table would
    make it far too easy to replay them to a client.
    """

    __tablename__ = "ai_messages"
    __table_args__ = (Index("ix_ai_messages_created_at", "created_at"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    generation_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    # Whether this turn is the whole answer. A stream that the client dropped
    # leaves real text behind, but it is not a finished answer and must not be
    # presented - or replayed to the model - as though it were.
    completion_status: Mapped[str] = mapped_column(
        String(20), default="completed", nullable=False
    )

    # Which context type answered this turn, and what it cited.
    context_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_factor_ids: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True
    )

    conversation: Mapped[AIConversation] = relationship(back_populates="messages")


class AIGeneration(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """What one provider call cost and how it was configured.

    Deliberately absent: the prompt, the context, the answer, the API key.
    This table exists for cost and reliability observability, and it must stay
    safe to read.
    """

    __tablename__ = "ai_generations"
    __table_args__ = (Index("ix_ai_generations_created_at", "created_at"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    use_case: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model_requested: Mapped[str] = mapped_column(String(60), nullable=False)
    model_actual: Mapped[str] = mapped_column(String(60), nullable=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)

    prompt_version: Mapped[str] = mapped_column(String(60), nullable=False)
    context_version: Mapped[str] = mapped_column(String(60), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cached_input_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider_response_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)


class AIReport(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A generated reading, frozen at the moment it was produced.

    ``input_fingerprint`` covers the source material plus the context, prompt
    and engine versions. Editing a birth profile or changing a prompt produces
    a *new* report; the old one keeps saying what the user already read.

    The fingerprint is deliberately **not** unique: it identifies the inputs,
    not a row. An explicit refresh writes another report from the same inputs,
    and the reading a user already has is never overwritten. Lookups take the
    newest completed row for a fingerprint.
    """

    __tablename__ = "ai_reports"
    __table_args__ = (Index("ix_ai_reports_created_at", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # What the report is about: "birth_profile", "horary_question",
    # "compatibility_report", "forecast", plus the id when there is one.
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sections: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    warnings: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    interpretation_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    safety_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    input_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    prompt_version: Mapped[str] = mapped_column(String(60), nullable=False)
    context_version: Mapped[str] = mapped_column(String(60), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    generation_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # The credit this snapshot was delivered against, when it is a paid report.
    # A later request for the same inputs returns it without charging again.
    entitlement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_entitlements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class AIReportJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A durable record of a long report generation.

    The state lives in Postgres rather than in a worker's memory, so a
    restart, a crash or a client disconnect leaves a row that can be inspected
    and retried instead of a silently lost request.
    """

    __tablename__ = "ai_report_jobs"
    # The claim query looks for the oldest queued job; this keeps that cheap
    # once a backlog exists.
    __table_args__ = (
        Index("ix_ai_report_jobs_claim", "status", "created_at"),
        # One paid operation per client reference: a retried request finds
        # its job instead of paying for a second one.
        UniqueConstraint("user_id", "consumer_ref", name="uq_ai_report_jobs_user_consumer_ref"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    locale: Mapped[str] = mapped_column(String(8), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Claim bookkeeping. A worker takes a job by writing its own id and a
    # lease; the lease is what lets another worker recover the job if this one
    # dies without ever finishing it.
    worker_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )

    report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_reports.id", ondelete="SET NULL"), nullable=True
    )
    input_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    # Payment. `payment_basis` is how the job was allowed to exist: "free",
    # "premium" or "credit"; NULL only on jobs queued before paid reports were
    # enforced, which are re-judged when they run. A credit job holds its
    # credit (`entitlement_id`, RESERVED) from creation and consumes it in the
    # same commit that completes the report.
    payment_basis: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consumer_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entitlement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_entitlements.id", ondelete="SET NULL"), nullable=True
    )
    refresh: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
