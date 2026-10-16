"""Operational queries: health check and the seed script's reset."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Comment, Post, Reaction, User, UserSession, Vote


def ping(db: Session) -> None:
    db.execute(select(1))


def all_media_keys(db: Session) -> list[str]:
    return list(db.scalars(select(Post.media_key)))


def wipe_all(db: Session) -> None:
    # Children before parents, so foreign keys never point at a deleted row.
    for model in (Comment, Reaction, Vote, Post, UserSession, User):
        db.execute(delete(model))
