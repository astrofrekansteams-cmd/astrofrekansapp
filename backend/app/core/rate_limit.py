"""Fixed-window rate limiting backed by the cache (Redis in production).

Used as a FastAPI dependency::

    @router.post("/login", dependencies=[Depends(RateLimit("10/minute"))])
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import Request

from app.core.cache import get_cache
from app.core.config import settings
from app.core.exceptions import RateLimited

_WINDOWS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
_PATTERN = re.compile(r"^(\d+)\s*/\s*(second|minute|hour|day)$")


@dataclass(slots=True, frozen=True)
class Quota:
    limit: int
    window_seconds: int

    @classmethod
    def parse(cls, value: str) -> "Quota":
        match = _PATTERN.match(value.strip())
        if not match:
            raise ValueError(f"Invalid rate limit expression: {value!r}")
        return cls(limit=int(match.group(1)), window_seconds=_WINDOWS[match.group(2)])


def client_key(request: Request) -> str:
    """Identify the caller: authenticated user first, then proxy-aware IP."""
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


class RateLimit:
    def __init__(
        self,
        expression: str,
        *,
        scope: str | None = None,
        code: str | None = None,
    ) -> None:
        self.quota = Quota.parse(expression)
        self.scope = scope
        # AI routes report `ai_rate_limited`, the same code the provider's own
        # throttling produces. The client's response is identical either way -
        # back off and retry - and the `scope` in the details says which limit
        # was hit when someone needs to know.
        self.code = code

    def identify(self, request: Request) -> str:
        return client_key(request)

    async def __call__(self, request: Request) -> None:
        await self.enforce(request, self.quota)

    async def enforce(self, request: Request, quota: "Quota") -> None:
        if not settings.rate_limit_enabled:
            return
        scope = self.scope or request.scope.get("route").path  # type: ignore[union-attr]
        key = f"ratelimit:{scope}:{self.identify(request)}"
        cache = get_cache()
        count = await cache.incr_with_ttl(key, quota.window_seconds)
        if count > quota.limit:
            retry_after = await cache.ttl(key) or quota.window_seconds
            raise RateLimited(
                code=self.code,
                details={
                    "limit": quota.limit,
                    "window_seconds": quota.window_seconds,
                    "scope": scope,
                },
                headers={"Retry-After": str(retry_after)},
            )
