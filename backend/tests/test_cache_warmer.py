"""
Tests for Cache Warming Service module.

Tests cover:
- CacheWarmer initialization
- warm_all orchestration
- warm_distance_matrices
- warm_reference_data
- warm_daily_plans
- warm_route_geometries
- Cache invalidation methods
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date, time
from uuid import uuid4

from app.services.caching.cache_warmer import CacheWarmer


class MockAgent:
    """Mock Agent model."""

    def __init__(
        self,
        agent_id=None,
        name="Test Agent",
        external_id="EXT001",
        is_active=True,
        clients=None,
    ):
        self.id = agent_id or uuid4()
        self.name = name
        self.external_id = external_id
        self.is_active = is_active
        self.start_latitude = 41.311
        self.start_longitude = 69.279
        self.work_start = time(9, 0)
        self.work_end = time(18, 0)
        self.max_visits_per_day = 15
        self.clients = clients or []


class MockClient:
    """Mock Client model."""

    def __init__(self, client_id=None, agent_id=None, is_active=True):
        self.id = client_id or uuid4()
        self.name = "Test Client"
        self.external_id = "CLI001"
        self.latitude = 41.320
        self.longitude = 69.290
        self.category = MagicMock(value="A")
        self.agent_id = agent_id
        self.is_active = is_active
        self.visit_duration_minutes = 15
        self.time_window_start = time(9, 0)
        self.time_window_end = time(18, 0)


class MockVehicle:
    """Mock Vehicle model."""

    def __init__(self, vehicle_id=None):
        self.id = vehicle_id or uuid4()
        self.name = "Test Vehicle"
        self.license_plate = "01A123BC"
        self.capacity_kg = 1000
        self.capacity_volume_m3 = 10
        self.is_active = True


class MockVisitPlan:
    """Mock VisitPlan model."""

    def __init__(self, plan_id=None, agent_id=None, client_id=None):
        self.id = plan_id or uuid4()
        self.agent_id = agent_id or uuid4()
        self.client_id = client_id or uuid4()
        self.sequence_number = 1
        self.planned_time = time(10, 0)
        self.status = MagicMock(value="planned")
        self.client = MockClient(client_id=self.client_id)


class MockDeliveryRoute:
    """Mock DeliveryRoute model."""

    def __init__(self, route_id=None):
        self.id = route_id or uuid4()
        self.stops = []


class TestCacheWarmer:
    """Tests for CacheWarmer class."""

    @pytest.fixture
    def mock_db_session_factory(self):
        """Create mock database session factory."""
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock()
        session.execute = AsyncMock()

        def factory():
            return session

        return factory

    @pytest.fixture
    def mock_cache_service(self):
        """Create mock cache service."""
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        cache.mset = AsyncMock()
        cache.delete_pattern = AsyncMock(return_value=1)
        return cache

    @pytest.fixture
    def mock_osrm_client(self):
        """Create mock OSRM client."""
        osrm = MagicMock()
        osrm.get_table = AsyncMock()
        return osrm

    @pytest.fixture
    def warmer(self, mock_db_session_factory, mock_cache_service, mock_osrm_client):
        """Create CacheWarmer instance."""
        return CacheWarmer(
            db_session_factory=mock_db_session_factory,
            cache_service=mock_cache_service,
            osrm_client=mock_osrm_client,
        )

    def test_initialization(self, warmer, mock_db_session_factory, mock_cache_service, mock_osrm_client):
        """Test warmer initialization."""
        assert warmer.db_session_factory == mock_db_session_factory
        assert warmer.cache == mock_cache_service
        assert warmer.osrm == mock_osrm_client

    @pytest.mark.asyncio
    async def test_warm_all_success(self, warmer):
        """Test warm_all orchestrates all warming tasks."""
        # Mock individual warming methods
        warmer.warm_distance_matrices = AsyncMock(return_value={"warmed": 5})
        warmer.warm_reference_data = AsyncMock(return_value={"agents": 10})
        warmer.warm_daily_plans = AsyncMock(return_value={"generated": 8})
        warmer.warm_route_geometries = AsyncMock(return_value={"warmed": 3})

        result = await warmer.warm_all()

        assert "distance_matrices" in result
        assert "reference_data" in result
        assert "daily_plans" in result
        assert "route_geometries" in result
        assert "duration_seconds" in result

        warmer.warm_distance_matrices.assert_called_once()
        warmer.warm_reference_data.assert_called_once()
        warmer.warm_daily_plans.assert_called_once()
        warmer.warm_route_geometries.assert_called_once()

    @pytest.mark.asyncio
    async def test_warm_all_handles_error(self, warmer):
        """Test warm_all handles errors gracefully."""
        warmer.warm_distance_matrices = AsyncMock(side_effect=Exception("DB Error"))

        result = await warmer.warm_all()

        assert "error" in result
        assert "DB Error" in result["error"]

    @pytest.mark.asyncio
    async def test_warm_distance_matrices_no_agents(self, warmer, mock_db_session_factory):
        """Test warming matrices with no active agents."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        session = mock_db_session_factory()
        session.execute.return_value = mock_result

        with patch.object(warmer, 'db_session_factory', return_value=session):
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock()

            result = await warmer.warm_distance_matrices()

        assert result["warmed"] == 0

    @pytest.mark.asyncio
    async def test_warm_distance_matrices_skips_small_client_count(self, warmer, mock_db_session_factory, mock_osrm_client):
        """Test warming skips agents with few clients."""
        # Agent with only 5 clients (less than 10 threshold)
        agent = MockAgent()
        agent.clients = [MockClient() for _ in range(5)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [agent]

        session = mock_db_session_factory()
        session.execute.return_value = mock_result
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock()

        with patch.object(warmer, 'db_session_factory', return_value=session):
            result = await warmer.warm_distance_matrices()

        assert result["skipped"] == 1
        assert result["warmed"] == 0
        mock_osrm_client.get_table.assert_not_called()

    @pytest.mark.asyncio
    async def test_warm_distance_matrices_warms_large_client_count(self, warmer, mock_db_session_factory, mock_osrm_client):
        """Test warming proceeds for agents with many clients."""
        # Agent with 15 clients (more than 10 threshold)
        agent = MockAgent()
        agent.clients = [MockClient() for _ in range(15)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [agent]

        session = mock_db_session_factory()
        session.execute.return_value = mock_result
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock()

        with patch.object(warmer, 'db_session_factory', return_value=session):
            result = await warmer.warm_distance_matrices()

        assert result["warmed"] == 1
        mock_osrm_client.get_table.assert_called_once()

    @pytest.mark.asyncio
    async def test_warm_reference_data_agents(self, warmer, mock_db_session_factory, mock_cache_service):
        """Test warming reference data for agents."""
        agents = [MockAgent() for _ in range(3)]

        session = mock_db_session_factory()
        session.execute = AsyncMock(side_effect=[
            # Agents query result
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=agents)))),
            # Clients query result
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            # Vehicles query result
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
        ])
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock()

        with patch.object(warmer, 'db_session_factory', return_value=session):
            result = await warmer.warm_reference_data()

        assert result["agents"] == 3
        mock_cache_service.mset.assert_called()

    @pytest.mark.asyncio
    async def test_warm_reference_data_all_types(self, warmer, mock_db_session_factory, mock_cache_service):
        """Test warming all reference data types."""
        agents = [MockAgent() for _ in range(2)]
        clients = [MockClient() for _ in range(5)]
        vehicles = [MockVehicle() for _ in range(3)]

        session = mock_db_session_factory()
        session.execute = AsyncMock(side_effect=[
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=agents)))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=clients)))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=vehicles)))),
        ])
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock()

        with patch.object(warmer, 'db_session_factory', return_value=session):
            result = await warmer.warm_reference_data()

        assert result["agents"] == 2
        assert result["clients"] == 5
        assert result["vehicles"] == 3

    @pytest.mark.asyncio
    async def test_warm_daily_plans_uses_cache(self, warmer, mock_db_session_factory, mock_cache_service):
        """Test warming daily plans checks cache first."""
        agent = MockAgent()
        plans = [MockVisitPlan(agent_id=agent.id) for _ in range(3)]

        # First execute returns agents, second returns plans
        session = mock_db_session_factory()
        session.execute = AsyncMock(side_effect=[
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[agent])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=plans)))),
        ])
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock()

        # Cache miss
        mock_cache_service.get.return_value = None

        with patch.object(warmer, 'db_session_factory', return_value=session):
            result = await warmer.warm_daily_plans()

        assert result["generated"] == 1
        mock_cache_service.set.assert_called()

    @pytest.mark.asyncio
    async def test_warm_daily_plans_cache_hit(self, warmer, mock_db_session_factory, mock_cache_service):
        """Test warming daily plans skips when cached."""
        agent = MockAgent()

        session = mock_db_session_factory()
        session.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[agent])))
        ))
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock()

        # Cache hit
        mock_cache_service.get.return_value = {"existing": "data"}

        with patch.object(warmer, 'db_session_factory', return_value=session):
            result = await warmer.warm_daily_plans()

        assert result["already_cached"] == 1
        assert result["generated"] == 0

    @pytest.mark.asyncio
    async def test_warm_route_geometries_no_routes(self, warmer, mock_db_session_factory):
        """Test warming route geometries with no routes."""
        session = mock_db_session_factory()
        session.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ))
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock()

        with patch.object(warmer, 'db_session_factory', return_value=session):
            result = await warmer.warm_route_geometries()

        assert result["warmed"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_invalidate_agent_caches(self, warmer, mock_cache_service):
        """Test agent cache invalidation."""
        agent_id = uuid4()

        result = await warmer.invalidate_agent_caches(agent_id)

        assert result >= 0
        mock_cache_service.delete_pattern.assert_called()

    @pytest.mark.asyncio
    async def test_invalidate_client_caches(self, warmer, mock_cache_service):
        """Test client cache invalidation."""
        client_id = uuid4()
        agent_id = uuid4()

        result = await warmer.invalidate_client_caches(client_id, agent_id)

        assert result >= 0
        # Should call delete_pattern multiple times for different patterns
        assert mock_cache_service.delete_pattern.call_count >= 1

    @pytest.mark.asyncio
    async def test_invalidate_client_caches_no_agent(self, warmer, mock_cache_service):
        """Test client cache invalidation without agent ID."""
        client_id = uuid4()

        result = await warmer.invalidate_client_caches(client_id)

        assert result >= 0
        mock_cache_service.delete_pattern.assert_called()


class TestCacheWarmerIntegration:
    """Integration tests for cache warmer."""

    @pytest.fixture
    def mock_db_session_factory(self):
        """Create mock database session factory."""
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock()
        session.execute = AsyncMock()
        return lambda: session

    @pytest.fixture
    def mock_cache_service(self):
        """Create mock cache service."""
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        cache.mset = AsyncMock()
        cache.delete_pattern = AsyncMock(return_value=1)
        return cache

    @pytest.fixture
    def mock_osrm_client(self):
        """Create mock OSRM client."""
        osrm = MagicMock()
        osrm.get_table = AsyncMock()
        return osrm

    @pytest.mark.asyncio
    async def test_full_warming_cycle(
        self,
        mock_db_session_factory,
        mock_cache_service,
        mock_osrm_client,
    ):
        """Test complete warming cycle."""
        warmer = CacheWarmer(
            db_session_factory=mock_db_session_factory,
            cache_service=mock_cache_service,
            osrm_client=mock_osrm_client,
        )

        # Setup: agents with clients
        agents = [MockAgent() for _ in range(2)]
        for agent in agents:
            agent.clients = [MockClient(agent_id=agent.id) for _ in range(15)]

        clients = [MockClient() for _ in range(10)]
        vehicles = [MockVehicle() for _ in range(5)]
        plans = [MockVisitPlan() for _ in range(8)]
        routes = [MockDeliveryRoute() for _ in range(3)]

        # Setup session responses
        session = mock_db_session_factory()

        # Create sequential responses for different queries
        execute_results = [
            # warm_distance_matrices - agents
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=agents)))),
            # warm_reference_data - agents
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=agents)))),
            # warm_reference_data - clients
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=clients)))),
            # warm_reference_data - vehicles
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=vehicles)))),
            # warm_daily_plans - agents
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=agents)))),
            # warm_daily_plans - plans for agent 1
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=plans[:4])))),
            # warm_daily_plans - plans for agent 2
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=plans[4:])))),
            # warm_route_geometries - routes
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=routes)))),
        ]

        session.execute = AsyncMock(side_effect=execute_results)

        with patch.object(warmer, 'db_session_factory', return_value=session):
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock()

            result = await warmer.warm_all()

        assert "duration_seconds" in result
        assert result.get("error") is None
