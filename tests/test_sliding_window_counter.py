import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from limiters.sliding_window_counter import SlidingWindowCounter


def test_allows_up_to_limit_within_one_window():
    limiter = SlidingWindowCounter(limit=3, window_seconds=1)
    assert limiter.allow_request() is True
    assert limiter.allow_request() is True
    assert limiter.allow_request() is True
    assert limiter.allow_request() is False


def test_resets_after_full_window_passes_with_no_traffic():
    limiter = SlidingWindowCounter(limit=2, window_seconds=0.5)
    assert limiter.allow_request() is True
    assert limiter.allow_request() is True
    assert limiter.allow_request() is False

    time.sleep(1.2)  # let more than 2 whole windows pass with no traffic

    # previous window should now be considered empty/stale, current window fresh
    assert limiter.allow_request() is True


def test_gradual_weighting_reduces_previous_windows_influence():
    limiter = SlidingWindowCounter(limit=10, window_seconds=0.4)

    # Fill up the first window completely
    for _ in range(10):
        assert limiter.allow_request() is True
    assert limiter.allow_request() is False

    # Wait until we're most of the way through the NEXT window,
    # so previous window's weight/overlap is small
    time.sleep(0.75)

    # Previous window's 10 requests should now barely count,
    # so new requests should be allowed again
    assert limiter.allow_request() is True