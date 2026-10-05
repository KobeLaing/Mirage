from typing import Annotated

from pydantic import Field

from app.db.models import AVATAR_COUNT
from app.schemas.common import StrictModel


class RankOut(StrictModel):
    key: str
    name: str
    min_xp: int


class UserSummary(StrictModel):
    id: int
    handle: str
    display_name: str
    avatar_id: int
    rank: str


class Profile(StrictModel):
    id: int
    handle: str
    display_name: str
    avatar_id: int
    xp: int
    rank: RankOut
    next_rank: RankOut | None
    progress: float


class AvatarUpdate(StrictModel):
    avatar_id: Annotated[int, Field(ge=1, le=AVATAR_COUNT)]
