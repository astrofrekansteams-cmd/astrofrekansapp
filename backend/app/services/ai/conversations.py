"""Conversation storage and memory.

Memory is two layers, never the whole transcript: the last N turns verbatim,
plus a rolling summary refreshed with a cheap model. Sending an entire history
on every turn costs more each time and buys nothing.

The summary records *what the person is dealing with and how they like to be
spoken to*. It never records astrological facts: a remembered "my Venus is in
Aries" must never become a fact the next answer builds on. Chart material is
re-read from the engine every time.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFound
from app.core.logging import get_logger
from app.db.models.ai import AIConversation, AIMessage
from app.domain.ai import (
    AstroContext,
    CompletionStatus,
    ContextType,
    Locale,
    MessageRole,
    ModelTier,
    UseCase,
)
from app.services.ai import prompts
from app.services.ai.generation import GenerationService
from app.services.ai.provider import AIError

logger = get_logger(__name__)


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------- CRUD

    async def create(
        self, *, user_id: uuid.UUID, locale: Locale, title: str | None = None
    ) -> AIConversation:
        conversation = AIConversation(
            user_id=user_id, locale=locale.value, title=title
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get(
        self, *, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> AIConversation:
        conversation = await self.session.scalar(
            select(AIConversation).where(
                AIConversation.id == conversation_id,
                AIConversation.user_id == user_id,
            )
        )
        if conversation is None:
            # Another user's conversation is simply not found, never a 403
            # that confirms it exists.
            raise NotFound("Conversation not found.")
        return conversation

    async def list(
        self,
        *,
        user_id: uuid.UUID,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[AIConversation]:
        statement = (
            select(AIConversation)
            .where(AIConversation.user_id == user_id)
            .order_by(AIConversation.updated_at.desc())
            .limit(limit)
        )
        if not include_archived:
            statement = statement.where(AIConversation.archived_at.is_(None))
        return list(await self.session.scalars(statement))

    async def archive(
        self, *, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> AIConversation:
        conversation = await self.get(
            user_id=user_id, conversation_id=conversation_id
        )
        conversation.archived_at = datetime.now(UTC)
        await self.session.flush()
        return conversation

    async def messages(
        self, *, conversation_id: uuid.UUID, limit: int = 200
    ) -> list[AIMessage]:
        result = await self.session.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at)
            .limit(limit)
        )
        return list(result)

    async def add_message(
        self,
        conversation: AIConversation,
        *,
        role: MessageRole,
        content: str,
        generation_id: uuid.UUID | None = None,
        context_type: ContextType | None = None,
        source_factor_ids: list[str] | None = None,
        completion_status: CompletionStatus = CompletionStatus.COMPLETED,
    ) -> AIMessage:
        message = AIMessage(
            conversation_id=conversation.id,
            role=role.value,
            content=content,
            generation_id=generation_id,
            context_type=context_type.value if context_type else None,
            source_factor_ids={"ids": source_factor_ids or []},
            completion_status=completion_status.value,
        )
        self.session.add(message)
        conversation.message_count += 1
        conversation.updated_at = datetime.now(UTC)
        await self.session.flush()
        return message

    # ----------------------------------------------------------- memory

    async def recent_history(
        self, conversation: AIConversation, *, window: int | None = None
    ) -> list[dict[str, str]]:
        """The last few turns, oldest first, as provider input items."""
        size = window or settings.ai_recent_message_window
        result = await self.session.scalars(
            select(AIMessage)
            .where(
                AIMessage.conversation_id == conversation.id,
                AIMessage.role.in_(
                    [MessageRole.USER.value, MessageRole.ASSISTANT.value]
                ),
            )
            .order_by(AIMessage.created_at.desc())
            .limit(size)
        )
        rows = list(result)[::-1]
        return [
            {
                "role": row.role,
                "content": self._history_content(row),
            }
            for row in rows
        ]

    @staticmethod
    def _history_content(row: AIMessage) -> str:
        """What a stored turn looks like when it is replayed to the model.

        An interrupted answer is included - dropping it would leave the thread
        incoherent, with a question and no reply - but it is labelled, so the
        model treats it as something it began rather than something it said.
        """
        status = row.completion_status
        if status == CompletionStatus.COMPLETED.value:
            return row.content
        return f"[unfinished answer, {status}] {row.content}"

    def needs_summary(self, conversation: AIConversation) -> bool:
        unsummarised = (
            conversation.message_count - conversation.summarised_message_count
        )
        return unsummarised >= settings.ai_summary_trigger_messages

    async def refresh_summary(
        self,
        conversation: AIConversation,
        *,
        generation: GenerationService,
        user_id: uuid.UUID,
    ) -> str | None:
        """Rebuild the rolling summary with the cheap model.

        Failure here is not a user-facing error: a stale summary is a minor
        loss of memory, not a broken conversation.
        """
        history = await self.recent_history(
            conversation, window=settings.ai_summary_trigger_messages * 2
        )
        if not history:
            return conversation.summary

        transcript = "\n".join(
            f"{item['role']}: {item['content']}" for item in history
        )
        context = AstroContext(
            context_type=ContextType.GENERAL_ASTRO_CHAT,
            subject={"kind": "conversation_summary"},
            time_reference=datetime.now(UTC),
            locale=Locale(conversation.locale),
            factors=[],
            warnings=[
                "This is conversation memory. It must not contain "
                "astrological placements, dates or scores."
            ],
            context_version="conversation_memory_v1",
            source_fingerprint=str(conversation.id),
        )

        try:
            text, _ = await generation.run_text(
                session=self.session,
                user_id=user_id,
                prompt=prompts.CONVERSATION_SUMMARY,
                context=context,
                user_text=transcript,
                use_case=UseCase.SUMMARY,
                tier=ModelTier.LOW_COST,
                max_output_tokens=settings.ai_max_output_tokens_summary,
                conversation_id=conversation.id,
            )
        except AIError as exc:
            logger.warning("ai_summary_failed", error_code=getattr(exc, "code", None))
            return conversation.summary

        conversation.summary = text.strip()[:2000]
        conversation.summary_version += 1
        conversation.summarised_message_count = conversation.message_count
        await self.session.flush()
        return conversation.summary

    async def ensure_title(
        self,
        conversation: AIConversation,
        *,
        first_message: str,
        generation: GenerationService,
        user_id: uuid.UUID,
    ) -> None:
        """Name a new conversation from its opening message."""
        if conversation.title:
            return

        context = AstroContext(
            context_type=ContextType.GENERAL_ASTRO_CHAT,
            subject={"kind": "conversation_title"},
            time_reference=datetime.now(UTC),
            locale=Locale(conversation.locale),
            context_version="conversation_title_v1",
            source_fingerprint=str(conversation.id),
        )
        try:
            title, _ = await generation.run_text(
                session=self.session,
                user_id=user_id,
                prompt=prompts.CONVERSATION_TITLE,
                context=context,
                user_text=first_message,
                use_case=UseCase.TITLE,
                tier=ModelTier.LOW_COST,
                max_output_tokens=40,
                conversation_id=conversation.id,
            )
        except AIError:
            # A conversation without a title is perfectly usable.
            return

        conversation.title = title.strip().strip('"')[:160] or None
        await self.session.flush()
