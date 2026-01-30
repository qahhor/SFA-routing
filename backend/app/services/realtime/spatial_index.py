"""
H3 Spatial Index (R5).

Hierarchical spatial indexing using Uber's H3 library for
fast nearest-neighbor queries and geographic clustering.

H3 Resolutions:
- Resolution 4: ~1,770 km² (regional/country level)
- Resolution 7: ~5.16 km² (city district)
- Resolution 9: ~0.1 km² (neighborhood)
- Resolution 11: ~0.0025 km² (street block)

Reference: https://h3geo.org/
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from math import cos, radians
from uuid import UUID

logger = logging.getLogger(__name__)

# H3 library import with fallback
try:
    import h3

    H3_AVAILABLE = True
except ImportError:
    H3_AVAILABLE = False
    logger.warning("H3 library not installed. Spatial indexing will use fallback.")


@dataclass
class SpatialEntity:
    """Entity with spatial coordinates."""

    id: UUID
    latitude: float
    longitude: float
    data: dict = field(default_factory=dict)


@dataclass
class SpatialQueryResult:
    """Result of spatial query."""

    entities: list[SpatialEntity]
    h3_cells_searched: int
    query_time_ms: float


class H3SpatialIndex:
    """
    H3-based spatial index for fast geographic queries.

    Features:
    - O(1) cell lookup
    - Efficient k-ring neighbor queries
    - Multi-resolution support
    - In-memory index with optional Redis persistence
    """

    DEFAULT_RESOLUTION = 9  # ~100m precision

    def __init__(
        self,
        resolution: int = DEFAULT_RESOLUTION,
        redis_client=None,
    ):
        """
        Initialize H3 spatial index.

        Args:
            resolution: H3 resolution (0-15, higher = more precise)
            redis_client: Optional Redis client for persistence
        """
        if not H3_AVAILABLE:
            raise ImportError("H3 library required: pip install h3")

        self.resolution = resolution
        self.redis = redis_client

        # In-memory index: h3_cell -> list of entities
        self._index: dict[str, list[SpatialEntity]] = defaultdict(list)

        # Entity lookup: entity_id -> h3_cell
        self._entity_cells: dict[UUID, str] = {}

    def add(self, entity: SpatialEntity) -> str:
        """
        Add entity to spatial index.

        Returns:
            H3 cell index
        """
        cell = h3.geo_to_h3(entity.latitude, entity.longitude, self.resolution)

        # Remove from old cell if exists
        if entity.id in self._entity_cells:
            old_cell = self._entity_cells[entity.id]
            self._index[old_cell] = [e for e in self._index[old_cell] if e.id != entity.id]

        # Add to new cell
        self._index[cell].append(entity)
        self._entity_cells[entity.id] = cell

        return cell

    def remove(self, entity_id: UUID) -> bool:
        """
        Remove entity from index.

        Returns:
            True if entity was found and removed
        """
        if entity_id not in self._entity_cells:
            return False

        cell = self._entity_cells[entity_id]
        self._index[cell] = [e for e in self._index[cell] if e.id != entity_id]

        del self._entity_cells[entity_id]
        return True

    def get_cell(self, lat: float, lon: float) -> str:
        """Get H3 cell for coordinates."""
        return h3.geo_to_h3(lat, lon, self.resolution)

    def query_cell(self, cell: str) -> list[SpatialEntity]:
        """Get all entities in a cell."""
        return self._index.get(cell, [])

    def query_point(
        self,
        lat: float,
        lon: float,
        k_ring: int = 1,
    ) -> SpatialQueryResult:
        """
        Query entities near a point.

        Args:
            lat: Latitude
            lon: Longitude
            k_ring: Number of rings to search (0=same cell only)

        Returns:
            SpatialQueryResult with nearby entities
        """
        import time

        start = time.time()

        center_cell = h3.geo_to_h3(lat, lon, self.resolution)

        if k_ring == 0:
            cells = {center_cell}
        else:
            cells = h3.k_ring(center_cell, k_ring)

        entities = []
        for cell in cells:
            entities.extend(self._index.get(cell, []))

        query_time = (time.time() - start) * 1000

        return SpatialQueryResult(
            entities=entities,
            h3_cells_searched=len(cells),
            query_time_ms=query_time,
        )

    def query_radius(
        self,
        lat: float,
        lon: float,
        radius_meters: float,
    ) -> SpatialQueryResult:
        """
        Query entities within radius of a point.

        Args:
            lat: Latitude
            lon: Longitude
            radius_meters: Search radius in meters

        Returns:
            SpatialQueryResult with entities within radius
        """
        import time

        start = time.time()

        # Estimate k-ring size needed for radius
        # At resolution 9, each cell is ~100m across
        cell_size = self._get_cell_size_meters()
        k_ring = max(1, int(radius_meters / cell_size) + 1)

        # Get candidate entities from cells
        result = self.query_point(lat, lon, k_ring)

        # Filter by exact distance
        filtered = []
        for entity in result.entities:
            distance = self._haversine(lat, lon, entity.latitude, entity.longitude)
            if distance <= radius_meters:
                filtered.append(entity)

        query_time = (time.time() - start) * 1000

        return SpatialQueryResult(
            entities=filtered,
            h3_cells_searched=result.h3_cells_searched,
            query_time_ms=query_time,
        )

    def query_nearest(
        self,
        lat: float,
        lon: float,
        n: int = 5,
        max_k_ring: int = 10,
    ) -> list[tuple[SpatialEntity, float]]:
        """
        Find n nearest entities to a point.

        Args:
            lat: Latitude
            lon: Longitude
            n: Number of nearest entities to return
            max_k_ring: Maximum search radius in k-rings

        Returns:
            List of (entity, distance_meters) tuples, sorted by distance
        """
        candidates = []

        # Expand search until we have enough candidates
        for k in range(max_k_ring + 1):
            result = self.query_point(lat, lon, k)

            for entity in result.entities:
                distance = self._haversine(lat, lon, entity.latitude, entity.longitude)
                candidates.append((entity, distance))

            if len(candidates) >= n:
                break

        # Sort by distance and return top n
        candidates.sort(key=lambda x: x[1])
        return candidates[:n]

    def get_clusters(
        self,
        min_entities: int = 3,
    ) -> dict[str, list[SpatialEntity]]:
        """
        Get all cells with at least min_entities.

        Useful for identifying high-density areas.
        """
        clusters = {}
        for cell, entities in self._index.items():
            if len(entities) >= min_entities:
                clusters[cell] = entities
        return clusters

    def get_statistics(self) -> dict:
        """Get index statistics."""
        total_entities = sum(len(e) for e in self._index.values())
        cells_used = len([c for c, e in self._index.items() if e])
        max_per_cell = max(len(e) for e in self._index.values()) if self._index else 0
        avg_per_cell = total_entities / cells_used if cells_used > 0 else 0

        return {
            "resolution": self.resolution,
            "total_entities": total_entities,
            "cells_used": cells_used,
            "max_entities_per_cell": max_per_cell,
            "avg_entities_per_cell": round(avg_per_cell, 2),
            "cell_size_meters": self._get_cell_size_meters(),
        }

    def _get_cell_size_meters(self) -> float:
        """Get approximate cell edge length in meters."""
        # H3 cell sizes by resolution (approximate edge length in meters)
        cell_sizes = {
            0: 1107712.591,
            1: 418676.005,
            2: 158244.655,
            3: 59810.857,
            4: 22606.379,
            5: 8544.408,
            6: 3229.482,
            7: 1220.629,
            8: 461.354,
            9: 174.375,
            10: 65.907,
            11: 24.910,
            12: 9.415,
            13: 3.559,
            14: 1.348,
            15: 0.509,
        }
        return cell_sizes.get(self.resolution, 100)

    def _haversine(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Calculate distance between two points in meters."""
        from math import atan2, cos, radians, sin, sqrt

        R = 6371000  # Earth radius in meters

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return R * c

    # Redis persistence methods

    async def save_to_redis(self, key_prefix: str = "spatial_index") -> int:
        """
        Persist index to Redis.

        Returns:
            Number of cells saved
        """
        if not self.redis:
            raise ValueError("Redis client not configured")

        import json

        saved = 0
        for cell, entities in self._index.items():
            if not entities:
                continue

            data = [
                {
                    "id": str(e.id),
                    "lat": e.latitude,
                    "lon": e.longitude,
                    "data": e.data,
                }
                for e in entities
            ]

            await self.redis.set(
                f"{key_prefix}:{cell}",
                json.dumps(data),
            )
            saved += 1

        return saved

    async def load_from_redis(self, key_prefix: str = "spatial_index") -> int:
        """
        Load index from Redis.

        Returns:
            Number of entities loaded
        """
        if not self.redis:
            raise ValueError("Redis client not configured")

        import json

        # Clear current index
        self._index.clear()
        self._entity_cells.clear()

        loaded = 0
        cursor = 0

        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=f"{key_prefix}:*",
                count=100,
            )

            for key in keys:
                data = await self.redis.get(key)
                if not data:
                    continue

                entities = json.loads(data)
                cell = key.decode().split(":")[-1]

                for e in entities:
                    entity = SpatialEntity(
                        id=UUID(e["id"]),
                        latitude=e["lat"],
                        longitude=e["lon"],
                        data=e.get("data", {}),
                    )
                    self._index[cell].append(entity)
                    self._entity_cells[entity.id] = cell
                    loaded += 1

            if cursor == 0:
                break

        return loaded


class FallbackSpatialIndex:
    """
    Fallback spatial index when H3 is not available.

    Uses simple grid-based indexing.
    """

    def __init__(self, grid_size_degrees: float = 0.01):
        """
        Initialize fallback index.

        Args:
            grid_size_degrees: Grid cell size in degrees (~1km at equator)
        """
        self.grid_size = grid_size_degrees
        self._index: dict[tuple[int, int], list[SpatialEntity]] = defaultdict(list)
        self._entity_cells: dict[UUID, tuple[int, int]] = {}

    def _get_cell(self, lat: float, lon: float) -> tuple[int, int]:
        """Get grid cell for coordinates."""
        return (
            int(lat / self.grid_size),
            int(lon / self.grid_size),
        )

    def add(self, entity: SpatialEntity) -> tuple[int, int]:
        """Add entity to index."""
        cell = self._get_cell(entity.latitude, entity.longitude)

        if entity.id in self._entity_cells:
            old_cell = self._entity_cells[entity.id]
            self._index[old_cell] = [e for e in self._index[old_cell] if e.id != entity.id]

        self._index[cell].append(entity)
        self._entity_cells[entity.id] = cell
        return cell

    def query_radius(
        self,
        lat: float,
        lon: float,
        radius_meters: float,
    ) -> list[SpatialEntity]:
        """Query entities within radius."""
        # Approximate degrees for radius
        lat_range = radius_meters / 111000  # ~111km per degree
        lon_range = radius_meters / (111000 * abs(cos(radians(lat))) or 1)

        center = self._get_cell(lat, lon)
        cells_to_check = int(max(lat_range, lon_range) / self.grid_size) + 1

        candidates = []
        for di in range(-cells_to_check, cells_to_check + 1):
            for dj in range(-cells_to_check, cells_to_check + 1):
                cell = (center[0] + di, center[1] + dj)
                candidates.extend(self._index.get(cell, []))

        # Filter by exact distance
        from math import atan2, cos, radians, sin, sqrt

        R = 6371000
        filtered = []

        for entity in candidates:
            lat1, lon1, lat2, lon2 = map(radians, [lat, lon, entity.latitude, entity.longitude])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            distance = R * 2 * atan2(sqrt(a), sqrt(1 - a))

            if distance <= radius_meters:
                filtered.append(entity)

        return filtered


# Factory function
def create_spatial_index(
    resolution: int = 9,
    redis_client=None,
) -> H3SpatialIndex | FallbackSpatialIndex:
    """
    Create spatial index with automatic fallback.

    Returns H3 index if available, otherwise fallback grid index.
    """
    if H3_AVAILABLE:
        return H3SpatialIndex(resolution, redis_client)
    else:
        logger.warning("Using fallback spatial index (install h3 for better performance)")
        return FallbackSpatialIndex()
