"""Chat, presence, attachments and push: the vocabulary.

Two domains named "conversation" exist in this product and they are **not**
the same thing:

* `app/domain/ai.py` - Astro AI conversations. A user talking to a model.
  Stored in Postgres, no realtime, no second party.
* this module - expert chat. Two people, realtime transport in Firestore,
  authorisation in Postgres.

They share no tables and no code. Confusing them would put a user's private
consultation into an AI prompt, or an AI transcript into an expert's inbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AuthMode(StrEnum):
    """Which credentials the backend accepts.

    `HYBRID` exists so a Firebase migration does not sign out every existing
    account on deploy day.
    """

    LOCAL_JWT = "local_jwt"
    FIREBASE = "firebase"
    HYBRID = "hybrid"


class IdentitySource(StrEnum):
    """How the caller proved who they are, on this request."""

    LOCAL_JWT = "local_jwt"
    FIREBASE = "firebase"


class ConversationStatus(StrEnum):
    """Whether a conversation is live.

    `READ_ONLY` is its own state rather than a flag on `CLOSED`, because a
    finished consultation that a user can still scroll back through is a
    different thing from one that was shut down.
    """

    ACTIVE = "active"
    READ_ONLY = "read_only"
    CLOSED = "closed"
    SUSPENDED = "suspended"

    @property
    def allows_read(self) -> bool:
        return self is not ConversationStatus.SUSPENDED

    @property
    def allows_write(self) -> bool:
        return self is ConversationStatus.ACTIVE


class ProvisioningStatus(StrEnum):
    """Whether the Firestore projection of a conversation exists yet.

    Firebase being briefly unavailable must not roll back an order somebody
    paid for, so provisioning is allowed to lag and be retried.
    """

    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"


class ConversationRole(StrEnum):
    USER = "user"
    EXPERT = "expert"


class ChatMessageType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"


class AttachmentStatus(StrEnum):
    """An attachment only becomes a message once it is really there.

    `PENDING` is an authorised intent, not a file. A message referencing a
    pending attachment would render as a broken image.
    """

    PENDING = "pending"
    UPLOADED = "uploaded"
    READY = "ready"
    REJECTED = "rejected"
    DELETED = "deleted"

    @property
    def is_usable(self) -> bool:
        return self is AttachmentStatus.READY


class DevicePlatform(StrEnum):
    ANDROID = "android"
    IOS = "ios"
    WEB = "web"


class PushEvent(StrEnum):
    """What a notification is about.

    Deliberately coarse. The payload carries an id and a generic title; the
    app fetches the detail once the user opens it, because a lock screen is a
    public surface.
    """

    NEW_CHAT_MESSAGE = "new_chat_message"
    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    APPOINTMENT_REMINDER = "appointment_reminder"
    ORDER_STATUS_CHANGED = "order_status_changed"
    # B10. The payload names the call and its type; never the service, the
    # topic or the other person.
    INCOMING_CALL = "incoming_call"
    CALL_CANCELLED = "call_cancelled"
    CALL_MISSED = "call_missed"
    # B12C.1. Tells a callee's other devices to stop ringing: the call was
    # answered on one of them.
    CALL_ANSWERED = "call_answered"
    # B11. Never an amount, a product, a transaction id or a purchase token.
    PAYMENT_SUCCEEDED = "payment_succeeded"
    PAYMENT_FAILED = "payment_failed"
    REFUND_PROCESSED = "refund_processed"
    SUBSCRIPTION_RENEWED = "subscription_renewed"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    # An AI reading/report generated in the background is ready.
    AI_REPORT_READY = "ai_report_ready"
    # Content pushes. Optional by the user's preferences; no producer
    # schedules them yet.
    DAILY_CONTENT = "daily_content"
    PROMOTION = "promotion"


class PushCredential(StrEnum):
    """What kind of push credential a device row holds. Never interchangeable."""

    FCM = "fcm"
    APNS_VOIP = "apns_voip"


CALL_EVENTS = frozenset(
    {
        PushEvent.INCOMING_CALL,
        PushEvent.CALL_CANCELLED,
        PushEvent.CALL_MISSED,
        PushEvent.CALL_ANSWERED,
    }
)


class OutboxStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True, frozen=True)
class FirebaseIdentity:
    """A verified Firebase identity. Never a decoded token taken on trust.

    Only the fields the backend actually uses are carried across. The rest of
    the token stays in the SDK: a claim the product does not need is a claim
    that cannot be misused.
    """

    uid: str
    email: str | None = None
    email_verified: bool = False
    provider_id: str | None = None
    name: str | None = None
    picture: str | None = None
    auth_time: int | None = None

    @property
    def is_email_trustworthy(self) -> bool:
        """Whether this email may be used to match an existing account.

        An unverified email proves nothing: anyone can sign up with somebody
        else's address at a provider that does not check.
        """
        return bool(self.email) and self.email_verified


@dataclass(slots=True, frozen=True)
class ChatMessage:
    """One message, as the transport stores it."""

    message_id: str
    conversation_id: str
    sender_uid: str
    sender_role: ConversationRole
    message_type: ChatMessageType
    text: str | None
    attachment_id: str | None
    client_message_id: str | None
    created_at: str
    edited_at: str | None = None
    deleted_at: str | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


@dataclass(slots=True, frozen=True)
class PresenceState:
    uid: str
    online: bool
    last_changed: str | None = None
