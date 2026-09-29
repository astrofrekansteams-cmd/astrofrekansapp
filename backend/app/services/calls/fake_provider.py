"""An in-memory LiveKit, for tests.

Two parts of it are deliberately *not* fake: join tokens and webhook signatures
use LiveKit's own SDK with a throwaway key pair. So a test that inspects a
token's grants is inspecting a real LiveKit JWT, and a test that forges a
webhook is attacking LiveKit's real verification code. Only the network - rooms
and who is in them - is simulated.

The key pair below is a test fixture that authorises nothing anywhere. It is
not a LiveKit credential and could not be one: no LiveKit server is configured
with it.

Refused in production by `assert_production_ready`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.calls.livekit_provider import (
    mint_join_token,
    sign_webhook_body,
    verify_webhook,
)
from app.services.calls.provider import (
    CallProviderNotConfigured,
    CallProviderUnavailable,
    CallTokenFailed,
    JoinToken,
    ParticipantPresence,
    ProviderWebhookEvent,
    RoomInfo,
    RoomSpec,
    TokenRequest,
)

PROVIDER_NAME = "fake"

FAKE_API_KEY = "fake-test-key"
FAKE_API_SECRET = "fake-test-secret-used-only-by-the-test-suite-0000"
FAKE_URL = "wss://livekit.invalid"


@dataclass
class FakeRoom:
    spec: RoomSpec
    # identity -> state
    participants: dict[str, str] = field(default_factory=dict)


class FakeRealtimeCommunicationProvider:
    name = PROVIDER_NAME

    def __init__(self) -> None:
        self.rooms: dict[str, FakeRoom] = {}
        self.deleted_rooms: list[str] = []
        self.removed: list[tuple[str, str]] = []
        self.token_requests: list[TokenRequest] = []

        # Failure knobs.
        self.unavailable = False
        self.fail_create_room = False
        self.fail_token = False
        self.fail_list = False
        self.not_configured = False
        self.closed = False

    # ------------------------------------------------------------ test helpers

    def join(self, room_name: str, identity: str) -> None:
        """Simulate a participant connecting."""
        self.rooms.setdefault(
            room_name, FakeRoom(spec=RoomSpec(room_name, 2, 300, 45))
        ).participants[identity] = "active"

    def leave(self, room_name: str, identity: str) -> None:
        room = self.rooms.get(room_name)
        if room:
            room.participants.pop(identity, None)

    def signed_webhook(self, body: bytes) -> str:
        """The Authorization header LiveKit would send with this body."""
        return sign_webhook_body(
            body, api_key=FAKE_API_KEY, api_secret=FAKE_API_SECRET
        )

    # ---------------------------------------------------------------- protocol

    @property
    def available(self) -> bool:
        return not self.not_configured

    @property
    def client_url(self) -> str:
        if self.not_configured:
            raise CallProviderNotConfigured()
        return FAKE_URL

    def _check(self) -> None:
        if self.not_configured:
            raise CallProviderNotConfigured()
        if self.unavailable:
            raise CallProviderUnavailable()

    async def create_room(self, spec: RoomSpec) -> RoomInfo:
        self._check()
        if self.fail_create_room:
            raise CallProviderUnavailable()
        room = self.rooms.setdefault(spec.name, FakeRoom(spec=spec))
        return RoomInfo(name=spec.name, num_participants=len(room.participants))

    async def delete_room(self, room_name: str) -> None:
        self._check()
        self.rooms.pop(room_name, None)
        self.deleted_rooms.append(room_name)

    async def get_room(self, room_name: str) -> RoomInfo | None:
        self._check()
        room = self.rooms.get(room_name)
        if room is None:
            return None
        return RoomInfo(name=room_name, num_participants=len(room.participants))

    async def list_participants(self, room_name: str) -> list[ParticipantPresence]:
        self._check()
        if self.fail_list:
            raise CallProviderUnavailable()
        room = self.rooms.get(room_name)
        if room is None:
            return []
        return [
            ParticipantPresence(identity=identity, state=state)
            for identity, state in room.participants.items()
        ]

    async def remove_participant(self, room_name: str, identity: str) -> None:
        self._check()
        self.removed.append((room_name, identity))
        room = self.rooms.get(room_name)
        if room:
            room.participants.pop(identity, None)

    def create_participant_token(self, request: TokenRequest) -> JoinToken:
        if self.not_configured:
            raise CallProviderNotConfigured()
        if self.fail_token:
            raise CallTokenFailed()
        self.token_requests.append(request)
        return mint_join_token(
            request, api_key=FAKE_API_KEY, api_secret=FAKE_API_SECRET
        )

    def parse_webhook(
        self, body: bytes, authorization: str | None
    ) -> ProviderWebhookEvent:
        if self.not_configured:
            raise CallProviderNotConfigured()
        return verify_webhook(
            body,
            authorization,
            api_key=FAKE_API_KEY,
            api_secret=FAKE_API_SECRET,
        )

    async def close(self) -> None:
        self.closed = True
