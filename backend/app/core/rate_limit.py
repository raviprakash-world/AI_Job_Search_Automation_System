import time
from collections import defaultdict
from threading import Lock

from app.core.errors import AppError


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"


class SlidingWindowRateLimiter:
    """In-process, per-key sliding-window limiter. Single-process deployments only."""

    def __init__(self, max_attempts: int, window_seconds: float):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.pop(0)
            if len(hits) >= self.max_attempts:
                raise RateLimitError("Too many attempts. Please try again later.")
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


login_rate_limiter = SlidingWindowRateLimiter(max_attempts=10, window_seconds=300)
register_rate_limiter = SlidingWindowRateLimiter(max_attempts=5, window_seconds=3600)
