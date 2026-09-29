"""What the backend's share of a call costs.

    python -m scripts.benchmark_calls [--iterations 100]

Measured with the fake provider on real Postgres, on purpose: LiveKit's network
latency belongs to LiveKit and varies by region, while authorisation, lookups,
token minting, webhook verification and state transitions are ours. Add the
region's LiveKit round trip to `create` (one CreateRoom) to get a real first
open; `join` makes no provider call once the room exists.

Token minting and webhook verification run the real LiveKit SDK code (JWT
signing and SHA-256 checks), so those figures are real.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import statistics
import sys
import time
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from app.core.config import settings
from app.db.models.calls import CallParticipant, CallSession
from app.db.models.user import User
from app.db.session import get_session_factory
from app.domain.calls import CallType
from app.services.calls.fake_provider import FakeRealtimeCommunicationProvider
from app.services.calls.livekit_provider import mint_join_token, verify_webhook
from app.services.calls.provider import TokenRequest
from app.services.calls.service import CallService
from scripts.call_concurrency_check import build_scenario, cleanup

MARKER = "call-benchmark"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(int(len(ordered) * fraction), len(ordered) - 1)]


def report(label: str, samples: list[float]) -> None:
    print(
        f"  {label:<38} mean {statistics.mean(samples) * 1000:7.2f} ms   "
        f"p50 {percentile(samples, 0.5) * 1000:7.2f}   "
        f"p95 {percentile(samples, 0.95) * 1000:7.2f}"
    )


async def main(iterations: int) -> int:
    if settings.database_url.startswith("sqlite"):
        print("SKIPPED: SQLite would flatter the lookups.")
        return 2
    if settings.is_production:
        print("REFUSED: this writes test rows. Not in production.")
        return 1

    logging.getLogger().setLevel(logging.WARNING)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING)
    )

    provider = FakeRealtimeCommunicationProvider()
    factory = get_session_factory()
    await cleanup(MARKER)
    try:
        scenario = await build_scenario(MARKER)
        print(f"dialect    : {settings.database_url.split('://', 1)[0]}")
        print("provider   : fake (LiveKit network latency excluded)")
        print(f"iterations : {iterations}\n")

        # --- pure CPU: the SDK's own work -------------------------------------
        mint: list[float] = []
        request = TokenRequest(
            room="call_bench", identity="p_bench", publish_sources=("camera", "microphone"),
            ttl_seconds=600,
        )
        for _ in range(iterations):
            started = time.perf_counter()
            mint_join_token(request, api_key="bench-key", api_secret="bench-secret-" + "0" * 32)
            mint.append(time.perf_counter() - started)

        body = json.dumps({"event": "room_started", "id": "EV_bench", "room": {"name": "x"}}).encode()
        from app.services.calls.livekit_provider import sign_webhook_body

        signature = sign_webhook_body(body, api_key="bench-key", api_secret="bench-secret-" + "0" * 32)
        verify: list[float] = []
        for _ in range(iterations):
            started = time.perf_counter()
            verify_webhook(body, signature, api_key="bench-key", api_secret="bench-secret-" + "0" * 32)
            verify.append(time.perf_counter() - started)

        print("SDK (CPU only)")
        report("mint a join token", mint)
        report("verify a webhook signature", verify)

        # --- create: authorise + insert session and participants -------------
        creates: list[float] = []
        call_id = None
        for _ in range(max(10, iterations // 5)):
            async with factory() as session:
                caller = await session.get(User, scenario["user_id"])
                service = CallService(session, provider)
                started = time.perf_counter()
                call, _ = await service.create(
                    caller, order_id=scenario["order_id"], call_type=CallType.VIDEO
                )
                await session.commit()
                creates.append(time.perf_counter() - started)
                call_id = call.id
                # End it so the next iteration creates afresh.
                await service.end(caller, call_id)
                await session.commit()

        async with factory() as session:
            caller = await session.get(User, scenario["user_id"])
            call, _ = await CallService(session, provider).create(
                caller, order_id=scenario["order_id"], call_type=CallType.VIDEO
            )
            await session.commit()
            call_id = call.id

        # --- lookup: membership + clock --------------------------------------
        lookups: list[float] = []
        for _ in range(iterations):
            async with factory() as session:
                caller = await session.get(User, scenario["user_id"])
                started = time.perf_counter()
                await CallService(session, provider).get_for_member(caller, call_id)
                await session.commit()
                lookups.append(time.perf_counter() - started)

        # --- join preparation: full re-authorisation + token -------------------
        joins: list[float] = []
        for _ in range(iterations):
            async with factory() as session:
                caller = await session.get(User, scenario["user_id"])
                started = time.perf_counter()
                await CallService(session, provider).issue_join_token(caller, call_id)
                await session.commit()
                joins.append(time.perf_counter() - started)

        print("\ncall path (Postgres, provider excluded)")
        report("create (authorise, insert, room)", creates)
        report("get call (membership, clock)", lookups)
        report("join (re-authorise, mint token)", joins)

        # --- webhooks: verify + record + apply --------------------------------
        async with factory() as session:
            call = await session.get(CallSession, call_id)
            participant = await session.scalar(
                select(CallParticipant).where(
                    CallParticipant.call_session_id == call_id,
                    CallParticipant.role == "user",
                )
            )
            room, identity = call.provider_room_name, participant.provider_identity

        hooks: list[float] = []
        for index in range(iterations):
            event = "participant_joined" if index % 2 == 0 else "participant_left"
            payload = {
                "event": event,
                "id": f"{MARKER}-EV-{uuid.uuid4().hex}",
                "createdAt": str(int(datetime.now(UTC).timestamp())),
                "room": {"name": room},
                "participant": {"identity": identity, "disconnectReason": "SIGNAL_CLOSE"},
            }
            if event == "participant_joined":
                del payload["participant"]["disconnectReason"]
                provider.join(room, identity)
            else:
                provider.leave(room, identity)
            raw = json.dumps(payload).encode()
            header = provider.signed_webhook(raw)
            async with factory() as session:
                started = time.perf_counter()
                parsed = provider.parse_webhook(raw, header)
                await CallService(session, provider).apply_provider_event(parsed)
                await session.commit()
                hooks.append(time.perf_counter() - started)

        # --- reconcile against the (fake) provider -----------------------------
        reconciles: list[float] = []
        for _ in range(iterations):
            async with factory() as session:
                call = await session.get(CallSession, call_id)
                started = time.perf_counter()
                await CallService(session, provider).reconcile(call)
                await session.commit()
                reconciles.append(time.perf_counter() - started)

        print("\nprovider-driven (Postgres, provider excluded)")
        report("webhook (verify, dedupe, apply)", hooks)
        report("reconcile (list participants, repair)", reconciles)

        print(
            "\nNot included: LiveKit's own latency - one CreateRoom on the first\n"
            "join of a call, one ListParticipants per reconcile - which depends on\n"
            "the region and is LiveKit's, not ours."
        )
        return 0
    finally:
        await cleanup(MARKER)
        print("\ncleaned up")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=100)
    sys.exit(asyncio.run(main(parser.parse_args().iterations)))
