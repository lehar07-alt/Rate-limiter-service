import time
import threading


class TokenBucket:
    """
    Token Bucket rate limiter.

    - capacity: max number of tokens the bucket can hold (burst limit)
    - refill_rate: tokens added per second (steady-state allowed rate)
    """

    def __init__(self, capacity: float, refill_rate: float):
        if capacity <= 0 or refill_rate <= 0:
            raise ValueError("capacity and refill_rate must be positive")

        self.capacity = capacity
        self.refill_rate = refill_rate

        # Bucket starts full — this allows an initial burst
        self.tokens = capacity

        # Track the last time we refilled, so we can calculate
        # elapsed time on the next request (lazy refill).
        self.last_refill_time = time.monotonic()

        # A lock so this is safe if multiple requests hit it
        # at the same time (thread safety matters for a real server).
        self.lock = threading.Lock()

    def _refill(self):
        """Add tokens based on how much time has passed since last check."""
        now = time.monotonic()
        elapsed = now - self.last_refill_time

        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)

        self.last_refill_time = now

    def allow_request(self, tokens_requested: float = 1) -> bool:
        """
        Returns True if the request is allowed (and consumes a token),
        False if it should be rejected.
        """
        with self.lock:
            self._refill()

            if self.tokens >= tokens_requested:
                self.tokens -= tokens_requested
                return True
            else:
                return False