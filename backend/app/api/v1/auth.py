from __future__ import annotations

from typing import Annotated

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from app.api.deps import (
    CurrentUser,
    DbSession,
    SensitiveUser,
    UserRateLimit,
    request_context,
)
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.core.rate_limit import RateLimit
from app.core.security import TOKEN_TYPE_ACCESS, decode_token
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    ResetTokenCheckRequest,
    ResetTokenStatus,
    SessionResponse,
    TokenResponse,
)
from app.schemas.common import Message
from app.schemas.user import UserProfileResponse
from app.services.auth.service import AuthResult, AuthService, RequestContext, ip_hint
from app.services.mail import get_mailer
from app.services.mail.templates import password_reset_email
from app.services.users.service import UserService, to_user_response

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

Context = Annotated[RequestContext, Depends(request_context)]

RESET_REQUESTED_MESSAGE = "If the account is eligible, a reset link has been sent."


class SessionNotRevocable(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "session_not_revocable"
    message = "This sign-in is managed by Firebase; sign out on that device instead."


class PasswordResetUnavailable(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "password_reset_unavailable"
    message = "Password reset by email is not available right now."


async def send_password_reset_email(email: str, token: str, language: str | None) -> None:
    """Runs after the response. A failure is logged, never shown to anyone.

    The mailer retries transient failures itself; what reaches here is final.
    Neither the address nor the token is ever logged.
    """
    try:
        await get_mailer().send(password_reset_email(to=email, token=token, language=language))
    except Exception as error:  # noqa: BLE001 - never reaches the client
        logger.warning(
            "password_reset_email_failed",
            reason=getattr(error, "reason", type(error).__name__),
        )


def _tokens(result: AuthResult) -> TokenResponse:
    return TokenResponse(
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
        expires_at=result.tokens.access_expires_at,
        refresh_expires_at=result.tokens.refresh_expires_at,
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimit(settings.register_rate_limit, scope="register"))],
    summary="Create an account",
)
async def register(
    payload: RegisterRequest, session: DbSession, context: Context
) -> TokenResponse:
    service = AuthService(session)
    result = await service.register(
        email=payload.email,
        password=payload.password,
        name=payload.name,
        language=payload.language,
        timezone=payload.timezone,
        context=context,
    )
    # Birth data is optional at sign-up; when present it is stored right away
    # (and geocoded if only a place name was given).
    if payload.birth_date is not None:
        await UserService(session).upsert_birth_profile(
            user=result.user,
            birth_date=payload.birth_date,
            birth_time=payload.birth_time,
            birth_place=payload.birth_place,
            latitude=None,
            longitude=None,
            timezone=None,
            house_system=payload.house_system,
        )
    await session.commit()
    return _tokens(result)


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(RateLimit(settings.login_rate_limit, scope="login"))],
    summary="Sign in with email and password",
)
async def login(
    payload: LoginRequest, session: DbSession, context: Context
) -> TokenResponse:
    result = await AuthService(session).login(
        email=payload.email, password=payload.password, context=context
    )
    await session.commit()
    return _tokens(result)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(RateLimit("60/hour", scope="refresh"))],
    summary="Rotate the refresh token",
)
async def refresh(
    payload: RefreshRequest, session: DbSession, context: Context
) -> TokenResponse:
    result = await AuthService(session).refresh(
        refresh_token=payload.refresh_token, context=context
    )
    await session.commit()
    return _tokens(result)


@router.post("/logout", response_model=Message, summary="Revoke the current session")
async def logout(
    payload: LogoutRequest, session: DbSession, request: Request
) -> Message:
    service = AuthService(session)
    if payload.refresh_token:
        await service.logout(refresh_token=payload.refresh_token)
    await session.commit()
    return Message(message="Signed out.")


@router.post(
    "/logout-all",
    response_model=Message,
    summary="Revoke every session of the current user",
)
async def logout_all(user: SensitiveUser, session: DbSession) -> Message:
    await AuthService(session).logout_everywhere(user)
    await session.commit()
    return Message(message="All sessions revoked.")


@router.post(
    "/forgot-password",
    response_model=Message,
    dependencies=[Depends(RateLimit("5/hour", scope="forgot_password"))],
    summary="Start a password reset",
)
async def forgot_password(
    payload: ForgotPasswordRequest, session: DbSession, background: BackgroundTasks
) -> Message:
    # No mail provider: say so, to everyone alike. Answering "sent" when
    # nothing can be sent would leave a locked-out user waiting for an email
    # that never comes. The answer does not depend on the address, so it
    # reveals nothing about which accounts exist.
    if not get_mailer().configured:
        raise PasswordResetUnavailable()

    service = AuthService(session)
    token = await service.request_password_reset(email=payload.email)
    language = await service.language_for_email(payload.email) if token else None
    await session.commit()

    # Sent after the response, so an eligible address does not take longer to
    # answer than an unknown one. The token is never in the response - that
    # would hand the account to anyone who can guess an address.
    if token:
        background.add_task(send_password_reset_email, payload.email, token, language)

    # Same answer whether or not the address exists or is eligible.
    return Message(message=RESET_REQUESTED_MESSAGE)


@router.post(
    "/reset-password/check",
    response_model=ResetTokenStatus,
    dependencies=[Depends(RateLimit("30/hour", scope="reset_password_check"))],
    summary="Is this reset link still usable?",
    description=(
        "Lets the app show an expired or used link before the new password is "
        "typed. `401 token_expired` or `401 token_used` otherwise."
    ),
)
async def check_reset_token(
    payload: ResetTokenCheckRequest, session: DbSession
) -> ResetTokenStatus:
    expires_at = await AuthService(session).check_reset_token(token=payload.token)
    return ResetTokenStatus(valid=True, expires_at=expires_at)


@router.post(
    "/reset-password",
    response_model=Message,
    dependencies=[Depends(RateLimit("10/hour", scope="reset_password"))],
    summary="Finish a password reset",
)
async def reset_password(
    payload: ResetPasswordRequest, session: DbSession
) -> Message:
    await AuthService(session).reset_password(
        token=payload.token, new_password=payload.new_password
    )
    await session.commit()
    return Message(message="Password updated.")


def _current_session_id(request: Request) -> uuid.UUID | None:
    """The caller's own login session, when they use a backend token."""
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        return None
    try:
        payload = decode_token(header[7:].strip(), token_type=TOKEN_TYPE_ACCESS)
        return uuid.UUID(payload["sid"])
    except Exception:  # noqa: BLE001 - a Firebase token, or an older token without sid
        return None


@router.get(
    "/sessions",
    response_model=list[SessionResponse],
    summary="Where you are signed in",
    description=(
        "Email-and-password sign-ins, one row per device session. `current` "
        "marks the session making this request. Firebase sign-ins are managed "
        "by Firebase and are not listed; push-registered devices are under "
        "`/devices/push`."
    ),
)
async def list_sessions(
    request: Request, user: SensitiveUser, session: DbSession
) -> list[SessionResponse]:
    current = _current_session_id(request)
    rows = await AuthService(session).list_sessions(user)
    listed = [
        SessionResponse(**{**row, "id": str(row["id"])}, current=row["id"] == current)
        for row in rows
    ]
    firebase = getattr(request.state, "firebase_sign_in", None)
    if firebase is not None:
        # A Firebase sign-in is not a session this server holds: Firebase
        # issues and refreshes its tokens. It is shown for this device only,
        # honestly marked as not revocable here; other devices' Firebase
        # sign-ins are not visible to the server at all.
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        signed_in = (
            datetime.fromtimestamp(firebase["auth_time"], UTC)
            if firebase.get("auth_time")
            else now
        )
        context = request_context(request)
        listed.insert(
            0,
            SessionResponse(
                id="firebase:current",
                kind="firebase",
                revocable=False,
                sign_in_provider=firebase.get("provider"),
                created_at=signed_in,
                last_used_at=now,
                user_agent=context.user_agent,
                ip_hint=ip_hint(context.ip_address),
                current=True,
            ),
        )
    return listed


@router.delete(
    "/sessions/{session_id}",
    responses={409: {"description": "`session_not_revocable`: a Firebase sign-in."}},
    response_model=Message,
    summary="Sign out one session",
    description=(
        "Revokes that session's refresh token at once. An access token already "
        "issued to it stays valid until it expires (minutes)."
    ),
)
async def revoke_session(
    session_id: str, user: SensitiveUser, session: DbSession
) -> Message:
    if session_id.startswith("firebase:"):
        raise SessionNotRevocable()
    try:
        parsed = uuid.UUID(session_id)
    except ValueError:
        from app.core.exceptions import NotFound

        raise NotFound("Session not found.") from None
    await AuthService(session).revoke_session(user, parsed)
    await session.commit()
    return Message(message="Session signed out.")


@router.post(
    "/change-password",
    response_model=Message,
    summary="Change your password",
    # Per account: the current password must not be guessable by retrying.
    dependencies=[Depends(UserRateLimit("10/hour", scope="change_password"))],
)
async def change_password(
    payload: ChangePasswordRequest, user: SensitiveUser, session: DbSession
) -> Message:
    await AuthService(session).change_password(
        user=user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    await session.commit()
    return Message(message="Password updated. Please sign in again.")


@router.get("/me", response_model=UserProfileResponse, summary="Current user")
async def me(user: CurrentUser) -> UserProfileResponse:
    return to_user_response(user)
