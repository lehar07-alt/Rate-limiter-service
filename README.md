# Rate Limiter Service

A from-scratch implementation and benchmark comparison of three classic rate-limiting algorithms, wrapped in a FastAPI middleware. Built to understand the real tradeoffs between accuracy, speed, and memory that production systems (Stripe, GitHub, Cloudflare, etc.) navigate every day.

## Algorithms implemented

- **Token Bucket** — a bucket of tokens refills at a fixed rate; each request consumes a token. Allows short bursts while enforcing a long-term average rate.
- **Sliding Window Log** — stores a timestamp per allowed request in a rolling window. Exact enforcement, no approximation, but memory scales with traffic volume.
- **Sliding Window Counter** — approximates a rolling window using two fixed-window counters (current + previous), weighted by overlap. Constant memory, but not perfectly precise.

All three are implemented as standalone, framework-agnostic Python classes in `limiters/`, with unit tests in `tests/`, then wired into a FastAPI app (`app.py`) as per-client middleware.

## Running it

```bash
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install fastapi uvicorn pytest matplotlib

# Run tests
pytest tests/ -v

# Run the API
uvicorn app:app --reload
# then hit http://127.0.0.1:8000/ repeatedly to see 200s turn into 429s

# Run the benchmark suite (prints results + saves graphs to results/)
python benchmark.py
```

Switch which algorithm the API uses by changing `ALGORITHM` in `app.py` (`"token_bucket"`, `"sliding_window_log"`, or `"sliding_window_counter"`).

## Benchmark results

### Throughput (raw calls/sec, no delay)

![Throughput](results/throughput.png)

| Algorithm | Calls/sec |
|---|---|
| Token Bucket | ~1.9M |
| Sliding Window Log | ~2.5M |
| Sliding Window Counter | ~1.7M |

**This surprised me.** I expected Sliding Window Log to be the slowest, since it maintains a growing/shrinking list of timestamps while the other two just track a couple of numbers. It was actually the *fastest*.

The reason: `deque.popleft()` (used to evict expired timestamps) is an O(1) operation — removing one entry costs the same tiny amount of time regardless of how many entries are stored. Even under sustained load with real evictions happening (tested separately below), each request only touches the *few* entries that are actually expired, never the whole list. So Sliding Window Log's speed doesn't degrade with scale — its real cost lives elsewhere.

### Memory usage (bytes, after 1,000 requests)

![Memory](results/memory_usage.png)

| Algorithm | Bytes |
|---|---|
| Token Bucket | 272 |
| Sliding Window Log | 33,480 |
| Sliding Window Counter | 272 |

**This is where the real tradeoff lives.** Token Bucket and Sliding Window Counter use fixed, constant memory no matter how much traffic they've handled — they only ever store a couple of numbers. Sliding Window Log stores one timestamp per request in the current window, so its memory footprint is directly proportional to traffic volume — about **123x more memory** than the other two at this test's limit of 1,000 requests, and it would keep growing at higher limits.

This is the actual, honest engineering tradeoff behind Sliding Window Log's precision: it's exact because it remembers everything, and remembering everything costs memory, not speed.

### Accuracy under bursty traffic

![Bursty accuracy](results/bursty_accuracy.png)

Simulated 3 bursts of 20 requests each, 1 second apart, against a limit of 10 requests/window:

- **Token Bucket** and **Sliding Window Log** both allowed exactly the expected count consistently.
- **Sliding Window Counter** was noticeably more restrictive in most runs (allowing fewer requests than the true limit would technically permit), because its two-window-weighted approximation still partially penalizes a new burst based on the previous window's activity. Its exact result varies slightly run-to-run, since the overlap weighting depends on real wall-clock timing precision between bursts — a good reminder that approximation algorithms are more sensitive to timing jitter than exact ones.

## Key takeaways

1. **Token Bucket** — best default choice for most APIs. Cheap, allows natural bursts, simple to reason about.
2. **Sliding Window Log** — use when you need exact enforcement (e.g. billing-related limits) and can afford the memory cost, or when your traffic volume per window is naturally small.
3. **Sliding Window Counter** — good middle ground when you need low, constant memory *and* reasonably close accuracy, and can tolerate slight approximation error, especially right at window boundaries.

## Project structure

```
rate-limiter-service/
├── limiters/                    # Framework-agnostic algorithm implementations
│   ├── token_bucket.py
│   ├── sliding_window_log.py
│   └── sliding_window_counter.py
├── tests/                       # Unit tests for each algorithm
├── app.py                       # FastAPI app using the limiters as middleware
├── benchmark.py                 # Benchmark suite + graph generation
├── results/                     # Generated benchmark graphs (PNG)
└── README.md
```