"""Astro AI API contracts."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.domain.ai import (
    CompletionStatus,
    ContextType,
    Intent,
    JobStatus,
    Locale,
    MessageRole,
    ReportStatus,
    ReportType,
)
from app.schemas.common import APIModel


class ConversationCreateRequest(APIModel):
    title: str | None = Field(default=None, max_length=160)
    locale: Locale | None = None


class ConversationResponse(APIModel):
    id: uuid.UUID
    title: str | None
    locale: Locale
    message_count: int
    archived: bool
    has_summary: bool = Field(
        description="Whether a rolling memory summary exists for this thread."
    )
    created_at: datetime
    updated_at: datetime


class MessageResponse(APIModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    context_type: ContextType | None = None
    source_factor_ids: list[str] = Field(default_factory=list)
    completion_status: CompletionStatus = Field(
        default=CompletionStatus.COMPLETED,
        description=(
            "Whether this turn is a finished answer. A stream the client "
            "dropped is stored as cancelled or partial and should not be "
            "rendered as a complete reply."
        ),
    )
    created_at: datetime


class ChatRequest(APIModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None
    locale: Locale | None = None

    # Lets the client pin the material, e.g. "explain this transit".
    context_mode: ContextType | None = None
    saved_person_id: uuid.UUID | None = None


class GenerationMetadataResponse(APIModel):
    model: str = Field(description="The model that actually answered.")
    model_requested: str
    fallback_reason: str | None = None
    prompt_version: str
    context_version: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int
    provider: str


class InfluenceResponse(APIModel):
    id: str
    kind: str
    nature: str | None = None
    label: str = Field(description="Localized, engine-derived line, e.g. 'Transit Satürn kare natal Güneş'.")


class ChatResponse(APIModel):
    conversation_id: uuid.UUID
    answer: str
    context_type: ContextType
    intent: Intent

    source_factor_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Factor ids from the context that this answer rests on. Only ids "
            "the backend supplied are ever returned."
        ),
    )
    context_note: str | None = None
    warnings: list[str] = Field(default_factory=list)
    influences: list[InfluenceResponse] = Field(
        default_factory=list,
        description="The astrological basis of this answer, readable ('Bu yorumu oluşturan etkiler').",
    )
    metadata: GenerationMetadataResponse


class ReportSectionResponse(APIModel):
    key: str
    title: str
    body: str
    factor_ids: list[str] = Field(default_factory=list)
    general_summary: bool = False


class ReportRequest(APIModel):
    report_type: ReportType
    source_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Required for horary and compatibility reports: the question or "
            "compatibility report to interpret. Must belong to the caller."
        ),
    )
    locale: Locale | None = None
    refresh: bool = False
    background: bool = Field(
        default=False,
        description="Queue a durable job instead of generating inline.",
    )
    consumer_ref: str | None = Field(
        default=None,
        min_length=8,
        max_length=100,
        pattern=r"^[A-Za-z0-9._:-]+$",
        description=(
            "Required for a report sold as a credit (natal, synastry, yearly "
            "unless premium includes them). A client-generated id for this "
            "purchase attempt, reused on every retry of it: the same reference "
            "returns the same job/report and never uses a second credit."
        ),
    )
    pay_with_coins: bool = Field(
        default=False,
        description=(
            "Pay a report sold as a credit with AstroCoins instead (the "
            "`special_analysis` price). Needs `consumer_ref`."
        ),
    )


class ReportResponse(APIModel):
    id: uuid.UUID
    report_type: ReportType
    source_type: str
    source_id: uuid.UUID | None
    locale: Locale
    status: ReportStatus

    title: str | None
    summary: str | None
    sections: list[ReportSectionResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    interpretation_scope: str | None = None
    safety_note: str | None = None

    prompt_version: str
    context_version: str
    engine_version: str
    provider: str
    model: str
    cached: bool = False
    created_at: datetime


class ReportSummary(APIModel):
    id: uuid.UUID
    report_type: ReportType
    source_type: str
    source_id: uuid.UUID | None
    locale: Locale
    status: ReportStatus
    title: str | None
    model: str
    created_at: datetime


class ReportJobResponse(APIModel):
    id: uuid.UUID
    report_type: ReportType
    status: JobStatus
    attempt: int
    error_code: str | None = None
    report_id: uuid.UUID | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ModelStatus(APIModel):
    """Which model each tier would ask for. Names only, never credentials."""

    low_cost: str
    standard: str
    premium: str


class AIStatusResponse(APIModel):
    """What the client needs to know before offering AI features."""

    configured: bool
    provider: str
    context_version: str
    prompt_versions: dict[str, str]
    locales: list[Locale]

    models: ModelStatus = Field(
        description="The models this server is configured to request."
    )
    fallback: dict[str, bool] = Field(
        default_factory=dict,
        description=(
            "Per use case, whether a cheaper model may serve the request. "
            "Premium reports default to false: a downgraded report should "
            "fail loudly rather than be delivered as the premium reading."
        ),
    )
    diagnostic: str | None = Field(
        default=None,
        description=(
            "Why AI is unavailable, when it is. Never contains credentials."
        ),
    )
