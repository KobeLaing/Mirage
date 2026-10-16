from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile

from app.api.deps import CurrentUser, Limits, rate_limit
from app.schemas.common import ErrorResponse
from app.schemas.scanner import ScanResult
from app.services import scanner_service

router = APIRouter(prefix="/scanner", tags=["scanner"])

ERRORS = {code: {"model": ErrorResponse} for code in (401, 403, 413, 415, 422, 429)}


# Private: the file is analysed and deleted; it is never stored or posted.
# Rate-limited per user because scans (especially videos) are CPU-heavy.
@router.post("", response_model=ScanResult, responses=ERRORS, dependencies=[rate_limit("scan")])
def scan(
    request: Request,
    limits: Limits,
    user: CurrentUser,
    file: Annotated[UploadFile, File(description="One image or video to check")],
) -> ScanResult:
    return scanner_service.scan(file.file, limits, request.app.state.scanner)
