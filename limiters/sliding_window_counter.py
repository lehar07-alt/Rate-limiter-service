import time
import threading


class SlidingWindowCounter:
    """
    Sliding Window Counter rate limiter.

    - limit: max requests allowed per window
    - window_seconds: size of each fixed window, in seconds

    Approximates a true sliding window using two fixed-window counters
    (current + previous), weighted by how much the previous window
    overlaps with the current rolling view.
    """

    def __init__(self, limit: int, window_seconds: float):
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")

        self.limit = limit
        self.window_seconds = window_seconds

        self.current_window_start = self._window_start(time.monotonic())
        self.current_count = 0
        self.previous_count = 0

        self.lock = threading.Lock()

    def _window_start(self, now: float) -> float:
        """
        Snaps 'now' down to the start of its fixed window.
        e.g. if window_seconds=60 and now=125, window_start=120.
        """
        return (now // self.window_seconds) * self.window_seconds

    def _advance_window_if_needed(self, now: float):
        """
        Checks whether we've moved into a new fixed window since the
        last request. If so, roll current -> previous, and reset current.
        Handles the case of multiple empty windows passing too.
        """
        now_window_start = self._window_start(now)

        if now_window_start == self.current_window_start:
            return  # still in the same window, nothing to do

        windows_passed = (now_window_start - self.current_window_start) / self.window_seconds

        if windows_passed == 1:
            # Exactly one window boundary crossed: current becomes previous
            self.previous_count = self.current_count
        else:
            # More than one window passed with no requests in between
            # (e.g. traffic went quiet) -> previous window is now empty too
            self.previous_count = 0

        self.current_count = 0
        self.current_window_start = now_window_start

    def allow_request(self) -> bool:
        with self.lock:
            now = time.monotonic()
            self._advance_window_if_needed(now)

            # How far are we into the current window, as a fraction (0.0 to 1.0)?
            elapsed_in_current = now - self.current_window_start
            position_in_window = elapsed_in_current / self.window_seconds

            # The overlap of the previous window with our rolling view
            # shrinks as we move further into the current window.
            overlap_weight = 1 - position_in_window

            estimated_count = self.current_count + (self.previous_count * overlap_weight)

            if estimated_count < self.limit:
                self.current_count += 1
                return True
            else:
                return False