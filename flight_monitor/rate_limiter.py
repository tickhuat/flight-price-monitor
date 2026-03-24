from __future__ import annotations

import time
import threading


class RateLimiter:
    """Simple token-bucket rate limiter. Thread-safe."""

    def __init__(self, calls_per_second: float = 5.0):
        self.min_interval = 1.0 / calls_per_second
        self._last_call: float = 0.0
        self._lock = threading.Lock()

    def wait(self):
        """Block until we can make the next call."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_call = time.monotonic()
