"""Firebase provider abstraction.

Everything above this file speaks in domain types; nothing above it imports
`firebase_admin`. That is what makes the SDK swappable, the test double
honest, and a test suite that needs no service account possible.

Five capabilities, five protocols, because they fail independently: Firestore
being slow is not a reason FCM cannot send, and a missing storage bucket is
not a reason identity verification should stop.

Errors are mapped to a small set of stable codes here, so a raw SDK exception
- which can carry project ids and request echoes - never reaches a client.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.core.exceptions import AppError
from app.domain.chat import (
    ChatMessage,
    ChatMessageType,
    ConversationRole,
    ConversationStatus,
    FirebaseIdentity,
    PresenceState,
)


# --------------------------------------------------------------- errors


class FirebaseError(AppError):
    status_code = 502
    code = "firebase_unavailable"
    message = "The realtime service is unavailable right now."


class FirebaseNotConfigured(FirebaseError):
    status_code = 503
    code = "firebase_not_configured"
    message = "The realtime service is not configured on this server."


class FirebaseTokenInvalid(FirebaseError):
    status_code = 401
    code = "invalid_firebase_token"
    message = "That sign-in token is not valid."


class FirebaseTokenExpired(FirebaseError):
    status_code = 401
    code = "firebase_token_expired"
    message = "That sign-in token has expired. Please sign in again."


class FirebaseTokenRevoked(FirebaseError):
    status_code = 401
    code = "firebase_token_revoked"
    message = "That session was signed out. Please sign in again."


class FirebaseAccountDisabled(FirebaseError):
    status_code = 403
    code = "firebase_account_disabled"
    message = "This account has been disabled."


class PushTokenUnregistered(FirebaseError):
    """The device is gone. Its token should be retired, not retried."""

    status_code = 410
    code = "push_token_unregistered"
    message = "That device is no longer registered."


# -------------------------------------------------------------- payloads


@dataclass(slots=True, frozen=True)
class ConversationProjection:
    """The minimum Firestore needs to serve realtime reads.

    Deliberately not a copy of the Postgres row. Firestore holds who may
    listen and whether the thread is live; it does not hold the order, the
    price, the consent or anything else a client has no business reading from
    a document it can subscribe to.
    """

    conversation_id: str
    member_uids: list[str]
    status: ConversationStatus
    user_uid: str | None
    expert_uid: str | None
    order_id: str
    version: int = 1


@dataclass(slots=True, frozen=True)
class StorageUploadGrant:
    """Where a client may upload, and nothing wider than that."""

    storage_key: str
    bucket: str
    max_bytes: int
    allowed_mime_types: list[str]
    expires_at: str | None = None
    upload_url: str | None = None


@dataclass(slots=True, frozen=True)
class StorageObjectInfo:
    exists: bool
    size_bytes: int | None = None
    content_type: str | None = None
    sha256: str | None = None


@dataclass(slots=True, frozen=True)
class PushMessage:
    """A notification, already stripped of anything private.

    `title` and `body` are generic by construction - a lock screen is a public
    surface, so the detail lives behind the tap, not in the payload.
    """

    title: str
    body: str
    data: dict[str, str]
    collapse_key: str | None = None
    # Seconds the message stays deliverable. None: the provider default (FCM:
    # four weeks). Set for time-bound notices so they are not shown late.
    ttl_seconds: int | None = None


@dataclass(slots=True, frozen=True)
class DataPushMessage:
    """A data-only message: no `notification` block, nothing the OS shows.

    For call lifecycle events. The app's own receiver (Android
    `FirebaseMessagingService.onMessageReceived`) decides what to present, so a
    ringing screen can be shown - and dismissed - by the app, from the payload
    alone, without a network round trip.
    """

    data: dict[str, str]
    # "high" wakes the device and is reserved by FCM for messages that lead
    # to something the user sees; "normal" may wait for Doze.
    android_priority: str = "high"
    ttl_seconds: int | None = None
    collapse_key: str | None = None
    # For an iOS FCM token: send as an APNs background update
    # (`content-available`, `apns-push-type: background`, priority 5). Best
    # effort by Apple's design - never used to ring.
    apns_background: bool = False


@dataclass(slots=True, frozen=True)
class PushResult:
    success_count: int
    failure_count: int
    # Tokens the provider says are dead. The caller retires them.
    invalid_tokens: list[str]
    retryable: bool = False
    # Tokens that failed for a reason worth retrying (per-device ledgers).
    retry_tokens: list[str] = field(default_factory=list)


# ------------------------------------------------------------- protocols


@runtime_checkable
class FirebaseIdentityProvider(Protocol):
    name: str

    @property
    def available(self) -> bool:
        """False without credentials; callers answer `firebase_not_configured`."""

    async def verify_id_token(
        self, token: str, *, check_revoked: bool = False
    ) -> FirebaseIdentity:
        """Verify signature, issuer, audience and expiry. Never trust a payload."""

    async def revoke_refresh_tokens(self, uid: str) -> None:
        """Sign a user out of every device."""

    async def delete_user(self, uid: str) -> None:
        """Remove the Firebase identity. The local account is separate."""


@runtime_checkable
class FirestoreChatProvider(Protocol):
    name: str

    @property
    def available(self) -> bool: ...

    async def upsert_conversation(self, projection: ConversationProjection) -> None:
        """Write the membership projection. Idempotent."""

    async def set_conversation_status(
        self, conversation_id: str, status: ConversationStatus
    ) -> None: ...

    async def append_message(
        self,
        conversation_id: str,
        *,
        sender_uid: str,
        sender_role: ConversationRole,
        message_type: ChatMessageType,
        text: str | None = None,
        attachment_id: str | None = None,
        client_message_id: str | None = None,
    ) -> ChatMessage:
        """Append a message with a **server** timestamp."""

    async def find_by_client_message_id(
        self, conversation_id: str, client_message_id: str
    ) -> ChatMessage | None:
        """For idempotency: has this client message already landed?"""

    async def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 50,
        before: str | None = None,
    ) -> list[ChatMessage]:
        """A page of history, newest first. Never the whole thread."""

    async def soft_delete_message(
        self, conversation_id: str, message_id: str, *, sender_uid: str
    ) -> ChatMessage:
        """Mark a message deleted. Only its own sender may."""


@runtime_checkable
class FirebasePresenceProvider(Protocol):
    name: str

    @property
    def available(self) -> bool: ...

    async def publish_membership(
        self, conversation_id: str, member_uids: list[str]
    ) -> None:
        """Mirror membership so the RTDB rules can check it."""

    async def revoke_membership(self, conversation_id: str) -> None: ...

    async def read_visibility(self) -> dict[str, dict[str, dict[str, Any]]]:
        """The whole `presenceVisibility` tree. Maintenance only."""

    async def add_visibility_grant(
        self, target_uid: str, reader_uid: str, conversation_id: str
    ) -> None:
        """Add one `{target}/{reader}/{conversation}` key, transactionally."""

    async def remove_visibility_grant(
        self, target_uid: str, reader_uid: str, conversation_id: str
    ) -> None:
        """Remove one key; an emptied reader node goes with it."""

    async def read_presence(self, uid: str) -> PresenceState:
        """Server-side read. Clients read through rules, not through this."""

    async def clear_typing(self, conversation_id: str) -> None: ...


@runtime_checkable
class FirebaseStorageProvider(Protocol):
    name: str

    @property
    def available(self) -> bool: ...

    def build_upload_grant(
        self,
        *,
        conversation_id: str,
        attachment_id: str,
        mime_type: str,
        max_bytes: int,
    ) -> StorageUploadGrant:
        """The one path this attachment may occupy. Server-chosen, always."""

    async def inspect(self, storage_key: str) -> StorageObjectInfo:
        """What is actually in the bucket - not what the client claimed."""

    async def delete(self, storage_key: str) -> None: ...


@runtime_checkable
class FirebasePushProvider(Protocol):
    name: str

    @property
    def available(self) -> bool: ...

    async def send_to_device(self, token: str, message: PushMessage) -> PushResult: ...

    async def send_multicast(
        self, tokens: list[str], message: PushMessage
    ) -> PushResult:
        """Fan out to a user's devices.

        Named for what it does. The SDK's own `send_multicast` was removed in
        firebase-admin 7.x; the implementation uses
        `send_each_for_multicast`.
        """

    async def send_data(
        self, tokens: list[str], message: DataPushMessage
    ) -> PushResult:
        """A data-only fan-out (no `notification` block). Call events only."""


@dataclass(slots=True, frozen=True)
class FirebaseProviders:
    """The five capabilities, wired together."""

    identity: FirebaseIdentityProvider
    chat: FirestoreChatProvider
    presence: FirebasePresenceProvider
    storage: FirebaseStorageProvider
    push: FirebasePushProvider

    @property
    def available(self) -> bool:
        return self.identity.available

    def require(self) -> None:
        if not self.available:
            raise FirebaseNotConfigured()


def safe_metadata(payload: dict[str, Any]) -> dict[str, str]:
    """Coerce a push payload to strings, dropping anything empty.

    FCM data values must be strings. Doing the conversion here means no caller
    accidentally ships a nested object - which would be silently stringified
    into something a client cannot parse.
    """
    return {
        key: str(value)
        for key, value in payload.items()
        if value is not None and value != ""
    }
