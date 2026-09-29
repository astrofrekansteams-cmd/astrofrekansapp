"""User, birth-profile and saved-people use cases.

Birth data is only useful once it has coordinates *and* a timezone, so the
service geocodes a bare place string and derives the zone from the resulting
coordinates. When it cannot resolve them the profile is still stored (the user
can chart without houses) and the response says what is missing.
"""

from __future__ import annotations

import uuid
from datetime import date, time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound, ValidationFailed
from app.core.logging import get_logger
from app.db.models.birth_profile import BirthProfile, SavedPerson
from app.db.models.user import User
from app.domain.astrology import BirthData
from app.domain.enums import HouseSystem, SavedPersonRelation
from app.repositories.birth_profile_repository import (
    BirthProfileRepository,
    SavedPersonRepository,
    to_birth_data,
)
from app.schemas.user import (
    AVATAR_PRESETS,
    BirthProfileResponse,
    COVER_THEMES,
    LANGUAGES,
    NotificationPreferences,
    ProfilePrivacy,
    SavedPersonResponse,
    UserProfileResponse,
)
from app.services.geocoding.base import GeocodedPlace
from app.services.geocoding.providers import get_geocoding_provider
from app.services.timezone.service import (
    is_valid_timezone,
    timezone_for_coordinates,
    utc_offset_hours,
)

logger = get_logger(__name__)


def to_user_response(user: User) -> UserProfileResponse:
    profile = user.profile
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        name=profile.name if profile else "",
        avatar_url=profile.avatar_url if profile else None,
        avatar_preset=profile.avatar_preset if profile else None,
        bio=profile.bio if profile else None,
        cover_theme=(profile.cover_theme if profile else None) or "cosmic_night",
        privacy=ProfilePrivacy(**((profile.privacy if profile else None) or {})),
        notification_prefs=NotificationPreferences(
            **((profile.notification_prefs if profile else None) or {})
        ),
        language=profile.language if profile else "tr",
        timezone=profile.timezone if profile else "Europe/Istanbul",
        subscription_tier=user.tier,
        is_email_verified=user.is_email_verified,
        created_at=user.created_at,
        has_local_password=bool(user.password_hash),
        firebase_linked=bool(user.firebase_uid),
    )


def to_birth_profile_response(profile: BirthProfile) -> BirthProfileResponse:
    birth = to_birth_data(profile)
    return BirthProfileResponse(
        id=profile.id,
        birth_date=profile.birth_date,
        birth_time=profile.birth_time,
        birth_time_known=profile.birth_time_known,
        birth_place=profile.birth_place,
        latitude=profile.latitude,
        longitude=profile.longitude,
        timezone=profile.timezone,
        house_system=HouseSystem(profile.house_system),
        is_primary=profile.is_primary,
        label=profile.label,
        utc_offset_hours=(
            utc_offset_hours(profile.birth_date, profile.birth_time, profile.timezone)
            if profile.timezone
            else None
        ),
        can_compute_houses=birth.can_compute_houses,
        updated_at=profile.updated_at,
    )


def to_saved_person_response(person: SavedPerson) -> SavedPersonResponse:
    return SavedPersonResponse(
        id=person.id,
        name=person.name,
        relation=SavedPersonRelation(person.relation),
        birth_date=person.birth_date,
        birth_time=person.birth_time,
        birth_time_known=person.birth_time_known,
        birth_place=person.birth_place,
        latitude=person.latitude,
        longitude=person.longitude,
        timezone=person.timezone,
        house_system=HouseSystem(person.house_system),
        note=person.note,
        created_at=person.created_at,
    )


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.birth_profiles = BirthProfileRepository(session)
        self.saved_people = SavedPersonRepository(session)
        self.geocoder = get_geocoding_provider()

    # ------------------------------------------------------------- profile

    async def update_profile(
        self,
        *,
        user: User,
        name: str | None = None,
        avatar_url: str | None = None,
        language: str | None = None,
        timezone: str | None = None,
        avatar_preset: str | None = None,
        bio: str | None = None,
        cover_theme: str | None = None,
        privacy: ProfilePrivacy | None = None,
        notification_prefs: NotificationPreferences | None = None,
    ) -> User:
        profile = user.profile
        if profile is None:  # pragma: no cover - created with the account
            raise NotFound("Profile missing.")
        if avatar_preset is not None:
            if avatar_preset and avatar_preset not in AVATAR_PRESETS:
                raise ValidationFailed(
                    "Unknown avatar.", details={"avatar_preset": avatar_preset}
                )
            profile.avatar_preset = avatar_preset or None
        if bio is not None:
            profile.bio = bio.strip() or None
        if cover_theme is not None:
            if cover_theme not in COVER_THEMES:
                raise ValidationFailed(
                    "Unknown cover theme.", details={"cover_theme": cover_theme}
                )
            profile.cover_theme = cover_theme
        if privacy is not None:
            profile.privacy = privacy.model_dump()
        if notification_prefs is not None:
            profile.notification_prefs = notification_prefs.model_dump()
        if language is not None and language not in LANGUAGES:
            raise ValidationFailed("Unknown language.", details={"language": language})
        if name is not None:
            profile.name = name.strip()
        if avatar_url is not None:
            profile.avatar_url = avatar_url
        if language is not None:
            profile.language = language
        if timezone is not None:
            if not is_valid_timezone(timezone):
                raise ValidationFailed(
                    "Unknown timezone.", details={"timezone": timezone}
                )
            profile.timezone = timezone
        await self.session.flush()
        return user

    # -------------------------------------------------------- birth profile

    async def resolve_location(
        self,
        *,
        place: str | None,
        latitude: float | None,
        longitude: float | None,
        timezone: str | None,
    ) -> tuple[float | None, float | None, str | None, str | None]:
        """Fill in coordinates/timezone from whatever the caller provided.

        Returns ``(latitude, longitude, timezone, resolved_place)``.
        """
        resolved_place = place

        if latitude is None or longitude is None:
            if place:
                match: GeocodedPlace | None = await self.geocoder.resolve(place)
                if match is not None:
                    latitude = match.latitude
                    longitude = match.longitude
                    timezone = timezone or match.timezone
                    resolved_place = match.display_name
                else:
                    logger.info("geocoding_no_match", provider=self.geocoder.name)

        if timezone is None and latitude is not None and longitude is not None:
            timezone = timezone_for_coordinates(latitude, longitude)

        if timezone is not None and not is_valid_timezone(timezone):
            raise ValidationFailed("Unknown timezone.", details={"timezone": timezone})

        return latitude, longitude, timezone, resolved_place

    async def upsert_birth_profile(
        self,
        *,
        user: User,
        birth_date: date,
        birth_time: time | None,
        birth_place: str | None,
        latitude: float | None,
        longitude: float | None,
        timezone: str | None,
        house_system: HouseSystem = HouseSystem.PLACIDUS,
        label: str | None = None,
    ) -> BirthProfile:
        latitude, longitude, timezone, place = await self.resolve_location(
            place=birth_place,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
        )
        return await self.birth_profiles.upsert_primary(
            user_id=user.id,
            birth_date=birth_date,
            birth_time=birth_time,
            birth_place=place,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            house_system=house_system,
            label=label,
        )

    async def get_primary_birth_data(self, user: User) -> BirthData:
        profile = await self.birth_profiles.get_primary(user.id)
        if profile is None:
            raise NotFound(
                "No birth profile yet.", code="birth_profile_missing"
            )
        return to_birth_data(profile)

    # -------------------------------------------------------- saved people

    async def create_saved_person(
        self,
        *,
        user: User,
        name: str,
        relation: SavedPersonRelation,
        birth_date: date,
        birth_time: time | None,
        birth_place: str | None,
        latitude: float | None,
        longitude: float | None,
        timezone: str | None,
        house_system: HouseSystem = HouseSystem.PLACIDUS,
        note: str | None = None,
    ) -> SavedPerson:
        latitude, longitude, timezone, place = await self.resolve_location(
            place=birth_place,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
        )
        return await self.saved_people.create(
            user_id=user.id,
            name=name,
            relation=relation,
            birth_date=birth_date,
            birth_time=birth_time,
            birth_place=place,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            house_system=house_system,
            note=note,
        )

    async def update_saved_person(
        self, *, user: User, person_id: uuid.UUID, changes: dict
    ) -> SavedPerson:
        """Apply only what was sent. A new place without coordinates is
        geocoded again; coordinates without a timezone get one derived."""
        person = await self.saved_people.get(user.id, person_id)
        if person is None:
            raise NotFound("Saved person not found.")
        if "name" in changes and changes["name"] is not None:
            person.name = changes["name"].strip()
        if changes.get("relation") is not None:
            person.relation = changes["relation"]
        if changes.get("birth_date") is not None:
            person.birth_date = changes["birth_date"]
        if "birth_time" in changes:
            person.birth_time = changes["birth_time"]
            person.birth_time_known = changes["birth_time"] is not None
        if "note" in changes:
            person.note = (changes["note"] or "").strip() or None

        location_keys = {"birth_place", "latitude", "longitude", "timezone"}
        if location_keys & changes.keys():
            place_changed = "birth_place" in changes and changes["birth_place"] != person.birth_place
            coords_sent = changes.get("latitude") is not None and changes.get("longitude") is not None
            latitude, longitude, timezone, place = await self.resolve_location(
                place=changes.get("birth_place", person.birth_place),
                # A new place without new coordinates must not keep the old
                # place's coordinates.
                latitude=changes.get("latitude") if coords_sent or place_changed else person.latitude,
                longitude=changes.get("longitude") if coords_sent or place_changed else person.longitude,
                timezone=changes.get("timezone") if "timezone" in changes or place_changed else person.timezone,
            )
            person.birth_place = place
            person.latitude = latitude
            person.longitude = longitude
            person.timezone = timezone
        await self.session.flush()
        logger.info("saved_person_updated", user_id=str(user.id), person_id=str(person.id),
                    fields=sorted(changes.keys()))
        return person

    async def delete_saved_person(self, *, user: User, person_id: uuid.UUID) -> None:
        person = await self.saved_people.get(user.id, person_id)
        if person is None:
            raise NotFound("Saved person not found.")
        await self.saved_people.soft_delete(person)
