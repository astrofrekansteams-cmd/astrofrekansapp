"""Benchmark the parts of Astro AI the backend actually controls.

Provider latency is the provider's; it varies by model, load and prompt length
and there is nothing to optimise here. What *is* ours is everything around the
call: resolving and authorising a source, running the engine, selecting and
budgeting the context, rendering it, and validating what comes back. Those are
what this measures, with the fake provider standing in for the model so the
numbers are stable and cost nothing.

Run:  python -m scripts.benchmark_ai
"""

from __future__ import annotations

import asyncio
import statistics
import time
from datetime import date, time as clock_time

from app.domain.ai import Locale, ModelTier, UseCase
from app.domain.astrology import BirthData
from app.domain.enums import HouseSystem
from app.services.ai import prompts
from app.services.ai.context.budget import estimate_tokens
from app.services.ai.context.builder import AstroAIContextBuilder
from app.services.ai.context.intent import classify
from app.services.ai.fake_provider import FakeAIProvider
from app.services.ai.generation import GenerationService, render_context
from app.services.ai.schemas import REPORT_SCHEMA, validate_report
from app.services.astrology.skyfield_engine import get_engine

BIRTH = BirthData(
    birth_date=date(1992, 5, 14),
    birth_time=clock_time(14, 30),
    timezone="Europe/Istanbul",
    latitude=41.0082,
    longitude=28.9784,
    house_system=HouseSystem.PLACIDUS,
)


def timed(label: str, func, repeat: int = 20) -> dict:
    samples = []
    for _ in range(repeat):
        started = time.perf_counter()
        result = func()
        samples.append((time.perf_counter() - started) * 1000)
    return {
        "label": label,
        "median_ms": round(statistics.median(samples), 2),
        "p95_ms": round(sorted(samples)[int(len(samples) * 0.95) - 1], 2),
        "result": result,
    }


async def main() -> None:
    engine = get_engine()
    builder = AstroAIContextBuilder()
    provider = FakeAIProvider()
    generation = GenerationService(provider)

    rows: list[dict] = []

    # The chart itself: the engine cost the AI layer inherits.
    rows.append(timed("natal chart (engine)", lambda: engine.natal_chart(BIRTH), 10))
    chart = rows[-1].pop("result")

    rows.append(
        timed(
            "natal context (build + budget)",
            lambda: builder.natal(
                chart, locale=Locale.TR, subject={"kind": "app_user"},
                token_budget=14000,
            ),
        )
    )
    context = rows[-1].pop("result")

    rows.append(timed("render context", lambda: render_context(context), 50))
    rendered = rows[-1].pop("result")

    rows.append(
        timed(
            "intent routing",
            lambda: classify("Bu ay kariyerimde ne var?"),
            200,
        )
    )
    rows[-1].pop("result")

    rows.append(
        timed(
            "instructions (prompt assembly)",
            lambda: prompts.NATAL_REPORT.instructions(Locale.TR),
            200,
        )
    )
    rows[-1].pop("result")

    payload = provider._payload_for(
        type("R", (), {"input": [{"content": rendered}], "json_schema": REPORT_SCHEMA})()
    )
    rows.append(
        timed("validate + ground report", lambda: validate_report(payload, context), 200)
    )
    rows[-1].pop("result")

    # End to end, minus the model's own thinking time.
    started = time.perf_counter()
    for _ in range(10):
        await generation.run_structured(
            session=None,
            user_id=None,
            prompt=prompts.NATAL_REPORT,
            context=context,
            json_schema=REPORT_SCHEMA,
            schema_name="astrofrekans_report",
            validator=validate_report,
            use_case=UseCase.REPORT,
            tier=ModelTier.PREMIUM,
        )
    end_to_end = (time.perf_counter() - started) * 1000 / 10

    print(f"{'step':38} {'median ms':>10} {'p95 ms':>9}")
    print("-" * 60)
    for row in rows:
        print(f"{row['label']:38} {row['median_ms']:>10} {row['p95_ms']:>9}")
    print("-" * 60)
    print(f"{'backend overhead per report (fake)':38} {round(end_to_end, 2):>10}")
    print()
    print(f"context factors kept      : {len(context.factors)}")
    print(f"context factors trimmed   : {len(context.trimmed_factor_ids)}")
    print(f"context estimated tokens  : {context.estimated_tokens}")
    print(f"rendered characters       : {len(rendered)}")
    print(f"rendered estimated tokens : {estimate_tokens(rendered)}")
    print(f"instruction tokens (est.) : "
          f"{estimate_tokens(prompts.NATAL_REPORT.instructions(Locale.TR))}")

    # Budget behaviour under pressure.
    print()
    print(f"{'budget':>8} {'kept':>6} {'trimmed':>8} {'tokens':>8}")
    for limit in (1000, 3000, 6000, 14000):
        trimmed = builder.natal(
            chart, locale=Locale.TR, subject={}, token_budget=limit
        )
        print(
            f"{limit:>8} {len(trimmed.factors):>6} "
            f"{len(trimmed.trimmed_factor_ids):>8} {trimmed.estimated_tokens:>8}"
        )


if __name__ == "__main__":
    asyncio.run(main())
