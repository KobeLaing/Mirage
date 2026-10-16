from app.schemas.common import StrictModel
from app.schemas.users import UserSummary


class LeaderboardEntry(StrictModel):
    position: int  # 1-based
    user: UserSummary  # includes avatar and rank key (for the badge icon)
    xp: int
    rank_name: str  # e.g. "Gold Verifier"


class Leaderboard(StrictModel):
    items: list[LeaderboardEntry]
