"""Geocoding contract.

A birth place string is not enough for a chart: the engine needs coordinates
and a timezone. Providers are swappable; the default in local/test
environments is the deterministic mock so the suite never hits the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(slots=True, frozen=True)
class GeocodedPlace:
    query: str
    display_name: str
    latitude: float
    longitude: float
    timezone: str
    country_code: str | None = None
    provider: str = "mock"
    confidence: float = 1.0


@runtime_checkable
class GeocodingProvider(Protocol):
    name: str

    async def search(self, query: str, *, limit: int = 5) -> list[GeocodedPlace]:
        """Best matches for a free-text place, most relevant first."""

    async def resolve(self, query: str) -> GeocodedPlace | None:
        """The single best match, or ``None``."""
