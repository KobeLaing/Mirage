"""The interface every scanner detector implements.

A detector is one independent way of judging whether media is AI-generated
(reading Content Credentials, looking at noise, checking optical flow, ...).
Each one lives in its own module under app/scanner/detectors/ and only has to:

    name                    a short id, also its section name in scanner.toml
    label                   a human-readable name for the results screen
    media_types             which kinds it handles: {"image"}, {"video"} or both
    analyze(media)          return a DetectorResult

The scanner service never needs to know what a detector does inside. It asks
the registry for the enabled detectors, calls supports() and analyze() on each,
and combines the results. That is what lets a new detector be added without
touching the service (see README, "Adding a detector").
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np

if TYPE_CHECKING:
    from app.config import Settings


@dataclass(frozen=True)
class DetectorResult:
    """One detector's opinion.

    score:       probability the media is AI-generated, 0.0 (real) to 1.0 (AI),
                 or None when the detector found nothing to judge by.
    confidence:  0..1, how much this particular reading should be trusted
                 (e.g. a noise check on a heavily compressed file is weak).
    conclusive:  True only when the signal is clear enough to stand on its own.
                 If no detector is conclusive, the overall verdict is
                 "Inconclusive" instead of a misleading middle score.
    decisive:    True for proof-level evidence (a signed C2PA "made by AI"
                 claim). It overrides the weighted average; see combine.py.
    explanation: one or two plain-English sentences for the results screen.
    """

    score: float | None
    explanation: str
    confidence: float = 1.0
    conclusive: bool = False
    decisive: bool = False
    status: str = "ok"  # "ok" | "error" | "unavailable"

    @classmethod
    def no_signal(cls, explanation: str) -> "DetectorResult":
        return cls(score=None, explanation=explanation, confidence=0.0)

    @classmethod
    def unavailable(cls, explanation: str) -> "DetectorResult":
        return cls(score=None, explanation=explanation, confidence=0.0, status="unavailable")


@dataclass
class MediaInput:
    """The file being scanned, plus decoded views that detectors share.

    Decoding is lazy and cached, so if three image detectors need the pixels
    the file is only decoded once.
    """

    path: Path
    kind: str  # "image" | "video"
    mime: str

    @cached_property
    def rgb(self) -> np.ndarray:
        """Image pixels as an RGB uint8 array (first frame for animated GIFs)."""
        from PIL import Image

        with Image.open(self.path) as img:
            return np.asarray(img.convert("RGB"))

    @cached_property
    def gray(self) -> np.ndarray:
        """Image pixels as float32 grayscale, 0..255."""
        rgb = self.rgb.astype(np.float32)
        return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


class Detector(ABC):
    """Base class for all detectors. Subclasses set the class attributes and implement analyze()."""

    name: ClassVar[str]
    label: ClassVar[str]
    media_types: ClassVar[frozenset[str]]
    # Safety flag for future third-party detectors (Hive, Sightengine, a
    # hosted Hugging Face model, ...). The registry keeps any detector that
    # sends media off this machine OFF unless it is explicitly enabled in
    # scanner.toml AND its API key is present in the environment.
    sends_media_off_device: ClassVar[bool] = False
    # Environment variable holding the API key, for detectors that need one.
    api_key_env: ClassVar[str | None] = None

    def __init__(self, options: dict[str, Any], settings: "Settings"):
        # options: the detector's own table from scanner.toml (weight, thresholds, ...).
        # settings: deployment settings from .env (model paths, future API keys).
        self.options = options
        self.settings = settings

    def supports(self, media_type: str) -> bool:
        return media_type in self.media_types

    def unavailable_reason(self) -> str | None:
        """Override to report a missing model file or dependency. None = ready."""
        return None

    @abstractmethod
    def analyze(self, media: MediaInput) -> DetectorResult:
        ...
