"""Error Level Analysis (ELA), for JPEG images.

How it works: re-save the image as a JPEG at a known quality and measure how
much each 16x16 block changes. Areas that were already compressed the same
way as the rest change by a similar small amount. A region pasted in from
another source, or retouched after the last save, often changes by a very
different amount and stands out.

What it can and can't tell us: ELA spots *editing and compositing*, not
generation as such. A fully AI-made image is usually uniform under ELA. So a
strong finding nudges the score slightly towards "manipulated" and is never
conclusive alone. It only runs on JPEGs: for PNG or GIF, the first JPEG save
changes everything, so the comparison means nothing.
"""

import io

import numpy as np
from PIL import Image

from app.scanner.analysis import NOISE_SIZE, center_crop
from app.scanner.base import Detector, DetectorResult, MediaInput

RESAVE_QUALITY = 90
BLOCK = 16
LOCALISED_RATIO = 6.0  # brightest 1% of blocks vs the typical block


def ela_ratio(rgb: np.ndarray) -> float | None:
    gray_for_crop = rgb.mean(axis=2)
    crop_gray = center_crop(gray_for_crop, NOISE_SIZE, multiple=BLOCK)
    if crop_gray is None:
        return None
    side = crop_gray.shape[0]
    h, w = rgb.shape[:2]
    top, left = (h - side) // 2, (w - side) // 2
    crop = rgb[top:top + side, left:left + side]

    buf = io.BytesIO()
    Image.fromarray(crop).save(buf, "JPEG", quality=RESAVE_QUALITY)
    resaved = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"), dtype=np.float32)
    error = np.abs(crop.astype(np.float32) - resaved).mean(axis=2)
    n = side // BLOCK
    per_block = error[: n * BLOCK, : n * BLOCK].reshape(n, BLOCK, n, BLOCK).mean(axis=(1, 3))
    return float(np.percentile(per_block, 99) / (np.median(per_block) + 1e-3))


class ElaDetector(Detector):
    name = "ela"
    label = "Error Level Analysis (ELA)"
    media_types = frozenset({"image"})

    def analyze(self, media: MediaInput) -> DetectorResult:
        if media.mime != "image/jpeg":
            return DetectorResult.no_signal("ELA only works on JPEG files, so it was skipped.")
        ratio = ela_ratio(media.rgb)
        if ratio is None:
            return DetectorResult.no_signal("Too small for Error Level Analysis.")
        if ratio >= LOCALISED_RATIO:
            return DetectorResult(
                score=0.6, confidence=0.3,
                explanation="Some areas re-compress very differently from the rest, which can mean "
                            "parts were edited or pasted in. That's a sign of editing, not proof of AI.",
            )
        return DetectorResult.no_signal(
            "Compression is even across the image: no sign of pasted-in or retouched areas."
        )
