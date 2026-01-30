"""
Rate limiting middleware using Redis.

Implements sliding window rate limiting per API client.
"""

import time

from fastapi import HTTPException, Request, status

from app.core.config import settings


class RateLimiter:
    """
    Redis-based rate limiter using sliding window algorithm.

    Each client gets their own rate limit bucket in Redis.
    """

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis = None

    async def get_redis(self):
        """Lazy initialization of Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as redis

                self._redis = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
            except ImportError:
                # Redis not available, skip rate limiting
                return None
        return self._redis

    async def is_rate_limited(
        self,
        client_id: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, dict]:
        """
        Check if client is rate limited.

        Uses sliding window algorithm:
        - Key: rate_limit:{client_id}
        - Value: sorted set of request timestamps

        Args:
            client_id: Unique client identifier
            limit: Maximum requests per window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_limited, info_dict)
        """
        redis = await self.get_redis()
        if redis is None:
            # Redis not available, don't rate limit
            return False, {"remaining": limit, "reset": 0}

        key = f"rate_limit:{client_id}"
        now = time.time()
        window_start = now - window_seconds

        try:
            # Start pipeline
            pipe = redis.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current requests in window
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(now): now})

            # Set expiry on key
            pipe.expire(key, window_seconds + 1)

            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1]

            remaining = max(0, limit - current_count - 1)
            reset_time = int(now + window_seconds)

            info = {
                "limit": limit,
                "remaining": remaining,
                "reset": reset_time,
                "window": window_seconds,
            }

            if current_count >= limit:
                return True, info

            return False, info

        except Exception as e:
            # On Redis error, allow request but log
            print(f"Rate limiter error: {e}")
            return False, {"remaining": limit, "reset": 0}

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()


# Global rate limiter instance
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware.

    Checks rate limit based on API client if authenticated,
    otherwise uses IP address.
    """
    # Get client identifier
    client_id = None
    limit = 10  # Default for unauthenticated requests

    # Check if request has API client (set by auth dependency)
    if hasattr(request.state, "api_client"):
        client = request.state.api_client
        client_id = str(client.id)
        limit = client.rate_limit_per_minute
    else:
        # Use IP address for unauthenticated requests
        client_id = f"ip:{request.client.host}"

    # Check rate limit
    is_limited, info = await rate_limiter.is_rate_limited(
        client_id=client_id,
        limit=limit,
        window_seconds=60,
    )

    # Add rate limit headers
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(info.get("limit", limit))
    response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
    response.headers["X-RateLimit-Reset"] = str(info.get("reset", 0))

    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Limit: {limit} requests per minute.",
            headers={
                "Retry-After": str(info.get("reset", 60) - int(time.time())),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(info.get("reset", 0)),
            },
        )

    return response


def create_rate_limit_dependency(requests_per_minute: int = None):
    """
    Create a rate limit dependency with custom limit.

    Usage:
        @router.post("/heavy-operation")
        async def heavy_operation(
            _: None = Depends(create_rate_limit_dependency(5))  # 5 req/min
        ):
            ...
    """

    async def rate_limit_check(request: Request):
        client_id = None
        limit = requests_per_minute or 10

        if hasattr(request.state, "api_client"):
            client = request.state.api_client
            client_id = str(client.id)
            if requests_per_minute is None:
                limit = client.rate_limit_per_minute
        else:
            client_id = f"ip:{request.client.host}"

        is_limited, info = await rate_limiter.is_rate_limited(
            client_id=client_id,
            limit=limit,
            window_seconds=60,
        )

        if is_limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Limit: {limit} requests per minute.",
                headers={"Retry-After": str(60)},
            )

    return rate_limit_check
