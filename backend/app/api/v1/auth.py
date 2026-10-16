from fastapi import APIRouter, Request, Response, status

from app.api.deps import DB, CurrentUser, PasswordHashing, Tokens, check_login_rate, client_ip, get_settings
from app.schemas.auth import LoginIn, SessionOut
from app.schemas.common import ErrorResponse
from app.security.tokens import SESSION_COOKIE
from app.services import auth_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])

ERRORS = {code: {"model": ErrorResponse} for code in (401, 403, 422, 429)}


def _set_session_cookie(response: Response, request: Request, value: str, max_age: int) -> None:
    settings = get_settings(request)
    # httponly: page JavaScript can't read it, so an XSS bug can't steal it.
    # secure: only sent over HTTPS (browsers treat localhost as secure).
    # samesite=lax: not sent on cross-site POSTs, a first line of CSRF defence.
    response.set_cookie(
        SESSION_COOKIE, value, max_age=max_age, path="/",
        httponly=True, secure=settings.cookie_secure, samesite="lax",
    )


@router.post("/login", response_model=SessionOut, responses=ERRORS)
def login(body: LoginIn, request: Request, response: Response, db: DB, passwords: PasswordHashing, tokens: Tokens) -> SessionOut:
    # Rate limiting comes first, so bots and password guessers are throttled
    # before we spend any time hashing.
    check_login_rate(request, body.username)
    result = auth_service.login(
        db, passwords, tokens,
        username=body.username, password=body.password, honeypot=body.website, client_ip=client_ip(request),
    )
    _set_session_cookie(response, request, result.cookie_value, tokens.ttl_seconds)
    return user_service.session_view(db, result.user, tokens.csrf_for(result.cookie_value))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
def logout(request: Request, db: DB, tokens: Tokens) -> Response:
    auth_service.logout(db, tokens, request.cookies.get(SESSION_COOKIE))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    settings = get_settings(request)
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax")
    return response


@router.get("/session", response_model=SessionOut, responses=ERRORS)
def current_session(request: Request, db: DB, user: CurrentUser, tokens: Tokens) -> SessionOut:
    """Lets the frontend ask "am I signed in?" after a page reload, and get a fresh CSRF token."""
    cookie = request.cookies.get(SESSION_COOKIE, "")
    return user_service.session_view(db, user, tokens.csrf_for(cookie))
