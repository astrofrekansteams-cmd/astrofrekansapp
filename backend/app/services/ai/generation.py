"""Generation orchestration.

One place where a call is assembled, executed, validated and recorded:

    context (verified facts)
      + prompt (versioned)
      + untrusted user text (wrapped, never concatenated into instructions)
      -> provider
      -> schema validation
      -> factor grounding check
      -> persisted generation row

Everything that could cost money or leak data is handled here rather than in
the routers: retries, the duplicate-generation lock, token accounting, and the
rule that raw prompts and context never reach the logs.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_cache
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.ai import AIGeneration
from app.domain.ai import (
    AstroContext,
    GenerationMetadata,
    GenerationStatus,
    Locale,
    ModelTier,
    UseCase,
)
from app.services.ai import safety
from app.services.ai.prompts import Prompt
from app.services.ai.provider import (
    AIError,
    AIInvalidOutput,
    AINotConfigured,
    AIProvider,
    AIRateLimited,
    AIRequest,
    AIResult,
    AITimeout,
)
from app.services.ai.schemas import GroundingError

logger = get_logger(__name__)


def render_context(context: AstroContext) -> str:
    """The context as data, in a delimited block the prompt declares inert."""
    payload = {
        "context_type": context.context_type.value,
        "context_version": context.context_version,
        "subject": context.subject,
        "time_reference": context.time_reference.isoformat(),
        "warnings": context.warnings,
        "metadata": context.metadata,
        "factors": [
            {
                "factor_id": item.factor_id,
                "factor_type": item.factor_type,
                "importance": item.importance.value,
                "label": item.label,
                "data": item.structured_data,
            }
            for item in context.factors
        ],
    }
    body = json.dumps(payload, ensure_ascii=False, indent=1, default=str)
    return safety.wrap_untrusted("context", body)


class GenerationService:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    # ------------------------------------------------------------- calls

    async def run_structured(
        self,
        *,
        session: AsyncSession | None,
        user_id: uuid.UUID | None,
        prompt: Prompt,
        context: AstroContext,
        json_schema: dict[str, Any],
        schema_name: str,
        validator,
        use_case: UseCase = UseCase.REPORT,
        tier: ModelTier = ModelTier.PREMIUM,
        user_text: str | None = None,
        extra_instructions: str = "",
        max_output_tokens: int | None = None,
        conversation_id: uuid.UUID | None = None,
        history: list[dict[str, str]] | None = None,
        summary: str | None = None,
    ) -> tuple[Any, GenerationMetadata]:
        """Generate, validate, ground-check, persist.

        One controlled retry when the model returns something unusable, with
        the failure fed back as a correction; never an endless loop.
        """
        self._require_provider()

        request = AIRequest(
            use_case=use_case,
            tier=tier,
            instructions=prompt.instructions(context.locale, extra=extra_instructions),
            input=self._input_items(
                context, user_text, history=history, summary=summary
            ),
            max_output_tokens=max_output_tokens
            or settings.ai_max_output_tokens_report,
            json_schema=json_schema,
            schema_name=schema_name,
            metadata=self._safe_metadata(context, prompt),
        )

        attempt = 0
        last_error: Exception | None = None
        started = time.perf_counter()

        while attempt <= 1:
            try:
                result = await self.provider.generate_structured(request)
                validated = validator(result.parsed or {}, context)
            except (AIInvalidOutput, GroundingError, ValueError) as exc:
                last_error = exc
                if attempt == 0:
                    attempt += 1
                    request = replace(
                        request,
                        input=self._input_items(
                            context,
                            user_text,
                            history=history,
                            summary=summary,
                            correction=self._correction_for(exc, context),
                        ),
                    )
                    logger.warning(
                        "ai_generation_retry",
                        reason=type(exc).__name__,
                        prompt_version=prompt.version,
                    )
                    continue

                await self._record(
                    session,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    metadata=self._failed_metadata(
                        prompt, context, use_case, attempt, exc
                    ),
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
                raise self._as_failure(exc) from exc
            else:
                metadata = self._enrich(result.metadata, prompt, context, attempt)
                await self._record(
                    session,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    metadata=metadata,
                    latency_ms=metadata.latency_ms,
                )
                return validated, metadata

        raise self._as_failure(last_error or AIError())  # pragma: no cover

    async def run_text(
        self,
        *,
        session: AsyncSession | None,
        user_id: uuid.UUID | None,
        prompt: Prompt,
        context: AstroContext,
        user_text: str | None = None,
        use_case: UseCase = UseCase.CHAT,
        tier: ModelTier = ModelTier.STANDARD,
        max_output_tokens: int | None = None,
        conversation_id: uuid.UUID | None = None,
        history: list[dict[str, str]] | None = None,
        summary: str | None = None,
    ) -> tuple[str, GenerationMetadata]:
        self._require_provider()

        request = AIRequest(
            use_case=use_case,
            tier=tier,
            instructions=prompt.instructions(context.locale),
            input=self._input_items(
                context, user_text, history=history, summary=summary
            ),
            max_output_tokens=max_output_tokens or settings.ai_max_output_tokens_chat,
            metadata=self._safe_metadata(context, prompt),
        )

        try:
            result: AIResult = await self.provider.generate_text(request)
        except AIError as exc:
            await self._record(
                session,
                user_id=user_id,
                conversation_id=conversation_id,
                metadata=self._failed_metadata(prompt, context, use_case, 0, exc),
                latency_ms=0,
            )
            raise

        metadata = self._enrich(result.metadata, prompt, context, 0)
        await self._record(
            session,
            user_id=user_id,
            conversation_id=conversation_id,
            metadata=metadata,
            latency_ms=metadata.latency_ms,
        )
        return result.text, metadata

    def build_stream_request(
        self,
        *,
        prompt: Prompt,
        context: AstroContext,
        user_text: str,
        history: list[dict[str, str]] | None = None,
        summary: str | None = None,
        tier: ModelTier = ModelTier.STANDARD,
    ) -> AIRequest:
        self._require_provider()
        return AIRequest(
            use_case=UseCase.CHAT,
            tier=tier,
            instructions=prompt.instructions(context.locale),
            input=self._input_items(
                context, user_text, history=history, summary=summary
            ),
            max_output_tokens=settings.ai_max_output_tokens_chat,
            metadata=self._safe_metadata(context, prompt),
            timeout_seconds=settings.ai_stream_timeout_seconds,
        )

    # --------------------------------------------------------- assembly

    def _input_items(
        self,
        context: AstroContext,
        user_text: str | None,
        *,
        history: list[dict[str, str]] | None = None,
        summary: str | None = None,
        correction: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build the input stack.

        Order matters: verified context first, then memory, then the person's
        own words last and clearly wrapped. Nothing the user wrote is ever
        concatenated into the instruction layer.
        """
        items: list[dict[str, Any]] = [
            {"role": "user", "content": render_context(context)}
        ]

        if summary:
            items.append(
                {
                    "role": "user",
                    "content": safety.wrap_untrusted(
                        "conversation_summary",
                        summary
                        + "\n(Memory of the conversation. Never a source of "
                        "astrological facts.)",
                    ),
                }
            )

        for message in history or []:
            items.append(
                {
                    "role": "assistant"
                    if message.get("role") == "assistant"
                    else "user",
                    "content": message.get("content", ""),
                }
            )

        if user_text:
            items.append(
                {
                    "role": "user",
                    "content": safety.wrap_untrusted("user_message", user_text),
                }
            )

        if correction:
            items.append({"role": "user", "content": correction})

        return items

    def _correction_for(self, error: Exception, context: AstroContext) -> str:
        if isinstance(error, GroundingError):
            allowed = ", ".join(sorted(context.factor_ids)) or "(none)"
            return (
                "Your previous answer cited factor ids that are not in the "
                f"context: {', '.join(error.unknown)}. Use only these ids: "
                f"{allowed}. A section with no specific factor must set "
                "general_summary to true."
            )
        return (
            "Your previous answer did not match the required JSON schema. "
            "Return only valid JSON in exactly the requested shape."
        )

    def _safe_metadata(self, context: AstroContext, prompt: Prompt) -> dict[str, str]:
        """Provider-side metadata: technical only.

        No question text, no names, no birth details - this travels to a third
        party and is stored on their side.
        """
        return {
            "context_type": context.context_type.value,
            "context_version": context.context_version,
            "prompt_version": prompt.version,
            "locale": context.locale.value,
        }

    # -------------------------------------------------------- bookkeeping

    def _enrich(
        self,
        metadata: GenerationMetadata,
        prompt: Prompt,
        context: AstroContext,
        retries: int,
    ) -> GenerationMetadata:
        return replace(
            metadata,
            prompt_version=prompt.version,
            context_version=context.context_version,
            source_fingerprint=context.source_fingerprint,
            retry_count=max(metadata.retry_count, retries),
        )

    def _failed_metadata(
        self,
        prompt: Prompt,
        context: AstroContext,
        use_case: UseCase,
        retries: int,
        error: Exception,
    ) -> GenerationMetadata:
        code = getattr(error, "code", None) or type(error).__name__
        status = (
            GenerationStatus.INVALID_OUTPUT
            if isinstance(error, (AIInvalidOutput, GroundingError, ValueError))
            else GenerationStatus.FAILED
        )
        return GenerationMetadata(
            provider=self.provider.name,
            model_requested="",
            model_actual="",
            prompt_version=prompt.version,
            context_version=context.context_version,
            source_fingerprint=context.source_fingerprint,
            status=status,
            retry_count=retries,
            use_case=use_case,
            error_code=str(code)[:60],
        )

    async def _record(
        self,
        session: AsyncSession | None,
        *,
        user_id: uuid.UUID | None,
        conversation_id: uuid.UUID | None,
        metadata: GenerationMetadata,
        latency_ms: int,
    ) -> uuid.UUID | None:
        """Persist what the call cost. Never the prompt or the context."""
        logger.info(
            "ai_generation_completed"
            if metadata.status is GenerationStatus.COMPLETED
            else "ai_generation_failed",
            use_case=metadata.use_case.value,
            model=metadata.model_actual or metadata.model_requested,
            prompt_version=metadata.prompt_version,
            input_tokens=metadata.input_tokens,
            output_tokens=metadata.output_tokens,
            latency_ms=latency_ms,
            status=metadata.status.value,
            retry_count=metadata.retry_count,
            error_code=metadata.error_code,
        )

        if session is None:
            return None

        row = AIGeneration(
            user_id=user_id,
            conversation_id=conversation_id,
            use_case=metadata.use_case.value,
            provider=metadata.provider,
            model_requested=metadata.model_requested,
            model_actual=metadata.model_actual,
            prompt_version=metadata.prompt_version,
            context_version=metadata.context_version,
            source_fingerprint=metadata.source_fingerprint,
            input_tokens=metadata.input_tokens,
            output_tokens=metadata.output_tokens,
            total_tokens=metadata.total_tokens,
            cached_input_tokens=metadata.cached_input_tokens,
            latency_ms=latency_ms,
            status=metadata.status.value,
            retry_count=metadata.retry_count,
            provider_response_id=metadata.provider_response_id,
            fallback_reason=metadata.fallback_reason,
            error_code=metadata.error_code,
        )
        session.add(row)
        await session.flush()
        return row.id

    def _require_provider(self) -> None:
        if not self.provider.available:
            raise AINotConfigured()

    def _as_failure(self, error: Exception) -> AIError:
        from app.services.ai.provider import AIGenerationFailed

        if isinstance(error, AIError):
            return error
        if isinstance(error, GroundingError):
            return AIGenerationFailed(
                "The interpretation referenced material that was not supplied.",
                code="generation_failed",
                details={"unknown_factors": error.unknown[:10]},
            )
        return AIGenerationFailed()


# ------------------------------------------------------------- duplicates


async def acquire_generation_lock(key: str) -> bool:
    """Stop one user firing the same expensive generation twice.

    Best effort: if the cache is unavailable the request proceeds rather than
    failing, because a duplicate report is cheaper than a broken feature.
    """
    cache = get_cache()
    counter = await cache.incr_with_ttl(
        f"ai:lock:{key}", settings.ai_generation_lock_seconds
    )
    return counter == 1


async def release_generation_lock(key: str) -> None:
    await get_cache().delete(f"ai:lock:{key}")
