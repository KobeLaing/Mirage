from sqlalchemy import case, select, update
from sqlalchemy.orm import Session

from app.db.models import User


def get(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def list_all(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


def create(db: Session, *, handle: str, display_name: str, avatar_id: int, xp: int = 0) -> User:
    user = User(handle=handle, display_name=display_name, avatar_id=avatar_id, xp=xp)
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
