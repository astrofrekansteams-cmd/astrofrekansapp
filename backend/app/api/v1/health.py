"""Liveness and readiness probes.

``/health`` answers as long as the process is up. ``/ready`` additionally
checks the dependencies a request actually needs: database, cache and the
ephemeris kernel. Kubernetes/Cloud Run should point its readiness probe at the
latter and its liveness probe at the former.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.cache import get_cache
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_session_factory

logger = get_logger(__name__)

router = APIRouter(tags=["system"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }


@router.get("/ready", summary="Readiness probe")
async def ready(response: Response) -> dict[str, Any]:
    checks: dict[str, str] = {}

    try:
        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - probe must not raise
        logger.warning("readiness_database_failed", error_type=type(exc).__name__)
        checks["database"] = "unavailable"

    checks["cache"] = "ok" if await get_cache().ping() else "degraded"

    try:
        from app.services.astrology.skyfield_engine import get_engine

        get_engine()
        checks["ephemeris"] = "ok"
    except Exception as exc:  # noqa: BLE001 - probe must not raise
        logger.warning("readiness_ephemeris_failed", error_type=type(exc).__name__)
        checks["ephemeris"] = "unavailable"

    ready_now = checks["database"] == "ok" and checks["ephemeris"] == "ok"
    if not ready_now:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready_now else "not_ready", "checks": checks}
