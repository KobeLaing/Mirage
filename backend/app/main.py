"""Application factory. Run with `python run.py` (uvicorn factory mode)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.api import v1
from app.config import Settings, get_settings
from app.db.session import build_engine, build_session_factory
from app.errors import register_error_handlers
from app.logging_setup import configure_logging
from app.middleware import BodySizeLimitMiddleware, RequestContextMiddleware, SecurityHeadersMiddleware
from app.ratelimit import InMemoryRateLimiter
from app.storage.local import LocalDiskStorage

JSON_BODY_LIMIT = 64 * 1024
MULTIPART_OVERHEAD = 1024 * 1024


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Mirage API",
        version="1.0.0",
        debug=False,  # never send tracebacks to clients (SR-16)
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    # Wiring only; no per-user or per-session state is kept on the server (NFR-2).
    engine = build_engine(settings.database_url)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    app.state.storage = LocalDiskStorage(settings.upload_dir, settings.public_api_url)
    app.state.rate_limiter = InMemoryRateLimiter()

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(v1.router)

    # Middleware: the last one added is the outermost.
    app.add_middleware(
        BodySizeLimitMiddleware,
        default_limit=JSON_BODY_LIMIT,
        upload_limit=settings.max_video_bytes + MULTIPART_OVERHEAD,
        upload_paths=("/api/v1/posts",),
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],  # SR-13: the frontend only
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-User-Id", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
        allow_credentials=False,
        max_age=600,
    )
    app.add_middleware(SecurityHeadersMiddleware, docs_enabled=settings.docs_enabled)
    return app
