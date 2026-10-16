from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import Comment


def create(db: Session, *, post_id: int, user_id: int, body: str) -> Comment:
    comment = Comment(post_id=post_id, user_id=user_id, body=body)
    db.add(comment)
    db.flush()
    return comment


def get(db: Session, comment_id: int) -> Comment | None:
    return db.get(Comment, comment_id)


def delete(db: Session, comment: Comment) -> None:
    db.delete(comment)


def latest_for_post(db: Session, post_id: int, limit: int) -> list[Comment]:
    """The newest `limit` comments, returned oldest first (newest last). Served by ix_comments_post."""
    newest_first = list(
        db.scalars(
            select(Comment)
            .options(joinedload(Comment.author))
            .where(Comment.post_id == post_id)
            .order_by(Comment.created_at.desc(), Comment.id.desc())
            .limit(limit)
        )
    )
    return newest_first[::-1]


def counts(db: Session, post_ids: list[int]) -> dict[int, int]:
    """One GROUP BY for a whole feed page (no N+1)."""
    result: dict[int, int] = defaultdict(int)
    if post_ids:
        rows = db.execute(
            select(Comment.post_id, func.count()).where(Comment.post_id.in_(post_ids)).group_by(Comment.post_id)
        )
        for post_id, n in rows:
            result[post_id] = n
    return result
