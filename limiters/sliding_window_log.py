import time
import threading
from collections import deque


class SlidingWindowLog:
    """
    Sliding Window Log rate limiter.

    - limit: max number of requests allowed within the window
    - window_seconds: size of the rolling time window, in seconds
    """

    def __init__(self, limit: int, window_seconds: float):
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")

        self.limit = limit
        self.window_seconds = window_seconds

        # Stores a timestamp for every allowed request, oldest first.
        self.log = deque()

        self.lock = threading.Lock()

    def _evict_old_entries(self, now: float):
        """Remove timestamps that have fallen outside the current window."""
        cutoff = now - self.window_seconds
        while self.log and self.log[0] <= cutoff:
            self.log.popleft()

    def allow_request(self) -> bool:
        """
        Returns True if the request is allowed (and logs its timestamp),
        False if it should be rejected.
        """
        with self.lock:
            now = time.monotonic()
            self._evict_old_entries(now)

            if len(self.log) < self.limit:
                self.log.append(now)
                return True
            else:
                return False