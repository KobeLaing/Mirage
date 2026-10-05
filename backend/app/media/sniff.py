"""Identify uploads by their bytes, never by name or client Content-Type (SR-1, SR-2)."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DetectedType:
    kind: str  # "image" | "video"
    mime: str
    ext: str
    pillow_format: str | None = None


# The complete allow-list (SR-1): JPEG, PNG and GIF images, MP4 videos.
# Anything else (WebP, WebM, SVG, HEIC, ...) is rejected with 415.
JPEG = DetectedType("image", "image/jpeg", "jpg", "JPEG")
PNG = DetectedType("image", "image/png", "png", "PNG")
GIF = DetectedType("image", "image/gif", "gif", "GIF")
MP4 = DetectedType("video", "video/mp4", "mp4")

ALL_TYPES = (JPEG, PNG, GIF, MP4)
MIME_BY_EXT = {t.ext: t.mime for t in ALL_TYPES}

# ISO-BMFF "major brands" that mean an MP4 video. HEIC/AVIF images and M4A audio
# share the container, so the brand is checked rather than just "ftyp".
MP4_BRANDS = {
    b"isom", b"iso2", b"iso3", b"iso4", b"iso5", b"iso6",
    b"mp41", b"mp42", b"avc1", b"M4V ", b"mmp4", b"dash", b"MSNV",
}

HEADER_BYTES = 64


def detect(head: bytes) -> DetectedType | None:
    if head.startswith(b"\xff\xd8\xff"):
        return JPEG
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return GIF
    if head[4:8] == b"ftyp" and head[8:12] in MP4_BRANDS:
        return MP4
    return None


def mp4_structure_ok(path: Path) -> bool:
    """Walk top-level ISO-BMFF boxes: sizes must be consistent, types printable,
    'ftyp' first and a 'moov' present. Rejects files with appended junk or a
    script/HTML payload disguised behind an MP4 header."""
    size_total = path.stat().st_size
    seen_moov = False
    offset = 0
    with path.open("rb") as f:
        first = True
        while offset < size_total:
            f.seek(offset)
            header = f.read(8)
            if len(header) < 8:
                return False
            box_size = int.from_bytes(header[:4], "big")
            box_type = header[4:8]
            header_len = 8
            if box_size == 1:
                large = f.read(8)
                if len(large) < 8:
                    return False
                box_size = int.from_bytes(large, "big")
                header_len = 16
            elif box_size == 0:
                box_size = size_total - offset
            if box_size < header_len or offset + box_size > size_total:
                return False
            if not all(0x20 <= b <= 0x7E for b in box_type):
                return False
            if first and box_type != b"ftyp":
                return False
            first = False
            seen_moov = seen_moov or box_type == b"moov"
            offset += box_size
    return seen_moov
