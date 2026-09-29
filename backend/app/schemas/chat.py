"""Chat, attachment and device API contracts.

Two things these schemas never carry: a push token back to the client that did
not just send it, and any message content in a notification payload. Both are
deliberate - see `docs/push_notifications.md`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.chat import (
    AttachmentStatus,
    ChatMessageType,
    ConversationRole,
    ConversationStatus,
    DevicePlatform,
    ProvisioningStatus,
)
from app.schemas.common import APIModel


# --------------------------------------------------------------- identity


class FirebaseSessionResponse(APIModel):
    """What the client gets after presenting a Firebase ID token.

    No backend JWT is issued. Wrapping a Firebase token in one would mean two
    session lifetimes to keep in step and two revocation stories; the Firebase
    SDK already refreshes its own token on the client.
    """

    user_id: uuid.UUID
    firebase_uid: str
    email: str | None = None
    email_verified: bool
    is_new_account: bool = Field(
        description="True when this sign-in created the local account."
    )
    provider_id: str | None = None
    auth_mode: str


class FirebaseLinkRequest(APIModel):
    """Link a Firebase identity to the account the caller is already in.

    The safe linking path: being signed in is the proof of ownership that a
    matching email address is not.
    """

    id_token: str = Field(min_length=16, max_length=4096)


class AuthCapabilitiesResponse(APIModel):
    auth_mode: str
    accepts_local_jwt: bool
    accepts_firebase_token: bool
    firebase_configured: bool
    firebase_project_id: str | None = Field(
        default=None,
        description="The project a client should initialise against. Never a key.",
    )
    password_reset_email: bool = Field(
        default=False,
        description=(
            "Whether this server can email a password-reset link for a local "
            "(email and password) account. False until a mail provider is set."
        ),
    )


# ----------------------------------------------------------- conversations


class ConversationCreateRequest(APIModel):
    order_id: uuid.UUID = Field(
        description=(
            "Chat exists because an order does. A user cannot open a thread "
            "with an arbitrary expert."
        )
    )


class ChatPermissionResponse(APIModel):
    can_read: bool
    can_write: bool
    reason: str = Field(
        description="Why, in machine-readable form, so a client can explain it."
    )


class ConversationResponse(APIModel):
    id: uuid.UUID
    order_id: uuid.UUID
    appointment_id: uuid.UUID | None = None

    status: ConversationStatus
    provisioning_status: ProvisioningStatus = Field(
        description=(
            "Whether the realtime projection exists yet. `pending` or `failed` "
            "means listeners are not ready; the conversation itself is real."
        )
    )

    # Who the caller is in this thread, so a client need not work it out.
    my_role: ConversationRole
    counterpart_display_name: str | None = None
    expert_id: uuid.UUID
    permission: ChatPermissionResponse

    firebase_conversation_id: str | None = Field(
        default=None,
        description="The Firestore document to subscribe to.",
    )

    message_count: int
    last_message_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime


class ConversationSummary(APIModel):
    id: uuid.UUID
    order_id: uuid.UUID
    status: ConversationStatus
    my_role: ConversationRole
    counterpart_display_name: str | None = None
    message_count: int
    last_message_at: datetime | None = None
    created_at: datetime


class CloseConversationRequest(APIModel):
    reason: str | None = Field(default=None, max_length=120)


# --------------------------------------------------------------- messages


class MessageSendRequest(APIModel):
    text: str | None = Field(default=None, max_length=4000)
    attachment_id: uuid.UUID | None = Field(
        default=None,
        description="A `ready` attachment from this conversation.",
    )
    client_message_id: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "An id the client generates. Resending with the same id returns the "
            "original message instead of posting a duplicate."
        ),
    )


class MessageResponse(APIModel):
    message_id: str
    conversation_id: uuid.UUID
    sender_role: ConversationRole
    message_type: ChatMessageType
    text: str | None = None
    attachment_id: str | None = None
    client_message_id: str | None = None
    created_at: str = Field(
        description="A server timestamp. A client clock is never canonical."
    )
    deleted_at: str | None = None


class MessagePageResponse(APIModel):
    items: list[MessageResponse]
    # `created_at` of the oldest item, to pass back as `before`.
    next_cursor: str | None = None
    has_more: bool = False


# ------------------------------------------------------------ attachments


class AttachmentCreateRequest(APIModel):
    mime_type: str = Field(max_length=80)
    size_bytes: int = Field(gt=0)
    original_filename: str | None = Field(default=None, max_length=255)


class UploadGrantResponse(APIModel):
    """Where this attachment may be uploaded, and nothing wider.

    The path is server-derived. A client-supplied filename in a storage path is
    a traversal and overwrite problem, so the original name is metadata only.
    """

    storage_key: str
    bucket: str
    max_bytes: int
    allowed_mime_types: list[str]


class AttachmentResponse(APIModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    status: AttachmentStatus
    mime_type: str
    verified_mime_type: str | None = Field(
        default=None,
        description="What the stored object actually is, not what was claimed.",
    )
    size_bytes: int
    original_filename: str | None = None
    storage_key: str
    rejection_reason: str | None = None
    created_at: datetime


class AttachmentIntentResponse(APIModel):
    attachment: AttachmentResponse
    upload: UploadGrantResponse


# ---------------------------------------------------------------- devices


class DeviceRegisterRequest(APIModel):
    token: str = Field(min_length=32, max_length=300)
    platform: DevicePlatform
    device_id: str | None = Field(
        default=None,
        max_length=200,
        description="Stored only as a hash, to recognise a re-registration.",
    )
    app_version: str | None = Field(default=None, max_length=40)


class VoipDeviceRegisterRequest(APIModel):
    """An iOS PushKit VoIP token (`PKPushRegistry`, type `.voIP`).

    Not the FCM token: a different credential, used by the backend for
    exactly one thing - ringing an incoming call through CallKit.
    """

    token: str = Field(
        min_length=32,
        max_length=200,
        pattern=r"^[0-9a-fA-F]+$",
        description="The PushKit token as hex (`pushCredentials.token`).",
    )
    environment: Literal["production", "sandbox"] = Field(
        description=(
            "`production` for TestFlight/App Store builds, `sandbox` for "
            "development builds. Must match the server's APNS_ENVIRONMENT."
        ),
    )
    device_id: str | None = Field(
        default=None,
        max_length=200,
        description="Stored only as a hash, to recognise a re-registration.",
    )
    app_version: str | None = Field(default=None, max_length=40)


class VoipDeviceResponse(APIModel):
    """A registered VoIP credential. The token is never returned."""

    id: uuid.UUID
    token_fingerprint: str
    environment: str
    app_version: str | None = None
    enabled: bool
    disabled_reason: str | None = None
    last_seen_at: datetime | None = None
    created_at: datetime


class DeviceResponse(APIModel):
    """A registered device.

    The token is **not** returned. A client that just sent it already has it,
    and echoing every token back would turn a device list into a way to harvest
    them. `token_fingerprint` is enough to match a support report to a row.
    """

    id: uuid.UUID
    platform: DevicePlatform
    token_fingerprint: str
    app_version: str | None = None
    enabled: bool
    disabled_reason: str | None = None
    last_seen_at: datetime | None = None
    created_at: datetime


# --------------------------------------------------------------- presence


class PresenceResponse(APIModel):
    """One participant's presence, read server-side.

    Only ever returned for somebody the caller shares a conversation with. A
    global presence lookup would let any account watch any other.
    """

    firebase_uid: str
    online: bool
    last_changed: str | None = None


class ChatPolicyResponse(APIModel):
    """The rules, as data, so the client and the docs cannot drift."""

    writable_order_states: list[str]
    readable_order_states: list[str]
    chat_delivery_types: list[str]
    read_only_after_completion_days: int
    message_max_length: int
    attachments_per_message: int
    attachment_max_bytes: int
    attachment_allowed_mime_types: list[str]
