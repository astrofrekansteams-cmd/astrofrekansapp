"""Voice and video call endpoints, and the LiveKit webhook.

The contract, once:

* `POST /calls` opens the call for an order (either party; idempotent).
* `POST /calls/{id}/join` authorises in full and returns a short-lived LiveKit
  token. **The only response that carries a token**, sent `no-store`.
* `GET /calls/{id}` is the backend's view of the call - the status a client
  should trust, because it comes from provider events, not from clients.
* `POST /calls/{id}/end` ends it for both.
* `POST /webhooks/livekit` is LiveKit telling us who joined and who left.
  Signature verified against the raw body, or rejected.

Everything member-scoped answers `404` to non-members.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, UserRateLimit
from app.core.config import settings
from app.core.logging import get_logger
from app.core.rate_limit import RateLimit
from app.db.models.calls import CallParticipant, CallSession
from app.domain.calls import (
    CallEndReason,
    CallStatus,
    CallType,
    ParticipantRole,
    ParticipantStatus,
)
from app.schemas.calls import (
    CallCreateRequest,
    CallJoinResponse,
    CallPageResponse,
    CallParticipantResponse,
    CallResponse,
    CallStatusResponse,
    CallSummary,
    RoomOptions,
)
from app.services.calls import policy
from app.services.calls.factory import calls_available, get_call_provider
from app.services.calls.provider import (
    CallProviderNotConfigured,
    CallProviderUnavailable,
    InvalidWebhook,
)
from app.services.calls.service import CallService

logger = get_logger(__name__)

router = APIRouter(prefix="/calls", tags=["calls"])
webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_create_limit = Depends(
    UserRateLimit(settings.call_create_rate_limit, scope="call_create")
)
_join_limit = Depends(
    UserRateLimit(settings.call_join_token_rate_limit, scope="call_join_token")
)
_end_limit = Depends(UserRateLimit(settings.call_end_rate_limit, scope="call_end"))
# Keyed by IP, not user: LiveKit is not a user. The signature is the real
# protection; this bounds the cost of checking signatures on garbage.
_webhook_limit = Depends(
    RateLimit(settings.livekit_webhook_rate_limit, scope="livekit_webhook")
)

# A join token must not be kept by anything between us and the client.
NO_STORE = {"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"}


def _require_calls() -> None:
    if not calls_available():
        raise CallProviderNotConfigured()


def _service(session) -> CallService:  # noqa: ANN001
    return CallService(session, get_call_provider())


def _role_of(call: CallSession, user_id: uuid.UUID) -> ParticipantRole:
    return ParticipantRole.USER if user_id == call.user_id else ParticipantRole.EXPERT


async def _to_schema(session, call: CallSession, viewer_id: uuid.UUID) -> CallResponse:  # noqa: ANN001
    participants = list(
        await session.scalars(
            select(CallParticipant)
            .where(CallParticipant.call_session_id == call.id)
            .order_by(CallParticipant.role)
        )
    )
    window = policy.window_for(
        call.scheduled_start_at, call.scheduled_end_at, created_at=call.created_at
    )
    return CallResponse(
        id=call.id,
        order_id=call.order_id,
        appointment_id=call.appointment_id,
        conversation_id=call.conversation_id,
        call_type=CallType(call.call_type),
        status=CallStatus(call.status),
        my_role=_role_of(call, viewer_id),
        scheduled_start_at=call.scheduled_start_at,
        scheduled_end_at=call.scheduled_end_at,
        join_opens_at=window.opens_at,
        join_closes_at=window.closes_at,
        ringing_at=call.ringing_at,
        started_at=call.started_at,
        ended_at=call.ended_at,
        end_reason=CallEndReason(call.end_reason) if call.end_reason else None,
        duration_seconds=call.duration_seconds,
        # Status and timestamps only. Never the other party's LiveKit
        # identity, which is theirs to present, not ours to hand out.
        participants=[
            CallParticipantResponse(
                role=ParticipantRole(item.role),
                status=ParticipantStatus(item.status),
                is_me=item.user_id == viewer_id,
                first_joined_at=item.first_joined_at,
                last_left_at=item.last_left_at,
            )
            for item in participants
        ],
        recording_enabled=False,
        created_at=call.created_at,
    )


# ------------------------------------------------------------------ status


@router.get(
    "/status",
    response_model=CallStatusResponse,
    summary="Whether voice and video calls work on this server",
    description="`configured` and the provider name. Never a URL or a key.",
)
async def call_status(user: CurrentUser) -> CallStatusResponse:
    return CallStatusResponse(
        configured=calls_available(), provider=settings.realtime_provider
    )


# -------------------------------------------------------------------- calls


@router.post(
    "",
    response_model=CallResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_create_limit],
    summary="Open the call for an order",
    description=(
        "Either party may open it. Idempotent: while a call for the order is "
        "live, both parties get that same call (`200`), never a second room. "
        "Eligibility comes from the order, its payment, its appointment and "
        "the catalogue."
    ),
)
async def create_call(
    payload: CallCreateRequest,
    user: CurrentUser,
    session: DbSession,
    response: Response,
) -> CallResponse:
    _require_calls()
    call, created = await _service(session).create(
        user,
        order_id=payload.order_id,
        call_type=payload.call_type,
        appointment_id=payload.appointment_id,
    )
    if created and call.status == CallStatus.FAILED.value:
        # Recorded, not rolled back: the failed attempt is part of the audit
        # trail, and the order is untouched. Opening the call again is a new
        # attempt.
        await session.commit()
        raise CallProviderUnavailable(details={"call_id": str(call.id)})

    await session.commit()
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return await _to_schema(session, call, user.id)


@router.get(
    "",
    response_model=CallPageResponse,
    summary="Your calls, as user or as expert",
)
async def list_calls(
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    before: datetime | None = Query(default=None),
) -> CallPageResponse:
    rows = await _service(session).list_for_user(user, limit=limit, before=before)
    return CallPageResponse(
        items=[
            CallSummary(
                id=row.id,
                order_id=row.order_id,
                call_type=CallType(row.call_type),
                status=CallStatus(row.status),
                my_role=_role_of(row, user.id),
                started_at=row.started_at,
                ended_at=row.ended_at,
                duration_seconds=row.duration_seconds,
                end_reason=CallEndReason(row.end_reason) if row.end_reason else None,
                created_at=row.created_at,
            )
            for row in rows
        ],
        next_cursor=rows[-1].created_at if len(rows) == limit else None,
    )


@router.get(
    "/{call_id}",
    response_model=CallResponse,
    summary="One call",
    description=(
        "Also applies whatever the clock says has happened - a ring timeout, a "
        "reconnect grace running out - so the status is current. No token."
    ),
)
async def get_call(
    call_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> CallResponse:
    call, _ = await _service(session).get_for_member(user, call_id)
    await session.commit()
    return await _to_schema(session, call, user.id)


@router.post(
    "/{call_id}/join",
    response_model=CallJoinResponse,
    dependencies=[_join_limit],
    summary="Get a LiveKit token to join",
    description=(
        "Re-authorises everything - membership, order, payment, expert, "
        "appointment window, call state - every time, including a reissue "
        "after a token expired before connecting. The response is sensitive "
        "and sent `Cache-Control: no-store`."
    ),
)
async def join_call(
    call_id: uuid.UUID, user: CurrentUser, session: DbSession, response: Response
) -> CallJoinResponse:
    _require_calls()
    response.headers.update(NO_STORE)
    grant = await _service(session).issue_join_token(user, call_id)
    await session.commit()

    call_type = CallType(grant.call.call_type)
    return CallJoinResponse(
        call_id=grant.call.id,
        call_type=call_type,
        livekit_url=grant.client_url,
        token=grant.token.token,
        token_expires_at=grant.token.expires_at,
        participant_identity=grant.participant.provider_identity,
        role=ParticipantRole(grant.participant.role),
        room_options=RoomOptions(audio=True, video=call_type is CallType.VIDEO),
    )


@router.post(
    "/{call_id}/end",
    response_model=CallResponse,
    dependencies=[_end_limit],
    summary="End the call",
    description=(
        "Either party. An active call becomes `ended`; one that never became "
        "active is `cancelled`. Idempotent, and final: an ended call never "
        "becomes live again."
    ),
)
async def end_call(
    call_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> CallResponse:
    call = await _service(session).end(user, call_id)
    await session.commit()
    return await _to_schema(session, call, user.id)


# ------------------------------------------------------------------ webhook


@webhook_router.post(
    "/livekit",
    dependencies=[_webhook_limit],
    summary="LiveKit webhook receiver",
    description=(
        "Verified against the raw request body: the `Authorization` header is "
        "a JWT from our API key carrying the body's SHA-256. Anything that "
        "does not verify is `401 invalid_webhook`. Verified events are applied "
        "idempotently by event id."
    ),
    include_in_schema=True,
)
async def livekit_webhook(request: Request, session: DbSession) -> dict[str, str]:
    provider = get_call_provider()
    if not calls_available():
        raise CallProviderNotConfigured()

    # The raw bytes, exactly as sent. Parsed JSON re-serialised would not hash
    # to what LiveKit signed.
    body = await request.body()
    try:
        event = provider.parse_webhook(body, request.headers.get("authorization"))
    except InvalidWebhook:
        # Neither the header nor the body is logged: both are attacker-supplied
        # and the header may be a real token.
        logger.warning(
            "livekit_webhook_rejected",
            has_authorization=bool(request.headers.get("authorization")),
            body_bytes=len(body),
        )
        raise

    outcome = await _service(session).apply_provider_event(event)
    await session.commit()
    return {"status": "ok", "outcome": outcome}
