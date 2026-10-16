"""Frame sampling, for videos: the image frequency and noise checks, run on frames.

We take frames at regular intervals through the clip, run the same FFT and
noise-residual measurements as for images (app/scanner/analysis.py), and use
the median across frames. The median ignores a few odd frames (a fade, a
title card) instead of letting one frame swing the result.

Video codecs compress much harder than photo JPEGs and smooth away sensor
noise, so the noise reading gets half its usual confidence here.
"""

import numpy as np

from app.scanner.analysis import NoiseStats, noise_stats, periodic_peak_z
from app.scanner.base import Detector, DetectorResult, MediaInput
from app.scanner.detectors.frequency import score_peak
from app.scanner.detectors.noise import score_noise
from app.scanner.frames import sample_frames, to_gray

VIDEO_NOISE_CONFIDENCE = 0.5


class VideoFramesDetector(Detector):
    name = "video_frames"
    label = "Frame sampling (frequency + noise)"
    media_types = frozenset({"video"})

    def analyze(self, media: MediaInput) -> DetectorResult:
        frames = sample_frames(media.path, int(self.options.get("frames", 12)))
        if not frames:
            return DetectorResult.no_signal("Couldn't decode any frames from this video.")
        grays = [to_gray(f) for f in frames]

        zs = [z for z in (periodic_peak_z(g, block_coded=True) for g in grays) if z is not None]
        stats = [s for s in (noise_stats(g) for g in grays) if s is not None]
        freq = score_peak(
            float(np.median(zs)) if zs else None,
            float(self.options.get("peak_z_weak", 12.0)),
            float(self.options.get("peak_z_strong", 25.0)),
        )
        noise = score_noise(
            NoiseStats(
                flat_sigma=float(np.median([s.flat_sigma for s in stats])),
                brightness_corr=float(np.median([s.brightness_corr for s in stats])),
                flat_blocks=int(np.median([s.flat_blocks for s in stats])),
            ) if stats else None
        )
        parts = [(freq, freq.confidence), (noise, noise.confidence * VIDEO_NOISE_CONFIDENCE)]
        parts = [(r, c) for r, c in parts if r.score is not None and c > 0]
        if not parts:
            return DetectorResult.no_signal(f"Checked {len(frames)} frames but they were too small to analyse.")

        total = sum(c for _, c in parts)
        return DetectorResult(
            score=sum(r.score * c for r, c in parts) / total,
            confidence=max(c for _, c in parts),
            conclusive=any(r.conclusive for r, _ in parts),
            explanation=f"Checked {len(frames)} frames. {freq.explanation} {noise.explanation}",
        )
