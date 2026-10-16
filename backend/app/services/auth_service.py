"""Signing in, signing out, and turning a session cookie back into a user.

Every login failure raises the same InvalidCredentials error ("Invalid username
or password"), whether the username doesn't exist, the password is wrong, or
the honeypot was filled in. The reason is only written to the server log, so
an attacker learns nothing from the response.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import User
from app.errors import InvalidCredentials
from app.repositories import session_repo, user_repo
from app.security.passwords import Passwords
from app.security.tokens import SessionTokens, session_id

log = logging.getLogger("mirage.auth")


@dataclass(frozen=True)
class LoginResult:
    user: User
    cookie_value: str


def _log_failure(reason: str, username: str, client_ip: str | None) -> None:
    # The username is logged (truncated) so an operator can spot an account
    # under attack. The password is never passed to this function at all.
    log.warning("auth.login_failed", extra={"reason": reason, "username": username[:32], "ip": client_ip})


def login(
    db: Session,
    passwords: Passwords,
    tokens: SessionTokens,
    *,
    username: str,
    password: str,
    honeypot: str,
    client_ip: str | None,
) -> LoginResult:
    # HONEYPOT: server-side check of the hidden "website" field. A person never
    # sees that field, so any value means a bot auto-filled the form. We reject
    # it with exactly the same error as a wrong password, so the bot can't tell
    # it was caught, and log it as a suspected bot. This runs before the
    # password check, so a bot never gets to test a password.
    if honeypot:
        log.warning("auth.suspected_bot", extra={"username": username[:32], "ip": client_ip})
        raise InvalidCredentials()

    user = user_repo.get_by_username(db, username)
    # Always run the hash check, even for an unknown username, so both cases
    # take the same time (see Passwords.verify).
    if not passwords.verify(user.password_hash if user else None, password) or user is None:
        _log_failure("unknown_user" if user is None else "bad_password", username, client_ip)
        raise InvalidCredentials()

    now = utcnow()
    raw_secret = tokens.new_secret()
    session_repo.delete_dead_for_user(db, user.id, now)
    session_repo.create(
        db, session_id=session_id(raw_secret), user_id=user.id, expires_at=now + timedelta(seconds=tokens.ttl_seconds)
    )
    db.commit()
    log.info("auth.login", extra={"ip": client_ip})
    return LoginResult(user=user, cookie_value=tokens.sign(raw_secret))


def resolve(db: Session, tokens: SessionTokens, cookie_value: str | None) -> User | None:
    """The user behind a session cookie, or None if it's missing, forged, expired or revoked."""
    if not cookie_value:
        return None
    raw_secret = tokens.unsign(cookie_value)
    if raw_secret is None:
        return None
    row = session_repo.get_active(db, session_id(raw_secret), utcnow())
    if row is None:
        return None
    return user_repo.get(db, row.user_id)


def logout(db: Session, tokens: SessionTokens, cookie_value: str | None) -> None:
    raw_secret = tokens.unsign(cookie_value) if cookie_value else None
    if raw_secret is None:
        return
    session_repo.revoke(db, session_id(raw_secret), utcnow())
    db.commit()
    log.info("auth.logout")
