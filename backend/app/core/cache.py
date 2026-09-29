"""Redis cache with an in-process fallback.

Charts, moon phases and transits are expensive to compute and change slowly,
so they are cached. The API must still work when Redis is unavailable, hence
the fallback: it keeps the service up (degraded, per-process) instead of
failing requests.
"""

from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Cache:
    """Minimal async cache interface used across services."""

    async def get(self, key: str) -> Any | None:  # pragma: no cover - interface
        raise NotImplementedError

    async def set(self, key: str, value: Any, ttl: int) -> None:  # pragma: no cover
        raise NotImplementedError

    async def delete(self, key: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def incr_with_ttl(self, key: str, ttl: int) -> int:  # pragma: no cover
        raise NotImplementedError

    async def ttl(self, key: str) -> int:  # pragma: no cover - interface
        """Seconds until the key expires; 0 when it has none or is gone."""
        raise NotImplementedError

    async def ping(self) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    async def close(self) -> None:  # pragma: no cover - interface
        return None


class InMemoryCache(Cache):
    """Process-local fallback. Not shared between workers."""

    def __init__(self) -> None:
        self._values: dict[str, tuple[float, Any]] = {}

    def _expired(self, key: str) -> bool:
        entry = self._values.get(key)
        if entry is None:
            return True
        if entry[0] < time.monotonic():
            self._values.pop(key, None)
            return True
        return False

    async def get(self, key: str) -> Any | None:
        if self._expired(key):
            return None
        return self._values[key][1]

    async def set(self, key: str, value: Any, ttl: int) -> None:
        self._values[key] = (time.monotonic() + ttl, value)

    async def delete(self, key: str) -> None:
        self._values.pop(key, None)

    async def incr_with_ttl(self, key: str, ttl: int) -> int:
        current = 0 if self._expired(key) else int(self._values[key][1])
        expires_at = (
            time.monotonic() + ttl if self._expired(key) else self._values[key][0]
        )
        current += 1
        self._values[key] = (expires_at, current)
        return current

    async def ttl(self, key: str) -> int:
        if self._expired(key):
            return 0
        return max(0, int(self._values[key][0] - time.monotonic()))

    async def ping(self) -> bool:
        return True


class RedisCache(Cache):
    def __init__(self, url: str) -> None:
        self._client: redis.Redis = redis.from_url(
            url, encoding="utf-8", decode_responses=True
        )

    async def get(self, key: str) -> Any | None:
        raw = await self._client.get(key)
        return None if raw is None else json.loads(raw)

    async def set(self, key: str, value: Any, ttl: int) -> None:
        await self._client.set(key, json.dumps(value, default=str), ex=ttl)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def incr_with_ttl(self, key: str, ttl: int) -> int:
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, ttl, nx=True)
            result = await pipe.execute()
        return int(result[0])

    async def ttl(self, key: str) -> int:
        # Redis answers -2 for a missing key and -1 for one without an expiry;
        # neither is a wait a client should be told to observe.
        remaining = int(await self._client.ttl(key))
        return remaining if remaining > 0 else 0

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:  # noqa: BLE001 - health probe must not raise
            return False

    async def close(self) -> None:
        await self._client.aclose()


_cache: Cache | None = None


async def init_cache() -> Cache:
    """Called from the app lifespan."""
    global _cache
    if settings.redis_url:
        candidate = RedisCache(settings.redis_url)
        if await candidate.ping():
            _cache = candidate
            logger.info("cache_ready", backend="redis")
            return _cache
        await candidate.close()
        logger.warning("cache_fallback", backend="memory", reason="redis_unreachable")
    else:
        logger.info("cache_ready", backend="memory")
    _cache = InMemoryCache()
    return _cache


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = InMemoryCache()
    return _cache


async def close_cache() -> None:
    global _cache
    if _cache is not None:
        await _cache.close()
        _cache = None
