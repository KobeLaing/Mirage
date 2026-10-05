"""Pure-ASGI middleware: request ID + access log, security headers, body size limit."""

import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errors import error_body
from app.logging_setup import begin_request, end_request

access_log = logging.getLogger("mirage.access")

_UUID_RE = re.compile(r"^[0-9a-fA-F-]{32,36}$")

API_SECURITY_HEADERS = {
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cross-origin-resource-policy": "same-site",
}

# Swagger UI (development only) needs its CDN assets.
DOCS_CSP = (
    "default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; "
    "connect-src 'self'; frame-ancestors 'none'"
)


class RequestContextMiddleware:
    """Assigns a request ID, echoes it in X-Request-ID, and writes one JSON access line."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = Headers(scope=scope).get("x-request-id", "")
        request_id = incoming if _UUID_RE.match(incoming) else uuid.uuid4().hex
        token = begin_request(request_id)
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                MutableHeaders(scope=message)["x-request-id"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # Handled here rather than by Starlette's outermost error middleware so the
            # 500 still carries the request ID, CORS, and security headers (SR-16).
            access_log.exception("request.unhandled_exception")
            if response_started:
                raise
            response = JSONResponse(
                error_body("internal_error", "Something went wrong on our side."), status_code=500
            )
            await response(scope, receive, send_wrapper)
        finally:
            access_log.info(
                "http.request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            end_request(token)


class SecurityHeadersMiddleware:
    """Adds security headers to every response unless the route already set them (SR-14)."""

    def __init__(self, app: ASGIApp, docs_enabled: bool):
        self.app = app
        self.docs_enabled = docs_enabled

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_docs = self.docs_enabled and scope["path"] in ("/docs", "/redoc")

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in API_SECURITY_HEADERS.items():
                    if name not in headers:
                        headers[name] = value
                if is_docs:
                    headers["content-security-policy"] = DOCS_CSP
            await send(message)

        await self.app(scope, receive, send_wrapper)


class BodySizeLimitMiddleware:
    """Rejects request bodies over a limit while they stream in (SR-3, AC-11).

    Uploads get a larger allowance than JSON endpoints. The per-type limits
    (image vs video) are enforced again in the upload pipeline after sniffing.
    """

    def __init__(self, app: ASGIApp, default_limit: int, upload_limit: int, upload_paths: tuple[str, ...]):
        self.app = app
        self.default_limit = default_limit
        self.upload_limit = upload_limit
        self.upload_paths = upload_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.upload_limit if scope["path"] in self.upload_paths else self.default_limit
        declared = Headers(scope=scope).get("content-length")
        if declared and declared.isdigit() and int(declared) > limit:
            await self._reject(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # Raised inside the app's body parsing; FastAPI re-raises HTTPException
                    # as-is and our handler renders the standard error shape.
                    raise HTTPException(status_code=413, detail="That file is too large.")
            return message

        await self.app(scope, limited_receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            error_body("payload_too_large", "That file is too large."), status_code=413,
            headers={"connection": "close"},
        )
        await response(scope, receive, send)
