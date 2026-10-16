"""Combining detector results into one score and verdict.

The weighted average
--------------------
Each detector i returns a score s_i (0 = looks real, 1 = looks AI-made) and a
confidence c_i (0..1). Its weight w_i comes from scanner.toml. The overall
score is

    overall = sum(w_i * c_i * s_i) / sum(w_i * c_i)

Multiplying by the weight lets strong kinds of evidence count for more:
provenance data (C2PA, metadata) states where a file came from, while pixel
statistics are only hints. Multiplying by the confidence lets a detector say
"I measured something, but don't lean on it much", for example a noise check
on a heavily compressed file. Detectors with no score (nothing found) are
left out entirely rather than counted as 0.5, so "no metadata" doesn't drag
the result towards the middle.

Decisive evidence
-----------------
A cryptographically signed C2PA manifest that says "created by a generative
AI model" is a statement from the tool that made the file, not a statistical
guess. A weighted average would let several weak pixel checks water it down,
so a decisive result sets the floor of the overall score instead.

When we refuse to give a number
-------------------------------
A middle score usually just means "no idea", and showing "52% AI" makes it
look like a measurement. So the verdict is "Inconclusive", and no score is
shown, when:
  * no detector produced a conclusive result, or
  * the conclusive evidence adds up to less than min_conclusive_weight, or
  * the overall score lands between the real and AI thresholds.
"""

from dataclasses import dataclass

from app.scanner.base import DetectorResult

VERDICT_AI = "likely_ai"
VERDICT_REAL = "likely_real"
VERDICT_INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class CombineConfig:
    min_conclusive_weight: float = 1.0
    ai_threshold: float = 0.65
    real_threshold: float = 0.35


@dataclass(frozen=True)
class Combined:
    verdict: str
    score: float | None  # None whenever the verdict is inconclusive


def combine(results: list[tuple[float, DetectorResult]], config: CombineConfig) -> Combined:
    """`results` pairs each detector's configured weight with its result."""
    scored = [(w, r) for w, r in results if r.score is not None and r.status == "ok" and w > 0]

    total = sum(w * r.confidence for w, r in scored)
    if total <= 0:
        return Combined(VERDICT_INCONCLUSIVE, None)
    overall = sum(w * r.confidence * r.score for w, r in scored) / total

    decisive = [r.score for _, r in scored if r.decisive]
    if decisive:
        overall = max(overall, max(decisive))

    conclusive_weight = sum(w * r.confidence for w, r in scored if r.conclusive)
    if not decisive and conclusive_weight < config.min_conclusive_weight:
        return Combined(VERDICT_INCONCLUSIVE, None)
    if overall >= config.ai_threshold:
        return Combined(VERDICT_AI, overall)
    if overall <= config.real_threshold:
        return Combined(VERDICT_REAL, overall)
    return Combined(VERDICT_INCONCLUSIVE, None)
