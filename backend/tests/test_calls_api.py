"""Voice and video calls: authorisation, lifecycle, webhooks and the invariants.

The properties worth breaking a build over:

* **A call exists because a paid, scheduled order does.** Not because somebody
  knows an expert's id, and not before payment.
* **Nothing reaches LiveKit before every business check has passed**, on every
  token, including reissues.
* **Only provider events make a call ACTIVE.** A client cannot declare a call
  started, and a forged webhook is refused.
* **Tokens are least-privilege, short-lived, and never logged.** An audio
  consultation cannot publish video; nobody can publish data or administer the
  room.
* **The lock screen learns nothing.** Incoming-call pushes carry an id and a
  type.

The provider is the in-memory fake - but its tokens and webhook signatures are
LiveKit's real ones, minted and verified by the SDK with a test key pair.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, time, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.models.calls import CallParticipant, CallProviderEvent, CallSession
from app.db.models.chat import NotificationOutbox
from app.db.models.marketplace import (
    Appointment,
    Expert,
    ExpertAvailability,
    ExpertService,
    ServiceOrder,
)
from app.db.models.service import ServiceDefinition
from app.db.models.user import User
from app.domain.calls import CallEndReason, CallStatus, ParticipantStatus
from app.domain.marketplace import (
    AppointmentStatus,
    DeliveryType,
    ExpertStatus,
    FulfillmentMode,
    OrderStatus,
    PaymentStatus,
)
from app.services.calls import factory as call_factory
from app.services.calls.fake_provider import (
    FAKE_API_KEY,
    FAKE_API_SECRET,
    FakeRealtimeCommunicationProvider,
)
from app.services.calls.service import CallService

API = "/api/v1"


# ================================================================ fixtures


@pytest.fixture
def lk(monkeypatch):
    """The fake LiveKit, installed as the provider."""
    monkeypatch.setattr(settings, "realtime_provider", "fake")
    provider = FakeRealtimeCommunicationProvider()
    call_factory.set_call_provider(provider)
    yield provider
    call_factory.set_call_provider(None)


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
    return {"headers": {"Authorization": f"Bearer {response.json()['access_token']}"}}


@pytest.fixture
async def world(client: httpx.AsyncClient, lk, session_factory):
    """A user, an expert, and offerings for every channel."""
    from app.services.catalog.service import CatalogService

    user = await register(client, "caller@example.com")
    expert = await register(client, "callexpert@example.com")

    async with session_factory() as session:
        await CatalogService(session).seed()
        await session.commit()
        definition = await session.scalar(
            select(ServiceDefinition)
            .where(
                ServiceDefinition.supports_voice.is_(True),
                ServiceDefinition.supports_video.is_(True),
                ServiceDefinition.supports_appointment.is_(True),
                ServiceDefinition.active.is_(True),
            )
            .limit(1)
        )
        user_row = await session.scalar(
            select(User).where(User.email == "caller@example.com")
        )
        expert_user = await session.scalar(
            select(User).where(User.email == "callexpert@example.com")
        )
        profile = Expert(
            user_id=expert_user.id,
            display_name="Call Expert",
            languages=["tr"],
            specialties=["astrology"],
            experience_years=5,
            timezone="Europe/Istanbul",
            status=ExpertStatus.ACTIVE.value,
            verified=True,
            rating_average=0,
            rating_count=0,
        )
        session.add(profile)
        await session.flush()

        offerings = {}
        for delivery in (DeliveryType.VIDEO, DeliveryType.VOICE, DeliveryType.CHAT):
            row = ExpertService(
                expert_id=profile.id,
                service_definition_id=definition.id,
                title=f"{delivery.value} consultation",
                delivery_type=delivery.value,
                duration_minutes=60,
                price_minor=10000,
                currency="TRY",
                active=True,
            )
            session.add(row)
            await session.flush()
            offerings[delivery] = row.id
        session.add(
            ExpertAvailability(
                expert_id=profile.id,
                weekday=0,
                start_local_time=time(0, 0),
                end_local_time=time(23, 0),
                timezone="Europe/Istanbul",
                active=True,
            )
        )
        await session.commit()

        return {
            "user": user,
            "expert": expert,
            "user_id": user_row.id,
            "expert_user_id": expert_user.id,
            "expert_id": profile.id,
            "definition_id": definition.id,
            "offerings": offerings,
        }


async def make_order(
    session_factory,
    world: dict,
    *,
    delivery: DeliveryType = DeliveryType.VIDEO,
    price_minor: int = 10000,
    status: OrderStatus = OrderStatus.CONFIRMED,
    payment: PaymentStatus | None = None,
    start_in: timedelta = timedelta(minutes=-5),
    duration: timedelta = timedelta(minutes=60),
    with_appointment: bool = True,
) -> dict:
    """An order in a known state, written directly.

    Deliberately not through `POST /orders`: no payment provider exists, so the
    only way a priced order becomes PAID today is a fixture like this one. The
    production endpoint never does it.
    """
    if payment is None:
        payment = PaymentStatus.PAID if price_minor else PaymentStatus.NOT_REQUIRED
    now = datetime.now(UTC)
    async with session_factory() as session:
        order = ServiceOrder(
            user_id=world["user_id"],
            service_definition_id=world["definition_id"],
            expert_id=world["expert_id"],
            expert_service_id=world["offerings"][delivery],
            fulfillment_mode=FulfillmentMode.EXPERT.value,
            delivery_type=delivery.value,
            status=status.value,
            payment_status=payment.value,
            subtotal_minor=price_minor,
            discount_minor=0,
            total_minor=price_minor,
            currency="TRY",
            commission_basis_points=2000,
            platform_fee_minor=price_minor // 5,
            expert_net_minor=price_minor - price_minor // 5,
            service_title="Consultation",
            service_duration_minutes=60,
        )
        session.add(order)
        await session.flush()
        appointment_id = None
        if with_appointment:
            appointment = Appointment(
                user_id=world["user_id"],
                expert_id=world["expert_id"],
                expert_service_id=world["offerings"][delivery],
                service_order_id=order.id,
                starts_at_utc=now + start_in,
                ends_at_utc=now + start_in + duration,
                timezone="Europe/Istanbul",
                status=AppointmentStatus.CONFIRMED.value,
            )
            session.add(appointment)
            await session.flush()
            appointment_id = appointment.id
        await session.commit()
        return {"order_id": order.id, "appointment_id": appointment_id}


async def open_call(client, world, order, *, as_role="user", call_type="video"):
    return await client.post(
        f"{API}/calls",
        headers=world[as_role]["headers"],
        json={"order_id": str(order["order_id"]), "call_type": call_type},
    )


async def room_and_identities(session_factory, call_id) -> tuple[str, dict[str, str]]:
    async with session_factory() as session:
        call = await session.scalar(
            select(CallSession).where(CallSession.id == uuid.UUID(str(call_id)))
        )
        parts = list(
            await session.scalars(
                select(CallParticipant).where(
                    CallParticipant.call_session_id == call.id
                )
            )
        )
        return call.provider_room_name, {p.role: p.provider_identity for p in parts}


def webhook_body(
    event: str,
    *,
    room: str | None,
    identity: str | None = None,
    reason: str | None = None,
    event_id: str | None = None,
    at: datetime | None = None,
) -> bytes:
    """A webhook body in LiveKit's protobuf-JSON shape."""
    payload: dict = {
        "event": event,
        "id": event_id or f"EV_{uuid.uuid4().hex}",
        "createdAt": str(int((at or datetime.now(UTC)).timestamp())),
    }
    if room:
        payload["room"] = {"name": room, "sid": "RM_x"}
    if identity:
        participant = {"identity": identity, "sid": "PA_x", "name": "ignored name"}
        if reason:
            participant["disconnectReason"] = reason
        payload["participant"] = participant
    return json.dumps(payload).encode()


async def send_webhook(client, lk, body: bytes, *, authorization: str | None = "sign"):
    """Deliver a webhook - and keep the fake room consistent with it.

    A real LiveKit room contains whoever joined; the fake only knows what it is
    told. Mirroring joins and leaves keeps "ask the provider" honest in tests.
    """
    payload = json.loads(body)
    room = (payload.get("room") or {}).get("name")
    identity = (payload.get("participant") or {}).get("identity")
    reason = (payload.get("participant") or {}).get("disconnectReason")
    if authorization == "sign" and room and identity:
        if payload["event"] == "participant_joined":
            lk.join(room, identity)
        elif payload["event"] == "participant_left" and reason != "DUPLICATE_IDENTITY":
            lk.leave(room, identity)
    headers = {"Content-Type": "application/webhook+json"}
    if authorization == "sign":
        headers["Authorization"] = lk.signed_webhook(body)
    elif authorization is not None:
        headers["Authorization"] = authorization
    return await client.post(f"{API}/webhooks/livekit", content=body, headers=headers)


async def load_call(session_factory, call_id) -> CallSession:
    async with session_factory() as session:
        return await session.scalar(
            select(CallSession).where(CallSession.id == uuid.UUID(str(call_id)))
        )


async def advance(session_factory, lk, call_id, at: datetime) -> CallSession:
    """Run the clock forward to `at` the way the worker would."""
    async with session_factory() as session:
        service = CallService(session, lk)
        call = await session.scalar(
            select(CallSession).where(CallSession.id == uuid.UUID(str(call_id)))
        )
        await service.advance(call, at)
        await session.commit()
    return await load_call(session_factory, call_id)


async def outbox_rows(session_factory, event_type: str) -> list[NotificationOutbox]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(NotificationOutbox).where(
                    NotificationOutbox.event_type == event_type
                )
            )
        )


def decode(token: str):
    from livekit import api

    return api.TokenVerifier(FAKE_API_KEY, FAKE_API_SECRET).verify(token)


# ============================================================ configuration


async def test_status_says_only_configured_and_provider(
    client: httpx.AsyncClient, world
):
    response = await client.get(f"{API}/calls/status", headers=world["user"]["headers"])
    assert response.status_code == 200
    assert response.json() == {"configured": True, "provider": "fake"}


async def test_without_livekit_calls_answer_503_and_nothing_else_breaks(
    client: httpx.AsyncClient, registered, monkeypatch
):
    monkeypatch.setattr(settings, "realtime_provider", "livekit")
    monkeypatch.setattr(settings, "livekit_url", None)
    monkeypatch.setattr(settings, "livekit_api_key", None)
    monkeypatch.setattr(settings, "livekit_api_secret", None)
    call_factory.set_call_provider(None)
    try:
        response = await client.post(
            f"{API}/calls",
            headers=registered["headers"],
            json={"order_id": str(uuid.uuid4()), "call_type": "audio"},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "call_provider_not_configured"

        status = await client.get(f"{API}/calls/status", headers=registered["headers"])
        assert status.json() == {"configured": False, "provider": "livekit"}

        hook = await client.post(f"{API}/webhooks/livekit", content=b"{}")
        assert hook.status_code == 503

        # The rest of the product is unaffected.
        chart = await client.get(
            f"{API}/astrology/natal-chart/me", headers=registered["headers"]
        )
        assert chart.status_code == 200
    finally:
        call_factory.set_call_provider(None)


def test_production_refuses_the_fake_provider(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "cors_origins", "https://app.example")
    monkeypatch.setattr(settings, "jwt_secret", "x" * 40)
    monkeypatch.setattr(settings, "jwt_refresh_secret", "y" * 40)
    monkeypatch.setattr(settings, "realtime_provider", "fake")
    with pytest.raises(RuntimeError, match="REALTIME_PROVIDER=fake"):
        settings.assert_production_ready()


def test_production_refuses_plaintext_livekit(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "cors_origins", "https://app.example")
    monkeypatch.setattr(settings, "jwt_secret", "x" * 40)
    monkeypatch.setattr(settings, "jwt_refresh_secret", "y" * 40)
    monkeypatch.setattr(settings, "realtime_provider", "livekit")
    monkeypatch.setattr(settings, "livekit_url", "ws://livekit.example")
    with pytest.raises(RuntimeError, match="wss://"):
        settings.assert_production_ready()


# ============================================================ authorisation


async def test_the_user_opens_a_call_and_the_expert_gets_the_same_one(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)

    first = await open_call(client, world, order)
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["status"] == "waiting"
    assert body["my_role"] == "user"
    assert "token" not in body

    second = await open_call(client, world, order, as_role="expert")
    assert second.status_code == 200
    assert second.json()["id"] == body["id"]
    assert second.json()["my_role"] == "expert"

    # One room, and it is opaque.
    room, identities = await room_and_identities(session_factory, body["id"])
    assert room.startswith("call_") and len(room) == 29
    assert list(lk.rooms) == [room]
    assert lk.rooms[room].spec.max_participants == 2
    for identity in identities.values():
        assert identity.startswith("p_")
        assert str(world["user_id"]) not in identity
        assert "@" not in identity


async def test_repeated_creates_converge_on_one_session(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(session_factory, world)
    ids = set()
    for index in range(10):
        response = await open_call(
            client, world, order, as_role="user" if index % 2 else "expert"
        )
        assert response.status_code in (200, 201)
        ids.add(response.json()["id"])
    assert len(ids) == 1

    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(CallSession).where(CallSession.order_id == order["order_id"])
            )
        )
    assert len(rows) == 1


async def test_the_database_refuses_a_second_live_call(
    client: httpx.AsyncClient, world, session_factory
):
    """The partial unique index, not the application, is the guarantee."""
    order = await make_order(session_factory, world)
    created = await open_call(client, world, order)
    existing = await load_call(session_factory, created.json()["id"])

    async with session_factory() as session:
        session.add(
            CallSession(
                order_id=existing.order_id,
                user_id=existing.user_id,
                expert_id=existing.expert_id,
                expert_user_id=existing.expert_user_id,
                created_by_user_id=existing.user_id,
                call_type="audio",
                status=CallStatus.WAITING.value,
                provider="fake",
                provider_room_name="call_second",
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()


async def test_a_stranger_cannot_open_a_call_on_someone_elses_order(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(session_factory, world)
    stranger = await register(client, "stranger@example.com")
    response = await client.post(
        f"{API}/calls",
        headers=stranger["headers"],
        json={"order_id": str(order["order_id"]), "call_type": "video"},
    )
    assert response.status_code == 404


async def test_another_expert_is_not_the_orders_expert(
    client: httpx.AsyncClient, world, session_factory
):
    """An expert profile is not a credential for somebody else's order."""
    order = await make_order(session_factory, world)
    rival = await register(client, "rival@example.com")
    async with session_factory() as session:
        rival_user = await session.scalar(
            select(User).where(User.email == "rival@example.com")
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
                verified=True,
                rating_average=0,
                rating_count=0,
            )
        )
        await session.commit()

    response = await client.post(
        f"{API}/calls",
        headers=rival["headers"],
        json={"order_id": str(order["order_id"]), "call_type": "video"},
    )
    assert response.status_code == 404


async def test_an_unknown_order_is_404(client: httpx.AsyncClient, world):
    response = await client.post(
        f"{API}/calls",
        headers=world["user"]["headers"],
        json={"order_id": str(uuid.uuid4()), "call_type": "video"},
    )
    assert response.status_code == 404


async def test_a_mismatched_appointment_is_refused(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(session_factory, world)
    response = await client.post(
        f"{API}/calls",
        headers=world["user"]["headers"],
        json={
            "order_id": str(order["order_id"]),
            "appointment_id": str(uuid.uuid4()),
            "call_type": "video",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["details"]["reason"] == "appointment_mismatch"


async def test_a_chat_order_has_no_call(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(session_factory, world, delivery=DeliveryType.CHAT)
    for call_type in ("audio", "video"):
        response = await open_call(client, world, order, call_type=call_type)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "call_type_not_supported"


async def test_a_voice_order_allows_audio_but_not_video(
    client: httpx.AsyncClient, world, session_factory
):
    """Video on a voice order is an upgrade nobody paid for."""
    order = await make_order(session_factory, world, delivery=DeliveryType.VOICE)
    video = await open_call(client, world, order, call_type="video")
    assert video.status_code == 422
    assert video.json()["error"]["code"] == "call_type_not_supported"

    audio = await open_call(client, world, order, call_type="audio")
    assert audio.status_code == 201


async def test_a_video_order_allows_an_audio_call(
    client: httpx.AsyncClient, world, session_factory
):
    """Audio on a video order is a downgrade the customer may choose."""
    order = await make_order(session_factory, world, delivery=DeliveryType.VIDEO)
    response = await open_call(client, world, order, call_type="audio")
    assert response.status_code == 201


async def test_an_unpaid_priced_order_cannot_call(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(
        session_factory,
        world,
        status=OrderStatus.CONFIRMED,
        payment=PaymentStatus.PENDING,
    )
    response = await open_call(client, world, order)
    assert response.status_code == 403
    assert response.json()["error"]["details"]["reason"] == "payment_required"


async def test_a_priced_order_claiming_not_required_cannot_call(
    client: httpx.AsyncClient, world, session_factory
):
    """`not_required` counts only when the order is actually free."""
    order = await make_order(
        session_factory, world, payment=PaymentStatus.NOT_REQUIRED
    )
    response = await open_call(client, world, order)
    assert response.status_code == 403
    assert response.json()["error"]["details"]["reason"] == "payment_required"


async def test_a_free_order_can_call(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(session_factory, world, price_minor=0)
    response = await open_call(client, world, order)
    assert response.status_code == 201


async def test_pending_payment_is_not_callable(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(
        session_factory,
        world,
        status=OrderStatus.PENDING_PAYMENT,
        payment=PaymentStatus.PENDING,
    )
    response = await open_call(client, world, order)
    assert response.status_code == 403
    assert response.json()["error"]["details"]["reason"] == "order_state_pending_payment"


async def test_an_appointment_service_needs_its_appointment(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(session_factory, world, with_appointment=False)
    response = await open_call(client, world, order)
    assert response.status_code == 403
    assert response.json()["error"]["details"]["reason"] == "appointment_required"


async def test_a_deleted_counterpart_means_no_call(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(session_factory, world)
    async with session_factory() as session:
        expert_user = await session.scalar(
            select(User).where(User.id == world["expert_user_id"])
        )
        expert_user.deleted_at = datetime.now(UTC)
        await session.commit()

    response = await open_call(client, world, order)
    assert response.status_code == 403
    assert response.json()["error"]["details"]["reason"] == "participant_unavailable"


# ================================================================== window


async def test_too_early_is_scheduled_and_cannot_be_joined(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world, start_in=timedelta(hours=5))
    created = await open_call(client, world, order)
    assert created.status_code == 201
    assert created.json()["status"] == "scheduled"
    # No room exists before the window opens.
    assert lk.rooms == {}

    join = await client.post(
        f"{API}/calls/{created.json()['id']}/join", headers=world["user"]["headers"]
    )
    assert join.status_code == 409
    assert join.json()["error"]["code"] == "call_too_early"
    assert "opens_at" in join.json()["error"]["details"]


async def test_the_window_opens_early_seconds_before_the_start(
    client: httpx.AsyncClient, world, session_factory
):
    inside = timedelta(seconds=settings.call_join_early_seconds - 60)
    order = await make_order(session_factory, world, start_in=inside)
    created = await open_call(client, world, order)
    join = await client.post(
        f"{API}/calls/{created.json()['id']}/join", headers=world["user"]["headers"]
    )
    assert join.status_code == 200, join.text


async def test_after_the_window_there_is_no_call(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(
        session_factory,
        world,
        start_in=-timedelta(hours=3),
        duration=timedelta(minutes=45),
    )
    response = await open_call(client, world, order)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "call_window_closed"


async def test_late_is_measured_from_the_end_so_a_dropped_caller_can_rejoin(
    client: httpx.AsyncClient, world, session_factory
):
    """30 minutes into a 45 minute consultation is inside the window."""
    order = await make_order(
        session_factory,
        world,
        start_in=-timedelta(minutes=30),
        duration=timedelta(minutes=45),
    )
    created = await open_call(client, world, order)
    join = await client.post(
        f"{API}/calls/{created.json()['id']}/join", headers=world["user"]["headers"]
    )
    assert join.status_code == 200


# =================================================================== tokens


async def test_a_video_token_is_least_privilege(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(session_factory, world)
    created = await open_call(client, world, order)
    join = await client.post(
        f"{API}/calls/{created.json()['id']}/join", headers=world["user"]["headers"]
    )
    assert join.status_code == 200
    body = join.json()

    room, identities = await room_and_identities(session_factory, body["call_id"])
    claims = decode(body["token"])
    grants = claims.video

    assert claims.identity == identities["user"] == body["participant_identity"]
    assert grants.room_join is True
    assert grants.room == room
    assert grants.can_subscribe is True
    assert sorted(grants.can_publish_sources) == ["camera", "microphone"]
    # No data channel: chat lives in Firestore.
    assert grants.can_publish_data is False
    assert not grants.can_update_own_metadata
    # No administration of any kind.
    assert not grants.room_admin
    assert not grants.room_create
    assert not grants.room_list
    assert not grants.room_record
    # No name and no metadata travel in the token.
    assert claims.name == ""
    assert claims.metadata == ""
    assert body["room_options"] == {"audio": True, "video": True}
    assert body["livekit_url"].startswith("wss://")


async def test_an_audio_token_cannot_publish_a_camera(
    client: httpx.AsyncClient, world, session_factory
):
    """`canPublishSources` is enforced by LiveKit, not by the client UI."""
    order = await make_order(session_factory, world, delivery=DeliveryType.VOICE)
    created = await open_call(client, world, order, call_type="audio")
    join = await client.post(
        f"{API}/calls/{created.json()['id']}/join", headers=world["user"]["headers"]
    )
    grants = decode(join.json()["token"]).video
    assert grants.can_publish_sources == ["microphone"]
    assert join.json()["room_options"] == {"audio": True, "video": False}


async def test_the_token_is_short_lived_and_not_cached(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(session_factory, world)
    created = await open_call(client, world, order)
    join = await client.post(
        f"{API}/calls/{created.json()['id']}/join", headers=world["user"]["headers"]
    )
    assert "no-store" in join.headers["cache-control"]

    expires = datetime.fromisoformat(join.json()["token_expires_at"])
    remaining = (expires - datetime.now(UTC)).total_seconds()
    # LiveKit's own default is six hours; ours is minutes.
    assert 0 < remaining <= settings.call_token_ttl_seconds + 2


async def test_no_token_outlives_the_window(
    client: httpx.AsyncClient, world, session_factory
):
    # The window closes two minutes from now.
    closes_in = 120
    order = await make_order(
        session_factory,
        world,
        start_in=-timedelta(minutes=60),
        duration=timedelta(seconds=60 * 60 + closes_in - settings.call_join_late_seconds),
    )
    created = await open_call(client, world, order)
    join = await client.post(
        f"{API}/calls/{created.json()['id']}/join", headers=world["user"]["headers"]
    )
    expires = datetime.fromisoformat(join.json()["token_expires_at"])
    assert (expires - datetime.now(UTC)).total_seconds() <= closes_in + 2


async def test_each_reissue_is_reauthorised(
    client: httpx.AsyncClient, world, session_factory
):
    """A token that expired before connecting may be reissued - but only if
    everything that allowed the first one still holds."""
    order = await make_order(session_factory, world)
    created = await open_call(client, world, order)
    call_id = created.json()["id"]

    first = await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
    second = await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
    assert first.status_code == second.status_code == 200
    # Same identity: a reconnect is the same participant, not a new one.
    assert first.json()["participant_identity"] == second.json()["participant_identity"]

    # The order is refunded in the meantime.
    async with session_factory() as session:
        row = await session.scalar(
            select(ServiceOrder).where(ServiceOrder.id == order["order_id"])
        )
        row.status = OrderStatus.REFUNDED.value
        row.payment_status = PaymentStatus.REFUNDED.value
        await session.commit()

    third = await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
    assert third.status_code == 403
    assert third.json()["error"]["code"] == "call_not_allowed"


async def test_the_two_parties_get_different_identities(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    mine = await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
    theirs = await client.post(f"{API}/calls/{call_id}/join", headers=world["expert"]["headers"])
    assert mine.json()["participant_identity"] != theirs.json()["participant_identity"]
    assert theirs.json()["role"] == "expert"


async def test_tokens_and_secrets_are_never_logged(
    client: httpx.AsyncClient, world, session_factory, monkeypatch
):
    from app.api.v1 import calls as calls_routes
    from app.services.calls import livekit_provider, service as service_module

    recorded: list[tuple[str, dict]] = []

    class Recorder:
        def _record(self, event, *args, **fields):
            recorded.append((event, fields))

        info = warning = error = exception = debug = _record

    for module in (calls_routes, service_module, livekit_provider):
        monkeypatch.setattr(module, "logger", Recorder())

    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    join = await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
    token = join.json()["token"]

    events = [event for event, _ in recorded]
    assert "call_created" in events
    assert "call_token_issued" in events

    blob = repr(recorded)
    assert token not in blob
    assert token.split(".")[2] not in blob  # not even the signature
    assert FAKE_API_SECRET not in blob
    assert "Person" not in blob
    assert "caller@example.com" not in blob

    issued = next(fields for event, fields in recorded if event == "call_token_issued")
    assert set(issued) >= {"call_id", "participant_id", "role", "ttl_seconds", "latency_ms"}


async def test_a_normal_call_response_carries_no_token_or_identity(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
    room, identities = await room_and_identities(session_factory, call_id)

    view = await client.get(f"{API}/calls/{call_id}", headers=world["expert"]["headers"])
    text = view.text
    assert "token" not in view.json()
    for identity in identities.values():
        assert identity not in text
    assert room not in text  # the room name is not exposed either


# ========================================================= provider trouble


async def test_room_failure_records_a_failed_call_and_touches_no_order(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    lk.fail_create_room = True

    response = await open_call(client, world, order)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "call_provider_unavailable"
    failed_id = response.json()["error"]["details"]["call_id"]

    failed = await load_call(session_factory, failed_id)
    assert failed.status == CallStatus.FAILED.value
    assert failed.provider_error_code == "call_provider_unavailable"
    assert failed.end_reason == CallEndReason.PROVIDER_ERROR.value

    async with session_factory() as session:
        row = await session.scalar(
            select(ServiceOrder).where(ServiceOrder.id == order["order_id"])
        )
        appointment = await session.scalar(
            select(Appointment).where(Appointment.id == order["appointment_id"])
        )
    assert row.status == OrderStatus.CONFIRMED.value
    assert appointment.status == AppointmentStatus.CONFIRMED.value

    # The provider recovers; opening again is a new attempt.
    lk.fail_create_room = False
    retry = await open_call(client, world, order)
    assert retry.status_code == 201
    assert retry.json()["id"] != failed_id


async def test_an_outage_at_join_leaves_the_call_intact(
    client: httpx.AsyncClient, world, session_factory, lk
):
    """Scheduled, then the window opens while LiveKit is down."""
    order = await make_order(session_factory, world, start_in=timedelta(hours=2))
    call_id = (await open_call(client, world, order)).json()["id"]

    async with session_factory() as session:
        call = await session.scalar(
            select(CallSession).where(CallSession.id == uuid.UUID(call_id))
        )
        appointment = await session.scalar(
            select(Appointment).where(Appointment.id == order["appointment_id"])
        )
        now = datetime.now(UTC)
        for row in (call,):
            row.scheduled_start_at = now - timedelta(minutes=1)
            row.scheduled_end_at = now + timedelta(minutes=59)
        appointment.starts_at_utc = now - timedelta(minutes=1)
        appointment.ends_at_utc = now + timedelta(minutes=59)
        await session.commit()

    lk.unavailable = True
    join = await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
    assert join.status_code == 503
    assert join.json()["error"]["code"] == "call_provider_unavailable"
    assert (await load_call(session_factory, call_id)).status == CallStatus.SCHEDULED.value

    lk.unavailable = False
    again = await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
    assert again.status_code == 200
    assert (await load_call(session_factory, call_id)).status == CallStatus.WAITING.value


async def test_a_token_failure_is_a_stable_code(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    lk.fail_token = True
    join = await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
    assert join.status_code == 503
    assert join.json()["error"]["code"] == "call_token_failed"


# ================================================================ webhooks


async def test_joins_drive_ringing_then_active(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)

    first = await send_webhook(
        client, lk, webhook_body("participant_joined", room=room, identity=ids["user"])
    )
    assert first.status_code == 200, first.text
    assert first.json()["outcome"] == "applied"
    call = await load_call(session_factory, call_id)
    assert call.status == CallStatus.RINGING.value
    assert call.started_at is None

    # The other party is rung - and only the other party.
    rings = await outbox_rows(session_factory, "incoming_call")
    assert [row.user_id for row in rings] == [world["expert_user_id"]]
    ring = rings[0]
    assert ring.payload["body"] == "Gelen görüntülü görüşme"
    data = ring.payload["data"]
    # Minimal by construction: the call, its type, an ordering version and
    # when the ring ends. Nothing else.
    assert set(data) == {"event", "call_id", "call_type", "event_version", "expires_at"}
    assert (data["event"], data["call_id"], data["call_type"]) == ("incoming_call", call_id, "video")
    assert data["event_version"].isdigit() and data["expires_at"].isdigit()
    assert ring.expires_at is not None

    second = await send_webhook(
        client, lk, webhook_body("participant_joined", room=room, identity=ids["expert"])
    )
    assert second.json()["outcome"] == "applied"
    call = await load_call(session_factory, call_id)
    assert call.status == CallStatus.ACTIVE.value
    assert call.started_at is not None

    # Answered: a ring still in the queue would make a phone ring for nothing.
    rings = await outbox_rows(session_factory, "incoming_call")
    assert rings[0].status == "skipped"
    # And the callee's other devices are told to stop ringing.
    answered = await outbox_rows(session_factory, "call_answered")
    assert [row.user_id for row in answered] == [world["expert_user_id"]]
    assert int(answered[0].payload["data"]["event_version"]) > int(data["event_version"])


async def test_an_audio_ring_says_audio(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world, delivery=DeliveryType.VOICE)
    call_id = (await open_call(client, world, order, call_type="audio")).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    await send_webhook(
        client, lk, webhook_body("participant_joined", room=room, identity=ids["expert"])
    )
    rings = await outbox_rows(session_factory, "incoming_call")
    assert rings[0].user_id == world["user_id"]
    assert rings[0].payload["body"] == "Gelen sesli görüşme"


async def test_the_client_cannot_declare_a_call_started(
    client: httpx.AsyncClient, world, session_factory
):
    """Issuing tokens to both parties is not both parties being in the room."""
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
    await client.post(f"{API}/calls/{call_id}/join", headers=world["expert"]["headers"])

    call = await load_call(session_factory, call_id)
    assert call.status == CallStatus.WAITING.value
    assert call.started_at is None


async def test_a_duplicate_webhook_is_applied_once(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)

    body = webhook_body(
        "participant_joined", room=room, identity=ids["user"], event_id="EV_same"
    )
    first = await send_webhook(client, lk, body)
    second = await send_webhook(client, lk, body)
    assert first.json()["outcome"] == "applied"
    assert second.json()["outcome"] == "duplicate"

    async with session_factory() as session:
        participant = await session.scalar(
            select(CallParticipant).where(CallParticipant.provider_identity == ids["user"])
        )
        events = list(await session.scalars(select(CallProviderEvent)))
    assert participant.connection_count == 1
    assert len(events) == 1
    assert len(await outbox_rows(session_factory, "incoming_call")) == 1


async def test_the_event_store_keeps_no_raw_payload(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    await send_webhook(
        client, lk, webhook_body("participant_joined", room=room, identity=ids["user"])
    )
    async with session_factory() as session:
        event = await session.scalar(select(CallProviderEvent))
    columns = {c.name for c in CallProviderEvent.__table__.columns}
    assert "payload" not in columns
    assert len(event.payload_sha256) == 64
    # The participant's display name was in the body; it is nowhere in the row.
    assert "ignored name" not in repr(vars(event))


@pytest.mark.parametrize("tamper", ["missing", "garbage", "wrong_key", "modified_body"])
async def test_forged_webhooks_are_refused(
    client: httpx.AsyncClient, world, session_factory, lk, tamper
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    body = webhook_body("participant_joined", room=room, identity=ids["user"])

    if tamper == "missing":
        response = await send_webhook(client, lk, body, authorization=None)
    elif tamper == "garbage":
        response = await send_webhook(client, lk, body, authorization="not-a-jwt")
    elif tamper == "wrong_key":
        from app.services.calls.livekit_provider import sign_webhook_body

        forged = sign_webhook_body(
            body, api_key=FAKE_API_KEY, api_secret="an-attackers-guess-at-the-secret-000"
        )
        response = await send_webhook(client, lk, body, authorization=forged)
    else:
        # A genuine signature over a different body: the hash no longer matches.
        signature = lk.signed_webhook(body)
        altered = body.replace(ids["user"].encode(), b"p_intruder000000000000000")
        response = await send_webhook(client, lk, altered, authorization=signature)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_webhook"
    call = await load_call(session_factory, call_id)
    assert call.status == CallStatus.WAITING.value
    async with session_factory() as session:
        assert list(await session.scalars(select(CallProviderEvent))) == []


async def test_a_webhook_for_someone_elses_room_is_ignored(
    client: httpx.AsyncClient, world, lk
):
    body = webhook_body("participant_joined", room="call_not_ours", identity="p_x")
    response = await send_webhook(client, lk, body)
    assert response.status_code == 200
    assert response.json()["outcome"] == "unknown_room"


async def test_a_third_participant_is_removed(
    client: httpx.AsyncClient, world, session_factory, lk, monkeypatch
):
    from app.services.calls import service as service_module

    warnings: list[tuple[str, dict]] = []

    class Recorder:
        def info(self, *_args, **_fields):
            pass

        def warning(self, event, **fields):
            warnings.append((event, fields))

    monkeypatch.setattr(service_module, "logger", Recorder())

    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)

    response = await send_webhook(
        client, lk, webhook_body("participant_joined", room=room, identity="p_intruder")
    )
    assert response.json()["outcome"] == "intruder"
    assert (room, "p_intruder") in lk.removed
    assert (await load_call(session_factory, call_id)).status == CallStatus.WAITING.value

    event, fields = next(item for item in warnings if item[0] == "call_intruder_detected")
    # Logged by fingerprint, not by the identity itself.
    assert "p_intruder" not in repr(fields)


async def test_leaving_briefly_does_not_end_the_call(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    for role in ("user", "expert"):
        await send_webhook(
            client, lk, webhook_body("participant_joined", room=room, identity=ids[role])
        )

    left_at = datetime.now(UTC)
    await send_webhook(
        client,
        lk,
        webhook_body(
            "participant_left",
            room=room,
            identity=ids["user"],
            reason="SIGNAL_CLOSE",
            at=left_at,
        ),
    )
    call = await load_call(session_factory, call_id)
    assert call.status == CallStatus.ACTIVE.value

    # Inside the grace: still active.
    inside = left_at + timedelta(seconds=settings.call_reconnect_grace_seconds - 5)
    assert (await advance(session_factory, lk, call_id, inside)).status == "active"

    # They come back.
    await send_webhook(
        client,
        lk,
        webhook_body(
            "participant_joined",
            room=room,
            identity=ids["user"],
            at=left_at + timedelta(seconds=10),
        ),
    )
    after = left_at + timedelta(seconds=settings.call_reconnect_grace_seconds + 60)
    call = await advance(session_factory, lk, call_id, after)
    assert call.status == CallStatus.ACTIVE.value

    async with session_factory() as session:
        user_part = await session.scalar(
            select(CallParticipant).where(CallParticipant.provider_identity == ids["user"])
        )
    assert user_part.connection_count == 2


async def test_a_drop_past_the_grace_ends_the_call_at_the_drop(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    for role in ("user", "expert"):
        await send_webhook(
            client, lk, webhook_body("participant_joined", room=room, identity=ids[role])
        )

    # Pretend the call has been running for ten minutes: move its history back
    # consistently, rather than delivering backdated webhooks against a room
    # the fake says is occupied now.
    started = datetime.now(UTC) - timedelta(minutes=10)
    async with session_factory() as session:
        call = await session.scalar(
            select(CallSession).where(CallSession.id == uuid.UUID(call_id))
        )
        call.started_at = started
        call.ringing_at = started
        for participant in await session.scalars(
            select(CallParticipant).where(CallParticipant.call_session_id == call.id)
        ):
            participant.first_joined_at = participant.last_joined_at = started
            participant.last_event_at = started
        await session.commit()

    dropped = started + timedelta(minutes=7)
    response = await send_webhook(
        client,
        lk,
        webhook_body(
            "participant_left", room=room, identity=ids["expert"], reason="SIGNAL_CLOSE", at=dropped
        ),
    )
    assert response.json()["outcome"] == "applied"

    call = await advance(
        session_factory,
        lk,
        call_id,
        dropped + timedelta(seconds=settings.call_reconnect_grace_seconds + 1),
    )
    assert call.status == CallStatus.ENDED.value
    assert call.end_reason == CallEndReason.NETWORK_DISCONNECT.value
    # Duration from server timestamps, and the grace is not billed. Within a
    # second: provider webhook timestamps are whole seconds.
    assert abs(call.duration_seconds - 7 * 60) <= 1
    assert room in lk.deleted_rooms


async def test_the_provider_is_asked_before_a_drop_ends_a_call(
    client: httpx.AsyncClient, world, session_factory, lk
):
    """We missed the rejoin webhook; the room says they are back."""
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    for role in ("user", "expert"):
        await send_webhook(
            client, lk, webhook_body("participant_joined", room=room, identity=ids[role])
        )
    left = datetime.now(UTC)
    await send_webhook(
        client,
        lk,
        webhook_body("participant_left", room=room, identity=ids["expert"], reason="SIGNAL_CLOSE", at=left),
    )
    # They reconnected; that webhook never arrived.
    lk.join(room, ids["expert"])

    call = await advance(
        session_factory,
        lk,
        call_id,
        left + timedelta(seconds=settings.call_reconnect_grace_seconds + 1),
    )
    assert call.status == CallStatus.ACTIVE.value


async def test_a_deliberate_leave_is_recorded_as_that_party_ending(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    for role in ("user", "expert"):
        await send_webhook(
            client, lk, webhook_body("participant_joined", room=room, identity=ids[role])
        )
    left = datetime.now(UTC)
    await send_webhook(
        client,
        lk,
        webhook_body(
            "participant_left", room=room, identity=ids["user"], reason="CLIENT_INITIATED", at=left
        ),
    )
    call = await advance(
        session_factory, lk, call_id, left + timedelta(seconds=settings.call_reconnect_grace_seconds + 1)
    )
    assert call.end_reason == CallEndReason.USER_ENDED.value
    assert call.ended_by == "user"


async def test_a_late_webhook_does_not_mark_a_live_call_missed(
    client: httpx.AsyncClient, world, session_factory, lk
):
    """A backlog delivers the first join long after it happened.

    Judged by our clock alone, the ring timeout expired minutes ago and the
    call would be MISSED - while both people are in the room talking. The
    provider is asked before an absence becomes a verdict.
    """
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    lk.join(room, ids["user"])
    lk.join(room, ids["expert"])

    long_ago = datetime.now(UTC) - timedelta(minutes=5)
    await send_webhook(
        client,
        lk,
        webhook_body("participant_joined", room=room, identity=ids["user"], at=long_ago),
    )
    call = await load_call(session_factory, call_id)
    assert call.status == CallStatus.ACTIVE.value
    assert call.started_at is not None
    # Nobody is told they missed a call they are in.
    assert await outbox_rows(session_factory, "call_missed") == []


async def test_a_second_device_replaces_rather_than_leaves(
    client: httpx.AsyncClient, world, session_factory, lk
):
    """LiveKit disconnects the older connection with DUPLICATE_IDENTITY."""
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    for role in ("user", "expert"):
        await send_webhook(
            client, lk, webhook_body("participant_joined", room=room, identity=ids[role])
        )

    response = await send_webhook(
        client,
        lk,
        webhook_body(
            "participant_left", room=room, identity=ids["user"], reason="DUPLICATE_IDENTITY"
        ),
    )
    assert response.json()["outcome"] == "replaced"
    async with session_factory() as session:
        user_part = await session.scalar(
            select(CallParticipant).where(CallParticipant.provider_identity == ids["user"])
        )
    assert user_part.status == ParticipantStatus.JOINED.value


async def test_a_late_webhook_does_not_move_a_participant_backwards(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    now = datetime.now(UTC)
    await send_webhook(
        client, lk, webhook_body("participant_joined", room=room, identity=ids["user"], at=now)
    )
    stale = await send_webhook(
        client,
        lk,
        webhook_body(
            "participant_left",
            room=room,
            identity=ids["user"],
            reason="SIGNAL_CLOSE",
            at=now - timedelta(seconds=30),
        ),
    )
    assert stale.json()["outcome"] == "stale"


# ============================================================ missed / end


async def test_an_unanswered_call_is_missed(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    rang = datetime.now(UTC)
    await send_webhook(
        client, lk, webhook_body("participant_joined", room=room, identity=ids["user"], at=rang)
    )

    call = await advance(
        session_factory, lk, call_id, rang + timedelta(seconds=settings.call_ring_timeout_seconds + 1)
    )
    assert call.status == CallStatus.MISSED.value
    assert call.end_reason == CallEndReason.MISSED.value
    assert call.duration_seconds is None

    missed = await outbox_rows(session_factory, "call_missed")
    # The person who did not answer is told; the caller is not.
    assert [row.user_id for row in missed] == [world["expert_user_id"]]
    assert missed[0].payload["body"] == "Cevapsız görüntülü görüşme"


async def test_a_caller_who_hangs_up_before_an_answer_stops_the_ring(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    rang = datetime.now(UTC)
    await send_webhook(
        client, lk, webhook_body("participant_joined", room=room, identity=ids["user"], at=rang)
    )
    await send_webhook(
        client,
        lk,
        webhook_body(
            "participant_left",
            room=room,
            identity=ids["user"],
            reason="CLIENT_INITIATED",
            at=rang + timedelta(seconds=5),
        ),
    )
    # Well inside the ring timeout, past the reconnect grace.
    monkey_grace = settings.call_reconnect_grace_seconds
    assert monkey_grace + 5 < settings.call_ring_timeout_seconds + 60
    call = await advance(
        session_factory, lk, call_id, rang + timedelta(seconds=5 + monkey_grace + 1)
    )
    if call.status == CallStatus.WAITING.value:
        cancelled = await outbox_rows(session_factory, "call_cancelled")
        assert [row.user_id for row in cancelled] == [world["expert_user_id"]]
    else:
        # A ring timeout shorter than the grace makes it MISSED first; both are
        # correct outcomes of "nobody answered".
        assert call.status == CallStatus.MISSED.value


async def test_ending_an_active_call(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    for role in ("user", "expert"):
        await send_webhook(
            client, lk, webhook_body("participant_joined", room=room, identity=ids[role])
        )

    ended = await client.post(f"{API}/calls/{call_id}/end", headers=world["expert"]["headers"])
    assert ended.status_code == 200
    body = ended.json()
    assert body["status"] == "ended"
    assert body["end_reason"] == "expert_ended"
    assert body["duration_seconds"] is not None
    assert room in lk.deleted_rooms

    # Idempotent, and final.
    again = await client.post(f"{API}/calls/{call_id}/end", headers=world["user"]["headers"])
    assert again.json()["status"] == "ended"
    join = await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
    assert join.status_code == 409
    assert join.json()["error"]["code"] == "call_already_ended"

    # And a new consultation attempt is a new session.
    fresh = await open_call(client, world, order)
    assert fresh.status_code == 201
    assert fresh.json()["id"] != call_id


async def test_a_leftover_token_cannot_reopen_an_ended_call(
    client: httpx.AsyncClient, world, session_factory, lk
):
    """LiveKit creates rooms on join; a token still inside its TTL would."""
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    await client.post(f"{API}/calls/{call_id}/end", headers=world["user"]["headers"])

    response = await send_webhook(
        client, lk, webhook_body("participant_joined", room=room, identity=ids["user"])
    )
    assert response.json()["outcome"] == "late_join_removed"
    assert (room, ids["user"]) in lk.removed
    assert (await load_call(session_factory, call_id)).status == CallStatus.CANCELLED.value


async def test_hanging_up_while_ringing_cancels_and_tells_the_other_party(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    await send_webhook(
        client, lk, webhook_body("participant_joined", room=room, identity=ids["user"])
    )

    ended = await client.post(f"{API}/calls/{call_id}/end", headers=world["user"]["headers"])
    assert ended.json()["status"] == "cancelled"
    assert ended.json()["end_reason"] == "user_ended"

    cancelled = await outbox_rows(session_factory, "call_cancelled")
    assert [row.user_id for row in cancelled] == [world["expert_user_id"]]
    # The unanswered ring is withdrawn from the queue.
    rings = await outbox_rows(session_factory, "incoming_call")
    assert all(row.status == "skipped" for row in rings)


async def test_the_window_closing_ends_an_active_call(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    for role in ("user", "expert"):
        await send_webhook(
            client, lk, webhook_body("participant_joined", room=room, identity=ids[role])
        )
    call = await load_call(session_factory, call_id)
    closes = call.scheduled_end_at + timedelta(seconds=settings.call_join_late_seconds)
    call = await advance(session_factory, lk, call_id, closes + timedelta(seconds=1))
    assert call.status == CallStatus.ENDED.value
    assert call.end_reason == CallEndReason.TIMEOUT.value
    assert call.ended_at == closes


async def test_nobody_joining_is_a_no_show(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    call = await load_call(session_factory, call_id)
    closes = call.scheduled_end_at + timedelta(seconds=settings.call_join_late_seconds)
    call = await advance(session_factory, lk, call_id, closes + timedelta(minutes=1))
    assert call.status == CallStatus.ENDED.value
    assert call.end_reason == CallEndReason.NO_SHOW.value
    assert call.started_at is None
    assert call.duration_seconds is None


async def test_the_hard_ceiling_ends_any_call(
    client: httpx.AsyncClient, world, session_factory, lk, monkeypatch
):
    monkeypatch.setattr(settings, "call_max_duration_seconds", 600)
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    started = datetime.now(UTC)
    for role in ("user", "expert"):
        await send_webhook(
            client, lk, webhook_body("participant_joined", room=room, identity=ids[role], at=started)
        )
    call = await advance(session_factory, lk, call_id, started + timedelta(seconds=601))
    assert call.status == CallStatus.ENDED.value
    assert call.end_reason == CallEndReason.TIMEOUT.value
    assert call.duration_seconds == 600


# ============================================================ marketplace


async def test_cancelling_the_order_cancels_its_call(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]

    cancelled = await client.post(
        f"{API}/orders/{order['order_id']}/cancel",
        headers=world["user"]["headers"],
        json={"reason": "changed plans"},
    )
    assert cancelled.status_code == 200, cancelled.text

    call = await load_call(session_factory, call_id)
    assert call.status == CallStatus.CANCELLED.value
    assert call.end_reason == CallEndReason.ORDER_CANCELLED.value
    join = await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
    assert join.status_code == 409


async def test_cancelling_the_appointment_cancels_its_call(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]

    response = await client.post(
        f"{API}/appointments/{order['appointment_id']}/cancel",
        headers=world["user"]["headers"],
        json={},
    )
    assert response.status_code == 200, response.text
    call = await load_call(session_factory, call_id)
    assert call.status == CallStatus.CANCELLED.value
    assert call.end_reason == CallEndReason.APPOINTMENT_CANCELLED.value


async def test_ending_a_call_does_not_complete_the_appointment(
    client: httpx.AsyncClient, world, session_factory, lk
):
    """A dropped call is not a finished consultation."""
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    for role in ("user", "expert"):
        await send_webhook(
            client, lk, webhook_body("participant_joined", room=room, identity=ids[role])
        )
    await client.post(f"{API}/calls/{call_id}/end", headers=world["user"]["headers"])

    async with session_factory() as session:
        appointment = await session.scalar(
            select(Appointment).where(Appointment.id == order["appointment_id"])
        )
        row = await session.scalar(
            select(ServiceOrder).where(ServiceOrder.id == order["order_id"])
        )
    assert appointment.status == AppointmentStatus.CONFIRMED.value
    assert row.status == OrderStatus.CONFIRMED.value


async def test_suspending_the_expert_stops_calls_and_refuses_new_ones(
    client: httpx.AsyncClient, world, session_factory, lk
):
    from app.services.marketplace.experts import ExpertProfileService

    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)
    for role in ("user", "expert"):
        await send_webhook(
            client, lk, webhook_body("participant_joined", room=room, identity=ids[role])
        )

    async with session_factory() as session:
        await ExpertProfileService(session).suspend(world["expert_id"], reason="review")
        await session.commit()

    call = await load_call(session_factory, call_id)
    assert call.status == CallStatus.ENDED.value
    assert call.end_reason == CallEndReason.EXPERT_SUSPENDED.value
    assert room in lk.deleted_rooms

    other = await make_order(session_factory, world, start_in=timedelta(minutes=-1))
    response = await open_call(client, world, other)
    assert response.status_code == 403
    assert response.json()["error"]["details"]["reason"] == "expert_suspended"


# ================================================================= history


async def test_call_history_is_member_only(
    client: httpx.AsyncClient, world, session_factory
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    stranger = await register(client, "watcher@example.com")

    for method, path in (
        ("get", f"{API}/calls/{call_id}"),
        ("post", f"{API}/calls/{call_id}/join"),
        ("post", f"{API}/calls/{call_id}/end"),
    ):
        response = await getattr(client, method)(path, headers=stranger["headers"])
        assert response.status_code == 404, path

    listed = await client.get(f"{API}/calls", headers=stranger["headers"])
    assert listed.json()["items"] == []

    for role in ("user", "expert"):
        mine = await client.get(f"{API}/calls", headers=world[role]["headers"])
        assert [item["id"] for item in mine.json()["items"]] == [call_id]
        assert mine.json()["items"][0]["my_role"] == role


# ========================================================== reconciliation


async def test_reconciliation_repairs_a_missed_webhook(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, ids = await room_and_identities(session_factory, call_id)

    # Both joined; no webhook ever arrived.
    lk.join(room, ids["user"])
    lk.join(room, ids["expert"])
    lk.join(room, "p_unexpected")

    async with session_factory() as session:
        service = CallService(session, lk)
        call = await session.scalar(
            select(CallSession).where(CallSession.id == uuid.UUID(call_id))
        )
        outcome = await service.reconcile(call)
        await session.commit()

    assert outcome == "changed"
    call = await load_call(session_factory, call_id)
    assert call.status == CallStatus.ACTIVE.value
    assert (room, "p_unexpected") in lk.removed

    # And a departure nobody reported.
    lk.leave(room, ids["expert"])
    async with session_factory() as session:
        call = await session.scalar(
            select(CallSession).where(CallSession.id == uuid.UUID(call_id))
        )
        await CallService(session, lk).reconcile(call)
        await session.commit()
        expert_part = await session.scalar(
            select(CallParticipant).where(CallParticipant.provider_identity == ids["expert"])
        )
    assert expert_part.status == ParticipantStatus.DISCONNECTED.value


async def test_reconciliation_survives_a_provider_outage(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    lk.fail_list = True
    async with session_factory() as session:
        call = await session.scalar(
            select(CallSession).where(CallSession.id == uuid.UUID(call_id))
        )
        assert await CallService(session, lk).reconcile(call) == "provider_unavailable"
    assert (await load_call(session_factory, call_id)).status == CallStatus.WAITING.value


async def test_the_worker_sweep_applies_the_clock(
    client: httpx.AsyncClient, world, session_factory, lk, monkeypatch
):
    from app.workers import call_worker

    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    async with session_factory() as session:
        call = await session.scalar(
            select(CallSession).where(CallSession.id == uuid.UUID(call_id))
        )
        call.scheduled_end_at = datetime.now(UTC) - timedelta(hours=2)
        call.scheduled_start_at = call.scheduled_end_at - timedelta(hours=1)
        await session.commit()

    monkeypatch.setattr(call_worker, "get_session_factory", lambda: session_factory)
    seen = await call_worker.CallWorker(worker_id="test").run_once()
    assert seen == 1
    assert (await load_call(session_factory, call_id)).end_reason == CallEndReason.NO_SHOW.value


# ================================================================ privacy


async def test_recording_is_off_and_cannot_be_switched_on(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    join = await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
    assert not decode(join.json()["token"]).video.room_record
    assert join.json()  # sanity
    view = await client.get(f"{API}/calls/{call_id}", headers=world["user"]["headers"])
    assert view.json()["recording_enabled"] is False

    async with session_factory() as session:
        call = await session.scalar(
            select(CallSession).where(CallSession.id == uuid.UUID(call_id))
        )
        call.recording_enabled = True
        with pytest.raises(IntegrityError):
            await session.flush()


async def test_the_room_carries_no_personal_data(
    client: httpx.AsyncClient, world, session_factory, lk
):
    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    room, _ = await room_and_identities(session_factory, call_id)
    spec = lk.rooms[room].spec
    assert spec.name == room
    assert "Call Expert" not in repr(spec)
    assert str(world["user_id"]) not in repr(spec)


# ============================================================= rate limits


async def test_the_join_token_quota_is_its_own_scope(
    client: httpx.AsyncClient, world, session_factory, monkeypatch
):
    from app.api.v1 import calls as calls_routes
    from app.core.rate_limit import Quota

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(
        calls_routes._join_limit.dependency, "quota", Quota(limit=2, window_seconds=60)
    )

    order = await make_order(session_factory, world)
    call_id = (await open_call(client, world, order)).json()["id"]
    for _ in range(2):
        allowed = await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
        assert allowed.status_code == 200

    blocked = await client.post(f"{API}/calls/{call_id}/join", headers=world["user"]["headers"])
    assert blocked.status_code == 429
    assert blocked.json()["error"]["details"]["scope"] == "call_join_token"
    assert blocked.headers.get("retry-after")

    # Per user: the expert still has their allowance.
    theirs = await client.post(f"{API}/calls/{call_id}/join", headers=world["expert"]["headers"])
    assert theirs.status_code == 200
