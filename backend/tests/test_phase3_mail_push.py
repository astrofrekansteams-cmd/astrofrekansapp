"""Phase 3: production email, localised push, inbox/push consistency, search.

* Email: validated SMTP settings, retries only for transient failures,
  multipart HTML + text in the account's language, the reset URL from one
  setting, logs without addresses or tokens, production refusing an
  incomplete configuration.
* Push: the title/body follow the recipient's language (TR/EN) at queue time
  and again at delivery; the event, its data and its dedupe key do not.
* The inbox and the push are one record: the push carries the inbox id,
  a retried event is still one record.
* Search: past 500 experts, a match is still found.
"""

from __future__ import annotations

import smtplib
import uuid

import pytest
from sqlalchemy import update

from app.core.config import settings
from app.db.models.chat import NotificationOutbox
from app.db.models.marketplace import Expert
from app.db.models.user import UserProfile
from app.domain.chat import PushEvent
from app.domain.marketplace import ExpertStatus
from app.services.mail import mailer as mail_module
from app.services.mail.templates import password_reset_email, password_reset_link
from app.services.notifications.messages import push_text
from app.services.notifications.outbox import OutboxService
from tests.test_call_delivery import (  # noqa: F401 - fixtures
    ANDROID_TOKEN,
    add_devices,
    deliver,
    enqueue_call,
    firebase,
    user,
    voip,
)

API = "/api/v1"


# ==================================================================== mail


@pytest.fixture
def smtp_settings(monkeypatch):
    values = {
        "mail_provider": "smtp",
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "mail_from": "Astrofrekans <noreply@example.com>",
        "smtp_username": "relay-user",
        "smtp_password": "relay-secret",
        "smtp_starttls": True,
        "smtp_ssl": False,
        "smtp_max_attempts": 3,
        "smtp_retry_backoff_seconds": 0.0,
    }
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)
    return values


class _Server:
    """Stands in for smtplib.SMTP; fails with the queued errors, then sends."""

    def __init__(self, errors):
        self.errors = errors
        self.sent = []
        self.logins = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        self.logins.append(user)

    def send_message(self, mail):
        if self.errors:
            raise self.errors.pop(0)
        self.sent.append(mail)


def _patch_connect(monkeypatch, server):
    attempts = {"n": 0}

    def connect(self):
        attempts["n"] += 1
        return server

    monkeypatch.setattr(mail_module.SmtpMailer, "_connect", connect)
    return attempts


def test_smtp_configuration_is_validated(smtp_settings, monkeypatch):
    assert mail_module.smtp_config_problems() == []
    assert mail_module.SmtpMailer().configured is True
    for key, value, problem in (
        ("smtp_host", None, "SMTP_HOST"),
        ("mail_from", "not-an-address", "MAIL_FROM"),
        ("smtp_port", 70000, "SMTP_PORT"),
        ("smtp_ssl", True, "exclusive"),
        ("smtp_password", None, "together"),
    ):
        with monkeypatch.context() as local:
            local.setattr(settings, key, value)
            problems = mail_module.smtp_config_problems()
            assert any(problem in p for p in problems), (key, problems)
            assert mail_module.SmtpMailer().configured is False
            # A problem names the setting, never its value.
            assert "relay-secret" not in " ".join(problems)


def test_production_refuses_incomplete_smtp_and_non_https_reset_url(smtp_settings, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "smtp_host", None)
    with pytest.raises(RuntimeError) as refused:
        settings.assert_production_ready()
    assert "SMTP_HOST" in str(refused.value)
    monkeypatch.setattr(settings, "password_reset_url_base", "astrofrekans://app/reset-password")
    with pytest.raises(RuntimeError, match="PASSWORD_RESET_URL_BASE"):
        settings.assert_production_ready()


async def test_transient_failures_are_retried_then_sent(smtp_settings, monkeypatch):
    server = _Server([smtplib.SMTPServerDisconnected("gone"), TimeoutError()])
    attempts = _patch_connect(monkeypatch, server)
    message = password_reset_email(to="a@example.com", token="tok-123", language="tr")
    await mail_module.SmtpMailer().send(message)
    assert attempts["n"] == 3 and len(server.sent) == 1
    # Each attempt is a fresh connection, so it signs in again.
    assert server.logins == ["relay-user"] * 3


@pytest.mark.parametrize(
    "error",
    [
        smtplib.SMTPAuthenticationError(535, b"bad credentials"),
        smtplib.SMTPRecipientsRefused({"a@example.com": (550, b"no such user")}),
        smtplib.SMTPDataError(554, b"rejected"),
    ],
)
async def test_permanent_failures_are_not_retried(smtp_settings, monkeypatch, error):
    server = _Server([error])
    attempts = _patch_connect(monkeypatch, server)
    with pytest.raises(mail_module.MailDeliveryFailed) as failed:
        await mail_module.SmtpMailer().send(
            password_reset_email(to="a@example.com", token="tok-123", language="en")
        )
    assert failed.value.transient is False
    assert attempts["n"] == 1


async def test_retries_stop_at_the_limit(smtp_settings, monkeypatch):
    server = _Server([smtplib.SMTPServerDisconnected("x")] * 5)
    attempts = _patch_connect(monkeypatch, server)
    with pytest.raises(mail_module.MailDeliveryFailed) as failed:
        await mail_module.SmtpMailer().send(
            password_reset_email(to="a@example.com", token="tok-123", language="en")
        )
    assert failed.value.transient is True and attempts["n"] == 3


async def test_mail_logs_carry_no_address_token_or_secret(smtp_settings, monkeypatch, caplog):
    server = _Server([smtplib.SMTPServerDisconnected("relay said something about a@example.com")])
    _patch_connect(monkeypatch, server)
    records = []
    monkeypatch.setattr(
        mail_module.logger, "warning", lambda event, **kw: records.append((event, kw))
    )
    monkeypatch.setattr(mail_module.logger, "info", lambda event, **kw: records.append((event, kw)))
    await mail_module.SmtpMailer().send(
        password_reset_email(to="person@example.com", token="secret-reset-token", language="tr")
    )
    blob = repr(records)
    assert [event for event, _ in records] == ["mail_attempt_failed", "mail_sent"]
    for secret in ("person@example.com", "secret-reset-token", "relay-secret", "a@example.com"):
        assert secret not in blob


def test_reset_email_is_multipart_localised_and_uses_the_configured_url(smtp_settings):
    tr = password_reset_email(to="a@example.com", token="t/ok+en", language="tr")
    en = password_reset_email(to="a@example.com", token="t/ok+en", language="en")
    link = password_reset_link("t/ok+en")
    assert link == f"{settings.password_reset_url_base}#token=t%2Fok%2Ben"
    assert link.startswith("https://astrofrekansteams-cmd.github.io/astrofrekansapp/reset-password.html")
    assert "şifre sıfırlama" in tr.subject and "password reset" in en.subject
    for message in (tr, en):
        assert link in message.text
        assert link.replace("&", "&amp;") in message.html
        assert "<script" not in message.html and "http://" not in message.html
    mail = mail_module.build_email(en)
    assert mail.is_multipart()
    assert [part.get_content_type() for part in mail.iter_parts()] == ["text/plain", "text/html"]
    assert mail["Auto-Submitted"] == "auto-generated"


async def test_reset_email_follows_the_account_language(client, registered, session_factory):
    memory = mail_module.MemoryMailer()
    mail_module.set_mailer(memory)
    try:
        async with session_factory() as session:
            await session.execute(update(UserProfile).values(language="en"))
            await session.commit()
        response = await client.post(f"{API}/auth/forgot-password", json={"email": registered["email"]})
        unknown = await client.post(f"{API}/auth/forgot-password", json={"email": "ghost@example.com"})
    finally:
        mail_module.set_mailer(None)
    assert response.json() == unknown.json()
    [message] = memory.outbox
    assert message.subject == "Astrofrekans password reset"
    assert message.html and settings.password_reset_url_base in message.text


# ==================================================================== push


async def _set_language(session_factory, user_id, language):
    async with session_factory() as session:
        await session.execute(
            update(UserProfile).where(UserProfile.user_id == user_id).values(language=language)
        )
        await session.commit()


def test_every_event_has_both_languages():
    for event in PushEvent:
        tr = push_text(event, language="tr")
        en = push_text(event, language="en")
        assert tr[1] and en[1] and tr != en, event
    assert push_text(PushEvent.INCOMING_CALL, language="en", variant="video")[1] == "Incoming video call"
    assert push_text("not_an_event", language="xx")[1] == "Bir bildirimin var."


@pytest.mark.parametrize(
    ("event", "language", "body"),
    [
        (PushEvent.AI_REPORT_READY, "en", "Your Astro AI reading is ready."),
        (PushEvent.APPOINTMENT_REMINDER, "tr", "Yaklaşan bir randevun var."),
        (PushEvent.APPOINTMENT_CANCELLED, "en", "An appointment was cancelled."),
        (PushEvent.NEW_CHAT_MESSAGE, "en", "You have a new message."),
        (PushEvent.REFUND_PROCESSED, "tr", "İaden işlendi."),
        (PushEvent.DAILY_CONTENT, "en", "Today's sky is ready."),
    ],
)
async def test_queued_text_is_in_the_recipients_language(session_factory, user, event, language, body):
    await _set_language(session_factory, user.id, language)
    async with session_factory() as session:
        row = await OutboxService(session).enqueue(
            event=event, user_id=user.id, dedupe_key=f"lang:{event.value}",
            data={"order_id": "o-1"},
        )
        await session.commit()
    assert row.payload["body"] == body and row.payload["title"] == "Astrofrekans"
    assert row.payload["language"] == language
    # Canonical parts do not depend on language.
    assert row.event_type == event.value
    assert row.payload["data"] == {"event": event.value, "order_id": "o-1"}


async def test_delivery_uses_the_language_at_send_time_and_keeps_the_data(
    session_factory, firebase, voip, user
):
    await add_devices(session_factory, user, android=[ANDROID_TOKEN])
    async with session_factory() as session:
        row = await OutboxService(session).enqueue(
            event=PushEvent.APPOINTMENT_REMINDER, user_id=user.id, dedupe_key="send-time-lang",
            data={"appointment_id": "a-1", "minutes_before": "60"},
        )
        await session.commit()
    assert row.payload["body"] == "Yaklaşan bir randevun var."
    await _set_language(session_factory, user.id, "en")
    await deliver(session_factory, firebase, voip, row.id)
    [(_, message)] = firebase.push.sent
    assert message.body == "You have an upcoming appointment."
    assert message.data == {
        "event": "appointment_reminder",
        "appointment_id": "a-1",
        "minutes_before": "60",
        # The inbox record this push is: opening it marks the same one read.
        "notification_id": str(row.id),
    }


async def test_call_push_text_is_localised_and_its_data_unchanged(session_factory, firebase, voip, user):
    await _set_language(session_factory, user.id, "en")
    outbox_id, call_id = await enqueue_call(session_factory, user, PushEvent.CALL_MISSED)
    async with session_factory() as session:
        row = await session.get(NotificationOutbox, outbox_id)
    assert row.payload["body"] == "Missed video call"
    assert row.payload["data"]["call_id"] == call_id
    assert "notification_id" not in row.payload["data"]


# ======================================================== inbox & push


async def test_a_retried_event_is_one_record_and_one_unread(client, registered, session_factory, user):
    async with session_factory() as session:
        outbox = OutboxService(session)
        first = await outbox.enqueue(
            event=PushEvent.REFUND_PROCESSED, user_id=user.id, dedupe_key="refund_processed:r-1",
            data={"order_id": str(uuid.uuid4())},
        )
        again = await outbox.enqueue(
            event=PushEvent.REFUND_PROCESSED, user_id=user.id, dedupe_key="refund_processed:r-1",
            data={"order_id": str(uuid.uuid4())},
        )
        await session.commit()
    assert first is not None and again is None
    page = (await client.get(f"{API}/notifications", headers=registered["headers"])).json()
    assert [item["id"] for item in page["items"]] == [str(first.id)]
    assert page["unread_count"] == 1
    # Opening the push marks the same record; doing it twice changes nothing.
    for _ in range(2):
        marked = await client.patch(
            f"{API}/notifications/{first.id}", headers=registered["headers"], json={"read": True}
        )
        assert marked.json()["read"] is True
    count = (await client.get(f"{API}/notifications/unread-count", headers=registered["headers"])).json()
    assert count == {"unread_count": 0}


# ================================================================ search


async def test_search_finds_experts_beyond_the_first_500(client, registered, session_factory):
    from app.db.models.user import User

    async with session_factory() as session:
        owners = [User(email=f"bulk{index}@example.com") for index in range(521)]
        session.add_all(owners)
        await session.flush()
        # 520 experts, all rated above the one being searched for, so she
        # sorts last - past any fixed scan window.
        session.add_all(
            Expert(
                user_id=owners[index].id,
                display_name=f"Bulk {index}", languages=["en"], specialties=["astrology"],
                experience_years=1, timezone="UTC", status=ExpertStatus.ACTIVE.value,
                verified=False, rating_average=5, rating_count=index + 1,
            )
            for index in range(520)
        )
        session.add(Expert(
            user_id=owners[520].id, display_name="Zerrin Sonuncu", languages=["tr"],
            specialties=["tarot"], experience_years=1, timezone="UTC",
            status=ExpertStatus.ACTIVE.value, verified=False, rating_average=0, rating_count=0,
        ))
        await session.commit()
    found = (await client.get(f"{API}/experts", params={"q": "zerrin"}, headers=registered["headers"])).json()
    assert [item["display_name"] for item in found["items"]] == ["Zerrin Sonuncu"]
    by_language = (await client.get(
        f"{API}/experts", params={"language": "tr", "limit": 5}, headers=registered["headers"]
    )).json()
    assert by_language["total"] == 1
    by_specialty = (await client.get(
        f"{API}/experts", params={"specialty": "astrology", "limit": 10, "offset": 510},
        headers=registered["headers"],
    )).json()
    assert by_specialty["total"] == 520 and len(by_specialty["items"]) == 10


# ========================================================== firebase


@pytest.fixture
def fake_firebase(monkeypatch):
    from app.services.firebase import factory

    monkeypatch.setattr(settings, "firebase_provider", "fake")
    monkeypatch.setattr(settings, "firebase_project_id", "astrofrekans-test")
    providers = factory.fake_providers()
    factory.set_firebase(providers)
    yield providers
    factory.set_firebase(None)


async def test_a_firebase_sign_in_is_listed_honestly_and_not_revocable(client, fake_firebase):
    fake_firebase.identity.register(
        "fb-id-token-sessions-0001", uid="uid-sessions", email="fb@example.com", provider_id="google.com"
    )
    headers = {"Authorization": "Bearer fb-id-token-sessions-0001", "User-Agent": "Astrofrekans/1.0 (Android)"}
    me = (await client.get(f"{API}/users/me", headers=headers)).json()
    assert me["has_local_password"] is False and me["firebase_linked"] is True

    sessions = (await client.get(f"{API}/auth/sessions", headers=headers)).json()
    assert len(sessions) == 1
    [row] = sessions
    assert row["kind"] == "firebase" and row["revocable"] is False and row["current"] is True
    assert row["sign_in_provider"] == "google.com"
    assert "fb-id-token" not in str(row)

    refused = await client.delete(f"{API}/auth/sessions/{row['id']}", headers=headers)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "session_not_revocable"
    assert (await client.get(f"{API}/users/me", headers=headers)).status_code == 200


async def test_a_password_account_lists_revocable_sessions_only(client, registered):
    me = (await client.get(f"{API}/users/me", headers=registered["headers"])).json()
    assert me["has_local_password"] is True and me["firebase_linked"] is False
    sessions = (await client.get(f"{API}/auth/sessions", headers=registered["headers"])).json()
    assert sessions and all(row["kind"] == "password" and row["revocable"] for row in sessions)
    bad = await client.delete(f"{API}/auth/sessions/not-a-session", headers=registered["headers"])
    assert bad.status_code == 404
