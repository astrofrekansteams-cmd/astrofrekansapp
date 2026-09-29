"""Phase 6: production runs AUTH_MODE=hybrid. Server (local JWT) and Firebase
accounts both sign in, one address is never two accounts, and a password
reset goes only to the kind of account whose password lives here."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.db.models.user import User
from app.services.mail import mailer as mail_module
from tests.test_phase5_release import production, refusal  # noqa: F401 - fixture

API = "/api/v1"


def test_production_requires_hybrid(production):  # noqa: F811
    assert refusal() == ""
    for mode in ("local_jwt", "firebase"):
        production.setattr(settings, "auth_mode", mode)
        assert "AUTH_MODE must be hybrid in production" in refusal()


@pytest.fixture
def hybrid(client, monkeypatch):
    from app.services.firebase import factory

    monkeypatch.setattr(settings, "auth_mode", "hybrid")
    monkeypatch.setattr(settings, "firebase_provider", "fake")
    monkeypatch.setattr(settings, "firebase_project_id", "astrofrekans-test")
    monkeypatch.setattr(settings, "firebase_auto_link_verified_email", False)
    providers = factory.fake_providers()
    factory.set_firebase(providers)
    yield providers
    factory.set_firebase(None)


async def users(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(User))


async def test_both_kinds_of_account_sign_in(client, hybrid, registered):
    # A server account: backend email + password, local JWT.
    login = await client.post(
        f"{API}/auth/login", json={"email": registered["email"], "password": registered["password"]}
    )
    assert login.status_code == 200
    local = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.get(f"{API}/users/me", headers=local)).status_code == 200

    # A Firebase email/password account.
    hybrid.identity.register("fb-hybrid-new-0001", uid="uid-new", email="new@example.com")
    firebase = {"Authorization": "Bearer fb-hybrid-new-0001"}
    me = await client.get(f"{API}/users/me", headers=firebase)
    assert me.status_code == 200
    assert me.json()["email"] == "new@example.com"
    assert me.json()["has_local_password"] is False and me.json()["firebase_linked"] is True


@pytest.mark.parametrize("verified", [False, True])
async def test_a_firebase_sign_in_never_takes_or_duplicates_a_server_account(
    client, hybrid, registered, session_factory, verified
):
    before = await users(session_factory)
    hybrid.identity.register(
        "fb-hybrid-clash-0001", uid="uid-clash", email=registered["email"], email_verified=verified
    )
    refused = await client.post(
        f"{API}/auth/firebase/session",
        headers={"Authorization": "Bearer fb-hybrid-clash-0001"},
        json={"id_token": "fb-hybrid-clash-0001"},
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "account_link_required"
    assert await users(session_factory) == before
    # The server account itself is untouched and still signs in.
    login = await client.post(
        f"{API}/auth/login", json={"email": registered["email"], "password": registered["password"]}
    )
    assert login.status_code == 200


async def test_registering_an_address_a_firebase_account_owns_is_refused(
    client, hybrid, session_factory
):
    hybrid.identity.register("fb-hybrid-owner-0001", uid="uid-owner", email="owner@example.com")
    assert (
        await client.get(f"{API}/users/me", headers={"Authorization": "Bearer fb-hybrid-owner-0001"})
    ).status_code == 200
    before = await users(session_factory)
    taken = await client.post(
        f"{API}/auth/register",
        json={"email": "owner@example.com", "password": "Str0ngPassphrase!", "name": "Someone",
              "birth_date": "1990-01-01"},
    )
    assert taken.status_code == 409
    assert taken.json()["error"]["code"] == "email_in_use"
    assert await users(session_factory) == before


async def test_the_server_resets_only_server_passwords(client, hybrid, registered):
    memory = mail_module.MemoryMailer()
    mail_module.set_mailer(memory)
    try:
        hybrid.identity.register("fb-hybrid-reset-0001", uid="uid-reset", email="fire@example.com")
        await client.get(f"{API}/users/me", headers={"Authorization": "Bearer fb-hybrid-reset-0001"})

        answers = []
        for email in (registered["email"], "fire@example.com", "nobody@example.com"):
            response = await client.post(f"{API}/auth/forgot-password", json={"email": email})
            answers.append((response.status_code, response.json()["message"]))
        # Same answer for a server account, a Firebase account and no account.
        assert len(set(answers)) == 1
        # Only the server account got a link; the Firebase one resets through
        # Firebase (the app asks Firebase too), so no backend password is ever
        # created on a Firebase account.
        assert [m.to for m in memory.outbox] == [registered["email"]]
    finally:
        mail_module.set_mailer(None)


async def test_without_mail_the_server_says_so_for_everyone(client, hybrid, registered):
    mail_module.set_mailer(mail_module.DisabledMailer())
    try:
        codes = {
            (await client.post(f"{API}/auth/forgot-password", json={"email": e})).json()["error"]["code"]
            for e in (registered["email"], "nobody@example.com")
        }
        assert codes == {"password_reset_unavailable"}
    finally:
        mail_module.set_mailer(None)
