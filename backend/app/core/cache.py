"""
Redis caching service for route optimization.

Provides caching for:
- Distance matrices (OSRM responses)
- Reference data (agents, vehicles, clients)
- Optimization results
"""

import hashlib
import json
from datetime import timedelta
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union

from app.core.config import settings

T = TypeVar("T")


class CacheService:
    """
    Redis-based caching service with support for:
    - Key-value caching with TTL
    - Function result caching (decorator)
    - Cache invalidation patterns
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
                return None
        return self._redis

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        redis = await self.get_redis()
        if redis is None:
            return None

        try:
            value = await redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception:
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Union[int, timedelta] = 300,
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time to live in seconds or timedelta

        Returns:
            True if successful, False otherwise
        """
        redis = await self.get_redis()
        if redis is None:
            return False

        try:
            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())

            serialized = json.dumps(value, default=str)
            await redis.setex(key, ttl, serialized)
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        redis = await self.get_redis()
        if redis is None:
            return False

        try:
            await redis.delete(key)
            return True
        except Exception:
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.

        Args:
            pattern: Redis key pattern (e.g., "matrix:*")

        Returns:
            Number of deleted keys
        """
        redis = await self.get_redis()
        if redis is None:
            return 0

        try:
            keys = []
            async for key in redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                await redis.delete(*keys)
            return len(keys)
        except Exception:
            return 0

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        redis = await self.get_redis()
        if redis is None:
            return False

        try:
            return await redis.exists(key) > 0
        except Exception:
            return False

    # R10: Redis Pipeline Operations for batch efficiency
    async def mget(self, keys: list[str]) -> list[Optional[Any]]:
        """
        Batch get multiple keys using pipeline.

        Performance: O(1) network round trip vs O(n) for individual gets.

        Args:
            keys: List of cache keys to retrieve

        Returns:
            List of values (None for missing keys)
        """
        if not keys:
            return []

        redis = await self.get_redis()
        if redis is None:
            return [None] * len(keys)

        try:
            async with redis.pipeline() as pipe:
                for key in keys:
                    pipe.get(key)
                results = await pipe.execute()

            return [json.loads(r) if r else None for r in results]
        except Exception:
            return [None] * len(keys)

    async def mset(
        self,
        items: dict[str, Any],
        ttl: Union[int, timedelta] = 3600,
    ) -> bool:
        """
        Batch set multiple keys using pipeline.

        Performance: O(1) network round trip vs O(n) for individual sets.

        Args:
            items: Dict of key -> value to cache
            ttl: Time to live in seconds or timedelta

        Returns:
            True if successful
        """
        if not items:
            return True

        redis = await self.get_redis()
        if redis is None:
            return False

        try:
            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())

            async with redis.pipeline() as pipe:
                for key, value in items.items():
                    serialized = json.dumps(value, default=str)
                    pipe.setex(key, ttl, serialized)
                await pipe.execute()

            return True
        except Exception:
            return False

    async def mdelete(self, keys: list[str]) -> int:
        """
        Batch delete multiple keys.

        Args:
            keys: List of keys to delete

        Returns:
            Number of keys deleted
        """
        if not keys:
            return 0

        redis = await self.get_redis()
        if redis is None:
            return 0

        try:
            return await redis.delete(*keys)
        except Exception:
            return 0

    async def ttl(self, key: str) -> Optional[int]:
        """Get remaining TTL of a key."""
        redis = await self.get_redis()
        if redis is None:
            return None

        try:
            return await redis.ttl(key)
        except Exception:
            return None

    @staticmethod
    def make_key(*args, prefix: str = "cache") -> str:
        """
        Generate cache key from arguments.

        Args:
            *args: Values to include in key
            prefix: Key prefix

        Returns:
            Cache key string
        """
        data = json.dumps(args, sort_keys=True, default=str)
        hash_val = hashlib.md5(data.encode()).hexdigest()[:16]
        return f"{prefix}:{hash_val}"

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


# Global cache instance
cache = CacheService()


class DistanceMatrixCache:
    """
    Specialized cache for OSRM distance matrices.

    Matrices are cached for 24 hours by default since
    road networks don't change frequently.
    """

    def __init__(
        self,
        cache_service: CacheService = None,
        default_ttl: int = 86400,  # 24 hours
    ):
        self.cache = cache_service or cache
        self.ttl = default_ttl
        self.prefix = "matrix"

    def _make_key(self, coordinates: list[tuple[float, float]]) -> str:
        """Generate cache key for coordinate set."""
        # Round coordinates to 5 decimal places (~1m precision)
        rounded = [(round(lat, 5), round(lon, 5)) for lat, lon in coordinates]
        data = json.dumps(rounded, sort_keys=True)
        hash_val = hashlib.md5(data.encode()).hexdigest()
        return f"{self.prefix}:{hash_val}"

    async def get(
        self,
        coordinates: list[tuple[float, float]],
    ) -> Optional[dict]:
        """Get cached distance matrix."""
        key = self._make_key(coordinates)
        return await self.cache.get(key)

    async def set(
        self,
        coordinates: list[tuple[float, float]],
        matrix: dict,
        ttl: int = None,
    ) -> bool:
        """Cache distance matrix."""
        key = self._make_key(coordinates)
        return await self.cache.set(key, matrix, ttl or self.ttl)

    async def invalidate_region(self, region: str) -> int:
        """
        Invalidate all cached matrices for a region.

        Used when road data is updated.
        """
        pattern = f"{self.prefix}:*"
        return await self.cache.delete_pattern(pattern)


class ReferenceDataCache:
    """
    Cache for reference data (agents, vehicles, clients).

    Shorter TTL (5 minutes) since this data may change more frequently.
    """

    def __init__(
        self,
        cache_service: CacheService = None,
        default_ttl: int = 300,  # 5 minutes
    ):
        self.cache = cache_service or cache
        self.ttl = default_ttl

    async def get_agent(self, agent_id: str) -> Optional[dict]:
        """Get cached agent data."""
        return await self.cache.get(f"agent:{agent_id}")

    async def set_agent(self, agent_id: str, data: dict) -> bool:
        """Cache agent data."""
        return await self.cache.set(f"agent:{agent_id}", data, self.ttl)

    async def invalidate_agent(self, agent_id: str) -> bool:
        """Invalidate agent cache."""
        return await self.cache.delete(f"agent:{agent_id}")

    async def get_vehicle(self, vehicle_id: str) -> Optional[dict]:
        """Get cached vehicle data."""
        return await self.cache.get(f"vehicle:{vehicle_id}")

    async def set_vehicle(self, vehicle_id: str, data: dict) -> bool:
        """Cache vehicle data."""
        return await self.cache.set(f"vehicle:{vehicle_id}", data, self.ttl)

    async def get_clients(self, agent_id: str) -> Optional[list]:
        """Get cached client list for an agent."""
        return await self.cache.get(f"clients:{agent_id}")

    async def set_clients(self, agent_id: str, data: list) -> bool:
        """Cache client list for an agent."""
        return await self.cache.set(f"clients:{agent_id}", data, self.ttl)


# Global specialized cache instances
distance_matrix_cache = DistanceMatrixCache()
reference_data_cache = ReferenceDataCache()


def cached(
    prefix: str,
    ttl: int = 300,
    key_builder: Callable[..., str] = None,
):
    """
    Decorator for caching async function results.

    Usage:
        @cached("my_function", ttl=600)
        async def my_expensive_function(arg1, arg2):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = cache.make_key(*args, **kwargs, prefix=prefix)

            # Try cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            await cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator
