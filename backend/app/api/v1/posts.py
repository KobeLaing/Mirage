from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile, status

from app.api.deps import DB, CurrentUser, Limits, OptionalUser, Storage, rate_limit
from app.schemas.common import ErrorResponse
from app.schemas.posts import CAPTION_PATTERN, MAX_CAPTION_CHARS, FeedPage, PostOut
from app.services import post_service

router = APIRouter(prefix="/posts", tags=["posts"])

ERRORS = {code: {"model": ErrorResponse} for code in (400, 401, 403, 404, 413, 415, 422, 429)}


@router.get("", response_model=FeedPage, responses=ERRORS)
def list_posts(
    db: DB,
    storage: Storage,
    viewer: OptionalUser,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=post_service.MAX_PAGE_SIZE)] = 20,
) -> FeedPage:
    return post_service.list_feed(db, storage, viewer.id if viewer else None, cursor, limit)


@router.post(
    "", response_model=PostOut, status_code=status.HTTP_201_CREATED, responses=ERRORS,
    dependencies=[rate_limit("post")],
)
def create_post(
    db: DB,
    storage: Storage,
    limits: Limits,
    user: CurrentUser,
    file: Annotated[UploadFile, File(description="One image or video")],
    caption: Annotated[str | None, Form(max_length=MAX_CAPTION_CHARS, pattern=CAPTION_PATTERN)] = None,
) -> PostOut:
    # The client's filename and Content-Type are ignored; the service sniffs the bytes.
    return post_service.create_post(db, storage, limits, user, file.file, caption)


@router.get("/{post_id}", response_model=PostOut, responses=ERRORS)
def get_post(post_id: int, db: DB, storage: Storage, viewer: OptionalUser) -> PostOut:
    return post_service.get_post(db, storage, post_id, viewer.id if viewer else None)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
def delete_post(post_id: int, db: DB, storage: Storage, user: CurrentUser) -> Response:
    post_service.delete_post(db, storage, user, post_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
