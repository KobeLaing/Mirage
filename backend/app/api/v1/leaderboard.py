from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.schemas.common import ErrorResponse
from app.schemas.leaderboard import Leaderboard
from app.services import leaderboard_service

router = APIRouter(tags=["leaderboard"])


@router.get("/leaderboard", response_model=Leaderboard, responses={401: {"model": ErrorResponse}})
def leaderboard(db: DB, viewer: CurrentUser) -> Leaderboard:
    return leaderboard_service.top(db)
