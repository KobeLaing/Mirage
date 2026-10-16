from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DB, CurrentUser, Storage
from app.schemas.common import ErrorResponse
from app.schemas.posts import Activity
from app.schemas.users import AvatarUpdate, BlindModeState, BlindModeUpdate, Profile
from app.services import activity_service, user_service

router = APIRouter(tags=["users"])

ERRORS = {code: {"model": ErrorResponse} for code in (401, 403, 404, 422)}


@router.get("/me", response_model=Profile, responses=ERRORS)
def me(db: DB, user: CurrentUser) -> Profile:
    return user_service.get_profile(db, user.id)


# Only "/me/..." routes write to a user: there is no route that takes another user's id for a write (SR-11).
@router.put("/me/avatar", response_model=Profile, responses=ERRORS)
def set_avatar(body: AvatarUpdate, db: DB, user: CurrentUser) -> Profile:
    return user_service.set_avatar(db, user, body.avatar_id)


@router.put("/me/blind-mode", response_model=BlindModeState, responses=ERRORS)
def set_blind_mode(body: BlindModeUpdate, db: DB, user: CurrentUser) -> BlindModeState:
    return user_service.set_blind_mode(db, user, body.enabled)


@router.get("/users/{user_id}", response_model=Profile, responses=ERRORS)
def profile(user_id: int, db: DB, viewer: CurrentUser) -> Profile:
    return user_service.get_profile(db, user_id)


@router.get("/users/{user_id}/activity", response_model=Activity, responses=ERRORS)
def activity(
    user_id: int,
    db: DB,
    storage: Storage,
    viewer: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=activity_service.MAX_ITEMS)] = 30,
) -> Activity:
    return activity_service.recent(db, storage, user_id, viewer, limit)
