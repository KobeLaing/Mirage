"""The leaderboard: the top users by XP, highest first.

XP only comes from server-side actions (votes and posts, see progression.py),
so the ranking can't be edited by a client. One query, capped at TOP_N rows.
"""

from sqlalchemy.orm import Session

from app.progression import rank_for_xp
from app.repositories import user_repo
from app.schemas.leaderboard import Leaderboard, LeaderboardEntry
from app.services.user_service import to_summary

TOP_N = 50


def top(db: Session) -> Leaderboard:
    users = user_repo.top_by_xp(db, TOP_N)
    return Leaderboard(
        items=[
            LeaderboardEntry(position=i, user=to_summary(u), xp=u.xp, rank_name=rank_for_xp(u.xp).name)
            for i, u in enumerate(users, start=1)
        ]
    )
