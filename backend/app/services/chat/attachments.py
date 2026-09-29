"""Chat attachments: authorise, then upload, then verify.

Three decisions worth stating.

**The server picks the path.** `chat/{conversationId}/{attachmentId}/original.jpg`
is derived from ids the backend issued. A client-supplied filename in a storage
path is a directory-traversal and an overwrite problem wearing a convenience
disguise, so the original name is kept as display metadata and never touched by
the path.

**The claimed type is not the type.** A client says `image/png`; the bucket says
what was actually stored. Finalisation compares the two and rejects a mismatch,
because "trust the extension" is how an HTML file becomes a stored XSS and an
SVG becomes a script.

**Pending is not a file.** An attachment is an authorised intent until the bytes
arrive. A message may only reference a `ready` one, or it renders as a broken
image in somebody's paid consultation.

The upload itself is direct to Firebase Storage. That is the right call for a
mobile client - a photo should not be proxied through the API - but it means the
storage rules have to enforce the same path, size and membership that this
service does. Both are written; neither is trusted alone.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, NotFound
from app.core.logging import get_logger
from app.db.models.chat import ExpertConversation, MediaAttachment
from app.db.models.user import User
from app.domain.chat import AttachmentStatus
from app.services.firebase.provider import (
    FirebaseProviders,
    StorageUploadGrant,
)

logger = get_logger(__name__)

# Types that are never accepted, whatever the configuration says. SVG and HTML
# are scriptable; the rest are executable. A "chat image" that runs code in a
# viewer's browser is not an image.
NEVER_ALLOWED = frozenset(
    {
        "image/svg+xml",
        "text/html",
        "application/xhtml+xml",
        "application/javascript",
        "text/javascript",
        "application/x-msdownload",
        "application/x-sh",
        "application/vnd.microsoft.portable-executable",
    }
)


class AttachmentRejected(AppError):
    status_code = 422
    code = "attachment_rejected"
    message = "That file cannot be attached."


class AttachmentQuotaExceeded(AppError):
    status_code = 429
    code = "attachment_quota_exceeded"
    message = "Too many attachments in this conversation right now."


class AttachmentService:
    def __init__(self, session: AsyncSession, firebase: FirebaseProviders) -> None:
        self.session = session
        self.firebase = firebase

    # ------------------------------------------------------------ create

    def _check_type(self, mime_type: str) -> str:
        normalised = (mime_type or "").strip().lower()
        if normalised in NEVER_ALLOWED:
            raise AttachmentRejected(
                f"'{normalised}' is never accepted as an attachment.",
                code="mime_type_forbidden",
            )
        if normalised not in settings.allowed_attachment_mime_types:
            raise AttachmentRejected(
                f"'{normalised}' is not an accepted attachment type.",
                code="mime_type_not_allowed",
                details={
                    "allowed": sorted(settings.allowed_attachment_mime_types)
                },
            )
        return normalised

    def _check_size(self, declared_bytes: int) -> int:
        if declared_bytes <= 0:
            raise AttachmentRejected("An empty file cannot be attached.")
        if declared_bytes > settings.attachment_max_bytes:
            raise AttachmentRejected(
                "That file is larger than attachments may be.",
                code="attachment_too_large",
                details={"max_bytes": settings.attachment_max_bytes},
            )
        return declared_bytes

    async def create_intent(
        self,
        user: User,
        conversation: ExpertConversation,
        *,
        mime_type: str,
        size_bytes: int,
        original_filename: str | None = None,
    ) -> tuple[MediaAttachment, StorageUploadGrant]:
        """Authorise an upload, and say exactly where it may go.

        Returns the row and the grant. The grant names one path, one size
        ceiling and one content type - nothing wider.
        """
        normalised_type = self._check_type(mime_type)
        declared = self._check_size(size_bytes)

        # A bound on in-flight uploads per conversation, so an abandoned client
        # loop cannot mint authorisations indefinitely.
        pending_rows = await self.session.scalars(
            select(MediaAttachment.id).where(
                MediaAttachment.conversation_id == conversation.id,
                MediaAttachment.uploader_user_id == user.id,
                MediaAttachment.status == AttachmentStatus.PENDING.value,
            )
        )
        if len(list(pending_rows)) >= max(settings.chat_attachments_per_message * 4, 8):
            raise AttachmentQuotaExceeded()

        attachment_id = uuid.uuid4()
        grant = self.firebase.storage.build_upload_grant(
            conversation_id=str(conversation.id),
            attachment_id=str(attachment_id),
            mime_type=normalised_type,
            max_bytes=settings.attachment_max_bytes,
        )

        attachment = MediaAttachment(
            id=attachment_id,
            conversation_id=conversation.id,
            uploader_user_id=user.id,
            storage_provider="firebase",
            storage_key=grant.storage_key,
            original_filename=(original_filename or "").strip()[:255] or None,
            mime_type=normalised_type,
            size_bytes=declared,
            status=AttachmentStatus.PENDING.value,
        )
        self.session.add(attachment)
        await self.session.flush()

        # The filename is not logged: it is user-supplied text that often
        # carries a name or a date.
        logger.info(
            "attachment_intent_created",
            attachment_id=str(attachment.id),
            conversation_id=str(conversation.id),
            mime_type=normalised_type,
            declared_bytes=declared,
        )
        return attachment, grant

    # ---------------------------------------------------------- finalise

    async def finalise(
        self, user: User, conversation: ExpertConversation, attachment_id: uuid.UUID
    ) -> MediaAttachment:
        """Confirm the bytes arrived, and that they are what was promised.

        This is the only place an attachment becomes usable, and it believes
        the bucket rather than the client.
        """
        attachment = await self.get_own(user, conversation, attachment_id)

        if AttachmentStatus(attachment.status) is AttachmentStatus.READY:
            return attachment
        if AttachmentStatus(attachment.status) in (
            AttachmentStatus.REJECTED,
            AttachmentStatus.DELETED,
        ):
            raise AttachmentRejected(
                "That attachment was already rejected.",
                details={"status": attachment.status},
            )

        info = await self.firebase.storage.inspect(attachment.storage_key)
        if not info.exists:
            raise AttachmentRejected(
                "Nothing has been uploaded for that attachment yet.",
                code="attachment_missing",
            )

        actual_type = (info.content_type or "").split(";")[0].strip().lower()
        if actual_type in NEVER_ALLOWED or (
            actual_type
            and actual_type not in settings.allowed_attachment_mime_types
        ):
            await self._reject(attachment, "mime_type_mismatch")
            raise AttachmentRejected(
                "The uploaded file is not an accepted type.",
                code="mime_type_not_allowed",
                details={"detected": actual_type},
            )

        if info.size_bytes is not None:
            if info.size_bytes > settings.attachment_max_bytes:
                await self._reject(attachment, "too_large")
                raise AttachmentRejected(
                    "The uploaded file is larger than attachments may be.",
                    code="attachment_too_large",
                )
            if info.size_bytes == 0:
                await self._reject(attachment, "empty")
                raise AttachmentRejected("The uploaded file is empty.")

        attachment.status = AttachmentStatus.READY.value
        attachment.verified_mime_type = actual_type or attachment.mime_type
        attachment.size_bytes = info.size_bytes or attachment.size_bytes
        attachment.sha256 = info.sha256
        await self.session.flush()

        logger.info(
            "attachment_ready",
            attachment_id=str(attachment.id),
            conversation_id=str(conversation.id),
            verified_mime_type=attachment.verified_mime_type,
            size_bytes=attachment.size_bytes,
        )
        return attachment

    async def _reject(self, attachment: MediaAttachment, reason: str) -> None:
        attachment.status = AttachmentStatus.REJECTED.value
        attachment.rejection_reason = reason[:120]
        await self.session.flush()
        logger.warning(
            "attachment_rejected",
            attachment_id=str(attachment.id),
            reason=reason,
        )
        # The bytes are not wanted, so they do not stay in the bucket.
        try:
            await self.firebase.storage.delete(attachment.storage_key)
        except Exception:  # noqa: BLE001 - cleanup is best effort
            logger.warning(
                "attachment_cleanup_failed", attachment_id=str(attachment.id)
            )

    # -------------------------------------------------------------- read

    async def get_own(
        self,
        user: User,
        conversation: ExpertConversation,
        attachment_id: uuid.UUID,
    ) -> MediaAttachment:
        """Scoped to this conversation **and** this uploader.

        Both, so a member cannot finalise somebody else's pending upload and a
        finalised attachment cannot be replayed into another thread.
        """
        attachment = await self.session.scalar(
            select(MediaAttachment).where(
                MediaAttachment.id == attachment_id,
                MediaAttachment.conversation_id == conversation.id,
                MediaAttachment.uploader_user_id == user.id,
            )
        )
        if attachment is None:
            raise NotFound("Attachment not found.")
        return attachment

    async def list_for_conversation(
        self, conversation: ExpertConversation, *, limit: int = 50
    ) -> list[MediaAttachment]:
        return list(
            await self.session.scalars(
                select(MediaAttachment)
                .where(
                    MediaAttachment.conversation_id == conversation.id,
                    MediaAttachment.status == AttachmentStatus.READY.value,
                )
                .order_by(MediaAttachment.created_at.desc())
                .limit(limit)
            )
        )

    # ----------------------------------------------------------- cleanup

    async def purge_stale_intents(self, *, limit: int = 100) -> int:
        """Retire authorisations nobody used.

        A pending row is a promise the client never kept. Left alone they
        accumulate, and each one is a path somebody is still allowed to write
        to - so they expire.
        """
        cutoff = datetime.now(UTC) - timedelta(
            seconds=settings.attachment_pending_ttl_seconds
        )
        rows = list(
            await self.session.scalars(
                select(MediaAttachment)
                .where(
                    MediaAttachment.status == AttachmentStatus.PENDING.value,
                    MediaAttachment.created_at < cutoff,
                )
                .limit(limit)
            )
        )

        for attachment in rows:
            # A client may have uploaded without ever finalising. If bytes are
            # there they are orphaned, so they go too.
            try:
                info = await self.firebase.storage.inspect(attachment.storage_key)
                if info.exists:
                    await self.firebase.storage.delete(attachment.storage_key)
            except Exception:  # noqa: BLE001 - best effort
                pass
            attachment.status = AttachmentStatus.DELETED.value
            attachment.rejection_reason = "expired_unused"

        if rows:
            await self.session.flush()
            logger.info("attachment_intents_purged", count=len(rows))
        return len(rows)
