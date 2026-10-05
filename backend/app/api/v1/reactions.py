from fastapi import APIRouter

from app.api.deps import DB, CurrentUser, rate_limit
from app.schemas.common import ErrorResponse
from app.schemas.votes import ReactionIn, ReactionState
from app.services import reaction_service

router = APIRouter(prefix="/posts/{post_id}/reaction", tags=["reactions"])

ERRORS = {code: {"model": ErrorResponse} for code in (401, 404, 422, 429)}


@router.put("", response_model=ReactionState, responses=ERRORS, dependencies=[rate_limit("react")])
def set_reaction(post_id: int, body: ReactionIn, db: DB, user: CurrentUser) -> ReactionState:
    return reaction_service.set_reaction(db, user, post_id, body.kind)


@router.delete("", response_model=ReactionState, responses=ERRORS, dependencies=[rate_limit("react")])
def remove_reaction(post_id: int, db: DB, user: CurrentUser) -> ReactionState:
    return reaction_service.remove_reaction(db, user, post_id)
