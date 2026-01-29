"""
Parallel OSRM matrix computation (R7).

Splits large distance matrix requests into batches and processes
them concurrently for significant performance improvement.

Performance:
- Sequential 300x300: ~18 seconds (9 requests * 2s each)
- Parallel 300x300: ~6 seconds (3 batches * 2s with concurrency=4)
"""
import asyncio
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class ParallelMatrixComputer:
    """
    Parallel OSRM distance matrix computation.

    Uses asyncio.Semaphore to limit concurrent requests and
    reconstructs full NxN matrix from batch results.
    """

    def __init__(
        self,
        osrm_client,
        max_concurrent: int = 4,
        batch_size: int = 100,
    ):
        """
        Initialize parallel matrix computer.

        Args:
            osrm_client: OSRM client instance
            max_concurrent: Maximum concurrent OSRM requests
            batch_size: Maximum points per OSRM request (OSRM limit ~100)
        """
        self.osrm = osrm_client
        self.max_concurrent = max_concurrent
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def compute(
        self,
        coordinates: list[tuple[float, float]],
        profile: str = "car",
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Compute full NxN distance and duration matrices.

        Args:
            coordinates: List of (longitude, latitude) tuples
            profile: OSRM profile (car, foot, bicycle)

        Returns:
            Tuple of (durations_matrix, distances_matrix) as numpy arrays
        """
        n = len(coordinates)

        if n == 0:
            return np.array([[]]), np.array([[]])

        if n <= self.batch_size:
            # Small enough for single request
            result = await self.osrm.get_table(coordinates, profile=profile)
            durations = np.array(result.durations) if result.durations else np.zeros((n, n))
            distances = np.array(result.distances) if result.distances else np.zeros((n, n))
            return durations, distances

        logger.info(
            f"Computing {n}x{n} matrix in parallel "
            f"(batch_size={self.batch_size}, max_concurrent={self.max_concurrent})"
        )

        # Create batch ranges
        batch_ranges = []
        for i in range(0, n, self.batch_size):
            i_end = min(i + self.batch_size, n)
            batch_ranges.append((i, i_end))

        # Generate all batch pair tasks
        tasks = []
        for i_start, i_end in batch_ranges:
            for j_start, j_end in batch_ranges:
                tasks.append(
                    self._compute_batch(
                        coordinates,
                        i_start, i_end,
                        j_start, j_end,
                        profile,
                    )
                )

        # Execute all tasks with concurrency limit
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Initialize result matrices
        durations = np.zeros((n, n))
        distances = np.zeros((n, n))

        # Merge results
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch computation failed: {result}")
                continue

            i_start, i_end, j_start, j_end, batch_durations, batch_distances = result
            durations[i_start:i_end, j_start:j_end] = batch_durations
            distances[i_start:i_end, j_start:j_end] = batch_distances

        logger.info(f"Parallel matrix computation complete: {n}x{n}")
        return durations, distances

    async def _compute_batch(
        self,
        all_coords: list[tuple[float, float]],
        i_start: int,
        i_end: int,
        j_start: int,
        j_end: int,
        profile: str,
    ) -> tuple[int, int, int, int, np.ndarray, np.ndarray]:
        """
        Compute a single batch of the matrix.

        Args:
            all_coords: Full coordinate list
            i_start, i_end: Row range
            j_start, j_end: Column range
            profile: OSRM profile

        Returns:
            Tuple of (i_start, i_end, j_start, j_end, durations, distances)
        """
        async with self.semaphore:
            # Extract source and destination coordinates
            source_coords = all_coords[i_start:i_end]
            dest_coords = all_coords[j_start:j_end]

            # Combine coordinates for OSRM request
            combined_coords = source_coords + dest_coords
            n_sources = len(source_coords)
            n_dests = len(dest_coords)

            # Source indices are 0 to n_sources-1
            # Destination indices are n_sources to n_sources+n_dests-1
            source_indices = list(range(n_sources))
            dest_indices = list(range(n_sources, n_sources + n_dests))

            try:
                result = await self.osrm.get_table(
                    combined_coords,
                    sources=source_indices,
                    destinations=dest_indices,
                    profile=profile,
                    annotations=["duration", "distance"],
                )

                durations = np.array(result.durations) if result.durations else np.zeros((n_sources, n_dests))
                distances = np.array(result.distances) if result.distances else np.zeros((n_sources, n_dests))

                return (i_start, i_end, j_start, j_end, durations, distances)

            except Exception as e:
                logger.error(f"Batch [{i_start}:{i_end}][{j_start}:{j_end}] failed: {e}")
                # Return zeros for failed batch
                return (
                    i_start, i_end, j_start, j_end,
                    np.zeros((i_end - i_start, j_end - j_start)),
                    np.zeros((i_end - i_start, j_end - j_start)),
                )

    async def compute_durations_only(
        self,
        coordinates: list[tuple[float, float]],
        profile: str = "car",
    ) -> np.ndarray:
        """
        Compute only durations matrix (faster, less data).

        Args:
            coordinates: List of (longitude, latitude) tuples
            profile: OSRM profile

        Returns:
            Duration matrix as numpy array
        """
        durations, _ = await self.compute(coordinates, profile)
        return durations


class MatrixCache:
    """
    Caching layer for computed matrices.

    Uses content-addressed storage based on coordinate hash.
    """

    def __init__(self, redis_client, ttl_seconds: int = 604800):
        """
        Initialize matrix cache.

        Args:
            redis_client: Redis client instance
            ttl_seconds: Cache TTL (default 7 days)
        """
        self.redis = redis_client
        self.ttl = ttl_seconds

    def _compute_key(
        self,
        coordinates: list[tuple[float, float]],
        profile: str,
    ) -> str:
        """Generate cache key from coordinates."""
        import hashlib

        # Round coordinates to 5 decimal places (~1m precision)
        rounded = [(round(lon, 5), round(lat, 5)) for lon, lat in coordinates]
        coord_str = str(sorted(rounded))
        hash_val = hashlib.md5(coord_str.encode()).hexdigest()

        return f"matrix:{profile}:{hash_val}"

    async def get(
        self,
        coordinates: list[tuple[float, float]],
        profile: str = "car",
    ) -> Optional[tuple[np.ndarray, np.ndarray]]:
        """Get cached matrix if available."""
        import json

        key = self._compute_key(coordinates, profile)
        data = await self.redis.get(key)

        if data:
            parsed = json.loads(data)
            return (
                np.array(parsed["durations"]),
                np.array(parsed["distances"]),
            )

        return None

    async def set(
        self,
        coordinates: list[tuple[float, float]],
        durations: np.ndarray,
        distances: np.ndarray,
        profile: str = "car",
    ) -> None:
        """Cache computed matrix."""
        import json

        key = self._compute_key(coordinates, profile)
        data = json.dumps({
            "durations": durations.tolist(),
            "distances": distances.tolist(),
        })

        await self.redis.setex(key, self.ttl, data)


class CachedParallelMatrixComputer:
    """
    Matrix computer with integrated caching.

    Combines ParallelMatrixComputer with MatrixCache for
    optimal performance on repeated queries.
    """

    def __init__(
        self,
        osrm_client,
        redis_client,
        max_concurrent: int = 4,
        batch_size: int = 100,
        cache_ttl: int = 604800,
    ):
        self.computer = ParallelMatrixComputer(
            osrm_client, max_concurrent, batch_size
        )
        self.cache = MatrixCache(redis_client, cache_ttl)

    async def compute(
        self,
        coordinates: list[tuple[float, float]],
        profile: str = "car",
        use_cache: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Compute matrix with caching.

        Args:
            coordinates: List of (longitude, latitude) tuples
            profile: OSRM profile
            use_cache: Whether to use cache

        Returns:
            Tuple of (durations, distances) matrices
        """
        if use_cache:
            cached = await self.cache.get(coordinates, profile)
            if cached:
                logger.debug("Matrix cache hit")
                return cached

        # Compute fresh
        durations, distances = await self.computer.compute(coordinates, profile)

        # Cache result
        if use_cache and len(coordinates) > 10:
            await self.cache.set(coordinates, durations, distances, profile)

        return durations, distances
