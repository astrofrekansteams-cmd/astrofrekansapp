"""Shared FastAPI dependencies."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, PermissionDenied, TokenError
from app.core.logging import get_logger, user_id_var
from app.core.rate_limit import Quota, RateLimit, client_key
from app.core.security import TOKEN_TYPE_ACCESS, decode_token
from app.db.models.user import User
from app.db.session import get_db_session
from app.domain.enums import SubscriptionTier
from app.repositories.user_repository import UserRepository
from app.services.astrology.service import ChartService, get_chart_service
from app.services.auth.service import AuthService, RequestContext

logger = get_logger(__name__)

bearer_scheme = HTTPBearer(
    auto_error=False,
    description=(
        "A backend access token or a Firebase ID token. Which one is "
        "accepted depends on AUTH_MODE; `hybrid` takes both."
    ),
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async for session in get_db_session():
        yield session


DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_auth_service(session: DbSession) -> AuthService:
    return AuthService(session)


def request_context(request: Request) -> RequestContext:
    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    return RequestContext(user_agent=request.headers.get("user-agent"), ip_address=ip)


async def get_current_user(
    request: Request,
    session: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> User:
    """Resolve the caller, whichever credential they presented.

    One `Bearer` header, two possible credentials: the backend's own access
    token, or a Firebase ID token. Both resolve to the same local `User`, so no
    business service ever needs to know which was used - and the Firebase
    migration does not touch a single route.

    A local JWT is tried first because it is free to check (a signature, no
    network). A Firebase token is only verified if that fails, so the common
    path never pays for the uncommon one.
    """
    if credentials is None or not credentials.credentials:
        raise AuthenticationError()

    token = credentials.credentials
    user: User | None = None
    source = "local_jwt"

    if settings.accepts_local_jwt:
        try:
            payload = decode_token(token, token_type=TOKEN_TYPE_ACCESS)
        except Exception:  # noqa: BLE001 - fall through to Firebase
            payload = None
        if payload is not None:
            try:
                user_id = uuid.UUID(payload["sub"])
            except (KeyError, ValueError) as exc:
                raise TokenError() from exc
            user = await UserRepository(session).get(user_id)

    if user is None and settings.accepts_firebase_token:
        user = await _user_from_firebase_token(session, token, request)
        source = "firebase"

    if user is None:
        # Neither credential was usable. Which one failed is not a client's
        # business - saying so would help somebody work out which tokens a
        # given account accepts.
        raise AuthenticationError()

    if not user.is_active:
        raise AuthenticationError("This account is no longer active.")

    # Bind the id (never the email) to logs and to the rate limiter.
    request.state.user_id = str(user.id)
    request.state.identity_source = source
    user_id_var.set(str(user.id))
    return user


async def _user_from_firebase_token(
    session: AsyncSession, token: str, request: Request | None = None
) -> User | None:
    """Verify a Firebase ID token and map it to a local account.

    Verification goes through the Admin SDK - signature, issuer, audience and
    expiry - never by decoding the payload and believing it.
    """
    from app.services.firebase.factory import firebase_available, get_firebase
    from app.services.firebase.identity import FirebaseIdentityService
    from app.services.firebase.provider import FirebaseError, FirebaseNotConfigured

    if not firebase_available():
        return None

    providers = get_firebase()
    try:
        identity = await providers.identity.verify_id_token(token)
    except FirebaseNotConfigured:
        return None
    except FirebaseError:
        # An expired, revoked or malformed Firebase token is a real
        # authentication failure and is reported as one.
        raise

    if request is not None:
        # What the sessions view may say about this sign-in: the provider
        # (password, google.com, apple.com) and when it happened. Never the
        # token.
        request.state.firebase_sign_in = {
            "provider": identity.provider_id,
            "auth_time": identity.auth_time,
        }

    service = FirebaseIdentityService(session, providers.identity)
    resolved = await service.resolve(identity)
    await session.commit()

    logger.info(
        "firebase_token_verified",
        user_id=str(resolved.id),
        firebase_uid=identity.uid,
        provider=identity.provider_id,
    )

    # Re-read through the repository so the request gets a fully loaded user,
    # exactly as the local-JWT path does. A freshly inserted instance has never
    # had its relationships loaded, and touching one later - `user.tier` reads
    # the subscription - would attempt IO outside the async context.
    return await UserRepository(session).get(resolved.id)


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_sensitive_user(
    request: Request,
    user: CurrentUser,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> User:
    """`CurrentUser`, re-checked with Firebase for security-sensitive actions.

    `FIREBASE_CHECK_REVOKED` stays off globally: asking Firebase on every
    request costs ~0.26 s and makes a Firebase outage an outage of the app.
    The actions where a revoked or disabled sign-in must stop *now*, not
    within the hour an ID token lives - changing the password, deleting the
    account, verifying a purchase, managing sessions - ask here instead:
    revoked -> 401, disabled -> 403, Firebase unreachable -> 502 (not a
    sign-out). A local JWT needs nothing extra: its sessions are the
    backend's own.
    """
    if getattr(request.state, "identity_source", None) != "firebase" or credentials is None:
        return user
    from app.services.firebase.factory import get_firebase

    await get_firebase().identity.verify_id_token(
        credentials.credentials, check_revoked=True
    )
    return user


SensitiveUser = Annotated[User, Depends(get_sensitive_user)]


class UserRateLimit(RateLimit):
    """A quota for an authenticated route, keyed by the user.

    Route-level dependencies are resolved before the endpoint's own
    parameters, so by the time a plain `RateLimit` runs nothing has verified
    the token yet and `request.state.user_id` is still empty - the limit
    silently falls back to the client IP. That is the wrong bucket for a
    signed-in feature: everyone behind one NAT or one carrier gateway would
    share a quota, and a single heavy user could lock out strangers.

    Declaring the authenticated user here makes FastAPI resolve it first. The
    dependency is cached per request, so the endpoint's own `CurrentUser`
    costs nothing extra.
    """

    async def __call__(self, request: Request, user: CurrentUser) -> None:  # type: ignore[override]
        await super().__call__(request)

    def identify(self, request: Request) -> str:
        user_id = getattr(request.state, "user_id", None)
        return f"user:{user_id}" if user_id else client_key(request)


class TieredUserRateLimit(UserRateLimit):
    """A per-user quota that may differ for premium (B11).

    The tier comes from `User.tier`, which is the projection of verified store
    entitlements - never from anything the client says. When no premium quota
    is configured, premium users get the free quota: the product has not
    decided the number, and this seam does not invent one.
    """

    def __init__(self, expression: str, *, premium: str | None = None, **kwargs) -> None:  # noqa: ANN003
        super().__init__(expression, **kwargs)
        self.premium_quota = Quota.parse(premium) if premium else None

    async def __call__(self, request: Request, user: CurrentUser) -> None:  # type: ignore[override]
        quota = (
            self.premium_quota
            if self.premium_quota is not None and user.tier.includes(SubscriptionTier.PREMIUM)
            else self.quota
        )
        await self.enforce(request, quota)


async def require_premium(user: CurrentUser) -> User:
    if not user.tier.includes(SubscriptionTier.PREMIUM):
        raise PermissionDenied(
            "This feature requires an Astrofrekans Premium subscription.",
            code="premium_required",
        )
    return user


PremiumUser = Annotated[User, Depends(require_premium)]


def get_charts() -> ChartService:
    return get_chart_service()


Charts = Annotated[ChartService, Depends(get_charts)]
