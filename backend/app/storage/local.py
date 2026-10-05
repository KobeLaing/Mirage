import os
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO

from app.storage.base import is_valid_key


class LocalDiskStorage:
    """Stores media under a data directory that is never imported or executed (SR-5)."""

    def __init__(self, root: Path, public_api_url: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.public_api_url = public_api_url.rstrip("/")

    def _path(self, key: str) -> Path:
        # Keys are server-generated, but validate anyway before touching the disk (AC-10).
        if not is_valid_key(key):
            raise ValueError("invalid media key")
        path = (self.root / key).resolve()
        if path.parent != self.root:
            raise ValueError("invalid media key")
        return path

    def save(self, key: str, src: BinaryIO) -> None:
        target = self._path(key)
        # Write to a temp file in the same directory, then rename atomically, so a
        # half-written file is never visible under its final name.
        fd, tmp_name = tempfile.mkstemp(dir=self.root, prefix=".incoming-")
        try:
            with os.fdopen(fd, "wb") as out:
                shutil.copyfileobj(src, out, length=64 * 1024)
            os.replace(tmp_name, target)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def url_for(self, key: str) -> str:
        return f"{self.public_api_url}/api/v1/media/{key}"

    def local_path(self, key: str) -> Path | None:
        try:
            path = self._path(key)
        except ValueError:
            return None
        return path if path.is_file() else None
