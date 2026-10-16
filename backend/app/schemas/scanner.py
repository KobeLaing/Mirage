from typing import Literal

from app.schemas.common import StrictModel

NOTICE = (
    "This score is an estimate, not proof. Detectors can be wrong, "
    "especially on compressed or edited media."
)


class ScanSignal(StrictModel):
    detector: str
    label: str
    # ok = gave a score; no_signal = ran but found nothing to judge by;
    # unavailable = enabled but missing a model; error = failed (scan continued)
    status: Literal["ok", "no_signal", "unavailable", "error"]
    score: int | None  # 0..100, AI likelihood from this detector alone
    conclusive: bool
    weight: float
    explanation: str


class ScanResult(StrictModel):
    media_kind: Literal["image", "video"]
    verdict: Literal["likely_ai", "likely_real", "inconclusive"]
    verdict_label: str
    score: int | None  # 0..100; null whenever the verdict is inconclusive
    signals: list[ScanSignal]
    notice: str = NOTICE
