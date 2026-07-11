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


if __name__ == "__main__":
    throughput_results = benchmark_throughput()
    steady_results = benchmark_steady_traffic()
    bursty_results = benchmark_bursty_traffic()

    print("\n=== Summary ===")
    print("Throughput (calls/sec):", throughput_results)
    print("Steady traffic (allowed/total):", steady_results)
    print("Bursty traffic (allowed/total):", bursty_results)