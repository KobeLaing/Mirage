from pathlib import Path

from app.errors import NotFound
from app.media.sniff import MIME_BY_EXT
from app.storage.base import MediaStorage


def resolve_local(storage: MediaStorage, key: str) -> tuple[Path, str]:
    """Path and Content-Type for a stored file. The type comes from the extension,
    which itself came from content sniffing at upload time."""
    path = storage.local_path(key)  # validates the key; None for bad or missing keys
    if path is None:
        raise NotFound("Media not found.")
    return path, MIME_BY_EXT[path.suffix.lstrip(".")]
