"""FastAPI dependencies: database session, storage, identity, rate limits."""

import logging
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import User
from app.errors import RateLimited, Unauthorized
from app.logging_setup import set_user_id
from app.media.pipeline import MediaLimits
from app.ratelimit import RateLimiter
from app.services import user_service
from app.storage.base import MediaStorage

log = logging.getLogger("mirage.auth")


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()  # rolls back anything a service didn't commit


def get_storage(request: Request) -> MediaStorage:
    return request.app.state.storage


def get_media_limits(settings: Annotated[Settings, Depends(get_settings)]) -> MediaLimits:
    return MediaLimits(settings.max_image_bytes, settings.max_video_bytes, settings.max_image_pixels)


DB = Annotated[Session, Depends(get_db)]
Storage = Annotated[MediaStorage, Depends(get_storage)]
Limits = Annotated[MediaLimits, Depends(get_media_limits)]


# ---------------------------------------------------------------------------
# Identity seam (FR-3). The ONLY place that decides who the caller is.
#
# DEV ONLY: trusts the X-User-Id header sent by the frontend's account switcher.
# Real authentication replaces the body of _identify() (verify a session cookie
# or bearer token, look up the user) and nothing else in the codebase changes.
# Settings refuses AUTH_MODE=dev_header in production.
# ---------------------------------------------------------------------------
def _identify(db: Session, x_user_id: str | None) -> User | None:
    if x_user_id is None:
        return None
    if not (x_user_id.isascii() and x_user_id.isdigit() and len(x_user_id) <= 12):
        raise Unauthorized("Unknown account.")
    user = user_service.resolve(db, int(x_user_id))
    if user is None:
        log.warning("auth.unknown_user")
        raise Unauthorized("Unknown account.")
    set_user_id(user.id)
    return user


def get_current_user(db: DB, x_user_id: Annotated[str | None, Header()] = None) -> User:
    user = _identify(db, x_user_id)
    if user is None:
        raise Unauthorized()
    return user


def get_optional_user(db: DB, x_user_id: Annotated[str | None, Header()] = None) -> User | None:
    """For read endpoints: anonymous is fine, but a supplied identity must be valid."""
    return _identify(db, x_user_id)


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


# ---------------------------------------------------------------------------
# Per-user rate limits (SR-12). Keyed on the resolved user, after identity.
# ---------------------------------------------------------------------------
def _limits(settings: Settings) -> dict[str, tuple[int, float, str]]:
    return {
        "post": (settings.rate_limit_posts_per_hour, 3600.0, "You've posted a lot recently. Try again later."),
        "vote": (settings.rate_limit_votes_per_minute, 60.0, "You're voting too fast. Slow down a little."),
        "react": (settings.rate_limit_reactions_per_minute, 60.0, "You're reacting too fast. Slow down a little."),
    }


def rate_limit(action: str):
    def dependency(request: Request, user: CurrentUser) -> None:
        settings: Settings = request.app.state.settings
        limiter: RateLimiter = request.app.state.rate_limiter
        limit, window, message = _limits(settings)[action]
        retry_after = limiter.hit(f"{user.id}:{action}", limit, window)
        if retry_after is not None:
            log.warning("rate_limited", extra={"action": action})
            raise RateLimited(retry_after, message)

    return Depends(dependency)
