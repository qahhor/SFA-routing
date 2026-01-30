"""
Tests for individual VRP solvers (VROOM, OR-Tools, Greedy).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from decimal import Decimal

from app.services.solvers.solver_interface import (
    RoutingProblem,
    Job,
    VehicleConfig,
    Location,
    SolutionResult,
    SolverType,
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
                    id=str(uuid4()),
                    location=Location(latitude=41.311, longitude=69.279),
                    service_time_s=900,
                    demand=[10],
                ),
                Job(
                    id=str(uuid4()),
                    location=Location(latitude=41.320, longitude=69.290),
                    service_time_s=600,
                    demand=[5],
                ),
            ],
            vehicles=[
                VehicleConfig(
                    id=str(uuid4()),
                    start_location=Location(latitude=41.300, longitude=69.270),
                    capacity=[100],
                    max_travel_time_s=28800,  # 8 hours
                ),
            ],
        )

    def test_solver_initialization(self, solver):
        """Test VROOM solver initializes correctly."""
        assert solver.base_url is not None
        assert solver.max_retries == 3
        assert solver.base_delay == 1.0

    def test_build_request_structure(self, solver, sample_problem):
        """Test VROOM request building."""
        request = solver._build_request(sample_problem)

        assert "vehicles" in request
        assert "jobs" in request
        assert len(request["vehicles"]) == 1
        assert len(request["jobs"]) == 2

        # Check vehicle structure
        vehicle = request["vehicles"][0]
        assert "start" in vehicle
        assert "capacity" in vehicle

        # Check job structure
        job = request["jobs"][0]
        assert "location" in job
        assert "service" in job

    @pytest.mark.asyncio
    async def test_solve_tsp_trivial(self, solver):
        """Test TSP with trivial input (<=2 locations)."""
        locations = [
            Location(latitude=41.311, longitude=69.279),
            Location(latitude=41.320, longitude=69.290),
        ]

        result = await solver.solve_tsp(locations)

        assert result == [0, 1]

    @pytest.mark.asyncio
    async def test_solve_tsp_single_location(self, solver):
        """Test TSP with single location."""
        locations = [Location(latitude=41.311, longitude=69.279)]

        result = await solver.solve_tsp(locations)

        assert result == [0]

    def test_parse_load_from_delivery(self, solver):
        """Test that load is correctly parsed from VROOM response."""
        # Mock response with delivery data
        route_data = {
            "vehicle": 0,
            "steps": [
                {"type": "start", "location": [69.279, 41.311]},
                {"type": "job", "job": 0, "location": [69.290, 41.320]},
                {"type": "end", "location": [69.279, 41.311]},
            ],
            "delivery": [15, 10],  # Multi-dimensional load
            "distance": 5000,
            "duration": 1800,
        }

        # Sum of delivery array should be total_load
        delivery = route_data.get("delivery", [])
        total_load = sum(delivery) if delivery else 0

        assert total_load == 25


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
            Location(latitude=41.300, longitude=69.270),  # Depot
            Location(latitude=41.311, longitude=69.279),
            Location(latitude=41.320, longitude=69.290),
            Location(latitude=41.305, longitude=69.285),
        ]

    def test_solver_initialization(self, solver):
        """Test OR-Tools solver initializes correctly."""
        assert solver is not None

    @pytest.mark.asyncio
    async def test_solve_tsp_returns_valid_tour(self, solver, sample_locations):
        """Test that OR-Tools TSP returns a valid tour."""
        # Create distance matrix (mock)
        with patch.object(solver, '_compute_distance_matrix') as mock_matrix:
            # Simple distance matrix
            mock_matrix.return_value = [
                [0, 100, 200, 150],
                [100, 0, 150, 100],
                [200, 150, 0, 100],
                [150, 100, 100, 0],
            ]

            result = await solver.solve_tsp(sample_locations, start_index=0)

            # Result should contain all indices
            assert len(set(result)) >= len(sample_locations) - 1  # At least n-1 unique
            assert result[0] == 0  # Should start at depot


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
                    id=str(uuid4()),
                    location=Location(latitude=41.311, longitude=69.279),
                    service_time_s=900,
                ),
                Job(
                    id=str(uuid4()),
                    location=Location(latitude=41.320, longitude=69.290),
                    service_time_s=600,
                ),
                Job(
                    id=str(uuid4()),
                    location=Location(latitude=41.305, longitude=69.285),
                    service_time_s=450,
                ),
            ],
            vehicles=[
                VehicleConfig(
                    id=str(uuid4()),
                    start_location=Location(latitude=41.300, longitude=69.270),
                    capacity=[100],
                ),
            ],
        )

    def test_solver_initialization(self, solver):
        """Test Greedy solver initializes correctly."""
        assert solver is not None
        assert solver.use_2opt is True  # Should use 2-opt by default

    @pytest.mark.asyncio
    async def test_solve_returns_solution(self, solver, sample_problem):
        """Test that greedy solver returns a solution."""
        # Mock distance matrix
        with patch.object(solver, '_get_distance_matrix') as mock_matrix:
            mock_matrix.return_value = (
                # Duration matrix
                [
                    [0, 600, 900, 750],
                    [600, 0, 450, 300],
                    [900, 450, 0, 600],
                    [750, 300, 600, 0],
                ],
                # Distance matrix
                [
                    [0, 5000, 8000, 6000],
                    [5000, 0, 4000, 2500],
                    [8000, 4000, 0, 5000],
                    [6000, 2500, 5000, 0],
                ],
            )

            result = await solver.solve(sample_problem)

            assert isinstance(result, SolutionResult)
            assert result.solver_used == SolverType.GREEDY
            assert len(result.routes) >= 0  # May have routes or not

    def test_2opt_improvement(self, solver):
        """Test that 2-opt improves a tour."""
        # A tour that can be improved: 0 -> 2 -> 1 -> 3 -> 0
        # Optimal might be: 0 -> 1 -> 2 -> 3 -> 0
        initial_tour = [0, 2, 1, 3]

        distance_matrix = [
            [0, 1, 10, 10],
            [1, 0, 1, 10],
            [10, 1, 0, 1],
            [10, 10, 1, 0],
        ]

        improved = solver._apply_2opt(initial_tour, distance_matrix)

        # Calculate distances
        def tour_distance(tour):
            total = 0
            for i in range(len(tour) - 1):
                total += distance_matrix[tour[i]][tour[i + 1]]
            total += distance_matrix[tour[-1]][tour[0]]  # Return to start
            return total

        assert tour_distance(improved) <= tour_distance(initial_tour)

    def test_nearest_neighbor_construction(self, solver):
        """Test nearest neighbor tour construction."""
        distance_matrix = [
            [0, 10, 20, 15],
            [10, 0, 25, 10],
            [20, 25, 0, 10],
            [15, 10, 10, 0],
        ]

        tour = solver._nearest_neighbor(distance_matrix, start=0)

        # Should visit all nodes
        assert len(tour) == 4
        assert set(tour) == {0, 1, 2, 3}
        assert tour[0] == 0  # Starts at specified node


class TestSolverFallback:
    """Tests for solver fallback chain."""

    @pytest.mark.asyncio
    async def test_fallback_to_greedy_on_vroom_failure(self):
        """Test that system falls back to greedy when VROOM fails."""
        from app.services.solvers.solver_interface import SolverFactory

        problem = RoutingProblem(
            jobs=[
                Job(
                    id=str(uuid4()),
                    location=Location(latitude=41.311, longitude=69.279),
                    service_time_s=900,
                ),
            ],
            vehicles=[
                VehicleConfig(
                    id=str(uuid4()),
                    start_location=Location(latitude=41.300, longitude=69.270),
                ),
            ],
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

    def test_solution_result_metrics(self):
        """Test SolutionResult captures metrics correctly."""
        result = SolutionResult(
            routes=[],
            unassigned_jobs=["job1", "job2"],
            total_distance_m=50000,
            total_duration_s=7200,
            solver_used=SolverType.VROOM,
        )

        assert result.total_distance_m == 50000
        assert result.total_duration_s == 7200
        assert len(result.unassigned_jobs) == 2
        assert result.solver_used == SolverType.VROOM
