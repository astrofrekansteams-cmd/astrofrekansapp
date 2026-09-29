"""Application errors and the single error envelope used by the API.

Every failure leaves the API as::

    {"error": {"code": "...", "message": "...", "details": {...}}}
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for every expected error."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    message: str = "Request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        self.status_code = status_code or self.status_code
        # Some errors carry protocol information a client should act on -
        # Retry-After being the obvious one. It belongs in a header, not only
        # in a body the client may not parse.
        self.headers = headers or {}
        super().__init__(self.message)

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_error"
    message = "The submitted data is not valid."


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"
    message = "Authentication is required."


class InvalidCredentials(AuthenticationError):
    code = "invalid_credentials"
    message = "Email or password is incorrect."


class CurrentPasswordIncorrect(AppError):
    """A signed-in person re-confirmed with the wrong password.

    Deliberately not 401: the session is fine, only the confirmation failed.
    A 401 tells a client its token is bad, and a client that refreshes and
    then signs out on a second 401 would log somebody out for a typo.
    """

    status_code = status.HTTP_403_FORBIDDEN
    code = "current_password_incorrect"
    message = "The current password is incorrect."


class TokenError(AuthenticationError):
    code = "invalid_token"
    message = "The token is invalid or has expired."


class PermissionDenied(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "You do not have access to this resource."


class NotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Resource not found."


class Conflict(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "Resource already exists."


class EmailAlreadyRegistered(Conflict):
    code = "email_in_use"
    message = "This email is already registered."


class RateLimited(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Too many requests. Please slow down."


class AstrologyError(AppError):
    status_code = 422
    code = "astrology_error"
    message = "The chart could not be calculated."


class MissingBirthData(AstrologyError):
    code = "missing_birth_data"
    message = "Birth date, time and place are required for this calculation."


class UpstreamError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "upstream_error"
    message = "An upstream service failed."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_payload(),
            headers=exc.headers or None,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = {
            "fields": [
                {
                    "loc": [str(part) for part in error.get("loc", [])],
                    "type": error.get("type"),
                    "message": error.get("msg"),
                }
                for error in exc.errors()
            ]
        }
        error = ValidationFailed(details=details)
        return JSONResponse(status_code=error.status_code, content=error.to_payload())

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = {
            401: "unauthenticated",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            429: "rate_limited",
        }.get(exc.status_code, "http_error")
        payload = {
            "error": {
                "code": code,
                "message": str(exc.detail),
                "details": {},
            }
        }
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        # The message is deliberately generic: internals never leak to clients.
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error_type=type(exc).__name__,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Something went wrong.",
                    "details": {},
                }
            },
        )
