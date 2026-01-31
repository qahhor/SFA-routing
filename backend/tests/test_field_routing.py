"""
Tests for Routing API.

TSP - Traveling Salesperson Problem
VRPC - Vehicle Routing Problem with Capacity Constraints
"""

import pytest

from app.schemas.field_routing import (
    DayRoute,
    ErrorCode,
    Intensity,
    StartLocation,
    TSPAutoResponse,
    TSPKind,
    TSPLocation,
    TSPRequest,
    TSPSingleResponse,
    VehicleType,
    VRPCDepot,
    VRPCLoop,
    VRPCPoint,
    VRPCRequest,
    VRPCResponse,
    VRPCUrls,
    VRPCVehicle,
    WeekPlan,
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

    def test_intensity_enum(self):
        """Test intensity enum values."""
        assert Intensity.THREE_TIMES_A_WEEK == "THREE_TIMES_A_WEEK"
        assert Intensity.TWO_TIMES_A_WEEK == "TWO_TIMES_A_WEEK"
        assert Intensity.ONCE_A_WEEK == "ONCE_A_WEEK"
        assert Intensity.ONCE_IN_TWO_WEEKS == "ONCE_IN_TWO_WEEKS"
        assert Intensity.ONCE_A_MONTH == "ONCE_A_MONTH"

    def test_tsp_location_creation(self):
        """Test TSP location creation."""
        loc = TSPLocation(
            id="loc-1",
            latitude=41.311081,
            longitude=69.279737,
            visitDuration=15,
            intensity=Intensity.ONCE_A_WEEK,
        )
        assert loc.id == "loc-1"
        assert loc.latitude == 41.311081
        assert loc.longitude == 69.279737
        assert loc.visitDuration == 15
        assert loc.intensity == Intensity.ONCE_A_WEEK
        assert loc.workingDays == [1, 2, 3, 4, 5, 6]

    def test_tsp_location_with_working_days(self):
        """Test TSP location with custom working days."""
        loc = TSPLocation(
            id="loc-2",
            latitude=41.321081,
            longitude=69.289737,
            visitDuration=20,
            intensity=Intensity.TWO_TIMES_A_WEEK,
            workingDays=[1, 2, 3, 4, 5],
        )
        assert loc.workingDays == [1, 2, 3, 4, 5]

    def test_tsp_location_invalid_working_days(self):
        """Test TSP location with invalid working days."""
        with pytest.raises(ValueError):
            TSPLocation(
                id="loc-1",
                latitude=41.311081,
                longitude=69.279737,
                visitDuration=15,
                intensity=Intensity.ONCE_A_WEEK,
                workingDays=[0, 7],  # Invalid: 0 and 7 are not valid days
            )

    def test_start_location_creation(self):
        """Test start location creation."""
        start = StartLocation(latitude=41.311081, longitude=69.279737)
        assert start.latitude == 41.311081
        assert start.longitude == 69.279737

    def test_tsp_request_creation(self):
        """Test TSP request creation."""
        request = TSPRequest(
            kind=TSPKind.AUTO,
            locations=[
                TSPLocation(
                    id="loc-1",
                    latitude=41.311081,
                    longitude=69.279737,
                    visitDuration=15,
                    intensity=Intensity.ONCE_A_WEEK,
                )
            ],
        )
        assert request.kind == TSPKind.AUTO
        assert len(request.locations) == 1
        assert request.startLocation is None

    def test_tsp_request_with_start_location(self):
        """Test TSP request with start location."""
        request = TSPRequest(
            kind=TSPKind.SINGLE,
            locations=[
                TSPLocation(
                    id="loc-1",
                    latitude=41.311081,
                    longitude=69.279737,
                    visitDuration=15,
                    intensity=Intensity.ONCE_A_WEEK,
                )
            ],
            startLocation=StartLocation(
                latitude=41.300000, longitude=69.260000
            ),
        )
        assert request.startLocation is not None
        assert request.startLocation.latitude == 41.300000

    def test_day_route_creation(self):
        """Test day route creation."""
        route = DayRoute(
            dayNumber=1,
            route=["loc-1", "loc-2", "loc-3"],
            totalDuration=180,
            totalDistance=22.5,
        )
        assert route.dayNumber == 1
        assert route.route == ["loc-1", "loc-2", "loc-3"]
        assert route.totalDuration == 180
        assert route.totalDistance == 22.5

    def test_week_plan_creation(self):
        """Test week plan creation."""
        week = WeekPlan(
            weekNumber=1,
            days=[
                DayRoute(
                    dayNumber=1,
                    route=["loc-1", "loc-2"],
                    totalDuration=120,
                    totalDistance=15.0,
                ),
                DayRoute(
                    dayNumber=3,
                    route=["loc-3", "loc-4"],
                    totalDuration=100,
                    totalDistance=12.0,
                ),
            ],
        )
        assert week.weekNumber == 1
        assert len(week.days) == 2

    def test_tsp_single_response(self):
        """Test TSP single response."""
        response = TSPSingleResponse(
            code=ErrorCode.SUCCESS,
            weeks=[
                WeekPlan(
                    weekNumber=1,
                    days=[
                        DayRoute(
                            dayNumber=1,
                            route=["loc-1", "loc-2"],
                            totalDuration=120,
                            totalDistance=15.0,
                        )
                    ],
                )
            ],
        )
        assert response.code == 100
        assert len(response.weeks) == 1
        assert response.weeks[0].weekNumber == 1

    def test_tsp_auto_response(self):
        """Test TSP auto response."""
        response = TSPAutoResponse(
            code=ErrorCode.SUCCESS,
            plans=[
                [
                    WeekPlan(
                        weekNumber=1,
                        days=[
                            DayRoute(
                                dayNumber=1,
                                route=["loc-1", "loc-2"],
                                totalDuration=120,
                                totalDistance=15.0,
                            )
                        ],
                    )
                ]
            ],
        )
        assert response.code == 100
        assert len(response.plans) == 1

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

    def test_vrpc_depot_invalid_coordinate(self):
        """Test VRPC depot with invalid coordinate."""
        with pytest.raises(ValueError):
            VRPCDepot(lat="invalid", lng="69.279737")

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
            locations=[
                TSPLocation(
                    id="loc-1",
                    latitude=41.311081,
                    longitude=69.279737,
                    visitDuration=15,
                    intensity=Intensity.ONCE_A_WEEK,
                ),
                TSPLocation(
                    id="loc-2",
                    latitude=41.321081,
                    longitude=69.289737,
                    visitDuration=15,
                    intensity=Intensity.TWO_TIMES_A_WEEK,
                ),
                TSPLocation(
                    id="loc-3",
                    latitude=41.301081,
                    longitude=69.269737,
                    visitDuration=15,
                    intensity=Intensity.ONCE_A_MONTH,
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_tsp_single_solve(self, sample_tsp_request):
        """Test TSP single solve returns valid response."""
        from app.services.planning.field_routing import TSPService

        service = TSPService()
        result = await service.solve(sample_tsp_request)

        assert isinstance(result, TSPSingleResponse)
        assert result.code == ErrorCode.SUCCESS
        assert result.weeks is not None
        assert len(result.weeks) == 4  # 4 weeks

    @pytest.mark.asyncio
    async def test_tsp_auto_solve(self):
        """Test TSP auto solve with clustering."""
        from app.services.planning.field_routing import TSPService

        request = TSPRequest(
            kind=TSPKind.AUTO,
            locations=[
                TSPLocation(
                    id=f"loc-{i}",
                    latitude=41.311081 + (i * 0.01),
                    longitude=69.279737 + (i * 0.01),
                    visitDuration=15,
                    intensity=Intensity.ONCE_A_WEEK,
                )
                for i in range(10)
            ],
        )

        service = TSPService()
        result = await service.solve(request)

        assert isinstance(result, TSPAutoResponse)
        assert result.code == ErrorCode.SUCCESS
        assert result.plans is not None
        assert len(result.plans) > 0

    @pytest.mark.asyncio
    async def test_tsp_empty_locations(self):
        """Test TSP with empty locations returns error."""
        # Pydantic validation should fail for empty list
        with pytest.raises(ValueError):
            TSPRequest(kind=TSPKind.SINGLE, locations=[])

    @pytest.mark.asyncio
    async def test_tsp_with_start_location(self):
        """Test TSP with start location."""
        from app.services.planning.field_routing import TSPService

        request = TSPRequest(
            kind=TSPKind.SINGLE,
            locations=[
                TSPLocation(
                    id="loc-1",
                    latitude=41.311081,
                    longitude=69.279737,
                    visitDuration=15,
                    intensity=Intensity.ONCE_A_WEEK,
                )
            ],
            startLocation=StartLocation(
                latitude=41.300000, longitude=69.260000
            ),
        )

        service = TSPService()
        result = await service.solve(request)

        assert result.code == ErrorCode.SUCCESS


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
            # Missing truck URL
            urls=VRPCUrls(car="https://osrm-car.example.com"),
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
            vehicles=[
                VRPCVehicle(type=VehicleType.TRUCK, capacity=50)
            ],  # Not enough capacity
            urls=VRPCUrls(truck="https://osrm-truck.example.com"),
        )

        service = VRPCService()
        result = await service.solve(request)

        assert result.code == ErrorCode.WEIGHT_EXCEEDS_CAPACITY
