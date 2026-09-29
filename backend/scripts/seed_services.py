"""Seed or refresh the service catalogue.

Idempotent: matches on ``code``, so it is safe to run after every deploy.

    python scripts/seed_services.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import dispose_engine, session_scope  # noqa: E402
from app.services.catalog.service import CatalogService  # noqa: E402


async def main() -> int:
    async with session_scope() as session:
        created, updated = await CatalogService(session).seed()
    await dispose_engine()
    print(f"Service catalogue: {created} created, {updated} updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
