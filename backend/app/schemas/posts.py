from datetime import datetime
from typing import Literal

from app.schemas.common import StrictModel
from app.schemas.users import UserSummary

VoteValue = Literal["AI", "REAL"]
ReactionKind = Literal["heart", "like", "laugh"]

MAX_CAPTION_CHARS = 500  # matches posts.caption VARCHAR(500)
# No ASCII control characters other than tab/newline/carriage return.
CAPTION_PATTERN = r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]*$"


class MediaOut(StrictModel):
    kind: Literal["image", "video"]
    url: str
    mime_type: str
    width: int | None
    height: int | None


class VoteCounts(StrictModel):
    ai: int = 0
    real: int = 0


class ReactionCounts(StrictModel):
    heart: int = 0
    like: int = 0
    laugh: int = 0


class PostOut(StrictModel):
    id: int
    author: UserSummary
    caption: str | None
    media: MediaOut
    # null when Blind Mode hides them (blind=true): the viewer hasn't voted yet.
    votes: VoteCounts | None
    reactions: ReactionCounts | None
    my_vote: VoteValue | None
    my_reaction: ReactionKind | None
    comment_count: int | None
    blind: bool
    created_at: datetime


class FeedPage(StrictModel):
    items: list[PostOut]
    next_cursor: str | None


class ActivityItem(StrictModel):
    type: Literal["voted", "posted"]
    at: datetime
    post: PostOut
    vote: VoteValue | None  # how the profile owner voted on this post


class Activity(StrictModel):
    items: list[ActivityItem]
