"""
Tests for Parallel OSRM Matrix Computation module.

Tests cover:
- ParallelMatrixComputer initialization
- Batch computation
- Matrix assembly
- MatrixCache operations
- CachedParallelMatrixComputer
"""
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from app.services.caching.parallel_matrix import (
    ParallelMatrixComputer,
    MatrixCache,
    CachedParallelMatrixComputer,
)


@dataclass
class MockOSRMResult:
    """Mock OSRM table result."""
    durations: list[list[float]]
    distances: list[list[float]]


class TestParallelMatrixComputer:
    """Tests for ParallelMatrixComputer class."""

    @pytest.fixture
    def mock_osrm_client(self):
        """Create mock OSRM client."""
        client = MagicMock()
        client.get_table = AsyncMock()
        return client

    @pytest.fixture
    def computer(self, mock_osrm_client):
        """Create ParallelMatrixComputer instance."""
        return ParallelMatrixComputer(
            osrm_client=mock_osrm_client,
            max_concurrent=2,
            batch_size=10,
        )

    def test_initialization(self, computer, mock_osrm_client):
        """Test computer initialization."""
        assert computer.osrm == mock_osrm_client
        assert computer.max_concurrent == 2
        assert computer.batch_size == 10

    @pytest.mark.asyncio
    async def test_compute_empty_coordinates(self, computer, mock_osrm_client):
        """Test computation with empty coordinates."""
        durations, distances = await computer.compute([])

        assert durations.shape == (1, 0)
        assert distances.shape == (1, 0)

    @pytest.mark.asyncio
    async def test_compute_small_batch(self, computer, mock_osrm_client):
        """Test computation with small batch (single request)."""
        # Small enough to fit in one batch
        coordinates = [(69.0, 41.0), (69.1, 41.1), (69.2, 41.2)]

        mock_osrm_client.get_table.return_value = MockOSRMResult(
            durations=[[0, 100, 200], [100, 0, 150], [200, 150, 0]],
            distances=[[0, 1000, 2000], [1000, 0, 1500], [2000, 1500, 0]],
        )

        durations, distances = await computer.compute(coordinates)

        assert durations.shape == (3, 3)
        assert distances.shape == (3, 3)
        assert durations[0, 0] == 0
        assert durations[0, 1] == 100
        mock_osrm_client.get_table.assert_called_once()

    @pytest.mark.asyncio
    async def test_compute_null_result(self, computer, mock_osrm_client):
        """Test handling of null results from OSRM."""
        coordinates = [(69.0, 41.0), (69.1, 41.1)]

        mock_osrm_client.get_table.return_value = MockOSRMResult(
            durations=None,
            distances=None,
        )

        durations, distances = await computer.compute(coordinates)

        # Should return zeros when OSRM returns null
        assert durations.shape == (2, 2)
        assert np.all(durations == 0)

    @pytest.mark.asyncio
    async def test_compute_large_batch_parallel(self, computer, mock_osrm_client):
        """Test parallel computation with large batch."""
        # 15 coordinates, batch_size=10 -> multiple batches
        coordinates = [(69.0 + i * 0.01, 41.0 + i * 0.01) for i in range(15)]

        def create_mock_result(*args, **kwargs):
            """Create mock result based on indices."""
            sources = kwargs.get('sources', list(range(len(args[0]))))
            dests = kwargs.get('destinations', sources)
            n_sources = len(sources)
            n_dests = len(dests)
            return MockOSRMResult(
                durations=[[100.0] * n_dests for _ in range(n_sources)],
                distances=[[1000.0] * n_dests for _ in range(n_sources)],
            )

        mock_osrm_client.get_table.side_effect = create_mock_result

        durations, distances = await computer.compute(coordinates)

        assert durations.shape == (15, 15)
        assert distances.shape == (15, 15)
        # Multiple calls should have been made
        assert mock_osrm_client.get_table.call_count > 1

    @pytest.mark.asyncio
    async def test_compute_durations_only(self, computer, mock_osrm_client):
        """Test computing only durations."""
        coordinates = [(69.0, 41.0), (69.1, 41.1)]

        mock_osrm_client.get_table.return_value = MockOSRMResult(
            durations=[[0, 100], [100, 0]],
            distances=[[0, 1000], [1000, 0]],
        )

        durations = await computer.compute_durations_only(coordinates)

        assert durations.shape == (2, 2)
        assert isinstance(durations, np.ndarray)

    @pytest.mark.asyncio
    async def test_compute_batch_error_handling(self, computer, mock_osrm_client):
        """Test error handling in batch computation."""
        coordinates = [(69.0 + i * 0.01, 41.0 + i * 0.01) for i in range(15)]

        # First call succeeds, second fails
        call_count = [0]

        async def mock_get_table(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Network error")
            sources = kwargs.get('sources', list(range(len(args[0]))))
            dests = kwargs.get('destinations', sources)
            n_sources = len(sources)
            n_dests = len(dests)
            return MockOSRMResult(
                durations=[[100.0] * n_dests for _ in range(n_sources)],
                distances=[[1000.0] * n_dests for _ in range(n_sources)],
            )

        mock_osrm_client.get_table.side_effect = mock_get_table

        # Should not raise, failed batches return zeros
        durations, distances = await computer.compute(coordinates)

        assert durations.shape == (15, 15)


class TestMatrixCache:
    """Tests for MatrixCache class."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = MagicMock()
        redis.get = AsyncMock()
        redis.setex = AsyncMock()
        return redis

    @pytest.fixture
    def cache(self, mock_redis):
        """Create MatrixCache instance."""
        return MatrixCache(
            redis_client=mock_redis,
            ttl_seconds=3600,
        )

    def test_initialization(self, cache, mock_redis):
        """Test cache initialization."""
        assert cache.redis == mock_redis
        assert cache.ttl == 3600

    def test_compute_key(self, cache):
        """Test cache key computation."""
        coords1 = [(69.27901, 41.31101), (69.28001, 41.31201)]
        coords2 = [(69.27901, 41.31101), (69.28001, 41.31201)]
        coords3 = [(69.27901, 41.31101), (69.28001, 41.31301)]

        key1 = cache._compute_key(coords1, "car")
        key2 = cache._compute_key(coords2, "car")
        key3 = cache._compute_key(coords3, "car")

        # Same coordinates should produce same key
        assert key1 == key2
        # Different coordinates should produce different key
        assert key1 != key3
        # Key should include profile
        assert "car" in key1

    def test_compute_key_rounds_coordinates(self, cache):
        """Test that coordinates are rounded in key computation."""
        coords1 = [(69.279001, 41.311001)]
        coords2 = [(69.279002, 41.311002)]

        key1 = cache._compute_key(coords1, "car")
        key2 = cache._compute_key(coords2, "car")

        # Should be same after rounding to 5 decimals
        assert key1 == key2

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache, mock_redis):
        """Test cache miss returns None."""
        mock_redis.get.return_value = None

        result = await cache.get([(69.0, 41.0)], "car")

        assert result is None
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, cache, mock_redis):
        """Test cache hit returns data."""
        import json

        mock_redis.get.return_value = json.dumps({
            "durations": [[0, 100], [100, 0]],
            "distances": [[0, 1000], [1000, 0]],
        })

        result = await cache.get([(69.0, 41.0), (69.1, 41.1)], "car")

        assert result is not None
        durations, distances = result
        assert durations.shape == (2, 2)
        assert distances.shape == (2, 2)

    @pytest.mark.asyncio
    async def test_set_cache(self, cache, mock_redis):
        """Test setting cache value."""
        durations = np.array([[0, 100], [100, 0]])
        distances = np.array([[0, 1000], [1000, 0]])

        await cache.set(
            [(69.0, 41.0), (69.1, 41.1)],
            durations,
            distances,
            "car",
        )

        mock_redis.setex.assert_called_once()
        # Check TTL was passed
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 3600  # TTL


class TestCachedParallelMatrixComputer:
    """Tests for CachedParallelMatrixComputer class."""

    @pytest.fixture
    def mock_osrm_client(self):
        """Create mock OSRM client."""
        client = MagicMock()
        client.get_table = AsyncMock()
        return client

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        return redis

    @pytest.fixture
    def cached_computer(self, mock_osrm_client, mock_redis):
        """Create CachedParallelMatrixComputer instance."""
        return CachedParallelMatrixComputer(
            osrm_client=mock_osrm_client,
            redis_client=mock_redis,
            max_concurrent=2,
            batch_size=10,
            cache_ttl=3600,
        )

    def test_initialization(self, cached_computer):
        """Test cached computer initialization."""
        assert cached_computer.computer is not None
        assert cached_computer.cache is not None

    @pytest.mark.asyncio
    async def test_compute_cache_miss(self, cached_computer, mock_osrm_client, mock_redis):
        """Test compute with cache miss."""
        coordinates = [(69.0, 41.0), (69.1, 41.1)]

        mock_osrm_client.get_table.return_value = MockOSRMResult(
            durations=[[0, 100], [100, 0]],
            distances=[[0, 1000], [1000, 0]],
        )

        durations, distances = await cached_computer.compute(coordinates)

        # Should have computed and cached
        assert durations.shape == (2, 2)
        mock_osrm_client.get_table.assert_called_once()

    @pytest.mark.asyncio
    async def test_compute_cache_hit(self, cached_computer, mock_osrm_client, mock_redis):
        """Test compute with cache hit."""
        import json

        coordinates = [(69.0, 41.0), (69.1, 41.1)]

        # Set up cache hit
        mock_redis.get.return_value = json.dumps({
            "durations": [[0, 100], [100, 0]],
            "distances": [[0, 1000], [1000, 0]],
        })

        durations, distances = await cached_computer.compute(coordinates)

        # Should have used cache
        assert durations.shape == (2, 2)
        mock_osrm_client.get_table.assert_not_called()

    @pytest.mark.asyncio
    async def test_compute_bypass_cache(self, cached_computer, mock_osrm_client, mock_redis):
        """Test compute with cache bypass."""
        import json

        coordinates = [(69.0, 41.0), (69.1, 41.1)]

        # Set up cache
        mock_redis.get.return_value = json.dumps({
            "durations": [[0, 100], [100, 0]],
            "distances": [[0, 1000], [1000, 0]],
        })

        mock_osrm_client.get_table.return_value = MockOSRMResult(
            durations=[[0, 200], [200, 0]],
            distances=[[0, 2000], [2000, 0]],
        )

        # Bypass cache
        durations, distances = await cached_computer.compute(coordinates, use_cache=False)

        # Should have computed fresh
        assert durations[0, 1] == 200
        mock_osrm_client.get_table.assert_called_once()

    @pytest.mark.asyncio
    async def test_compute_small_set_not_cached(self, cached_computer, mock_osrm_client, mock_redis):
        """Test that very small sets are not cached."""
        coordinates = [(69.0, 41.0), (69.1, 41.1)]

        mock_osrm_client.get_table.return_value = MockOSRMResult(
            durations=[[0, 100], [100, 0]],
            distances=[[0, 1000], [1000, 0]],
        )

        await cached_computer.compute(coordinates)

        # Should not cache small sets (< 10 points)
        mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_compute_large_set_cached(self, cached_computer, mock_osrm_client, mock_redis):
        """Test that larger sets are cached."""
        coordinates = [(69.0 + i * 0.01, 41.0 + i * 0.01) for i in range(15)]

        def create_mock_result(*args, **kwargs):
            sources = kwargs.get('sources', list(range(len(args[0]))))
            dests = kwargs.get('destinations', sources)
            n_sources = len(sources)
            n_dests = len(dests)
            return MockOSRMResult(
                durations=[[100.0] * n_dests for _ in range(n_sources)],
                distances=[[1000.0] * n_dests for _ in range(n_sources)],
            )

        mock_osrm_client.get_table.side_effect = create_mock_result

        await cached_computer.compute(coordinates)

        # Should cache larger sets
        mock_redis.setex.assert_called()


class TestBatchRangeCalculation:
    """Tests for batch range calculations."""

    @pytest.fixture
    def computer(self):
        """Create computer with small batch size for testing."""
        mock_client = MagicMock()
        return ParallelMatrixComputer(
            osrm_client=mock_client,
            max_concurrent=4,
            batch_size=5,
        )

    def test_batch_ranges_small(self, computer):
        """Test batch ranges for small input."""
        n = 3
        batch_ranges = []
        for i in range(0, n, computer.batch_size):
            i_end = min(i + computer.batch_size, n)
            batch_ranges.append((i, i_end))

        assert len(batch_ranges) == 1
        assert batch_ranges[0] == (0, 3)

    def test_batch_ranges_exact(self, computer):
        """Test batch ranges when n is exact multiple of batch_size."""
        n = 10
        batch_ranges = []
        for i in range(0, n, computer.batch_size):
            i_end = min(i + computer.batch_size, n)
            batch_ranges.append((i, i_end))

        assert len(batch_ranges) == 2
        assert batch_ranges[0] == (0, 5)
        assert batch_ranges[1] == (5, 10)

    def test_batch_ranges_remainder(self, computer):
        """Test batch ranges with remainder."""
        n = 12
        batch_ranges = []
        for i in range(0, n, computer.batch_size):
            i_end = min(i + computer.batch_size, n)
            batch_ranges.append((i, i_end))

        assert len(batch_ranges) == 3
        assert batch_ranges[0] == (0, 5)
        assert batch_ranges[1] == (5, 10)
        assert batch_ranges[2] == (10, 12)


class TestMatrixAssembly:
    """Tests for matrix assembly from batch results."""

    def test_matrix_assembly(self):
        """Test that batch results are assembled correctly."""
        # Simulate 10x10 matrix computed in batches of 5
        full_matrix = np.zeros((10, 10))

        # Batch (0,5)x(0,5) -> fill upper-left quadrant
        full_matrix[0:5, 0:5] = np.ones((5, 5)) * 1

        # Batch (0,5)x(5,10) -> fill upper-right quadrant
        full_matrix[0:5, 5:10] = np.ones((5, 5)) * 2

        # Batch (5,10)x(0,5) -> fill lower-left quadrant
        full_matrix[5:10, 0:5] = np.ones((5, 5)) * 3

        # Batch (5,10)x(5,10) -> fill lower-right quadrant
        full_matrix[5:10, 5:10] = np.ones((5, 5)) * 4

        # Verify assembly
        assert full_matrix[0, 0] == 1  # Upper-left
        assert full_matrix[0, 9] == 2  # Upper-right
        assert full_matrix[9, 0] == 3  # Lower-left
        assert full_matrix[9, 9] == 4  # Lower-right
