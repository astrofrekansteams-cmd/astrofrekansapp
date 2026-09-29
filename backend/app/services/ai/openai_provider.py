"""OpenAI provider, built on the Responses API.

Notes that matter:

* **Responses API**, not Chat Completions - `client.responses.create(...)` with
  `instructions` (the trusted layer) and `input` (everything else).
* **Structured Outputs** with `text={"format": {"type": "json_schema",
  "strict": True, ...}}`, so a report is schema-valid before it is ever
  stored. An invalid response is retried once and then fails loudly.
* **Streaming** is adapted into our own `StreamChunk` contract; OpenAI event
  names never reach the client.
* The API key lives only in the server environment. It is never logged, never
  returned, and a missing key degrades the AI endpoints instead of crashing
  the app.
* No tools are ever passed: no web search, no file search, no code execution.
  The model interprets the context it is given and nothing else.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.ai import GenerationMetadata, GenerationStatus
from app.services.ai.provider import (
    AIContextTooLarge,
    AIError,
    AIInvalidOutput,
    AINotConfigured,
    AIRateLimited,
    AIRequest,
    AIResult,
    AITimeout,
    StreamChunk,
)
from app.services.ai.router import ModelChoice, get_model_router

logger = get_logger(__name__)

PROVIDER_NAME = "openai"


class OpenAIProvider:
    name = PROVIDER_NAME

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.openai_api_key
        self._client: Any | None = None

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def _ensure_client(self):  # noqa: ANN202 - returns AsyncOpenAI
        if not self.available:
            raise AINotConfigured()
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=settings.openai_base_url or None,
                organization=settings.openai_organization or None,
                max_retries=0,  # retries are ours, with our own policy
                timeout=settings.ai_request_timeout_seconds,
            )
        return self._client

    # ------------------------------------------------------------- calls

    async def generate_text(self, request: AIRequest) -> AIResult:
        return await self._create(request, structured=False)

    async def generate_structured(self, request: AIRequest) -> AIResult:
        if request.json_schema is None:
            raise AIInvalidOutput(
                "A structured generation needs a schema.", code="ai_invalid_output"
            )
        return await self._create(request, structured=True)

    async def _create(self, request: AIRequest, *, structured: bool) -> AIResult:
        import json

        client = self._ensure_client()
        router = get_model_router()
        choice = router.choose(request.use_case, tier=request.tier)

        attempt = 0
        last_error: Exception | None = None

        while True:
            payload: dict[str, Any] = {
                "model": choice.model,
                "instructions": request.instructions,
                "input": request.input,
                "max_output_tokens": request.max_output_tokens,
                # Metadata is technical only: never a question, a name or a
                # birth detail.
                "metadata": request.metadata,
                "store": False,
            }
            if request.temperature is not None:
                payload["temperature"] = request.temperature
            if structured:
                payload["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": request.schema_name,
                        "schema": request.json_schema,
                        "strict": True,
                    }
                }

            started = time.perf_counter()
            try:
                response = await client.responses.create(
                    **payload,
                    timeout=request.timeout_seconds
                    or settings.ai_request_timeout_seconds,
                )
            except Exception as exc:  # noqa: BLE001 - mapped below
                mapped = self._map_error(exc)
                last_error = mapped
                fallback = (
                    router.fallback(
                        choice,
                        reason=type(mapped).__name__,
                        use_case=request.use_case,
                    )
                    if isinstance(mapped, (AIError,))
                    and not isinstance(mapped, AIRateLimited)
                    else None
                )
                if fallback is not None and attempt == 0:
                    logger.warning(
                        "ai_model_fallback",
                        requested=choice.requested_model,
                        actual=fallback.model,
                        reason=fallback.fallback_reason,
                    )
                    choice = fallback
                    attempt += 1
                    continue
                if attempt < settings.ai_max_retries and isinstance(
                    mapped, (AIRateLimited, AITimeout)
                ):
                    attempt += 1
                    await self._backoff(attempt)
                    continue
                raise mapped from exc

            latency_ms = int((time.perf_counter() - started) * 1000)
            text = (getattr(response, "output_text", "") or "").strip()

            parsed: dict[str, Any] | None = None
            if structured:
                try:
                    parsed = json.loads(text) if text else None
                except json.JSONDecodeError:
                    parsed = None
                if parsed is None:
                    # One controlled retry, then fail. Never an endless loop.
                    if attempt < 1:
                        attempt += 1
                        logger.warning("ai_structured_retry", model=choice.model)
                        continue
                    raise AIInvalidOutput()

            return AIResult(
                text=text,
                parsed=parsed,
                metadata=self._metadata(
                    response,
                    request=request,
                    choice=choice,
                    latency_ms=latency_ms,
                    retry_count=attempt,
                ),
            )

        raise last_error or AIError()  # pragma: no cover - loop always returns

    # --------------------------------------------------------- streaming

    async def stream_text(self, request: AIRequest) -> AsyncIterator[StreamChunk]:
        """Adapt the provider's events into our own contract."""
        client = self._ensure_client()
        choice = get_model_router().choose(request.use_case, tier=request.tier)
        started = time.perf_counter()

        payload: dict[str, Any] = {
            "model": choice.model,
            "instructions": request.instructions,
            "input": request.input,
            "max_output_tokens": request.max_output_tokens,
            "metadata": request.metadata,
            "store": False,
            "stream": True,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        try:
            stream = await client.responses.create(
                **payload,
                timeout=request.timeout_seconds or settings.ai_stream_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            raise self._map_error(exc) from exc

        yield StreamChunk(type="message_start", data={"model": choice.model})

        final_response: Any | None = None
        try:
            async for event in stream:
                event_type = getattr(event, "type", "")
                if event_type == "response.output_text.delta":
                    yield StreamChunk(type="text_delta", text=event.delta)
                elif event_type == "response.completed":
                    final_response = event.response
                elif event_type in ("response.failed", "error"):
                    raise AIError()
                elif event_type == "response.incomplete":
                    # Ran into a limit: the text so far is real, so the stream
                    # closes cleanly with a reason rather than an error.
                    final_response = getattr(event, "response", None)
                    yield StreamChunk(
                        type="metadata", data={"incomplete": True}
                    )
        except AIError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise self._map_error(exc) from exc
        finally:
            close = getattr(stream, "close", None)
            if close is not None:
                try:
                    await close()
                except Exception:  # noqa: BLE001 - cancellation is best effort
                    pass

        latency_ms = int((time.perf_counter() - started) * 1000)
        metadata = self._metadata(
            final_response,
            request=request,
            choice=choice,
            latency_ms=latency_ms,
            retry_count=0,
        )
        yield StreamChunk(
            type="message_complete",
            data={
                "model": metadata.model_actual,
                "input_tokens": metadata.input_tokens,
                "output_tokens": metadata.output_tokens,
                "latency_ms": metadata.latency_ms,
                "provider_response_id": metadata.provider_response_id,
            },
        )

    # ----------------------------------------------------------- helpers

    def _metadata(
        self,
        response: Any | None,
        *,
        request: AIRequest,
        choice: ModelChoice,
        latency_ms: int,
        retry_count: int,
    ) -> GenerationMetadata:
        usage = getattr(response, "usage", None) if response is not None else None
        cached = 0
        if usage is not None:
            details = getattr(usage, "input_tokens_details", None)
            cached = int(getattr(details, "cached_tokens", 0) or 0)

        return GenerationMetadata(
            provider=self.name,
            model_requested=choice.requested_model,
            model_actual=(
                getattr(response, "model", None) or choice.model
                if response is not None
                else choice.model
            ),
            prompt_version="",  # filled in by the generation service
            context_version="",
            source_fingerprint="",
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
            cached_input_tokens=cached,
            latency_ms=latency_ms,
            status=GenerationStatus.COMPLETED,
            retry_count=retry_count,
            provider_response_id=getattr(response, "id", None)
            if response is not None
            else None,
            fallback_reason=choice.fallback_reason,
            use_case=request.use_case,
        )

    async def _backoff(self, attempt: int) -> None:
        import asyncio
        import random

        delay = settings.ai_retry_base_delay_seconds * (2 ** (attempt - 1))
        # Jitter, so a burst of failures does not retry in lockstep.
        await asyncio.sleep(delay * (0.5 + random.random() / 2))

    def _map_error(self, exc: Exception) -> AIError:
        """Upstream errors become our own stable codes.

        The raw provider body is deliberately dropped: it can contain request
        echoes, and it is not something a client should ever parse.
        """
        name = type(exc).__name__
        status = getattr(exc, "status_code", None)

        if name in ("APITimeoutError", "TimeoutError", "ReadTimeout"):
            return AITimeout()
        if name == "RateLimitError" or status == 429:
            return AIRateLimited()
        if name == "AuthenticationError" or status in (401, 403):
            logger.error("ai_authentication_failed")
            return AINotConfigured(
                "The interpretation service rejected the server credentials.",
                code="ai_not_configured",
            )
        if status == 400 and "context" in str(exc).lower():
            return AIContextTooLarge()
        if name == "BadRequestError" or status == 400:
            return AIInvalidOutput()

        logger.warning("ai_provider_error", error_type=name, status=status)
        return AIError()

    async def close(self) -> None:
        if self._client is not None:
            close = getattr(self._client, "close", None)
            if close is not None:
                await close()
            self._client = None
