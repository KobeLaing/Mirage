from fastapi import APIRouter

from app.api.deps import DB, CurrentUser, rate_limit
from app.schemas.common import ErrorResponse
from app.schemas.votes import VoteIn, VoteState
from app.services import vote_service

router = APIRouter(prefix="/posts/{post_id}/vote", tags=["votes"])

ERRORS = {code: {"model": ErrorResponse} for code in (401, 404, 422, 429)}


# PUT + DELETE on "my vote" are idempotent by HTTP semantics and by implementation (FR-24).
# The voter is always the authenticated user; there is no user id in the path or body (SR-11).
@router.put("", response_model=VoteState, responses=ERRORS, dependencies=[rate_limit("vote")])
def set_vote(post_id: int, body: VoteIn, db: DB, user: CurrentUser) -> VoteState:
    return vote_service.set_vote(db, user, post_id, body.value)


@router.delete("", response_model=VoteState, responses=ERRORS, dependencies=[rate_limit("vote")])
def remove_vote(post_id: int, db: DB, user: CurrentUser) -> VoteState:
    return vote_service.remove_vote(db, user, post_id)
