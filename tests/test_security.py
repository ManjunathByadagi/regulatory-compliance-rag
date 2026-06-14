import pytest
from fastapi import HTTPException

from app.api.security import RateLimiter


def test_rate_limiter_blocks_after_limit() -> None:
    limiter = RateLimiter(2)
    key = "k"
    limiter.check(key)
    limiter.check(key)
    with pytest.raises(HTTPException):
        limiter.check(key)
