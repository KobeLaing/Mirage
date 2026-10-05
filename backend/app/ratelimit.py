"""Per-user rate limiting (SR-12).

InMemoryRateLimiter is correct for one process. Running several API instances
means swapping in a shared implementation (e.g. Redis) of the same protocol.
"""

import threading
import time
from collections import defaultdict, deque
from typing import Callable, Protocol


class RateLimiter(Protocol):
    def hit(self, key: str, limit: int, window_seconds: float) -> float | None:
        """Record one action. Return None if allowed, else seconds until retry."""


class InMemoryRateLimiter:
    """Sliding-window log: remembers the timestamps of recent actions per key."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: float) -> float | None:
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return hits[0] + window_seconds - now
            hits.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
