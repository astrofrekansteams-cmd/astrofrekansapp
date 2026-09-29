"""Firebase sign-in endpoints.

Deliberately small. The business API accepts a Firebase ID token directly in the
`Authorization` header, so there is no exchange step and **no backend JWT is
minted for a Firebase session**. Wrapping one token in another would mean two
session lifetimes to keep in step, two revocation stories, and a refresh token
whose expiry nobody is watching.

What is here:

* `GET /auth/capabilities` - what this server accepts, so a client knows whether
  to initialise Firebase at all.
* `POST /auth/firebase/session` - resolve a token to a local account and say
  whether that created one. Optional: the same mapping happens implicitly on any
  authenticated request.
* `POST /auth/firebase/link` / `DELETE` - attach or detach a Firebase identity
  to the account the caller is **already signed in to**. Being signed in is the
  proof of ownership that a matching email address is not.

The existing email/password endpoints are untouched.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, status

from app.api.deps import CurrentUser, DbSession, UserRateLimit
from app.core.config import settings
from app.core.rate_limit import RateLimit
from app.schemas.chat import (
    AuthCapabilitiesResponse,
    FirebaseLinkRequest,
    FirebaseSessionResponse,
)
from app.schemas.common import Message
from app.services.firebase.factory import firebase_available, get_firebase
from app.services.mail import get_mailer
from app.services.firebase.identity import (
    LINK_EXISTING_SESSION,
    FirebaseIdentityService,
)
from app.services.firebase.provider import FirebaseNotConfigured

router = APIRouter(prefix="/auth", tags=["auth"])

# Unauthenticated: this is the route a client uses *before* it has a session,
# so it is limited by IP rather than by user.
_bootstrap_limit = Depends(
    RateLimit(
        settings.firebase_auth_bootstrap_rate_limit,
        scope="firebase_auth_bootstrap",
    )
)
_link_limit = Depends(
    UserRateLimit(
        settings.firebase_auth_bootstrap_rate_limit,
        scope="firebase_auth_bootstrap",
    )
)


@router.get(
    "/capabilities",
    response_model=AuthCapabilitiesResponse,
    summary="Which credentials this server accepts",
    description=(
        "Lets a client decide whether to initialise Firebase. Returns the "
        "project id so the client knows which project to talk to - never a key "
        "of any kind."
    ),
)
async def capabilities() -> AuthCapabilitiesResponse:
    return AuthCapabilitiesResponse(
        auth_mode=settings.auth_mode,
        accepts_local_jwt=settings.accepts_local_jwt,
        accepts_firebase_token=settings.accepts_firebase_token,
        firebase_configured=firebase_available(),
        password_reset_email=settings.accepts_local_jwt and get_mailer().configured,
        # Public configuration, not a secret: a client needs it to initialise.
        firebase_project_id=(
            settings.firebase_project_id if firebase_available() else None
        ),
    )


@router.post(
    "/firebase/session",
    response_model=FirebaseSessionResponse,
    dependencies=[_bootstrap_limit],
    summary="Resolve a Firebase ID token to a local account",
    description=(
        "Optional. The same mapping happens on any authenticated request, so a "
        "client may skip this and simply send its Firebase token as the bearer "
        "token. Useful on first sign-in, to learn the local user id and whether "
        "an account was just created.\n\n"
        "No backend JWT is issued: the Firebase SDK owns the session lifecycle "
        "on the client."
    ),
)
async def firebase_session(
    session: DbSession,
    id_token: str = Body(embed=True, min_length=16, max_length=4096),
) -> FirebaseSessionResponse:
    if not settings.accepts_firebase_token:
        raise FirebaseNotConfigured(
            "This server is not accepting Firebase sign-in.",
            code="firebase_auth_disabled",
        )
    if not firebase_available():
        raise FirebaseNotConfigured()

    providers = get_firebase()
    identity = await providers.identity.verify_id_token(id_token)

    service = FirebaseIdentityService(session, providers.identity)
    user, created = await service.resolve_detailed(identity)
    await session.commit()

    return FirebaseSessionResponse(
        user_id=user.id,
        firebase_uid=identity.uid,
        email=user.email,
        email_verified=user.is_email_verified,
        is_new_account=created,
        provider_id=identity.provider_id,
        auth_mode=settings.auth_mode,
    )


@router.post(
    "/firebase/link",
    response_model=FirebaseSessionResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[_link_limit],
    summary="Link a Firebase identity to your account",
    description=(
        "The safe linking path. The caller is already signed in, which is the "
        "proof of ownership a matching email address is not - so this is how a "
        "user with an existing password account adds Google or Apple sign-in."
    ),
)
async def link_firebase_identity(
    payload: FirebaseLinkRequest, user: CurrentUser, session: DbSession
) -> FirebaseSessionResponse:
    if not firebase_available():
        raise FirebaseNotConfigured()

    providers = get_firebase()
    identity = await providers.identity.verify_id_token(payload.id_token)

    service = FirebaseIdentityService(session, providers.identity)
    linked = await service.link(user, identity, method=LINK_EXISTING_SESSION)
    await session.commit()

    return FirebaseSessionResponse(
        user_id=linked.id,
        firebase_uid=identity.uid,
        email=linked.email,
        email_verified=linked.is_email_verified,
        is_new_account=False,
        provider_id=identity.provider_id,
        auth_mode=settings.auth_mode,
    )


@router.delete(
    "/firebase/link",
    response_model=Message,
    summary="Unlink your Firebase identity",
    description=(
        "Refused when it would leave the account with no way to sign in - set a "
        "password first."
    ),
)
async def unlink_firebase_identity(
    user: CurrentUser, session: DbSession
) -> Message:
    providers = get_firebase()
    await FirebaseIdentityService(session, providers.identity).unlink(user)
    await session.commit()
    return Message(message="Sign-in method removed.")
