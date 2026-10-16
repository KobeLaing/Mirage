"""The one place detectors are registered and switched on or off.

To add a detector: write its module in app/scanner/detectors/, add the class
to DETECTOR_CLASSES below, and add a [detectors.<name>] table to scanner.toml.
Nothing else changes; the scanner service works from whatever this returns.

Safety rule for detectors that send media off this machine (third-party APIs,
hosted models): they are built only if scanner.toml explicitly enables them
AND their API key is present. Otherwise they are skipped with a warning, so a
missing key fails safe (no upload leaves the server) instead of crashing.
"""

import logging
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import Settings
from app.scanner.base import Detector
from app.scanner.combine import CombineConfig
from app.scanner.detectors.c2pa_detector import C2paDetector
from app.scanner.detectors.ela import ElaDetector
from app.scanner.detectors.face_swap import FaceSwapDetector
from app.scanner.detectors.frequency import FrequencyDetector
from app.scanner.detectors.metadata import MetadataDetector
from app.scanner.detectors.noise import NoiseDetector
from app.scanner.detectors.temporal import TemporalDetector
from app.scanner.detectors.video_container import VideoContainerDetector
from app.scanner.detectors.video_frames import VideoFramesDetector

log = logging.getLogger("mirage.scanner")

CONFIG_PATH = Path(__file__).with_name("scanner.toml")

# Order here is the order results are shown in.
DETECTOR_CLASSES: tuple[type[Detector], ...] = (
    C2paDetector,
    MetadataDetector,
    VideoContainerDetector,
    FrequencyDetector,
    NoiseDetector,
    ElaDetector,
    VideoFramesDetector,
    TemporalDetector,
    FaceSwapDetector,
)


@dataclass(frozen=True)
class ConfiguredDetector:
    detector: Detector
    weight: float


@dataclass(frozen=True)
class ScannerSetup:
    detectors: tuple[ConfiguredDetector, ...]
    combine: CombineConfig


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def _allowed_off_device(cls: type[Detector], name: str) -> bool:
    if not cls.api_key_env or not os.environ.get(cls.api_key_env):
        log.warning("scanner.detector_skipped_missing_key", extra={"detector": name, "env": cls.api_key_env})
        return False
    return True


def build(settings: Settings, config: dict[str, Any] | None = None) -> ScannerSetup:
    config = config if config is not None else load_config()
    tables: dict[str, dict[str, Any]] = config.get("detectors", {})
    known = {cls.name for cls in DETECTOR_CLASSES}
    for unknown in set(tables) - known:
        log.warning("scanner.unknown_detector_in_config", extra={"detector": unknown})

    built = []
    for cls in DETECTOR_CLASSES:
        options = tables.get(cls.name)
        if not options or options.get("enabled") is not True:
            continue  # missing from the config, or switched off
        if cls.sends_media_off_device and not _allowed_off_device(cls, cls.name):
            continue
        built.append(ConfiguredDetector(cls(options, settings), float(options.get("weight", 1.0))))

    combine = config.get("combine", {})
    return ScannerSetup(
        detectors=tuple(built),
        combine=CombineConfig(
            min_conclusive_weight=float(combine.get("min_conclusive_weight", 1.0)),
            ai_threshold=float(combine.get("ai_threshold", 0.65)),
            real_threshold=float(combine.get("real_threshold", 0.35)),
        ),
    )
