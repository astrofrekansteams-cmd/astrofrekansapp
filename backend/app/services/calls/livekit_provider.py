"""The LiveKit implementation of `RealtimeCommunicationProvider`.

Written against `livekit-api==1.2.1`, read from the installed source rather
than recalled. The facts that shaped it:

* `AccessToken` defaults to a **six hour** TTL. Every token here sets its own.
* `VideoGrants.can_publish_data` defaults to **True**. It is set to False:
  expert chat lives in Firestore (B9) and a second, unaudited text channel
  inside the call would be a second chat source of truth.
* `can_publish_sources` supersedes `can_publish` and is enforced by the
  server. So an audio consultation gets `["microphone"]` and genuinely cannot
  publish a camera track, whatever the client does.
* Token expiry is checked on the **initial connection only**; LiveKit refreshes
  tokens for connected clients. Token lifetime is therefore join
  authorisation, not call duration.
* A second connection with the same identity **replaces** the first, which is
  disconnected with `DUPLICATE_IDENTITY`. One identity is one presence.
* Webhooks are signed: the `Authorization` header is a JWT, issued by our API
  key, carrying a base64 SHA-256 of the exact body. `WebhookReceiver` checks
  both, so verification needs the raw body, byte for byte.
* The server API converts `ws(s)://` to `http(s)://` itself.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.calls import ProviderEventType
from app.services.calls.provider import (
    CallProviderNotConfigured,
    CallProviderUnavailable,
    CallTokenFailed,
    InvalidWebhook,
    JoinToken,
    ParticipantPresence,
    ProviderWebhookEvent,
    RoomInfo,
    RoomSpec,
    TokenRequest,
)

logger = get_logger(__name__)

PROVIDER_NAME = "livekit"


# ------------------------------------------------------ shared primitives
#
# Token minting and webhook verification are pure functions of a key pair, so
# they live here as functions. The fake provider uses them too, with a test key
# pair - which means the webhook signature tests exercise LiveKit's real
# verification code rather than a stand-in.


def mint_join_token(
    request: TokenRequest, *, api_key: str, api_secret: str
) -> JoinToken:
    """A least-privilege join token for one identity in one room."""
    from livekit import api

    grants = api.VideoGrants(
        room_join=True,
        room=request.room,
        can_subscribe=True,
        can_publish=True,
        # Supersedes can_publish: only these sources may be published.
        can_publish_sources=list(request.publish_sources),
        # No data channel. Chat is B9's, in Firestore, audited.
        can_publish_data=False,
        can_update_own_metadata=False,
        # room_admin / room_create / room_list / room_record are left unset,
        # which omits them from the token entirely.
    )
    try:
        token = (
            api.AccessToken(api_key, api_secret)
            .with_identity(request.identity)
            # No name and no metadata: the other party's client learns nothing
            # about this person from the room. Display names come from our API.
            .with_grants(grants)
            .with_ttl(timedelta(seconds=request.ttl_seconds))
            .to_jwt()
        )
    except Exception as exc:  # noqa: BLE001 - reported as a stable code
        logger.warning("call_token_mint_failed", error_type=type(exc).__name__)
        raise CallTokenFailed() from exc

    # Read the expiry back from the token rather than recomputing it, so the
    # value we report is the value the server will enforce.
    claims = jwt.decode(token, options={"verify_signature": False})
    return JoinToken(
        token=token,
        identity=request.identity,
        expires_at=datetime.fromtimestamp(int(claims["exp"]), tz=UTC),
    )


def sign_webhook_body(body: bytes, *, api_key: str, api_secret: str) -> str:
    """Produce the Authorization header LiveKit sends with a webhook.

    Used by tests and the local smoke to build genuinely signed events. The
    scheme is LiveKit's: a JWT from our key whose `sha256` claim is the base64
    digest of the body.
    """
    from livekit import api

    digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
    return (
        api.AccessToken(api_key, api_secret)
        .with_sha256(digest)
        .with_ttl(timedelta(minutes=5))
        .to_jwt()
    )


def verify_webhook(
    body: bytes, authorization: str | None, *, api_key: str, api_secret: str
) -> ProviderWebhookEvent:
    """Verify a LiveKit webhook and reduce it to what the lifecycle needs.

    Anything wrong - no header, a bad signature, an expired token, a body that
    does not match the signed hash - is the same `invalid_webhook`. Saying which
    check failed would help nobody but somebody forging one.
    """
    from livekit import api
    from livekit.protocol import models

    if not authorization:
        raise InvalidWebhook()
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidWebhook() from exc

    receiver = api.WebhookReceiver(api.TokenVerifier(api_key, api_secret))
    try:
        event = receiver.receive(text, token)
    except Exception as exc:  # noqa: BLE001 - every failure is the same answer
        raise InvalidWebhook() from exc

    if not event.id or not event.event:
        raise InvalidWebhook("Webhook is missing its id or event name.")

    room_name = event.room.name if event.HasField("room") else None
    identity = None
    disconnect_reason = None
    if event.HasField("participant"):
        identity = event.participant.identity or None
        if event.participant.disconnect_reason:
            disconnect_reason = models.DisconnectReason.Name(
                event.participant.disconnect_reason
            )

    created_at = (
        datetime.fromtimestamp(int(event.created_at), tz=UTC)
        if event.created_at
        else None
    )

    return ProviderWebhookEvent(
        event_id=event.id[:80],
        event_type=ProviderEventType.parse(event.event),
        event_name=event.event[:40],
        room_name=(room_name or None),
        participant_identity=identity,
        disconnect_reason=disconnect_reason,
        created_at=created_at,
        payload_sha256=hashlib.sha256(body).hexdigest(),
    )


def _is_not_found(exc: BaseException) -> bool:
    code = str(getattr(exc, "code", "") or "").lower()
    return code == "not_found" or getattr(exc, "status", None) == 404


# ------------------------------------------------------------ the provider


class LiveKitProvider:
    name = PROVIDER_NAME

    def __init__(self) -> None:
        self._client = None  # created lazily, inside the running event loop

    # --------------------------------------------------------- configuration

    @property
    def available(self) -> bool:
        return bool(
            settings.livekit_url
            and settings.livekit_api_key
            and settings.livekit_api_secret
        )

    def _require(self) -> tuple[str, str]:
        if not self.available:
            raise CallProviderNotConfigured()
        return settings.livekit_api_key or "", settings.livekit_api_secret or ""

    @property
    def client_url(self) -> str:
        if not settings.livekit_url:
            raise CallProviderNotConfigured()
        return settings.livekit_url

    def _api(self):  # noqa: ANN202 - SDK type
        if self._client is None:
            import aiohttp
            from livekit import api

            key, secret = self._require()
            self._client = api.LiveKitAPI(
                url=settings.livekit_server_url,
                api_key=key,
                api_secret=secret,
                timeout=aiohttp.ClientTimeout(
                    total=settings.livekit_request_timeout_seconds
                ),
            )
        return self._client

    async def _room_call(self, operation: str, run, *, missing_ok: bool = False):  # noqa: ANN001,ANN202
        """Run one server API call, translating every failure.

        The provider's message never leaves this function: it can carry room
        names, identities or internal hosts. Only the operation and an error
        class are logged.
        """
        self._require()
        try:
            return await run(self._api().room)
        except Exception as exc:  # noqa: BLE001 - translated below
            if missing_ok and _is_not_found(exc):
                return None
            logger.warning(
                "livekit_request_failed",
                operation=operation,
                error_type=type(exc).__name__,
                error_code=str(getattr(exc, "code", "") or "")[:40] or None,
            )
            raise CallProviderUnavailable() from exc

    # ------------------------------------------------------------------ rooms

    async def create_room(self, spec: RoomSpec) -> RoomInfo:
        from livekit import api

        room = await self._room_call(
            "create_room",
            lambda service: service.create_room(
                api.CreateRoomRequest(
                    name=spec.name,
                    max_participants=spec.max_participants,
                    empty_timeout=spec.empty_timeout_seconds,
                    departure_timeout=spec.departure_timeout_seconds,
                    # No metadata and no egress: nothing personal, nothing
                    # recorded.
                )
            ),
        )
        return RoomInfo(name=room.name, num_participants=room.num_participants)

    async def delete_room(self, room_name: str) -> None:
        from livekit import api

        await self._room_call(
            "delete_room",
            lambda service: service.delete_room(api.DeleteRoomRequest(room=room_name)),
            missing_ok=True,
        )

    async def get_room(self, room_name: str) -> RoomInfo | None:
        from livekit import api

        response = await self._room_call(
            "get_room",
            lambda service: service.list_rooms(
                api.ListRoomsRequest(names=[room_name])
            ),
        )
        for room in response.rooms:
            if room.name == room_name:
                return RoomInfo(name=room.name, num_participants=room.num_participants)
        return None

    async def list_participants(self, room_name: str) -> list[ParticipantPresence]:
        from livekit import api
        from livekit.protocol import models

        response = await self._room_call(
            "list_participants",
            lambda service: service.list_participants(
                api.ListParticipantsRequest(room=room_name)
            ),
            missing_ok=True,
        )
        if response is None:
            return []
        return [
            ParticipantPresence(
                identity=participant.identity,
                state=models.ParticipantInfo.State.Name(participant.state).lower(),
                joined_at=(
                    datetime.fromtimestamp(int(participant.joined_at), tz=UTC)
                    if participant.joined_at
                    else None
                ),
            )
            for participant in response.participants
        ]

    async def remove_participant(self, room_name: str, identity: str) -> None:
        from livekit import api

        await self._room_call(
            "remove_participant",
            lambda service: service.remove_participant(
                api.RoomParticipantIdentity(room=room_name, identity=identity)
            ),
            missing_ok=True,
        )

    # ----------------------------------------------------------------- tokens

    def create_participant_token(self, request: TokenRequest) -> JoinToken:
        key, secret = self._require()
        return mint_join_token(request, api_key=key, api_secret=secret)

    # --------------------------------------------------------------- webhooks

    def parse_webhook(
        self, body: bytes, authorization: str | None
    ) -> ProviderWebhookEvent:
        key, secret = self._require()
        return verify_webhook(body, authorization, api_key=key, api_secret=secret)

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            finally:
                self._client = None
