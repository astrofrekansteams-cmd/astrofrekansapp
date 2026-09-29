"""Authentication flows, including the security-critical ones."""

from __future__ import annotations

import httpx
import pytest

from app.core.security import (
    create_token_pair,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.exceptions import TokenError

API = "/api/v1"


# ------------------------------------------------------------------ hashing


def test_password_hash_is_argon2_and_verifies():
    hashed = hash_password("Str0ngPassphrase!")
    assert hashed.startswith("$argon2")
    assert "Str0ngPassphrase!" not in hashed
    assert verify_password("Str0ngPassphrase!", hashed)
    assert not verify_password("wrong", hashed)


def test_same_password_hashes_differently():
    assert hash_password("same-password") != hash_password("same-password")


def test_refresh_tokens_are_stored_as_digests():
    pair = create_token_pair(__import__("uuid").uuid4())
    digest = hash_token(pair.refresh_token)
    assert len(digest) == 64
    assert pair.refresh_token not in digest


def test_access_token_cannot_be_used_as_refresh_token():
    pair = create_token_pair(__import__("uuid").uuid4())
    with pytest.raises(TokenError):
        decode_token(pair.access_token, token_type="refresh")
    with pytest.raises(TokenError):
        decode_token(pair.refresh_token, token_type="access")


def test_tampered_token_is_rejected():
    pair = create_token_pair(__import__("uuid").uuid4())
    tampered = pair.access_token[:-4] + "aaaa"
    with pytest.raises(TokenError):
        decode_token(tampered, token_type="access")


# -------------------------------------------------------------------- flows


async def test_register_returns_tokens_and_creates_profile(client: httpx.AsyncClient):
    response = await client.post(
        f"{API}/auth/register",
        json={
            "email": "Orion@Example.com",
            "password": "Str0ngPassphrase!",
            "name": "Orion",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["access_token"] and body["refresh_token"]

    me = await client.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "orion@example.com"  # normalised
    assert me.json()["name"] == "Orion"
    assert me.json()["subscription_tier"] == "free"


async def test_register_rejects_duplicate_email(client: httpx.AsyncClient, registered):
    response = await client.post(
        f"{API}/auth/register",
        json={
            "email": registered["email"].upper(),
            "password": "AnotherPassphrase1",
            "name": "Copy",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_in_use"


async def test_register_rejects_weak_password(client: httpx.AsyncClient):
    response = await client.post(
        f"{API}/auth/register",
        json={"email": "weak@example.com", "password": "short", "name": "Weak"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_login_succeeds_and_wrong_password_fails(
    client: httpx.AsyncClient, registered
):
    good = await client.post(
        f"{API}/auth/login",
        json={"email": registered["email"], "password": registered["password"]},
    )
    assert good.status_code == 200

    bad = await client.post(
        f"{API}/auth/login",
        json={"email": registered["email"], "password": "not-the-password"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_credentials"


async def test_login_does_not_reveal_whether_an_account_exists(
    client: httpx.AsyncClient, registered
):
    unknown = await client.post(
        f"{API}/auth/login",
        json={"email": "nobody@example.com", "password": "whatever-password"},
    )
    known = await client.post(
        f"{API}/auth/login",
        json={"email": registered["email"], "password": "wrong-password"},
    )
    assert unknown.status_code == known.status_code == 401
    assert unknown.json()["error"] == known.json()["error"]


async def test_refresh_rotates_the_token(client: httpx.AsyncClient, registered):
    first = registered["tokens"]["refresh_token"]
    response = await client.post(f"{API}/auth/refresh", json={"refresh_token": first})
    assert response.status_code == 200
    rotated = response.json()["refresh_token"]
    assert rotated != first

    # The rotated token works...
    second = await client.post(f"{API}/auth/refresh", json={"refresh_token": rotated})
    assert second.status_code == 200


async def test_reusing_a_rotated_refresh_token_kills_the_session(
    client: httpx.AsyncClient, registered
):
    original = registered["tokens"]["refresh_token"]
    rotated = (
        await client.post(f"{API}/auth/refresh", json={"refresh_token": original})
    ).json()["refresh_token"]

    replayed = await client.post(f"{API}/auth/refresh", json={"refresh_token": original})
    assert replayed.status_code == 401
    assert replayed.json()["error"]["code"] == "token_reused"

    # The whole family is revoked, so the newest token is dead too.
    after = await client.post(f"{API}/auth/refresh", json={"refresh_token": rotated})
    assert after.status_code == 401


async def test_logout_revokes_the_refresh_token(client: httpx.AsyncClient, registered):
    token = registered["tokens"]["refresh_token"]
    logout = await client.post(f"{API}/auth/logout", json={"refresh_token": token})
    assert logout.status_code == 200

    response = await client.post(f"{API}/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401


async def test_protected_endpoint_requires_a_token(client: httpx.AsyncClient):
    assert (await client.get(f"{API}/auth/me")).status_code == 401
    assert (
        await client.get(f"{API}/auth/me", headers={"Authorization": "Bearer nonsense"})
    ).status_code == 401


async def test_password_reset_flow(
    client: httpx.AsyncClient, registered, session_factory
):
    start = await client.post(
        f"{API}/auth/forgot-password", json={"email": registered["email"]}
    )
    assert start.status_code == 200
    # The response never carries the token; it goes to the user by email.
    assert "eyJ" not in start.json()["message"]

    # Stand in for the mailer: issue the token through the service directly.
    from app.services.auth.service import AuthService

    async with session_factory() as session:
        token = await AuthService(session).request_password_reset(
            email=registered["email"]
        )
        await session.commit()
    assert token

    reset = await client.post(
        f"{API}/auth/reset-password",
        json={"token": token, "new_password": "BrandNewPassphrase9"},
    )
    assert reset.status_code == 200

    # Old password no longer works, new one does.
    old = await client.post(
        f"{API}/auth/login",
        json={"email": registered["email"], "password": registered["password"]},
    )
    assert old.status_code == 401
    new = await client.post(
        f"{API}/auth/login",
        json={"email": registered["email"], "password": "BrandNewPassphrase9"},
    )
    assert new.status_code == 200

    # The reset token is single use.
    again = await client.post(
        f"{API}/auth/reset-password",
        json={"token": token, "new_password": "YetAnotherPassphrase1"},
    )
    assert again.status_code == 401


async def test_forgot_password_is_silent_for_unknown_addresses(
    client: httpx.AsyncClient,
):
    known = await client.post(
        f"{API}/auth/forgot-password", json={"email": "ghost@example.com"}
    )
    assert known.status_code == 200
    assert known.json()["message"] == "If the account is eligible, a reset link has been sent."


async def test_changing_the_password_revokes_sessions(
    client: httpx.AsyncClient, registered
):
    response = await client.post(
        f"{API}/auth/change-password",
        headers=registered["headers"],
        json={
            "current_password": registered["password"],
            "new_password": "RotatedPassphrase12",
        },
    )
    assert response.status_code == 200

    refresh = await client.post(
        f"{API}/auth/refresh",
        json={"refresh_token": registered["tokens"]["refresh_token"]},
    )
    assert refresh.status_code == 401


async def test_error_envelope_shape(client: httpx.AsyncClient):
    response = await client.get(f"{API}/auth/me")
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert "x-request-id" in response.headers
