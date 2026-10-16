"""Face-swap (deepfake) detection, for videos. OFF by default.

How it works: take frames through the video, find faces with the YuNet face
detector, crop each face, and ask a face-swap classifier (any ONNX image
classifier trained on real vs swapped faces, e.g. on FaceForensics++) how
likely each face is to be fake. The score is the average over all faces.

Why it's off by default: no maintained, clearly licensed face-swap model
exists that we could ship with Mirage. Point DEEPFAKE_MODEL_PATH at a model
you trust and enable [detectors.face_swap] in scanner.toml. The model's input
size, normalisation and output layout are set there too, so most ONNX
classifiers work without code changes. Everything runs locally through
OpenCV's DNN module; no frame leaves the server.
"""

from pathlib import Path

import cv2
import numpy as np

from app.config import BACKEND_DIR
from app.scanner.base import Detector, DetectorResult, MediaInput
from app.scanner.frames import sample_frames

MIN_FACE = 48  # pixels; smaller faces don't carry enough detail to judge
MAX_FACES_PER_FRAME = 4


def _resolve(path: str | Path | None) -> Path | None:
    if not path:
        return None
    p = Path(path)
    return p if p.is_absolute() else BACKEND_DIR / p


class FaceSwapDetector(Detector):
    name = "face_swap"
    label = "Face-swap detection"
    media_types = frozenset({"video"})

    def _paths(self) -> tuple[Path | None, Path | None]:
        return _resolve(self.options.get("face_model")), _resolve(self.settings.deepfake_model_path)

    def unavailable_reason(self) -> str | None:
        face_model, classifier = self._paths()
        if classifier is None or not classifier.is_file():
            return "No face-swap model is installed (set DEEPFAKE_MODEL_PATH), so this check was skipped."
        if face_model is None or not face_model.is_file():
            return "The face finder model is missing (run `python -m scripts.fetch_models`)."
        return None

    def _fake_probability(self, net, face: np.ndarray) -> float:
        size = int(self.options.get("input_size", 224))
        rgb = cv2.cvtColor(cv2.resize(face, (size, size)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        mean = np.array(self.options.get("mean", [0.0, 0.0, 0.0]), dtype=np.float32)
        std = np.array(self.options.get("std", [1.0, 1.0, 1.0]), dtype=np.float32)
        blob = ((rgb - mean) / std).transpose(2, 0, 1)[None]  # NCHW
        net.setInput(blob)
        out = np.asarray(net.forward(), dtype=np.float64).ravel()
        activation = self.options.get("activation", "softmax")
        if activation == "softmax":
            exp = np.exp(out - out.max())
            out = exp / exp.sum()
        elif activation == "sigmoid":
            out = 1.0 / (1.0 + np.exp(-out))
        index = int(self.options.get("fake_index", 1))
        return float(np.clip(out[min(index, out.size - 1)], 0.0, 1.0))

    def analyze(self, media: MediaInput) -> DetectorResult:
        face_model, classifier = self._paths()
        net = cv2.dnn.readNetFromONNX(str(classifier))
        finder = cv2.FaceDetectorYN.create(str(face_model), "", (320, 320), score_threshold=0.8)

        probabilities = []
        for frame in sample_frames(media.path, int(self.options.get("frames", 8))):
            h, w = frame.shape[:2]
            finder.setInputSize((w, h))
            _, faces = finder.detect(frame)
            for face in (faces if faces is not None else [])[:MAX_FACES_PER_FRAME]:
                x, y, fw, fh = (int(v) for v in face[:4])
                if fw < MIN_FACE or fh < MIN_FACE:
                    continue
                pad_x, pad_y = fw // 5, fh // 5  # classifiers are trained on faces with some margin
                crop = frame[max(0, y - pad_y): min(h, y + fh + pad_y), max(0, x - pad_x): min(w, x + fw + pad_x)]
                if crop.size:
                    probabilities.append(self._fake_probability(net, crop))

        if not probabilities:
            return DetectorResult.no_signal("No clear faces found in the sampled frames.")
        score = float(np.mean(probabilities))
        clear = len(probabilities) >= 3 and (score >= 0.8 or score <= 0.2)
        return DetectorResult(
            score=score, confidence=0.6, conclusive=clear,
            explanation=f"The face-swap model checked {len(probabilities)} face(s) and rated them "
                        f"{score:.0%} likely to be swapped on average.",
        )
