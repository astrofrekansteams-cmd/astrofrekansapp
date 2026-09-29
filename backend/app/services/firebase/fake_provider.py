"""In-memory Firebase test doubles.

The suite must never need a service account. A test that requires real
credentials is a test that does not run in CI, on a new laptop, or for a
contributor - and a phase whose security properties are only checked by hand
is a phase whose security properties are not checked.

So these implement the same protocols over dictionaries, and can be told to
misbehave on purpose: expire a token, revoke it, disable an account, fail a
push, report a token as dead, return a bucket object that does not match what
was promised. Those are the cases worth testing.

Refused in production by `assert_production_ready`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.config import settings
from app.domain.chat import (
    ChatMessage,
    ChatMessageType,
    ConversationRole,
    ConversationStatus,
    FirebaseIdentity,
    PresenceState,
)
from app.services.firebase.provider import (
    ConversationProjection,
    FirebaseAccountDisabled,
    FirebaseNotConfigured,
    FirebaseTokenExpired,
    FirebaseTokenInvalid,
    FirebaseTokenRevoked,
    DataPushMessage,
    PushMessage,
    PushResult,
    StorageObjectInfo,
    StorageUploadGrant,
)

PROVIDER_NAME = "fake"


def _now() -> str:
    return datetime.now(UTC).isoformat()


class FakeFirebaseIdentityProvider:
    """Tokens are whatever a test says they are."""

    name = PROVIDER_NAME

    def __init__(self) -> None:
        self.identities: dict[str, FirebaseIdentity] = {}
        self.expired: set[str] = set()
        self.revoked: set[str] = set()
        self.disabled: set[str] = set()
        self.revoked_uids: list[str] = []
        self.deleted_uids: list[str] = []
        self.unavailable = False

    @property
    def available(self) -> bool:
        return not self.unavailable

    # --- test helpers ---------------------------------------------------

    def register(
        self,
        token: str,
        *,
        uid: str | None = None,
        email: str | None = None,
        email_verified: bool = True,
        provider_id: str = "password",
    ) -> FirebaseIdentity:
        identity = FirebaseIdentity(
            uid=uid or f"uid-{uuid.uuid4().hex[:12]}",
            email=email,
            email_verified=email_verified,
            provider_id=provider_id,
            auth_time=int(datetime.now(UTC).timestamp()),
        )
        self.identities[token] = identity
        return identity

    # --- protocol -------------------------------------------------------

    async def verify_id_token(
        self, token: str, *, check_revoked: bool = False
    ) -> FirebaseIdentity:
        if not self.available:
            raise FirebaseNotConfigured()
        # Same switch as the real provider: the setting turns the check on
        # for every request.
        check_revoked = check_revoked or settings.firebase_check_revoked
        if token in self.expired:
            raise FirebaseTokenExpired()
        if token in self.revoked:
            # Only surfaced when the caller asked, mirroring the real SDK.
            if check_revoked:
                raise FirebaseTokenRevoked()
        if token in self.disabled:
            if check_revoked:
                raise FirebaseAccountDisabled()
        identity = self.identities.get(token)
        if identity is None:
            raise FirebaseTokenInvalid()
        return identity

    async def revoke_refresh_tokens(self, uid: str) -> None:
        if not self.available:
            raise FirebaseNotConfigured()
        self.revoked_uids.append(uid)

    async def delete_user(self, uid: str) -> None:
        if not self.available:
            raise FirebaseNotConfigured()
        self.deleted_uids.append(uid)


class FakeFirestoreChatProvider:
    name = PROVIDER_NAME

    def __init__(self) -> None:
        self.conversations: dict[str, ConversationProjection] = {}
        self.messages: dict[str, list[ChatMessage]] = {}
        self.unavailable = False
        self.fail_next_append = False

    @property
    def available(self) -> bool:
        return not self.unavailable

    async def upsert_conversation(self, projection: ConversationProjection) -> None:
        if not self.available:
            raise FirebaseNotConfigured()
        self.conversations[projection.conversation_id] = projection
        self.messages.setdefault(projection.conversation_id, [])

    async def set_conversation_status(
        self, conversation_id: str, status: ConversationStatus
    ) -> None:
        if not self.available:
            raise FirebaseNotConfigured()
        existing = self.conversations.get(conversation_id)
        if existing is not None:
            self.conversations[conversation_id] = ConversationProjection(
                conversation_id=existing.conversation_id,
                member_uids=existing.member_uids,
                status=status,
                user_uid=existing.user_uid,
                expert_uid=existing.expert_uid,
                order_id=existing.order_id,
                version=existing.version + 1,
            )

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
        if not self.available:
            raise FirebaseNotConfigured()
        if self.fail_next_append:
            self.fail_next_append = False
            raise FirebaseNotConfigured("Firestore is unavailable.")

        message = ChatMessage(
            message_id=uuid.uuid4().hex,
            conversation_id=conversation_id,
            sender_uid=sender_uid,
            sender_role=sender_role,
            message_type=message_type,
            text=text,
            attachment_id=attachment_id,
            client_message_id=client_message_id,
            created_at=_now(),
        )
        self.messages.setdefault(conversation_id, []).append(message)
        return message

    async def find_by_client_message_id(
        self, conversation_id: str, client_message_id: str
    ) -> ChatMessage | None:
        if not self.available:
            raise FirebaseNotConfigured()
        for message in self.messages.get(conversation_id, []):
            if message.client_message_id == client_message_id:
                return message
        return None

    async def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 50,
        before: str | None = None,
    ) -> list[ChatMessage]:
        if not self.available:
            raise FirebaseNotConfigured()
        rows = sorted(
            self.messages.get(conversation_id, []),
            key=lambda item: item.created_at,
            reverse=True,
        )
        if before:
            rows = [row for row in rows if row.created_at < before]
        return rows[:limit]

    async def soft_delete_message(
        self, conversation_id: str, message_id: str, *, sender_uid: str
    ) -> ChatMessage:
        if not self.available:
            raise FirebaseNotConfigured()
        rows = self.messages.get(conversation_id, [])
        for index, message in enumerate(rows):
            if message.message_id != message_id:
                continue
            if message.sender_uid != sender_uid:
                raise FirebaseTokenInvalid("Only the sender may delete a message.")
            deleted = ChatMessage(
                message_id=message.message_id,
                conversation_id=message.conversation_id,
                sender_uid=message.sender_uid,
                sender_role=message.sender_role,
                message_type=message.message_type,
                text=None,
                attachment_id=None,
                client_message_id=message.client_message_id,
                created_at=message.created_at,
                deleted_at=_now(),
            )
            rows[index] = deleted
            return deleted
        raise FirebaseTokenInvalid("That message does not exist.")


class FakePresenceProvider:
    name = PROVIDER_NAME

    def __init__(self) -> None:
        self.membership: dict[str, list[str]] = {}
        # target uid -> reader uid -> shared conversation ids. Mirrors
        # `presenceVisibility` in database.rules.json, which
        # is what lets a partner's listener read `presence/{uid}` at all.
        self.visibility: dict[str, dict[str, set[str]]] = {}
        # Calls to the maintenance primitives, so a test can prove a dry run
        # or a no-op run wrote nothing.
        self.visibility_writes = 0
        self.presence: dict[str, bool] = {}
        self.typing_cleared: list[str] = []
        self.unavailable = False

    def may_see(self, reader_uid: str, subject_uid: str) -> bool:
        """Whether the RTDB rules would let `reader_uid` read that presence."""
        if reader_uid == subject_uid:
            return True
        return bool(self.visibility.get(subject_uid, {}).get(reader_uid))

    @property
    def available(self) -> bool:
        return not self.unavailable

    async def publish_membership(
        self, conversation_id: str, member_uids: list[str]
    ) -> None:
        if not self.available:
            raise FirebaseNotConfigured()
        self.membership[conversation_id] = list(member_uids)
        for uid in member_uids:
            for reader_uid in member_uids:
                if reader_uid != uid:
                    self.visibility.setdefault(uid, {}).setdefault(
                        reader_uid, set()
                    ).add(conversation_id)

    async def revoke_membership(self, conversation_id: str) -> None:
        if not self.available:
            raise FirebaseNotConfigured()
        self.membership.pop(conversation_id, None)
        for readers in self.visibility.values():
            for reader_uid, grants in list(readers.items()):
                grants.discard(conversation_id)
                if not grants:
                    del readers[reader_uid]

    async def read_visibility(self) -> dict[str, dict[str, dict[str, bool]]]:
        if not self.available:
            raise FirebaseNotConfigured()
        return {
            target: {
                reader: {conversation: True for conversation in grants}
                for reader, grants in readers.items()
            }
            for target, readers in self.visibility.items()
        }

    async def add_visibility_grant(
        self, target_uid: str, reader_uid: str, conversation_id: str
    ) -> None:
        if not self.available:
            raise FirebaseNotConfigured()
        self.visibility_writes += 1
        self.visibility.setdefault(target_uid, {}).setdefault(
            reader_uid, set()
        ).add(conversation_id)

    async def remove_visibility_grant(
        self, target_uid: str, reader_uid: str, conversation_id: str
    ) -> None:
        if not self.available:
            raise FirebaseNotConfigured()
        self.visibility_writes += 1
        readers = self.visibility.get(target_uid, {})
        grants = readers.get(reader_uid)
        if grants is None:
            return
        grants.discard(conversation_id)
        if not grants:
            del readers[reader_uid]
        if not readers:
            self.visibility.pop(target_uid, None)

    async def read_presence(self, uid: str) -> PresenceState:
        if not self.available:
            raise FirebaseNotConfigured()
        return PresenceState(
            uid=uid, online=self.presence.get(uid, False), last_changed=_now()
        )

    async def clear_typing(self, conversation_id: str) -> None:
        if not self.available:
            raise FirebaseNotConfigured()
        self.typing_cleared.append(conversation_id)


class FakeStorageProvider:
    name = PROVIDER_NAME

    def __init__(self) -> None:
        self.objects: dict[str, StorageObjectInfo] = {}
        self.deleted: list[str] = []
        self.unavailable = False

    @property
    def available(self) -> bool:
        return not self.unavailable

    def build_upload_grant(
        self,
        *,
        conversation_id: str,
        attachment_id: str,
        mime_type: str,
        max_bytes: int,
    ) -> StorageUploadGrant:
        extension = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }.get(mime_type, "bin")
        return StorageUploadGrant(
            storage_key=f"chat/{conversation_id}/{attachment_id}/original.{extension}",
            bucket="fake-bucket",
            max_bytes=max_bytes,
            allowed_mime_types=[mime_type],
        )

    async def inspect(self, storage_key: str) -> StorageObjectInfo:
        if not self.available:
            raise FirebaseNotConfigured()
        return self.objects.get(storage_key, StorageObjectInfo(exists=False))

    async def delete(self, storage_key: str) -> None:
        if not self.available:
            raise FirebaseNotConfigured()
        self.objects.pop(storage_key, None)
        self.deleted.append(storage_key)

    # --- test helper ----------------------------------------------------

    def place(
        self,
        storage_key: str,
        *,
        size_bytes: int = 1024,
        content_type: str = "image/jpeg",
    ) -> None:
        """Pretend a client uploaded something. Possibly not what it promised."""
        self.objects[storage_key] = StorageObjectInfo(
            exists=True, size_bytes=size_bytes, content_type=content_type
        )


class FakePushProvider:
    name = PROVIDER_NAME

    def __init__(self) -> None:
        self.sent: list[tuple[list[str], PushMessage]] = []
        # Data-only call messages, kept apart from notifications.
        self.data_sent: list[tuple[list[str], DataPushMessage]] = []
        self.dead_tokens: set[str] = set()
        self.transient_tokens: set[str] = set()
        self.fail_transient_times = 0
        self.unavailable = False

    @property
    def available(self) -> bool:
        return not self.unavailable

    async def send_to_device(self, token: str, message: PushMessage) -> PushResult:
        return await self.send_multicast([token], message)

    async def send_multicast(
        self, tokens: list[str], message: PushMessage
    ) -> PushResult:
        if not self.available:
            raise FirebaseNotConfigured()
        if not tokens:
            return PushResult(success_count=0, failure_count=0, invalid_tokens=[])

        if self.fail_transient_times > 0:
            self.fail_transient_times -= 1
            return PushResult(
                success_count=0,
                failure_count=len(tokens),
                invalid_tokens=[],
                retryable=True,
            )

        self.sent.append((list(tokens), message))
        dead = [token for token in tokens if token in self.dead_tokens]
        return PushResult(
            success_count=len(tokens) - len(dead),
            failure_count=len(dead),
            invalid_tokens=dead,
        )

    async def send_data(
        self, tokens: list[str], message: DataPushMessage
    ) -> PushResult:
        if not self.available:
            raise FirebaseNotConfigured()
        if not tokens:
            return PushResult(success_count=0, failure_count=0, invalid_tokens=[])
        self.data_sent.append((list(tokens), message))
        dead = [token for token in tokens if token in self.dead_tokens]
        retry = [token for token in tokens if token in self.transient_tokens]
        return PushResult(
            success_count=len(tokens) - len(dead) - len(retry),
            failure_count=len(dead) + len(retry),
            invalid_tokens=dead,
            retryable=bool(retry),
            retry_tokens=retry,
        )

    # --- test helpers ---------------------------------------------------

    @property
    def all_tokens(self) -> list[str]:
        return [token for tokens, _ in self.sent for token in tokens]

    def last_message(self) -> PushMessage | None:
        return self.sent[-1][1] if self.sent else None
