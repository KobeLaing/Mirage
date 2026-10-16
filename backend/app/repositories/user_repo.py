from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from app.db.models import User


def get(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_by_username(db: Session, username: str) -> User | None:
    """Usernames are matched case-insensitively, so "kobelaing" finds "KobeLaing"."""
    return db.scalar(select(User).where(func.lower(User.handle) == username.lower()))


def top_by_xp(db: Session, limit: int) -> list[User]:
    # Ties go to the older account (lower id), so the order is stable between requests.
    return list(db.scalars(select(User).order_by(User.xp.desc(), User.id.asc()).limit(limit)))


def create(
    db: Session, *, handle: str, display_name: str, avatar_id: int, xp: int = 0, password_hash: str | None = None
) -> User:
    user = User(handle=handle, display_name=display_name, avatar_id=avatar_id, xp=xp, password_hash=password_hash)
    db.add(user)
    db.flush()
    return user


def add_xp(db: Session, user_id: int, delta: int) -> None:
    """Atomic in-database increment, floored at 0 (portable CASE, not MAX/GREATEST)."""
    new_xp = User.xp + delta
    db.execute(
        update(User)
        .where(User.id == user_id)
        .values(xp=case((new_xp < 0, 0), else_=new_xp))
        # Refresh any User already loaded in this session so responses show the new XP.
        .execution_options(synchronize_session="fetch")
    )


def current_xp(db: Session, user_id: int) -> int:
    return db.scalar(select(User.xp).where(User.id == user_id)) or 0


def set_avatar(db: Session, user: User, avatar_id: int) -> None:
    user.avatar_id = avatar_id
