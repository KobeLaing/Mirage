from fastapi import APIRouter, Response, status

from app.api.deps import DB, CurrentUser, rate_limit
from app.schemas.comments import CommentIn, CommentList, CommentOut
from app.schemas.common import ErrorResponse
from app.services import comment_service

router = APIRouter(tags=["comments"])

ERRORS = {code: {"model": ErrorResponse} for code in (400, 401, 403, 404, 422, 429)}


@router.get("/posts/{post_id}/comments", response_model=CommentList, responses=ERRORS)
def list_comments(post_id: int, db: DB, user: CurrentUser) -> CommentList:
    return comment_service.list_comments(db, user, post_id)


# The author is always the signed-in user; the body has no user field (SR-11).
@router.post(
    "/posts/{post_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED,
    responses=ERRORS, dependencies=[rate_limit("comment")],
)
def add_comment(post_id: int, body: CommentIn, db: DB, user: CurrentUser) -> CommentOut:
    return comment_service.add_comment(db, user, post_id, body.body)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
def delete_comment(comment_id: int, db: DB, user: CurrentUser) -> Response:
    comment_service.delete_comment(db, user, comment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
