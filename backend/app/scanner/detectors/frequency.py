"""Frequency analysis (FFT), for images.

Looks for the faint repeating grid that some image generators leave behind
when they upsample. The maths lives in analysis.periodic_peak_z(); this
module turns the measurement into a score.

Absence of a pattern is only weak evidence of a real photo: many modern
generators leave no visible grid. So a "no pattern" reading leans real only
slightly, with low confidence.
"""

from app.scanner.analysis import periodic_peak_z
from app.scanner.base import Detector, DetectorResult, MediaInput


def score_peak(z: float | None, weak: float, strong: float) -> DetectorResult:
    if z is None:
        return DetectorResult.no_signal("Too small to analyse the frequency spectrum (needs at least 128x128 pixels).")
    if z >= strong:
        return DetectorResult(
            score=0.8, confidence=0.7, conclusive=True,
            explanation="A strong repeating pattern shows up in the frequency spectrum, "
                        "a known trace of image-generator upsampling.",
        )
    if z >= weak:
        return DetectorResult(
            score=0.62, confidence=0.4,
            explanation="A faint repeating pattern shows up in the frequency spectrum. It could come "
                        "from a generator, or from resizing or sharpening.",
        )
    return DetectorResult(
        score=0.42, confidence=0.25,
        explanation="No unusual repeating pattern in the frequency spectrum. "
                    "That doesn't rule out AI: many newer generators leave none.",
    )


class FrequencyDetector(Detector):
    name = "frequency"
    label = "Frequency analysis (FFT)"
    media_types = frozenset({"image"})

    def analyze(self, media: MediaInput) -> DetectorResult:
        z = periodic_peak_z(media.gray, block_coded=media.mime == "image/jpeg")
        return score_peak(z, float(self.options.get("peak_z_weak", 12.0)), float(self.options.get("peak_z_strong", 25.0)))
