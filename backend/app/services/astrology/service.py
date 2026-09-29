"""Chart service: engine + caching + persistence.

A natal chart is a pure function of (birth data, house system, engine version),
so it is cached twice:

1. Redis, for the hot path (TTL from settings),
2. the ``natal_charts`` table, so a cold cache does not re-run the ephemeris
   for every user after a deploy.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, replace
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_cache
from app.core.config import settings
from app.core.exceptions import MissingBirthData
from app.core.logging import get_logger
from app.db.models.chart import ChartCache
from app.domain.astrology import BirthData, Chart, ChartSubject, MoonPhase
from app.domain.enums import ChartKind, HouseSystem
from app.services.astrology.serializers import chart_from_payload, chart_to_payload
from app.services.astrology.skyfield_engine import SkyfieldEngine, get_engine

logger = get_logger(__name__)


def chart_fingerprint(subject: ChartSubject, engine_version: str) -> str:
    """Cache key: everything the chart actually depends on, nothing else.

    Two users born at the same instant in the same place share a cache entry -
    that is correct, and the payload holds no personal data beyond the chart
    itself.
    """
    payload = {
        "kind": subject.kind.value,
        "moment": subject.moment_utc.isoformat(),
        "lat": round(subject.latitude, 6) if subject.latitude is not None else None,
        "lon": round(subject.longitude, 6) if subject.longitude is not None else None,
        "house_system": subject.house_system.value,
        "engine": engine_version,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ChartService:
    def __init__(self, engine: SkyfieldEngine | None = None) -> None:
        self._engine = engine or get_engine()

    @property
    def engine(self) -> SkyfieldEngine:
        return self._engine

    async def natal_chart(
        self,
        birth: BirthData,
        *,
        session: AsyncSession | None = None,
        user_id: uuid.UUID | None = None,
        subject_type: str = "user",
        subject_id: uuid.UUID | None = None,
        house_system: HouseSystem | None = None,
        use_cache: bool = True,
    ) -> Chart:
        if birth.birth_date is None:  # pragma: no cover - guarded by schemas
            raise MissingBirthData()

        system = house_system or birth.house_system
        subject = birth.to_subject()
        if not birth.can_compute_houses:
            subject = replace(subject, latitude=None, longitude=None)
        subject = replace(subject, house_system=system)
        fingerprint = chart_fingerprint(subject, self._engine.version)
        cache_key = f"chart:{fingerprint}"

        if use_cache:
            cached = await get_cache().get(cache_key)
            if cached is not None:
                return chart_from_payload(cached)

            if session is not None:
                row = await session.scalar(
                    select(ChartCache).where(
                        ChartCache.input_hash == fingerprint
                    )
                )
                if row is not None:
                    await get_cache().set(
                        cache_key, row.payload, settings.natal_chart_cache_ttl_seconds
                    )
                    return chart_from_payload(row.payload)

        chart = self._engine.natal_chart(birth, house_system=system)
        payload = chart_to_payload(chart)

        if use_cache:
            await get_cache().set(
                cache_key, payload, settings.natal_chart_cache_ttl_seconds
            )
            if session is not None:
                session.add(
                    ChartCache(
                        user_id=user_id,
                        chart_kind=ChartKind.NATAL,
                        subject_type=subject_type,
                        subject_id=subject_id,
                        moment_utc=subject.moment_utc,
                        input_hash=fingerprint,
                        engine_version=self._engine.version,
                        house_system=chart.house_system.value,
                        payload=payload,
                    )
                )
                await session.flush()

        return chart

    async def moon_phase(self, moment: datetime | None = None) -> MoonPhase:
        when = moment or datetime.now(UTC)
        # Phase changes slowly; cache on the hour.
        cache_key = f"moon_phase:{when.astimezone(UTC).strftime('%Y%m%d%H')}"
        cached = await get_cache().get(cache_key)
        if cached is not None:
            return MoonPhase(
                moment=datetime.fromisoformat(cached["moment"]),
                phase=cached["phase"],
                illumination=cached["illumination"],
                age_days=cached["age_days"],
                elongation=cached["elongation"],
                sign=cached["sign"],
                next_phase=cached["next_phase"],
                next_phase_at=(
                    datetime.fromisoformat(cached["next_phase_at"])
                    if cached["next_phase_at"]
                    else None
                ),
            )

        phase = self._engine.moon_phase(when)
        await get_cache().set(cache_key, asdict(phase), 3600)
        return phase


_service: ChartService | None = None


def get_chart_service() -> ChartService:
    global _service
    if _service is None:
        _service = ChartService()
    return _service
