"""Structured JSON logs on stdout (NFR-8). Stdlib only."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# One mutable dict per request. Sync dependencies run in worker threads with a
# *copy* of the context, so a plain value set there would be lost; mutating a
# shared dict is visible to the middleware and to every log line of the request.
_request_ctx: ContextVar[dict | None] = ContextVar("request_ctx", default=None)

# Attributes every LogRecord has; anything else came from `extra=` and is logged as a field.
_STANDARD_ATTRS = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "taskName"}


def begin_request(request_id: str):
    return _request_ctx.set({"request_id": request_id, "user_id": None})


def end_request(token) -> None:
    _request_ctx.reset(token)


def current_request_id() -> str | None:
    ctx = _request_ctx.get()
    return ctx["request_id"] if ctx else None


def current_user_id() -> int | None:
    ctx = _request_ctx.get()
    return ctx["user_id"] if ctx else None


def set_user_id(value: int | None) -> None:
    ctx = _request_ctx.get()
    if ctx is not None:
        ctx["user_id"] = value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": current_request_id(),
            "user_id": current_user_id(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS and key not in entry:
                entry[key] = value
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # Uvicorn's own access log is replaced by ours (which carries request_id and user_id).
    logging.getLogger("uvicorn.access").disabled = True
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True
