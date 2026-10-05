"""Operational queries: health check and the seed script's reset."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Post, Reaction, User, Vote


def ping(db: Session) -> None:
    db.execute(select(1))


def all_media_keys(db: Session) -> list[str]:
    return list(db.scalars(select(Post.media_key)))


def wipe_all(db: Session) -> None:
    for model in (Reaction, Vote, Post, User):
        db.execute(delete(model))
