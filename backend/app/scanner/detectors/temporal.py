"""Temporal consistency check (optical flow), for videos.

In real footage, almost everything that changes from one frame to the next is
explained by motion: things move, the camera pans. Generated video often has
change that motion can't explain: textures that flicker, objects that melt or
morph, details that pop in and out.

How it works, for several pairs of consecutive frames spread through the
clip:
1. Estimate optical flow (Farneback): for each pixel, where did it move to?
2. Warp the second frame back along that flow. If the motion explains the
   change, the warped frame matches the first one closely.
3. "Unexplained change" = what's left after warping, divided by how much the
   frames differed to begin with.

Pairs with almost no change (a still shot) or a huge change (a scene cut)
are skipped, because they say nothing about consistency. Confidence is kept
low: fast motion, motion blur and heavy compression also leave unexplained
change in real video.
"""

import cv2
import numpy as np

from app.scanner.base import Detector, DetectorResult, MediaInput
from app.scanner.frames import sample_pairs

MIN_CHANGE = 0.5  # mean grey-level difference below which a pair is "still"
SCENE_CUT = 40.0  # above this, the pair straddles a cut
HIGH_UNEXPLAINED = 0.6
LOW_UNEXPLAINED = 0.3


def unexplained_change(a: np.ndarray, b: np.ndarray) -> float | None:
    a32, b32 = a.astype(np.float32), b.astype(np.float32)
    change = float(np.abs(a32 - b32).mean())
    if change < MIN_CHANGE or change > SCENE_CUT:
        return None
    flow = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    h, w = a.shape
    grid_x, grid_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    warped = cv2.remap(b32, grid_x + flow[..., 0], grid_y + flow[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    m = 8  # ignore the border, where pixels move in from outside the frame
    leftover = float(np.abs(a32 - warped)[m:-m, m:-m].mean())
    return leftover / change


class TemporalDetector(Detector):
    name = "temporal"
    label = "Temporal consistency (optical flow)"
    media_types = frozenset({"video"})

    def analyze(self, media: MediaInput) -> DetectorResult:
        pairs = sample_pairs(media.path, int(self.options.get("pairs", 8)))
        ratios = [r for r in (unexplained_change(a, b) for a, b in pairs) if r is not None]
        if not ratios:
            return DetectorResult.no_signal("Too little motion between frames to check for flicker or morphing.")
        ratio = float(np.median(ratios))
        if ratio >= HIGH_UNEXPLAINED:
            return DetectorResult(
                score=0.7, confidence=0.35, conclusive=True,
                explanation=f"Much of the change between frames ({ratio:.0%}) isn't explained by motion: "
                            "signs of flicker or morphing, common in generated video.",
            )
        if ratio <= LOW_UNEXPLAINED:
            return DetectorResult(
                score=0.35, confidence=0.25,
                explanation="Changes between frames follow smooth, consistent motion, as in real footage.",
            )
        return DetectorResult(
            score=0.5, confidence=0.1,
            explanation="Some frame-to-frame change isn't explained by motion; could be compression or fast movement.",
        )
