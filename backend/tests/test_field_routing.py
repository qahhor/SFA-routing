"""
Tests for Field Team Routing API.

Тесты для API маршрутизации полевых команд.
"""
import pytest
from datetime import date, time
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.field_routing import (
    FieldRoutingRequest,
    FieldRoutingResponse,
    RoutingMode,
    VisitPoint,
    Location,
    WorkingHours,
    AvailableHours,
)


# ============================================================
# Schema Validation Tests
# ============================================================


class TestFieldRoutingSchemas:
    """Tests for Pydantic schema validation."""

    def test_routing_mode_enum(self):
        """Test routing mode enum values."""
        assert RoutingMode.CAR == "car"
        assert RoutingMode.WALKING == "walking"

    def test_working_hours_validation(self):
        """Test working hours validation."""
        hours = WorkingHours(start=time(9, 0), end=time(17, 0))
        assert hours.start == time(9, 0)
        assert hours.end == time(17, 0)

    def test_working_hours_end_must_be_after_start(self):
        """Test that end time must be after start time."""
        with pytest.raises(ValueError, match="end must be after start"):
            WorkingHours(start=time(17, 0), end=time(9, 0))

    def test_location_validation(self):
        """Test location coordinate validation."""
        loc = Location(latitude=41.311081, longitude=69.279737)
        assert loc.latitude == 41.311081
        assert loc.longitude == 69.279737

    def test_location_invalid_latitude(self):
        """Test invalid latitude."""
        with pytest.raises(ValueError):
            Location(latitude=100.0, longitude=69.279737)

    def test_location_invalid_longitude(self):
        """Test invalid longitude."""
        with pytest.raises(ValueError):
            Location(latitude=41.311081, longitude=200.0)

    def test_visit_point_creation(self):
        """Test visit point creation with all fields."""
        visit = VisitPoint(
            id="POINT-001",
            location=Location(latitude=41.311081, longitude=69.279737),
            available_hours=AvailableHours(start=time(9, 0), end=time(18, 0)),
            service_time=20,
            manager_acceptance_time=5,
            priority=1,
        )
        assert visit.id == "POINT-001"
        assert visit.service_time == 20
        assert visit.manager_acceptance_time == 5
        assert visit.priority == 1

    def test_visit_point_default_values(self):
        """Test visit point default values."""
        visit = VisitPoint(
            id="POINT-002",
            location=Location(latitude=41.311081, longitude=69.279737),
            available_hours=AvailableHours(start=time(9, 0), end=time(18, 0)),
            priority=3,
        )
        assert visit.service_time == 15  # Default
        assert visit.manager_acceptance_time == 0  # Default

    def test_visit_point_priority_bounds(self):
        """Test visit point priority bounds (1-10)."""
        with pytest.raises(ValueError):
            VisitPoint(
                id="POINT-003",
                location=Location(latitude=41.311081, longitude=69.279737),
                available_hours=AvailableHours(start=time(9, 0), end=time(18, 0)),
                priority=0,  # Invalid: must be >= 1
            )

        with pytest.raises(ValueError):
            VisitPoint(
                id="POINT-003",
                location=Location(latitude=41.311081, longitude=69.279737),
                available_hours=AvailableHours(start=time(9, 0), end=time(18, 0)),
                priority=11,  # Invalid: must be <= 10
            )

    def test_field_routing_request_creation(self):
        """Test field routing request creation."""
        request = FieldRoutingRequest(
            working_days=4,
            working_hours=WorkingHours(start=time(9, 0), end=time(17, 0)),
            max_visits_per_day=12,
            routing_mode=RoutingMode.CAR,
            start_location=Location(latitude=41.311081, longitude=69.279737),
            visits=[
                VisitPoint(
                    id="POINT-001",
                    location=Location(latitude=41.328, longitude=69.255),
                    available_hours=AvailableHours(start=time(9, 0), end=time(18, 0)),
                    priority=1,
                )
            ],
        )
        assert request.working_days == 4
        assert request.max_visits_per_day == 12
        assert request.routing_mode == RoutingMode.CAR
        assert len(request.visits) == 1

    def test_field_routing_request_working_days_bounds(self):
        """Test working days bounds (1-14)."""
        with pytest.raises(ValueError):
            FieldRoutingRequest(
                working_days=0,  # Invalid: must be >= 1
                working_hours=WorkingHours(start=time(9, 0), end=time(17, 0)),
                max_visits_per_day=12,
                routing_mode=RoutingMode.CAR,
                visits=[
                    VisitPoint(
                        id="POINT-001",
                        location=Location(latitude=41.328, longitude=69.255),
                        available_hours=AvailableHours(start=time(9, 0), end=time(18, 0)),
                        priority=1,
                    )
                ],
            )

    def test_field_routing_request_max_visits_bounds(self):
        """Test max visits per day bounds (1-50)."""
        with pytest.raises(ValueError):
            FieldRoutingRequest(
                working_days=4,
                working_hours=WorkingHours(start=time(9, 0), end=time(17, 0)),
                max_visits_per_day=51,  # Invalid: must be <= 50
                routing_mode=RoutingMode.CAR,
                visits=[
                    VisitPoint(
                        id="POINT-001",
                        location=Location(latitude=41.328, longitude=69.255),
                        available_hours=AvailableHours(start=time(9, 0), end=time(18, 0)),
                        priority=1,
                    )
                ],
            )

    def test_field_routing_request_empty_visits(self):
        """Test that visits list cannot be empty."""
        with pytest.raises(ValueError):
            FieldRoutingRequest(
                working_days=4,
                working_hours=WorkingHours(start=time(9, 0), end=time(17, 0)),
                max_visits_per_day=12,
                routing_mode=RoutingMode.CAR,
                visits=[],  # Invalid: min_length=1
            )


# ============================================================
# Service Tests
# ============================================================


class TestFieldRoutingService:
    """Tests for FieldRoutingService."""

    @pytest.fixture
    def sample_field_routing_request(self):
        """Sample request for field routing."""
        return FieldRoutingRequest(
            working_days=3,
            working_hours=WorkingHours(start=time(9, 0), end=time(17, 0)),
            max_visits_per_day=10,
            routing_mode=RoutingMode.CAR,
            start_location=Location(latitude=41.311081, longitude=69.279737),
            visits=[
                VisitPoint(
                    id="POINT-001",
                    location=Location(latitude=41.328, longitude=69.255),
                    available_hours=AvailableHours(start=time(9, 0), end=time(18, 0)),
                    service_time=20,
                    manager_acceptance_time=5,
                    priority=1,
                ),
                VisitPoint(
                    id="POINT-002",
                    location=Location(latitude=41.295, longitude=69.220),
                    available_hours=AvailableHours(start=time(10, 0), end=time(16, 0)),
                    service_time=15,
                    priority=2,
                ),
                VisitPoint(
                    id="POINT-003",
                    location=Location(latitude=41.340, longitude=69.270),
                    available_hours=AvailableHours(start=time(8, 0), end=time(12, 0)),
                    service_time=30,
                    priority=3,
                ),
                VisitPoint(
                    id="POINT-004",
                    location=Location(latitude=41.305, longitude=69.295),
                    available_hours=AvailableHours(start=time(14, 0), end=time(18, 0)),
                    service_time=15,
                    priority=2,
                ),
                VisitPoint(
                    id="POINT-005",
                    location=Location(latitude=41.275, longitude=69.285),
                    available_hours=AvailableHours(start=time(9, 0), end=time(15, 0)),
                    service_time=25,
                    priority=1,
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_plan_route_returns_response(
        self, sample_field_routing_request, mock_osrm_client
    ):
        """Test that plan_route returns a valid response."""
        from app.services.planning.field_routing import FieldRoutingService

        service = FieldRoutingService(osrm_client=mock_osrm_client)
        result = await service.plan_route(
            request=sample_field_routing_request,
            start_date=date(2024, 2, 5),
        )

        assert isinstance(result, FieldRoutingResponse)
        assert result.total_visits > 0
        assert result.days_used > 0
        assert result.solver_used in ["vroom", "ortools", "genetic", "greedy"]
        assert result.computation_time_ms >= 0

    @pytest.mark.asyncio
    async def test_plan_route_respects_max_visits_per_day(
        self, mock_osrm_client
    ):
        """Test that max_visits_per_day is respected."""
        from app.services.planning.field_routing import FieldRoutingService

        # Create a request with 10 visits and max 3 per day
        visits = [
            VisitPoint(
                id=f"POINT-{i:03d}",
                location=Location(latitude=41.311 + i * 0.01, longitude=69.279 + i * 0.01),
                available_hours=AvailableHours(start=time(9, 0), end=time(18, 0)),
                priority=1,
            )
            for i in range(10)
        ]

        request = FieldRoutingRequest(
            working_days=5,
            working_hours=WorkingHours(start=time(9, 0), end=time(17, 0)),
            max_visits_per_day=3,
            routing_mode=RoutingMode.CAR,
            visits=visits,
        )

        service = FieldRoutingService(osrm_client=mock_osrm_client)
        result = await service.plan_route(request=request, start_date=date(2024, 2, 5))

        # Check that no day exceeds max_visits_per_day
        for daily in result.daily_summary:
            assert daily.visits_count <= 3

    @pytest.mark.asyncio
    async def test_plan_route_priority_ordering(
        self, sample_field_routing_request, mock_osrm_client
    ):
        """Test that higher priority visits are scheduled first."""
        from app.services.planning.field_routing import FieldRoutingService

        service = FieldRoutingService(osrm_client=mock_osrm_client)
        result = await service.plan_route(
            request=sample_field_routing_request,
            start_date=date(2024, 2, 5),
        )

        # Priority 1 visits should generally be in earlier days
        priority_1_visits = [
            v for v in result.scheduled_visits
            if v.visit_id in ["POINT-001", "POINT-005"]
        ]

        # At least some priority 1 visits should be on day 1
        day_1_priority_visits = [v for v in priority_1_visits if v.day_number == 1]
        assert len(day_1_priority_visits) > 0

    @pytest.mark.asyncio
    async def test_plan_route_unassigned_visits(self, mock_osrm_client):
        """Test handling of visits that cannot be assigned."""
        from app.services.planning.field_routing import FieldRoutingService

        # Create impossible scenario: many visits, few days, short hours
        visits = [
            VisitPoint(
                id=f"POINT-{i:03d}",
                location=Location(latitude=41.311 + i * 0.01, longitude=69.279 + i * 0.01),
                available_hours=AvailableHours(start=time(9, 0), end=time(10, 0)),  # Very short window
                service_time=60,  # Long service time
                priority=1,
            )
            for i in range(20)
        ]

        request = FieldRoutingRequest(
            working_days=1,  # Only 1 day
            working_hours=WorkingHours(start=time(9, 0), end=time(12, 0)),  # Only 3 hours
            max_visits_per_day=3,
            routing_mode=RoutingMode.CAR,
            visits=visits,
        )

        service = FieldRoutingService(osrm_client=mock_osrm_client)
        result = await service.plan_route(request=request, start_date=date(2024, 2, 5))

        # Some visits should be unassigned
        assert len(result.unassigned_visits) > 0

    @pytest.mark.asyncio
    async def test_plan_route_without_start_location(self, mock_osrm_client):
        """Test planning when no start location is provided."""
        from app.services.planning.field_routing import FieldRoutingService

        request = FieldRoutingRequest(
            working_days=2,
            working_hours=WorkingHours(start=time(9, 0), end=time(17, 0)),
            max_visits_per_day=10,
            routing_mode=RoutingMode.WALKING,
            start_location=None,  # No start location
            visits=[
                VisitPoint(
                    id="POINT-001",
                    location=Location(latitude=41.328, longitude=69.255),
                    available_hours=AvailableHours(start=time(9, 0), end=time(18, 0)),
                    priority=1,
                ),
                VisitPoint(
                    id="POINT-002",
                    location=Location(latitude=41.295, longitude=69.220),
                    available_hours=AvailableHours(start=time(10, 0), end=time(16, 0)),
                    priority=2,
                ),
            ],
        )

        service = FieldRoutingService(osrm_client=mock_osrm_client)
        result = await service.plan_route(request=request, start_date=date(2024, 2, 5))

        assert isinstance(result, FieldRoutingResponse)
        assert result.total_visits > 0


# ============================================================
# API Endpoint Tests
# ============================================================


class TestFieldRoutingAPI:
    """Tests for Field Routing API endpoints."""

    @pytest.fixture
    def sample_request_json(self):
        """Sample JSON request for API tests."""
        return {
            "working_days": 4,
            "working_hours": {"start": "09:00:00", "end": "17:00:00"},
            "max_visits_per_day": 12,
            "routing_mode": "car",
            "start_location": {"latitude": 41.311081, "longitude": 69.279737},
            "visits": [
                {
                    "id": "POINT-001",
                    "location": {"latitude": 41.328, "longitude": 69.255},
                    "available_hours": {"start": "09:00:00", "end": "18:00:00"},
                    "service_time": 20,
                    "manager_acceptance_time": 5,
                    "priority": 1,
                },
                {
                    "id": "POINT-002",
                    "location": {"latitude": 41.295, "longitude": 69.220},
                    "available_hours": {"start": "10:00:00", "end": "16:00:00"},
                    "service_time": 15,
                    "priority": 2,
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_plan_field_route_endpoint(self, client: AsyncClient, sample_request_json):
        """Test POST /field-routing/plan endpoint."""
        with patch("app.api.routes.field_routing.get_field_routing_service") as mock_get_service:
            # Create mock service
            mock_service = MagicMock()
            mock_service.plan_route = AsyncMock(
                return_value=FieldRoutingResponse(
                    total_visits=2,
                    total_distance=15.5,
                    total_duration=180,
                    days_used=1,
                    daily_summary=[],
                    scheduled_visits=[],
                    unassigned_visits=[],
                    solver_used="vroom",
                    computation_time_ms=150,
                )
            )
            mock_get_service.return_value = mock_service

            response = await client.post(
                "/api/v1/field-routing/plan",
                json=sample_request_json,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_visits"] == 2
            assert data["solver_used"] == "vroom"

    @pytest.mark.asyncio
    async def test_plan_field_route_with_start_date(self, client: AsyncClient, sample_request_json):
        """Test POST /field-routing/plan with start_date parameter."""
        with patch("app.api.routes.field_routing.get_field_routing_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.plan_route = AsyncMock(
                return_value=FieldRoutingResponse(
                    total_visits=2,
                    total_distance=15.5,
                    total_duration=180,
                    days_used=1,
                    daily_summary=[],
                    scheduled_visits=[],
                    unassigned_visits=[],
                    solver_used="vroom",
                    computation_time_ms=150,
                )
            )
            mock_get_service.return_value = mock_service

            response = await client.post(
                "/api/v1/field-routing/plan?start_date=2024-02-15",
                json=sample_request_json,
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_validate_field_routing_request_valid(
        self, client: AsyncClient, sample_request_json
    ):
        """Test POST /field-routing/validate with valid request."""
        response = await client.post(
            "/api/v1/field-routing/validate",
            json=sample_request_json,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["visits_count"] == 2

    @pytest.mark.asyncio
    async def test_validate_field_routing_request_invalid(self, client: AsyncClient):
        """Test POST /field-routing/validate with invalid request."""
        invalid_request = {
            "working_days": 0,  # Invalid: must be >= 1
            "working_hours": {"start": "09:00:00", "end": "17:00:00"},
            "max_visits_per_day": 12,
            "routing_mode": "car",
            "visits": [],  # Invalid: cannot be empty
        }

        response = await client.post(
            "/api/v1/field-routing/validate",
            json=invalid_request,
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_plan_field_route_invalid_routing_mode(self, client: AsyncClient):
        """Test POST /field-routing/plan with invalid routing mode."""
        invalid_request = {
            "working_days": 4,
            "working_hours": {"start": "09:00:00", "end": "17:00:00"},
            "max_visits_per_day": 12,
            "routing_mode": "bicycle",  # Invalid mode
            "visits": [
                {
                    "id": "POINT-001",
                    "location": {"latitude": 41.328, "longitude": 69.255},
                    "available_hours": {"start": "09:00:00", "end": "18:00:00"},
                    "priority": 1,
                }
            ],
        }

        response = await client.post(
            "/api/v1/field-routing/plan",
            json=invalid_request,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_plan_field_route_missing_required_fields(self, client: AsyncClient):
        """Test POST /field-routing/plan with missing required fields."""
        incomplete_request = {
            "working_days": 4,
            # Missing working_hours, max_visits_per_day, routing_mode, visits
        }

        response = await client.post(
            "/api/v1/field-routing/plan",
            json=incomplete_request,
        )

        assert response.status_code == 422


# ============================================================
# Integration Tests
# ============================================================


class TestFieldRoutingIntegration:
    """Integration tests for Field Routing."""

    @pytest.mark.asyncio
    async def test_full_planning_workflow(self, mock_osrm_client):
        """Test complete planning workflow from request to response."""
        from app.services.planning.field_routing import FieldRoutingService

        # Create a realistic request with multiple visits
        visits = []
        tashkent_points = [
            ("Супермаркет Макро", 41.328, 69.255, 9, 18, 1),
            ("Корзинка Юнусабад", 41.365, 69.285, 9, 14, 2),
            ("Гипермаркет Хамкор", 41.295, 69.220, 10, 15, 3),
            ("Магазин Барака", 41.340, 69.270, 8, 11, 1),
            ("Озиқ-овқат Центр", 41.275, 69.285, 11, 16, 2),
            ("Продукты 24", 41.305, 69.295, 14, 18, 3),
            ("Korzinka Чиланзар", 41.285, 69.205, 9, 13, 2),
            ("Минимаркет Сергели", 41.245, 69.215, 10, 17, 3),
        ]

        for i, (name, lat, lon, start_h, end_h, priority) in enumerate(tashkent_points):
            visits.append(
                VisitPoint(
                    id=f"POINT-{i + 1:03d}",
                    location=Location(latitude=lat, longitude=lon),
                    available_hours=AvailableHours(
                        start=time(start_h, 0),
                        end=time(end_h, 0),
                    ),
                    service_time=15,
                    manager_acceptance_time=5,
                    priority=priority,
                )
            )

        request = FieldRoutingRequest(
            working_days=3,
            working_hours=WorkingHours(start=time(9, 0), end=time(17, 0)),
            max_visits_per_day=4,
            routing_mode=RoutingMode.CAR,
            start_location=Location(latitude=41.311081, longitude=69.279737),
            visits=visits,
        )

        service = FieldRoutingService(osrm_client=mock_osrm_client)
        result = await service.plan_route(request=request, start_date=date(2024, 2, 5))

        # Verify response structure
        assert result.total_visits <= len(visits)
        assert result.days_used <= request.working_days
        assert len(result.daily_summary) == result.days_used
        assert len(result.scheduled_visits) == result.total_visits

        # Verify daily summaries
        total_visits_in_summaries = sum(d.visits_count for d in result.daily_summary)
        assert total_visits_in_summaries == result.total_visits

        # Verify scheduled visits have correct structure
        for visit in result.scheduled_visits:
            assert visit.day_number >= 1
            assert visit.day_number <= result.days_used
            assert visit.sequence_number >= 1
            assert visit.scheduled_start < visit.scheduled_end

    @pytest.mark.asyncio
    async def test_walking_mode_vs_car_mode(self, mock_osrm_client):
        """Test that walking mode produces valid results."""
        from app.services.planning.field_routing import FieldRoutingService

        visits = [
            VisitPoint(
                id="POINT-001",
                location=Location(latitude=41.311, longitude=69.279),
                available_hours=AvailableHours(start=time(9, 0), end=time(18, 0)),
                priority=1,
            ),
            VisitPoint(
                id="POINT-002",
                location=Location(latitude=41.315, longitude=69.282),
                available_hours=AvailableHours(start=time(9, 0), end=time(18, 0)),
                priority=2,
            ),
        ]

        request_walking = FieldRoutingRequest(
            working_days=1,
            working_hours=WorkingHours(start=time(9, 0), end=time(17, 0)),
            max_visits_per_day=10,
            routing_mode=RoutingMode.WALKING,
            visits=visits,
        )

        request_car = FieldRoutingRequest(
            working_days=1,
            working_hours=WorkingHours(start=time(9, 0), end=time(17, 0)),
            max_visits_per_day=10,
            routing_mode=RoutingMode.CAR,
            visits=visits,
        )

        service = FieldRoutingService(osrm_client=mock_osrm_client)

        result_walking = await service.plan_route(
            request=request_walking, start_date=date(2024, 2, 5)
        )
        result_car = await service.plan_route(
            request=request_car, start_date=date(2024, 2, 5)
        )

        # Both should produce valid results
        assert result_walking.total_visits > 0
        assert result_car.total_visits > 0
