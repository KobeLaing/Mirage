"""File metadata analysis, for images.

Three kinds of clue, from strongest to weakest:
1. Generator fingerprints: a generator's name or settings in EXIF, XMP or
   PNG text chunks (Stable Diffusion front-ends save the full prompt and
   sampler settings, ComfyUI saves its workflow). Strong evidence of AI.
2. Camera data: a camera make and model plus exposure settings (shutter
   speed, aperture, ISO) is what a real camera writes. Leans real, but only
   moderately, because EXIF is easy to copy from another photo.
3. Editing software tags (Photoshop, GIMP, ...): reported, but not scored.
   Being edited says nothing about whether the original was AI-made.

No metadata at all scores nothing. Social apps and messaging services strip
it from everything, so its absence proves nothing.
"""

import logging

from PIL import ExifTags, Image

from app.scanner.base import Detector, DetectorResult, MediaInput
from app.scanner.fingerprints import find_generators, looks_like_sd_parameters

log = logging.getLogger("mirage.scanner.metadata")

EDITORS = ("photoshop", "lightroom", "gimp", "snapseed", "canva", "picsart", "affinity", "pixelmator", "capture one")
EXPOSURE_TAGS = (ExifTags.Base.ExposureTime, ExifTags.Base.FNumber, ExifTags.Base.ISOSpeedRatings, ExifTags.Base.FocalLength)
TEXT_TAGS = (ExifTags.Base.Software, ExifTags.Base.ImageDescription, ExifTags.Base.Artist, ExifTags.Base.UserComment)
MAX_TEXT = 200_000  # metadata text we'll look through; enough for any real XMP packet


def _as_text(value) -> str:
    if isinstance(value, bytes):
        return value[:MAX_TEXT].decode("utf-8", errors="ignore")
    return str(value)[:MAX_TEXT]


def read_metadata(path) -> tuple[dict, str]:
    """(EXIF as {tag_id: value}, all other metadata text joined together)."""
    with Image.open(path) as img:
        exif = img.getexif()
        tags = dict(exif)
        try:
            tags.update(exif.get_ifd(ExifTags.IFD.Exif))
        except Exception:  # a corrupt sub-IFD shouldn't stop the scan
            log.info("metadata.exif_ifd_unreadable")
        # img.info holds XMP, ICC, PNG text chunks ("parameters", "prompt",
        # "workflow", "Software", ...), GIF comments, and so on.
        texts = [f"{key}: {_as_text(value)}" for key, value in img.info.items() if key not in ("icc_profile", "exif")]
    texts += [_as_text(tags[t]) for t in TEXT_TAGS if t in tags]
    return tags, "\n".join(texts)


class MetadataDetector(Detector):
    name = "metadata"
    label = "File metadata"
    media_types = frozenset({"image"})

    def analyze(self, media: MediaInput) -> DetectorResult:
        tags, text = read_metadata(media.path)

        generators = find_generators(text)
        if generators or looks_like_sd_parameters(text):
            found = ", ".join(generators[:3]) if generators else "Stable Diffusion settings"
            return DetectorResult(
                score=0.95, confidence=0.9, conclusive=True,
                explanation=f"The file's metadata names an AI generator: {found}.",
            )

        make = _as_text(tags.get(ExifTags.Base.Make, "")).strip()
        model = _as_text(tags.get(ExifTags.Base.Model, "")).strip()
        exposure = sum(1 for t in EXPOSURE_TAGS if t in tags)
        software = _as_text(tags.get(ExifTags.Base.Software, "")).strip()
        edited = next((e for e in EDITORS if e in software.lower()), None)
        edit_note = f" It was also saved by editing software ({software[:40]})." if edited else ""

        if make and model and exposure >= 2:
            return DetectorResult(
                score=0.2, confidence=0.6, conclusive=True,
                explanation=f"Camera data is present ({make} {model}, with exposure settings). "
                            f"That's typical of a real photo, though EXIF can be copied.{edit_note}",
            )
        if edited:
            return DetectorResult.no_signal(
                f"Edited with {software[:40]}. Editing alone doesn't show whether the original was AI-made."
            )
        return DetectorResult.no_signal(
            "No camera or generator metadata. Many apps strip metadata, so this points neither way."
        )
