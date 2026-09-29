"""Live OpenAI smoke test. Synthetic data only.

    python -m scripts.live_openai_smoke

Everything else in this repository is tested against a fake provider, which
proves our own behaviour but proves nothing about the real API: whether the
model names exist, whether the Responses API accepts our strict schema,
whether the streaming events are named what we think. This script is the one
place that finds out, and it is deliberately tiny.

**No personal data.** The context here is one invented factor,
``test:sun:trine:jupiter``. No name, no birth date, no place, no coordinates,
no real user row - nothing that reaches the provider could identify anyone.

**No key ever leaves the process.** It is read from the environment, handed to
the SDK, and never printed, logged, written to a file or included in output.

Cost: four small calls (three cheap, one short premium). Skipped entirely when
``OPENAI_API_KEY`` is unset, and that is not a failure - it is reported.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime

from app.core.config import settings
from app.domain.ai import (
    AstroContext,
    ContextFactor,
    ContextType,
    FactorImportance,
    Locale,
    ModelTier,
    UseCase,
)
from app.services.ai import prompts
from app.services.ai.generation import GenerationService, render_context
from app.services.ai.openai_provider import OpenAIProvider
from app.services.ai.provider import AIRequest
from app.services.ai.schemas import (
    REPORT_SCHEMA,
    GroundingError,
    validate_report,
)

# The one fact the model is allowed to use. It is not a real placement for
# anyone; it exists so grounding can be checked without touching user data.
FACTOR_ID = "test:sun:trine:jupiter"

SYNTHETIC_CONTEXT = AstroContext(
    context_type=ContextType.GENERAL_ASTRO_CHAT,
    subject={"kind": "synthetic_test_subject"},
    time_reference=datetime(2026, 1, 1, tzinfo=UTC),
    locale=Locale.EN,
    factors=[
        ContextFactor(
            factor_id=FACTOR_ID,
            factor_type="synthetic_aspect",
            importance=FactorImportance.HIGH,
            structured_data={
                "planet_a": "sun",
                "planet_b": "jupiter",
                "aspect": "trine",
                "orb": 1.2,
            },
            label="Sun trine Jupiter (synthetic)",
        )
    ],
    warnings=["Synthetic test data. Not a real chart."],
    context_version="live_smoke_v1",
    source_fingerprint="live-smoke",
)

# Exactly the shape the phase specification asked for.
SMOKE_SCHEMA = {
    "type": "object",
    "title": "astrofrekans_smoke",
    "properties": {
        "summary": {"type": "string"},
        "factor_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "factor_ids"],
    "additionalProperties": False,
}

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, note: str = "") -> None:
    results.append((name, ok, note))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{f' - {note}' if note else ''}")


async def test_text(provider: OpenAIProvider) -> None:
    """Test 1 - low cost model, plain text through the Responses API."""
    request = AIRequest(
        use_case=UseCase.SUMMARY,
        tier=ModelTier.LOW_COST,
        instructions=(
            "Reply with one short sentence. No astrological claims, no "
            "predictions."
        ),
        input=[{"role": "user", "content": "Say that the connection works."}],
        max_output_tokens=60,
    )
    try:
        result = await provider.generate_text(request)
    except Exception as exc:  # noqa: BLE001 - the point is to report it
        record("low_cost text", False, f"{type(exc).__name__}: {exc}")
        return

    record(
        "low_cost text",
        bool(result.text.strip()),
        f"model={result.metadata.model_actual} "
        f"tokens={result.metadata.total_tokens} "
        f"latency={result.metadata.latency_ms}ms",
    )


async def test_structured(provider: OpenAIProvider) -> None:
    """Test 2 - standard model, strict structured output, grounded."""
    request = AIRequest(
        use_case=UseCase.CHAT,
        tier=ModelTier.STANDARD,
        instructions=(
            "You interpret astrological factors supplied to you. Use only the "
            "factor_id values in the context; never invent one. Reply with a "
            "one-sentence summary and the factor_ids you used."
        ),
        input=[
            {"role": "user", "content": render_context(SYNTHETIC_CONTEXT)},
            {"role": "user", "content": "Explain this factor in one sentence."},
        ],
        max_output_tokens=200,
        json_schema=SMOKE_SCHEMA,
        schema_name="astrofrekans_smoke",
    )
    try:
        result = await provider.generate_structured(request)
    except Exception as exc:  # noqa: BLE001
        record("standard structured output", False, f"{type(exc).__name__}: {exc}")
        record("strict schema accepted by API", False, "request rejected")
        return

    record("strict schema accepted by API", True, "json_schema strict=true")

    payload = result.parsed or {}
    shape_ok = isinstance(payload.get("summary"), str) and isinstance(
        payload.get("factor_ids"), list
    )
    record("structured payload matches schema", shape_ok, json.dumps(payload)[:160])

    cited = set(payload.get("factor_ids") or [])
    grounded = cited.issubset({FACTOR_ID})
    record(
        "factor grounding held",
        grounded,
        "only the supplied id was cited"
        if grounded
        else f"invented: {sorted(cited - {FACTOR_ID})}",
    )


async def test_stream(provider: OpenAIProvider) -> None:
    """Test 3 - standard model, our own stream contract."""
    request = AIRequest(
        use_case=UseCase.CHAT,
        tier=ModelTier.STANDARD,
        instructions="Reply with two short sentences about a trine aspect.",
        input=[
            {"role": "user", "content": render_context(SYNTHETIC_CONTEXT)},
            {"role": "user", "content": "Describe this factor briefly."},
        ],
        max_output_tokens=120,
    )

    seen: list[str] = []
    text: list[str] = []
    try:
        async for chunk in provider.stream_text(request):
            seen.append(chunk.type)
            if chunk.type == "text_delta" and chunk.text:
                text.append(chunk.text)
    except Exception as exc:  # noqa: BLE001
        record("streaming", False, f"{type(exc).__name__}: {exc}")
        return

    for event in ("message_start", "text_delta", "message_complete"):
        record(f"stream event {event}", event in seen)
    record("stream produced text", bool("".join(text).strip()))


async def test_premium(provider: OpenAIProvider) -> None:
    """Test 4 - one short premium call, through the real validator.

    Deliberately minimal: a full premium report would cost real money to prove
    something the standard-tier test already proved about the schema path.
    """
    service = GenerationService(provider)
    try:
        report, metadata = await service.run_structured(
            session=None,
            user_id=None,
            prompt=prompts.NATAL_REPORT,
            context=SYNTHETIC_CONTEXT,
            json_schema=REPORT_SCHEMA,
            schema_name="astrofrekans_report",
            validator=validate_report,
            use_case=UseCase.REPORT,
            tier=ModelTier.PREMIUM,
            max_output_tokens=500,
        )
    except GroundingError as exc:
        record("premium structured report", False, f"grounding: {exc}")
        return
    except Exception as exc:  # noqa: BLE001
        record("premium structured report", False, f"{type(exc).__name__}: {exc}")
        return

    record(
        "premium structured report",
        bool(report.title and report.sections),
        f"model={metadata.model_actual} tokens={metadata.total_tokens} "
        f"sections={len(report.sections)}",
    )


async def test_azerbaijani(provider: OpenAIProvider) -> None:
    """Test 5 - is the output actually Azerbaijani, and still grounded?

    This checks the language *switch*, not the quality of the astrology
    language. A native review stays an open item however this comes out.
    """
    context = AstroContext(
        context_type=SYNTHETIC_CONTEXT.context_type,
        subject=SYNTHETIC_CONTEXT.subject,
        time_reference=SYNTHETIC_CONTEXT.time_reference,
        locale=Locale.AZ,
        factors=SYNTHETIC_CONTEXT.factors,
        warnings=SYNTHETIC_CONTEXT.warnings,
        context_version=SYNTHETIC_CONTEXT.context_version,
        source_fingerprint=SYNTHETIC_CONTEXT.source_fingerprint,
    )
    request = AIRequest(
        use_case=UseCase.CHAT,
        tier=ModelTier.LOW_COST,
        instructions=prompts.CHAT.instructions(Locale.AZ),
        input=[
            {"role": "user", "content": render_context(context)},
            {
                "role": "user",
                "content": (
                    "<user_message>\nBu astroloji faktoru qısa izah et.\n"
                    "</user_message>"
                ),
            },
        ],
        max_output_tokens=200,
    )
    try:
        result = await provider.generate_text(request)
    except Exception as exc:  # noqa: BLE001
        record("azerbaijani output", False, f"{type(exc).__name__}: {exc}")
        return

    text = result.text
    # Crude but honest: letters that exist in Azerbaijani and not in English,
    # plus a few common words. This says "not English", not "good Azerbaijani".
    azeri_markers = sum(text.lower().count(ch) for ch in "əğıöşüç")
    words = ("bu", "üçün", "və", "faktor", "gün", "ilə")
    word_hits = sum(1 for word in words if f" {word} " in f" {text.lower()} ")
    looks_azeri = azeri_markers >= 3 or word_hits >= 2

    record(
        "azerbaijani output (language switch only)",
        looks_azeri,
        f"markers={azeri_markers} words={word_hits}",
    )
    print("      NOTE: language quality still needs a native reviewer.")


async def main() -> int:
    if not settings.openai_api_key:
        print("SKIPPED: OPENAI_API_KEY is not set.")
        print("This is not a failure. The live path is simply unverified.")
        return 2

    print("provider=openai  configured=True  (key not shown)")
    print(f"models: low_cost={settings.ai_model_low_cost} "
          f"standard={settings.ai_model_standard} "
          f"premium={settings.ai_model_premium}\n")

    provider = OpenAIProvider()
    try:
        await test_text(provider)
        await test_structured(provider)
        await test_stream(provider)
        await test_premium(provider)
        await test_azerbaijani(provider)
    finally:
        await provider.close()

    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("failed: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
