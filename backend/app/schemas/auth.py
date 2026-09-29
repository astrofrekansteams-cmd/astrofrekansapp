from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import EmailStr, Field, field_validator

from app.domain.enums import HouseSystem
from app.schemas.common import APIModel

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def _validate_password(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError("Password is too long.")
    if value.strip() != value:
        raise ValueError("Password cannot start or end with whitespace.")
    return value


class RegisterRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    name: str = Field(min_length=2, max_length=120)
    language: str = Field(default="tr", max_length=8)
    timezone: str = Field(default="Europe/Istanbul", max_length=64)

    # Optional birth data so the mobile sign-up flow can send everything at
    # once; the chart is only computed once the place has been geocoded.
    birth_date: date | None = None
    birth_time: time | None = None
    birth_place: str | None = Field(default=None, max_length=255)
    house_system: HouseSystem = HouseSystem.PLACIDUS

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return _validate_password(value)


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class RefreshRequest(APIModel):
    refresh_token: str = Field(min_length=10)


class LogoutRequest(APIModel):
    refresh_token: str | None = None
    everywhere: bool = False


class ForgotPasswordRequest(APIModel):
    email: EmailStr


class ResetTokenCheckRequest(APIModel):
    token: str = Field(min_length=10, max_length=2048)


class ResetTokenStatus(APIModel):
    valid: bool
    expires_at: datetime


class ResetPasswordRequest(APIModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("new_password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return _validate_password(value)


class ChangePasswordRequest(APIModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("new_password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return _validate_password(value)


class SessionResponse(APIModel):
    id: str
    kind: Literal["password", "firebase"] = Field(
        default="password",
        description=(
            "`password`: an email-and-password sign-in held by this server; "
            "`revocable`. `firebase`: a Firebase sign-in, managed by Firebase - "
            "listed for the device making the request only, never revocable here."
        ),
    )
    revocable: bool = True
    sign_in_provider: str | None = Field(
        default=None, description="For Firebase: password, google.com, apple.com."
    )
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime | None = None
    user_agent: str | None = None
    ip_hint: str | None = Field(default=None, description="Shortened, e.g. 85.105.x.x.")
    current: bool = False


class TokenResponse(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_at: datetime
    refresh_expires_at: datetime
