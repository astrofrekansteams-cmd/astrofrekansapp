"""Rebuilding `presenceVisibility` for conversations provisioned before B9's fix.

The properties worth breaking a build over:

* **Both directions, per conversation.** A granting thread gets
  `{a}/{b}/{id}` and `{b}/{a}/{id}`, nothing else.
* **The B9 policy decides**, not a status list copied here: closed, suspended
  and unpaid threads get nothing; a stored status its order has overtaken is
  not trusted.
* **Idempotent.** A second run writes nothing.
* **Nothing is removed unless asked**, and even then only what Postgres
  positively says is invalid.
* **Counts only.** No uid leaves the command.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models.chat import ExpertConversation
from app.db.models.marketplace import Expert, ExpertService, ServiceOrder
from app.db.models.service import ServiceDefinition
from app.db.models.user import User
from app.domain.chat import ConversationStatus, ProvisioningStatus
from app.domain.marketplace import (
    DeliveryType,
    ExpertStatus,
    FulfillmentMode,
    OrderStatus,
    PaymentStatus,
)
from app.services.chat import presence_backfill
from app.services.chat.presence_backfill import PresenceVisibilityBackfill
from app.services.firebase import factory as firebase_factory
from app.services.firebase.provider import FirebaseNotConfigured

USER_UID = "uid-backfill-user"
EXPERT_UID = "uid-backfill-expert"
OTHER_UID = "uid-backfill-other"


# ================================================================ fixtures


@pytest.fixture
def firebase(monkeypatch):
    monkeypatch.setattr(settings, "firebase_provider", "fake")
    providers = firebase_factory.fake_providers()
    firebase_factory.set_firebase(providers)
    yield providers
    firebase_factory.set_firebase(None)


@pytest.fixture
async def world(session_factory) -> dict:
    """A user and an expert, both on Firebase, and a chat offering."""
    from app.services.catalog.service import CatalogService

    async with session_factory() as session:
        await CatalogService(session).seed()
        definition = await session.scalar(
            select(ServiceDefinition)
            .where(ServiceDefinition.supports_chat.is_(True))
            .limit(1)
        )
        users = {}
        for key, uid in (("user", USER_UID), ("expert", EXPERT_UID), ("other", OTHER_UID)):
            row = User(
                email=f"{key}-backfill@example.com",
                password_hash=None,
                is_active=True,
                is_email_verified=True,
                firebase_uid=uid,
            )
            session.add(row)
            users[key] = row
        await session.flush()

        expert = Expert(
            user_id=users["expert"].id,
            display_name="Backfill Expert",
            languages=["tr"],
            specialties=["astrology"],
            experience_years=5,
            timezone="Europe/Istanbul",
            status=ExpertStatus.ACTIVE.value,
            verified=True,
            rating_average=0,
            rating_count=0,
        )
        session.add(expert)
        await session.flush()
        offering = ExpertService(
            expert_id=expert.id,
            service_definition_id=definition.id,
            title="Chat",
            delivery_type=DeliveryType.CHAT.value,
            duration_minutes=60,
            price_minor=10000,
            currency="TRY",
            active=True,
        )
        session.add(offering)
        await session.commit()
        return {
            "user_id": users["user"].id,
            "other_id": users["other"].id,
            "expert_user_id": users["expert"].id,
            "expert_id": expert.id,
            "definition_id": definition.id,
            "offering_id": offering.id,
        }


async def make_conversation(
    session_factory,
    world: dict,
    *,
    order_status: OrderStatus = OrderStatus.CONFIRMED,
    status: ConversationStatus = ConversationStatus.ACTIVE,
    user_key: str = "user_id",
) -> str:
    """An order and its conversation, written the way B9 left them."""
    async with session_factory() as session:
        order = ServiceOrder(
            user_id=world[user_key],
            service_definition_id=world["definition_id"],
            expert_id=world["expert_id"],
            expert_service_id=world["offering_id"],
            fulfillment_mode=FulfillmentMode.EXPERT.value,
            delivery_type=DeliveryType.CHAT.value,
            status=order_status.value,
            payment_status=PaymentStatus.PAID.value,
            subtotal_minor=10000,
            discount_minor=0,
            total_minor=10000,
            currency="TRY",
            commission_basis_points=2000,
            platform_fee_minor=2000,
            expert_net_minor=8000,
            service_title="Chat",
            service_duration_minutes=60,
        )
        session.add(order)
        await session.flush()
        conversation = ExpertConversation(
            order_id=order.id,
            user_id=world[user_key],
            expert_id=world["expert_id"],
            expert_user_id=world["expert_user_id"],
            status=status.value,
            provisioning_status=ProvisioningStatus.ACTIVE.value,
            closed_at=datetime.now(UTC) if status is ConversationStatus.CLOSED else None,
        )
        session.add(conversation)
        await session.commit()
        return str(conversation.id)


async def close(session_factory, conversation_id: str) -> None:
    """Close in Postgres only - as if the RTDB revoke never landed."""
    async with session_factory() as session:
        row = await session.get(ExpertConversation, uuid.UUID(conversation_id))
        row.status = ConversationStatus.CLOSED.value
        row.closed_at = datetime.now(UTC)
        await session.commit()


async def backfill(session_factory, firebase, **options):
    async with session_factory() as session:
        return await PresenceVisibilityBackfill(
            session, firebase.presence, batch_size=2
        ).run(**options)


def grants(firebase) -> dict:
    """The visibility tree as RTDB would hold it: empty nodes do not exist."""
    return {
        target: {reader: set(ids) for reader, ids in readers.items() if ids}
        for target, readers in copy.deepcopy(firebase.presence.visibility).items()
        if any(readers.values())
    }


# ================================================================== tests


async def test_an_active_conversation_gets_both_projections(session_factory, firebase, world):
    conversation = await make_conversation(session_factory, world)

    report = await backfill(session_factory, firebase)

    assert grants(firebase) == {
        USER_UID: {EXPERT_UID: {conversation}},
        EXPERT_UID: {USER_UID: {conversation}},
    }
    assert firebase.presence.may_see(EXPERT_UID, USER_UID)
    assert firebase.presence.may_see(USER_UID, EXPERT_UID)
    assert not firebase.presence.may_see(OTHER_UID, USER_UID)
    assert report.conversations_granting == 1
    assert report.projections_required == 2
    assert report.projections_missing == 2
    assert report.written == 2


async def test_two_conversations_get_four_conversation_specific_projections(
    session_factory, firebase, world
):
    first = await make_conversation(session_factory, world)
    second = await make_conversation(session_factory, world)

    report = await backfill(session_factory, firebase)

    assert grants(firebase) == {
        USER_UID: {EXPERT_UID: {first, second}},
        EXPERT_UID: {USER_UID: {first, second}},
    }
    assert report.projections_required == 4
    assert report.written == 4


async def test_closing_one_removes_only_its_two_nodes(session_factory, firebase, world):
    first = await make_conversation(session_factory, world)
    second = await make_conversation(session_factory, world)
    await backfill(session_factory, firebase)

    await close(session_factory, first)
    report = await backfill(session_factory, firebase, prune_stale=True)

    assert report.projections_stale == 2
    assert report.pruned_stale == 2
    assert report.written == 0
    assert grants(firebase) == {
        USER_UID: {EXPERT_UID: {second}},
        EXPERT_UID: {USER_UID: {second}},
    }
    # They still share the other thread.
    assert firebase.presence.may_see(EXPERT_UID, USER_UID)
    assert firebase.presence.may_see(USER_UID, EXPERT_UID)


async def test_closing_the_last_removes_presence_access(session_factory, firebase, world):
    first = await make_conversation(session_factory, world)
    second = await make_conversation(session_factory, world)
    await backfill(session_factory, firebase)

    await close(session_factory, first)
    await close(session_factory, second)
    report = await backfill(session_factory, firebase, prune_stale=True)

    assert report.pruned_stale == 4
    assert grants(firebase) == {}
    assert not firebase.presence.may_see(EXPERT_UID, USER_UID)
    assert not firebase.presence.may_see(USER_UID, EXPERT_UID)


async def test_a_second_run_changes_nothing(session_factory, firebase, world):
    await make_conversation(session_factory, world)
    await make_conversation(session_factory, world)
    await backfill(session_factory, firebase)
    before = grants(firebase)
    writes = firebase.presence.visibility_writes

    report = await backfill(session_factory, firebase, prune_stale=True, prune_legacy=True)

    assert grants(firebase) == before
    assert firebase.presence.visibility_writes == writes
    assert report.projections_missing == 0
    assert report.projections_present == 4
    assert report.written == report.pruned_stale == report.pruned_legacy == 0


async def test_a_dry_run_writes_nothing(session_factory, firebase, world):
    await make_conversation(session_factory, world)
    stale = await make_conversation(session_factory, world)
    await backfill(session_factory, firebase)
    await close(session_factory, stale)
    await make_conversation(session_factory, world)  # one missing
    before = grants(firebase)
    writes = firebase.presence.visibility_writes

    report = await backfill(
        session_factory, firebase, dry_run=True, prune_stale=True, prune_legacy=True
    )

    assert grants(firebase) == before
    assert firebase.presence.visibility_writes == writes
    assert report.conversations_examined == 3
    assert report.projections_required == 4
    assert report.projections_missing == 2
    assert report.projections_stale == 2
    assert report.written == report.pruned_stale == 0


async def test_without_prune_nothing_is_removed(session_factory, firebase, world):
    closed = await make_conversation(session_factory, world)
    await backfill(session_factory, firebase)
    await close(session_factory, closed)
    before = grants(firebase)
    writes = firebase.presence.visibility_writes

    report = await backfill(session_factory, firebase)

    assert report.projections_stale == 2
    assert report.pruned_stale == 0
    assert grants(firebase) == before
    assert firebase.presence.visibility_writes == writes


async def test_the_b9_policy_decides_who_is_granted(session_factory, firebase, world):
    # Unpaid, failed, suspended, closed-by-a-party: nothing.
    await make_conversation(session_factory, world, order_status=OrderStatus.PENDING_PAYMENT)
    await make_conversation(session_factory, world, order_status=OrderStatus.FAILED)
    await make_conversation(session_factory, world, status=ConversationStatus.SUSPENDED)
    await make_conversation(session_factory, world, status=ConversationStatus.CLOSED)
    # Stored ACTIVE, but the order has since failed: the stored status is not
    # trusted over the order.
    await make_conversation(
        session_factory, world, order_status=OrderStatus.FAILED,
        status=ConversationStatus.ACTIVE,
    )

    report = await backfill(session_factory, firebase)

    assert report.conversations_examined == 5
    assert report.conversations_not_granting == 5
    assert report.written == 0
    assert grants(firebase) == {}


async def test_a_member_without_firebase_is_counted_not_projected(
    session_factory, firebase, world
):
    async with session_factory() as session:
        row = await session.get(User, world["other_id"])
        row.firebase_uid = None
        await session.commit()
    await make_conversation(session_factory, world, user_key="other_id")

    report = await backfill(session_factory, firebase)

    assert report.conversations_missing_identity == 1
    assert report.written == 0
    assert grants(firebase) == {}


async def test_agrees_with_normal_provisioning(session_factory, firebase, world):
    """A thread provisioned by B9 itself needs nothing from the backfill."""
    from app.services.chat.conversations import ConversationService

    conversation_id = await make_conversation(session_factory, world)
    async with session_factory() as session:
        row = await session.get(ExpertConversation, uuid.UUID(conversation_id))
        assert await ConversationService(session, firebase).provision(row)
        await session.commit()
    writes = firebase.presence.visibility_writes

    report = await backfill(session_factory, firebase, prune_stale=True)

    assert report.projections_present == 2
    assert report.projections_missing == report.projections_stale == 0
    assert firebase.presence.visibility_writes == writes


async def test_legacy_nodes_are_removed_only_when_asked(session_factory, firebase, world):
    conversation = await make_conversation(session_factory, world)
    # The old layout: {target}/{conversationId}/{reader}.
    firebase.presence.visibility = {
        USER_UID: {conversation: {EXPERT_UID}},
        EXPERT_UID: {conversation: {USER_UID}},
    }

    report = await backfill(session_factory, firebase)
    assert report.legacy_nodes == 2
    assert report.written == 2
    assert grants(firebase)[USER_UID][conversation] == {EXPERT_UID}

    report = await backfill(session_factory, firebase, prune_legacy=True)
    assert report.pruned_legacy == 2
    assert grants(firebase) == {
        USER_UID: {EXPERT_UID: {conversation}},
        EXPERT_UID: {USER_UID: {conversation}},
    }


async def test_a_conversation_postgres_does_not_know_is_never_pruned(
    session_factory, firebase, world
):
    unknown = str(uuid.uuid4())
    firebase.presence.visibility = {USER_UID: {EXPERT_UID: {unknown}}}

    report = await backfill(session_factory, firebase, prune_stale=True, prune_legacy=True)

    assert report.unrecognised_nodes == 1
    assert report.pruned_stale == report.pruned_legacy == 0
    assert grants(firebase) == {USER_UID: {EXPERT_UID: {unknown}}}


async def test_unconfigured_firebase_is_a_clear_refusal(session_factory, firebase, world):
    firebase.presence.unavailable = True
    with pytest.raises(FirebaseNotConfigured):
        await backfill(session_factory, firebase)


async def test_the_command_refuses_without_real_firebase(monkeypatch, capsys):
    from scripts import rebuild_presence_visibility as command

    monkeypatch.setattr(settings, "firebase_provider", "fake")
    assert await command.main(["--dry-run"]) == command.EXIT_NOT_CONFIGURED
    assert json.loads(capsys.readouterr().out)["error"] == "firebase_not_configured"

    monkeypatch.setattr(settings, "firebase_provider", "firebase")
    monkeypatch.setattr(settings, "firebase_project_id", None)
    assert await command.main([]) == command.EXIT_NOT_CONFIGURED
    assert json.loads(capsys.readouterr().out)["error"] == "firebase_not_configured"


async def test_only_counts_are_reported_or_logged(session_factory, firebase, world, monkeypatch):
    recorded: list = []

    class Recorder:
        def _record(self, event, *args, **fields):
            recorded.append((event, fields))

        info = warning = error = exception = debug = _record

    monkeypatch.setattr(presence_backfill, "logger", Recorder())
    conversation = await make_conversation(session_factory, world)

    report = await backfill(session_factory, firebase)

    values = report.as_dict().values()
    assert all(isinstance(value, (int, bool)) for value in values)
    blob = repr(recorded) + repr(report.as_dict())
    for secret in (USER_UID, EXPERT_UID, conversation, "backfill@example.com"):
        assert secret not in blob


async def test_the_real_rtdb_provider_writes_the_canonical_paths(
    session_factory, world, monkeypatch
):
    """The Admin SDK implementation, over an in-memory RTDB reference."""
    from app.services.firebase.firebase_provider import FirebasePresenceProviderImpl
    from tests.test_presence_contract import MemoryReference

    first = await make_conversation(session_factory, world)
    second = await make_conversation(session_factory, world)
    tree = {
        # Old layout for `first`, left from before the fix.
        "presenceVisibility": {
            USER_UID: {first: {EXPERT_UID: True}},
            EXPERT_UID: {first: {USER_UID: True}},
        }
    }
    provider = FirebasePresenceProviderImpl()
    monkeypatch.setattr(FirebasePresenceProviderImpl, "available", property(lambda _: True))
    monkeypatch.setattr(provider, "_reference", lambda path: MemoryReference(tree, path))

    async def run(**options):
        async with session_factory() as session:
            return await PresenceVisibilityBackfill(session, provider).run(**options)

    report = await run()
    assert report.written == 4
    assert tree["presenceVisibility"][USER_UID][EXPERT_UID] == {first: True, second: True}
    assert tree["presenceVisibility"][EXPERT_UID][USER_UID] == {first: True, second: True}

    await close(session_factory, first)
    report = await run(prune_stale=True, prune_legacy=True)
    assert (report.written, report.pruned_stale, report.pruned_legacy) == (0, 2, 2)
    assert tree["presenceVisibility"] == {
        USER_UID: {EXPERT_UID: {second: True}},
        EXPERT_UID: {USER_UID: {second: True}},
    }

    await close(session_factory, second)
    await run(prune_stale=True)
    assert tree["presenceVisibility"] == {USER_UID: {}, EXPERT_UID: {}}
    assert (await run()).projections_required == 0


# =============================================== provision and backfill agree


async def provisioned(session_factory, world, conversation_id: str):
    """Run B9's normal provisioning path against its own fresh fake."""
    from app.services.chat.conversations import ConversationService

    providers = firebase_factory.fake_providers()
    async with session_factory() as session:
        row = await session.get(ExpertConversation, uuid.UUID(conversation_id))
        assert await ConversationService(session, providers).provision(row)
        await session.commit()
    return providers


@pytest.mark.parametrize(
    ("order_status", "status", "completed_days_ago", "expected"),
    [
        (OrderStatus.CONFIRMED, ConversationStatus.ACTIVE, None, True),
        # Current product policy: read-only threads keep presence.
        (OrderStatus.CANCELLED, ConversationStatus.READ_ONLY, None, True),
        (OrderStatus.COMPLETED, ConversationStatus.READ_ONLY, 365, True),
        (OrderStatus.CONFIRMED, ConversationStatus.SUSPENDED, None, False),
        (OrderStatus.CONFIRMED, ConversationStatus.CLOSED, None, False),
    ],
    ids=["active", "read_only_cancelled", "read_only_after_grace", "suspended", "closed"],
)
async def test_provision_and_backfill_reach_the_same_grants(
    session_factory, firebase, world, order_status, status, completed_days_ago, expected
):
    conversation = await make_conversation(
        session_factory, world, order_status=order_status, status=status
    )
    if completed_days_ago is not None:
        async with session_factory() as session:
            row = await session.get(ExpertConversation, uuid.UUID(conversation))
            order = await session.get(ServiceOrder, row.order_id)
            order.completed_at = datetime.now(UTC) - timedelta(days=completed_days_ago)
            await session.commit()

    via_provision = await provisioned(session_factory, world, conversation)
    report = await backfill(session_factory, firebase)

    granted = {
        USER_UID: {EXPERT_UID: {conversation}},
        EXPERT_UID: {USER_UID: {conversation}},
    }
    assert grants(via_provision) == grants(firebase)
    assert grants(firebase) == (granted if expected else {})
    assert via_provision.presence.may_see(USER_UID, EXPERT_UID) is expected
    assert report.conversations_granting == int(expected)


async def test_active_plus_suspended_leaves_only_the_active_grant_until_it_closes(
    session_factory, world
):
    from app.services.chat.conversations import ConversationService

    active = await make_conversation(session_factory, world)
    suspended = await make_conversation(
        session_factory, world, status=ConversationStatus.SUSPENDED
    )
    providers = firebase_factory.fake_providers()
    async with session_factory() as session:
        service = ConversationService(session, providers)
        for conversation_id in (active, suspended):
            row = await session.get(ExpertConversation, uuid.UUID(conversation_id))
            assert await service.provision(row)
        await session.commit()

    assert grants(providers) == {
        USER_UID: {EXPERT_UID: {active}},
        EXPERT_UID: {USER_UID: {active}},
    }
    assert suspended not in providers.presence.membership

    # The active thread closes the normal way; nothing else holds them together.
    async with session_factory() as session:
        user = await session.get(User, world["user_id"])
        await ConversationService(session, providers).close(user, uuid.UUID(active))
        await session.commit()

    assert grants(providers) == {}
    assert not providers.presence.may_see(USER_UID, EXPERT_UID)
    assert not providers.presence.may_see(EXPERT_UID, USER_UID)


async def test_suspending_withdraws_an_existing_grant_on_reprovisioning(
    session_factory, world
):
    """Moderation marks the thread suspended and pending; reconciliation revokes."""
    from app.services.chat.conversations import ConversationService

    conversation = await make_conversation(session_factory, world)
    providers = await provisioned(session_factory, world, conversation)
    assert providers.presence.may_see(USER_UID, EXPERT_UID)

    async with session_factory() as session:
        row = await session.get(ExpertConversation, uuid.UUID(conversation))
        row.status = ConversationStatus.SUSPENDED.value
        row.provisioning_status = ProvisioningStatus.PENDING.value
        await session.commit()
    async with session_factory() as session:
        assert await ConversationService(session, providers).reconcile_pending() == 1
        await session.commit()

    assert grants(providers) == {}
    assert conversation not in providers.presence.membership
