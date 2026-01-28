"""
Redis client for caching.
"""
import hashlib
import json
from typing import Any, Optional

import redis.asyncio as redis

from app.core.config import settings


class RedisClient:
    """Async Redis client with caching utilities."""

    def __init__(self, url: Optional[str] = None):
        self.url = url or settings.REDIS_URL
        self._client: Optional[redis.Redis] = None

    async def get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        client = await self.get_client()
        return await client.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Set value in cache with optional TTL."""
        client = await self.get_client()
        if ttl_seconds:
            await client.setex(key, ttl_seconds, value)
        else:
            await client.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        client = await self.get_client()
        await client.delete(key)

    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value from cache."""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Set JSON value in cache."""
        await self.set(key, json.dumps(value), ttl_seconds)

    async def health_check(self) -> bool:
        """Check if Redis is available."""
        try:
            client = await self.get_client()
            await client.ping()
            return True
        except Exception:
            return False

    @staticmethod
    def hash_key(*args: Any) -> str:
        """Generate a hash key from arguments."""
        key_data = json.dumps(args, sort_keys=True, default=str)
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]


# Cache TTL constants (in seconds)
class CacheTTL:
    """Cache TTL constants."""
    OSRM_MATRIX = 7 * 24 * 60 * 60  # 7 days
    OSRM_ROUTE = 24 * 60 * 60  # 1 day
    WEEKLY_PLAN = 60 * 60  # 1 hour
    SHORT = 5 * 60  # 5 minutes


# Singleton instance
redis_client = RedisClient()
