"""Noise residual analysis, for images.

Real camera sensors leave random noise that gets stronger in brighter areas;
generated images tend to have smooth areas that are unnaturally clean. The
measurement is analysis.noise_stats(); this module scores it.

Confidence is deliberately low. JPEG compression and phone "beauty" filters
erase noise too, and film grain filters add it back, so this check can only
nudge the result, never decide it alone.
"""

from app.scanner.analysis import NoiseStats, noise_stats
from app.scanner.base import Detector, DetectorResult, MediaInput


def score_noise(stats: NoiseStats | None) -> DetectorResult:
    if stats is None:
        return DetectorResult.no_signal("Not enough smooth area to measure sensor noise.")
    if stats.flat_sigma < 0.35 and abs(stats.brightness_corr) < 0.2:
        return DetectorResult(
            score=0.7, confidence=0.4, conclusive=True,
            explanation="Smooth areas are almost perfectly clean, with none of the grain a camera "
                        "sensor leaves. Common in generated images, but heavy denoising does this too.",
        )
    if stats.flat_sigma >= 1.0 and stats.brightness_corr >= 0.3:
        return DetectorResult(
            score=0.3, confidence=0.4, conclusive=True,
            explanation="Smooth areas carry natural-looking grain that gets stronger in brighter "
                        "areas, the way camera sensor noise behaves.",
        )
    return DetectorResult(
        score=0.5, confidence=0.15,
        explanation="The noise pattern is mixed and doesn't clearly match a camera or a generator.",
    )


class NoiseDetector(Detector):
    name = "noise"
    label = "Noise residual analysis"
    media_types = frozenset({"image"})

    def analyze(self, media: MediaInput) -> DetectorResult:
        return score_noise(noise_stats(media.gray))
