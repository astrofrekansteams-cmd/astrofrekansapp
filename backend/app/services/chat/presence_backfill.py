"""Rebuild the RTDB presence-visibility projection from Postgres.

Deployment tool, not a request path. Conversations provisioned under the old
`presenceVisibility/{targetUid}/{conversationId}/{readerUid}` layout carry no
grant the current rule can see (it checks
`presenceVisibility/{targetUid}/{readerUid}`), so after the upgrade every live
partner listener is denied until each thread is reprovisioned. This writes the
canonical nodes

    presenceVisibility/{targetUid}/{readerUid}/{conversationId}: true

for both directions of every conversation that `grants_presence` - the B9
chat policy, the same rule `ConversationService.provision` applies - says
should have them.

Guarantees:

* **Idempotent.** Grants are per-key transactions; a second run finds nothing
  missing and writes nothing.
* **Adds only, unless told otherwise.** `prune_stale` removes canonical grants
  whose conversation Postgres knows and says grants nothing (closed,
  suspended, no longer readable, deleted, or a uid that is not a member).
  `prune_legacy` removes old-layout nodes of known conversations. Nodes naming
  a conversation Postgres has never heard of are counted, never removed - a
  command pointed at the wrong database must not blind every user.
* **Numbers only.** The report and the log hold counts. No uid, email, name or
  conversation id.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.logging import get_logger
from app.db.models.chat import ExpertConversation
from app.db.models.marketplace import Expert, ServiceOrder
from app.db.models.user import User
from app.services.chat.policy import grants_presence
from app.services.firebase.provider import (
    FirebaseNotConfigured,
    FirebasePresenceProvider,
)

logger = get_logger(__name__)

Grant = tuple[str, str, str]  # (target uid, reader uid, conversation id)


@dataclass(slots=True)
class PresenceBackfillReport:
    dry_run: bool
    prune_stale: bool
    prune_legacy: bool
    conversations_examined: int = 0
    conversations_granting: int = 0
    conversations_not_granting: int = 0
    conversations_missing_identity: int = 0
    projections_required: int = 0
    projections_present: int = 0
    projections_missing: int = 0
    projections_stale: int = 0
    legacy_nodes: int = 0
    unrecognised_nodes: int = 0
    written: int = 0
    pruned_stale: int = 0
    pruned_legacy: int = 0

    def as_dict(self) -> dict[str, int | bool]:
        return asdict(self)


@dataclass(slots=True)
class _Plan:
    missing: set[Grant]
    stale: set[Grant]
    legacy: set[Grant]  # (target uid, conversation id, reader uid) - old layout


class PresenceVisibilityBackfill:
    def __init__(
        self,
        session: AsyncSession,
        presence: FirebasePresenceProvider,
        *,
        batch_size: int = 500,
    ) -> None:
        self.session = session
        self.presence = presence
        self.batch_size = batch_size

    async def run(
        self,
        *,
        dry_run: bool = False,
        prune_stale: bool = False,
        prune_legacy: bool = False,
    ) -> PresenceBackfillReport:
        if not self.presence.available:
            raise FirebaseNotConfigured()

        report = PresenceBackfillReport(
            dry_run=dry_run, prune_stale=prune_stale, prune_legacy=prune_legacy
        )
        plan = await self._plan(report)

        if not dry_run:
            # Grants before removals: a pair that shares another thread never
            # loses sight of each other mid-run.
            for target, reader, conversation in sorted(plan.missing):
                await self.presence.add_visibility_grant(target, reader, conversation)
                report.written += 1
            if prune_stale:
                for target, reader, conversation in sorted(plan.stale):
                    await self.presence.remove_visibility_grant(
                        target, reader, conversation
                    )
                    report.pruned_stale += 1
            if prune_legacy:
                # Old layout: {target}/{conversation}/{reader}. Same shape of
                # removal, with the middle and leaf keys in their old places.
                for target, conversation, reader in sorted(plan.legacy):
                    await self.presence.remove_visibility_grant(
                        target, conversation, reader
                    )
                    report.pruned_legacy += 1

        logger.info("presence_visibility_backfill", **report.as_dict())
        return report

    # ------------------------------------------------------------ planning

    async def _plan(self, report: PresenceBackfillReport) -> _Plan:
        known: set[str] = set()
        required: set[Grant] = set()

        async for conversation, order, expert, user_uid, expert_uid in self._rows():
            conversation_id = str(conversation.id)
            known.add(conversation_id)
            report.conversations_examined += 1

            if not grants_presence(conversation, order, expert=expert):
                report.conversations_not_granting += 1
                continue
            if not user_uid or not expert_uid or user_uid == expert_uid:
                # Provisioning would record `no_firebase_identity`; nothing to
                # project until both sides have signed in to Firebase.
                report.conversations_missing_identity += 1
                continue

            report.conversations_granting += 1
            required.add((user_uid, expert_uid, conversation_id))
            required.add((expert_uid, user_uid, conversation_id))

        tree = await self.presence.read_visibility()
        present: set[Grant] = set()
        stale: set[Grant] = set()
        legacy: set[Grant] = set()

        for target, readers in tree.items():
            if not isinstance(readers, dict):
                report.unrecognised_nodes += 1
                continue
            for middle, leaves in readers.items():
                if not isinstance(leaves, dict):
                    report.unrecognised_nodes += 1
                    continue
                if middle in known:
                    # A conversation id where a reader uid belongs: the old
                    # layout. The current rule never matches it.
                    legacy.update((target, middle, leaf) for leaf in leaves)
                    continue
                for conversation_id in leaves:
                    grant = (target, middle, conversation_id)
                    if grant in required:
                        present.add(grant)
                    elif conversation_id in known:
                        stale.add(grant)
                    else:
                        report.unrecognised_nodes += 1

        missing = required - present
        report.projections_required = len(required)
        report.projections_present = len(present)
        report.projections_missing = len(missing)
        report.projections_stale = len(stale)
        report.legacy_nodes = len(legacy)
        return _Plan(missing=missing, stale=stale, legacy=legacy)

    async def _rows(self):  # noqa: ANN202 - async generator of row tuples
        """Every conversation, deleted ones included, in id-ordered batches.

        Deleted rows are read so their leftover grants count as stale rather
        than unrecognised.
        """
        member = aliased(User)
        expert_member = aliased(User)
        after: uuid.UUID | None = None
        while True:
            statement = (
                select(
                    ExpertConversation,
                    ServiceOrder,
                    Expert,
                    member.firebase_uid,
                    expert_member.firebase_uid,
                )
                .join(ServiceOrder, ServiceOrder.id == ExpertConversation.order_id)
                .outerjoin(Expert, Expert.id == ExpertConversation.expert_id)
                .outerjoin(member, member.id == ExpertConversation.user_id)
                .outerjoin(
                    expert_member, expert_member.id == ExpertConversation.expert_user_id
                )
                .order_by(ExpertConversation.id)
                .limit(self.batch_size)
            )
            if after is not None:
                statement = statement.where(ExpertConversation.id > after)
            batch = (await self.session.execute(statement)).all()
            if not batch:
                return
            for row in batch:
                yield tuple(row)
            after = batch[-1][0].id
            # Read-only pass: drop the loaded rows between batches.
            self.session.expunge_all()
