"""The real Firebase Admin SDK implementations.

Verified against firebase-admin **7.6.0** before writing, because two things
have changed in ways that break older examples:

* `messaging.send_multicast()` and `messaging.send_all()` were **removed** in
  7.x. The current API is `send_each_for_multicast()`, which returns a
  `BatchResponse` whose `responses[i].exception` tells you which token failed
  and why.
* `auth.verify_id_token(id_token, app=None, check_revoked=False,
  clock_skew_seconds=0)` is the current signature, and it raises
  `InvalidIdTokenError`, `ExpiredIdTokenError`, `RevokedIdTokenError`,
  `UserDisabledError` or `CertificateFetchError`.

The SDK is synchronous. Its calls run in a worker thread via `asyncio.to_thread`
so a Firestore round trip cannot block the event loop while other requests are
waiting.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
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
    FirebaseError,
    FirebaseNotConfigured,
    FirebaseTokenExpired,
    FirebaseTokenInvalid,
    FirebaseTokenRevoked,
    DataPushMessage,
    PushMessage,
    PushResult,
    StorageObjectInfo,
    StorageUploadGrant,
    safe_metadata,
)

logger = get_logger(__name__)

CONVERSATIONS = "conversations"
MESSAGES = "messages"

# The Android channel ordinary pushes use ("Astrofrekans Bildirimleri"),
# created by the app (android/.../NotificationChannels.kt). Call pushes are
# data-only and keep their own channel.
ANDROID_NOTIFICATION_CHANNEL = "astrofrekans_default"

_app: Any | None = None


def _credentials():  # noqa: ANN202 - SDK type
    """Build a credential from a path or an inline JSON secret.

    Inline suits container secret mounts; a path suits a developer machine.
    Neither is ever logged, and there is no third option that reads a
    credential from a request.
    """
    from firebase_admin import credentials

    if settings.firebase_credentials_json:
        return credentials.Certificate(
            json.loads(settings.firebase_credentials_json)
        )
    if settings.firebase_credentials_path:
        return credentials.Certificate(str(settings.firebase_credentials_path))
    raise FirebaseNotConfigured(
        "No Firebase service account is configured on this server."
    )


def get_app():  # noqa: ANN201 - SDK type
    """Initialise the Admin SDK once per process."""
    global _app
    if _app is not None:
        return _app

    if not settings.firebase_configured:
        raise FirebaseNotConfigured()

    import firebase_admin

    options: dict[str, Any] = {"projectId": settings.firebase_project_id}
    if settings.firebase_storage_bucket:
        options["storageBucket"] = settings.firebase_storage_bucket
    if settings.firebase_database_url:
        options["databaseURL"] = settings.firebase_database_url

    try:
        _app = firebase_admin.initialize_app(_credentials(), options)
    except ValueError:
        # Already initialised elsewhere in the process.
        _app = firebase_admin.get_app()

    logger.info(
        "firebase_initialised",
        project_id=settings.firebase_project_id,
        has_storage=bool(settings.firebase_storage_bucket),
        has_database=bool(settings.firebase_database_url),
    )
    return _app


def reset_app() -> None:
    """Drop the cached app. Tests and configuration reloads only."""
    global _app
    _app = None


def _configured() -> bool:
    return settings.firebase_configured and settings.firebase_provider == "firebase"


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------- identity


class FirebaseIdentityProviderImpl:
    name = "firebase"

    @property
    def available(self) -> bool:
        return _configured()

    async def verify_id_token(
        self, token: str, *, check_revoked: bool = False
    ) -> FirebaseIdentity:
        if not self.available:
            raise FirebaseNotConfigured()

        from firebase_admin import auth
        from firebase_admin import exceptions as firebase_exceptions

        def _verify() -> dict[str, Any]:
            return auth.verify_id_token(
                token,
                app=get_app(),
                check_revoked=check_revoked or settings.firebase_check_revoked,
                clock_skew_seconds=settings.firebase_token_clock_skew_seconds,
            )

        try:
            claims = await asyncio.to_thread(_verify)
        except auth.ExpiredIdTokenError as exc:
            raise FirebaseTokenExpired() from exc
        except auth.RevokedIdTokenError as exc:
            raise FirebaseTokenRevoked() from exc
        except auth.UserDisabledError as exc:
            raise FirebaseAccountDisabled() from exc
        except auth.InvalidIdTokenError as exc:
            # Deliberately not echoing the SDK message: it can describe the
            # token, and a client has no use for that detail.
            raise FirebaseTokenInvalid() from exc
        except auth.CertificateFetchError as exc:
            logger.error("firebase_certificate_fetch_failed")
            raise FirebaseError(
                "Could not verify the sign-in token right now."
            ) from exc
        except auth.UserNotFoundError as exc:
            # Revocation check only: the token is genuine but its account is
            # gone.
            raise FirebaseTokenInvalid() from exc
        except firebase_exceptions.FirebaseError as exc:
            # Revocation check only: Firebase could not be asked (outage,
            # quota, timeout). Not the person's fault - a 5xx, never a 401 that
            # would sign them out.
            logger.error(
                "firebase_revocation_check_failed", error_class=type(exc).__name__
            )
            raise FirebaseError(
                "Could not verify the sign-in token right now."
            ) from exc
        except ValueError as exc:
            raise FirebaseTokenInvalid() from exc

        return _identity_from_claims(claims)

    async def revoke_refresh_tokens(self, uid: str) -> None:
        if not self.available:
            raise FirebaseNotConfigured()
        from firebase_admin import auth

        await asyncio.to_thread(auth.revoke_refresh_tokens, uid, get_app())
        logger.info("firebase_tokens_revoked", firebase_uid=uid)

    async def delete_user(self, uid: str) -> None:
        if not self.available:
            raise FirebaseNotConfigured()
        from firebase_admin import auth

        try:
            await asyncio.to_thread(auth.delete_user, uid, get_app())
        except auth.UserNotFoundError:
            # Already gone is the desired end state.
            pass
        logger.info("firebase_user_deleted", firebase_uid=uid)


def _identity_from_claims(claims: dict[str, Any]) -> FirebaseIdentity:
    """Take only the claims the product uses.

    `firebase.sign_in_provider` is where the actual provider lives; the
    top-level `provider_id` is not reliably present.
    """
    firebase_claims = claims.get("firebase") or {}
    return FirebaseIdentity(
        uid=claims["uid"],
        email=claims.get("email"),
        email_verified=bool(claims.get("email_verified", False)),
        provider_id=firebase_claims.get("sign_in_provider"),
        name=claims.get("name"),
        picture=claims.get("picture"),
        auth_time=claims.get("auth_time"),
    )


# ---------------------------------------------------------------- firestore


class FirestoreChatProviderImpl:
    name = "firebase"

    @property
    def available(self) -> bool:
        return _configured()

    def _client(self):  # noqa: ANN202 - SDK type
        from firebase_admin import firestore

        return firestore.client(app=get_app())

    async def upsert_conversation(self, projection: ConversationProjection) -> None:
        if not self.available:
            raise FirebaseNotConfigured()

        def _write() -> None:
            doc = (
                self._client()
                .collection(CONVERSATIONS)
                .document(projection.conversation_id)
            )
            # merge=True keeps this idempotent: a reconciliation pass must not
            # wipe fields it does not know about.
            doc.set(
                {
                    "memberUids": projection.member_uids,
                    "userUid": projection.user_uid,
                    "expertUid": projection.expert_uid,
                    "status": projection.status.value,
                    "orderId": projection.order_id,
                    "version": projection.version,
                    "updatedAt": _now(),
                },
                merge=True,
            )

        await asyncio.to_thread(_write)
        logger.info(
            "firebase_projection_created",
            conversation_id=projection.conversation_id,
            members=len(projection.member_uids),
            status=projection.status.value,
        )

    async def set_conversation_status(
        self, conversation_id: str, status: ConversationStatus
    ) -> None:
        if not self.available:
            raise FirebaseNotConfigured()

        def _write() -> None:
            self._client().collection(CONVERSATIONS).document(conversation_id).set(
                {"status": status.value, "updatedAt": _now()}, merge=True
            )

        await asyncio.to_thread(_write)

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

        from firebase_admin import firestore

        message_id = uuid.uuid4().hex

        def _write() -> dict[str, Any]:
            payload = {
                "senderUid": sender_uid,
                "senderRole": sender_role.value,
                "type": message_type.value,
                "text": text,
                "attachmentId": attachment_id,
                "clientMessageId": client_message_id,
                # The server's clock, not the client's: a device with a wrong
                # clock would otherwise reorder somebody else's conversation.
                "createdAt": firestore.SERVER_TIMESTAMP,
                "editedAt": None,
                "deletedAt": None,
            }
            reference = (
                self._client()
                .collection(CONVERSATIONS)
                .document(conversation_id)
                .collection(MESSAGES)
                .document(message_id)
            )
            reference.set(payload)
            return reference.get().to_dict() or {}

        stored = await asyncio.to_thread(_write)
        return _message_from_doc(conversation_id, message_id, stored)

    async def find_by_client_message_id(
        self, conversation_id: str, client_message_id: str
    ) -> ChatMessage | None:
        if not self.available:
            raise FirebaseNotConfigured()

        def _read() -> tuple[str, dict[str, Any]] | None:
            query = (
                self._client()
                .collection(CONVERSATIONS)
                .document(conversation_id)
                .collection(MESSAGES)
                .where("clientMessageId", "==", client_message_id)
                .limit(1)
            )
            for snapshot in query.stream():
                return snapshot.id, snapshot.to_dict() or {}
            return None

        found = await asyncio.to_thread(_read)
        if found is None:
            return None
        return _message_from_doc(conversation_id, found[0], found[1])

    async def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 50,
        before: str | None = None,
    ) -> list[ChatMessage]:
        if not self.available:
            raise FirebaseNotConfigured()

        from firebase_admin import firestore

        def _read() -> list[tuple[str, dict[str, Any]]]:
            query = (
                self._client()
                .collection(CONVERSATIONS)
                .document(conversation_id)
                .collection(MESSAGES)
                .order_by("createdAt", direction=firestore.Query.DESCENDING)
            )
            if before:
                query = query.start_after({"createdAt": before})
            return [
                (snapshot.id, snapshot.to_dict() or {})
                for snapshot in query.limit(limit).stream()
            ]

        rows = await asyncio.to_thread(_read)
        return [
            _message_from_doc(conversation_id, doc_id, data) for doc_id, data in rows
        ]

    async def soft_delete_message(
        self, conversation_id: str, message_id: str, *, sender_uid: str
    ) -> ChatMessage:
        if not self.available:
            raise FirebaseNotConfigured()

        def _write() -> dict[str, Any]:
            reference = (
                self._client()
                .collection(CONVERSATIONS)
                .document(conversation_id)
                .collection(MESSAGES)
                .document(message_id)
            )
            snapshot = reference.get()
            data = snapshot.to_dict() or {}
            if not snapshot.exists:
                raise FirebaseError("That message does not exist.")
            if data.get("senderUid") != sender_uid:
                # Belt and braces: the service layer checks this too, but a
                # store that enforces it cannot be talked around.
                raise FirebaseError("Only the sender may delete a message.")
            reference.set(
                {"deletedAt": _now(), "text": None, "attachmentId": None},
                merge=True,
            )
            return reference.get().to_dict() or {}

        stored = await asyncio.to_thread(_write)
        return _message_from_doc(conversation_id, message_id, stored)


def _message_from_doc(
    conversation_id: str, message_id: str, data: dict[str, Any]
) -> ChatMessage:
    created = data.get("createdAt")
    return ChatMessage(
        message_id=message_id,
        conversation_id=conversation_id,
        sender_uid=data.get("senderUid", ""),
        sender_role=ConversationRole(data.get("senderRole", "user")),
        message_type=ChatMessageType(data.get("type", "text")),
        text=data.get("text"),
        attachment_id=data.get("attachmentId"),
        client_message_id=data.get("clientMessageId"),
        created_at=created.isoformat() if hasattr(created, "isoformat") else str(created),
        edited_at=data.get("editedAt"),
        deleted_at=data.get("deletedAt"),
    )


# ----------------------------------------------------------------- presence


class FirebasePresenceProviderImpl:
    name = "firebase"

    @property
    def available(self) -> bool:
        return _configured() and bool(settings.firebase_database_url)

    def _reference(self, path: str):  # noqa: ANN202 - SDK type
        from firebase_admin import db

        return db.reference(path, app=get_app())

    async def publish_membership(
        self, conversation_id: str, member_uids: list[str]
    ) -> None:
        """Mirror membership into RTDB.

        The RTDB rules need to answer "is this uid a member?" without reading
        Postgres, so the backend writes the answer and the rules consult it.
        Clients cannot write these paths.

        Two projections, because they answer different questions. `typing` is
        per-conversation, so `conversationMembers/{id}` is enough. Presence is
        per-user - a client subscribes to `presence/{partnerUid}`, which names no
        conversation - so the rules need "may this reader see this user", and
        that is `presenceVisibility`. Without it a partner's listener is denied
        and nobody ever appears online.
        """
        if not self.available:
            raise FirebaseNotConfigured()

        def _write() -> None:
            self._reference(f"conversationMembers/{conversation_id}").set(
                {uid: True for uid in member_uids}
            )
            # Presence reads name a user, not a conversation. Keep each shared
            # conversation under the reader's uid so the rules can check one
            # path and revocation cannot remove another thread's grant.
            for uid in member_uids:
                for reader_uid in member_uids:
                    if reader_uid == uid:
                        continue
                    self._reference(
                        f"presenceVisibility/{uid}/{reader_uid}"
                    ).transaction(
                        lambda grants: {**(grants or {}), conversation_id: True}
                    )

        await asyncio.to_thread(_write)

    async def revoke_membership(self, conversation_id: str) -> None:
        if not self.available:
            raise FirebaseNotConfigured()

        def _write() -> None:
            members = (
                self._reference(f"conversationMembers/{conversation_id}").get()
                or {}
            )
            for uid in members:
                for reader_uid in members:
                    if reader_uid == uid:
                        continue
                    self._reference(
                        f"presenceVisibility/{uid}/{reader_uid}"
                    ).transaction(
                        lambda grants: (
                            {key: value for key, value in (grants or {}).items()
                             if key != conversation_id} or None
                        )
                    )
            self._reference(f"conversationMembers/{conversation_id}").delete()
            self._reference(f"typing/{conversation_id}").delete()

        await asyncio.to_thread(_write)

    async def read_visibility(self) -> dict[str, dict[str, dict[str, Any]]]:
        if not self.available:
            raise FirebaseNotConfigured()

        def _read() -> Any:
            return self._reference("presenceVisibility").get()

        tree = await asyncio.to_thread(_read)
        return tree if isinstance(tree, dict) else {}

    async def add_visibility_grant(
        self, target_uid: str, reader_uid: str, conversation_id: str
    ) -> None:
        if not self.available:
            raise FirebaseNotConfigured()

        def _write() -> None:
            self._reference(
                f"presenceVisibility/{target_uid}/{reader_uid}"
            ).transaction(
                lambda grants: {**(grants or {}), conversation_id: True}
            )

        await asyncio.to_thread(_write)

    async def remove_visibility_grant(
        self, target_uid: str, reader_uid: str, conversation_id: str
    ) -> None:
        if not self.available:
            raise FirebaseNotConfigured()

        def _write() -> None:
            self._reference(
                f"presenceVisibility/{target_uid}/{reader_uid}"
            ).transaction(
                lambda grants: (
                    {key: value for key, value in (grants or {}).items()
                     if key != conversation_id} or None
                )
            )

        await asyncio.to_thread(_write)

    async def read_presence(self, uid: str) -> PresenceState:
        if not self.available:
            raise FirebaseNotConfigured()

        def _read() -> dict[str, Any] | None:
            return self._reference(f"presence/{uid}").get()

        data = await asyncio.to_thread(_read) or {}
        return PresenceState(
            uid=uid,
            online=data.get("state") == "online",
            last_changed=data.get("lastChanged"),
        )

    async def clear_typing(self, conversation_id: str) -> None:
        if not self.available:
            raise FirebaseNotConfigured()

        def _write() -> None:
            self._reference(f"typing/{conversation_id}").delete()

        await asyncio.to_thread(_write)


# ------------------------------------------------------------------ storage


class FirebaseStorageProviderImpl:
    name = "firebase"

    @property
    def available(self) -> bool:
        return _configured() and bool(settings.firebase_storage_bucket)

    def _bucket(self):  # noqa: ANN202 - SDK type
        from firebase_admin import storage

        return storage.bucket(settings.firebase_storage_bucket, app=get_app())

    def build_upload_grant(
        self,
        *,
        conversation_id: str,
        attachment_id: str,
        mime_type: str,
        max_bytes: int,
    ) -> StorageUploadGrant:
        """The server picks the path. Always.

        A client-supplied filename in the path is a directory-traversal and an
        overwrite problem wearing a convenience disguise. The original name is
        kept as metadata in Postgres instead.
        """
        extension = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "application/pdf": "pdf",
        }.get(mime_type, "bin")

        return StorageUploadGrant(
            storage_key=(
                f"chat/{conversation_id}/{attachment_id}/original.{extension}"
            ),
            bucket=settings.firebase_storage_bucket or "",
            max_bytes=max_bytes,
            allowed_mime_types=sorted(settings.allowed_attachment_mime_types),
        )

    async def inspect(self, storage_key: str) -> StorageObjectInfo:
        """What is in the bucket, not what the client said it uploaded."""
        if not self.available:
            raise FirebaseNotConfigured()

        def _read() -> StorageObjectInfo:
            blob = self._bucket().get_blob(storage_key)
            if blob is None:
                return StorageObjectInfo(exists=False)
            return StorageObjectInfo(
                exists=True,
                size_bytes=blob.size,
                content_type=blob.content_type,
                sha256=None,
            )

        return await asyncio.to_thread(_read)

    async def delete(self, storage_key: str) -> None:
        if not self.available:
            raise FirebaseNotConfigured()

        def _write() -> None:
            blob = self._bucket().get_blob(storage_key)
            if blob is not None:
                blob.delete()

        await asyncio.to_thread(_write)


# --------------------------------------------------------------------- push


class FirebasePushProviderImpl:
    name = "firebase"

    @property
    def available(self) -> bool:
        return _configured()

    async def send_to_device(self, token: str, message: PushMessage) -> PushResult:
        return await self.send_multicast([token], message)

    async def send_multicast(
        self, tokens: list[str], message: PushMessage
    ) -> PushResult:
        """Fan out to a user's devices.

        Uses `send_each_for_multicast`, which is the current API -
        `send_multicast` and `send_all` were removed in firebase-admin 7.x.
        Per-token failures come back in the batch rather than as one exception,
        which is what lets a dead device be retired without failing the rest.
        """
        if not self.available:
            raise FirebaseNotConfigured()
        if not tokens:
            return PushResult(success_count=0, failure_count=0, invalid_tokens=[])

        from firebase_admin import messaging

        def _send() -> PushResult:
            apns_headers = {"apns-priority": "10"}
            android_ttl = None
            if message.ttl_seconds is not None:
                android_ttl = timedelta(seconds=max(0, message.ttl_seconds))
                apns_headers["apns-expiration"] = str(
                    int(time.time()) + max(0, message.ttl_seconds)
                )
            payload = messaging.MulticastMessage(
                tokens=tokens,
                notification=messaging.Notification(
                    title=message.title, body=message.body
                ),
                data=safe_metadata(message.data),
                android=messaging.AndroidConfig(
                    priority="high",
                    collapse_key=message.collapse_key,
                    ttl=android_ttl,
                    # `sound` matters on Android 7 (no channels); from 8 on the
                    # channel's own sound applies.
                    notification=messaging.AndroidNotification(
                        channel_id=ANDROID_NOTIFICATION_CHANNEL, sound="default"
                    ),
                ),
                apns=messaging.APNSConfig(
                    headers=apns_headers,
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound="default")
                    ),
                ),
            )
            return _batch_result(
                tokens, messaging.send_each_for_multicast(payload, app=get_app())
            )

        return await asyncio.to_thread(_send)

    async def send_data(
        self, tokens: list[str], message: DataPushMessage
    ) -> PushResult:
        """Data-only: no `notification`, so the app's receiver runs even in the
        background and presents (or dismisses) the call UI itself.

        Android: `priority` and `ttl` on `AndroidConfig`. An iOS FCM token only
        ever gets a background update (`content-available`, push type
        `background`, priority 5) - rings on iOS go through PushKit VoIP.
        """
        if not self.available:
            raise FirebaseNotConfigured()
        if not tokens:
            return PushResult(success_count=0, failure_count=0, invalid_tokens=[])

        from firebase_admin import messaging

        def _send() -> PushResult:
            ttl = (
                timedelta(seconds=max(0, message.ttl_seconds))
                if message.ttl_seconds is not None
                else None
            )
            apns = None
            if message.apns_background:
                headers = {"apns-push-type": "background", "apns-priority": "5"}
                if message.ttl_seconds is not None:
                    headers["apns-expiration"] = str(
                        int(time.time()) + max(0, message.ttl_seconds)
                    )
                apns = messaging.APNSConfig(
                    headers=headers,
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(content_available=True)
                    ),
                )
            payload = messaging.MulticastMessage(
                tokens=tokens,
                data=safe_metadata(message.data),
                android=messaging.AndroidConfig(
                    priority=message.android_priority,
                    ttl=ttl,
                    collapse_key=message.collapse_key,
                ),
                apns=apns,
            )
            return _batch_result(
                tokens, messaging.send_each_for_multicast(payload, app=get_app())
            )

        return await asyncio.to_thread(_send)


def _batch_result(tokens: list[str], batch) -> PushResult:  # noqa: ANN001 - SDK type
    """Per-token outcome of a multicast: delivered, dead, or worth retrying."""
    from firebase_admin import messaging

    dead: list[str] = []
    retry: list[str] = []
    for token, response in zip(tokens, batch.responses, strict=True):
        if response.success:
            continue
        error = response.exception
        if isinstance(
            error,
            (messaging.UnregisteredError, messaging.SenderIdMismatchError),
        ):
            # The device is gone or belongs to another project. Retiring
            # it is the fix; retrying never will be.
            dead.append(token)
        else:
            retry.append(token)
    return PushResult(
        success_count=batch.success_count,
        failure_count=batch.failure_count,
        invalid_tokens=dead,
        retryable=bool(retry),
        retry_tokens=retry,
    )
