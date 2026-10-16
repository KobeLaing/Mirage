from datetime import datetime
from typing import Annotated

from pydantic import Field

from app.schemas.common import StrictModel
from app.schemas.posts import CAPTION_PATTERN
from app.schemas.users import UserSummary

MAX_COMMENT_CHARS = 500  # matches comments.body VARCHAR(500)


class CommentIn(StrictModel):
    # Same rule as captions: no invisible control characters. HTML is allowed
    # as *text*; it's stored as typed and the frontend never renders it as HTML.
    body: Annotated[str, Field(min_length=1, max_length=MAX_COMMENT_CHARS, pattern=CAPTION_PATTERN)]


class CommentOut(StrictModel):
    id: int
    post_id: int
    author: UserSummary
    body: str
    created_at: datetime
    mine: bool  # lets the UI show a delete button; the server still checks on delete


class CommentList(StrictModel):
    items: list[CommentOut]
