"""Structured logging.

Logs carry request_id / method / path / status / latency. They never carry
passwords, tokens, birth details or AI conversation content - see
``REDACTED_KEYS``.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)

REDACTED_KEYS = frozenset(
    {
        "password",
        "new_password",
        "current_password",
        "password_confirmation",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "jwt",
        "api_key",
        "secret",
        # B10: a LiveKit join token or signing secret under any of its names.
        "api_secret",
        "livekit_api_secret",
        "join_token",
        "participant_token",
        "birth_date",
        "birth_time",
        "birth_place",
        "latitude",
        "longitude",
        "message",
        "content",
        "prompt",
        "email",
    }
)


def _redact(_logger: Any, _name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in list(event_dict):
        if key.lower() in REDACTED_KEYS:
            event_dict[key] = "[redacted]"
    return event_dict


def _add_context(_logger: Any, _name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    request_id = request_id_var.get()
    if request_id:
        event_dict.setdefault("request_id", request_id)
    user_id = user_id_var.get()
    if user_id:
        # Opaque id only: never the email or the name.
        event_dict.setdefault("user_id", user_id)
    return event_dict


def configure_logging(*, json_logs: bool = True, level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_context,
            _redact,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            (
                structlog.processors.JSONRenderer()
                if json_logs
                else structlog.dev.ConsoleRenderer(colors=False)
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
