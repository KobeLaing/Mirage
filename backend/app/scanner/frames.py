"""Reading frames out of an uploaded video with OpenCV.

Frames are taken at evenly spaced points through the whole clip, so a short
AI-generated section can't hide between samples. Reading is bounded (a fixed
number of frames, a cap on how far we seek) so a hostile or broken file can't
keep the server busy decoding for minutes.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import cv2
import numpy as np

MAX_FRAMES_TO_SEEK = 20_000  # ~11 minutes at 30 fps; beyond this we sample the start only
FLOW_WIDTH = 480  # optical flow doesn't need full resolution


@contextmanager
def _open(path: Path) -> Iterator[cv2.VideoCapture]:
    cap = cv2.VideoCapture(str(path))
    try:
        yield cap
    finally:
        cap.release()


def _positions(total: int, count: int, need_next: bool) -> list[int]:
    last = max(0, min(total, MAX_FRAMES_TO_SEEK) - (2 if need_next else 1))
    if count <= 1 or last == 0:
        return [0]
    return sorted({round(i * last / (count - 1)) for i in range(count)})


def sample_frames(path: Path, count: int) -> list[np.ndarray]:
    """`count` BGR frames spread evenly through the video."""
    frames = []
    with _open(path) as cap:
        if not cap.isOpened():
            return []
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        for pos in _positions(total, count, need_next=False):
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ok, frame = cap.read()
            if ok and frame is not None:
                frames.append(frame)
    return frames


def sample_pairs(path: Path, count: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """`count` pairs of *consecutive* frames, as small grayscale images for optical flow."""
    pairs = []
    with _open(path) as cap:
        if not cap.isOpened():
            return []
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        for pos in _positions(total, count, need_next=True):
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ok1, a = cap.read()
            ok2, b = cap.read()
            if ok1 and ok2 and a is not None and b is not None:
                pairs.append((_small_gray(a), _small_gray(b)))
    return pairs


def to_gray(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)


def _small_gray(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    if w > FLOW_WIDTH:
        gray = cv2.resize(gray, (FLOW_WIDTH, round(h * FLOW_WIDTH / w)), interpolation=cv2.INTER_AREA)
    return gray
