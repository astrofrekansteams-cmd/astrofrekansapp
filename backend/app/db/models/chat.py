"""Expert chat, attachments, devices and the notification outbox.

**Postgres is the source of truth for authorisation. Firestore is transport.**

That split decides the shape of every table here. `expert_conversations` says
who may talk to whom and until when; Firestore holds a small projection of the
membership so a client listener can work, and the messages themselves.
Duplicating the message text into Postgres would give two stores that can
disagree about what somebody said.

What is *not* in Firestore, deliberately: the order, the price, the consent
scopes, the audit metadata. A document a client can subscribe to is a document
a client can read, so it carries the minimum that realtime needs and nothing
else.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import UtcDateTime

JSONType = JSON().with_variant(JSONB(), "postgresql")


class FirebaseIdentityRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The link between a Firebase identity and a local account.

    A separate table rather than only a column on `users`, because one account
    may eventually sign in through several providers, and because the identity
    metadata (which provider, whether the email was verified, when it last
    signed in) is Firebase's business rather than the user profile's.

    `users.firebase_uid` also exists as a nullable unique column for the fast
    lookup path. This table is the record; that column is the index.

    Nothing business-related is keyed on a Firebase uid. Every foreign key in
    the product still points at the local user id, so losing or rotating a
    Firebase project does not orphan an order.
    """

    __tablename__ = "firebase_identities"
    __table_args__ = (
        UniqueConstraint("firebase_uid", name="uq_firebase_identities_uid"),
        Index("ix_firebase_identities_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    firebase_uid: Mapped[str] = mapped_column(String(128), nullable=False)

    provider_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # How the link was made. `automatic` means a verified email matched an
    # existing account, which is only allowed when an operator turns it on.
    link_method: Mapped[str] = mapped_column(String(30), nullable=False)
    last_firebase_login_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )


class ExpertConversation(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A chat thread between one user and one expert, about one order.

    A user cannot open a thread with an arbitrary expert: a conversation exists
    because an order exists, and `uq_expert_conversations_order` makes that one
    thread per order rather than a thing a retry can duplicate.

    `provisioning_status` exists because Firebase can be briefly unavailable
    while Postgres is fine. An order somebody paid for must not roll back
    because a projection write failed, so the conversation is created `pending`
    and reconciled.
    """

    __tablename__ = "expert_conversations"
    __table_args__ = (
        # One conversation per order. The database says so, because a retry
        # under a flaky connection would otherwise open a second thread.
        UniqueConstraint("order_id", name="uq_expert_conversations_order"),
        Index("ix_expert_conversations_user", "user_id", "status"),
        Index("ix_expert_conversations_expert", "expert_id", "status"),
        Index("ix_expert_conversations_provisioning", "provisioning_status"),
        Index("ix_expert_conversations_created_at", "created_at"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The expert's *account*, not their profile. Chat authorisation is about a
    # person signing in, and a profile id is not a credential.
    expert_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    provisioning_status: Mapped[str] = mapped_column(String(20), nullable=False)
    provisioning_error: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # The Firestore document id. Kept equal to this row's id in practice, but
    # stored explicitly so the projection can be renamed without a migration.
    firebase_conversation_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    projection_version: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    last_message_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Reserved for B10. Columns now so the call phase is an insert, not a
    # migration. Nothing writes them.
    call_session_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)

    attachments: Mapped[list["MediaAttachment"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class MediaAttachment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A chat attachment's metadata. The bytes live in Firebase Storage.

    The storage key is **server-chosen**. A client-supplied filename in a path
    is a directory-traversal and an overwrite problem wearing a convenience
    disguise, so the original name is kept here as metadata and the path is
    derived from ids.

    `status` matters: `pending` is an authorised intent, not a file. A message
    referencing a pending attachment would render as a broken image, so only
    `ready` may be attached to one.
    """

    __tablename__ = "media_attachments"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_media_attachments_key"),
        Index("ix_media_attachments_conversation", "conversation_id", "status"),
        Index("ix_media_attachments_pending", "status", "created_at"),
        CheckConstraint("size_bytes >= 0", name="ck_media_attachments_size"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("expert_conversations.id", ondelete="CASCADE"), nullable=False
    )
    uploader_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    storage_provider: Mapped[str] = mapped_column(
        String(20), default="firebase", nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False)

    # What the client called it. Display only; never part of the path.
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # What the client *claimed*. `verified_mime_type` is what the bucket says.
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    verified_mime_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Set once the attachment is referenced by a message, so a finalised
    # attachment cannot be silently reused in a second conversation.
    message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    conversation: Mapped[ExpertConversation] = relationship(
        back_populates="attachments"
    )


class PushDevice(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One push credential: an FCM registration token or a PushKit VoIP token.

    The token is the addressable secret, so it is unique across the table: a
    device that signs in as somebody else must move, not duplicate. Raw device
    identifiers are never stored - only a hash, and only to recognise a
    re-registration.

    `credential_type` keeps the two kinds apart. An iPhone has both, and they
    are different credentials for different transports: the FCM token carries
    ordinary notifications, the PushKit VoIP token (APNs, `apns-push-type:
    voip`) carries only incoming calls. Neither is ever used as the other.
    """

    __tablename__ = "push_devices"
    __table_args__ = (
        UniqueConstraint("token", name="uq_push_devices_token"),
        Index("ix_push_devices_user_enabled", "user_id", "enabled"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    firebase_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)

    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    token: Mapped[str] = mapped_column(String(300), nullable=False)
    # A hash, never the identifier itself.
    device_id_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(40), nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    disabled_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    # "fcm" or "apns_voip". Rows from before B12C.1 are FCM.
    credential_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="fcm", server_default="fcm"
    )
    # APNs only: "production" or "sandbox" - a token is valid in exactly one.
    apns_environment: Mapped[str | None] = mapped_column(String(12), nullable=True)


class NotificationOutbox(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A notification waiting to be sent.

    Push is not on the critical path of a business transaction. FCM being down
    must not roll back an order that succeeded, so the request writes a row and
    returns; a worker delivers it.

    `dedupe_key` is what stops one event producing two notifications when a
    request is retried or a worker restarts mid-flight.
    """

    __tablename__ = "notification_outbox"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_notification_outbox_dedupe"),
        Index("ix_notification_outbox_claim", "status", "created_at"),
        Index("ix_notification_outbox_user", "user_id"),
        Index("ix_notification_outbox_inbox", "user_id", "created_at"),
    )

    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # What the notification is about, for support and for cancellation.
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)

    # The payload that will be sent. Generic by construction - a lock screen
    # is a public surface, so no message text, no birth data, no question text.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)

    worker_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )

    # When it should be delivered. A reminder is an outbox row with a future
    # `scheduled_for`, which is why this phase needs no separate scheduler.
    scheduled_for: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True, index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # After this the notification is pointless (an incoming call that has
    # stopped ringing) and is skipped rather than sent. NULL: no expiry.
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    # The in-app notification centre reads this same row (migration 0017):
    # push delivery and the inbox are one event stream.
    read_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class NotificationDelivery(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One call notification to one device credential: one logical delivery.

    Call events are fanned out per device over different transports (APNs
    VoIP, FCM data). The unique pair is one logical delivery per device;
    `attempts` counts the physical sends it took. A retry resends only what is
    not yet delivered, and a `sending` delivery whose `lease_until` has lapsed
    (its worker died) is claimed again - at least once, with duplicates
    suppressed on the device by `call_id` + `event_version`.
    """

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("outbox_id", "device_id", name="uq_notification_deliveries_target"),
    )

    outbox_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notification_outbox.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("push_devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # apns_voip, fcm_call_data, fcm_background, fcm_alert.
    transport: Mapped[str] = mapped_column(String(20), nullable=False)
    # pending, sending, delivered, failed, skipped.
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # Physical send attempts; also the fence a worker's result is written under.
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    # While `sending`: until when the claiming worker owns it.
    lease_until: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
