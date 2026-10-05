"""Re-encode images to strip EXIF/GPS/XMP and anything appended to the file (SR-7, AC-9)."""

import io
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence

from app.media.sniff import DetectedType


class InvalidImage(Exception):
    pass


@dataclass(frozen=True)
class CleanImage:
    data: bytes
    width: int
    height: int


# Only the formats we sniff for are ever handed to Pillow.
_ANIMATED = {"GIF"}


def reencode(path: Path, detected: DetectedType, max_pixels: int) -> CleanImage:
    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        with warnings.catch_warnings():
            # A decompression-bomb warning is treated as an error, not a hint (AC-11).
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path, formats=[detected.pillow_format]) as probe:
                probe.verify()
            with Image.open(path, formats=[detected.pillow_format]) as img:
                return _reencode_open(img, detected)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidImage("image dimensions too large") from exc
    except InvalidImage:
        raise
    except Exception as exc:  # Pillow raises many types for malformed input
        raise InvalidImage("image could not be decoded") from exc


def _reencode_open(img: Image.Image, detected: DetectedType) -> CleanImage:
    fmt = detected.pillow_format
    out = io.BytesIO()
    icc = img.info.get("icc_profile")  # colour profile, kept: not personal metadata

    if fmt in _ANIMATED and getattr(img, "n_frames", 1) > 1:
        frames, durations = [], []
        for frame in ImageSequence.Iterator(img):
            durations.append(frame.info.get("duration", 100))
            clean = frame.copy()
            clean.info = {k: v for k, v in frame.info.items() if k in ("transparency",)}
            frames.append(clean)
        frames[0].save(
            out, fmt, save_all=True, append_images=frames[1:], duration=durations,
            loop=img.info.get("loop", 0),
        )
        width, height = img.size
    else:
        img.load()
        # Bake the EXIF orientation into the pixels before the EXIF is dropped.
        oriented = ImageOps.exif_transpose(img)
        clean = oriented.copy()
        # Drop every metadata entry (exif, xmp, comments, text chunks) except transparency.
        clean.info = {k: v for k, v in oriented.info.items() if k in ("transparency",)}
        width, height = clean.size
        if fmt == "JPEG":
            if clean.mode not in ("RGB", "L"):
                clean = clean.convert("RGB")
            clean.save(out, "JPEG", quality=90, icc_profile=icc)
        elif fmt == "PNG":
            clean.save(out, "PNG", icc_profile=icc)
        elif fmt == "GIF":
            clean.save(out, "GIF")
        else:
            raise InvalidImage("unsupported image format")

    return CleanImage(out.getvalue(), width, height)
