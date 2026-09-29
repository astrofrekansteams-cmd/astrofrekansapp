"""Deterministic test double.

The suite must never call a real model: tests would cost money, need a key,
and - because models are non-deterministic - would assert on text instead of
on the things that actually matter (schema validity, factor grounding,
authorisation, safety invariants).

So this provider produces *structurally correct* output derived from the
request, and can be told to misbehave on purpose: emit an unknown factor id,
return invalid JSON, time out, rate-limit. Those are the cases worth testing.

It is refused in production by ``assert_production_ready``.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from app.domain.ai import GenerationMetadata, GenerationStatus
from app.services.ai.provider import (
    AIInvalidOutput,
    AIRateLimited,
    AIRequest,
    AIResult,
    AITimeout,
    StreamChunk,
)
from app.services.ai.router import get_model_router

PROVIDER_NAME = "fake"


class FakeAIProvider:
    """Deterministic, offline, and deliberately controllable."""

    name = PROVIDER_NAME

    def __init__(self) -> None:
        # Test knobs.
        self.fail_with: Exception | None = None
        self.invalid_json_times = 0
        self.hallucinate_factor: str | None = None
        self.custom_payload: dict[str, Any] | None = None
        self.custom_text: str | None = None
        self.calls: list[AIRequest] = []

    @property
    def available(self) -> bool:
        return True

    # ------------------------------------------------------------- calls

    async def generate_text(self, request: AIRequest) -> AIResult:
        self.calls.append(request)
        self._maybe_fail()
        text = self.custom_text or self._text_for(request)
        return AIResult(text=text, parsed=None, metadata=self._metadata(request))

    async def generate_structured(self, request: AIRequest) -> AIResult:
        self.calls.append(request)
        self._maybe_fail()

        if self.invalid_json_times > 0:
            self.invalid_json_times -= 1
            raise AIInvalidOutput()

        payload = self.custom_payload or self._payload_for(request)
        return AIResult(
            text=json.dumps(payload, ensure_ascii=False),
            parsed=payload,
            metadata=self._metadata(request),
        )

    async def stream_text(self, request: AIRequest) -> AsyncIterator[StreamChunk]:
        self.calls.append(request)
        self._maybe_fail()

        model = get_model_router().choose(request.use_case, tier=request.tier).model
        yield StreamChunk(type="message_start", data={"model": model})

        text = self.custom_text or self._text_for(request)
        for word in text.split(" "):
            yield StreamChunk(type="text_delta", text=word + " ")

        yield StreamChunk(
            type="message_complete",
            data={
                "model": model,
                "input_tokens": 100,
                "output_tokens": len(text.split()),
                "latency_ms": 1,
                "provider_response_id": "fake-response",
            },
        )

    # ----------------------------------------------------------- content

    def _factor_ids(self, request: AIRequest) -> list[str]:
        """Pull the ids the context actually offered.

        The fake grounds its answer in the real context, which is what makes
        the grounding tests meaningful: if the builder did not supply an id,
        the fake cannot cite it either - unless a test asks it to.
        """
        ids: list[str] = []
        for item in request.input:
            content = item.get("content")
            if isinstance(content, str) and '"factor_id"' in content:
                try:
                    for line in content.splitlines():
                        marker = '"factor_id": "'
                        if marker in line:
                            ids.append(line.split(marker, 1)[1].split('"', 1)[0])
                except Exception:  # noqa: BLE001 - best effort in a test double
                    pass
        ids = ids[:8]
        if self.hallucinate_factor:
            # Near the front, so it lands in a cited section rather than
            # falling off the end and quietly passing the grounding check.
            ids.insert(min(1, len(ids)), self.hallucinate_factor)
        return ids

    def _text_for(self, request: AIRequest) -> str:
        return (
            "This is a deterministic test interpretation. The chart material "
            "supplied by the engine is described here in plain language, "
            "without claiming any settled outcome."
        )

    def _payload_for(self, request: AIRequest) -> dict[str, Any]:
        ids = self._factor_ids(request)
        first = ids[:1] or []

        # The double answers in whatever shape was asked for; a chat answer
        # and a report are different schemas and must not be confused.
        properties = (request.json_schema or {}).get("properties", {})
        if "answer" in properties:
            return {
                "answer": self._text_for(request),
                "source_factor_ids": ids[:3],
                "context_note": None,
            }

        return {
            "title": "Test Report",
            "summary": (
                "A deterministic summary produced by the fake provider for "
                "testing. It makes no predictions."
            ),
            "sections": [
                {
                    "key": "overview",
                    "title": "Overview",
                    "body": (
                        "Structured section body grounded in the supplied "
                        "context."
                    ),
                    "factor_ids": first,
                    "general_summary": not first,
                },
                {
                    "key": "detail",
                    "title": "Detail",
                    "body": "A second section, also grounded in the context.",
                    "factor_ids": ids[1:3],
                    "general_summary": len(ids) < 2,
                },
            ],
            "interpretation_scope": (
                "Astrological interpretation for reflection, not a prediction."
            ),
            "safety_note": None,
        }

    # ---------------------------------------------------------- plumbing

    def _maybe_fail(self) -> None:
        if self.fail_with is not None:
            error = self.fail_with
            self.fail_with = None
            raise error

    def _metadata(self, request: AIRequest) -> GenerationMetadata:
        choice = get_model_router().choose(request.use_case, tier=request.tier)
        return GenerationMetadata(
            provider=self.name,
            model_requested=choice.requested_model,
            model_actual=choice.model,
            prompt_version="",
            context_version="",
            source_fingerprint="",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            latency_ms=1,
            status=GenerationStatus.COMPLETED,
            retry_count=0,
            provider_response_id="fake-response",
            use_case=request.use_case,
        )

    async def close(self) -> None:
        return None

    # Convenience for tests.
    def raise_next(self, error: Exception) -> None:
        self.fail_with = error

    def rate_limit_next(self) -> None:
        self.fail_with = AIRateLimited()

    def timeout_next(self) -> None:
        self.fail_with = AITimeout()
