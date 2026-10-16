"""The private AI Authenticity Scanner.

A user uploads an image or video that is NOT posted anywhere, and gets back
an estimated probability that it is AI-generated, plus which signals
contributed. The steps:

1. The upload goes through the same validation as posts (type from the file's
   bytes, size limits, decode/structure checks) but is NOT re-encoded,
   because the metadata and compression traces are part of what we analyse.
2. Each enabled detector that supports the media type looks at the file.
   A detector that crashes is reported as an error; the others still run.
3. The results are combined into one score using the weights in
   scanner.toml (see app/scanner/combine.py for how and why).
4. The temporary copy is deleted in a `finally` block, so it's removed even
   if a detector fails. Nothing is written to permanent storage or the database.

Everything runs on this server. Detectors that would send media elsewhere
are kept off by the registry unless explicitly enabled with an API key.
"""

import logging
from typing import BinaryIO

from app.media import pipeline
from app.scanner.base import DetectorResult, MediaInput
from app.scanner.combine import VERDICT_AI, VERDICT_REAL, combine
from app.scanner.registry import ScannerSetup
from app.schemas.scanner import ScanResult, ScanSignal

log = logging.getLogger("mirage.scanner")

VERDICT_LABELS = {
    VERDICT_AI: "Likely AI-generated",
    VERDICT_REAL: "Likely real",
}


def _signal(name: str, label: str, weight: float, result: DetectorResult) -> ScanSignal:
    status = result.status if result.status != "ok" else ("ok" if result.score is not None else "no_signal")
    return ScanSignal(
        detector=name,
        label=label,
        status=status,
        score=round(result.score * 100) if result.score is not None else None,
        conclusive=result.conclusive,
        weight=weight,
        explanation=result.explanation,
    )


def scan(upload: BinaryIO, limits: pipeline.MediaLimits, setup: ScannerSetup) -> ScanResult:
    workdir = pipeline.new_workdir()
    try:
        validated = pipeline.validate(upload, limits, workdir)  # 413 / 415 on bad input
        media = MediaInput(path=validated.path, kind=validated.kind, mime=validated.detected.mime)

        weighted: list[tuple[float, DetectorResult]] = []
        signals: list[ScanSignal] = []
        for configured in setup.detectors:
            detector = configured.detector
            if not detector.supports(media.kind):
                continue
            reason = detector.unavailable_reason()
            if reason:
                result = DetectorResult.unavailable(reason)
            else:
                try:
                    result = detector.analyze(media)
                except Exception:  # one broken detector must not break the whole scan
                    log.exception("scanner.detector_failed", extra={"detector": detector.name})
                    result = DetectorResult(score=None, confidence=0.0, status="error",
                                            explanation="This check failed on this file and was left out.")
            weighted.append((configured.weight, result))
            signals.append(_signal(detector.name, detector.label, configured.weight, result))

        combined = combine(weighted, setup.combine)
    finally:
        pipeline.cleanup(workdir)  # the scanned file is deleted as soon as the scan finishes

    log.info("scanner.scanned", extra={"kind": media.kind, "verdict": combined.verdict})
    return ScanResult(
        media_kind=media.kind,
        verdict=combined.verdict,
        verdict_label=VERDICT_LABELS.get(combined.verdict, "Inconclusive"),
        score=round(combined.score * 100) if combined.score is not None else None,
        signals=signals,
    )
