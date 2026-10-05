from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.base import utcnow
from app.db.models import Post, Vote


def get(db: Session, user_id: int, post_id: int) -> Vote | None:
    return db.scalar(select(Vote).where(Vote.user_id == user_id, Vote.post_id == post_id))


def create(db: Session, user_id: int, post_id: int, value: str) -> Vote:
    vote = Vote(user_id=user_id, post_id=post_id, value=value)
    db.add(vote)
    db.flush()  # surfaces a unique-constraint race here, inside the transaction
    return vote


def change(db: Session, vote: Vote, value: str) -> None:
    vote.value = value
    vote.updated_at = utcnow()


def delete(db: Session, vote: Vote) -> None:
    db.delete(vote)
    db.flush()


def values_for_user(db: Session, user_id: int, post_ids: list[int]) -> dict[int, str]:
    if not post_ids:
        return {}
    rows = db.execute(
        select(Vote.post_id, Vote.value).where(Vote.user_id == user_id, Vote.post_id.in_(post_ids))
    )
    return {post_id: value for post_id, value in rows}


def recent_by_user(db: Session, user_id: int, limit: int) -> list[tuple[Vote, Post]]:
    stmt = (
        select(Vote, Post)
        .join(Post, Post.id == Vote.post_id)
        .options(joinedload(Post.author))
        .where(Vote.user_id == user_id)
        .order_by(Vote.updated_at.desc(), Vote.id.desc())
        .limit(limit)
    )
    return [(vote, post) for vote, post in db.execute(stmt).unique()]
