"""Test fixtures.

The suite runs entirely offline: SQLite instead of Postgres, the in-memory
cache instead of Redis, and the mock geocoder. Only the astrology engine is
the real one - its correctness is the point of the regression tests.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("JWT_SECRET", "test-secret-value-not-used-in-production")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-refresh-secret-not-in-production")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("GEOCODING_PROVIDER", "mock")
# Premium gating has its own tests (test_features.py) that switch it on; every
# other test exercises the feature itself with a free test user.
os.environ.setdefault("PREMIUM_GATING_ENABLED", "false")
# Password-reset mail is captured in memory; tests read what would be sent.
os.environ.setdefault("MAIL_PROVIDER", "memory")

# Hermetic by construction. Settings also reads the developer's `.env`, which
# from B13C on holds real staging credentials (Firebase service account,
# later OpenAI, LiveKit, APNs, store keys). A test must never reach a real
# project - one that does not use a fake fixture would otherwise write to
# staging Firestore. So every provider credential is forced empty here, over
# both `.env` and the shell: environment variables outrank the dotenv file,
# and blank values read as unset (`_blank_is_unset`).
for _credential in (
    "FIREBASE_PROJECT_ID",
    "FIREBASE_CREDENTIALS_PATH",
    "FIREBASE_CREDENTIALS_JSON",
    "FIREBASE_STORAGE_BUCKET",
    "FIREBASE_DATABASE_URL",
    "OPENAI_API_KEY",
    "LIVEKIT_URL",
    "LIVEKIT_API_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "APNS_TEAM_ID",
    "APNS_KEY_ID",
    "APNS_PRIVATE_KEY",
    "APNS_PRIVATE_KEY_PATH",
    "APNS_BUNDLE_ID",
    "APPLE_BUNDLE_ID",
    "APPLE_APP_APPLE_ID",
    "APPLE_ISSUER_ID",
    "APPLE_KEY_ID",
    "APPLE_PRIVATE_KEY",
    "APPLE_PRIVATE_KEY_PATH",
    "APPLE_ROOT_CERTIFICATES_PATH",
    "GOOGLE_PLAY_PACKAGE_NAME",
    "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON",
    "GOOGLE_PLAY_SERVICE_ACCOUNT_PATH",
    "GOOGLE_PUBSUB_PUSH_AUDIENCE",
    "GOOGLE_PUBSUB_PUSH_SERVICE_ACCOUNT",
    "STORE_PRODUCT_IDS",
):
    os.environ[_credential] = ""

import httpx  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.cache import InMemoryCache  # noqa: E402
from app.db.base import Base  # noqa: E402
import app.db.models  # noqa: F401,E402  (register the tables)
from app.db.session import get_db_session  # noqa: E402
from app.main import create_app  # noqa: E402

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_engine() -> AsyncIterator:
    # One shared in-memory database for the lifetime of a test.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=None,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine) -> async_sessionmaker:
    # Named db_engine, not engine: the astrology engine is also a fixture.
    return async_sessionmaker(bind=db_engine, expire_on_commit=False, autoflush=False)


@pytest.fixture
async def db_session(session_factory) -> AsyncIterator:
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(session_factory, monkeypatch) -> AsyncIterator[httpx.AsyncClient]:
    from app.core import cache as cache_module

    cache_module._cache = InMemoryCache()

    app = create_app()

    async def override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    from app.api.deps import get_session

    app.dependency_overrides[get_session] = override_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http_client:
        yield http_client

    cache_module._cache = None


@pytest.fixture
async def registered(client: httpx.AsyncClient) -> dict:
    """A signed-up user with birth data and ready-to-use tokens."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "nova@example.com",
            "password": "Str0ngPassphrase!",
            "name": "Nova",
            "birth_date": "1992-05-14",
            "birth_time": "14:30:00",
            "birth_place": "Istanbul",
        },
    )
    assert response.status_code == 201, response.text
    tokens = response.json()
    return {
        "tokens": tokens,
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
        "email": "nova@example.com",
        "password": "Str0ngPassphrase!",
    }


@pytest.fixture
def legacy_products_sellable(monkeypatch):
    """Sell the legacy one-off report products again, for tests only.

    Production never sells them (`ProductDefinition.sellable=False`); reports
    are paid with AstroCoin or included in a plan. The credit machinery they
    used stays in the code for records bought before, and these tests keep it
    covered by switching the sale back on inside the test.
    """
    from dataclasses import replace

    from app.services.payments import catalog

    monkeypatch.setattr(
        catalog, "CATALOG", tuple(replace(d, sellable=True) for d in catalog.CATALOG)
    )
    monkeypatch.setattr(catalog, "LEGACY_CODES", ())
