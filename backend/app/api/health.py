from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.deps import DB
from app.services import health_service

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DB) -> JSONResponse:
    ok = health_service.database_ok(db)
    return JSONResponse(
        {"status": "ok" if ok else "degraded", "database": "ok" if ok else "unreachable"},
        status_code=200 if ok else 503,
    )
