"""FastAPI application factory.

Boot order matters: settings are validated for the target environment first
(so an unsafe production config fails fast), then logging, then the cache, and
only then are requests accepted.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router, system_router
from app.core.cache import close_cache, init_cache
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger, request_id_var, user_id_var
from app.db.session import dispose_engine

logger = get_logger(__name__)

DESCRIPTION = """
Astrofrekans API - astrology engine, user data and AI context for the mobile
client.

* Charts are computed from JPL ephemerides (Skyfield), never by an LLM.
* All instants are UTC ISO-8601; birth data additionally carries its IANA zone.
* Errors always have the shape `{"error": {"code", "message", "details"}}`.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.assert_production_ready()
    await init_cache()

    # Load the ephemeris once at boot so the first request is not slow and a
    # missing kernel is noticed immediately.
    try:
        from app.services.astrology.skyfield_engine import get_engine

        engine = get_engine()
        logger.info("astrology_engine_ready", engine=engine.name, version=engine.version)
    except Exception as exc:  # noqa: BLE001 - keep the API up, /ready reports it
        logger.error("astrology_engine_unavailable", error_type=type(exc).__name__)

    # Say once what the AI layer will and will not do. Local check only: a
    # boot that calls a third-party API is a boot that fails when that API is
    # having a bad morning.
    try:
        from app.services.ai.diagnostics import log_startup_diagnostic

        log_startup_diagnostic()
    except Exception as exc:  # noqa: BLE001 - diagnostics never block a boot
        logger.error("ai_diagnostic_failed", error_type=type(exc).__name__)

    # Same shape as the AI diagnostic: local only, never a network call at
    # boot, and never fatal.
    try:
        from app.services.firebase.factory import (
            log_startup_diagnostic as log_firebase,
        )

        log_firebase()
    except Exception as exc:  # noqa: BLE001 - diagnostics never block a boot
        logger.error("firebase_diagnostic_failed", error_type=type(exc).__name__)

    try:
        from app.services.calls.factory import (
            log_startup_diagnostic as log_calls,
        )

        log_calls()
    except Exception as exc:  # noqa: BLE001 - diagnostics never block a boot
        logger.error("calls_diagnostic_failed", error_type=type(exc).__name__)

    try:
        from app.services.payments.factory import (
            log_startup_diagnostic as log_payments,
        )

        log_payments()
    except Exception as exc:  # noqa: BLE001 - diagnostics never block a boot
        logger.error("payments_diagnostic_failed", error_type=type(exc).__name__)

    logger.info("api_started", environment=settings.environment)
    try:
        yield
    finally:
        from app.services.ai.factory import close_ai_provider

        await close_ai_provider()
        from app.services.calls.factory import close_call_provider

        await close_call_provider()
        await close_cache()
        await dispose_engine()
        logger.info("api_stopped")


def create_app() -> FastAPI:
    configure_logging(
        json_logs=settings.environment not in ("local", "test"),
        level="DEBUG" if settings.debug else "INFO",
    )

    app = FastAPI(
        title=settings.app_name,
        description=DESCRIPTION,
        version="0.1.0",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # CORS: never allow-all in production. The mobile client does not need CORS
    # at all, so an empty list is the correct production default.
    origins = settings.cors_origin_list
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "Accept-Language"],
            max_age=600,
        )
    elif not settings.is_production:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def request_context_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request_id_var.set(request_id)
        user_id_var.set(None)
        request.state.request_id = request_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise

        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["x-request-id"] = request_id
        # Query strings are omitted on purpose: they can carry place names.
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
        )
        return response

    register_exception_handlers(app)
    app.include_router(system_router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
