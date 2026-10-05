"""Turns an untrusted upload stream into validated, sanitised bytes ready to store.

Used by post creation and by the seed script, so seeded media gets exactly the
same treatment as user uploads (FR-74).
"""

import io
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.errors import PayloadTooLarge, UnsupportedMediaType
from app.media import sanitize, sniff

log = logging.getLogger("mirage.media")

CHUNK = 64 * 1024


@dataclass(frozen=True)
class MediaLimits:
    max_image_bytes: int
    max_video_bytes: int
    max_image_pixels: int


@dataclass
class ProcessedMedia:
    kind: str
    mime: str
    ext: str
    width: int | None
    height: int | None
    _data: bytes | None = None
    _path: Path | None = None

    def open(self) -> BinaryIO:
        if self._data is not None:
            return io.BytesIO(self._data)
        if self._path is None:
            raise RuntimeError("processed media has no content")
        return self._path.open("rb")


def _reject(reason: str, exc: type[Exception], message: str | None = None):
    log.warning("upload.rejected", extra={"reason": reason})
    return exc(message) if message else exc()


def process(src: BinaryIO, limits: MediaLimits, workdir: Path) -> ProcessedMedia:
    """Copy src to a temp file (capped), sniff, then sanitise or structure-check.

    Raises PayloadTooLarge (413) or UnsupportedMediaType (415). The caller owns
    `workdir` and deletes it afterwards.
    """
    hard_cap = max(limits.max_image_bytes, limits.max_video_bytes)
    fd, tmp_name = tempfile.mkstemp(dir=workdir, prefix="upload-")
    os.close(fd)
    tmp = Path(tmp_name)
    written = 0
    with tmp.open("wb") as out:
        while chunk := src.read(CHUNK):
            written += len(chunk)
            if written > hard_cap:
                raise _reject("too_large", PayloadTooLarge)
            out.write(chunk)
    if written == 0:
        raise _reject("empty", UnsupportedMediaType, "The file is empty.")

    with tmp.open("rb") as f:
        detected = sniff.detect(f.read(sniff.HEADER_BYTES))
    if detected is None:
        raise _reject("type_not_allowed", UnsupportedMediaType)

    if detected.kind == "image":
        if written > limits.max_image_bytes:
            raise _reject("image_too_large", PayloadTooLarge, "Images can be at most "
                          f"{limits.max_image_bytes // (1024 * 1024)} MB.")
        try:
            clean = sanitize.reencode(tmp, detected, limits.max_image_pixels)
        except sanitize.InvalidImage:
            raise _reject("image_invalid", UnsupportedMediaType, "That image file is damaged or not supported.")
        return ProcessedMedia("image", detected.mime, detected.ext, clean.width, clean.height, _data=clean.data)

    if written > limits.max_video_bytes:
        raise _reject("video_too_large", PayloadTooLarge, "Videos can be at most "
                      f"{limits.max_video_bytes // (1024 * 1024)} MB.")
    if detected is sniff.MP4 and not sniff.mp4_structure_ok(tmp):
        raise _reject("video_invalid", UnsupportedMediaType, "That video file is damaged or not supported.")
    # Videos are stored as-is: no transcoding, so metadata is kept (known gap).
    return ProcessedMedia("video", detected.mime, detected.ext, None, None, _path=tmp)


def new_workdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="mirage-upload-"))


def cleanup(workdir: Path) -> None:
    shutil.rmtree(workdir, ignore_errors=True)
