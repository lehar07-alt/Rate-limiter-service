import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from limiters.sliding_window_log import SlidingWindowLog


def test_allows_up_to_limit():
    limiter = SlidingWindowLog(limit=3, window_seconds=1)
    assert limiter.allow_request() is True
    assert limiter.allow_request() is True
    assert limiter.allow_request() is True
    # 4th request within the same window should be rejected
    assert limiter.allow_request() is False


def test_old_requests_expire_out_of_window():
    limiter = SlidingWindowLog(limit=2, window_seconds=0.5)
    assert limiter.allow_request() is True
    assert limiter.allow_request() is True
    assert limiter.allow_request() is False  # window full

    time.sleep(0.6)  # both old requests should now be outside the window

    assert limiter.allow_request() is True  # window has room again


def test_partial_expiry():
    limiter = SlidingWindowLog(limit=2, window_seconds=0.5)
    assert limiter.allow_request() is True  # request A at t=0

    time.sleep(0.3)
    assert limiter.allow_request() is True  # request B at t=0.3, both in window

    time.sleep(0.3)  # now t=0.6 -> request A (t=0) should be expired, B (t=0.3) still valid
    assert limiter.allow_request() is True  # only 1 valid entry (B), so this is allowed
    assert limiter.allow_request() is False  # now 2 valid entries, limit hit