"""
Solver interface and factory for route optimization.

Implements Strategy pattern for swappable solvers:
- VROOM (default, fast)
- Google OR-Tools (complex constraints)
- Greedy (fallback)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal
from enum import Enum
from typing import Optional, Any
from uuid import UUID


class SolverType(str, Enum):
    """Available solver types."""
    VROOM = "vroom"
    ORTOOLS = "ortools"
    GREEDY = "greedy"
    AUTO = "auto"


@dataclass
class Location:
    """Location with coordinates and metadata."""
    id: UUID
    name: str
    latitude: float
    longitude: float
    service_time_minutes: int = 15
    time_window_start: Optional[time] = None
    time_window_end: Optional[time] = None


@dataclass
class VehicleConfig:
    """Vehicle configuration for routing."""
    id: UUID
    name: str
    capacity_kg: float
    capacity_volume: Optional[float] = None
    start_location: Optional[Location] = None
    end_location: Optional[Location] = None
    work_start: time = field(default_factory=lambda: time(8, 0))
    work_end: time = field(default_factory=lambda: time(20, 0))
    cost_per_km: float = 1.0
    fixed_cost: float = 0.0


@dataclass
class Job:
    """Job/delivery to be assigned to a vehicle."""
    id: UUID
    location: Location
    demand_kg: float = 0
    demand_volume: float = 0
    priority: int = 1
    time_window_start: Optional[datetime] = None
    time_window_end: Optional[datetime] = None


@dataclass
class RouteStep:
    """Single step in a route."""
    job_id: Optional[UUID]
    location: Location
    arrival_time: datetime
    departure_time: datetime
    distance_from_previous_m: int = 0
    duration_from_previous_s: int = 0
    load_after: float = 0
    step_type: str = "job"  # "start", "job", "end"


@dataclass
class Route:
    """Optimized route for a vehicle."""
    vehicle_id: UUID
    vehicle_name: str
    steps: list[RouteStep]
    total_distance_m: int = 0
    total_duration_s: int = 0
    total_load: float = 0
    geometry: Optional[str] = None  # Encoded polyline


@dataclass
class SolutionResult:
    """Result of route optimization."""
    routes: list[Route]
    unassigned_jobs: list[UUID]
    total_distance_m: int = 0
    total_duration_s: int = 0
    computation_time_ms: int = 0
    solver_used: SolverType = SolverType.AUTO
    quality_score: float = 0.0  # 0-1, estimated solution quality
    summary: dict = field(default_factory=dict)


@dataclass
class RoutingProblem:
    """Complete routing problem definition."""
    jobs: list[Job]
    vehicles: list[VehicleConfig]
    depot_location: Optional[Location] = None
    distance_matrix: Optional[list[list[int]]] = None
    duration_matrix: Optional[list[list[int]]] = None

    # Problem characteristics (for solver selection)
    has_time_windows: bool = False
    has_pickup_delivery: bool = False
    has_multi_depot: bool = False
    max_computation_time_s: int = 300


class RouteSolver(ABC):
    """
    Abstract base class for route solvers.

    Implement this interface to add new solver backends.
    """

    @property
    @abstractmethod
    def solver_type(self) -> SolverType:
        """Return the solver type identifier."""
        pass

    @abstractmethod
    async def solve(self, problem: RoutingProblem) -> SolutionResult:
        """
        Solve the routing problem.

        Args:
            problem: Complete problem definition

        Returns:
            SolutionResult with optimized routes
        """
        pass

    @abstractmethod
    async def solve_tsp(
        self,
        locations: list[Location],
        start_index: int = 0,
        return_to_start: bool = True,
    ) -> list[int]:
        """
        Solve Traveling Salesman Problem.

        Args:
            locations: List of locations to visit
            start_index: Index of starting location
            return_to_start: Whether to return to start location

        Returns:
            List of location indices in optimal order
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if solver is available and working."""
        pass

    def estimate_quality(self, result: SolutionResult) -> float:
        """
        Estimate solution quality (0-1).

        Default implementation based on unassigned jobs ratio.
        """
        if not result.routes and not result.unassigned_jobs:
            return 0.0

        total_jobs = sum(
            len([s for s in r.steps if s.step_type == "job"])
            for r in result.routes
        ) + len(result.unassigned_jobs)

        if total_jobs == 0:
            return 1.0

        assigned = total_jobs - len(result.unassigned_jobs)
        return assigned / total_jobs


class SolverFactory:
    """
    Factory for creating and selecting optimal solver.

    Selection logic:
    1. If specific solver requested, use it
    2. If auto, select based on problem characteristics
    3. Fallback chain: VROOM → OR-Tools → Greedy
    """

    _solvers: dict[SolverType, type[RouteSolver]] = {}

    @classmethod
    def register(cls, solver_type: SolverType):
        """Decorator to register a solver class."""
        def decorator(solver_class: type[RouteSolver]):
            cls._solvers[solver_type] = solver_class
            return solver_class
        return decorator

    @classmethod
    def get_solver(
        cls,
        solver_type: SolverType = SolverType.AUTO,
        problem: Optional[RoutingProblem] = None,
    ) -> RouteSolver:
        """
        Get appropriate solver instance.

        Args:
            solver_type: Preferred solver type
            problem: Problem for auto-selection

        Returns:
            Solver instance
        """
        if solver_type != SolverType.AUTO:
            if solver_type in cls._solvers:
                return cls._solvers[solver_type]()
            raise ValueError(f"Solver {solver_type} not registered")

        # Auto-selection based on problem characteristics
        if problem:
            return cls._select_optimal_solver(problem)

        # Default to VROOM
        if SolverType.VROOM in cls._solvers:
            return cls._solvers[SolverType.VROOM]()

        # Fallback to any available
        for solver_class in cls._solvers.values():
            return solver_class()

        raise RuntimeError("No solvers registered")

    @classmethod
    def _select_optimal_solver(cls, problem: RoutingProblem) -> RouteSolver:
        """Select optimal solver based on problem characteristics."""

        # Complex constraints → OR-Tools
        if (problem.has_pickup_delivery or
            problem.has_multi_depot or
            len(problem.jobs) > 500):
            if SolverType.ORTOOLS in cls._solvers:
                return cls._solvers[SolverType.ORTOOLS]()

        # Simple problem → VROOM (faster)
        if SolverType.VROOM in cls._solvers:
            return cls._solvers[SolverType.VROOM]()

        # Fallback to OR-Tools
        if SolverType.ORTOOLS in cls._solvers:
            return cls._solvers[SolverType.ORTOOLS]()

        # Last resort: Greedy
        if SolverType.GREEDY in cls._solvers:
            return cls._solvers[SolverType.GREEDY]()

        raise RuntimeError("No suitable solver available")

    @classmethod
    async def solve_with_fallback(
        cls,
        problem: RoutingProblem,
        preferred: SolverType = SolverType.AUTO,
    ) -> SolutionResult:
        """
        Solve with automatic fallback on failure.

        Tries solvers in order:
        1. Preferred solver
        2. Alternative solver
        3. Greedy fallback

        Args:
            problem: Routing problem
            preferred: Preferred solver type

        Returns:
            Best available solution
        """
        import time
        start = time.perf_counter()

        # Build fallback chain
        fallback_order = [preferred]
        if preferred != SolverType.VROOM and SolverType.VROOM in cls._solvers:
            fallback_order.append(SolverType.VROOM)
        if preferred != SolverType.ORTOOLS and SolverType.ORTOOLS in cls._solvers:
            fallback_order.append(SolverType.ORTOOLS)
        if SolverType.GREEDY in cls._solvers:
            fallback_order.append(SolverType.GREEDY)

        last_error = None

        for solver_type in fallback_order:
            try:
                solver = cls.get_solver(solver_type, problem)

                # Check health first
                if not await solver.health_check():
                    continue

                result = await solver.solve(problem)
                result.solver_used = solver.solver_type
                result.computation_time_ms = int((time.perf_counter() - start) * 1000)
                result.quality_score = solver.estimate_quality(result)

                # Accept if quality is good enough
                if result.quality_score >= 0.9 or solver_type == SolverType.GREEDY:
                    return result

            except Exception as e:
                last_error = e
                continue

        # If all solvers failed
        if last_error:
            raise RuntimeError(f"All solvers failed. Last error: {last_error}")

        raise RuntimeError("No solvers available")
