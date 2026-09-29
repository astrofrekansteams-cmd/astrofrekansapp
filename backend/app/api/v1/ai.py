"""Astro AI endpoints.

Every route here follows the same order: authenticate, authorise the source,
build the context from engine output, then call the model. Nothing reaches a
provider that the caller was not entitled to, and nothing astrological is left
for the model to work out for itself.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.deps import TieredUserRateLimit, CurrentUser, DbSession, UserRateLimit
from app.core.config import settings
from app.db.models.ai import AIReport
from app.domain.ai import (
    CompletionStatus,
    ContextType,
    JobStatus,
    Locale,
    MessageRole,
    ReportType,
)
from app.schemas.ai import (
    AIStatusResponse,
    ChatRequest,
    ChatResponse,
    ConversationCreateRequest,
    ConversationResponse,
    GenerationMetadataResponse,
    InfluenceResponse,
    MessageResponse,
    ModelStatus,
    ReportJobResponse,
    ReportRequest,
    ReportResponse,
    ReportSectionResponse,
    ReportSummary,
)
from app.schemas.common import Message
from app.services.ai import prompts
from app.services.ai.chat import to_sse
from app.services.ai.context.builder import CONTEXT_VERSION
from app.services.ai.diagnostics import describe as describe_ai
from app.services.ai.conversations import ConversationService
from app.services.ai.factory import (
    ai_available,
    build_chat_service,
    build_report_service,
    get_ai_provider,
)
from app.core.exceptions import AppError
from app.services.ai.provider import AIGenerationFailed, AINotConfigured
from app.services.ai.report_access import (
    ReportCreditConflict,
    ReportCreditUnavailable,
    ReportPaymentRequired,
)
from app.services.ai.reports import ReportOutcome

router = APIRouter(prefix="/ai", tags=["astro-ai"])

# All three report `ai_rate_limited`: from a client's point of view our quota
# and the provider's throttling call for the same response, and `Retry-After`
# says how long to wait.
# Tier-aware since B11: premium may get its own quota once the product sets
# one (AI_CHAT_RATE_LIMIT_PREMIUM); until then, the free quota applies to all.
_chat_limit = Depends(
    TieredUserRateLimit(
        settings.ai_chat_rate_limit,
        premium=settings.ai_chat_rate_limit_premium,
        scope="ai_chat",
        code="ai_rate_limited",
    )
)
_stream_limit = Depends(
    UserRateLimit(
        settings.ai_stream_rate_limit, scope="ai_stream", code="ai_rate_limited"
    )
)
_report_limit = Depends(
    TieredUserRateLimit(
        settings.ai_report_rate_limit,
        premium=settings.ai_report_rate_limit_premium,
        scope="ai_report",
        code="ai_rate_limited",
    )
)


def _require_ai() -> None:
    """A missing key is a controlled 503, never a crash."""
    if not ai_available():
        raise AINotConfigured()


def _locale(requested: Locale | None, user) -> Locale:  # noqa: ANN001
    if requested is not None:
        return requested
    preferred = (user.profile.language if user.profile else None) or "tr"
    try:
        return Locale(preferred)
    except ValueError:
        return Locale.TR


def _conversation_to_schema(conversation) -> ConversationResponse:  # noqa: ANN001
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        locale=Locale(conversation.locale),
        message_count=conversation.message_count,
        archived=conversation.archived_at is not None,
        has_summary=bool(conversation.summary),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _report_to_schema(report: AIReport, *, cached: bool = False) -> ReportResponse:
    payload = report.sections or {}
    return ReportResponse(
        id=report.id,
        report_type=ReportType(report.report_type),
        source_type=report.source_type,
        source_id=report.source_id,
        locale=Locale(report.locale),
        status=report.status,
        title=report.title,
        summary=report.summary,
        sections=[
            ReportSectionResponse(**section)
            for section in payload.get("sections", [])
        ],
        warnings=(report.warnings or {}).get("warnings", []),
        interpretation_scope=report.interpretation_scope,
        safety_note=report.safety_note,
        prompt_version=report.prompt_version,
        context_version=report.context_version,
        engine_version=report.engine_version,
        provider=report.provider,
        model=report.model,
        cached=cached,
        created_at=report.created_at,
    )


# --------------------------------------------------------------- status


@router.get(
    "/status",
    response_model=AIStatusResponse,
    summary="Whether Astro AI is available on this server",
)
async def status_endpoint(user: CurrentUser) -> AIStatusResponse:
    diagnostic = describe_ai()
    available = ai_available()
    return AIStatusResponse(
        configured=available,
        provider=get_ai_provider().name,
        context_version=CONTEXT_VERSION,
        prompt_versions=prompts.all_versions(),
        locales=list(Locale),
        models=ModelStatus(**diagnostic.models),
        fallback=diagnostic.fallback,
        # Only ever a configuration statement - never a key or a key prefix.
        diagnostic=None if available else diagnostic.reason,
    )


# -------------------------------------------------------- conversations


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a conversation",
)
async def create_conversation(
    payload: ConversationCreateRequest, user: CurrentUser, session: DbSession
) -> ConversationResponse:
    conversation = await ConversationService(session).create(
        user_id=user.id, locale=_locale(payload.locale, user), title=payload.title
    )
    await session.commit()
    return _conversation_to_schema(conversation)


@router.get(
    "/conversations",
    response_model=list[ConversationResponse],
    summary="Your conversations",
)
async def list_conversations(
    user: CurrentUser,
    session: DbSession,
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ConversationResponse]:
    rows = await ConversationService(session).list(
        user_id=user.id, include_archived=include_archived, limit=limit
    )
    return [_conversation_to_schema(row) for row in rows]


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="One conversation",
)
async def get_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> ConversationResponse:
    conversation = await ConversationService(session).get(
        user_id=user.id, conversation_id=conversation_id
    )
    return _conversation_to_schema(conversation)


@router.delete(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Archive a conversation",
    description=(
        "Archives rather than deletes, so a thread the user paid attention to "
        "is not destroyed by a mistaken tap."
    ),
)
async def archive_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> ConversationResponse:
    conversation = await ConversationService(session).archive(
        user_id=user.id, conversation_id=conversation_id
    )
    await session.commit()
    return _conversation_to_schema(conversation)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
    summary="Messages in a conversation",
)
async def list_messages(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[MessageResponse]:
    service = ConversationService(session)
    conversation = await service.get(
        user_id=user.id, conversation_id=conversation_id
    )
    rows = await service.messages(conversation_id=conversation.id, limit=limit)
    return [
        MessageResponse(
            id=row.id,
            role=MessageRole(row.role),
            content=row.content,
            context_type=ContextType(row.context_type) if row.context_type else None,
            source_factor_ids=(row.source_factor_ids or {}).get("ids", []),
            completion_status=CompletionStatus(row.completion_status),
            created_at=row.created_at,
        )
        for row in rows
    ]


# ------------------------------------------------------------------ chat


async def _conversation_for(session, user, payload: ChatRequest):  # noqa: ANN001
    service = ConversationService(session)
    if payload.conversation_id is not None:
        return await service.get(
            user_id=user.id, conversation_id=payload.conversation_id
        )
    return await service.create(user_id=user.id, locale=_locale(payload.locale, user))


@router.post(
    "/chat",
    response_model=ChatResponse,
    dependencies=[_chat_limit],
    summary="Ask Astro AI",
    description=(
        "Routes the question to the right astrological material, builds the "
        "context from engine output, and returns a grounded answer. Every "
        "factor id in the answer came from the backend - the model cannot "
        "invent one."
    ),
)
async def chat(
    payload: ChatRequest, user: CurrentUser, session: DbSession
) -> ChatResponse:
    _require_ai()
    conversation = await _conversation_for(session, user, payload)

    result = await build_chat_service(session).answer(
        user,
        conversation,
        message=payload.message,
        locale=_locale(payload.locale, user),
        context_mode=payload.context_mode,
    )
    await session.commit()

    metadata = result["metadata"]
    return ChatResponse(
        conversation_id=result["conversation_id"],
        answer=result["answer"],
        context_type=result["context_type"],
        intent=result["intent"],
        source_factor_ids=result["source_factor_ids"],
        context_note=result["context_note"],
        warnings=result["warnings"],
        influences=[InfluenceResponse(**item) for item in result.get("influences", [])],
        metadata=GenerationMetadataResponse(
            model=metadata.model_actual,
            model_requested=metadata.model_requested,
            fallback_reason=metadata.fallback_reason,
            prompt_version=metadata.prompt_version,
            context_version=metadata.context_version,
            input_tokens=metadata.input_tokens,
            output_tokens=metadata.output_tokens,
            total_tokens=metadata.total_tokens,
            latency_ms=metadata.latency_ms,
            provider=metadata.provider,
        ),
    )


@router.post(
    "/chat/stream",
    dependencies=[_stream_limit],
    summary="Ask Astro AI, streamed",
    description=(
        "Server-Sent Events in a provider-independent contract: "
        "`message_start`, `text_delta`, `metadata`, `message_complete`, "
        "`error`. Disconnecting cancels the generation."
    ),
    response_class=StreamingResponse,
)
async def chat_stream(
    payload: ChatRequest, user: CurrentUser, session: DbSession
) -> StreamingResponse:
    _require_ai()
    conversation = await _conversation_for(session, user, payload)
    service = build_chat_service(session)
    locale = _locale(payload.locale, user)

    async def event_source():
        try:
            async for chunk in service.stream(
                user,
                conversation,
                message=payload.message,
                locale=locale,
                context_mode=payload.context_mode,
            ):
                yield to_sse(chunk)
            await session.commit()
        except Exception:  # noqa: BLE001 - the stream owns its own failure
            await session.rollback()
            raise

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# --------------------------------------------------------------- reports


@router.post(
    "/reports",
    response_model=None,
    responses={
        200: {"model": ReportResponse},
        202: {"model": ReportJobResponse},
    },
    dependencies=[_report_limit],
    summary="Generate an interpretation report",
    description=(
        "Reports are snapshots: the same source, prompt and engine versions "
        "return the cached report, while `refresh=true` produces a new one. "
        "Horary and compatibility reports require a source id the caller "
        "owns. With `background=true` the work is queued and the response is "
        "202 with the job, which is then polled at `/ai/report-jobs/{id}`."
    ),
)
async def create_report(
    payload: ReportRequest, user: CurrentUser, session: DbSession
) -> ReportResponse | JSONResponse:
    _require_ai()
    service = build_report_service(session)
    outcome = await service.request(
        user,
        report_type=payload.report_type,
        source_id=payload.source_id,
        locale=_locale(payload.locale, user),
        refresh=payload.refresh,
        background=payload.background,
        consumer_ref=payload.consumer_ref,
        pay_with_coins=payload.pay_with_coins,
    )
    # A paid report's credit reservation and job are committed here, before
    # any generation: there is never a held credit without its job.
    await session.commit()
    return await deliver_report(service, session, user, outcome)


async def deliver_report(service, session, user, outcome: ReportOutcome):  # noqa: ANN001, ANN201
    """Turn a `ReportOutcome` into the response. Shared with divination.

    200 with the report when there is one; 202 with the job when the work is
    queued or running elsewhere. A synchronous paid report runs here, after its
    reservation is committed; its credit is consumed in the commit that
    completes it.
    """
    if outcome.report is not None:
        return _report_to_schema(outcome.report, cached=outcome.cached)

    job = outcome.job
    if outcome.run_inline:
        job = await service.run_job(job, user)
        await session.commit()
        if job.status == JobStatus.COMPLETED.value and job.report_id is not None:
            report = await service.get(user=user, report_id=job.report_id)
            return _report_to_schema(report, cached=False)
        if job.status == JobStatus.FAILED.value:
            raise _job_failure(job)

    # A queued job is a success with a different shape, not an error.
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=jsonable_encoder(_job_to_schema(job)),
    )


def _job_failure(job) -> AppError:  # noqa: ANN001
    """The error a failed synchronous paid report answers with."""
    known = {
        cls.code: cls
        for cls in (ReportPaymentRequired, ReportCreditUnavailable, ReportCreditConflict)
    }
    details = {"job_id": str(job.id)}
    error_class = known.get(job.error_code or "")
    if error_class is not None:
        return error_class(details=details)
    return AIGenerationFailed(
        "The report could not be generated. Retry with the same consumer_ref.",
        code=job.error_code or "generation_failed",
        details=details,
    )


@router.post(
    "/report-jobs",
    response_model=None,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"model": ReportJobResponse},
        200: {"model": ReportResponse},
    },
    dependencies=[_report_limit],
    summary="Queue a report for background generation",
)
async def create_report_job(
    payload: ReportRequest, user: CurrentUser, session: DbSession
) -> ReportJobResponse | JSONResponse:
    """202 with the job; 200 with the report when a paid replay is complete."""
    _require_ai()
    service = build_report_service(session)
    outcome = await service.request(
        user,
        report_type=payload.report_type,
        source_id=payload.source_id,
        locale=_locale(payload.locale, user),
        refresh=payload.refresh,
        background=True,
        consumer_ref=payload.consumer_ref,
        pay_with_coins=payload.pay_with_coins,
    )
    await session.commit()
    if outcome.report is not None:
        # Nothing to queue: a snapshot already paid for, or a replay of a
        # completed paid job.
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=jsonable_encoder(
                _report_to_schema(outcome.report, cached=outcome.cached)
            ),
        )
    return _job_to_schema(outcome.job)


@router.get(
    "/report-jobs/{job_id}",
    response_model=ReportJobResponse,
    summary="Report job status",
)
async def get_report_job(
    job_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> ReportJobResponse:
    job = await build_report_service(session).get_job(user=user, job_id=job_id)
    return _job_to_schema(job)


@router.post(
    "/report-jobs/{job_id}/cancel",
    response_model=ReportJobResponse,
    summary="Cancel a queued report job",
)
async def cancel_report_job(
    job_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> ReportJobResponse:
    job = await build_report_service(session).cancel_job(user=user, job_id=job_id)
    await session.commit()
    return _job_to_schema(job)


@router.get(
    "/reports",
    response_model=list[ReportSummary],
    summary="Your reports",
)
async def list_reports(
    user: CurrentUser,
    session: DbSession,
    report_type: ReportType | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ReportSummary]:
    rows = await build_report_service(session).list(
        user=user, report_type=report_type, limit=limit
    )
    return [
        ReportSummary(
            id=row.id,
            report_type=ReportType(row.report_type),
            source_type=row.source_type,
            source_id=row.source_id,
            locale=Locale(row.locale),
            status=row.status,
            title=row.title,
            model=row.model,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get(
    "/reports/{report_id}",
    response_model=ReportResponse,
    summary="One report",
)
async def get_report(
    report_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> ReportResponse:
    report = await build_report_service(session).get(user=user, report_id=report_id)
    return _report_to_schema(report)


def _job_to_schema(job) -> ReportJobResponse:  # noqa: ANN001
    return ReportJobResponse(
        id=job.id,
        report_type=ReportType(job.report_type),
        status=JobStatus(job.status),
        attempt=job.attempt,
        error_code=job.error_code,
        report_id=job.report_id,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )

