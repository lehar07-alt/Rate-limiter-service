import time
import sys
import os

# Allows importing from the limiters/ folder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from limiters.token_bucket import TokenBucket


def test_allows_burst_up_to_capacity():
    bucket = TokenBucket(capacity=5, refill_rate=1)
    # Bucket starts full, so first 5 requests should all succeed
    for _ in range(5):
        assert bucket.allow_request() is True
    # The 6th should fail — bucket is empty
    assert bucket.allow_request() is False


def test_refills_over_time():
    bucket = TokenBucket(capacity=2, refill_rate=2)  # refills 2 tokens/sec
    assert bucket.allow_request() is True
    assert bucket.allow_request() is True
    assert bucket.allow_request() is False  # empty now

    time.sleep(0.6)  # ~0.6 sec * 2 tokens/sec = ~1.2 tokens refilled

    assert bucket.allow_request() is True  # should have at least 1 token now


def test_does_not_exceed_capacity():
    bucket = TokenBucket(capacity=3, refill_rate=100)  # fast refill
    time.sleep(0.5)  # would add way more than capacity if uncapped
    # Bucket should still cap at 3, so only 3 requests succeed
    assert bucket.allow_request() is True
    assert bucket.allow_request() is True
    assert bucket.allow_request() is True
    assert bucket.allow_request() is False