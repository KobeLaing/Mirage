from collections import defaultdict
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import Post, Reaction, Vote


def create(db: Session, **fields) -> Post:
    post = Post(**fields)
    db.add(post)
    db.flush()
    return post


def get(db: Session, post_id: int) -> Post | None:
    return db.scalar(select(Post).options(joinedload(Post.author)).where(Post.id == post_id))


def list_page(db: Session, *, before: tuple[datetime, int] | None, limit: int) -> list[Post]:
    """Newest first, keyset pagination on (created_at, id). Served by ix_posts_feed."""
    stmt = select(Post).options(joinedload(Post.author))
    if before is not None:
        created_at, post_id = before
        stmt = stmt.where(
            or_(Post.created_at < created_at, and_(Post.created_at == created_at, Post.id < post_id))
        )
    stmt = stmt.order_by(Post.created_at.desc(), Post.id.desc()).limit(limit)
    return list(db.scalars(stmt))


def list_by_author(db: Session, author_id: int, limit: int) -> list[Post]:
    stmt = (
        select(Post)
        .options(joinedload(Post.author))
        .where(Post.author_id == author_id)
        .order_by(Post.created_at.desc(), Post.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def delete(db: Session, post: Post) -> None:
    db.delete(post)


def vote_counts(db: Session, post_ids: list[int]) -> dict[int, dict[str, int]]:
    """One GROUP BY query for a whole page (no N+1)."""
    counts: dict[int, dict[str, int]] = defaultdict(dict)
    if post_ids:
        rows = db.execute(
            select(Vote.post_id, Vote.value, func.count())
            .where(Vote.post_id.in_(post_ids))
            .group_by(Vote.post_id, Vote.value)
        )
        for post_id, value, n in rows:
            counts[post_id][value] = n
    return counts


def reaction_counts(db: Session, post_ids: list[int]) -> dict[int, dict[str, int]]:
    counts: dict[int, dict[str, int]] = defaultdict(dict)
    if post_ids:
        rows = db.execute(
            select(Reaction.post_id, Reaction.kind, func.count())
            .where(Reaction.post_id.in_(post_ids))
            .group_by(Reaction.post_id, Reaction.kind)
        )
        for post_id, kind, n in rows:
            counts[post_id][kind] = n
    return counts
