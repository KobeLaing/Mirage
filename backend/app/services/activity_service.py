"""Profile "recent activity" (FR-42): posts the user voted on (with how they voted)
plus their own posts, newest first. A fixed number of queries regardless of size."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Post, User
from app.errors import NotFound
from app.repositories import post_repo, user_repo, vote_repo
from app.schemas.posts import Activity, ActivityItem
from app.services import post_views
from app.storage.base import MediaStorage

MAX_ITEMS = 50


@dataclass
class _Entry:
    type: str
    at: datetime
    post: Post
    vote: str | None


def recent(db: Session, storage: MediaStorage, user_id: int, viewer: User, limit: int) -> Activity:
    if user_repo.get(db, user_id) is None:
        raise NotFound("That user doesn't exist.")
    limit = max(1, min(limit, MAX_ITEMS))

    own_posts = post_repo.list_by_author(db, user_id, limit)
    own_votes = vote_repo.values_for_user(db, user_id, [p.id for p in own_posts])
    entries = [_Entry("posted", p.created_at, p, own_votes.get(p.id)) for p in own_posts]
    # A post the user both made and voted on shows once, as "posted", with their vote.
    entries += [
        _Entry("voted", v.updated_at, p, v.value)
        for v, p in vote_repo.recent_by_user(db, user_id, limit)
        if p.author_id != user_id
    ]
    entries.sort(key=lambda e: (e.at, e.post.id), reverse=True)
    entries = entries[:limit]

    views = {view.id: view for view in post_views.build(db, storage, [e.post for e in entries], viewer)}
    # In Blind Mode, how the profile owner voted is also an opinion on the post,
    # so it's withheld for posts the viewer hasn't voted on yet.
    return Activity(
        items=[
            ActivityItem(type=e.type, at=e.at, post=views[e.post.id], vote=None if views[e.post.id].blind else e.vote)
            for e in entries
        ]
    )
