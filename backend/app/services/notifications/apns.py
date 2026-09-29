"""APNs PushKit VoIP delivery - iOS incoming calls only.

Verified against Apple's documentation (2026-09-25):

* HTTP/2 and TLS 1.2+ to `api.push.apple.com` (production) or
  `api.sandbox.push.apple.com` (development), `POST /3/device/<token>`.
* Token-based authentication: an ES256 JWT, header `kid` (key id), claims
  `iss` (team id) and `iat`, sent as `authorization: bearer <jwt>`. Refresh
  "no more than once every 20 minutes and no less than once every 60
  minutes"; an `iat` older than an hour is `ExpiredProviderToken`.
* `apns-push-type: voip`, and "the `apns-topic` header field must use your
  app's bundle ID with `.voip` appended to the end".
* `apns-expiration`: "0, or only a few seconds" for VoIP, so a call is never
  delivered after it stopped ringing. 0: "APNs attempts to deliver the
  notification only once and doesn't store it."
* VoIP payloads are limited to 5 KB. Ours is five short strings.
* Permanent token failures: `BadDeviceToken` (400), `Unregistered` (410),
  `DeviceTokenNotForTopic` (400) - the credential is disabled. 429 and 5xx
  are retryable. Other 4xx are our configuration and are not retried.

PushKit's own rule shapes what this carries: since the iOS 13 SDK every VoIP
push must be reported to CallKit as a new incoming call, and Apple says not to
send further pushes to cancel it. So this transport carries `incoming_call`
and nothing else.

The token is a secret-like device credential: it is in the request path, so
neither the URL nor the token is ever logged - only a fingerprint.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import httpx
import jwt

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

HOSTS = {
    "production": "https://api.push.apple.com",
    "sandbox": "https://api.sandbox.push.apple.com",
}

# Refresh the provider JWT inside Apple's 20-60 minute window.
JWT_REFRESH_SECONDS = 40 * 60

PERMANENT_TOKEN_REASONS = frozenset({"BadDeviceToken", "Unregistered", "DeviceTokenNotForTopic"})
RETRYABLE_REASONS = frozenset(
    {"TooManyRequests", "InternalServerError", "ServiceUnavailable", "Shutdown", "ExpiredProviderToken"}
)


@dataclass(slots=True, frozen=True)
class ApnsResult:
    # sent | invalid_token | retry | failed | not_configured
    outcome: str
    reason: str | None = None
    status_code: int | None = None


@runtime_checkable
class AppleVoipPushProvider(Protocol):
    name: str

    @property
    def available(self) -> bool: ...

    async def send_voip(
        self,
        token: str,
        payload: dict[str, str],
        *,
        environment: str,
        expiration: int,
        apns_id: str,
    ) -> ApnsResult: ...

    async def close(self) -> None: ...


def classify(status_code: int, reason: str | None) -> str:
    if status_code == 200:
        return "sent"
    if reason in PERMANENT_TOKEN_REASONS or status_code == 410:
        return "invalid_token"
    if status_code == 429 or status_code >= 500 or reason in RETRYABLE_REASONS:
        return "retry"
    return "failed"


class ApnsHttpProvider:
    """The real provider: APNs HTTP/2 with a token-based (.p8) JWT."""

    name = "apns"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._jwt: str | None = None
        self._jwt_issued: float = 0.0

    @property
    def available(self) -> bool:
        return settings.apns_provider == "apns" and settings.apns_configured

    def _private_key(self) -> str:
        if settings.apns_private_key:
            return settings.apns_private_key
        assert settings.apns_private_key_path is not None
        return settings.apns_private_key_path.read_text(encoding="utf-8")

    def _provider_token(self) -> str:
        now = time.time()
        if self._jwt is None or now - self._jwt_issued >= JWT_REFRESH_SECONDS:
            self._jwt = jwt.encode(
                {"iss": settings.apns_team_id, "iat": int(now)},
                self._private_key(),
                algorithm="ES256",
                headers={"kid": settings.apns_key_id},
            )
            self._jwt_issued = now
        return self._jwt

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=self._transport is None,
                transport=self._transport,
                timeout=settings.apns_timeout_seconds,
            )
        return self._client

    async def send_voip(
        self,
        token: str,
        payload: dict[str, str],
        *,
        environment: str,
        expiration: int,
        apns_id: str,
    ) -> ApnsResult:
        if not self.available:
            return ApnsResult("not_configured", "apns_not_configured")
        host = HOSTS.get(environment)
        if host is None:
            return ApnsResult("failed", "unknown_environment")
        headers = {
            "authorization": f"bearer {self._provider_token()}",
            "apns-push-type": "voip",
            "apns-topic": f"{settings.apns_bundle_id}.voip",
            "apns-priority": "10",
            "apns-expiration": str(expiration),
            "apns-id": apns_id,
            "content-type": "application/json",
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        try:
            response = await self._http().post(f"{host}/3/device/{token}", headers=headers, content=body)
        except httpx.HTTPError:
            return ApnsResult("retry", "network_error")

        reason: str | None = None
        if response.status_code != 200:
            try:
                reason = str((response.json() or {}).get("reason") or "") or None
            except ValueError:
                reason = None
        outcome = classify(response.status_code, reason)
        if reason == "ExpiredProviderToken":
            self._jwt = None
        return ApnsResult(outcome, reason, response.status_code)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


@dataclass
class FakeApnsProvider:
    """In-memory APNs. Records exactly what would have been sent.

    Refused in production by `assert_production_ready`.
    """

    name: str = "fake"
    requests: list[dict[str, Any]] = field(default_factory=list)
    # token -> APNs reason to answer with (e.g. "Unregistered", "ServiceUnavailable").
    reasons: dict[str, str] = field(default_factory=dict)
    unavailable: bool = False

    @property
    def available(self) -> bool:
        return not self.unavailable

    async def send_voip(
        self,
        token: str,
        payload: dict[str, str],
        *,
        environment: str,
        expiration: int,
        apns_id: str,
    ) -> ApnsResult:
        if not self.available:
            return ApnsResult("not_configured", "apns_not_configured")
        self.requests.append(
            {
                "host": HOSTS[environment],
                "path": f"/3/device/{token}",
                "token": token,
                "headers": {
                    "apns-push-type": "voip",
                    "apns-topic": f"{settings.apns_bundle_id or 'com.astrofrekans.app'}.voip",
                    "apns-priority": "10",
                    "apns-expiration": str(expiration),
                    "apns-id": apns_id,
                },
                "payload": dict(payload),
            }
        )
        reason = self.reasons.get(token)
        if reason is None:
            return ApnsResult("sent", None, 200)
        status = {"Unregistered": 410, "ServiceUnavailable": 503, "TooManyRequests": 429}.get(reason, 400)
        return ApnsResult(classify(status, reason), reason, status)

    async def close(self) -> None:
        return None


_provider: AppleVoipPushProvider | None = None


def get_voip_provider() -> AppleVoipPushProvider:
    global _provider
    if _provider is None:
        _provider = FakeApnsProvider() if settings.apns_provider == "fake" else ApnsHttpProvider()
    return _provider


def set_voip_provider(provider: AppleVoipPushProvider | None) -> None:
    """Swap the provider. Tests only."""
    global _provider
    _provider = provider


def new_apns_id() -> str:
    return str(uuid.uuid4())
