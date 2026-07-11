import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from limiters.token_bucket import TokenBucket
from limiters.sliding_window_log import SlidingWindowLog
from limiters.sliding_window_counter import SlidingWindowCounter

# ---------------------------------------------------------------------
# CONFIG: change ALGORITHM to switch which limiter the whole app uses.
# Options: "token_bucket", "sliding_window_log", "sliding_window_counter"
# ---------------------------------------------------------------------
ALGORITHM = "token_bucket"

# Shared settings, expressed consistently across algorithms:
# roughly "5 requests per second, with some burst allowance"
LIMIT = 5              # max requests per window / bucket capacity
WINDOW_SECONDS = 1      # window size (used by the two sliding-window algos)
REFILL_RATE = 5        # tokens per second (used by token bucket only)

app = FastAPI()

# This dictionary holds one limiter instance PER CLIENT.
# Key = client identifier (we'll use IP address), Value = limiter instance.
client_limiters: dict[str, object] = {}


def create_limiter():
    """Factory function: creates a fresh limiter instance based on config."""
    if ALGORITHM == "token_bucket":
        return TokenBucket(capacity=LIMIT, refill_rate=REFILL_RATE)
    elif ALGORITHM == "sliding_window_log":
        return SlidingWindowLog(limit=LIMIT, window_seconds=WINDOW_SECONDS)
    elif ALGORITHM == "sliding_window_counter":
        return SlidingWindowCounter(limit=LIMIT, window_seconds=WINDOW_SECONDS)
    else:
        raise ValueError(f"Unknown ALGORITHM: {ALGORITHM}")


def get_client_id(request: Request) -> str:
    """
    Identifies the client. In production this might be an API key or
    authenticated user ID; we use IP address here for simplicity.
    """
    return request.client.host


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_id = get_client_id(request)

    # Lazily create a limiter for this client the first time we see them
    if client_id not in client_limiters:
        client_limiters[client_id] = create_limiter()

    limiter = client_limiters[client_id]

    if limiter.allow_request():
        response = await call_next(request)
        return response
    else:
        return JSONResponse(
            status_code=429,
            content={
                "error": "Too Many Requests",
                "detail": f"Rate limit exceeded using algorithm: {ALGORITHM}",
            },
        )


@app.get("/")
def read_root():
    return {"message": "Hello! This request was allowed by the rate limiter."}


@app.get("/status")
def status():
    """A cheap endpoint to see how many distinct clients are being tracked."""
    return {"algorithm": ALGORITHM, "tracked_clients": len(client_limiters)}