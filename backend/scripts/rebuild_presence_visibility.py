"""Rebuild RTDB presence visibility from Postgres. Run once after upgrading.

    python -m scripts.rebuild_presence_visibility --dry-run
    python -m scripts.rebuild_presence_visibility
    python -m scripts.rebuild_presence_visibility --prune-stale --prune-legacy

Writes `presenceVisibility/{targetUid}/{readerUid}/{conversationId}: true` for
both members of every conversation the B9 chat policy says may see each other.
Idempotent: a second run writes nothing.

Removes nothing unless asked:

* ``--prune-stale``  canonical grants of conversations Postgres says grant
  nothing (closed, suspended, unreadable, deleted, not a member).
* ``--prune-legacy`` old-layout ``{targetUid}/{conversationId}/{readerUid}``
  nodes of conversations Postgres knows.

Grants naming a conversation Postgres does not know are counted, never removed.

Prints counts only - no uid, email, name or conversation id.

Exit codes: 0 done, 2 Firebase not configured.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.db.session import dispose_engine, session_scope  # noqa: E402
from app.services.chat.presence_backfill import PresenceVisibilityBackfill  # noqa: E402
from app.services.firebase.provider import FirebaseNotConfigured  # noqa: E402

EXIT_NOT_CONFIGURED = 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.rebuild_presence_visibility",
        description="Rebuild RTDB presenceVisibility from Postgres.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="count only; write nothing"
    )
    parser.add_argument(
        "--prune-stale",
        action="store_true",
        help="remove canonical grants Postgres says are no longer valid",
    )
    parser.add_argument(
        "--prune-legacy",
        action="store_true",
        help="remove old {target}/{conversation}/{reader} nodes of known conversations",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    return parser.parse_args(argv)


def not_configured(reason: str) -> int:
    print(json.dumps({"error": "firebase_not_configured", "reason": reason}))
    return EXIT_NOT_CONFIGURED


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if settings.firebase_provider == "fake":
        # The fake keeps its tree in this process's memory: every write would
        # vanish on exit while the report claimed success.
        return not_configured("fake_provider_has_no_database")
    if not settings.firebase_configured or not settings.firebase_database_url:
        return not_configured("credentials_or_database_url_missing")

    from app.services.firebase.factory import get_firebase

    presence = get_firebase().presence
    try:
        async with session_scope() as session:
            report = await PresenceVisibilityBackfill(
                session, presence, batch_size=args.batch_size
            ).run(
                dry_run=args.dry_run,
                prune_stale=args.prune_stale,
                prune_legacy=args.prune_legacy,
            )
            # Read-only on Postgres; nothing to commit.
            await session.rollback()
    except FirebaseNotConfigured:
        return not_configured("presence_provider_unavailable")
    finally:
        await dispose_engine()

    print(json.dumps(report.as_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
