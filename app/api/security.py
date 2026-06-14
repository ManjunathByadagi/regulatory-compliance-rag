from __future__ import annotations

from collections import defaultdict, deque
from time import time

from fastapi import Header, HTTPException, status

from app.core.config import settings


class RateLimiter:
    def __init__(self, max_per_minute: int) -> None:
        self.max_per_minute = max_per_minute
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time()
        bucket = self.requests[key]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= self.max_per_minute:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Max 100 requests/minute.")
        bucket.append(now)


rate_limiter = RateLimiter(settings.rate_limit_per_minute)


def validate_api_key(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    if token != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    rate_limiter.check(token)
    return token
