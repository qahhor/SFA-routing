"""
Tests for Routing API.

TSP - Traveling Salesperson Problem
VRPC - Vehicle Routing Problem with Capacity Constraints
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.field_routing import (
    ErrorCode,
    Profile,
    TSPAutoResponse,
    TSPData,
    TSPKind,
    TSPLocation,
    TSPRequest,
    TSPSingleResponse,
    VehicleType,
    VisitIntensity,
    VRPCDepot,
    VRPCLoop,
    VRPCPoint,
    VRPCRequest,
    VRPCResponse,
    VRPCUrls,
    VRPCVehicle,
)


# ============================================================
# TSP Schema Tests
# ============================================================


class TestTSPSchemas:
    """Tests for TSP Pydantic schemas."""

    def test_tsp_kind_enum(self):
        """Test TSP kind enum values."""
        assert TSPKind.AUTO == "auto"
        assert TSPKind.SINGLE == "single"
        assert TSPKind.MANUAL == "manual"

    def test_visit_intensity_enum(self):
        """Test visit intensity enum values."""
        assert VisitIntensity.THREE_TIMES_A_WEEK == "THREE_TIMES_A_WEEK"
        assert VisitIntensity.TWICE_A_WEEK == "TWICE_A_WEEK"
        assert VisitIntensity.ONCE_A_WEEK == "ONCE_A_WEEK"
        assert VisitIntensity.TWICE_A_MONTH == "TWICE_A_MONTH"
        assert VisitIntensity.ONCE_A_MONTH == "ONCE_A_MONTH"

    def test_profile_enum(self):
        """Test profile enum values."""
        assert Profile.DRIVING == "driving"
        assert Profile.WALKING == "walking"
        assert Profile.CYCLING == "cycling"

    def test_tsp_location_creation(self):
        """Test TSP location creation."""
        loc = TSPLocation(
            lat="41.311081",
            lng="69.279737",
            visit_duration=600,
            visit_intensity=VisitIntensity.ONCE_A_WEEK,
        )
        assert loc.lat == "41.311081"
        assert loc.lng == "69.279737"
        assert loc.visit_duration == 600
        assert loc.visit_intensity == VisitIntensity.ONCE_A_WEEK

    def test_tsp_location_invalid_coordinate(self):
        """Test TSP location with invalid coordinate."""
        with pytest.raises(ValueError):
            TSPLocation(
                lat="invalid",
                lng="69.279737",
                visit_duration=600,
                visit_intensity=VisitIntensity.ONCE_A_WEEK,
            )

    def test_tsp_data_creation(self):
        """Test TSP data creation."""
        data = TSPData(
            locations=[
                TSPLocation(
                    lat="41.311081",
                    lng="69.279737",
                    visit_duration=600,
                    visit_intensity=VisitIntensity.ONCE_A_WEEK,
                )
            ],
            map_url="https://osrm.example.com",
            profile=Profile.DRIVING,
            max_visit_limit_per_day=20,
            working_seconds_per_day=25000,
        )
        assert len(data.locations) == 1
        assert data.profile == Profile.DRIVING
        assert data.max_visit_limit_per_day == 20

    def test_tsp_request_creation(self):
        """Test TSP request creation."""
        request = TSPRequest(
            kind=TSPKind.AUTO,
            data=TSPData(
                locations=[
                    TSPLocation(
                        lat="41.311081",
                        lng="69.279737",
                        visit_duration=600,
                        visit_intensity=VisitIntensity.ONCE_A_WEEK,
                    )
                ],
                map_url="https://osrm.example.com",
                profile=Profile.DRIVING,
                max_visit_limit_per_day=20,
                working_seconds_per_day=25000,
            ),
        )
        assert request.kind == TSPKind.AUTO

    def test_tsp_auto_response(self):
        """Test TSP auto response."""
        response = TSPAutoResponse(
            code=ErrorCode.SUCCESS,
            plans=[[[[0, 1, 2], [3, 4]], [[0, 1], [2, 3, 4]]]],
        )
        assert response.code == 100
        assert len(response.plans) == 1

    def test_tsp_single_response(self):
        """Test TSP single response."""
        response = TSPSingleResponse(
            code=ErrorCode.SUCCESS,
            routes=[[[0, 1, 2], [3, 4]], [[0, 1], [2, 3, 4]]],
            ignored_locations=[5, 6],
        )
        assert response.code == 100
        assert len(response.routes) == 2
        assert response.ignored_locations == [5, 6]

    def test_tsp_error_response(self):
        """Test TSP error response."""
        response = TSPSingleResponse(
            code=ErrorCode.NO_SOLUTION_FOUND,
            error_text="No solution found to the problem",
        )
        assert response.code == 109
        assert response.error_text == "No solution found to the problem"


# ============================================================
# VRPC Schema Tests
# ============================================================


class TestVRPCSchemas:
    """Tests for VRPC Pydantic schemas."""

    def test_vehicle_type_enum(self):
        """Test vehicle type enum values."""
        assert VehicleType.CAR == "car"
        assert VehicleType.TRUCK == "truck"
        assert VehicleType.WALKING == "walking"
        assert VehicleType.CYCLING == "cycling"

    def test_vrpc_depot_creation(self):
        """Test VRPC depot creation."""
        depot = VRPCDepot(lat="41.311081", lng="69.279737")
        assert depot.lat == "41.311081"
        assert depot.lng == "69.279737"

    def test_vrpc_point_creation(self):
        """Test VRPC point creation."""
        point = VRPCPoint(lat="41.311081", lng="69.279737", weight=12.5)
        assert point.lat == "41.311081"
        assert point.weight == 12.5

    def test_vrpc_vehicle_creation(self):
        """Test VRPC vehicle creation."""
        vehicle = VRPCVehicle(type=VehicleType.TRUCK, capacity=100)
        assert vehicle.type == VehicleType.TRUCK
        assert vehicle.capacity == 100

    def test_vrpc_urls_creation(self):
        """Test VRPC URLs creation."""
        urls = VRPCUrls(
            car="https://osrm-car.example.com",
            truck="https://osrm-truck.example.com",
        )
        assert urls.car == "https://osrm-car.example.com"
        assert urls.truck == "https://osrm-truck.example.com"
        assert urls.walking is None

    def test_vrpc_request_creation(self):
        """Test VRPC request creation."""
        request = VRPCRequest(
            depot=VRPCDepot(lat="41.311081", lng="69.279737"),
            points=[
                VRPCPoint(lat="41.321", lng="69.289", weight=10),
                VRPCPoint(lat="41.301", lng="69.269", weight=15),
            ],
            vehicles=[VRPCVehicle(type=VehicleType.TRUCK, capacity=100)],
            max_cycle_distance=75000,
            global_span_coefficient=30,
            urls=VRPCUrls(truck="https://osrm-truck.example.com"),
        )
        assert len(request.points) == 2
        assert len(request.vehicles) == 1
        assert request.max_cycle_distance == 75000

    def test_vrpc_loop_creation(self):
        """Test VRPC loop creation."""
        loop = VRPCLoop(route=[0, 2, 1], distance=12423.5, duration=3600.0)
        assert loop.route == [0, 2, 1]
        assert loop.distance == 12423.5
        assert loop.duration == 3600.0

    def test_vrpc_response_success(self):
        """Test VRPC success response."""
        response = VRPCResponse(
            code=ErrorCode.SUCCESS,
            vehicles=[
                [VRPCLoop(route=[0, 1, 2], distance=5000, duration=600)],
                [VRPCLoop(route=[3, 4], distance=3000, duration=400)],
            ],
            total_distance=8000,
            total_duration=1000,
        )
        assert response.code == 100
        assert len(response.vehicles) == 2
        assert response.total_distance == 8000

    def test_vrpc_response_error(self):
        """Test VRPC error response."""
        response = VRPCResponse(
            code=ErrorCode.WEIGHT_EXCEEDS_CAPACITY,
            error_text="Total weight exceeds total capacity",
        )
        assert response.code == 106
        assert "weight" in response.error_text.lower()


# ============================================================
# Error Code Tests
# ============================================================


class TestErrorCodes:
    """Tests for error code definitions."""

    def test_error_codes(self):
        """Test error code values."""
        assert ErrorCode.SUCCESS == 100
        assert ErrorCode.INVALID_INPUT_FORMAT == 101
        assert ErrorCode.UNSUPPORTED_VEHICLE_TYPE == 102
        assert ErrorCode.URL_NOT_FOUND_FOR_VEHICLE == 103
        assert ErrorCode.OSRM_CONNECTION_ERROR == 104
        assert ErrorCode.OSRM_MATRIX_ERROR == 105
        assert ErrorCode.WEIGHT_EXCEEDS_CAPACITY == 106
        assert ErrorCode.ARC_COST_NOT_SET == 107
        assert ErrorCode.TIME_LIMIT_REACHED == 108
        assert ErrorCode.NO_SOLUTION_FOUND == 109
        assert ErrorCode.UNEXPECTED_ERROR == 110
        assert ErrorCode.OUT_OF_MEMORY == 111


# ============================================================
# TSP Service Tests
# ============================================================


class TestTSPService:
    """Tests for TSP service."""

    @pytest.fixture
    def sample_tsp_request(self):
        """Sample TSP request."""
        return TSPRequest(
            kind=TSPKind.SINGLE,
            data=TSPData(
                locations=[
                    TSPLocation(
                        lat="41.311081",
                        lng="69.279737",
                        visit_duration=600,
                        visit_intensity=VisitIntensity.ONCE_A_WEEK,
                    ),
                    TSPLocation(
                        lat="41.321081",
                        lng="69.289737",
                        visit_duration=600,
                        visit_intensity=VisitIntensity.TWICE_A_WEEK,
                    ),
                    TSPLocation(
                        lat="41.301081",
                        lng="69.269737",
                        visit_duration=600,
                        visit_intensity=VisitIntensity.ONCE_A_MONTH,
                    ),
                ],
                map_url="https://osrm.example.com",
                profile=Profile.DRIVING,
                max_visit_limit_per_day=10,
                working_seconds_per_day=28800,
            ),
        )

    @pytest.mark.asyncio
    async def test_tsp_solve_returns_response(self, sample_tsp_request):
        """Test TSP solve returns valid response."""
        from app.services.planning.field_routing import TSPService

        with patch.object(TSPService, "_TSPService__init__", lambda self, x=None: None):
            service = TSPService()
            service.osrm = MagicMock()
            service.osrm.get_distance_matrix = AsyncMock(
                return_value=(
                    [[0, 100, 200], [100, 0, 150], [200, 150, 0]],
                    [[0, 1000, 2000], [1000, 0, 1500], [2000, 1500, 0]],
                )
            )

            result = await service.solve(sample_tsp_request)

            assert isinstance(result, TSPSingleResponse)
            assert result.code == ErrorCode.SUCCESS
            assert result.routes is not None

    @pytest.mark.asyncio
    async def test_tsp_manual_not_implemented(self):
        """Test TSP manual kind returns error."""
        from app.services.planning.field_routing import TSPService

        request = TSPRequest(
            kind=TSPKind.MANUAL,
            data=TSPData(
                locations=[
                    TSPLocation(
                        lat="41.311081",
                        lng="69.279737",
                        visit_duration=600,
                        visit_intensity=VisitIntensity.ONCE_A_WEEK,
                    )
                ],
                map_url="https://osrm.example.com",
                profile=Profile.DRIVING,
                max_visit_limit_per_day=10,
                working_seconds_per_day=28800,
            ),
        )

        service = TSPService()
        result = await service.solve(request)

        assert result.code == ErrorCode.INVALID_INPUT_FORMAT
        assert "not implemented" in result.error_text.lower()


# ============================================================
# VRPC Service Tests
# ============================================================


class TestVRPCService:
    """Tests for VRPC service."""

    @pytest.fixture
    def sample_vrpc_request(self):
        """Sample VRPC request."""
        return VRPCRequest(
            depot=VRPCDepot(lat="41.311081", lng="69.279737"),
            points=[
                VRPCPoint(lat="41.321081", lng="69.289737", weight=10),
                VRPCPoint(lat="41.301081", lng="69.269737", weight=15),
                VRPCPoint(lat="41.331081", lng="69.299737", weight=20),
            ],
            vehicles=[
                VRPCVehicle(type=VehicleType.TRUCK, capacity=100),
            ],
            urls=VRPCUrls(truck="https://osrm-truck.example.com"),
        )

    @pytest.mark.asyncio
    async def test_vrpc_solve_returns_response(self, sample_vrpc_request):
        """Test VRPC solve returns valid response."""
        from app.services.planning.field_routing import VRPCService

        service = VRPCService()
        service.osrm = MagicMock()
        service.osrm.get_distance_matrix = AsyncMock(
            return_value=(
                [[0, 100, 200, 300], [100, 0, 150, 250], [200, 150, 0, 100], [300, 250, 100, 0]],
                [[0, 1000, 2000, 3000], [1000, 0, 1500, 2500], [2000, 1500, 0, 1000], [3000, 2500, 1000, 0]],
            )
        )

        result = await service.solve(sample_vrpc_request)

        assert isinstance(result, VRPCResponse)
        assert result.code == ErrorCode.SUCCESS
        assert result.vehicles is not None
        assert result.total_distance is not None
        assert result.total_duration is not None

    @pytest.mark.asyncio
    async def test_vrpc_missing_url_for_vehicle_type(self):
        """Test VRPC returns error when URL is missing for vehicle type."""
        from app.services.planning.field_routing import VRPCService

        request = VRPCRequest(
            depot=VRPCDepot(lat="41.311081", lng="69.279737"),
            points=[VRPCPoint(lat="41.321081", lng="69.289737", weight=10)],
            vehicles=[VRPCVehicle(type=VehicleType.TRUCK, capacity=100)],
            urls=VRPCUrls(car="https://osrm-car.example.com"),  # Missing truck URL
        )

        service = VRPCService()
        result = await service.solve(request)

        assert result.code == ErrorCode.URL_NOT_FOUND_FOR_VEHICLE
        assert "truck" in result.error_text.lower()

    @pytest.mark.asyncio
    async def test_vrpc_weight_exceeds_capacity(self):
        """Test VRPC returns error when weight exceeds capacity."""
        from app.services.planning.field_routing import VRPCService

        request = VRPCRequest(
            depot=VRPCDepot(lat="41.311081", lng="69.279737"),
            points=[
                VRPCPoint(lat="41.321081", lng="69.289737", weight=100),
                VRPCPoint(lat="41.301081", lng="69.269737", weight=100),
            ],
            vehicles=[VRPCVehicle(type=VehicleType.TRUCK, capacity=50)],  # Not enough capacity
            urls=VRPCUrls(truck="https://osrm-truck.example.com"),
        )

        service = VRPCService()
        result = await service.solve(request)

        assert result.code == ErrorCode.WEIGHT_EXCEEDS_CAPACITY
