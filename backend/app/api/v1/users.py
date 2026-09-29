from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, Query, status

from app.api.deps import CurrentUser, DbSession, SensitiveUser
from app.core.rate_limit import RateLimit
from app.schemas.common import Message
from app.api.deps import UserRateLimit
from app.schemas.user import (
    AccountDeletionRequest,
    BirthProfileRequest,
    DeletionCheckResponse,
    SavedPersonUpdateRequest,
    BirthProfileResponse,
    GeocodeResponse,
    GeocodeResult,
    SavedPersonRequest,
    SavedPersonResponse,
    UpdateProfileRequest,
    UserProfileResponse,
)
from app.services.geocoding.providers import get_geocoding_provider
from app.services.users.service import (
    UserService,
    to_birth_profile_response,
    to_saved_person_response,
    to_user_response,
)

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=UserProfileResponse, summary="Current profile")
async def get_me(user: CurrentUser) -> UserProfileResponse:
    return to_user_response(user)


@router.patch(
    "/users/me", response_model=UserProfileResponse, summary="Update the profile"
)
async def update_me(
    payload: UpdateProfileRequest, user: CurrentUser, session: DbSession
) -> UserProfileResponse:
    updated = await UserService(session).update_profile(
        user=user,
        name=payload.name,
        avatar_url=payload.avatar_url,
        language=payload.language,
        timezone=payload.timezone,
        avatar_preset=payload.avatar_preset,
        bio=payload.bio,
        cover_theme=payload.cover_theme,
        privacy=payload.privacy,
        notification_prefs=payload.notification_prefs,
    )
    await session.commit()
    return to_user_response(updated)


@router.get(
    "/users/me/deletion-check",
    response_model=DeletionCheckResponse,
    summary="Can this account be deleted now?",
)
async def deletion_check(user: CurrentUser, session: DbSession) -> DeletionCheckResponse:
    from app.services.users.deletion import AccountDeletionService

    found = await AccountDeletionService(session).blockers(user)
    return DeletionCheckResponse(
        allowed=not found.blocked,
        requires_password=bool(user.password_hash),
        **found.as_dict(),
    )


_deletion_limit = Depends(UserRateLimit("5/hour", scope="account_delete"))


async def _delete_account(user, session, payload: AccountDeletionRequest) -> Message:  # noqa: ANN001
    from app.services.users.deletion import AccountDeletionService

    await AccountDeletionService(session).delete(
        user, password=payload.password, confirm_email=payload.confirm_email
    )
    await session.commit()
    return Message(message="Account deleted.")


@router.post(
    "/users/me/delete",
    response_model=Message,
    dependencies=[_deletion_limit],
    summary="Delete the account",
    description=(
        "Re-authenticated (password, or email for an account without one) and "
        "refused with `409 account_has_active_services` while an order, "
        "appointment or refund is open. Soft delete: sessions are revoked, "
        "devices disabled, records kept."
    ),
)
async def delete_account(
    payload: AccountDeletionRequest, user: SensitiveUser, session: DbSession
) -> Message:
    return await _delete_account(user, session, payload)


@router.delete(
    "/users/me",
    response_model=Message,
    dependencies=[_deletion_limit],
    summary="Delete the account (same rules as POST /users/me/delete)",
)
async def delete_me(
    user: SensitiveUser,
    session: DbSession,
    payload: AccountDeletionRequest | None = Body(default=None),
) -> Message:
    return await _delete_account(user, session, payload or AccountDeletionRequest())


# ---------------------------------------------------------------- birth data


@router.get(
    "/birth-profiles",
    response_model=list[BirthProfileResponse],
    summary="List birth profiles",
)
async def list_birth_profiles(
    user: CurrentUser, session: DbSession
) -> list[BirthProfileResponse]:
    service = UserService(session)
    profiles = await service.birth_profiles.list_for_user(user.id)
    return [to_birth_profile_response(profile) for profile in profiles]


@router.put(
    "/birth-profiles/me",
    response_model=BirthProfileResponse,
    summary="Create or replace the primary birth profile",
)
async def upsert_birth_profile(
    payload: BirthProfileRequest, user: CurrentUser, session: DbSession
) -> BirthProfileResponse:
    profile = await UserService(session).upsert_birth_profile(
        user=user,
        birth_date=payload.birth_date,
        birth_time=payload.birth_time,
        birth_place=payload.birth_place,
        latitude=payload.latitude,
        longitude=payload.longitude,
        timezone=payload.timezone,
        house_system=payload.house_system,
        label=payload.label,
    )
    await session.commit()
    return to_birth_profile_response(profile)


@router.get(
    "/birth-profiles/me",
    response_model=BirthProfileResponse,
    summary="The primary birth profile",
)
async def get_birth_profile(
    user: CurrentUser, session: DbSession
) -> BirthProfileResponse:
    from app.core.exceptions import NotFound

    profile = await UserService(session).birth_profiles.get_primary(user.id)
    if profile is None:
        raise NotFound("No birth profile yet.", code="birth_profile_missing")
    return to_birth_profile_response(profile)


# -------------------------------------------------------------- saved people


@router.get(
    "/saved-people",
    response_model=list[SavedPersonResponse],
    summary="People saved for synastry and AI context",
)
async def list_saved_people(
    user: CurrentUser, session: DbSession
) -> list[SavedPersonResponse]:
    people = await UserService(session).saved_people.list_for_user(user.id)
    return [to_saved_person_response(person) for person in people]


@router.post(
    "/saved-people",
    response_model=SavedPersonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save another person's birth data",
)
async def create_saved_person(
    payload: SavedPersonRequest, user: CurrentUser, session: DbSession
) -> SavedPersonResponse:
    person = await UserService(session).create_saved_person(
        user=user,
        name=payload.name,
        relation=payload.relation,
        birth_date=payload.birth_date,
        birth_time=payload.birth_time,
        birth_place=payload.birth_place,
        latitude=payload.latitude,
        longitude=payload.longitude,
        timezone=payload.timezone,
        house_system=payload.house_system,
        note=payload.note,
    )
    await session.commit()
    return to_saved_person_response(person)


@router.patch(
    "/saved-people/{person_id}",
    response_model=SavedPersonResponse,
    summary="Edit a saved person",
    description=(
        "Only the sent fields change; `birth_time: null` marks the time "
        "unknown. Existing reports keep the birth data they were made from."
    ),
)
async def update_saved_person(
    person_id: uuid.UUID,
    payload: SavedPersonUpdateRequest,
    user: CurrentUser,
    session: DbSession,
) -> SavedPersonResponse:
    person = await UserService(session).update_saved_person(
        user=user,
        person_id=person_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    await session.commit()
    return to_saved_person_response(person)


@router.delete(
    "/saved-people/{person_id}", response_model=Message, summary="Remove a person"
)
async def delete_saved_person(
    person_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> Message:
    await UserService(session).delete_saved_person(user=user, person_id=person_id)
    await session.commit()
    return Message(message="Removed.")


# ----------------------------------------------------------------- geocoding


@router.get(
    "/geocode",
    response_model=GeocodeResponse,
    dependencies=[Depends(RateLimit("60/hour", scope="geocode"))],
    summary="Resolve a birth place to coordinates and timezone",
)
async def geocode(
    query: str = Query(min_length=2, max_length=160),
    limit: int = Query(default=5, ge=1, le=10),
    _user: CurrentUser = None,  # noqa: B008 - dependency injection
) -> GeocodeResponse:
    provider = get_geocoding_provider()
    matches = await provider.search(query, limit=limit)
    return GeocodeResponse(
        query=query,
        results=[
            GeocodeResult(
                display_name=match.display_name,
                latitude=match.latitude,
                longitude=match.longitude,
                timezone=match.timezone,
                country_code=match.country_code,
                provider=match.provider,
                confidence=match.confidence,
            )
            for match in matches
        ],
    )
