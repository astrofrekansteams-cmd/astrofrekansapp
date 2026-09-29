"""AI provider abstraction.

Everything above this line speaks in `AIRequest` / `AIResult`; nothing above
it imports an SDK. That is what makes the OpenAI implementation swappable,
the test double honest, and a future Anthropic provider a new file rather than
a refactor.

Provider errors are mapped to a small set of stable codes here, so a raw
upstream error body can never reach a client.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.core.exceptions import AppError
from app.domain.ai import GenerationMetadata, ModelTier, UseCase


# --------------------------------------------------------------- errors


class AIError(AppError):
    status_code = 502
    code = "ai_provider_unavailable"
    message = "The interpretation service is unavailable right now."


class AINotConfigured(AIError):
    status_code = 503
    code = "ai_not_configured"
    message = "The interpretation service is not configured on this server."


class AIRateLimited(AIError):
    status_code = 429
    code = "ai_rate_limited"
    message = "The interpretation service is busy. Please try again shortly."


class AITimeout(AIError):
    status_code = 504
    code = "ai_timeout"
    message = "The interpretation took too long. Please try again."


class AIInvalidOutput(AIError):
    status_code = 502
    code = "ai_invalid_output"
    message = "The interpretation could not be produced in a usable form."


class AIContextTooLarge(AIError):
    status_code = 422
    code = "ai_context_too_large"
    message = "There is too much material for one interpretation."


class AIGenerationFailed(AIError):
    status_code = 502
    code = "generation_failed"
    message = "The interpretation could not be generated."


# Errors worth retrying: transient upstream conditions only. A schema or
# prompt problem is never retried in a loop - it would burn tokens forever.
RETRYABLE: tuple[type[AIError], ...] = (AIRateLimited, AITimeout, AIError)


# -------------------------------------------------------------- payloads


@dataclass(slots=True)
class AIRequest:
    """One provider call.

    ``instructions`` is the system/developer layer. ``input`` carries the
    untrusted material (the user's message, the structured context) and is
    always presented to the model as data.
    """

    use_case: UseCase
    tier: ModelTier
    instructions: str
    input: list[dict[str, Any]]
    max_output_tokens: int
    temperature: float | None = None
    json_schema: dict[str, Any] | None = None
    schema_name: str = "astrofrekans_response"
    metadata: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float | None = None


@dataclass(slots=True)
class AIResult:
    text: str
    parsed: dict[str, Any] | None
    metadata: GenerationMetadata


@dataclass(slots=True, frozen=True)
class StreamChunk:
    """One event of our own stream contract.

    Provider event names never leave the backend: the client binds to
    ``message_start`` / ``text_delta`` / ``message_complete`` / ``metadata`` /
    ``error`` regardless of who generated the text.
    """

    type: str
    text: str | None = None
    data: dict[str, Any] | None = None


@runtime_checkable
class AIProvider(Protocol):
    name: str

    @property
    def available(self) -> bool:
        """False when the provider has no credentials; callers answer
        ``ai_not_configured`` rather than crashing."""

    async def generate_text(self, request: AIRequest) -> AIResult:
        """Free-form text."""

    async def generate_structured(self, request: AIRequest) -> AIResult:
        """JSON matching ``request.json_schema``, validated by the provider."""

    def stream_text(self, request: AIRequest) -> AsyncIterator[StreamChunk]:
        """Text as it is produced, in our stream contract."""

    async def close(self) -> None:
        """Release connections."""
