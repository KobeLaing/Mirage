import base64
import binascii
import json
import logging
import secrets
from datetime import datetime
from typing import BinaryIO

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.db.models import User
from app.errors import BadRequest, Forbidden, NotFound
from app.media import pipeline
from app.progression import XP_PER_POST
from app.repositories import post_repo, user_repo
from app.schemas.posts import FeedPage, PostOut
from app.services import post_views
from app.storage.base import MediaStorage

log = logging.getLogger("mirage.posts")

MAX_PAGE_SIZE = 50


class _Cursor(BaseModel):
    t: datetime
    id: int


def encode_cursor(created_at: datetime, post_id: int) -> str:
    raw = json.dumps({"t": created_at.isoformat(), "id": post_id}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    """Opaque to clients; decoded into typed values, never spliced into SQL (AC-14)."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        parsed = _Cursor.model_validate_json(base64.urlsafe_b64decode(padded.encode()))
    except (ValueError, binascii.Error, ValidationError):
        raise BadRequest("Invalid pagination cursor.") from None
    if parsed.t.tzinfo is None:
        raise BadRequest("Invalid pagination cursor.")
    return parsed.t, parsed.id


def list_feed(db: Session, storage: MediaStorage, viewer: User, cursor: str | None, limit: int) -> FeedPage:
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    before = decode_cursor(cursor) if cursor else None
    rows = post_repo.list_page(db, before=before, limit=limit + 1)
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more else None
    return FeedPage(items=post_views.build(db, storage, rows, viewer), next_cursor=next_cursor)


def get_post(db: Session, storage: MediaStorage, post_id: int, viewer: User) -> PostOut:
    post = post_repo.get(db, post_id)
    if post is None:
        raise NotFound("That post doesn't exist.")
    return post_views.build(db, storage, [post], viewer)[0]


def _normalise_caption(caption: str | None) -> str | None:
    if caption is None:
        return None
    caption = caption.strip()
    return caption or None


# Creating a post: validate and sanitise the upload (pipeline.process), store
# it under a random name, then save the post row and the author's XP in one
# transaction. If the database step fails, the stored file is deleted again,
# so a failed post leaves nothing behind and earns nothing.
def create_post(
    db: Session,
    storage: MediaStorage,
    limits: pipeline.MediaLimits,
    author: User,
    upload: BinaryIO,
    caption: str | None,
) -> PostOut:
    workdir = pipeline.new_workdir()
    try:
        media = pipeline.process(upload, limits, workdir)  # 413 / 415 on bad input
        key = f"{secrets.token_hex(16)}.{media.ext}"  # random name, never the client's (SR-4)
        with media.open() as data:
            storage.save(key, data)
    finally:
        pipeline.cleanup(workdir)

    try:
        post = post_repo.create(
            db,
            author_id=author.id,
            caption=_normalise_caption(caption),
            media_key=key,
            media_kind=media.kind,
            mime_type=media.mime,
            width=media.width,
            height=media.height,
        )
        user_repo.add_xp(db, author.id, XP_PER_POST)
        db.commit()  # post row + author XP together
    except Exception:
        db.rollback()
        storage.delete(key)  # don't leave an orphaned file behind
        raise
    log.info("post.created", extra={"post_id": post.id, "kind": media.kind})
    return get_post(db, storage, post.id, author)


def delete_post(db: Session, storage: MediaStorage, user: User, post_id: int) -> None:
    post = post_repo.get(db, post_id)
    if post is None:
        raise NotFound("That post doesn't exist.")
    if post.author_id != user.id:
        log.warning("post.delete_forbidden", extra={"post_id": post_id})
        raise Forbidden("You can only delete your own posts.")
    key = post.media_key
    post_repo.delete(db, post)  # votes and reactions cascade
    user_repo.add_xp(db, user.id, -XP_PER_POST)  # FR-53: deleting a post takes back its XP
    db.commit()
    storage.delete(key)
    log.info("post.deleted", extra={"post_id": post_id})
