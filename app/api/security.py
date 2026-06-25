from __future__ import annotations

from collections import defaultdict, deque
from time import time

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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

bearer_scheme = HTTPBearer(
    bearerFormat="API key",
    scheme_name="BearerAuth",
    description="Use the configured API key as a bearer token.",
    auto_error=False,
)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)) -> str:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = credentials.credentials.strip()
    if token != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    rate_limiter.check(token)
    return token


def validate_api_key(credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)) -> str:
    return get_current_user(credentials)