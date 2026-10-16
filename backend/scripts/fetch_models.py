"""Download the optional face-finder model used by the face-swap detector.

    python -m scripts.fetch_models

Only needed if you enable [detectors.face_swap] in app/scanner/scanner.toml.
The file is checked against a pinned SHA-256 before it's saved, so a
tampered or corrupted download is rejected instead of being loaded.
This fetches a *model*; it never uploads anything.
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

from app.config import BACKEND_DIR

MODELS_DIR = BACKEND_DIR / "models"

# YuNet face detector, MIT licence, from the OpenCV model zoo.
YUNET_URL = (
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
YUNET_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
YUNET_FILE = "face_detection_yunet_2023mar.onnx"
MAX_BYTES = 5 * 1024 * 1024


def fetch(url: str, sha256: str, target: Path) -> None:
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == sha256:
        print(f"{target.name}: already present")
        return
    if not url.startswith("https://"):
        raise ValueError("models are only downloaded over HTTPS")
    # Bandit B310 warns about urlopen with arbitrary schemes; this is a fixed
    # HTTPS URL (checked above) and the bytes are hash-verified below.
    with urllib.request.urlopen(url, timeout=60) as response:  # nosec B310
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("download is larger than expected")
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise ValueError(f"checksum mismatch for {target.name}: got {digest}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    print(f"{target.name}: downloaded and verified")


def main() -> int:
    fetch(YUNET_URL, YUNET_SHA256, MODELS_DIR / YUNET_FILE)
    print("Face-swap classifier: not downloaded. Put your own ONNX model at DEEPFAKE_MODEL_PATH (see README).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
