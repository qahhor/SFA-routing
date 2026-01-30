"""
OSRM (Open Source Routing Machine) client for distance matrix calculation.

Features:
- Redis caching for distance matrices (7 day TTL)
- Exponential backoff retry logic
- Batched matrix calculation for large coordinate sets
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from app.core.config import settings
from app.core.redis import redis_client, CacheTTL

logger = logging.getLogger(__name__)


class OSRMError(Exception):
    """OSRM service error."""

    def __init__(self, message: str, code: Optional[str] = None):
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass
class RouteResult:
    """Result of a route calculation."""
    distance_meters: float
    duration_seconds: float
    geometry: Optional[dict] = None


@dataclass
class MatrixResult:
    """Result of a distance matrix calculation."""
    distances: list[list[float]]  # meters
    durations: list[list[float]]  # seconds


class OSRMClient:
    """
    Client for OSRM routing service.

    OSRM provides fast routing and distance matrix calculations.
    Features Redis caching and exponential backoff retry logic.
    """

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # seconds
    MAX_COORDINATES_PER_REQUEST = 100  # OSRM limit

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.OSRM_URL).rstrip("/")
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    async def _request_with_retry(
        self,
        url: str,
        params: dict,
        operation: str = "request",
    ) -> dict:
        """
        Make HTTP request with exponential backoff retry.

        Args:
            url: Request URL
            params: Query parameters
            operation: Operation name for logging

        Returns:
            JSON response data

        Raises:
            OSRMError: If all retries fail
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    data = response.json()

                if data["code"] != "Ok":
                    raise OSRMError(
                        data.get("message", "Unknown OSRM error"),
                        code=data["code"],
                    )

                return data

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"OSRM {operation} HTTP error (attempt {attempt + 1}/{self.MAX_RETRIES}): "
                    f"{e.response.status_code}"
                )
            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    f"OSRM {operation} network error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}"
                )
            except OSRMError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(
                    f"OSRM {operation} error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}"
                )

            if attempt < self.MAX_RETRIES - 1:
                delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                logger.info(f"Retrying OSRM {operation} in {delay}s...")
                await asyncio.sleep(delay)

        raise OSRMError(
            f"OSRM {operation} failed after {self.MAX_RETRIES} attempts: {last_error}"
        )

    async def get_route(
        self,
        coordinates: list[tuple[float, float]],
        profile: str = "driving",
        geometries: str = "geojson",
        overview: str = "full",
        use_cache: bool = True,
    ) -> RouteResult:
        """
        Get route between coordinates.

        Args:
            coordinates: List of (longitude, latitude) tuples
            profile: Routing profile (driving, walking, cycling)
            geometries: Format for route geometry (geojson, polyline, polyline6)
            overview: Level of detail (full, simplified, false)
            use_cache: Whether to use Redis cache

        Returns:
            RouteResult with distance, duration, and geometry
        """
        # Check cache first
        cache_key = None
        if use_cache:
            cache_key = f"osrm:route:{redis_client.hash_key(coordinates, profile)}"
            cached = await redis_client.get_json(cache_key)
            if cached:
                logger.debug(f"OSRM route cache hit: {cache_key}")
                return RouteResult(**cached)

        coords_str = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
        url = f"{self.base_url}/route/v1/{profile}/{coords_str}"

        params = {
            "geometries": geometries,
            "overview": overview,
            "steps": "false",
        }

        data = await self._request_with_retry(url, params, "route")

        route = data["routes"][0]
        result = RouteResult(
            distance_meters=route["distance"],
            duration_seconds=route["duration"],
            geometry=route.get("geometry"),
        )

        # Cache result
        if cache_key:
            await redis_client.set_json(
                cache_key,
                {
                    "distance_meters": result.distance_meters,
                    "duration_seconds": result.duration_seconds,
                    "geometry": result.geometry,
                },
                CacheTTL.OSRM_ROUTE,
            )
            logger.debug(f"OSRM route cached: {cache_key}")

        return result

    async def get_table(
        self,
        coordinates: list[tuple[float, float]],
        profile: str = "driving",
        sources: Optional[list[int]] = None,
        destinations: Optional[list[int]] = None,
        use_cache: bool = True,
    ) -> MatrixResult:
        """
        Get distance/duration matrix between coordinates.

        Args:
            coordinates: List of (longitude, latitude) tuples
            profile: Routing profile
            sources: Indices of source points (default: all)
            destinations: Indices of destination points (default: all)
            use_cache: Whether to use Redis cache (7 day TTL)

        Returns:
            MatrixResult with distances and durations matrices
        """
        # Check cache first
        cache_key = None
        if use_cache:
            cache_key = f"osrm:table:{redis_client.hash_key(coordinates, profile, sources, destinations)}"
            cached = await redis_client.get_json(cache_key)
            if cached:
                logger.debug(f"OSRM table cache hit: {cache_key}")
                return MatrixResult(**cached)

        coords_str = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
        url = f"{self.base_url}/table/v1/{profile}/{coords_str}"

        params = {
            "annotations": "distance,duration",
        }

        if sources is not None:
            params["sources"] = ";".join(map(str, sources))
        if destinations is not None:
            params["destinations"] = ";".join(map(str, destinations))

        data = await self._request_with_retry(url, params, "table")

        result = MatrixResult(
            distances=data["distances"],
            durations=data["durations"],
        )

        # Cache result
        if cache_key:
            await redis_client.set_json(
                cache_key,
                {"distances": result.distances, "durations": result.durations},
                CacheTTL.OSRM_MATRIX,
            )
            logger.debug(f"OSRM table cached: {cache_key}")

        return result

    async def get_table_batched(
        self,
        coordinates: list[tuple[float, float]],
        profile: str = "driving",
        batch_size: int = 100,
        use_cache: bool = True,
    ) -> MatrixResult:
        """
        Get distance matrix for large coordinate sets using batched requests.

        Splits large coordinate sets into smaller batches to avoid OSRM limits.

        Args:
            coordinates: List of (longitude, latitude) tuples
            profile: Routing profile
            batch_size: Maximum coordinates per batch (default 100)
            use_cache: Whether to use Redis cache

        Returns:
            MatrixResult with combined distances and durations matrices
        """
        n = len(coordinates)

        if n <= batch_size:
            return await self.get_table(coordinates, profile, use_cache=use_cache)

        logger.info(f"Batching OSRM table request: {n} coordinates in batches of {batch_size}")

        # Initialize full matrices
        distances = [[0.0] * n for _ in range(n)]
        durations = [[0.0] * n for _ in range(n)]

        # Process in batches
        for i in range(0, n, batch_size):
            batch_end_i = min(i + batch_size, n)
            for j in range(0, n, batch_size):
                batch_end_j = min(j + batch_size, n)

                # Get coordinates for this batch
                batch_coords = coordinates[i:batch_end_i] + coordinates[j:batch_end_j]
                sources = list(range(batch_end_i - i))
                destinations = list(range(batch_end_i - i, len(batch_coords)))

                # Skip if sources and destinations are the same batch
                if i == j:
                    batch_coords = coordinates[i:batch_end_i]
                    result = await self.get_table(batch_coords, profile, use_cache=use_cache)
                else:
                    result = await self.get_table(
                        batch_coords, profile, sources, destinations, use_cache=use_cache
                    )

                # Fill in the result matrices
                for ii, src_idx in enumerate(range(i, batch_end_i)):
                    for jj, dst_idx in enumerate(range(j, batch_end_j)):
                        distances[src_idx][dst_idx] = result.distances[ii][jj]
                        durations[src_idx][dst_idx] = result.durations[ii][jj]

        logger.info(f"Completed batched OSRM table request for {n} coordinates")

        return MatrixResult(distances=distances, durations=durations)

    async def get_nearest(
        self,
        longitude: float,
        latitude: float,
        profile: str = "driving",
        number: int = 1,
    ) -> list[dict]:
        """
        Find nearest road point to a coordinate.

        Args:
            longitude: Longitude
            latitude: Latitude
            profile: Routing profile
            number: Number of results to return

        Returns:
            List of nearest points with location and distance
        """
        url = f"{self.base_url}/nearest/v1/{profile}/{longitude},{latitude}"
        params = {"number": number}

        data = await self._request_with_retry(url, params, "nearest")
        return data["waypoints"]

    async def health_check(self) -> bool:
        """Check if OSRM service is available."""
        try:
            url = f"{self.base_url}/health"
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception:
            # Try a simple route request as fallback
            try:
                # Tashkent coordinates
                await self.get_nearest(69.279737, 41.311081)
                return True
            except Exception:
                return False

    async def invalidate_cache(self, pattern: str = "osrm:*") -> int:
        """
        Invalidate cached OSRM data.

        Args:
            pattern: Key pattern to delete (default: all OSRM cache)

        Returns:
            Number of deleted keys
        """
        client = await redis_client.get_client()
        keys = []
        async for key in client.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            deleted = await client.delete(*keys)
            logger.info(f"Invalidated {deleted} OSRM cache keys matching '{pattern}'")
            return deleted
        return 0


# Singleton instance
osrm_client = OSRMClient()
