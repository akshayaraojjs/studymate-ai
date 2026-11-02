"""Small in-process rate limiter for LLM-backed endpoints.

Suitable for a single-instance deployment; swap for Redis when scaling out.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

_LOCK = threading.Lock()
_HITS: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(key: str, limit: int, window_seconds: int = 60) -> None:
    now = time.monotonic()
    with _LOCK:
        hits = _HITS[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = max(1, int(window_seconds - (now - hits[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)
