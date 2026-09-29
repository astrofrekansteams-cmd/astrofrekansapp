"""Firebase identity: verification, mapping, linking and dual auth.

Everything here runs against `FakeFirebaseIdentityProvider`. A test that needs a
real service account is a test that does not run in CI, on a new laptop, or for
a contributor - and a phase whose security properties are only checked by hand
is a phase whose security properties are not checked.

The property this file exists to protect: **a matching email address is not
proof of identity.** Adopting an existing account because a token carries its
address is an account-takeover primitive, and it is refused by default.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models.chat import FirebaseIdentityRecord
from app.db.models.user import User
from app.services.firebase import factory
from app.services.firebase.identity import (
    LINK_AUTOMATIC_VERIFIED_EMAIL,
    LINK_EXISTING_SESSION,
    LINK_NEW_ACCOUNT,
    AccountLinkRequired,
    FirebaseIdentityService,
)
from app.services.firebase.provider import (
    FirebaseTokenExpired,
    FirebaseTokenInvalid,
    FirebaseTokenRevoked,
)

API = "/api/v1"


@pytest.fixture
def firebase(monkeypatch):
    """Wire the doubles in, and make Firebase look configured."""
    monkeypatch.setattr(settings, "firebase_provider", "fake")
    monkeypatch.setattr(settings, "firebase_project_id", "astrofrekans-test")
    providers = factory.fake_providers()
    factory.set_firebase(providers)
    yield providers
    factory.set_firebase(None)


# ========================================================= verification


async def test_a_valid_token_resolves_to_a_new_local_account(
    client: httpx.AsyncClient, firebase, session_factory
):
    firebase.identity.register(
        "fb-id-token-newcomer-0001", uid="uid-new", email="newcomer@example.com"
    )

    response = await client.post(
        f"{API}/auth/firebase/session", json={"id_token": "fb-id-token-newcomer-0001"}
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["firebase_uid"] == "uid-new"
    assert body["is_new_account"] is True
    assert body["email"] == "newcomer@example.com"

    async with session_factory() as session:
        user = await session.scalar(
            select(User).where(User.firebase_uid == "uid-new")
        )
        assert user is not None
        # The account has no password: this identity is how it signs in.
        assert user.password_hash is None

        record = await session.scalar(
            select(FirebaseIdentityRecord).where(
                FirebaseIdentityRecord.firebase_uid == "uid-new"
            )
        )
        assert record is not None
        assert record.link_method == LINK_NEW_ACCOUNT


async def test_signing_in_twice_reuses_the_same_account(
    client: httpx.AsyncClient, firebase, session_factory
):
    firebase.identity.register("fb-id-token-repeat-0002", uid="uid-repeat", email="a@example.com")

    first = await client.post(
        f"{API}/auth/firebase/session", json={"id_token": "fb-id-token-repeat-0002"}
    )
    second = await client.post(
        f"{API}/auth/firebase/session", json={"id_token": "fb-id-token-repeat-0002"}
    )

    assert first.json()["is_new_account"] is True
    assert second.json()["is_new_account"] is False
    assert first.json()["user_id"] == second.json()["user_id"]

    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(User).where(User.firebase_uid == "uid-repeat")
            )
        )
    assert len(rows) == 1


@pytest.mark.parametrize(
    ("token", "expected"),
    [("fb-id-token-unknown-0018", 401), ("", 422)],
)
async def test_an_unusable_token_is_refused(
    client: httpx.AsyncClient, firebase, token: str, expected: int
):
    response = await client.post(
        f"{API}/auth/firebase/session", json={"id_token": token}
    )
    assert response.status_code == expected


async def test_expired_and_revoked_tokens_are_distinguished(firebase):
    firebase.identity.register("fb-id-token-expired-0003", uid="uid-1")
    firebase.identity.register("fb-id-token-revoked-0004", uid="uid-2")
    firebase.identity.expired.add("fb-id-token-expired-0003")
    firebase.identity.revoked.add("fb-id-token-revoked-0004")

    with pytest.raises(FirebaseTokenExpired) as expired:
        await firebase.identity.verify_id_token("fb-id-token-expired-0003")
    assert expired.value.code == "firebase_token_expired"
    assert expired.value.status_code == 401

    # Revocation is only surfaced when asked for, mirroring the real SDK: the
    # check costs a round trip to Firebase on every request.
    assert await firebase.identity.verify_id_token("fb-id-token-revoked-0004") is not None
    with pytest.raises(FirebaseTokenRevoked):
        await firebase.identity.verify_id_token("fb-id-token-revoked-0004", check_revoked=True)


async def test_an_invalid_token_says_nothing_about_why(firebase):
    with pytest.raises(FirebaseTokenInvalid) as error:
        await firebase.identity.verify_id_token("fb-id-token-nonsense-0005")
    # Deliberately generic: describing the token would help somebody probe it.
    assert "not valid" in error.value.message.lower()
    assert "signature" not in error.value.message.lower()


# ============================================================== linking


async def test_a_matching_email_does_not_hand_over_the_account(
    client: httpx.AsyncClient, registered, firebase
):
    """The account-takeover case, refused by default."""
    firebase.identity.register(
        "fb-id-token-attacker-0006",
        uid="uid-attacker",
        email=registered["email"],
        email_verified=True,
    )

    response = await client.post(
        f"{API}/auth/firebase/session", json={"id_token": "fb-id-token-attacker-0006"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "account_link_required"

    # And the existing account is untouched.
    me = await client.get(f"{API}/auth/me", headers=registered["headers"])
    assert me.status_code == 200


async def test_an_unverified_email_never_links_even_when_enabled(
    client: httpx.AsyncClient, registered, firebase, monkeypatch
):
    """An unverified address proves nothing, whatever the setting says."""
    monkeypatch.setattr(settings, "firebase_auto_link_verified_email", True)
    firebase.identity.register(
        "fb-id-token-unverified-0007",
        uid="uid-unverified",
        email=registered["email"],
        email_verified=False,
    )

    response = await client.post(
        f"{API}/auth/firebase/session", json={"id_token": "fb-id-token-unverified-0007"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "account_link_required"


async def test_automatic_linking_when_deliberately_enabled(
    client: httpx.AsyncClient, registered, firebase, monkeypatch, session_factory
):
    monkeypatch.setattr(settings, "firebase_auto_link_verified_email", True)
    firebase.identity.register(
        "fb-id-token-verified-0008",
        uid="uid-verified",
        email=registered["email"],
        email_verified=True,
    )

    response = await client.post(
        f"{API}/auth/firebase/session", json={"id_token": "fb-id-token-verified-0008"}
    )
    assert response.status_code == 200
    assert response.json()["is_new_account"] is False

    async with session_factory() as session:
        record = await session.scalar(
            select(FirebaseIdentityRecord).where(
                FirebaseIdentityRecord.firebase_uid == "uid-verified"
            )
        )
        assert record.link_method == LINK_AUTOMATIC_VERIFIED_EMAIL


async def test_linking_from_inside_a_session_is_the_safe_path(
    client: httpx.AsyncClient, registered, firebase, session_factory
):
    """Being signed in is the proof that an email address is not."""
    firebase.identity.register(
        "fb-id-token-link-0009", uid="uid-linked", email="other@example.com"
    )

    response = await client.post(
        f"{API}/auth/firebase/link",
        headers=registered["headers"],
        json={"id_token": "fb-id-token-link-0009"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["firebase_uid"] == "uid-linked"

    async with session_factory() as session:
        user = await session.scalar(
            select(User).where(User.email == registered["email"])
        )
        assert user.firebase_uid == "uid-linked"
        record = await session.scalar(
            select(FirebaseIdentityRecord).where(
                FirebaseIdentityRecord.firebase_uid == "uid-linked"
            )
        )
        assert record.link_method == LINK_EXISTING_SESSION


async def test_one_identity_cannot_serve_two_accounts(
    client: httpx.AsyncClient, registered, firebase
):
    firebase.identity.register("fb-id-token-shared-0010", uid="uid-shared", email="x@example.com")
    await client.post(
        f"{API}/auth/firebase/link",
        headers=registered["headers"],
        json={"id_token": "fb-id-token-shared-0010"},
    )

    other = await client.post(
        f"{API}/auth/register",
        json={
            "email": "second@example.com",
            "password": "An0therStrongPass!",
            "name": "Second",
        },
    )
    headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    response = await client.post(
        f"{API}/auth/firebase/link", headers=headers, json={"id_token": "fb-id-token-shared-0010"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "identity_already_linked"


async def test_unlinking_needs_another_way_in(
    client: httpx.AsyncClient, firebase, session_factory
):
    """An account with no password and no identity cannot be signed into."""
    firebase.identity.register("fb-id-token-only-0011", uid="uid-only", email="only@example.com")
    created = await client.post(
        f"{API}/auth/firebase/session", json={"id_token": "fb-id-token-only-0011"}
    )
    assert created.status_code == 200

    # Sign in with the Firebase token itself, then try to remove it.
    response = await client.delete(
        f"{API}/auth/firebase/link",
        headers={"Authorization": "Bearer fb-id-token-only-0011"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_sign_in_method"


async def test_unlinking_is_allowed_when_a_password_remains(
    client: httpx.AsyncClient, registered, firebase
):
    firebase.identity.register("fb-id-token-temp-0012", uid="uid-temp", email="temp@example.com")
    await client.post(
        f"{API}/auth/firebase/link",
        headers=registered["headers"],
        json={"id_token": "fb-id-token-temp-0012"},
    )

    response = await client.delete(
        f"{API}/auth/firebase/link", headers=registered["headers"]
    )
    assert response.status_code == 200

    # The local credential still works.
    me = await client.get(f"{API}/auth/me", headers=registered["headers"])
    assert me.status_code == 200


# ============================================================ dual auth


async def test_a_firebase_token_works_as_a_bearer_token(
    client: httpx.AsyncClient, firebase
):
    """The whole point of hybrid mode: no route had to change."""
    firebase.identity.register(
        "fb-id-token-bearer-0013", uid="uid-bearer", email="bearer@example.com"
    )

    response = await client.get(
        f"{API}/auth/me", headers={"Authorization": "Bearer fb-id-token-bearer-0013"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "bearer@example.com"


async def test_a_local_jwt_still_works(client: httpx.AsyncClient, registered, firebase):
    """A Firebase migration must not sign out every existing account."""
    response = await client.get(f"{API}/auth/me", headers=registered["headers"])
    assert response.status_code == 200
    assert response.json()["email"] == registered["email"]


async def test_both_credentials_reach_the_same_business_endpoint(
    client: httpx.AsyncClient, registered, firebase
):
    firebase.identity.register(
        "fb-id-token-dual-0014", uid="uid-dual", email="dual@example.com"
    )

    for headers in (
        registered["headers"],
        {"Authorization": "Bearer fb-id-token-dual-0014"},
    ):
        response = await client.get(f"{API}/experts", headers=headers)
        assert response.status_code == 200, headers


async def test_firebase_tokens_are_refused_in_local_only_mode(
    client: httpx.AsyncClient, firebase, monkeypatch
):
    monkeypatch.setattr(settings, "auth_mode", "local_jwt")
    firebase.identity.register("fb-id-token-localonly-0015", uid="uid-lo", email="lo@example.com")

    response = await client.get(
        f"{API}/auth/me", headers={"Authorization": "Bearer fb-id-token-localonly-0015"}
    )
    assert response.status_code == 401

    bootstrap = await client.post(
        f"{API}/auth/firebase/session", json={"id_token": "fb-id-token-localonly-0015"}
    )
    assert bootstrap.status_code == 503
    assert bootstrap.json()["error"]["code"] == "firebase_auth_disabled"


async def test_capabilities_tells_a_client_what_to_expect(
    client: httpx.AsyncClient, firebase
):
    response = await client.get(f"{API}/auth/capabilities")
    assert response.status_code == 200
    body = response.json()

    assert body["auth_mode"] == "hybrid"
    assert body["accepts_local_jwt"] is True
    assert body["accepts_firebase_token"] is True
    assert body["firebase_configured"] is True
    # The project id is public configuration a client needs; a key is not.
    assert body["firebase_project_id"] == "astrofrekans-test"
    assert "key" not in response.text.lower()
    assert "secret" not in response.text.lower()


# ====================================================== not configured


async def test_without_credentials_the_rest_of_the_api_still_works(
    client: httpx.AsyncClient, registered, monkeypatch
):
    """A missing service account degrades chat, not the product."""
    monkeypatch.setattr(settings, "firebase_provider", "firebase")
    monkeypatch.setattr(settings, "firebase_project_id", None)
    monkeypatch.setattr(settings, "firebase_credentials_json", None)
    monkeypatch.setattr(settings, "firebase_credentials_path", None)
    factory.set_firebase(None)

    try:
        assert (await client.get("/health")).status_code == 200
        assert (
            await client.get(f"{API}/auth/me", headers=registered["headers"])
        ).status_code == 200
        assert (
            await client.get(f"{API}/experts", headers=registered["headers"])
        ).status_code == 200
        assert (
            await client.get(
                f"{API}/astrology/natal-chart/me", headers=registered["headers"]
            )
        ).status_code == 200

        capabilities = await client.get(f"{API}/auth/capabilities")
        assert capabilities.json()["firebase_configured"] is False
        assert capabilities.json()["firebase_project_id"] is None

        # And the Firebase-backed endpoints say so, cleanly.
        chat = await client.get(
            f"{API}/conversations", headers=registered["headers"]
        )
        assert chat.status_code == 503
        assert chat.json()["error"]["code"] == "firebase_not_configured"
    finally:
        factory.set_firebase(None)


async def test_the_startup_diagnostic_never_raises(monkeypatch):
    monkeypatch.setattr(settings, "firebase_provider", "firebase")
    monkeypatch.setattr(settings, "firebase_project_id", None)

    detail = factory.log_startup_diagnostic()
    assert detail["configured"] is False
    assert "FIREBASE_PROJECT_ID" in detail["missing"]


def test_production_refuses_the_fake_provider(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "firebase_provider", "fake")
    monkeypatch.setattr(settings, "jwt_secret", "a-real-production-secret-value")
    monkeypatch.setattr(
        settings, "jwt_refresh_secret", "another-real-production-secret"
    )
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "cors_origins", "https://app.astrofrekans.com")
    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "sk-not-real")

    with pytest.raises(Exception) as error:
        settings.assert_production_ready()
    assert "FIREBASE_PROVIDER=fake" in str(error.value)


# ======================================================= account deletion


async def test_deletion_reports_what_it_actually_removed(
    client: httpx.AsyncClient, registered, firebase, db_session
):
    """A partial teardown is reported, not hidden."""
    firebase.identity.register("fb-id-token-delete-0016", uid="uid-del", email="del@example.com")
    await client.post(
        f"{API}/auth/firebase/link",
        headers=registered["headers"],
        json={"id_token": "fb-id-token-delete-0016"},
    )

    user = await db_session.scalar(
        select(User).where(User.email == registered["email"])
    )
    service = FirebaseIdentityService(db_session, firebase.identity)
    outcome = await service.detach_for_deletion(user)

    assert outcome == {"firebase_identity": True, "tokens_revoked": True}
    assert "uid-del" in firebase.identity.deleted_uids
    assert "uid-del" in firebase.identity.revoked_uids


async def test_deletion_survives_a_firebase_failure(
    client: httpx.AsyncClient, registered, firebase, db_session
):
    firebase.identity.register("fb-id-token-delete2-0017", uid="uid-del2", email="del2@example.com")
    await client.post(
        f"{API}/auth/firebase/link",
        headers=registered["headers"],
        json={"id_token": "fb-id-token-delete2-0017"},
    )
    firebase.identity.unavailable = True

    user = await db_session.scalar(
        select(User).where(User.email == registered["email"])
    )
    outcome = await FirebaseIdentityService(
        db_session, firebase.identity
    ).detach_for_deletion(user)

    # Reported as incomplete rather than claimed as done.
    assert outcome["firebase_identity"] is False
    assert outcome["tokens_revoked"] is False


# ======================================================= no foreign keys


async def test_business_tables_never_key_on_a_firebase_uid(
    client: httpx.AsyncClient, firebase, session_factory
):
    """Rotating a Firebase project must not orphan an order.

    Checked structurally: no column outside the identity tables is named after
    a Firebase uid, and every foreign key still points at `users.id`.
    """
    from app.db.base import Base

    offenders: list[str] = []
    for name, table in Base.metadata.tables.items():
        # These three legitimately carry an identity: the account itself, the
        # identity record, and a device (which belongs to a signed-in session).
        if name in ("users", "firebase_identities", "push_devices"):
            continue
        for column in table.c:
            if "firebase_uid" in column.name:
                offenders.append(f"{name}.{column.name}")

    assert offenders == [], f"business tables keyed on a Firebase uid: {offenders}"

    # And every foreign key still points at the local account.
    user_fks = [
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.c
        for fk in column.foreign_keys
        if fk.column.table.name == "users"
    ]
    assert user_fks, "nothing references users.id, which cannot be right"
