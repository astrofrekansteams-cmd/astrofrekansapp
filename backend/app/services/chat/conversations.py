"""Expert chat conversations: authorisation, provisioning and messages.

**Backend-mediated writes.** This is the phase's main architectural decision,
and it is worth stating plainly: clients read Firestore directly through a
listener, and write nothing. Every message goes through this service.

Why not let the client write straight to Firestore, which would be one fewer
hop?

* Authorisation here is not "is this person a member" - it is "does an order in
  a writable state entitle this person to speak to this expert right now". That
  depends on order state, expert suspension, a completion grace period and the
  catalogue. Security rules cannot see any of it without mirroring the whole
  marketplace into Firestore, and a mirror that can drift is a permission bug
  waiting to happen.
* Message idempotency, length and content limits, attachment readiness, the
  push outbox and rate limiting all need server logic regardless.
* It makes the rules small enough to reason about: members may read, nobody may
  write. A rule that permits writes has to be right about everything above.

The cost is honest: sending a message pays one backend round trip. Receiving is
still instant, because the listener is unchanged. That trade is documented in
`docs/chat_architecture.md`.

**Firestore is the canonical message store.** Postgres holds authorisation,
audit metadata, attachments and the outbox - not a second copy of every
message, which would give two stores that can disagree about what somebody
said.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, NotFound
from app.core.logging import get_logger
from app.db.models.chat import ExpertConversation, MediaAttachment
from app.db.models.marketplace import Appointment, Expert, ServiceOrder
from app.db.models.service import ServiceDefinition
from app.db.models.user import User
from app.domain.chat import (
    AttachmentStatus,
    ChatMessage,
    ChatMessageType,
    ConversationRole,
    ConversationStatus,
    ProvisioningStatus,
)
from app.services.chat.policy import (
    ChatNotAvailable,
    ChatPermission,
    conversation_status_for_order,
    grants_presence,
    order_allows_new_conversation,
    permission_for,
)
from app.services.firebase.provider import (
    ConversationProjection,
    FirebaseError,
    FirebaseProviders,
)

logger = get_logger(__name__)

# Control characters that have no business in a chat message. Newline and tab
# are fine; the rest are either invisible or break rendering.
_FORBIDDEN_CHARS = {chr(code) for code in range(32)} - {"\n", "\r", "\t"}


class MessageRejected(AppError):
    status_code = 422
    code = "message_rejected"
    message = "That message could not be sent."


class MessageConflict(AppError):
    status_code = 409
    code = "message_conflict"
    message = "That client message id was already used with a different message."


class NoFirebaseIdentity(AppError):
    """Chat needs a Firebase identity, because the transport is Firebase."""

    status_code = 409
    code = "firebase_identity_required"
    message = (
        "Sign in with your Firebase account to use chat. Your existing "
        "account continues to work everywhere else."
    )


def sanitise_text(text: str) -> str:
    """Reject the pathological, normalise the merely untidy."""
    cleaned = "".join(char for char in text if char not in _FORBIDDEN_CHARS)
    cleaned = cleaned.strip()

    if not cleaned:
        raise MessageRejected("An empty message cannot be sent.", code="empty_message")
    if len(cleaned) > settings.chat_message_max_length:
        raise MessageRejected(
            f"A message may be at most {settings.chat_message_max_length} "
            "characters.",
            code="message_too_long",
            details={"max_length": settings.chat_message_max_length},
        )
    return cleaned


class ConversationService:
    def __init__(self, session: AsyncSession, firebase: FirebaseProviders) -> None:
        self.session = session
        self.firebase = firebase

    # ------------------------------------------------------- eligibility

    async def _order_for_user(self, user: User, order_id: uuid.UUID) -> ServiceOrder:
        order = await self.session.scalar(
            select(ServiceOrder).where(
                ServiceOrder.id == order_id,
                ServiceOrder.user_id == user.id,
                ServiceOrder.deleted_at.is_(None),
            )
        )
        if order is None:
            raise NotFound("Order not found.")
        return order

    async def ensure_for_order(
        self, user: User, order_id: uuid.UUID
    ) -> ExpertConversation:
        """Open the conversation for an order, or return the existing one.

        Idempotent by construction: one conversation per order is a database
        constraint, so a retried request returns the original thread instead of
        opening a second one.
        """
        order = await self._order_for_user(user, order_id)
        definition = await self.session.scalar(
            select(ServiceDefinition).where(
                ServiceDefinition.id == order.service_definition_id
            )
        )
        if definition is None:  # pragma: no cover - FK guarantees it
            raise NotFound("That service is not in the catalogue.")

        existing = await self.session.scalar(
            select(ExpertConversation).where(
                ExpertConversation.order_id == order.id,
                ExpertConversation.deleted_at.is_(None),
            )
        )
        if existing is not None:
            await self._reconcile(existing, order)
            return existing

        eligible, reason = order_allows_new_conversation(order, definition)
        if not eligible:
            raise ChatNotAvailable(
                "Chat is not available for this order.",
                details={"reason": reason, "order_status": order.status},
            )

        expert = await self.session.scalar(
            select(Expert).where(Expert.id == order.expert_id)
        )
        if expert is None:  # pragma: no cover - FK guarantees it
            raise NotFound("Expert not found.")

        appointment = await self.session.scalar(
            select(Appointment).where(Appointment.service_order_id == order.id)
        )

        conversation = ExpertConversation(
            order_id=order.id,
            appointment_id=appointment.id if appointment else None,
            user_id=user.id,
            expert_id=expert.id,
            expert_user_id=expert.user_id,
            status=conversation_status_for_order(order).value,
            provisioning_status=ProvisioningStatus.PENDING.value,
        )
        self.session.add(conversation)

        try:
            await self.session.flush()
        except IntegrityError:
            # Two concurrent requests for the same order. The constraint held;
            # whoever lost reads the row the winner wrote.
            await self.session.rollback()
            again = await self.session.scalar(
                select(ExpertConversation).where(
                    ExpertConversation.order_id == order.id
                )
            )
            if again is None:  # pragma: no cover - the constraint says otherwise
                raise
            return again

        conversation.firebase_conversation_id = str(conversation.id)
        await self.session.flush()

        logger.info(
            "chat_conversation_created",
            conversation_id=str(conversation.id),
            order_id=str(order.id),
            expert_id=str(expert.id),
            status=conversation.status,
        )

        await self.provision(conversation)
        return conversation

    # ------------------------------------------------------ provisioning

    async def provision(self, conversation: ExpertConversation) -> bool:
        """Write the Firestore/RTDB projection.

        Failure is recorded, not raised. Firebase being briefly unavailable
        must not roll back an order somebody paid for - so the conversation
        exists, is marked `failed`, and a reconciliation pass retries it.
        """
        user_uid, expert_uid = await self._member_uids(conversation)
        members = [uid for uid in (user_uid, expert_uid) if uid]

        if not members:
            conversation.provisioning_status = ProvisioningStatus.PENDING.value
            conversation.provisioning_error = "no_firebase_identity"
            await self.session.flush()
            return False

        projection = ConversationProjection(
            conversation_id=str(conversation.id),
            member_uids=members,
            status=ConversationStatus(conversation.status),
            user_uid=user_uid,
            expert_uid=expert_uid,
            order_id=str(conversation.order_id),
            version=conversation.projection_version + 1,
        )

        # One presence rule for provisioning and the backfill command: a
        # suspended, closed or no-longer-readable thread publishes nothing and
        # withdraws what it had published.
        grants = await self._grants_presence(conversation)

        try:
            await self.firebase.chat.upsert_conversation(projection)
            if grants:
                await self.firebase.presence.publish_membership(
                    str(conversation.id), members
                )
            else:
                await self.firebase.presence.revoke_membership(str(conversation.id))
        except FirebaseError as exc:
            conversation.provisioning_status = ProvisioningStatus.FAILED.value
            conversation.provisioning_error = getattr(exc, "code", "firebase_error")[:120]
            await self.session.flush()
            logger.warning(
                "chat_projection_failed",
                conversation_id=str(conversation.id),
                error_code=conversation.provisioning_error,
            )
            return False

        conversation.provisioning_status = ProvisioningStatus.ACTIVE.value
        conversation.provisioning_error = None
        conversation.projection_version = projection.version
        await self.session.flush()
        return True

    async def _grants_presence(self, conversation: ExpertConversation) -> bool:
        order = await self.session.get(ServiceOrder, conversation.order_id)
        if order is None:  # pragma: no cover - FK guarantees it
            return False
        expert = await self.session.get(Expert, conversation.expert_id)
        return grants_presence(conversation, order, expert=expert)

    async def _member_uids(
        self, conversation: ExpertConversation
    ) -> tuple[str | None, str | None]:
        rows = await self.session.execute(
            select(User.id, User.firebase_uid).where(
                User.id.in_([conversation.user_id, conversation.expert_user_id])
            )
        )
        mapping = {row[0]: row[1] for row in rows.all()}
        return mapping.get(conversation.user_id), mapping.get(
            conversation.expert_user_id
        )

    async def _reconcile(
        self, conversation: ExpertConversation, order: ServiceOrder
    ) -> None:
        """Bring the conversation's status back in line with its order.

        Cheap and idempotent, so it runs on every read: a completed order that
        crossed its grace period becomes read-only without needing a scheduler.
        """
        expected = conversation_status_for_order(order)
        current = ConversationStatus(conversation.status)

        if current is ConversationStatus.SUSPENDED:
            # Moderation outranks order state.
            return

        if current is ConversationStatus.CLOSED and conversation.closed_at:
            # Closed on purpose, by one of the parties. Order state may reopen a
            # thread that went read-only by itself, but it must not reopen one
            # somebody chose to end - otherwise the next read silently undoes
            # the close.
            if conversation.provisioning_status != ProvisioningStatus.ACTIVE.value:
                await self.provision(conversation)
            return

        if expected is not current:
            conversation.status = expected.value
            await self.session.flush()
            try:
                await self.firebase.chat.set_conversation_status(
                    str(conversation.id), expected
                )
            except FirebaseError:
                conversation.provisioning_status = ProvisioningStatus.FAILED.value
                await self.session.flush()

        if conversation.provisioning_status != ProvisioningStatus.ACTIVE.value:
            await self.provision(conversation)

    async def reconcile_pending(self, *, limit: int = 20) -> int:
        """Retry projections that failed while Firebase was unavailable."""
        rows = list(
            await self.session.scalars(
                select(ExpertConversation)
                .where(
                    ExpertConversation.provisioning_status.in_(
                        [
                            ProvisioningStatus.PENDING.value,
                            ProvisioningStatus.FAILED.value,
                        ]
                    ),
                    ExpertConversation.deleted_at.is_(None),
                )
                .limit(limit)
            )
        )
        repaired = 0
        for conversation in rows:
            if await self.provision(conversation):
                repaired += 1
        return repaired

    # ------------------------------------------------------------- access

    async def get_for_member(
        self, user: User, conversation_id: uuid.UUID
    ) -> tuple[ExpertConversation, ConversationRole, ChatPermission]:
        """Load a conversation the caller is actually part of.

        Membership is checked against the **account** on both sides. An expert
        is authorised because `expert_user_id` is them, not because they hold an
        expert profile id - a profile id is not a credential.
        """
        conversation = await self.session.scalar(
            select(ExpertConversation).where(
                ExpertConversation.id == conversation_id,
                ExpertConversation.deleted_at.is_(None),
            )
        )
        if conversation is None:
            raise NotFound("Conversation not found.")

        if user.id == conversation.user_id:
            role = ConversationRole.USER
        elif user.id == conversation.expert_user_id:
            role = ConversationRole.EXPERT
        else:
            # Not a member. A 404 rather than a 403: a wrong guess must not
            # confirm that the conversation exists.
            raise NotFound("Conversation not found.")

        order = await self.session.scalar(
            select(ServiceOrder).where(ServiceOrder.id == conversation.order_id)
        )
        if order is None:  # pragma: no cover - FK guarantees it
            raise NotFound("Order not found.")

        await self._reconcile(conversation, order)

        expert = await self.session.scalar(
            select(Expert).where(Expert.id == conversation.expert_id)
        )
        permission = permission_for(conversation, order, expert=expert)
        return conversation, role, permission

    async def list_for_user(
        self, user: User, *, limit: int = 50
    ) -> list[ExpertConversation]:
        """Every conversation the caller is in, on either side."""
        return list(
            await self.session.scalars(
                select(ExpertConversation)
                .where(
                    (ExpertConversation.user_id == user.id)
                    | (ExpertConversation.expert_user_id == user.id),
                    ExpertConversation.deleted_at.is_(None),
                )
                .order_by(ExpertConversation.updated_at.desc())
                .limit(limit)
            )
        )

    async def close(
        self,
        user: User,
        conversation_id: uuid.UUID,
        *,
        reason: str | None = None,
    ) -> ExpertConversation:
        """Close a thread to new messages. History survives."""
        conversation, _, _ = await self.get_for_member(user, conversation_id)

        conversation.status = ConversationStatus.CLOSED.value
        conversation.closed_at = datetime.now(UTC)
        conversation.close_reason = (reason or "").strip()[:120] or None
        await self.session.flush()

        try:
            await self.firebase.chat.set_conversation_status(
                str(conversation.id), ConversationStatus.CLOSED
            )
            await self.firebase.presence.revoke_membership(str(conversation.id))
        except FirebaseError:
            conversation.provisioning_status = ProvisioningStatus.FAILED.value
            await self.session.flush()

        logger.info(
            "chat_conversation_closed",
            conversation_id=str(conversation.id),
            actor_role="user" if user.id == conversation.user_id else "expert",
        )
        return conversation

    # ----------------------------------------------------------- messages

    async def send_message(
        self,
        user: User,
        conversation_id: uuid.UUID,
        *,
        text: str | None = None,
        attachment_id: uuid.UUID | None = None,
        client_message_id: str | None = None,
    ) -> tuple[ChatMessage, ExpertConversation, ConversationRole]:
        """Append a message, having checked that they may.

        The order matters: authorise, validate, check idempotency, then write.
        A duplicate check after the write would have already sent the message.
        """
        conversation, role, permission = await self.get_for_member(
            user, conversation_id
        )
        permission.require_write()

        sender_uid = (
            user.firebase_uid
            if user.firebase_uid
            else None
        )
        if not sender_uid:
            # The transport identifies senders by Firebase uid, so a message
            # from an account with no Firebase identity has nowhere to come
            # from. Said plainly rather than failing deep inside the SDK.
            raise NoFirebaseIdentity()

        attachment: MediaAttachment | None = None
        message_type = ChatMessageType.TEXT
        body: str | None = None

        if attachment_id is not None:
            attachment = await self._usable_attachment(
                conversation, user, attachment_id
            )
            message_type = (
                ChatMessageType.IMAGE
                if (attachment.verified_mime_type or attachment.mime_type).startswith(
                    "image/"
                )
                else ChatMessageType.FILE
            )
            body = sanitise_text(text) if text else None
        else:
            if not text:
                raise MessageRejected(
                    "A message needs text or an attachment.", code="empty_message"
                )
            body = sanitise_text(text)

        if client_message_id:
            existing = await self.firebase.chat.find_by_client_message_id(
                str(conversation.id), client_message_id
            )
            if existing is not None:
                # Same id, same content: the original message. Same id,
                # different content: a client bug, and silently returning the
                # wrong message would hide it.
                if existing.text != body or existing.attachment_id != (
                    str(attachment_id) if attachment_id else None
                ):
                    raise MessageConflict()
                logger.info(
                    "chat_message_idempotent_replay",
                    conversation_id=str(conversation.id),
                )
                return existing, conversation, role

        message = await self.firebase.chat.append_message(
            str(conversation.id),
            sender_uid=sender_uid,
            sender_role=role,
            message_type=message_type,
            text=body,
            attachment_id=str(attachment_id) if attachment_id else None,
            client_message_id=client_message_id,
        )

        if attachment is not None:
            attachment.message_id = message.message_id
        conversation.message_count += 1
        conversation.last_message_at = datetime.now(UTC)
        await self.session.flush()

        # The message body is deliberately absent from this line.
        logger.info(
            "chat_message_sent",
            conversation_id=str(conversation.id),
            message_id=message.message_id,
            sender_role=role.value,
            message_type=message_type.value,
            has_attachment=attachment is not None,
        )
        return message, conversation, role

    async def _usable_attachment(
        self,
        conversation: ExpertConversation,
        user: User,
        attachment_id: uuid.UUID,
    ) -> MediaAttachment:
        """An attachment may be sent only if it is really there.

        Scoped to this conversation and this uploader, so a finalised
        attachment cannot be replayed into a different thread.
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

        if not AttachmentStatus(attachment.status).is_usable:
            raise MessageRejected(
                "That attachment has not finished uploading.",
                code="attachment_not_ready",
                details={"status": attachment.status},
            )
        if attachment.message_id is not None:
            raise MessageRejected(
                "That attachment has already been sent.",
                code="attachment_already_used",
            )
        return attachment

    async def history(
        self,
        user: User,
        conversation_id: uuid.UUID,
        *,
        limit: int | None = None,
        before: str | None = None,
    ) -> tuple[list[ChatMessage], ExpertConversation]:
        """A page of history. Never the whole thread."""
        conversation, _, permission = await self.get_for_member(user, conversation_id)
        permission.require_read()

        page = min(limit or settings.chat_history_page_size, 200)
        messages = await self.firebase.chat.list_messages(
            str(conversation.id), limit=page, before=before
        )
        return messages, conversation

    async def delete_message(
        self, user: User, conversation_id: uuid.UUID, message_id: str
    ) -> ChatMessage:
        """Soft-delete one's own message.

        Only the sender. An expert cannot remove a user's message and a user
        cannot remove an expert's - a conversation somebody can edit on the
        other party's behalf is not a record of anything.
        """
        conversation, _, permission = await self.get_for_member(user, conversation_id)
        permission.require_read()

        if not user.firebase_uid:
            raise NoFirebaseIdentity()

        return await self.firebase.chat.soft_delete_message(
            str(conversation.id), message_id, sender_uid=user.firebase_uid
        )

    # ------------------------------------------------------------ helpers

    async def counterpart_user_id(
        self, conversation: ExpertConversation, sender: User
    ) -> uuid.UUID:
        """Who should be notified about a message from this sender."""
        if sender.id == conversation.user_id:
            return conversation.expert_user_id
        return conversation.user_id
