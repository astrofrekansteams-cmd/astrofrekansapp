"""Push device registration.

An FCM token is an addressable secret: whoever holds it can be sent
notifications. So it is unique across the table - a device that signs in as
somebody else *moves* rather than duplicating - and it is never logged.

Raw device identifiers are not stored either. A hash is enough to recognise a
re-registration from the same handset, and a hash cannot be correlated back to
a device by anybody reading the table.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, NotFound
from app.core.logging import get_logger
from app.db.models.chat import PushDevice
from app.db.models.user import User
from app.domain.chat import DevicePlatform, PushCredential

logger = get_logger(__name__)

MIN_TOKEN_LENGTH = 32


class InvalidPushToken(AppError):
    status_code = 422
    code = "invalid_push_token"
    message = "That is not a usable push token."


class VoipEnvironmentMismatch(AppError):
    status_code = 422
    code = "voip_environment_mismatch"
    message = "This server does not deliver to that APNs environment."


# An APNs device token is hex. Its length is Apple's to change, so only a
# sane range is checked.
_APNS_TOKEN = re.compile(r"^[0-9a-fA-F]{32,200}$")


def hash_device_id(device_id: str | None) -> str | None:
    """A hash, never the identifier.

    Storing the raw id would let anyone with table access correlate a row to a
    physical handset, which is not something notification delivery needs.
    """
    if not device_id:
        return None
    return hashlib.sha256(device_id.strip().encode("utf-8")).hexdigest()


def mask_token(token: str) -> str:
    """A fingerprint for support, not the token.

    Enough to match a user's report against a row; useless to anybody who
    intercepts a log line.

    Logged under `token_fingerprint`, never `token`: the redaction processor
    replaces anything keyed `token` with `[redacted]`, which would throw away
    the one value here that is safe to keep.
    """
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{digest[:12]}…"


class DeviceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register(
        self,
        user: User,
        *,
        token: str,
        platform: DevicePlatform,
        device_id: str | None = None,
        app_version: str | None = None,
    ) -> PushDevice:
        """Register or re-register a device.

        Idempotent on the token, and it **moves** an existing token to the
        current account rather than refusing: a shared handset is a real thing,
        and leaving the token on the previous account would send that person's
        notifications to whoever is holding the phone now.
        """
        cleaned = (token or "").strip()
        if len(cleaned) < MIN_TOKEN_LENGTH:
            raise InvalidPushToken()

        existing = await self.session.scalar(
            select(PushDevice).where(PushDevice.token == cleaned)
        )
        now = datetime.now(UTC)

        if existing is not None and existing.credential_type != PushCredential.FCM.value:
            # A PushKit VoIP token is never an FCM token, and never becomes one.
            raise InvalidPushToken()

        if existing is not None:
            moved = existing.user_id != user.id
            existing.user_id = user.id
            existing.firebase_uid = user.firebase_uid
            existing.platform = platform.value
            existing.device_id_hash = hash_device_id(device_id)
            existing.app_version = (app_version or "").strip()[:40] or None
            existing.enabled = True
            existing.disabled_reason = None
            existing.last_seen_at = now
            await self.session.flush()

            logger.info(
                "push_device_registered",
                device_id=str(existing.id),
                user_id=str(user.id),
                platform=platform.value,
                reassigned=moved,
                token_fingerprint=mask_token(cleaned),
            )
            return existing

        device = PushDevice(
            user_id=user.id,
            firebase_uid=user.firebase_uid,
            platform=platform.value,
            token=cleaned,
            device_id_hash=hash_device_id(device_id),
            app_version=(app_version or "").strip()[:40] or None,
            enabled=True,
            last_seen_at=now,
        )
        self.session.add(device)
        await self.session.flush()

        logger.info(
            "push_device_registered",
            device_id=str(device.id),
            user_id=str(user.id),
            platform=platform.value,
            reassigned=False,
            token_fingerprint=mask_token(cleaned),
        )
        return device

    async def register_voip(
        self,
        user: User,
        *,
        token: str,
        environment: str,
        device_id: str | None = None,
        app_version: str | None = None,
    ) -> PushDevice:
        """Register an iOS PushKit VoIP token.

        A separate credential from the device's FCM token, used for exactly one
        thing: ringing an incoming call. Same ownership rules as FCM tokens -
        idempotent on the token, and a token registered from another account
        moves rather than duplicating.
        """
        cleaned = (token or "").strip()
        if not _APNS_TOKEN.fullmatch(cleaned):
            raise InvalidPushToken()
        cleaned = cleaned.lower()
        if environment != settings.apns_environment:
            raise VoipEnvironmentMismatch(details={"expected": settings.apns_environment})

        existing = await self.session.scalar(
            select(PushDevice).where(PushDevice.token == cleaned)
        )
        if existing is not None and existing.credential_type != PushCredential.APNS_VOIP.value:
            raise InvalidPushToken()

        now = datetime.now(UTC)
        device = existing or PushDevice(token=cleaned, user_id=user.id)
        moved = existing is not None and existing.user_id != user.id
        device.user_id = user.id
        device.firebase_uid = user.firebase_uid
        device.platform = DevicePlatform.IOS.value
        device.credential_type = PushCredential.APNS_VOIP.value
        device.apns_environment = environment
        device.device_id_hash = hash_device_id(device_id)
        device.app_version = (app_version or "").strip()[:40] or None
        device.enabled = True
        device.disabled_reason = None
        device.last_seen_at = now
        if existing is None:
            self.session.add(device)
        await self.session.flush()

        logger.info(
            "voip_device_registered",
            device_id=str(device.id),
            user_id=str(user.id),
            environment=environment,
            reassigned=moved,
            token_fingerprint=mask_token(cleaned),
        )
        return device

    async def list_for_user(
        self,
        user: User,
        *,
        enabled_only: bool = False,
        credential: PushCredential = PushCredential.FCM,
    ) -> list[PushDevice]:
        statement = select(PushDevice).where(
            PushDevice.user_id == user.id,
            PushDevice.credential_type == credential.value,
        )
        if enabled_only:
            statement = statement.where(PushDevice.enabled.is_(True))
        return list(
            await self.session.scalars(
                statement.order_by(PushDevice.created_at.desc())
            )
        )

    async def get_own(
        self,
        user: User,
        device_id: uuid.UUID,
        *,
        credential: PushCredential = PushCredential.FCM,
    ) -> PushDevice:
        device = await self.session.scalar(
            select(PushDevice).where(
                PushDevice.id == device_id,
                PushDevice.user_id == user.id,
                PushDevice.credential_type == credential.value,
            )
        )
        if device is None:
            # Another user's device is simply not found.
            raise NotFound("Device not found.")
        return device

    async def remove(
        self,
        user: User,
        device_id: uuid.UUID,
        *,
        credential: PushCredential = PushCredential.FCM,
    ) -> None:
        """Delete a token the user no longer wants notified.

        A real delete, not a flag: a token nobody should use is a token nobody
        should be able to read out of the database either.
        """
        device = await self.get_own(user, device_id, credential=credential)
        await self.session.delete(device)
        await self.session.flush()
        logger.info(
            "push_device_removed", device_id=str(device_id), user_id=str(user.id)
        )

    async def disable_token(self, token: str, *, reason: str) -> bool:
        """Retire a token the provider says is dead.

        Called from the worker when FCM reports `UnregisteredError`. Retrying
        such a token never succeeds, so it is disabled rather than left to fail
        on every future notification.
        """
        device = await self.session.scalar(
            select(PushDevice).where(
                PushDevice.token == token,
                PushDevice.credential_type == PushCredential.FCM.value,
            )
        )
        if device is None:
            return False

        device.enabled = False
        device.disabled_reason = reason[:60]
        await self.session.flush()
        logger.info(
            "push_device_disabled",
            device_id=str(device.id),
            reason=reason,
            token_fingerprint=mask_token(token),
        )
        return True

    async def disable_for_logout(self, user: User, token: str | None) -> int:
        """On sign-out, stop notifying the device that signed out.

        Only that device: a user with a phone and a tablet who signs out of one
        still wants the other to work.
        """
        if not token:
            return 0
        device = await self.session.scalar(
            select(PushDevice).where(
                PushDevice.token == token.strip(), PushDevice.user_id == user.id
            )
        )
        if device is None:
            return 0
        device.enabled = False
        device.disabled_reason = "signed_out"
        await self.session.flush()
        return 1

    async def disable_device(self, device: PushDevice, *, reason: str) -> None:
        """Retire a credential the provider says is permanently dead (APNs
        `Unregistered` / `BadDeviceToken` / `DeviceTokenNotForTopic`)."""
        device.enabled = False
        device.disabled_reason = reason[:60]
        await self.session.flush()
        logger.info(
            "push_device_disabled",
            device_id=str(device.id),
            reason=reason,
            token_fingerprint=mask_token(device.token),
        )

    async def active_tokens(self, user_id: uuid.UUID) -> list[str]:
        """FCM tokens for ordinary notifications. Never a VoIP token."""
        rows = await self.session.scalars(
            select(PushDevice.token).where(
                PushDevice.user_id == user_id,
                PushDevice.enabled.is_(True),
                PushDevice.credential_type == PushCredential.FCM.value,
            )
        )
        return list(rows)

    async def enabled_devices(self, user_id: uuid.UUID) -> list[PushDevice]:
        """Every enabled credential, both kinds - for call routing."""
        return list(
            await self.session.scalars(
                select(PushDevice)
                .where(PushDevice.user_id == user_id, PushDevice.enabled.is_(True))
                .order_by(PushDevice.created_at)
            )
        )
