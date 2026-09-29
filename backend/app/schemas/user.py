from __future__ import annotations

import uuid
from datetime import date, datetime, time

from pydantic import EmailStr, Field

from app.domain.enums import HouseSystem, SavedPersonRelation, SubscriptionTier
from app.schemas.common import APIModel


# Fixed choices: stable codes the client maps to bundled art.
AVATAR_PRESETS = (
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
)
COVER_THEMES = ("cosmic_night", "golden_dawn", "moonlit", "nebula", "aurora")
LANGUAGES = ("tr", "en", "az")


class ProfilePrivacy(APIModel):
    """What others may see where a profile is shown (e.g. to an expert)."""

    show_sun_sign: bool = True
    show_moon_sign: bool = True
    show_rising_sign: bool = True
    show_birth_date: bool = False
    show_bio: bool = True


class NotificationPreferences(APIModel):
    """Optional notifications. Calls, payments and subscription notices are
    never switched off here (see `services/notifications/preferences.py`)."""

    daily_horoscope: bool = True
    transit_alerts: bool = True
    moon_phases: bool = True
    ai_reports: bool = True
    expert_messages: bool = True
    appointment_reminders: bool = True
    promotions: bool = False


class UserProfileResponse(APIModel):
    id: uuid.UUID
    email: EmailStr
    name: str
    avatar_url: str | None = None
    avatar_preset: str | None = None
    bio: str | None = None
    cover_theme: str = "cosmic_night"
    privacy: ProfilePrivacy = Field(default_factory=ProfilePrivacy)
    notification_prefs: NotificationPreferences = Field(
        default_factory=NotificationPreferences
    )
    language: str
    timezone: str
    subscription_tier: SubscriptionTier
    is_email_verified: bool
    created_at: datetime
    has_local_password: bool = Field(
        default=False,
        description="An email-and-password sign-in held by this server exists.",
    )
    firebase_linked: bool = Field(
        default=False, description="The account has a Firebase identity."
    )


class UpdateProfileRequest(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=1024)
    avatar_preset: str | None = Field(
        default=None, description=f"One of: {', '.join(AVATAR_PRESETS)}; '' clears."
    )
    bio: str | None = Field(default=None, max_length=280)
    cover_theme: str | None = Field(
        default=None, description=f"One of: {', '.join(COVER_THEMES)}."
    )
    privacy: ProfilePrivacy | None = None
    notification_prefs: NotificationPreferences | None = None
    language: str | None = Field(default=None, max_length=8)
    timezone: str | None = Field(default=None, max_length=64)


class BirthProfileRequest(APIModel):
    birth_date: date
    birth_time: time | None = None
    birth_place: str | None = Field(default=None, max_length=255)

    # Coordinates are optional: when only a place is given the API geocodes it.
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = Field(default=None, max_length=64)
    house_system: HouseSystem = HouseSystem.PLACIDUS
    label: str | None = Field(default=None, max_length=80)


class BirthProfileResponse(APIModel):
    id: uuid.UUID
    birth_date: date
    birth_time: time | None
    birth_time_known: bool
    birth_place: str | None
    latitude: float | None
    longitude: float | None
    timezone: str | None
    house_system: HouseSystem
    is_primary: bool
    label: str | None = None
    utc_offset_hours: float | None = None
    can_compute_houses: bool = False
    updated_at: datetime


class SavedPersonRequest(BirthProfileRequest):
    name: str = Field(min_length=1, max_length=120)
    relation: SavedPersonRelation = SavedPersonRelation.OTHER
    note: str | None = Field(default=None, max_length=500)


class SavedPersonUpdateRequest(APIModel):
    """Only what is sent changes. `birth_time: null` means "unknown".

    Past reports are not touched: each report stores its own snapshot and is
    keyed by the birth data it was computed from, so an edit makes the next
    report a new one rather than rewriting an old one.
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)
    relation: SavedPersonRelation | None = None
    birth_date: date | None = None
    birth_time: time | None = None
    birth_place: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=500)


class AccountDeletionRequest(APIModel):
    password: str | None = Field(
        default=None, max_length=128, description="Required for an email-and-password account."
    )
    confirm_email: str | None = Field(
        default=None, max_length=320, description="Required when the account has no local password."
    )


class DeletionCheckResponse(APIModel):
    allowed: bool
    requires_password: bool
    open_orders: int
    live_appointments: int
    open_refunds: int
    expert_open_orders: int


class SavedPersonResponse(APIModel):
    id: uuid.UUID
    name: str
    relation: SavedPersonRelation
    birth_date: date
    birth_time: time | None
    birth_time_known: bool
    birth_place: str | None
    latitude: float | None
    longitude: float | None
    timezone: str | None
    house_system: HouseSystem
    note: str | None = None
    created_at: datetime


class GeocodeResult(APIModel):
    display_name: str
    latitude: float
    longitude: float
    timezone: str
    country_code: str | None = None
    provider: str
    confidence: float


class GeocodeResponse(APIModel):
    query: str
    results: list[GeocodeResult]
