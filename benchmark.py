import time
import statistics

from limiters.token_bucket import TokenBucket
from limiters.sliding_window_log import SlidingWindowLog
from limiters.sliding_window_counter import SlidingWindowCounter

# ---------------------------------------------------------------------
# Shared settings so all three algorithms are configured to allow
# roughly the same steady-state rate: ~10 requests/sec.
# ---------------------------------------------------------------------
LIMIT = 10
WINDOW_SECONDS = 1
REFILL_RATE = 10


def make_limiters():
    """Returns a fresh dict of {name: limiter_instance} for a clean test run."""
    return {
        "token_bucket": TokenBucket(capacity=LIMIT, refill_rate=REFILL_RATE),
        "sliding_window_log": SlidingWindowLog(limit=LIMIT, window_seconds=WINDOW_SECONDS),
        "sliding_window_counter": SlidingWindowCounter(limit=LIMIT, window_seconds=WINDOW_SECONDS),
    }


# ---------------------------------------------------------------------
# TEST 1: Raw throughput — how many allow_request() calls/sec can each
# algorithm sustain, with no artificial delay between calls?
# This measures computational overhead, not correctness.
# ---------------------------------------------------------------------
def benchmark_throughput(num_calls: int = 100_000):
    print("\n=== Throughput Benchmark (raw speed) ===")
    limiters = make_limiters()

    results = {}
    for name, limiter in limiters.items():
        start = time.perf_counter()
        for _ in range(num_calls):
            limiter.allow_request()
        elapsed = time.perf_counter() - start

        calls_per_sec = num_calls / elapsed
        results[name] = calls_per_sec
        print(f"{name:25s}: {calls_per_sec:,.0f} calls/sec  ({elapsed:.3f}s for {num_calls:,} calls)")

    return results

def benchmark_throughput_high_limit(num_calls: int = 100_000, high_limit: int = 10_000):
    """
    Same as benchmark_throughput, but with a much larger limit/capacity,
    so Sliding Window Log's deque can grow large -- this should reveal
    its cost scaling with traffic volume, unlike the other two algorithms
    whose cost stays constant regardless of limit size.
    """
    print(f"\n=== Throughput Benchmark (high limit = {high_limit}) ===")
    limiters = {
        "token_bucket": TokenBucket(capacity=high_limit, refill_rate=high_limit),
        "sliding_window_log": SlidingWindowLog(limit=high_limit, window_seconds=1),
        "sliding_window_counter": SlidingWindowCounter(limit=high_limit, window_seconds=1),
    }

    results = {}
    for name, limiter in limiters.items():
        start = time.perf_counter()
        for _ in range(num_calls):
            limiter.allow_request()
        elapsed = time.perf_counter() - start

        calls_per_sec = num_calls / elapsed
        results[name] = calls_per_sec
        print(f"{name:25s}: {calls_per_sec:,.0f} calls/sec  ({elapsed:.3f}s for {num_calls:,} calls)")

    return results

def benchmark_sustained_load_eviction(duration_seconds: float = 2.0, limit: int = 1000):
    """
    Sends requests continuously over a real time window (not instantly),
    so Sliding Window Log actually has to evict expired timestamps while
    accepting new ones. This is the scenario that should reveal its true
    per-call cost under sustained load, unlike the earlier instant-burst
    throughput tests where no time passed and eviction never triggered.
    """
    print(f"\n=== Sustained Load Benchmark (eviction stress, {duration_seconds}s, limit={limit}) ===")
    limiters = {
        "token_bucket": TokenBucket(capacity=limit, refill_rate=limit),
        "sliding_window_log": SlidingWindowLog(limit=limit, window_seconds=0.5),
        "sliding_window_counter": SlidingWindowCounter(limit=limit, window_seconds=0.5),
    }

    # No sleep between calls -- we want to hammer each limiter as fast as
    # possible for a fixed WALL-CLOCK duration, so the window naturally
    # rolls over multiple times during the test, forcing real eviction.
    results = {}
    for name, limiter in limiters.items():
        call_count = 0
        start = time.perf_counter()
        while time.perf_counter() - start < duration_seconds:
            limiter.allow_request()
            call_count += 1
        elapsed = time.perf_counter() - start

        calls_per_sec = call_count / elapsed
        results[name] = calls_per_sec
        print(f"{name:25s}: {calls_per_sec:,.0f} calls/sec  ({call_count:,} calls in {elapsed:.3f}s)")

    return results


# ---------------------------------------------------------------------
# TEST 2: Accuracy under steady traffic.
# We send requests at a fixed rate for N seconds and count how many
# were ALLOWED. If the limiter is correctly enforcing ~10 req/sec,
# the allowed count should be close to (duration * 10).
# ---------------------------------------------------------------------
def benchmark_steady_traffic(duration_seconds: float = 3.0, requests_per_sec: float = 15):
    print(f"\n=== Steady Traffic Benchmark ({requests_per_sec} req/sec for {duration_seconds}s) ===")
    limiters = make_limiters()
    delay = 1.0 / requests_per_sec

    results = {}
    for name, limiter in limiters.items():
        allowed = 0
        total = 0
        start = time.perf_counter()

        while time.perf_counter() - start < duration_seconds:
            if limiter.allow_request():
                allowed += 1
            total += 1
            time.sleep(delay)

        expected_allowed = duration_seconds * LIMIT
        results[name] = {"allowed": allowed, "total": total}
        print(
            f"{name:25s}: allowed {allowed}/{total} requests "
            f"(expected ~{expected_allowed:.0f} if limit enforced correctly)"
        )

    return results


# ---------------------------------------------------------------------
# TEST 3: Accuracy under bursty traffic.
# Fire a burst of requests instantly, then go quiet, repeat.
# This is where Token Bucket's burst-friendliness and Sliding Window
# Counter's approximation error should become visible.
# ---------------------------------------------------------------------
def benchmark_bursty_traffic(num_bursts: int = 3, burst_size: int = 20, quiet_seconds: float = 1.0):
    print(f"\n=== Bursty Traffic Benchmark ({num_bursts} bursts of {burst_size}, {quiet_seconds}s apart) ===")
    limiters = make_limiters()

    results = {}
    for name, limiter in limiters.items():
        allowed = 0
        total = 0

        for burst_num in range(num_bursts):
            for _ in range(burst_size):
                if limiter.allow_request():
                    allowed += 1
                total += 1
            time.sleep(quiet_seconds)

        results[name] = {"allowed": allowed, "total": total}
        print(f"{name:25s}: allowed {allowed}/{total} requests across all bursts")

    return results

import sys

def benchmark_memory_usage(limit: int = 1000):
    """
    Measures memory footprint after filling each limiter to capacity.
    Token Bucket and Sliding Window Counter should use a small, FIXED
    amount of memory regardless of limit size (just a few numbers).
    Sliding Window Log's memory should scale with the limit, since it
    stores one timestamp per allowed request.
    """
    print(f"\n=== Memory Usage Benchmark (limit={limit}) ===")
    limiters = {
        "token_bucket": TokenBucket(capacity=limit, refill_rate=limit),
        "sliding_window_log": SlidingWindowLog(limit=limit, window_seconds=60),
        "sliding_window_counter": SlidingWindowCounter(limit=limit, window_seconds=60),
    }

    results = {}
    for name, limiter in limiters.items():
        # Fill it up to capacity so we're measuring "worst case" memory
        for _ in range(limit):
            limiter.allow_request()

        size_bytes = sys.getsizeof(limiter.__dict__)
        # For sliding_window_log, also measure the deque itself,
        # since __dict__ only holds a reference to it, not its contents
        if hasattr(limiter, "log"):
            size_bytes += sys.getsizeof(limiter.log)
            size_bytes += sum(sys.getsizeof(item) for item in limiter.log)

        results[name] = size_bytes
        print(f"{name:25s}: {size_bytes:,} bytes (after {limit:,} requests)")

    return results


if __name__ == "__main__":
    throughput_results = benchmark_throughput()
    throughput_high_limit_results = benchmark_throughput_high_limit()
    sustained_load_results = benchmark_sustained_load_eviction()
    memory_results = benchmark_memory_usage()
    steady_results = benchmark_steady_traffic()
    bursty_results = benchmark_bursty_traffic()

    print("\n=== Summary ===")
    print("Throughput (calls/sec):", throughput_results)
    print("Throughput high-limit (calls/sec):", throughput_high_limit_results)
    print("Sustained load (calls/sec):", sustained_load_results)
    print("Memory usage (bytes):", memory_results)
    print("Steady traffic (allowed/total):", steady_results)
    print("Bursty traffic (allowed/total):", bursty_results)