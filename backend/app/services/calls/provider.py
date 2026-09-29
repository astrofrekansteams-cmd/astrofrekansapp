"""The seam between Astrofrekans and whoever carries the media.

Nothing outside `app/services/calls/` imports a LiveKit type. Routes and the
lifecycle service speak in the dataclasses below, so swapping LiveKit for
another SFU is a new implementation of `RealtimeCommunicationProvider`, not a
rewrite of the call domain.

What a provider is trusted with, and what it is not:

* **Trusted:** moving audio and video, reporting who is in a room, signing the
  tokens we ask it to sign.
* **Not trusted:** deciding who may join. That decision is made by the call
  policy (`app/services/calls/policy.py`) before a token is ever requested;
  the provider only enforces the grants it is handed.

Provider errors never cross this boundary raw. A LiveKit error message can name
a room, an identity or an internal host, and none of that belongs in an API
response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.core.exceptions import AppError
from app.domain.calls import ProviderEventType

# ------------------------------------------------------------------ errors


class CallProviderNotConfigured(AppError):
    status_code = 503
    code = "call_provider_not_configured"
    message = "Voice and video calls are not configured on this server."


class CallProviderUnavailable(AppError):
    status_code = 503
    code = "call_provider_unavailable"
    message = "The call service is temporarily unavailable. Please try again."


class CallTokenFailed(AppError):
    status_code = 503
    code = "call_token_failed"
    message = "A join token could not be issued. Please try again."


class InvalidWebhook(AppError):
    status_code = 401
    code = "invalid_webhook"
    message = "Webhook signature could not be verified."


# ------------------------------------------------------------ data shapes


@dataclass(slots=True, frozen=True)
class RoomSpec:
    """What we ask the provider for. Carries no personal data by design."""

    name: str
    max_participants: int
    empty_timeout_seconds: int
    departure_timeout_seconds: int


@dataclass(slots=True, frozen=True)
class RoomInfo:
    name: str
    num_participants: int = 0


@dataclass(slots=True, frozen=True)
class ParticipantPresence:
    """Somebody the provider says is in a room, by opaque identity only."""

    identity: str
    # joining / joined / active / disconnected, lower-cased from the provider.
    state: str
    joined_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class TokenRequest:
    room: str
    identity: str
    # Exactly the track sources this participant may publish. See
    # `PUBLISH_SOURCES` in `app.domain.calls`.
    publish_sources: tuple[str, ...]
    ttl_seconds: int


@dataclass(slots=True, frozen=True)
class JoinToken:
    token: str = field(repr=False)  # never in a repr, so never in a traceback
    identity: str = ""
    expires_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class ProviderWebhookEvent:
    """A verified webhook, reduced to what the lifecycle needs.

    The provider's payload carries more - participant names, metadata, track
    details - and all of it is dropped here, before anything is stored or
    logged.
    """

    event_id: str
    event_type: ProviderEventType
    event_name: str
    room_name: str | None
    participant_identity: str | None
    disconnect_reason: str | None
    created_at: datetime | None
    payload_sha256: str


# ---------------------------------------------------------------- protocol


@runtime_checkable
class RealtimeCommunicationProvider(Protocol):
    name: str

    @property
    def available(self) -> bool: ...

    @property
    def client_url(self) -> str:
        """The URL a client connects to. Public configuration, never a secret."""
        ...

    async def create_room(self, spec: RoomSpec) -> RoomInfo: ...

    async def delete_room(self, room_name: str) -> None:
        """Idempotent: deleting a room that does not exist is not an error."""
        ...

    async def get_room(self, room_name: str) -> RoomInfo | None: ...

    async def list_participants(self, room_name: str) -> list[ParticipantPresence]: ...

    async def remove_participant(self, room_name: str, identity: str) -> None: ...

    def create_participant_token(self, request: TokenRequest) -> JoinToken: ...

    def parse_webhook(
        self, body: bytes, authorization: str | None
    ) -> ProviderWebhookEvent: ...

    async def close(self) -> None: ...
