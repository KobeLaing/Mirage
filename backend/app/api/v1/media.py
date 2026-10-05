from fastapi import APIRouter, Path
from fastapi.responses import FileResponse

from app.api.deps import Storage
from app.schemas.common import ErrorResponse
from app.services import media_service

router = APIRouter(prefix="/media", tags=["media"])

# Stored files are images/videos only, but these headers make sure a browser can
# never treat one as a document with script (SR-6, AC-8).
MEDIA_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
    "Cross-Origin-Resource-Policy": "same-site",
    "Cache-Control": "public, max-age=31536000, immutable",  # keys are random and never reused
}


@router.get("/{key}", responses={404: {"model": ErrorResponse}})
def get_media(storage: Storage, key: str = Path(max_length=64)) -> FileResponse:
    path, mime = media_service.resolve_local(storage, key)
    return FileResponse(path, media_type=mime, headers=MEDIA_HEADERS, content_disposition_type="inline")
