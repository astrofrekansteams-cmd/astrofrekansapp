"""Mobile call delivery: the right transport per device, once per device.

The properties worth breaking a build over:

* **Android rings through data-only, HIGH, short-TTL FCM** - no `notification`
  block, so the app's own receiver presents and dismisses the call UI.
* **iOS rings through PushKit VoIP** - `apns-push-type: voip`, topic
  `<bundle>.voip` - and only for `incoming_call`: Apple says not to push
  again to cancel, so cancel/answered/missed never use VoIP.
* **An FCM token is never a VoIP token**, and ordinary notifications are
  untouched.
* **Late is never**: an expired ring is skipped, not sent.
* **Once per device**: retries resend only what failed.
* **Nothing private** reaches any payload.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select

from app.core.config import settings
from app.db.models.chat import NotificationDelivery, NotificationOutbox, PushDevice
from app.db.models.user import User
from app.domain.chat import DevicePlatform, OutboxStatus, PushEvent
from app.services.firebase import factory as firebase_factory
from app.services.notifications import apns as apns_module
from app.services.notifications.apns import ApnsHttpProvider, FakeApnsProvider
from app.services.notifications.call_delivery import call_event_fields
from app.services.notifications.devices import DeviceService
from app.services.notifications.outbox import OutboxService
from app.services.notifications.sender import NotificationSender

API = "/api/v1"
VOIP_TOKEN = "ab" * 32
VOIP_TOKEN_2 = "cd" * 32
ANDROID_TOKEN = "fcm-android-" + "a" * 40
ANDROID_TOKEN_2 = "fcm-android-" + "b" * 40
IOS_FCM_TOKEN = "fcm-ios-" + "c" * 40
PRIVATE = ("birth", "question", "message", "amount", "email", "phone", "livekit", "token", "order")


# ================================================================ fixtures


@pytest.fixture
def firebase(monkeypatch):
    monkeypatch.setattr(settings, "firebase_provider", "fake")
    monkeypatch.setattr(settings, "firebase_project_id", "astrofrekans-test")
    providers = firebase_factory.fake_providers()
    firebase_factory.set_firebase(providers)
    yield providers
    firebase_factory.set_firebase(None)


@pytest.fixture
def voip(monkeypatch) -> FakeApnsProvider:
    monkeypatch.setattr(settings, "apns_provider", "fake")
    monkeypatch.setattr(settings, "apns_bundle_id", "com.astrofrekans.app")
    monkeypatch.setattr(settings, "apns_environment", "production")
    provider = FakeApnsProvider()
    apns_module.set_voip_provider(provider)
    yield provider
    apns_module.set_voip_provider(None)


@pytest.fixture
async def user(registered, session_factory) -> User:
    async with session_factory() as session:
        return await session.scalar(select(User).where(User.email == registered["email"]))


async def add_devices(session_factory, user, *, android=(), ios_fcm=(), voip=()):
    async with session_factory() as session:
        row = await session.get(User, user.id)
        service = DeviceService(session)
        for token in android:
            await service.register(row, token=token, platform=DevicePlatform.ANDROID)
        for token in ios_fcm:
            await service.register(row, token=token, platform=DevicePlatform.IOS)
        for token in voip:
            await service.register_voip(row, token=token, environment="production")
        await session.commit()


async def enqueue_call(session_factory, user, event, *, ringing_at=None, call_id=None, suffix=""):
    call_id = call_id or str(uuid.uuid4())
    ringing_at = ringing_at or datetime.now(UTC)
    data, expires_at = call_event_fields(event, call_id=call_id, call_type="video", ringing_at=ringing_at)
    async with session_factory() as session:
        row = await OutboxService(session).enqueue(
            event=event,
            user_id=user.id,
            dedupe_key=f"{event.value}:{call_id}:{user.id}{suffix}",
            data=data,
            variant="video",
            expires_at=expires_at,
        )
        await session.commit()
        return row.id, call_id


async def deliver(session_factory, firebase, voip, outbox_id):
    async with session_factory() as session:
        row = await session.get(NotificationOutbox, outbox_id)
        row.status = OutboxStatus.SENDING.value
        row.attempts += 1
        await session.commit()
        return await NotificationSender(session, firebase, voip).deliver(row)


async def load(session_factory, model, *where):
    async with session_factory() as session:
        return list(await session.scalars(select(model).where(*where)))


# ================================================================ Android


async def test_android_rings_with_data_only_high_short_ttl(session_factory, firebase, voip, user):
    await add_devices(session_factory, user, android=[ANDROID_TOKEN])
    outbox_id, call_id = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)

    await deliver(session_factory, firebase, voip, outbox_id)

    assert firebase.push.sent == []  # no notification-block message at all
    [(tokens, message)] = firebase.push.data_sent
    assert tokens == [ANDROID_TOKEN]
    assert message.android_priority == "high"
    assert 0 < message.ttl_seconds <= settings.call_ring_timeout_seconds
    assert message.collapse_key == f"call:{call_id}"
    assert message.apns_background is False
    assert set(message.data) == {"event", "call_id", "call_type", "event_version", "expires_at"}
    assert message.data["event"] == "incoming_call" and message.data["call_id"] == call_id
    assert voip.requests == []
    [row] = await load(session_factory, NotificationOutbox, NotificationOutbox.id == outbox_id)
    assert row.status == "sent"


async def test_android_cancel_and_missed_are_data_only_and_ordered(session_factory, firebase, voip, user):
    await add_devices(session_factory, user, android=[ANDROID_TOKEN])
    ring = datetime.now(UTC)
    call_id = str(uuid.uuid4())
    versions = {}
    for event in (PushEvent.INCOMING_CALL, PushEvent.CALL_ANSWERED, PushEvent.CALL_CANCELLED, PushEvent.CALL_MISSED):
        outbox_id, _ = await enqueue_call(session_factory, user, event, ringing_at=ring, call_id=call_id)
        await deliver(session_factory, firebase, voip, outbox_id)
        tokens, message = firebase.push.data_sent[-1]
        assert tokens == [ANDROID_TOKEN]
        assert message.data["call_id"] == call_id
        versions[event] = int(message.data["event_version"])
    assert firebase.push.sent == []
    ordered = [versions[e] for e in (PushEvent.INCOMING_CALL, PushEvent.CALL_ANSWERED, PushEvent.CALL_CANCELLED, PushEvent.CALL_MISSED)]
    assert ordered == sorted(ordered) and len(set(ordered)) == 4

    # A later ring of the same call outranks anything from the earlier one.
    later, _ = call_event_fields(
        PushEvent.INCOMING_CALL, call_id=call_id, call_type="video", ringing_at=ring + timedelta(seconds=1)
    )
    assert int(later["event_version"]) > versions[PushEvent.CALL_MISSED]


async def test_ordinary_notifications_are_unchanged(session_factory, firebase, voip, user):
    await add_devices(session_factory, user, android=[ANDROID_TOKEN], ios_fcm=[IOS_FCM_TOKEN], voip=[VOIP_TOKEN])
    async with session_factory() as session:
        row = await OutboxService(session).enqueue_chat_message(
            recipient_user_id=user.id, conversation_id=uuid.uuid4(), message_id="m-1"
        )
        await session.commit()
        outbox_id = row.id

    await deliver(session_factory, firebase, voip, outbox_id)

    [(tokens, message)] = firebase.push.sent
    assert sorted(tokens) == sorted([ANDROID_TOKEN, IOS_FCM_TOKEN])  # never the VoIP token
    assert message.title == "Astrofrekans" and message.body == "Yeni bir mesajın var."
    assert message.ttl_seconds is None
    assert firebase.push.data_sent == [] and voip.requests == []
    assert await load(session_factory, NotificationDelivery) == []


# ==================================================================== iOS


async def test_ios_rings_through_apns_voip(session_factory, firebase, voip, user):
    await add_devices(session_factory, user, ios_fcm=[IOS_FCM_TOKEN], voip=[VOIP_TOKEN])
    outbox_id, call_id = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)

    await deliver(session_factory, firebase, voip, outbox_id)

    [request] = voip.requests
    assert request["host"] == "https://api.push.apple.com"
    assert request["path"] == f"/3/device/{VOIP_TOKEN}"
    headers = request["headers"]
    assert headers["apns-push-type"] == "voip"
    assert headers["apns-topic"] == "com.astrofrekans.app.voip"
    assert headers["apns-priority"] == "10"
    assert headers["apns-expiration"] == "0"
    [delivery] = await load(session_factory, NotificationDelivery)
    assert headers["apns-id"] == str(delivery.id)
    assert delivery.transport == "apns_voip" and delivery.status == "delivered"
    assert set(request["payload"]) == {"event", "call_id", "call_type", "event_version", "expires_at"}
    # A registered iPhone is rung by CallKit only - never also by a banner.
    assert firebase.push.sent == [] and firebase.push.data_sent == []


async def test_ios_without_voip_falls_back_to_an_alert(session_factory, firebase, voip, user):
    await add_devices(session_factory, user, ios_fcm=[IOS_FCM_TOKEN])
    outbox_id, _ = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)
    await deliver(session_factory, firebase, voip, outbox_id)
    [(tokens, message)] = firebase.push.sent
    assert tokens == [IOS_FCM_TOKEN]
    assert message.body == "Gelen görüntülü görüşme"
    assert 0 < message.ttl_seconds <= settings.call_ring_timeout_seconds
    assert voip.requests == []


async def test_ios_never_gets_voip_for_cancel_answered_or_missed(session_factory, firebase, voip, user):
    await add_devices(session_factory, user, ios_fcm=[IOS_FCM_TOKEN], voip=[VOIP_TOKEN])
    call_id = str(uuid.uuid4())
    for event in (PushEvent.CALL_CANCELLED, PushEvent.CALL_ANSWERED):
        outbox_id, _ = await enqueue_call(session_factory, user, event, call_id=call_id)
        await deliver(session_factory, firebase, voip, outbox_id)
        tokens, message = firebase.push.data_sent[-1]
        assert tokens == [IOS_FCM_TOKEN] and message.apns_background is True
    missed, _ = await enqueue_call(session_factory, user, PushEvent.CALL_MISSED, call_id=call_id)
    await deliver(session_factory, firebase, voip, missed)
    [(tokens, message)] = firebase.push.sent
    assert tokens == [IOS_FCM_TOKEN] and message.body == "Cevapsız görüntülü görüşme"
    assert voip.requests == []


async def test_a_dead_voip_token_is_disabled(session_factory, firebase, voip, user):
    await add_devices(session_factory, user, voip=[VOIP_TOKEN])
    voip.reasons[VOIP_TOKEN] = "Unregistered"
    outbox_id, _ = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)

    await deliver(session_factory, firebase, voip, outbox_id)

    [device] = await load(session_factory, PushDevice)
    assert device.enabled is False and device.disabled_reason == "apns_unregistered"
    [delivery] = await load(session_factory, NotificationDelivery)
    assert delivery.status == "failed" and delivery.error_code == "apns_Unregistered"
    assert delivery.attempts == 1
    [row] = await load(session_factory, NotificationOutbox)
    assert row.status == "failed"  # nothing reachable; not retried


async def test_apns_unavailable_retries_only_what_failed(session_factory, firebase, voip, user):
    await add_devices(session_factory, user, android=[ANDROID_TOKEN], voip=[VOIP_TOKEN])
    voip.reasons[VOIP_TOKEN] = "ServiceUnavailable"
    outbox_id, _ = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)

    await deliver(session_factory, firebase, voip, outbox_id)
    [row] = await load(session_factory, NotificationOutbox)
    assert row.status == "pending" and row.error_code == "call_delivery_retry"
    assert len(firebase.push.data_sent) == 1 and len(voip.requests) == 1

    del voip.reasons[VOIP_TOKEN]
    await deliver(session_factory, firebase, voip, outbox_id)
    [row] = await load(session_factory, NotificationOutbox)
    assert row.status == "sent"
    assert len(firebase.push.data_sent) == 1  # the Android phone did not ring twice
    assert len(voip.requests) == 2
    statuses = sorted(d.status for d in await load(session_factory, NotificationDelivery))
    assert statuses == ["delivered", "delivered"]


async def test_without_apns_credentials_ios_is_skipped_not_failed(session_factory, firebase, voip, user):
    await add_devices(session_factory, user, voip=[VOIP_TOKEN])
    voip.unavailable = True
    outbox_id, _ = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)
    await deliver(session_factory, firebase, voip, outbox_id)
    [row] = await load(session_factory, NotificationOutbox)
    assert row.status == "skipped" and row.notes == "provider_not_configured"


def test_the_real_provider_is_unavailable_without_credentials(monkeypatch):
    monkeypatch.setattr(settings, "apns_provider", "apns")
    for key in ("apns_team_id", "apns_key_id", "apns_bundle_id", "apns_private_key", "apns_private_key_path"):
        monkeypatch.setattr(settings, key, None)
    assert settings.apns_configured is False
    assert ApnsHttpProvider().available is False


def test_the_fake_is_refused_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "apns_provider", "fake")
    with pytest.raises(RuntimeError, match="APNS_PROVIDER=fake"):
        settings.assert_production_ready()


# ============================================================ the real APNs


async def test_the_real_provider_speaks_apns(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    monkeypatch.setattr(settings, "apns_provider", "apns")
    monkeypatch.setattr(settings, "apns_team_id", "TEAM123456")
    monkeypatch.setattr(settings, "apns_key_id", "KEY1234567")
    monkeypatch.setattr(settings, "apns_bundle_id", "com.astrofrekans.app")
    monkeypatch.setattr(settings, "apns_private_key", pem)

    seen: list[httpx.Request] = []
    answers = iter([
        httpx.Response(200, headers={"apns-id": "x"}),
        httpx.Response(410, json={"reason": "Unregistered", "timestamp": 1}),
        httpx.Response(503, json={"reason": "ServiceUnavailable"}),
        httpx.Response(400, json={"reason": "BadTopic"}),
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return next(answers)

    provider = ApnsHttpProvider(transport=httpx.MockTransport(handler))
    payload = {"event": "incoming_call", "call_id": "c-1"}
    outcomes = [
        (await provider.send_voip(VOIP_TOKEN, payload, environment=env, expiration=0, apns_id="id-1")).outcome
        for env in ("production", "sandbox", "production", "production")
    ]
    await provider.close()
    assert outcomes == ["sent", "invalid_token", "retry", "failed"]

    first = seen[0]
    assert str(first.url) == f"https://api.push.apple.com/3/device/{VOIP_TOKEN}"
    assert str(seen[1].url).startswith("https://api.sandbox.push.apple.com/3/device/")
    assert first.headers["apns-push-type"] == "voip"
    assert first.headers["apns-topic"] == "com.astrofrekans.app.voip"
    assert first.headers["apns-priority"] == "10"
    assert first.headers["apns-expiration"] == "0"
    assert json.loads(first.content) == payload
    token = first.headers["authorization"].removeprefix("bearer ")
    assert jwt.get_unverified_header(token) == {"alg": "ES256", "kid": "KEY1234567", "typ": "JWT"}
    claims = jwt.decode(token, key.public_key(), algorithms=["ES256"])
    assert claims["iss"] == "TEAM123456"
    # One provider token reused inside Apple's 20-60 minute window.
    assert len({request.headers["authorization"] for request in seen}) == 1


# ======================================================== registration API


async def test_voip_registration_is_owned_and_never_echoed(client, registered, voip):
    headers = registered["headers"]
    response = await client.post(
        f"{API}/devices/voip", headers=headers, json={"token": VOIP_TOKEN, "environment": "production"}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert VOIP_TOKEN not in json.dumps(body)
    assert body["token_fingerprint"] and body["environment"] == "production"

    listed = await client.get(f"{API}/devices/voip", headers=headers)
    assert [row["id"] for row in listed.json()] == [body["id"]]
    assert VOIP_TOKEN not in listed.text
    # A VoIP credential is not an ordinary push device.
    assert (await client.get(f"{API}/devices/push", headers=headers)).json() == []

    other = await client.post(f"{API}/auth/register", json={
        "email": "other-voip@example.com", "password": "Str0ngPassphrase!", "name": "Other",
        "birth_date": "1990-01-01", "birth_time": "10:00:00", "birth_place": "Istanbul"})
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    stranger = await client.delete(f"{API}/devices/voip/{body['id']}", headers=other_headers)
    assert stranger.status_code == 404
    wrong_kind = await client.delete(f"{API}/devices/push/{body['id']}", headers=headers)
    assert wrong_kind.status_code == 404

    # The handset signs in as somebody else: the token moves, not duplicates.
    moved = await client.post(
        f"{API}/devices/voip", headers=other_headers, json={"token": VOIP_TOKEN, "environment": "production"}
    )
    assert moved.json()["id"] == body["id"]
    assert (await client.get(f"{API}/devices/voip", headers=headers)).json() == []

    # Rotation: PushKit hands out a new token; the old one is deleted.
    rotated = await client.post(
        f"{API}/devices/voip", headers=other_headers, json={"token": VOIP_TOKEN_2, "environment": "production"}
    )
    assert rotated.status_code == 201
    deleted = await client.delete(f"{API}/devices/voip/{body['id']}", headers=other_headers)
    assert deleted.status_code == 200
    remaining = (await client.get(f"{API}/devices/voip", headers=other_headers)).json()
    assert [row["id"] for row in remaining] == [rotated.json()["id"]]


async def test_voip_and_fcm_tokens_are_never_interchangeable(client, registered, voip):
    headers = registered["headers"]
    await client.post(f"{API}/devices/voip", headers=headers, json={"token": VOIP_TOKEN, "environment": "production"})
    as_fcm = await client.post(f"{API}/devices/push", headers=headers, json={"token": VOIP_TOKEN, "platform": "ios"})
    assert as_fcm.status_code == 422
    await client.post(f"{API}/devices/push", headers=headers, json={"token": "f" * 64, "platform": "ios"})
    as_voip = await client.post(f"{API}/devices/voip", headers=headers, json={"token": "f" * 64, "environment": "production"})
    assert as_voip.status_code == 422

    not_hex = await client.post(f"{API}/devices/voip", headers=headers, json={"token": "z" * 64, "environment": "production"})
    assert not_hex.status_code == 422
    wrong_env = await client.post(f"{API}/devices/voip", headers=headers, json={"token": VOIP_TOKEN_2, "environment": "sandbox"})
    assert wrong_env.status_code == 422
    assert wrong_env.json()["error"]["code"] == "voip_environment_mismatch"
    assert VOIP_TOKEN_2 not in wrong_env.text


# ============================================================ outbox rules


async def test_an_expired_ring_is_skipped_not_sent(session_factory, firebase, voip, user):
    await add_devices(session_factory, user, android=[ANDROID_TOKEN], voip=[VOIP_TOKEN])
    long_ago = datetime.now(UTC) - timedelta(hours=3)
    outbox_id, _ = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL, ringing_at=long_ago)
    await deliver(session_factory, firebase, voip, outbox_id)
    [row] = await load(session_factory, NotificationOutbox)
    assert row.status == "skipped" and row.notes == "skipped_expired"
    assert firebase.push.data_sent == [] and voip.requests == []


async def test_every_device_rings_once_across_retries(session_factory, firebase, voip, user):
    await add_devices(
        session_factory, user, android=[ANDROID_TOKEN, ANDROID_TOKEN_2], ios_fcm=[IOS_FCM_TOKEN], voip=[VOIP_TOKEN]
    )
    outbox_id, _ = await enqueue_call(session_factory, user, PushEvent.INCOMING_CALL)
    # The same event enqueued again converges on the same row.
    async with session_factory() as session:
        [row] = list(await session.scalars(select(NotificationOutbox)))
        again = await OutboxService(session).enqueue(
            event=PushEvent.INCOMING_CALL, user_id=user.id, dedupe_key=row.dedupe_key, data={}
        )
        assert again is None

    await deliver(session_factory, firebase, voip, outbox_id)
    await deliver(session_factory, firebase, voip, outbox_id)  # a replayed claim

    [(tokens, _)] = firebase.push.data_sent
    assert sorted(tokens) == sorted([ANDROID_TOKEN, ANDROID_TOKEN_2])
    assert len(voip.requests) == 1
    assert firebase.push.sent == []  # the iPhone's FCM token is not rung too
    deliveries = await load(session_factory, NotificationDelivery)
    assert len(deliveries) == 3


async def test_no_payload_carries_anything_private(session_factory, firebase, voip, user):
    await add_devices(session_factory, user, android=[ANDROID_TOKEN], ios_fcm=[IOS_FCM_TOKEN], voip=[VOIP_TOKEN])
    call_id = str(uuid.uuid4())
    for event in (PushEvent.INCOMING_CALL, PushEvent.CALL_ANSWERED, PushEvent.CALL_CANCELLED, PushEvent.CALL_MISSED):
        outbox_id, _ = await enqueue_call(session_factory, user, event, call_id=call_id)
        await deliver(session_factory, firebase, voip, outbox_id)

    payloads = [message.data for _, message in firebase.push.data_sent]
    payloads += [message.data for _, message in firebase.push.sent]
    payloads += [request["payload"] for request in voip.requests]
    assert len(payloads) >= 6
    allowed = {"event", "call_id", "call_type", "event_version", "expires_at"}
    for payload in payloads:
        assert set(payload) <= allowed
        blob = json.dumps(payload).lower()
        assert user.email.lower() not in blob
        for word in PRIVATE:
            assert word not in set(payload)
