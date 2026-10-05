from fastapi import APIRouter

from app.api.v1 import media, posts, reactions, users, votes

router = APIRouter(prefix="/api/v1")
router.include_router(users.router)
router.include_router(posts.router)
router.include_router(votes.router)
router.include_router(reactions.router)
router.include_router(media.router)
