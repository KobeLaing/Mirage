"""Container metadata check, for videos (MP4).

An MP4 file is a tree of "boxes". Alongside the video data, the moov/udta/
meta boxes hold tags written by whatever produced the file: the encoder name
(the ©too tag), the phone make and model, and sometimes the generating
service. We read those boxes (never the huge video data box, mdat) and look
for:
- AI generator names (Sora, Runway, ...): strong evidence of AI.
- Phone camera tags (Apple's com.apple.quicktime.make, Android's
  com.android.version): leans real, though tags can be copied.
- A plain re-encoder such as FFmpeg ("Lavf"): neutral. It only means the
  file was converted, which strips the original tags.

C2PA data inside the video is handled by the C2PA detector, which also runs
on videos.
"""

import re
from pathlib import Path

from app.scanner.base import Detector, DetectorResult, MediaInput
from app.scanner.fingerprints import find_generators

MAX_METADATA_BYTES = 8 * 1024 * 1024
_PRINTABLE = re.compile(rb"[\x20-\x7e]{4,}")
_ENCODER = re.compile(rb"\xa9too.{4}data.{8}([\x20-\x7e]{1,100})", re.DOTALL)


def read_metadata_boxes(path: Path) -> bytes:
    """Bytes of every top-level box except the media data, capped in size."""
    chunks: list[bytes] = []
    remaining = MAX_METADATA_BYTES
    size_total = path.stat().st_size
    with path.open("rb") as f:
        offset = 0
        while offset + 8 <= size_total and remaining > 0:
            f.seek(offset)
            header = f.read(8)
            size, kind = int.from_bytes(header[:4], "big"), header[4:8]
            header_len = 8
            if size == 1:
                size, header_len = int.from_bytes(f.read(8), "big"), 16
            elif size == 0:
                size = size_total - offset
            if size < header_len:
                break  # malformed; upload validation already rejects most of these
            if kind not in (b"mdat", b"free", b"skip"):
                chunk = f.read(min(size - header_len, remaining))
                chunks.append(chunk)
                remaining -= len(chunk)
            offset += size
    return b"".join(chunks)


class VideoContainerDetector(Detector):
    name = "video_container"
    label = "Container metadata"
    media_types = frozenset({"video"})

    def analyze(self, media: MediaInput) -> DetectorResult:
        raw = read_metadata_boxes(media.path)
        text = "\n".join(s.decode("ascii") for s in _PRINTABLE.findall(raw))
        encoder_match = _ENCODER.search(raw)
        encoder = encoder_match.group(1).decode("ascii").strip() if encoder_match else ""

        generators = find_generators(text)
        if generators:
            return DetectorResult(
                score=0.95, confidence=0.9, conclusive=True,
                explanation=f"The video's metadata names an AI generator: {', '.join(generators[:3])}.",
            )
        if "com.apple.quicktime.make" in text or "com.android.version" in text:
            device = "an iPhone or other Apple device" if "com.apple" in text else "an Android phone"
            return DetectorResult(
                score=0.25, confidence=0.6, conclusive=True,
                explanation=f"Recorded-on-device tags from {device} are present, typical of real camera "
                            "footage (though tags can be copied).",
            )
        if encoder.lower().startswith("lavf"):
            return DetectorResult.no_signal(
                f"Re-encoded with FFmpeg ({encoder}), which drops the original tags, so the source can't be told."
            )
        if encoder:
            return DetectorResult.no_signal(f"Encoded with {encoder}; no generator or camera tags found.")
        return DetectorResult.no_signal("No encoder, camera or generator tags in the video's metadata.")
