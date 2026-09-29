"""Astro AI chat, buffered and streamed.

The flow for one turn:

    message -> intent (rule-first) -> context (verified engine facts)
            -> prompt + memory -> provider -> grounded answer -> stored turn

The user's message is untrusted input throughout: it is wrapped, placed below
the instruction layer, and never allowed to change the rules. The model is
given no tools - no web, no shell, no database - so the only material it can
draw on is the context the backend built.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.ai import AIConversation
from app.db.models.user import User
from app.domain.ai import (
    CompletionStatus,
    ContextType,
    GenerationMetadata,
    Locale,
    MessageRole,
    ModelTier,
    UseCase,
)
from app.services.ai import prompts, safety
from app.services.ai.influences import influences
from app.services.ai.context.intent import IntentResult, classify
from app.services.ai.conversations import ConversationService
from app.services.ai.generation import GenerationService
from app.services.ai.provider import AIError, StreamChunk
from app.services.ai.schemas import CHAT_SCHEMA, filter_known_factor_ids, validate_chat
from app.services.ai.sources import ResolvedSource, SourceResolver

logger = get_logger(__name__)

# Intents that also imply a life-area focus when the context is the natal
# chart, so "career" pulls the Midheaven and tenth house forward.
INTENT_FOCUS = {
    "career": "career",
    "money": "money",
    "love": "love",
    "relationship": "relationship",
}


class ChatService:
    def __init__(
        self,
        session: AsyncSession,
        conversations: ConversationService,
        resolver: SourceResolver,
        generation: GenerationService,
    ) -> None:
        self.session = session
        self.conversations = conversations
        self.resolver = resolver
        self.generation = generation

    # ----------------------------------------------------------- shared

    async def prepare(
        self,
        user: User,
        conversation: AIConversation,
        *,
        message: str,
        locale: Locale,
        context_mode: ContextType | None = None,
    ) -> tuple[IntentResult, ResolvedSource, list[dict[str, str]], str | None]:
        """Route, authorise and assemble everything one turn needs."""
        intent = classify(message, explicit=context_mode)
        focus = INTENT_FOCUS.get(intent.intent.value)

        source = await self.resolver.for_context_type(
            user,
            context_type=intent.context_type,
            locale=locale,
            budget=settings.ai_chat_context_budget,
            focus=focus,
        )
        history = await self.conversations.recent_history(conversation)
        return intent, source, history, conversation.summary

    # --------------------------------------------------------- buffered

    async def answer(
        self,
        user: User,
        conversation: AIConversation,
        *,
        message: str,
        locale: Locale,
        context_mode: ContextType | None = None,
    ) -> dict:
        intent, source, history, summary = await self.prepare(
            user,
            conversation,
            message=message,
            locale=locale,
            context_mode=context_mode,
        )

        await self.conversations.add_message(
            conversation, role=MessageRole.USER, content=message
        )

        answer, metadata = await self.generation.run_structured(
            session=self.session,
            user_id=user.id,
            prompt=prompts.CHAT,
            context=source.context,
            json_schema=CHAT_SCHEMA,
            schema_name="astrofrekans_chat_answer",
            validator=validate_chat,
            use_case=UseCase.CHAT,
            tier=ModelTier.STANDARD,
            user_text=message,
            max_output_tokens=settings.ai_max_output_tokens_chat,
            conversation_id=conversation.id,
            # Memory: the recent turns verbatim plus the rolling summary. The
            # streamed path always carried these; the buffered one did not,
            # which made a long conversation forget itself the moment the
            # client stopped streaming.
            history=history,
            summary=summary,
        )

        findings = safety.scan_output(answer.answer)
        if findings:
            logger.warning("ai_safety_violation", surface="chat", findings=findings)
            raise AIError(
                "The answer could not be produced safely.",
                code="generation_failed",
                details={"findings": findings},
            )

        await self.conversations.add_message(
            conversation,
            role=MessageRole.ASSISTANT,
            content=answer.answer,
            context_type=source.context.context_type,
            source_factor_ids=answer.source_factor_ids,
        )

        await self.conversations.ensure_title(
            conversation,
            first_message=message,
            generation=self.generation,
            user_id=user.id,
        )
        if self.conversations.needs_summary(conversation):
            await self.conversations.refresh_summary(
                conversation, generation=self.generation, user_id=user.id
            )

        return {
            "conversation_id": conversation.id,
            "answer": answer.answer,
            "context_type": source.context.context_type,
            "intent": intent.intent,
            "source_factor_ids": answer.source_factor_ids,
            "context_note": answer.context_note,
            "warnings": source.context.warnings,
            "influences": influences(
                source.context,
                source.context.locale.value,
                cited=answer.source_factor_ids,
            ),
            "metadata": metadata,
        }

    # ---------------------------------------------------------- stream

    async def stream(
        self,
        user: User,
        conversation: AIConversation,
        *,
        message: str,
        locale: Locale,
        context_mode: ContextType | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a turn in our own event contract.

        The turn is persisted from whatever was produced before the stream
        ended, so a disconnect mid-answer leaves a real conversation rather
        than a gap.
        """
        intent, source, history, summary = await self.prepare(
            user,
            conversation,
            message=message,
            locale=locale,
            context_mode=context_mode,
        )
        await self.conversations.add_message(
            conversation, role=MessageRole.USER, content=message
        )

        request = self.generation.build_stream_request(
            prompt=prompts.CHAT,
            context=source.context,
            user_text=message,
            history=history,
            summary=summary,
        )

        collected: list[str] = []
        metadata_payload: dict = {}
        cancelled = False
        failed = False

        try:
            async for chunk in self.generation.provider.stream_text(request):
                if chunk.type == "text_delta" and chunk.text:
                    collected.append(chunk.text)
                    yield chunk
                elif chunk.type == "message_start":
                    yield StreamChunk(
                        type="message_start",
                        data={
                            "conversation_id": str(conversation.id),
                            "context_type": source.context.context_type.value,
                            "intent": intent.intent.value,
                        },
                    )
                elif chunk.type == "message_complete":
                    metadata_payload = chunk.data or {}
                elif chunk.type == "metadata":
                    yield chunk
        except GeneratorExit:
            # The client went away: stop generating rather than paying for
            # text nobody will read.
            cancelled = True
            logger.info("ai_stream_cancelled", conversation_id=str(conversation.id))
            raise
        except AIError as exc:
            failed = True
            yield StreamChunk(
                type="error",
                data={
                    "code": getattr(exc, "code", "ai_provider_unavailable"),
                    "message": exc.message,
                },
            )
            return
        finally:
            text = "".join(collected).strip()
            if text:
                findings = safety.scan_output(text)
                # A dropped connection or an upstream failure leaves real text
                # the user partly saw. It is kept - deleting it would make the
                # thread lie about what happened - but it is recorded as
                # unfinished, so nothing downstream treats it as a full answer.
                status = CompletionStatus.COMPLETED
                if cancelled:
                    status = CompletionStatus.CANCELLED
                elif failed or not metadata_payload:
                    status = CompletionStatus.PARTIAL

                await self.conversations.add_message(
                    conversation,
                    role=MessageRole.ASSISTANT,
                    content=text,
                    context_type=source.context.context_type,
                    source_factor_ids=[],
                    completion_status=status,
                )
                if findings:
                    logger.warning(
                        "ai_safety_violation", surface="stream", findings=findings
                    )

        if cancelled:
            return

        yield StreamChunk(
            type="metadata",
            data={
                "context_type": source.context.context_type.value,
                "intent": intent.intent.value,
                "warnings": source.context.warnings,
                "available_factor_ids": sorted(source.context.factor_ids)[:20],
                "influences": influences(source.context, source.context.locale.value),
            },
        )
        yield StreamChunk(
            type="message_complete",
            data={
                "conversation_id": str(conversation.id),
                **{
                    key: value
                    for key, value in metadata_payload.items()
                    if key
                    in (
                        "model",
                        "input_tokens",
                        "output_tokens",
                        "latency_ms",
                    )
                },
            },
        )


def to_sse(chunk: StreamChunk) -> str:
    """Server-Sent Events framing for our stream contract."""
    payload: dict = {"type": chunk.type}
    if chunk.text is not None:
        payload["text"] = chunk.text
    if chunk.data is not None:
        payload["data"] = chunk.data
    return f"event: {chunk.type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
