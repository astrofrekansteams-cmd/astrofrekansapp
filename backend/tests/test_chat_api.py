"""Expert chat: eligibility, membership, attachments, push and the invariants.

The properties worth breaking a build over:

* **Chat exists because an order does.** A user cannot open a thread with an
  arbitrary expert, and not before the order is payable.
* **Membership is the account, not the profile.** An expert is authorised
  because the conversation's `expert_user_id` is them - an expert profile id is
  not a credential.
* **Opening a chat grants no data access.** B8 consent is unchanged by anything
  in this phase: an expert can talk to a user without being able to read their
  chart.
* **A lock screen carries no content.** Push payloads hold ids and a generic
  line, never the message.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models.chat import (
    ExpertConversation,
    MediaAttachment,
    NotificationOutbox,
    PushDevice,
)
from app.db.models.marketplace import (
    Expert,
    ExpertAvailability,
    ExpertService,
    ServiceOrder,
)
from app.db.models.service import ServiceDefinition
from app.db.models.user import User
from app.domain.chat import AttachmentStatus, ConversationStatus, OutboxStatus
from app.domain.marketplace import DeliveryType, ExpertStatus, OrderStatus
from app.services.firebase import factory as firebase_factory
from app.services.notifications.sender import NotificationSender
from app.services.notifications.outbox import OutboxService

API = "/api/v1"


# =============================================================== fixtures


@pytest.fixture
def firebase(monkeypatch):
    monkeypatch.setattr(settings, "firebase_provider", "fake")
    monkeypatch.setattr(settings, "firebase_project_id", "astrofrekans-test")
    providers = firebase_factory.fake_providers()
    firebase_factory.set_firebase(providers)
    yield providers
    firebase_factory.set_firebase(None)


async def register(client: httpx.AsyncClient, email: str) -> dict:
    response = await client.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "Str0ngPassphrase!",
            "name": "Person",
            "birth_date": "1990-04-04",
            "birth_time": "11:00:00",
            "birth_place": "Istanbul",
        },
    )
    assert response.status_code == 201, response.text
    return {
        "headers": {"Authorization": f"Bearer {response.json()['access_token']}"},
        "email": email,
    }


async def give_firebase_uid(
    client: httpx.AsyncClient, firebase, account: dict, uid: str
) -> None:
    """Link a Firebase identity, the safe way: from inside a session."""
    token = f"fb-id-token-{uid}-xxxxxxxx"
    firebase.identity.register(token, uid=uid, email=f"{uid}@example.com")
    response = await client.post(
        f"{API}/auth/firebase/link",
        headers=account["headers"],
        json={"id_token": token},
    )
    assert response.status_code == 200, response.text


@pytest.fixture
def wide_open(monkeypatch):
    """Remove scheduling friction so the fixture can pick any slot."""
    monkeypatch.setattr(settings, "appointment_minimum_notice_minutes", 0)
    monkeypatch.setattr(settings, "appointment_buffer_before_minutes", 0)
    monkeypatch.setattr(settings, "appointment_buffer_after_minutes", 0)


@pytest.fixture
async def chat_setup(client: httpx.AsyncClient, firebase, wide_open, session_factory):
    """A paid, chat-capable order with both parties on Firebase."""
    from app.services.catalog.service import CatalogService

    user_account = await register(client, "chatuser@example.com")
    expert_account = await register(client, "chatexpert@example.com")
    await give_firebase_uid(client, firebase, user_account, "uid-chat-user")
    await give_firebase_uid(client, firebase, expert_account, "uid-chat-expert")

    async with session_factory() as session:
        await CatalogService(session).seed()
        await session.commit()

        definition = await session.scalar(
            select(ServiceDefinition)
            .where(
                ServiceDefinition.supports_chat.is_(True),
                ServiceDefinition.supports_appointment.is_(True),
                ServiceDefinition.active.is_(True),
            )
            .limit(1)
        )
        assert definition is not None, "no chat-capable appointment service"

        user = await session.scalar(
            select(User).where(User.email == "chatuser@example.com")
        )
        expert_user = await session.scalar(
            select(User).where(User.email == "chatexpert@example.com")
        )

        expert = Expert(
            user_id=expert_user.id,
            display_name="Chat Expert",
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
            title="Chat consultation",
            delivery_type=DeliveryType.CHAT.value,
            duration_minutes=60,
            price_minor=10000,
            currency="TRY",
            active=True,
        )
        session.add(offering)
        for weekday in range(7):
            session.add(
                ExpertAvailability(
                    expert_id=expert.id,
                    weekday=weekday,
                    start_local_time=time(0, 0),
                    end_local_time=time(23, 0),
                    timezone="Europe/Istanbul",
                    active=True,
                )
            )
        await session.commit()

        context = {
            "user": user_account,
            "expert": expert_account,
            "user_id": user.id,
            "expert_user_id": expert_user.id,
            "expert_id": expert.id,
            "service_id": offering.id,
            "definition_id": definition.id,
        }

    now = datetime.now(UTC)
    slots = await client.get(
        f"{API}/experts/{context['expert_id']}/slots",
        headers=user_account["headers"],
        params={
            "service_id": str(context["service_id"]),
            "from": now.isoformat(),
            "to": (now + timedelta(days=5)).isoformat(),
        },
    )
    assert slots.status_code == 200, slots.text

    # Far enough out that all three reminder offsets are still in the future.
    # A nearer slot would have them skipped rather than scheduled, and the
    # reminder tests would pass vacuously.
    cutoff = now + timedelta(hours=26)
    starts = next(
        slot["starts_at_utc"]
        for slot in slots.json()["slots"]
        if datetime.fromisoformat(slot["starts_at_utc"]) > cutoff
    )

    order = await client.post(
        f"{API}/orders",
        headers=user_account["headers"],
        json={
            "expert_service_id": str(context["service_id"]),
            "starts_at_utc": starts,
        },
    )
    assert order.status_code == 201, order.text
    context["order_id"] = uuid.UUID(order.json()["id"])

    # A priced order waits for payment, and chat is not open then. Move it to
    # confirmed the way a payment webhook will.
    async with session_factory() as session:
        row = await session.scalar(
            select(ServiceOrder).where(ServiceOrder.id == context["order_id"])
        )
        row.status = OrderStatus.CONFIRMED.value
        await session.commit()

    return context


async def clear_outbox(session_factory) -> None:
    """Empty the queue.

    The fixture books an appointment, which legitimately queues notifications
    of its own. A test about the fate of *one* row has to start from an empty
    queue, or `claim_next` hands it a booking notification instead.
    """
    from sqlalchemy import delete

    async with session_factory() as session:
        await session.execute(delete(NotificationOutbox))
        await session.commit()


async def open_conversation(client, setup) -> dict:
    response = await client.post(
        f"{API}/conversations",
        headers=setup["user"]["headers"],
        json={"order_id": str(setup["order_id"])},
    )
    assert response.status_code == 201, response.text
    return response.json()


# ========================================================== eligibility


async def test_a_conversation_needs_an_order(client: httpx.AsyncClient, firebase, registered):
    """A user cannot open a thread with an arbitrary expert."""
    response = await client.post(
        f"{API}/conversations",
        headers=registered["headers"],
        json={"order_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


async def test_chat_is_closed_before_payment(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    """Chat before payment would be a free consultation channel."""
    async with session_factory() as session:
        order = await session.scalar(
            select(ServiceOrder).where(ServiceOrder.id == chat_setup["order_id"])
        )
        order.status = OrderStatus.PENDING_PAYMENT.value
        await session.commit()

    response = await client.post(
        f"{API}/conversations",
        headers=chat_setup["user"]["headers"],
        json={"order_id": str(chat_setup["order_id"])},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "chat_not_available"
    assert "pending_payment" in response.json()["error"]["details"]["reason"]


async def test_opening_a_conversation_is_idempotent(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    first = await open_conversation(client, chat_setup)
    second = await open_conversation(client, chat_setup)
    assert first["id"] == second["id"]

    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(ExpertConversation).where(
                    ExpertConversation.order_id == chat_setup["order_id"]
                )
            )
        )
    assert len(rows) == 1, "one conversation per order"


async def test_the_projection_is_written_for_both_members(
    client: httpx.AsyncClient, firebase, chat_setup
):
    conversation = await open_conversation(client, chat_setup)

    projection = firebase.chat.conversations[conversation["id"]]
    assert set(projection.member_uids) == {"uid-chat-user", "uid-chat-expert"}
    assert projection.status is ConversationStatus.ACTIVE
    # Membership is mirrored into RTDB so its rules can check it.
    assert set(firebase.presence.membership[conversation["id"]]) == {
        "uid-chat-user",
        "uid-chat-expert",
    }
    assert conversation["provisioning_status"] == "active"


async def test_a_firebase_outage_does_not_lose_the_conversation(
    client: httpx.AsyncClient, firebase, chat_setup
):
    """An order somebody paid for must not roll back because Firestore blinked."""
    firebase.chat.unavailable = True

    conversation = await open_conversation(client, chat_setup)
    assert conversation["provisioning_status"] == "failed"

    # And it is repaired once Firebase returns.
    firebase.chat.unavailable = False
    again = await client.get(
        f"{API}/conversations/{conversation['id']}",
        headers=chat_setup["user"]["headers"],
    )
    assert again.json()["provisioning_status"] == "active"


# ============================================================ membership


async def test_both_parties_are_members(client: httpx.AsyncClient, firebase, chat_setup):
    conversation = await open_conversation(client, chat_setup)

    as_user = await client.get(
        f"{API}/conversations/{conversation['id']}",
        headers=chat_setup["user"]["headers"],
    )
    assert as_user.json()["my_role"] == "user"
    assert as_user.json()["counterpart_display_name"] == "Chat Expert"

    as_expert = await client.get(
        f"{API}/conversations/{conversation['id']}",
        headers=chat_setup["expert"]["headers"],
    )
    assert as_expert.status_code == 200
    assert as_expert.json()["my_role"] == "expert"


async def test_a_stranger_cannot_reach_the_conversation(
    client: httpx.AsyncClient, firebase, chat_setup
):
    conversation = await open_conversation(client, chat_setup)
    stranger = await register(client, "nosy@example.com")

    for method, path, body in (
        ("get", f"{API}/conversations/{conversation['id']}", None),
        ("get", f"{API}/conversations/{conversation['id']}/messages", None),
        ("post", f"{API}/conversations/{conversation['id']}/messages", {"text": "hi"}),
        ("get", f"{API}/conversations/{conversation['id']}/presence", None),
        ("post", f"{API}/conversations/{conversation['id']}/close", {}),
    ):
        response = await getattr(client, method)(
            path, headers=stranger["headers"], **({"json": body} if body is not None else {})
        )
        # 404, not 403: a wrong guess must not confirm the thread exists.
        assert response.status_code == 404, path


async def test_another_expert_is_not_a_member(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    """An expert profile id is not a credential."""
    conversation = await open_conversation(client, chat_setup)
    other = await register(client, "rival-expert@example.com")

    async with session_factory() as session:
        rival_user = await session.scalar(
            select(User).where(User.email == "rival-expert@example.com")
        )
        session.add(
            Expert(
                user_id=rival_user.id,
                display_name="Rival",
                languages=["tr"],
                specialties=["tarot"],
                experience_years=1,
                timezone="Europe/Istanbul",
                status=ExpertStatus.ACTIVE.value,
                verified=False,
                rating_average=0,
                rating_count=0,
            )
        )
        await session.commit()

    response = await client.get(
        f"{API}/conversations/{conversation['id']}", headers=other["headers"]
    )
    assert response.status_code == 404


# ============================================================== messages


async def test_sending_and_reading_a_message(
    client: httpx.AsyncClient, firebase, chat_setup
):
    conversation = await open_conversation(client, chat_setup)

    sent = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "Merhaba, sorum var."},
    )
    assert sent.status_code == 201, sent.text
    body = sent.json()
    assert body["text"] == "Merhaba, sorum var."
    assert body["sender_role"] == "user"
    assert body["message_type"] == "text"
    # A server timestamp, not the client's clock.
    assert body["created_at"]

    history = await client.get(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["expert"]["headers"],
    )
    assert history.status_code == 200
    assert [item["text"] for item in history.json()["items"]] == [
        "Merhaba, sorum var."
    ]


async def test_message_idempotency(client: httpx.AsyncClient, firebase, chat_setup):
    conversation = await open_conversation(client, chat_setup)
    payload = {"text": "Tek mesaj", "client_message_id": "client-abc-1"}

    first = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json=payload,
    )
    second = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json=payload,
    )

    assert first.json()["message_id"] == second.json()["message_id"]
    history = await client.get(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
    )
    assert len(history.json()["items"]) == 1


async def test_the_same_client_id_with_different_text_is_a_conflict(
    client: httpx.AsyncClient, firebase, chat_setup
):
    conversation = await open_conversation(client, chat_setup)
    await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "First", "client_message_id": "dup-1"},
    )
    conflict = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "Different", "client_message_id": "dup-1"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "message_conflict"


@pytest.mark.parametrize(
    "text",
    ["", "   ", "\n\t "],
)
async def test_an_empty_message_is_refused(
    client: httpx.AsyncClient, firebase, chat_setup, text: str
):
    conversation = await open_conversation(client, chat_setup)
    response = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": text},
    )
    assert response.status_code == 422


async def test_an_oversized_message_is_refused(
    client: httpx.AsyncClient, firebase, chat_setup
):
    conversation = await open_conversation(client, chat_setup)
    response = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "x" * 5000},
    )
    assert response.status_code == 422


async def test_control_characters_are_stripped(
    client: httpx.AsyncClient, firebase, chat_setup
):
    conversation = await open_conversation(client, chat_setup)
    response = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "hello\x00\x07world"},
    )
    assert response.status_code == 201
    assert response.json()["text"] == "helloworld"


async def test_only_the_sender_may_delete_their_message(
    client: httpx.AsyncClient, firebase, chat_setup
):
    """A conversation either party can edit is not a record of anything."""
    conversation = await open_conversation(client, chat_setup)
    sent = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "Mine"},
    )
    message_id = sent.json()["message_id"]

    refused = await client.delete(
        f"{API}/conversations/{conversation['id']}/messages/{message_id}",
        headers=chat_setup["expert"]["headers"],
    )
    assert refused.status_code >= 400

    allowed = await client.delete(
        f"{API}/conversations/{conversation['id']}/messages/{message_id}",
        headers=chat_setup["user"]["headers"],
    )
    assert allowed.status_code == 200
    assert allowed.json()["deleted_at"] is not None
    assert allowed.json()["text"] is None


async def test_history_is_paginated(client: httpx.AsyncClient, firebase, chat_setup):
    conversation = await open_conversation(client, chat_setup)
    for index in range(5):
        await client.post(
            f"{API}/conversations/{conversation['id']}/messages",
            headers=chat_setup["user"]["headers"],
            json={"text": f"message {index}", "client_message_id": f"m{index}"},
        )

    page = await client.get(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        params={"limit": 2},
    )
    assert len(page.json()["items"]) == 2
    assert page.json()["has_more"] is True

    next_page = await client.get(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        params={"limit": 2, "before": page.json()["next_cursor"]},
    )
    assert len(next_page.json()["items"]) == 2
    first_ids = {item["message_id"] for item in page.json()["items"]}
    second_ids = {item["message_id"] for item in next_page.json()["items"]}
    assert not (first_ids & second_ids)


# ====================================================== order state policy


async def test_a_completed_order_becomes_read_only_after_the_grace_period(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory, monkeypatch
):
    conversation = await open_conversation(client, chat_setup)

    async with session_factory() as session:
        order = await session.scalar(
            select(ServiceOrder).where(ServiceOrder.id == chat_setup["order_id"])
        )
        order.status = OrderStatus.COMPLETED.value
        # Long enough ago that the grace period has passed.
        order.completed_at = datetime.now(UTC) - timedelta(days=60)
        await session.commit()

    view = await client.get(
        f"{API}/conversations/{conversation['id']}",
        headers=chat_setup["user"]["headers"],
    )
    assert view.json()["status"] == "read_only"
    assert view.json()["permission"]["can_read"] is True
    assert view.json()["permission"]["can_write"] is False

    blocked = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "too late"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "chat_read_only"


async def test_a_just_completed_order_still_allows_follow_up(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    """Somebody just told something complicated will have a question."""
    conversation = await open_conversation(client, chat_setup)

    async with session_factory() as session:
        order = await session.scalar(
            select(ServiceOrder).where(ServiceOrder.id == chat_setup["order_id"])
        )
        order.status = OrderStatus.COMPLETED.value
        order.completed_at = datetime.now(UTC)
        await session.commit()

    response = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "One more question"},
    )
    assert response.status_code == 201


async def test_a_cancelled_order_keeps_history_but_closes_writing(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    conversation = await open_conversation(client, chat_setup)
    await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "before cancellation"},
    )

    await client.post(
        f"{API}/orders/{chat_setup['order_id']}/cancel",
        headers=chat_setup["user"]["headers"],
        json={"reason": "changed my mind"},
    )

    history = await client.get(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
    )
    # The record survives: it is evidence of what was said.
    assert history.status_code == 200
    assert len(history.json()["items"]) == 1

    blocked = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "after"},
    )
    assert blocked.status_code == 409


async def test_a_suspended_expert_cannot_write(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    conversation = await open_conversation(client, chat_setup)

    async with session_factory() as session:
        expert = await session.scalar(
            select(Expert).where(Expert.id == chat_setup["expert_id"])
        )
        expert.status = ExpertStatus.SUSPENDED.value
        await session.commit()

    response = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["expert"]["headers"],
        json={"text": "still here"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "expert_suspended"

    # The user keeps their history: removing it would punish the wrong person.
    history = await client.get(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
    )
    assert history.status_code == 200


async def test_closing_a_conversation_stops_new_messages(
    client: httpx.AsyncClient, firebase, chat_setup
):
    conversation = await open_conversation(client, chat_setup)
    assert firebase.presence.may_see("uid-chat-user", "uid-chat-expert")
    closed = await client.post(
        f"{API}/conversations/{conversation['id']}/close",
        headers=chat_setup["user"]["headers"],
        json={"reason": "done"},
    )
    assert closed.json()["status"] == "closed"
    assert conversation["id"] not in firebase.presence.membership
    assert not firebase.presence.may_see("uid-chat-user", "uid-chat-expert")
    assert not firebase.presence.may_see("uid-chat-expert", "uid-chat-user")

    response = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "hello?"},
    )
    assert response.status_code == 409


# ======================================================== consent invariant


async def test_chat_access_does_not_grant_data_access(
    client: httpx.AsyncClient, firebase, chat_setup
):
    """The B9/B8 boundary: talking is not reading.

    An expert may hold a conversation and still have no consent to the user's
    chart. Opening a thread must not quietly become a grant.
    """
    conversation = await open_conversation(client, chat_setup)
    await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["expert"]["headers"],
        json={"text": "Merhaba"},
    )

    order = await client.get(
        f"{API}/expert/orders/{chat_setup['order_id']}",
        headers=chat_setup["expert"]["headers"],
    )
    assert order.status_code == 200
    # Chat is open; consent is still empty.
    assert order.json()["granted_consent_scopes"] == []


async def test_consent_and_chat_are_independent(
    client: httpx.AsyncClient, firebase, chat_setup
):
    """Granting consent does not open chat, and revoking it does not close it."""
    conversation = await open_conversation(client, chat_setup)

    await client.put(
        f"{API}/orders/{chat_setup['order_id']}/consents",
        headers=chat_setup["user"]["headers"],
        json={"scopes": ["share_birth_profile"]},
    )
    still_open = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "after granting"},
    )
    assert still_open.status_code == 201

    await client.put(
        f"{API}/orders/{chat_setup['order_id']}/consents",
        headers=chat_setup["user"]["headers"],
        json={"scopes": []},
    )
    after_revoke = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "after revoking"},
    )
    # Revoking data access does not silence the conversation.
    assert after_revoke.status_code == 201


# ============================================================ attachments


async def test_the_attachment_flow(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    conversation = await open_conversation(client, chat_setup)

    intent = await client.post(
        f"{API}/conversations/{conversation['id']}/attachments",
        headers=chat_setup["user"]["headers"],
        json={
            "mime_type": "image/jpeg",
            "size_bytes": 2048,
            "original_filename": "../../etc/passwd",
        },
    )
    assert intent.status_code == 201, intent.text
    attachment = intent.json()["attachment"]
    grant = intent.json()["upload"]

    # The path is server-derived; the client's filename never reaches it.
    assert grant["storage_key"] == (
        f"chat/{conversation['id']}/{attachment['id']}/original.jpg"
    )
    assert ".." not in grant["storage_key"]
    assert "passwd" not in grant["storage_key"]
    assert attachment["status"] == "pending"

    # Pending is not a file: it cannot be sent yet.
    too_early = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"attachment_id": attachment["id"]},
    )
    assert too_early.status_code == 422
    assert too_early.json()["error"]["code"] == "attachment_not_ready"

    # The client uploads, then finalises.
    firebase.storage.place(
        grant["storage_key"], size_bytes=2048, content_type="image/jpeg"
    )
    finalised = await client.post(
        f"{API}/attachments/{attachment['id']}/finalize",
        headers=chat_setup["user"]["headers"],
    )
    assert finalised.status_code == 200
    assert finalised.json()["status"] == "ready"
    assert finalised.json()["verified_mime_type"] == "image/jpeg"

    sent = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"attachment_id": attachment["id"]},
    )
    assert sent.status_code == 201
    assert sent.json()["message_type"] == "image"


@pytest.mark.parametrize(
    "mime_type",
    ["image/svg+xml", "text/html", "application/javascript", "application/pdf"],
)
async def test_dangerous_and_unlisted_types_are_refused(
    client: httpx.AsyncClient, firebase, chat_setup, mime_type: str
):
    conversation = await open_conversation(client, chat_setup)
    response = await client.post(
        f"{API}/conversations/{conversation['id']}/attachments",
        headers=chat_setup["user"]["headers"],
        json={"mime_type": mime_type, "size_bytes": 1024},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] in (
        "mime_type_forbidden",
        "mime_type_not_allowed",
    )


async def test_an_oversized_attachment_is_refused(
    client: httpx.AsyncClient, firebase, chat_setup
):
    conversation = await open_conversation(client, chat_setup)
    response = await client.post(
        f"{API}/conversations/{conversation['id']}/attachments",
        headers=chat_setup["user"]["headers"],
        json={"mime_type": "image/png", "size_bytes": 99 * 1024 * 1024},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "attachment_too_large"


async def test_a_lying_content_type_is_rejected_at_finalisation(
    client: httpx.AsyncClient, firebase, chat_setup
):
    """The claimed type is not the type. The bucket is believed."""
    conversation = await open_conversation(client, chat_setup)
    intent = await client.post(
        f"{API}/conversations/{conversation['id']}/attachments",
        headers=chat_setup["user"]["headers"],
        json={"mime_type": "image/png", "size_bytes": 1024},
    )
    grant = intent.json()["upload"]

    # The client promised a PNG and uploaded HTML.
    firebase.storage.place(
        grant["storage_key"], size_bytes=1024, content_type="text/html"
    )
    response = await client.post(
        f"{API}/attachments/{intent.json()['attachment']['id']}/finalize",
        headers=chat_setup["user"]["headers"],
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "mime_type_not_allowed"
    # And the bytes do not stay in the bucket.
    assert grant["storage_key"] in firebase.storage.deleted


async def test_finalising_before_uploading_is_refused(
    client: httpx.AsyncClient, firebase, chat_setup
):
    conversation = await open_conversation(client, chat_setup)
    intent = await client.post(
        f"{API}/conversations/{conversation['id']}/attachments",
        headers=chat_setup["user"]["headers"],
        json={"mime_type": "image/png", "size_bytes": 1024},
    )
    response = await client.post(
        f"{API}/attachments/{intent.json()['attachment']['id']}/finalize",
        headers=chat_setup["user"]["headers"],
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "attachment_missing"


async def test_an_attachment_cannot_be_replayed_into_another_conversation(
    client: httpx.AsyncClient, firebase, chat_setup
):
    conversation = await open_conversation(client, chat_setup)
    intent = await client.post(
        f"{API}/conversations/{conversation['id']}/attachments",
        headers=chat_setup["user"]["headers"],
        json={"mime_type": "image/png", "size_bytes": 512},
    )
    attachment_id = intent.json()["attachment"]["id"]
    firebase.storage.place(
        intent.json()["upload"]["storage_key"], content_type="image/png"
    )
    await client.post(
        f"{API}/attachments/{attachment_id}/finalize",
        headers=chat_setup["user"]["headers"],
    )

    await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"attachment_id": attachment_id},
    )
    again = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"attachment_id": attachment_id},
    )
    assert again.status_code == 422
    assert again.json()["error"]["code"] == "attachment_already_used"


async def test_another_member_cannot_finalise_your_upload(
    client: httpx.AsyncClient, firebase, chat_setup
):
    conversation = await open_conversation(client, chat_setup)
    intent = await client.post(
        f"{API}/conversations/{conversation['id']}/attachments",
        headers=chat_setup["user"]["headers"],
        json={"mime_type": "image/png", "size_bytes": 512},
    )
    firebase.storage.place(
        intent.json()["upload"]["storage_key"], content_type="image/png"
    )

    response = await client.post(
        f"{API}/attachments/{intent.json()['attachment']['id']}/finalize",
        headers=chat_setup["expert"]["headers"],
    )
    assert response.status_code == 404


async def test_stale_intents_are_purged(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory, db_session
):
    """A pending row is a path somebody is still allowed to write to."""
    conversation = await open_conversation(client, chat_setup)
    intent = await client.post(
        f"{API}/conversations/{conversation['id']}/attachments",
        headers=chat_setup["user"]["headers"],
        json={"mime_type": "image/png", "size_bytes": 512},
    )
    attachment_id = uuid.UUID(intent.json()["attachment"]["id"])

    async with session_factory() as session:
        row = await session.scalar(
            select(MediaAttachment).where(MediaAttachment.id == attachment_id)
        )
        row.created_at = datetime.now(UTC) - timedelta(hours=2)
        await session.commit()

    from app.services.chat.attachments import AttachmentService

    async with session_factory() as session:
        purged = await AttachmentService(session, firebase).purge_stale_intents()
        await session.commit()
    assert purged == 1

    async with session_factory() as session:
        row = await session.scalar(
            select(MediaAttachment).where(MediaAttachment.id == attachment_id)
        )
    assert row.status == AttachmentStatus.DELETED.value


# ================================================================== push


async def test_a_message_queues_a_notification_for_the_other_party(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    conversation = await open_conversation(client, chat_setup)
    sent = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "Gizli mesaj içeriği"},
    )
    message_id = sent.json()["message_id"]

    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(NotificationOutbox).where(
                    NotificationOutbox.event_type == "new_chat_message"
                )
            )
        )
    assert len(rows) == 1
    row = rows[0]

    # The other party, not the sender.
    assert row.user_id == chat_setup["expert_user_id"]
    assert row.dedupe_key == f"chat:{message_id}:{chat_setup['expert_user_id']}"

    # And the payload carries no message content: a lock screen is public.
    blob = str(row.payload)
    assert "Gizli mesaj" not in blob
    assert row.payload["data"]["conversation_id"] == conversation["id"]
    assert row.payload["body"] == "Yeni bir mesajın var."


async def test_one_message_one_notification(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    conversation = await open_conversation(client, chat_setup)
    payload = {"text": "retry me", "client_message_id": "retry-1"}

    await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json=payload,
    )
    await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json=payload,
    )

    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(NotificationOutbox).where(
                    NotificationOutbox.event_type == "new_chat_message"
                )
            )
        )
    assert len(rows) == 1, "a retry must not notify twice"


async def test_booking_queues_notifications_and_reminders(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    async with session_factory() as session:
        booked = list(
            await session.scalars(
                select(NotificationOutbox).where(
                    NotificationOutbox.event_type == "appointment_booked"
                )
            )
        )
        reminders = list(
            await session.scalars(
                select(NotificationOutbox).where(
                    NotificationOutbox.event_type == "appointment_reminder"
                )
            )
        )

    # Both parties learn about the booking.
    assert {row.user_id for row in booked} == {
        chat_setup["user_id"],
        chat_setup["expert_user_id"],
    }
    # Reminders are scheduled rows, which is why no separate scheduler exists.
    assert reminders
    assert all(row.scheduled_for is not None for row in reminders)


async def test_cancelling_drops_pending_reminders(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    """A reminder for something that is not happening is worse than none."""
    await client.post(
        f"{API}/orders/{chat_setup['order_id']}/cancel",
        headers=chat_setup["user"]["headers"],
        json={},
    )

    async with session_factory() as session:
        reminders = list(
            await session.scalars(
                select(NotificationOutbox).where(
                    NotificationOutbox.event_type == "appointment_reminder"
                )
            )
        )
    assert reminders
    assert all(row.status == OutboxStatus.SKIPPED.value for row in reminders)


async def test_delivery_sends_to_the_recipients_devices(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    conversation = await open_conversation(client, chat_setup)

    expert_token = "e" * 40
    await client.post(
        f"{API}/devices/push",
        headers=chat_setup["expert"]["headers"],
        json={"token": expert_token, "platform": "android"},
    )
    await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "ping"},
    )

    async with session_factory() as session:
        row = await session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.event_type == "new_chat_message"
            )
        )
        sender = NotificationSender(session, firebase)
        outcome = await sender.deliver(row)
        await session.commit()

    assert outcome.delivered == 1
    assert firebase.push.all_tokens == [expert_token]
    message = firebase.push.last_message()
    assert message.data["conversation_id"] == conversation["id"]
    assert "ping" not in str(message.data) + message.body


async def test_a_dead_token_is_retired_not_retried(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    conversation = await open_conversation(client, chat_setup)
    dead = "d" * 40
    await client.post(
        f"{API}/devices/push",
        headers=chat_setup["expert"]["headers"],
        json={"token": dead, "platform": "ios"},
    )
    firebase.push.dead_tokens.add(dead)

    await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "ping"},
    )

    async with session_factory() as session:
        row = await session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.event_type == "new_chat_message"
            )
        )
        await NotificationSender(session, firebase).deliver(row)
        await session.commit()

    async with session_factory() as session:
        device = await session.scalar(
            select(PushDevice).where(PushDevice.token == dead)
        )
        row = await session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.event_type == "new_chat_message"
            )
        )
    assert device.enabled is False
    assert device.disabled_reason == "unregistered"
    # Retrying a dead token never succeeds, so it is not retried.
    assert row.status == OutboxStatus.FAILED.value


async def test_a_transient_failure_is_retried(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    conversation = await open_conversation(client, chat_setup)
    await clear_outbox(session_factory)
    await client.post(
        f"{API}/devices/push",
        headers=chat_setup["expert"]["headers"],
        json={"token": "t" * 40, "platform": "android"},
    )
    await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "ping"},
    )
    firebase.push.fail_transient_times = 1

    async with session_factory() as session:
        outbox = OutboxService(session)
        row = await outbox.claim_next(worker_id="w1")
        await NotificationSender(session, firebase).deliver(row)

    async with session_factory() as session:
        row = await session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.event_type == "new_chat_message"
            )
        )
    assert row.status == OutboxStatus.PENDING.value
    assert row.attempts == 1

    # The second attempt succeeds.
    async with session_factory() as session:
        outbox = OutboxService(session)
        row = await outbox.claim_next(worker_id="w1")
        outcome = await NotificationSender(session, firebase).deliver(row)
    assert outcome.delivered == 1


async def test_no_devices_is_skipped_not_failed(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    """A user with notifications off is exercising a preference."""
    conversation = await open_conversation(client, chat_setup)
    await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "ping"},
    )

    async with session_factory() as session:
        row = await session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.event_type == "new_chat_message"
            )
        )
        outcome = await NotificationSender(session, firebase).deliver(row)
        await session.commit()

    assert outcome.was_skipped
    async with session_factory() as session:
        row = await session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.event_type == "new_chat_message"
            )
        )
    assert row.status == OutboxStatus.SKIPPED.value


async def test_a_claimed_notification_is_invisible_to_the_next_worker(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    conversation = await open_conversation(client, chat_setup)
    await clear_outbox(session_factory)
    await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "ping"},
    )

    async with session_factory() as session:
        first = await OutboxService(session).claim_next(worker_id="worker-a")
    async with session_factory() as session:
        second = await OutboxService(session).claim_next(worker_id="worker-b")

    assert first is not None
    assert second is None, "the same notification must not be sent twice"


async def test_a_scheduled_notification_waits(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory, db_session
):
    outbox = OutboxService(db_session)
    await outbox.enqueue(
        event=__import__(
            "app.domain.chat", fromlist=["PushEvent"]
        ).PushEvent.APPOINTMENT_REMINDER,
        user_id=chat_setup["user_id"],
        dedupe_key="future-reminder",
        scheduled_for=datetime.now(UTC) + timedelta(hours=2),
    )
    await db_session.commit()

    async with session_factory() as session:
        claimed = await OutboxService(session).claim_next(worker_id="w")
    # Only reminders that are due are claimed.
    assert claimed is None or claimed.dedupe_key != "future-reminder"


async def test_a_dead_worker_releases_its_notification(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory
):
    conversation = await open_conversation(client, chat_setup)
    await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "ping"},
    )

    async with session_factory() as session:
        row = await OutboxService(session).claim_next(worker_id="doomed")
        row.lease_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()

    async with session_factory() as session:
        recovered = await OutboxService(session).recover_stale()
    assert recovered == 1

    async with session_factory() as session:
        reclaimed = await OutboxService(session).claim_next(worker_id="worker-b")
    assert reclaimed is not None


async def test_a_deduped_notification_does_not_roll_back_the_caller(
    client: httpx.AsyncClient, firebase, chat_setup, session_factory, db_session
):
    """The reason enqueuing uses a savepoint rather than the transaction.

    Enqueuing is a side effect of somebody else's business transaction: booking
    notifies two people, and a dedupe on the second must not undo the
    appointment. An earlier version called `session.rollback()` here, which
    discarded the caller's work and expired every object they still held - which
    is how a deduped chat notification turned into a 500.

    The cheap pre-check is bypassed so the INSERT really collides, because that
    is the path a race takes and the only one that reaches the savepoint.
    """
    from app.domain.chat import PushEvent

    key = "savepoint-probe"
    outbox = OutboxService(db_session)
    assert await outbox.enqueue(
        event=PushEvent.ORDER_STATUS_CHANGED,
        user_id=chat_setup["user_id"],
        dedupe_key=key,
    )
    await db_session.commit()

    # The caller's own pending, uncommitted work.
    pending = PushDevice(
        user_id=chat_setup["user_id"],
        platform="android",
        token="caller-work-" + "z" * 30,
        enabled=True,
    )
    db_session.add(pending)
    await db_session.flush()

    # Force the collision: pretend the pre-check found nothing.
    real_scalar = db_session.scalar

    async def blind_once(*args, **kwargs):
        db_session.scalar = real_scalar
        return None

    db_session.scalar = blind_once
    try:
        second = await outbox.enqueue(
            event=PushEvent.ORDER_STATUS_CHANGED,
            user_id=chat_setup["user_id"],
            dedupe_key=key,
        )
    finally:
        db_session.scalar = real_scalar

    # Deduped, not raised.
    assert second is None

    # The caller's object is still live and still theirs - not expired, not
    # rolled back. Reading an attribute here is the exact thing that used to
    # raise MissingGreenlet.
    assert pending.token.startswith("caller-work-")
    assert pending in db_session
    await db_session.commit()

    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(NotificationOutbox).where(
                    NotificationOutbox.dedupe_key == key
                )
            )
        )
        kept = await session.scalar(
            select(PushDevice).where(PushDevice.token == pending.token)
        )
    assert len(rows) == 1, "one event, one notification row"
    assert kept is not None, "the caller's work was rolled back"


# ================================================================ devices


async def test_device_registration_is_idempotent_and_private(
    client: httpx.AsyncClient, firebase, registered
):
    token = "a" * 50
    first = await client.post(
        f"{API}/devices/push",
        headers=registered["headers"],
        json={"token": token, "platform": "android", "device_id": "handset-1"},
    )
    assert first.status_code == 201
    # The token is never echoed back.
    assert token not in first.text
    assert first.json()["token_fingerprint"].endswith("…")

    second = await client.post(
        f"{API}/devices/push",
        headers=registered["headers"],
        json={"token": token, "platform": "android"},
    )
    assert second.json()["id"] == first.json()["id"]

    listed = await client.get(f"{API}/devices/push", headers=registered["headers"])
    assert len(listed.json()) == 1
    assert token not in listed.text


async def test_a_push_token_is_never_logged(
    client: httpx.AsyncClient, firebase, registered, monkeypatch
):
    """And the fingerprint survives redaction, which is the point of having one.

    The redaction processor replaces anything keyed `token` with `[redacted]`,
    so logging the masked value under that key would throw away the one thing
    here that is safe to keep - and a fingerprint nobody can read is not a
    support tool.
    """
    from app.services.notifications import devices as module

    recorded: list[tuple[str, dict]] = []

    class Recorder:
        def info(self, event, **fields):
            recorded.append((event, fields))

    monkeypatch.setattr(module, "logger", Recorder())

    token = "f" * 60
    await client.post(
        f"{API}/devices/push",
        headers=registered["headers"],
        json={"token": token, "platform": "ios", "device_id": "handset-serial-1"},
    )

    assert recorded
    event, fields = recorded[-1]
    assert event == "push_device_registered"

    blob = repr(fields)
    assert token not in blob, "the raw push token reached a log line"
    # The raw handset identifier is not logged either, hashed or otherwise.
    assert "handset-serial-1" not in blob
    assert "token" not in fields, "a field keyed `token` would be redacted away"
    assert fields["token_fingerprint"].endswith("\u2026")


async def test_another_user_cannot_delete_your_device(
    client: httpx.AsyncClient, firebase, registered
):
    created = await client.post(
        f"{API}/devices/push",
        headers=registered["headers"],
        json={"token": "b" * 50, "platform": "ios"},
    )
    stranger = await register(client, "device-thief@example.com")

    response = await client.delete(
        f"{API}/devices/push/{created.json()['id']}", headers=stranger["headers"]
    )
    assert response.status_code == 404

    # And a stranger's list is empty rather than everybody's.
    listed = await client.get(f"{API}/devices/push", headers=stranger["headers"])
    assert listed.json() == []


async def test_a_token_moves_rather_than_duplicating(
    client: httpx.AsyncClient, firebase, registered, session_factory
):
    """A shared handset must not keep notifying the previous user."""
    token = "c" * 50
    await client.post(
        f"{API}/devices/push",
        headers=registered["headers"],
        json={"token": token, "platform": "android"},
    )
    second = await register(client, "handset-sharer@example.com")
    await client.post(
        f"{API}/devices/push",
        headers=second["headers"],
        json={"token": token, "platform": "android"},
    )

    async with session_factory() as session:
        rows = list(
            await session.scalars(select(PushDevice).where(PushDevice.token == token))
        )
        owner = await session.scalar(
            select(User).where(User.email == "handset-sharer@example.com")
        )
    assert len(rows) == 1
    assert rows[0].user_id == owner.id


async def test_a_short_token_is_refused(client: httpx.AsyncClient, firebase, registered):
    response = await client.post(
        f"{API}/devices/push",
        headers=registered["headers"],
        json={"token": "short", "platform": "web"},
    )
    assert response.status_code == 422


# ============================================================ rate limits


@pytest.fixture
def tight_limits(monkeypatch):
    """Small, test-only quotas. Never the production numbers."""
    from app.api.v1 import chat as chat_routes
    from app.core.rate_limit import Quota

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    for limit, allowance in (
        (chat_routes._message_limit, 2),
        (chat_routes._conversation_limit, 1),
        (chat_routes._attachment_limit, 1),
        (chat_routes._device_limit, 1),
    ):
        monkeypatch.setattr(
            limit.dependency, "quota", Quota(limit=allowance, window_seconds=60)
        )


async def test_the_message_quota_is_enforced(
    client: httpx.AsyncClient, firebase, chat_setup, tight_limits
):
    """Chat is a channel to a paid expert; it is also a channel to spam one."""
    conversation = await open_conversation(client, chat_setup)

    for index in range(2):
        allowed = await client.post(
            f"{API}/conversations/{conversation['id']}/messages",
            headers=chat_setup["user"]["headers"],
            json={"text": f"message {index}"},
        )
        assert allowed.status_code == 201

    blocked = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "one too many"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["details"]["scope"] == "message_send"

    retry_after = blocked.headers.get("retry-after")
    assert retry_after is not None, "a 429 must say how long to wait"
    assert 0 < int(retry_after) <= 60


async def test_the_quota_is_per_user_not_per_conversation(
    client: httpx.AsyncClient, firebase, chat_setup, tight_limits
):
    """Keyed by account. Otherwise opening a second thread resets the limit."""
    conversation = await open_conversation(client, chat_setup)
    for index in range(2):
        await client.post(
            f"{API}/conversations/{conversation['id']}/messages",
            headers=chat_setup["user"]["headers"],
            json={"text": f"message {index}"},
        )

    # The expert has spent none of their own allowance.
    theirs = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["expert"]["headers"],
        json={"text": "reply"},
    )
    assert theirs.status_code == 201


async def test_the_device_quota_is_a_separate_scope(
    client: httpx.AsyncClient, firebase, chat_setup, tight_limits
):
    first = await client.post(
        f"{API}/devices/push",
        headers=chat_setup["user"]["headers"],
        json={"token": "q" * 40, "platform": "android"},
    )
    assert first.status_code == 201

    blocked = await client.post(
        f"{API}/devices/push",
        headers=chat_setup["user"]["headers"],
        json={"token": "r" * 40, "platform": "ios"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["details"]["scope"] == "device_register"

    # And registering a device has not consumed the message allowance.
    conversation = await open_conversation(client, chat_setup)
    sent = await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": "still allowed"},
    )
    assert sent.status_code == 201


# =============================================================== presence


async def test_presence_is_only_visible_to_a_partner(
    client: httpx.AsyncClient, firebase, chat_setup
):
    conversation = await open_conversation(client, chat_setup)
    firebase.presence.presence["uid-chat-expert"] = True

    seen = await client.get(
        f"{API}/conversations/{conversation['id']}/presence",
        headers=chat_setup["user"]["headers"],
    )
    assert seen.status_code == 200
    states = {row["firebase_uid"]: row["online"] for row in seen.json()}
    assert states["uid-chat-expert"] is True

    # There is no endpoint that reads presence by uid, and a stranger cannot
    # reach the conversation's.
    stranger = await register(client, "watcher@example.com")
    refused = await client.get(
        f"{API}/conversations/{conversation['id']}/presence",
        headers=stranger["headers"],
    )
    assert refused.status_code == 404


async def test_presence_visibility_is_projected_for_the_rtdb_rules(
    client: httpx.AsyncClient, firebase, chat_setup
):
    """The client path, not the API path.

    A client subscribes to `presence/{partnerUid}`, which names no
    conversation, so the RTDB rules gate it on `presenceVisibility`. If the
    backend never writes that node the rules deny every listener and nobody
    ever appears online - while this endpoint keeps working, because the Admin
    SDK bypasses rules. So the projection is asserted directly.
    """
    conversation = await open_conversation(client, chat_setup)

    assert firebase.presence.may_see("uid-chat-expert", "uid-chat-user")
    assert firebase.presence.may_see("uid-chat-user", "uid-chat-expert")
    # And it is not a global grant.
    assert not firebase.presence.may_see("uid-nobody", "uid-chat-user")

    # The close endpoint removes the grant, not just the message permission.
    closed = await client.post(
        f"{API}/conversations/{conversation['id']}/close",
        headers=chat_setup["user"]["headers"],
        json={"reason": "done"},
    )
    assert closed.status_code == 200
    assert not firebase.presence.may_see("uid-chat-expert", "uid-chat-user")


# ================================================================ privacy


async def test_message_content_is_never_logged(
    client: httpx.AsyncClient, firebase, chat_setup, monkeypatch
):
    from app.services.chat import conversations as module

    recorded: list[tuple[str, dict]] = []

    class Recorder:
        def info(self, event, **fields):
            recorded.append((event, fields))

        def warning(self, event, **fields):
            recorded.append((event, fields))

    conversation = await open_conversation(client, chat_setup)
    monkeypatch.setattr(module, "logger", Recorder())

    secret = "Doğum tarihim 1990-04-04, Deniz ile ilişkim hakkında"
    await client.post(
        f"{API}/conversations/{conversation['id']}/messages",
        headers=chat_setup["user"]["headers"],
        json={"text": secret},
    )

    assert recorded
    event, fields = recorded[-1]
    assert event == "chat_message_sent"

    blob = repr(fields)
    assert secret not in blob
    assert "Deniz" not in blob
    assert "1990-04-04" not in blob
    assert "text" not in fields
    # The structural facts remain, to debug with.
    assert set(fields) >= {"conversation_id", "message_id", "sender_role"}


async def test_the_chat_policy_is_published(client: httpx.AsyncClient, firebase, registered):
    response = await client.get(f"{API}/chat/policy", headers=registered["headers"])
    assert response.status_code == 200
    body = response.json()

    assert "pending_payment" not in body["writable_order_states"]
    assert "completed" in body["readable_order_states"]
    assert body["message_max_length"] == settings.chat_message_max_length
    assert "image/jpeg" in body["attachment_allowed_mime_types"]
