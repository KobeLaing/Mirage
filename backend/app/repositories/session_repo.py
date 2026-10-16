from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db.models import UserSession


def create(db: Session, *, session_id: str, user_id: int, expires_at: datetime) -> UserSession:
    row = UserSession(id=session_id, user_id=user_id, expires_at=expires_at)
    db.add(row)
    db.flush()
    return row


def get_active(db: Session, session_id: str, now: datetime) -> UserSession | None:
    return db.scalar(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    )


def revoke(db: Session, session_id: str, now: datetime) -> None:
    db.execute(
        update(UserSession)
        .where(UserSession.id == session_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def delete_dead_for_user(db: Session, user_id: int, now: datetime) -> None:
    """Housekeeping at login, so the table doesn't grow forever."""
    db.execute(
        delete(UserSession).where(
            UserSession.user_id == user_id,
            (UserSession.expires_at <= now) | UserSession.revoked_at.is_not(None),
        )
    )
