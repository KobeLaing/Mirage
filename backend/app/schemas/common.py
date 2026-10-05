from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Unknown fields are rejected (422) rather than silently ignored (SR-20)."""

    model_config = ConfigDict(extra="forbid")


class ErrorInfo(BaseModel):
    code: str
    message: str
    request_id: str | None
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorInfo
