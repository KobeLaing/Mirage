from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import Reaction


def get(db: Session, user_id: int, post_id: int) -> Reaction | None:
    return db.scalar(select(Reaction).where(Reaction.user_id == user_id, Reaction.post_id == post_id))


def create(db: Session, user_id: int, post_id: int, kind: str) -> Reaction:
    reaction = Reaction(user_id=user_id, post_id=post_id, kind=kind)
    db.add(reaction)
    db.flush()
    return reaction


def change(db: Session, reaction: Reaction, kind: str) -> None:
    reaction.kind = kind
    reaction.updated_at = utcnow()


def delete(db: Session, reaction: Reaction) -> None:
    db.delete(reaction)
    db.flush()


def kinds_for_user(db: Session, user_id: int, post_ids: list[int]) -> dict[int, str]:
    if not post_ids:
        return {}
    rows = db.execute(
        select(Reaction.post_id, Reaction.kind).where(
            Reaction.user_id == user_id, Reaction.post_id.in_(post_ids)
        )
    )
    return {post_id: kind for post_id, kind in rows}
