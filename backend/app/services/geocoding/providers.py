"""Geocoding providers.

``MockGeocodingProvider`` ships a small city table so local development and the
test suite are deterministic and offline. ``NominatimProvider`` is a thin
OpenStreetMap client for staging/production; it is rate limited upstream, so
results are cached and a contact User-Agent is mandatory by their policy.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.cache import get_cache
from app.core.config import settings
from app.core.exceptions import UpstreamError
from app.core.logging import get_logger
from app.services.geocoding.base import GeocodedPlace
from app.services.timezone.service import timezone_for_coordinates

logger = get_logger(__name__)

_CACHE_TTL = 60 * 60 * 24 * 30

# Enough coverage for development and for the seeded demo accounts.
_CITIES: dict[str, tuple[str, float, float, str, str]] = {
    "istanbul": ("İstanbul, Türkiye", 41.0082, 28.9784, "Europe/Istanbul", "TR"),
    "ankara": ("Ankara, Türkiye", 39.9334, 32.8597, "Europe/Istanbul", "TR"),
    "izmir": ("İzmir, Türkiye", 38.4237, 27.1428, "Europe/Istanbul", "TR"),
    "bursa": ("Bursa, Türkiye", 40.1826, 29.0665, "Europe/Istanbul", "TR"),
    "antalya": ("Antalya, Türkiye", 36.8969, 30.7133, "Europe/Istanbul", "TR"),
    "adana": ("Adana, Türkiye", 37.0000, 35.3213, "Europe/Istanbul", "TR"),
    "trabzon": ("Trabzon, Türkiye", 41.0015, 39.7178, "Europe/Istanbul", "TR"),
    "baku": ("Bakı, Azərbaycan", 40.4093, 49.8671, "Asia/Baku", "AZ"),
    "london": ("London, United Kingdom", 51.5074, -0.1278, "Europe/London", "GB"),
    "berlin": ("Berlin, Deutschland", 52.5200, 13.4050, "Europe/Berlin", "DE"),
    "paris": ("Paris, France", 48.8566, 2.3522, "Europe/Paris", "FR"),
    "new york": ("New York, USA", 40.7128, -74.0060, "America/New_York", "US"),
    "los angeles": ("Los Angeles, USA", 34.0522, -118.2437, "America/Los_Angeles", "US"),
    "tokyo": ("Tokyo, Japan", 35.6762, 139.6503, "Asia/Tokyo", "JP"),
    "sydney": ("Sydney, Australia", -33.8688, 151.2093, "Australia/Sydney", "AU"),
    "dubai": ("Dubai, UAE", 25.2048, 55.2708, "Asia/Dubai", "AE"),
}


class MockGeocodingProvider:
    """Offline provider backed by a fixed city table."""

    name = "mock"

    async def search(self, query: str, *, limit: int = 5) -> list[GeocodedPlace]:
        needle = query.strip().lower()
        if not needle:
            return []
        matches = [
            self._build(query, key, value)
            for key, value in _CITIES.items()
            if needle.startswith(key) or key in needle or needle in key
        ]
        return matches[:limit]

    async def resolve(self, query: str) -> GeocodedPlace | None:
        matches = await self.search(query, limit=1)
        return matches[0] if matches else None

    def _build(
        self, query: str, key: str, value: tuple[str, float, float, str, str]
    ) -> GeocodedPlace:
        display, latitude, longitude, timezone, country = value
        return GeocodedPlace(
            query=query,
            display_name=display,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            country_code=country,
            provider=self.name,
            confidence=1.0 if query.strip().lower() == key else 0.6,
        )


class NominatimProvider:
    """OpenStreetMap Nominatim. Results are cached for a month."""

    name = "nominatim"

    def __init__(self, base_url: str | None = None, user_agent: str | None = None) -> None:
        self._base_url = (base_url or settings.nominatim_base_url).rstrip("/")
        self._user_agent = user_agent or settings.nominatim_user_agent

    async def search(self, query: str, *, limit: int = 5) -> list[GeocodedPlace]:
        needle = query.strip()
        if not needle:
            return []

        cache_key = f"geocode:{self.name}:{needle.lower()}:{limit}"
        cached = await get_cache().get(cache_key)
        if cached is not None:
            return [GeocodedPlace(**item) for item in cached]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self._base_url}/search",
                    params={"q": needle, "format": "jsonv2", "limit": limit},
                    headers={"User-Agent": self._user_agent},
                )
                response.raise_for_status()
                payload: list[dict[str, Any]] = response.json()
        except httpx.HTTPError as exc:
            logger.warning("geocoding_failed", provider=self.name, error=str(exc))
            raise UpstreamError("Geocoding provider is unavailable.") from exc

        places: list[GeocodedPlace] = []
        for item in payload:
            latitude = float(item["lat"])
            longitude = float(item["lon"])
            timezone = timezone_for_coordinates(latitude, longitude)
            if timezone is None:
                continue
            places.append(
                GeocodedPlace(
                    query=needle,
                    display_name=item.get("display_name", needle),
                    latitude=latitude,
                    longitude=longitude,
                    timezone=timezone,
                    country_code=(item.get("address", {}) or {}).get("country_code"),
                    provider=self.name,
                    confidence=float(item.get("importance", 0.5)),
                )
            )

        await get_cache().set(
            cache_key, [place.__dict__ for place in places], _CACHE_TTL
        )
        return places

    async def resolve(self, query: str) -> GeocodedPlace | None:
        matches = await self.search(query, limit=1)
        return matches[0] if matches else None


def get_geocoding_provider():  # noqa: ANN201 - returns GeocodingProvider
    if settings.geocoding_provider == "nominatim":
        return NominatimProvider()
    return MockGeocodingProvider()
