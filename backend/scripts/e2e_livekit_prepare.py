"""Set up (and tear down) a callable order for the local LiveKit end-to-end run.

    python -m scripts.e2e_livekit_prepare setup   > e2e.json
    python -m scripts.e2e_livekit_prepare room <call_id>
    python -m scripts.e2e_livekit_prepare cleanup

`setup` writes a paid video order with an appointment happening now, for a
throwaway user and expert, and prints what the driver needs: the API base URL,
an API token for each party (minted with this deployment's JWT secret) and the
order id. No LiveKit secret is printed.

The priced order is marked PAID directly - a fixture, as for every test in
this phase. No production path sets PAID until a payment provider exists.

Local and test environments only.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_token_pair
from app.db.models.calls import CallSession
from app.db.session import get_session_factory
from scripts.call_concurrency_check import build_scenario, cleanup

MARKER = "call-e2e"


async def setup() -> None:
    await cleanup(MARKER)
    scenario = await build_scenario(MARKER)
    print(
        json.dumps(
            {
                "base_url": "http://localhost:8000/api/v1",
                "order_id": str(scenario["order_id"]),
                "user_token": create_token_pair(scenario["user_id"]).access_token,
                "expert_token": create_token_pair(scenario["expert_user_id"]).access_token,
            }
        )
    )


async def room(call_id: str) -> None:
    async with get_session_factory()() as session:
        call = await session.scalar(
            select(CallSession).where(CallSession.id == uuid.UUID(call_id))
        )
        print(call.provider_room_name if call else "")


async def main(argv: list[str]) -> int:
    if settings.is_production:
        print("REFUSED: not in production.", file=sys.stderr)
        return 1
    if argv[:1] == ["setup"]:
        await setup()
    elif argv[:1] == ["room"] and len(argv) == 2:
        await room(argv[1])
    elif argv[:1] == ["cleanup"]:
        await cleanup(MARKER)
        print("cleaned up", file=sys.stderr)
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
