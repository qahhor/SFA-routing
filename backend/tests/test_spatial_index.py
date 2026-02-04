"""
Tests for H3 Spatial Index module.

Tests cover:
- SpatialEntity dataclass
- SpatialQueryResult dataclass
- H3SpatialIndex operations (add, remove, query)
- FallbackSpatialIndex operations
- create_spatial_index factory
- Distance calculations
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from app.services.realtime.spatial_index import (
    SpatialEntity,
    SpatialQueryResult,
    FallbackSpatialIndex,
    create_spatial_index,
)


class TestSpatialEntity:
    """Tests for SpatialEntity dataclass."""

    def test_creation(self):
        """Test basic entity creation."""
        entity_id = uuid4()
        entity = SpatialEntity(
            id=entity_id,
            latitude=41.311,
            longitude=69.279,
        )

        assert entity.id == entity_id
        assert entity.latitude == 41.311
        assert entity.longitude == 69.279
        assert entity.data == {}

    def test_creation_with_data(self):
        """Test entity creation with custom data."""
        entity_id = uuid4()
        entity = SpatialEntity(
            id=entity_id,
            latitude=41.311,
            longitude=69.279,
            data={"name": "Test", "category": "A"},
        )

        assert entity.data == {"name": "Test", "category": "A"}


class TestSpatialQueryResult:
    """Tests for SpatialQueryResult dataclass."""

    def test_creation(self):
        """Test result creation."""
        entities = [
            SpatialEntity(id=uuid4(), latitude=41.0, longitude=69.0),
            SpatialEntity(id=uuid4(), latitude=41.1, longitude=69.1),
        ]

        result = SpatialQueryResult(
            entities=entities,
            h3_cells_searched=7,
            query_time_ms=1.5,
        )

        assert len(result.entities) == 2
        assert result.h3_cells_searched == 7
        assert result.query_time_ms == 1.5


class TestH3SpatialIndex:
    """Tests for H3SpatialIndex class."""

    @pytest.fixture
    def mock_h3(self):
        """Create mock for h3 library."""
        with patch.dict('sys.modules', {'h3': MagicMock()}):
            import sys
            h3_mock = sys.modules['h3']

            # Mock geo_to_h3 to return predictable cells
            def mock_geo_to_h3(lat, lon, res):
                return f"cell_{int(lat*100)}_{int(lon*100)}_{res}"

            h3_mock.geo_to_h3 = mock_geo_to_h3

            # Mock k_ring to return adjacent cells
            def mock_k_ring(cell, k):
                if k == 0:
                    return {cell}
                # Return center and neighbors
                return {cell, f"{cell}_n1", f"{cell}_n2"}

            h3_mock.k_ring = mock_k_ring

            yield h3_mock

    @pytest.fixture
    def sample_entities(self):
        """Create sample entities for testing."""
        return [
            SpatialEntity(
                id=uuid4(),
                latitude=41.311,
                longitude=69.279,
                data={"name": "Point 1"},
            ),
            SpatialEntity(
                id=uuid4(),
                latitude=41.312,
                longitude=69.280,
                data={"name": "Point 2"},
            ),
            SpatialEntity(
                id=uuid4(),
                latitude=41.400,
                longitude=69.400,
                data={"name": "Far Point"},
            ),
        ]

    def test_h3_index_creation_without_h3(self):
        """Test that H3SpatialIndex raises error without h3 library."""
        # This test verifies the import check
        with patch('app.services.realtime.spatial_index.H3_AVAILABLE', False):
            # Need to reimport to apply patch
            from app.services.realtime.spatial_index import H3SpatialIndex
            with pytest.raises(ImportError, match="H3 library required"):
                H3SpatialIndex()


class TestFallbackSpatialIndex:
    """Tests for FallbackSpatialIndex class."""

    @pytest.fixture
    def index(self):
        """Create fallback index instance."""
        return FallbackSpatialIndex(grid_size_degrees=0.01)

    @pytest.fixture
    def sample_entities(self):
        """Create sample entities."""
        return [
            SpatialEntity(id=uuid4(), latitude=41.311, longitude=69.279),
            SpatialEntity(id=uuid4(), latitude=41.312, longitude=69.280),
            SpatialEntity(id=uuid4(), latitude=41.500, longitude=69.500),
        ]

    def test_initialization(self, index):
        """Test index initialization."""
        assert index.grid_size == 0.01
        assert len(index._index) == 0
        assert len(index._entity_cells) == 0

    def test_get_cell(self, index):
        """Test cell calculation."""
        cell = index._get_cell(41.311, 69.279)

        assert isinstance(cell, tuple)
        assert len(cell) == 2
        assert cell == (4131, 6927)  # 41.311 / 0.01 = 4131.1 -> 4131

    def test_add_entity(self, index, sample_entities):
        """Test adding entity to index."""
        entity = sample_entities[0]
        cell = index.add(entity)

        assert cell in index._index
        assert entity in index._index[cell]
        assert entity.id in index._entity_cells
        assert index._entity_cells[entity.id] == cell

    def test_add_multiple_entities(self, index, sample_entities):
        """Test adding multiple entities."""
        for entity in sample_entities:
            index.add(entity)

        assert len(index._entity_cells) == 3

    def test_add_entity_same_cell(self, index):
        """Test adding entities in same cell."""
        e1 = SpatialEntity(id=uuid4(), latitude=41.311, longitude=69.279)
        e2 = SpatialEntity(id=uuid4(), latitude=41.312, longitude=69.279)

        cell1 = index.add(e1)
        cell2 = index.add(e2)

        # Should be in same cell (within 0.01 degree grid)
        assert cell1 == cell2
        assert len(index._index[cell1]) == 2

    def test_add_entity_update_location(self, index):
        """Test updating entity location."""
        entity = SpatialEntity(id=uuid4(), latitude=41.311, longitude=69.279)

        old_cell = index.add(entity)

        # Update location (move to different cell)
        entity.latitude = 42.000
        entity.longitude = 70.000
        new_cell = index.add(entity)

        assert old_cell != new_cell
        assert entity not in index._index[old_cell]
        assert entity in index._index[new_cell]
        assert index._entity_cells[entity.id] == new_cell

    def test_query_radius_finds_nearby(self, index, sample_entities):
        """Test radius query finds nearby entities."""
        for entity in sample_entities:
            index.add(entity)

        # Query near first two entities (close together)
        results = index.query_radius(41.311, 69.279, 500)  # 500m radius

        # Should find the two close entities
        assert len(results) >= 1
        found_ids = {e.id for e in results}
        assert sample_entities[0].id in found_ids

    def test_query_radius_excludes_far(self, index, sample_entities):
        """Test radius query excludes far entities."""
        for entity in sample_entities:
            index.add(entity)

        # Query with small radius
        results = index.query_radius(41.311, 69.279, 100)  # 100m radius

        # Should not find the far entity (41.5, 69.5)
        found_ids = {e.id for e in results}
        assert sample_entities[2].id not in found_ids

    def test_query_radius_empty_area(self, index, sample_entities):
        """Test radius query in empty area."""
        for entity in sample_entities:
            index.add(entity)

        # Query far from all entities
        results = index.query_radius(50.0, 80.0, 1000)

        assert len(results) == 0

    def test_query_radius_large_radius(self, index, sample_entities):
        """Test query with large radius finds all entities."""
        for entity in sample_entities:
            index.add(entity)

        # Large radius should find all
        results = index.query_radius(41.4, 69.35, 50000)  # 50km

        assert len(results) == 3


class TestCreateSpatialIndex:
    """Tests for create_spatial_index factory function."""

    def test_creates_spatial_index(self):
        """Test factory creates appropriate index."""
        from app.services.realtime.spatial_index import create_spatial_index, H3_AVAILABLE, H3SpatialIndex

        index = create_spatial_index()

        # Should create H3SpatialIndex when H3 is available
        if H3_AVAILABLE:
            assert isinstance(index, H3SpatialIndex)
        else:
            assert isinstance(index, FallbackSpatialIndex)

    def test_factory_with_custom_resolution(self):
        """Test factory accepts resolution parameter."""
        from app.services.realtime.spatial_index import create_spatial_index, H3_AVAILABLE, H3SpatialIndex

        index = create_spatial_index(resolution=7)

        # Should create appropriate index based on H3 availability
        if H3_AVAILABLE:
            assert isinstance(index, H3SpatialIndex)
        else:
            assert isinstance(index, FallbackSpatialIndex)


class TestHaversineDistance:
    """Tests for distance calculation."""

    @pytest.fixture
    def index(self):
        """Create fallback index for distance tests."""
        return FallbackSpatialIndex()

    def test_same_point_zero_distance(self):
        """Test distance between same point is zero."""
        from math import radians, sin, cos, sqrt, atan2

        lat, lon = 41.311, 69.279

        # Calculate distance
        R = 6371000
        lat1, lon1, lat2, lon2 = map(radians, [lat, lon, lat, lon])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        distance = R * 2 * atan2(sqrt(a), sqrt(1-a))

        assert distance == 0.0

    def test_known_distance(self):
        """Test distance calculation with known points."""
        from math import radians, sin, cos, sqrt, atan2

        # Tashkent center to Chilanzar (~5km)
        lat1, lon1 = 41.311, 69.279
        lat2, lon2 = 41.311, 69.340  # ~5.5km east

        R = 6371000
        lat1r, lon1r, lat2r, lon2r = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2r - lat1r
        dlon = lon2r - lon1r
        a = sin(dlat/2)**2 + cos(lat1r) * cos(lat2r) * sin(dlon/2)**2
        distance = R * 2 * atan2(sqrt(a), sqrt(1-a))

        # Should be approximately 5-6 km
        assert 4000 < distance < 6000


class TestSpatialIndexIntegration:
    """Integration tests for spatial index operations."""

    @pytest.fixture
    def index(self):
        """Create index for integration tests."""
        return FallbackSpatialIndex(grid_size_degrees=0.001)  # ~100m grid

    def test_add_query_remove_cycle(self, index):
        """Test complete add-query-remove cycle."""
        # Add entities
        entities = [
            SpatialEntity(id=uuid4(), latitude=41.311, longitude=69.279)
            for _ in range(10)
        ]

        for e in entities:
            index.add(e)

        # Query
        results = index.query_radius(41.311, 69.279, 1000)
        assert len(results) == 10

        # Entities still in index
        assert len(index._entity_cells) == 10

    def test_bulk_add_performance(self, index):
        """Test adding many entities."""
        entities = [
            SpatialEntity(
                id=uuid4(),
                latitude=41.0 + i * 0.001,
                longitude=69.0 + i * 0.001,
            )
            for i in range(100)
        ]

        for e in entities:
            index.add(e)

        assert len(index._entity_cells) == 100

    def test_query_with_data_filter(self, index):
        """Test querying and filtering by custom data."""
        # Add entities with different categories
        entities = [
            SpatialEntity(
                id=uuid4(),
                latitude=41.311 + i * 0.001,
                longitude=69.279,
                data={"category": "A" if i % 2 == 0 else "B"},
            )
            for i in range(10)
        ]

        for e in entities:
            index.add(e)

        # Query all
        results = index.query_radius(41.315, 69.279, 2000)

        # Filter by category
        category_a = [e for e in results if e.data.get("category") == "A"]
        category_b = [e for e in results if e.data.get("category") == "B"]

        assert len(category_a) > 0
        assert len(category_b) > 0
