"""Media storage interface (NFR-5).

Services only see this protocol. LocalDiskStorage implements it today; an
object-storage implementation (S3, GCS, Azure Blob) would return pre-signed or
CDN URLs from url_for() and None from local_path(), and nothing else changes.
"""

import re
from pathlib import Path
from typing import BinaryIO, Protocol

ALLOWED_EXTENSIONS = ("jpg", "png", "gif", "mp4")
KEY_PATTERN = re.compile(r"^[0-9a-f]{32}\.(" + "|".join(ALLOWED_EXTENSIONS) + r")$")


def is_valid_key(key: str) -> bool:
    return bool(KEY_PATTERN.fullmatch(key))


class MediaStorage(Protocol):
    def save(self, key: str, src: BinaryIO) -> None: ...

    def delete(self, key: str) -> None: ...

    def url_for(self, key: str) -> str: ...

    def local_path(self, key: str) -> Path | None: ...
