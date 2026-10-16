"""One JSON error shape for every failure (NFR-7), and no internals in responses (SR-16).

    {"error": {"code": "...", "message": "...", "request_id": "...", "details": ...}}

Services raise AppError subclasses. Handlers below turn them, framework errors,
and unexpected exceptions into that shape.
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_setup import current_request_id

log = logging.getLogger("mirage.errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"
    message = "The request could not be processed."

    def __init__(self, message: str | None = None, *, details: Any = None, headers: dict | None = None):
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details
        self.headers = headers


class BadRequest(AppError):
    status_code, code = 400, "bad_request"


class Unauthorized(AppError):
    status_code, code, message = 401, "unauthorized", "Please sign in to continue."


class InvalidCredentials(AppError):
    # One message for every login failure (unknown user, wrong password, honeypot
    # tripped), so a failed attempt never tells the caller which part was wrong.
    status_code, code, message = 401, "invalid_credentials", "Invalid username or password"


class Forbidden(AppError):
    status_code, code, message = 403, "forbidden", "You can't change something that isn't yours."


class CsrfRejected(AppError):
    status_code, code, message = 403, "csrf_failed", "This request was blocked. Refresh the page and try again."


class NotFound(AppError):
    status_code, code, message = 404, "not_found", "Not found."


class PayloadTooLarge(AppError):
    status_code, code, message = 413, "payload_too_large", "That file is too large."


class UnsupportedMediaType(AppError):
    status_code, code = 415, "unsupported_media_type"
    message = "Only JPEG, PNG and GIF images and MP4 videos are allowed."


class RateLimited(AppError):
    status_code, code, message = 429, "rate_limited", "You're doing that too often. Try again shortly."

    def __init__(self, retry_after: float, message: str | None = None):
        seconds = max(1, int(retry_after + 0.999))
        super().__init__(message, headers={"Retry-After": str(seconds)}, details={"retry_after": seconds})


def error_body(code: str, message: str, details: Any = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": current_request_id(),
            "details": details,
        }
    }


def _status_code_name(status: int) -> str:
    try:
        return HTTPStatus(status).phrase.lower().replace(" ", "_").replace("-", "_")
    except ValueError:
        return "error"


async def _app_error(request: Request, exc: AppError) -> JSONResponse:
    log.info("request.rejected", extra={"code": exc.code, "status": exc.status_code})
    return JSONResponse(
        error_body(exc.code, exc.message, exc.details), status_code=exc.status_code, headers=exc.headers
    )


async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Framework errors (404 unknown route, 405, 413 from the body limiter). Use a
    # generic message for 5xx; client errors keep the framework's short reason.
    message = exc.detail if isinstance(exc.detail, str) and exc.status_code < 500 else "Request failed."
    return JSONResponse(
        error_body(_status_code_name(exc.status_code), message),
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )


async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Field locations and messages only; never echo the submitted input back.
    details = [
        {"field": ".".join(str(p) for p in err.get("loc", ()) if p != "body"), "message": err.get("msg", "")}
        for err in exc.errors()
    ]
    return JSONResponse(
        error_body("validation_error", "Some fields are invalid.", details), status_code=422
    )


async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.exception("request.unhandled_exception")
    return JSONResponse(
        error_body("internal_error", "Something went wrong on our side."), status_code=500
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled)
