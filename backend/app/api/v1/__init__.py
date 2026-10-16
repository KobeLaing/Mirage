from fastapi import APIRouter, Depends

from app.api.deps import csrf_protect
from app.api.v1 import auth, comments, leaderboard, media, posts, reactions, scanner, users, votes

# CSRF protection covers every route under /api/v1 (it ignores GET requests).
router = APIRouter(prefix="/api/v1", dependencies=[Depends(csrf_protect)])
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(posts.router)
router.include_router(votes.router)
router.include_router(reactions.router)
router.include_router(comments.router)
router.include_router(leaderboard.router)
router.include_router(scanner.router)
router.include_router(media.router)
