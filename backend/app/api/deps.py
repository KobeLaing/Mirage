"""FastAPI dependencies: database session, storage, identity, CSRF, rate limits."""

import logging
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import User
from app.errors import CsrfRejected, RateLimited, Unauthorized
from app.logging_setup import set_user_id
from app.media.pipeline import MediaLimits
from app.ratelimit import RateLimiter
from app.security.passwords import Passwords
from app.security.tokens import SESSION_COOKIE, SessionTokens
from app.services import auth_service
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


def get_tokens(request: Request) -> SessionTokens:
    return request.app.state.tokens


def get_passwords(request: Request) -> Passwords:
    return request.app.state.passwords


DB = Annotated[Session, Depends(get_db)]
Storage = Annotated[MediaStorage, Depends(get_storage)]
Limits = Annotated[MediaLimits, Depends(get_media_limits)]
Tokens = Annotated[SessionTokens, Depends(get_tokens)]
PasswordHashing = Annotated[Passwords, Depends(get_passwords)]


def client_ip(request: Request) -> str | None:
    # The direct peer address. If the API is ever put behind a reverse proxy,
    # this must read the proxy's forwarded header instead (and only trust it
    # from that proxy), or every user would share the proxy's IP.
    return request.client.host if request.client else None


# ---------------------------------------------------------------------------
# Identity. The ONLY place that decides who the caller is.
#
# The browser sends the httpOnly session cookie automatically; JavaScript can't
# read it, so an XSS bug can't steal it. auth_service checks the signature,
# expiry and revocation, then loads the user. No route accepts a user id from
# the client, so the current user can only ever come from a real session.
# ---------------------------------------------------------------------------
def get_current_user(request: Request, db: DB, tokens: Tokens) -> User:
    user = auth_service.resolve(db, tokens, request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise Unauthorized()
    set_user_id(user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# CSRF protection for every state-changing request (applied to the whole API
# router in app/api/v1/__init__.py). Two independent checks:
#
# 1. Origin must be our frontend. Browsers set this header themselves and page
#    script can't fake it, so a form or fetch from another site fails here.
# 2. X-CSRF-Token must match the session cookie (see app/security/tokens.py).
#    Login is exempt from this one because there's no session yet; the Origin
#    check and SameSite=Lax still protect it.
# ---------------------------------------------------------------------------
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CSRF_EXEMPT_PATHS = frozenset({"/api/v1/auth/login"})


def csrf_protect(request: Request) -> None:
    if request.method not in UNSAFE_METHODS:
        return
    settings: Settings = request.app.state.settings
    if request.headers.get("origin") != settings.frontend_origin:
        log.warning("csrf.bad_origin", extra={"path": request.url.path})
        raise CsrfRejected()
    if request.url.path in CSRF_EXEMPT_PATHS:
        return
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie is None:
        return  # not signed in; the route's identity dependency answers 401
    tokens: SessionTokens = request.app.state.tokens
    if not tokens.csrf_matches(cookie, request.headers.get("x-csrf-token", "")):
        log.warning("csrf.bad_token", extra={"path": request.url.path})
        raise CsrfRejected()


# ---------------------------------------------------------------------------
# Rate limits. Most are per signed-in user and run after identity. Login is
# special: there's no user yet, so it's limited per IP *and* per username.
# The IP limit slows one machine guessing many accounts; the username limit
# slows many machines (a botnet) guessing one account.
# ---------------------------------------------------------------------------
LOGIN_WINDOW_SECONDS = 15 * 60


def _limits(settings: Settings) -> dict[str, tuple[int, float, str]]:
    return {
        "post": (settings.rate_limit_posts_per_hour, 3600.0, "You've posted a lot recently. Try again later."),
        "vote": (settings.rate_limit_votes_per_minute, 60.0, "You're voting too fast. Slow down a little."),
        "react": (settings.rate_limit_reactions_per_minute, 60.0, "You're reacting too fast. Slow down a little."),
        "comment": (settings.rate_limit_comments_per_minute, 60.0, "You're commenting too fast. Slow down a little."),
        "scan": (settings.rate_limit_scans_per_hour, 3600.0, "You've run a lot of scans recently. Try again later."),
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


def check_login_rate(request: Request, username: str) -> None:
    settings: Settings = request.app.state.settings
    limiter: RateLimiter = request.app.state.rate_limiter
    message = "Too many sign-in attempts. Wait a few minutes and try again."
    checks = (
        (f"login-ip:{client_ip(request)}", settings.rate_limit_login_per_ip),
        (f"login-user:{username.lower()}", settings.rate_limit_login_per_username),
    )
    for key, limit in checks:
        retry_after = limiter.hit(key, limit, LOGIN_WINDOW_SECONDS)
        if retry_after is not None:
            log.warning("auth.login_rate_limited", extra={"ip": client_ip(request), "username": username[:32]})
            raise RateLimited(retry_after, message)
