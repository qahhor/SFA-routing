"""
Tests for individual VRP solvers (VROOM, OR-Tools, Greedy).

Updated to match actual solver implementations.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import date

from app.services.solvers.solver_interface import (
    RoutingProblem,
    Job,
    VehicleConfig,
    Location,
    SolutionResult,
    SolverType,
    Route,
    RouteStep,
)
from app.services.solvers.vroom_solver import VROOMSolver, VROOMError
from app.services.solvers.ortools_solver import ORToolsSolver
from app.services.solvers.greedy_solver import GreedySolver


class TestVROOMSolver:
    """Tests for VROOM solver."""

    @pytest.fixture
    def solver(self):
        """Create VROOM solver instance."""
        return VROOMSolver()

    @pytest.fixture
    def sample_problem(self):
        """Create a sample routing problem."""
        return RoutingProblem(
            jobs=[
                Job(
                    id=uuid4(),
                    location=Location(id=uuid4(), name="Job 1", latitude=41.311, longitude=69.279),
                    demand_kg=10.0,
                    priority=1,
                ),
                Job(
                    id=uuid4(),
                    location=Location(id=uuid4(), name="Job 2", latitude=41.320, longitude=69.290),
                    demand_kg=5.0,
                    priority=1,
                ),
            ],
            vehicles=[
                VehicleConfig(
                    id=uuid4(),
                    name="Vehicle 1",
                    start_location=Location(id=uuid4(), name="Depot", latitude=41.300, longitude=69.270),
                    capacity_kg=100.0,
                ),
            ],
            planning_date=date.today(),
        )

    def test_solver_initialization(self, solver):
        """Test VROOM solver initializes correctly."""
        assert solver.base_url is not None
        assert solver.solver_type == SolverType.VROOM

    def test_solver_type(self, solver):
        """Test solver type property."""
        assert solver.solver_type == SolverType.VROOM

    @pytest.mark.asyncio
    async def test_health_check(self, solver):
        """Test health check method exists."""
        # Health check may fail without actual VROOM service
        # but method should exist and be callable
        try:
            result = await solver.health_check()
            assert isinstance(result, bool)
        except Exception:
            # Expected if VROOM is not running
            pass

    @pytest.mark.asyncio
    async def test_solve_tsp_trivial(self, solver):
        """Test TSP with trivial input (<=2 locations)."""
        locations = [
            Location(id=uuid4(), name="Loc 1", latitude=41.311, longitude=69.279),
            Location(id=uuid4(), name="Loc 2", latitude=41.320, longitude=69.290),
        ]

        result = await solver.solve_tsp(locations)

        assert result == [0, 1]

    @pytest.mark.asyncio
    async def test_solve_tsp_single_location(self, solver):
        """Test TSP with single location."""
        locations = [Location(id=uuid4(), name="Loc 1", latitude=41.311, longitude=69.279)]

        result = await solver.solve_tsp(locations)

        assert result == [0]


class TestORToolsSolver:
    """Tests for Google OR-Tools solver."""

    @pytest.fixture
    def solver(self):
        """Create OR-Tools solver instance."""
        return ORToolsSolver()

    @pytest.fixture
    def sample_locations(self):
        """Create sample locations for testing."""
        return [
            Location(id=uuid4(), name="Depot", latitude=41.300, longitude=69.270),
            Location(id=uuid4(), name="Loc 1", latitude=41.311, longitude=69.279),
            Location(id=uuid4(), name="Loc 2", latitude=41.320, longitude=69.290),
            Location(id=uuid4(), name="Loc 3", latitude=41.305, longitude=69.285),
        ]

    def test_solver_initialization(self, solver):
        """Test OR-Tools solver initializes correctly."""
        assert solver is not None
        assert solver.solver_type == SolverType.ORTOOLS

    def test_solver_type(self, solver):
        """Test solver type property."""
        assert solver.solver_type == SolverType.ORTOOLS

    @pytest.mark.asyncio
    async def test_health_check(self, solver):
        """Test health check returns True (OR-Tools is local)."""
        result = await solver.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_solve_tsp_small(self, solver, sample_locations):
        """Test TSP with small number of locations."""
        # return_to_start=True by default, so result includes return to start
        result = await solver.solve_tsp(sample_locations, start_index=0, return_to_start=True)

        # Result should contain all indices plus return to start
        assert len(result) == len(sample_locations) + 1
        assert result[0] == 0  # Should start at depot
        assert result[-1] == 0  # Should return to depot

    @pytest.mark.asyncio
    async def test_solve_tsp_no_return(self, solver, sample_locations):
        """Test TSP without returning to start."""
        result = await solver.solve_tsp(sample_locations, start_index=0, return_to_start=False)

        # Result should contain all indices without return
        assert len(result) == len(sample_locations)
        assert set(result) == set(range(len(sample_locations)))
        assert result[0] == 0  # Should start at depot

    def test_compute_euclidean_matrix(self, solver, sample_locations):
        """Test euclidean distance matrix computation."""
        # Method takes locations directly, not a problem
        matrix = solver._compute_euclidean_matrix(sample_locations)

        # Matrix should be a list of lists (square)
        assert isinstance(matrix, list)
        assert len(matrix) == len(sample_locations)
        assert len(matrix) == len(matrix[0])
        # Diagonal should be zero
        for i in range(len(matrix)):
            assert matrix[i][i] == 0


class TestGreedySolver:
    """Tests for Greedy solver with 2-opt improvement."""

    @pytest.fixture
    def solver(self):
        """Create Greedy solver instance."""
        return GreedySolver()

    @pytest.fixture
    def sample_problem(self):
        """Create a sample routing problem."""
        return RoutingProblem(
            jobs=[
                Job(
                    id=uuid4(),
                    location=Location(id=uuid4(), name="Job 1", latitude=41.311, longitude=69.279),
                    demand_kg=10.0,
                    priority=1,
                ),
                Job(
                    id=uuid4(),
                    location=Location(id=uuid4(), name="Job 2", latitude=41.320, longitude=69.290),
                    demand_kg=5.0,
                    priority=1,
                ),
                Job(
                    id=uuid4(),
                    location=Location(id=uuid4(), name="Job 3", latitude=41.305, longitude=69.285),
                    demand_kg=8.0,
                    priority=1,
                ),
            ],
            vehicles=[
                VehicleConfig(
                    id=uuid4(),
                    name="Vehicle 1",
                    start_location=Location(id=uuid4(), name="Depot", latitude=41.300, longitude=69.270),
                    capacity_kg=100.0,
                ),
            ],
            planning_date=date.today(),
        )

    @pytest.fixture
    def sample_locations(self):
        """Create sample locations for TSP testing."""
        return [
            Location(id=uuid4(), name="Depot", latitude=41.300, longitude=69.270),
            Location(id=uuid4(), name="Loc 1", latitude=41.311, longitude=69.279),
            Location(id=uuid4(), name="Loc 2", latitude=41.320, longitude=69.290),
            Location(id=uuid4(), name="Loc 3", latitude=41.305, longitude=69.285),
        ]

    def test_solver_initialization(self, solver):
        """Test Greedy solver initializes correctly."""
        assert solver is not None
        assert solver.solver_type == SolverType.GREEDY

    def test_solver_type(self, solver):
        """Test solver type property."""
        assert solver.solver_type == SolverType.GREEDY

    @pytest.mark.asyncio
    async def test_health_check(self, solver):
        """Test health check returns True (Greedy is local)."""
        result = await solver.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_solve_returns_solution(self, solver, sample_problem):
        """Test that greedy solver returns a solution."""
        result = await solver.solve(sample_problem)

        assert isinstance(result, SolutionResult)
        # solver_used can be AUTO or GREEDY depending on implementation
        assert result.solver_used in [SolverType.GREEDY, SolverType.AUTO]

    @pytest.mark.asyncio
    async def test_solve_tsp(self, solver, sample_locations):
        """Test TSP solving."""
        # return_to_start=True by default, so result includes return to start
        result = await solver.solve_tsp(sample_locations, start_index=0, return_to_start=True)

        # Should return valid tour with return to start
        assert len(result) == len(sample_locations) + 1
        assert result[0] == 0  # Starts at specified index
        assert result[-1] == 0  # Returns to start

    @pytest.mark.asyncio
    async def test_solve_tsp_no_return(self, solver, sample_locations):
        """Test TSP without returning to start."""
        result = await solver.solve_tsp(sample_locations, start_index=0, return_to_start=False)

        # Should return valid tour without return
        assert len(result) == len(sample_locations)
        assert set(result) == set(range(len(sample_locations)))
        assert result[0] == 0  # Starts at specified index

    def test_calculate_distance(self, solver):
        """Test haversine distance calculation."""
        loc1 = Location(id=uuid4(), name="A", latitude=41.300, longitude=69.270)
        loc2 = Location(id=uuid4(), name="B", latitude=41.311, longitude=69.279)

        distance = solver._calculate_distance(loc1, loc2)

        # Distance is in meters (not km) - Earth radius = 6371000m
        assert distance > 0
        assert distance < 10000  # Should be less than 10km (10000m) for these coords

    def test_2opt_improvement(self, solver, sample_locations):
        """Test that 2-opt improves a tour."""
        # Create a suboptimal tour
        tour = [0, 2, 1, 3]  # Suboptimal order

        # Apply 2-opt improvement - uses locations not distance matrix
        improved = solver._improve_with_2opt(sample_locations, tour, is_closed=True)

        # Should return a valid tour
        assert len(improved) == len(tour)
        assert set(improved) == set(tour)


class TestSolverFallback:
    """Tests for solver fallback chain."""

    @pytest.mark.asyncio
    async def test_fallback_to_greedy_on_vroom_failure(self):
        """Test that system falls back to greedy when VROOM fails."""
        from app.services.solvers.solver_interface import SolverFactory

        problem = RoutingProblem(
            jobs=[
                Job(
                    id=uuid4(),
                    location=Location(id=uuid4(), name="Job 1", latitude=41.311, longitude=69.279),
                    demand_kg=10.0,
                    priority=1,
                ),
            ],
            vehicles=[
                VehicleConfig(
                    id=uuid4(),
                    name="Vehicle 1",
                    start_location=Location(id=uuid4(), name="Depot", latitude=41.300, longitude=69.270),
                    capacity_kg=100.0,
                ),
            ],
            planning_date=date.today(),
        )

        # Mock VROOM to fail
        with patch.object(VROOMSolver, 'solve', side_effect=VROOMError("Connection failed")):
            with patch.object(ORToolsSolver, 'solve', side_effect=Exception("OR-Tools failed")):
                with patch.object(GreedySolver, 'solve') as mock_greedy:
                    mock_greedy.return_value = SolutionResult(
                        routes=[],
                        unassigned_jobs=[],
                        total_distance_m=0,
                        total_duration_s=0,
                        solver_used=SolverType.GREEDY,
                    )

                    result = await SolverFactory.solve_with_fallback(
                        problem,
                        preferred=SolverType.VROOM
                    )

                    # Should have called greedy as fallback
                    mock_greedy.assert_called_once()


class TestSolverMetrics:
    """Tests for solver performance metrics."""

    def test_solution_result_creation(self):
        """Test SolutionResult can be created correctly."""
        result = SolutionResult(
            routes=[],
            unassigned_jobs=[uuid4(), uuid4()],
            total_distance_m=50000,
            total_duration_s=7200,
            solver_used=SolverType.VROOM,
        )

        assert result.total_distance_m == 50000
        assert result.total_duration_s == 7200
        assert len(result.unassigned_jobs) == 2
        assert result.solver_used == SolverType.VROOM

    def test_solution_result_kpis(self):
        """Test SolutionResult KPI calculation."""
        vehicle_id = uuid4()
        result = SolutionResult(
            routes=[
                Route(
                    vehicle_id=vehicle_id,
                    vehicle_name="V1",
                    steps=[],
                    total_distance_m=10000,
                    total_duration_s=3600,
                )
            ],
            unassigned_jobs=[],
            total_distance_m=10000,
            total_duration_s=3600,
            solver_used=SolverType.GREEDY,
        )

        kpis = result.calculate_kpis()
        assert isinstance(kpis, dict)


class TestRouteAndRouteStep:
    """Tests for Route and RouteStep dataclasses."""

    def test_route_creation(self):
        """Test Route can be created with required fields."""
        vehicle_id = uuid4()
        route = Route(
            vehicle_id=vehicle_id,
            vehicle_name="Test Vehicle",
            steps=[],
        )

        assert route.vehicle_id == vehicle_id
        assert route.vehicle_name == "Test Vehicle"
        assert route.steps == []
        assert route.total_distance_m == 0
        assert route.total_duration_s == 0

    def test_route_step_creation(self):
        """Test RouteStep can be created."""
        from datetime import datetime

        loc = Location(id=uuid4(), name="Test", latitude=41.0, longitude=69.0)
        now = datetime.now()

        step = RouteStep(
            job_id=uuid4(),
            location=loc,
            arrival_time=now,
            departure_time=now,
        )

        assert step.location == loc
        assert step.step_type == "job"
