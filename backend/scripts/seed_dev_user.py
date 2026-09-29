"""Seed a local development test user with a birth profile.

For clicking through the app against a LOCAL API only (web on
``http://localhost:3000`` or the Android emulator). Idempotent: registers the
user, or logs in if it already exists, then stores the birth profile.

    python scripts/seed_dev_user.py [--base-url http://localhost:8000]

Refuses any non-local base URL. The credentials below are test values for the
local database and must never be created on staging or production.
"""

from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse

import httpx

DEV_EMAIL = "dev.tester@example.com"
DEV_PASSWORD = "DevTester!2026"
DEV_NAME = "Dev Tester"
DEV_BIRTH_PROFILE = {
    "birth_date": "1990-05-15",
    "birth_time": "14:30:00",
    "birth_place": "İstanbul, Türkiye",
    "latitude": 41.0082,
    "longitude": 28.9784,
    "timezone": "Europe/Istanbul",
}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    if urlparse(args.base_url).hostname not in LOCAL_HOSTS:
        print("refused: seed_dev_user only targets a local API")
        return 2

    client = httpx.Client(base_url=f"{args.base_url.rstrip('/')}/api/v1", timeout=30)
    response = client.post(
        "/auth/register",
        json={"email": DEV_EMAIL, "password": DEV_PASSWORD, "name": DEV_NAME},
    )
    if response.status_code == 409:
        response = client.post(
            "/auth/login", json={"email": DEV_EMAIL, "password": DEV_PASSWORD}
        )
    response.raise_for_status()
    body = response.json()
    token = (body.get("tokens") or body)["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    profile = client.put("/birth-profiles/me", json=DEV_BIRTH_PROFILE)
    profile.raise_for_status()
    print(f"dev user ready: {DEV_EMAIL} (birth profile {profile.status_code})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
