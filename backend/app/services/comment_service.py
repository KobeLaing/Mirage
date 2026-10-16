"""Comments on posts.

- Anyone signed in can comment on any post. Comments are listed newest last.
- Only the author of a comment can delete it. The check is done here, on the
  server, against the comment's stored user_id; the "mine" flag the API sends
  is only a hint for the UI.
- Commenting never changes XP, so it can't be used to farm points. Spam is
  limited by a per-user rate limit on the route instead.
"""

import logging

from sqlalchemy.orm import Session

from app.db.models import Comment, User
from app.errors import BadRequest, Forbidden, NotFound
from app.repositories import comment_repo, post_repo, vote_repo
from app.schemas.comments import CommentList, CommentOut
from app.services.blind_mode import HIDDEN_MESSAGE, is_hidden
from app.services.user_service import to_summary

log = logging.getLogger("mirage.comments")

MAX_LISTED = 200


def _out(comment: Comment, author: User, viewer_id: int) -> CommentOut:
    return CommentOut(
        id=comment.id,
        post_id=comment.post_id,
        author=to_summary(author),
        body=comment.body,
        created_at=comment.created_at,
        mine=comment.user_id == viewer_id,
    )


def _require_visible_post(db: Session, viewer: User, post_id: int) -> None:
    post = post_repo.get(db, post_id)
    if post is None:
        raise NotFound("That post doesn't exist.")
    # Blind Mode: no reading (or writing) comments until you've voted. This is
    # checked here, so the comments can't be fetched by calling the API directly.
    if is_hidden(viewer, post.author_id, vote_repo.values_for_user(db, viewer.id, [post_id]).get(post_id)):
        raise Forbidden(HIDDEN_MESSAGE)


def list_comments(db: Session, viewer: User, post_id: int) -> CommentList:
    _require_visible_post(db, viewer, post_id)
    comments = comment_repo.latest_for_post(db, post_id, MAX_LISTED)
    return CommentList(items=[_out(c, c.author, viewer.id) for c in comments])


def add_comment(db: Session, author: User, post_id: int, body: str) -> CommentOut:
    _require_visible_post(db, author, post_id)
    body = body.strip()
    if not body:
        raise BadRequest("Write something before posting a comment.")
    comment = comment_repo.create(db, post_id=post_id, user_id=author.id, body=body)
    db.commit()  # no XP change: commenting is deliberately unrewarded
    log.info("comment.created", extra={"post_id": post_id, "comment_id": comment.id})
    return _out(comment, author, author.id)


def delete_comment(db: Session, user: User, comment_id: int) -> None:
    comment = comment_repo.get(db, comment_id)
    if comment is None:
        raise NotFound("That comment doesn't exist.")
    if comment.user_id != user.id:
        log.warning("comment.delete_forbidden", extra={"comment_id": comment_id})
        raise Forbidden("You can only delete your own comments.")
    comment_repo.delete(db, comment)
    db.commit()
    log.info("comment.deleted", extra={"comment_id": comment_id})
