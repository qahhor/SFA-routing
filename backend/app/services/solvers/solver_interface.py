"""
Solver interface and factory for route optimization.

Implements Strategy pattern for swappable solvers:
- VROOM (default, fast)
- Google OR-Tools (complex constraints)
- Greedy (fallback)

FMCG-specific extensions:
- Client categories (A/B/C) with visit frequency
- Stock level prioritization
- Debt collection routing
- Central Asia regional constraints
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import Optional
from uuid import UUID


class SolverType(str, Enum):
    """Available solver types."""

    VROOM = "vroom"
    ORTOOLS = "ortools"
    GREEDY = "greedy"
    AUTO = "auto"


class ClientCategory(str, Enum):
    """Client category for visit frequency."""

    A = "A"  # 2-3 visits/week
    B = "B"  # 1 visit/week
    C = "C"  # 1-2 visits/month


class VisitPurpose(str, Enum):
    """Purpose of the visit."""

    REGULAR = "regular"
    PROMO = "promo"
    AUDIT = "audit"
    COLLECTION = "collection"  # Debt collection
    ONBOARDING = "onboarding"  # New client
    PROBLEM = "problem"  # Problem resolution


class RegionalConfig(str, Enum):
    """Regional configuration presets."""

    UZBEKISTAN = "uzbekistan"
    KAZAKHSTAN = "kazakhstan"
    DEFAULT = "default"


class TransportMode(str, Enum):
    """Transport mode for routing."""

    CAR = "car"
    PEDESTRIAN = "foot"
    BICYCLE = "bicycle"


@dataclass
class Break:
    """Scheduled break for a vehicle/driver."""

    id: int
    start: Optional[time] = None
    end: Optional[time] = None
    description: str = ""
    duration_minutes: int = 60  # Default duration if start/end not fixed


@dataclass
class RegionalConstraints:
    """Region-specific constraints for Central Asia markets."""

    # Daily schedule
    lunch_break_start: time = field(default_factory=lambda: time(13, 0))
    lunch_break_end: time = field(default_factory=lambda: time(14, 0))
    friday_prayer_start: Optional[time] = field(default_factory=lambda: time(12, 0))
    friday_prayer_end: Optional[time] = field(default_factory=lambda: time(13, 30))

    # Traffic peaks (avoid for routing)
    morning_peak_start: time = field(default_factory=lambda: time(8, 0))
    morning_peak_end: time = field(default_factory=lambda: time(9, 30))
    evening_peak_start: time = field(default_factory=lambda: time(17, 0))
    evening_peak_end: time = field(default_factory=lambda: time(19, 0))

    # Seasonal
    summer_early_start: bool = True  # Start at 7:00 in summer
    ramadan_adjusted_hours: bool = False  # Shorter work hours during Ramadan

    # Business patterns
    payday_dates: list[int] = field(default_factory=lambda: [5, 20])
    market_days: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def for_uzbekistan(cls) -> "RegionalConstraints":
        """Get Uzbekistan-specific constraints."""
        return cls(
            lunch_break_start=time(13, 0),
            lunch_break_end=time(14, 0),
            friday_prayer_start=time(12, 0),
            friday_prayer_end=time(13, 30),
            payday_dates=[5, 20],
            market_days={
                "chorsu": ["saturday", "sunday"],
                "alaysky": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
            },
            summer_early_start=True,
        )

    @classmethod
    def for_kazakhstan(cls) -> "RegionalConstraints":
        """Get Kazakhstan-specific constraints."""
        return cls(
            lunch_break_start=time(13, 0),
            lunch_break_end=time(14, 0),
            friday_prayer_start=None,  # Less strict
            friday_prayer_end=None,
            payday_dates=[10, 25],
            morning_peak_start=time(7, 30),
            morning_peak_end=time(10, 0),
            evening_peak_start=time(17, 0),
            evening_peak_end=time(20, 0),  # Almaty has longer evening traffic
        )


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

    # FMCG-specific fields
    client_category: ClientCategory = ClientCategory.B
    has_loading_dock: bool = False
    requires_appointment: bool = False
    delivery_day_restrictions: list[int] = field(default_factory=list)  # 0=Mon, 6=Sun


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
    breaks: list[Break] = field(default_factory=list)
    cost_per_km: float = 1.0
    fixed_cost: float = 0.0

    # Extended vehicle properties
    has_refrigeration: bool = False
    min_temp_celsius: Optional[float] = None
    max_temp_celsius: Optional[float] = None
    vehicle_height_m: float = 3.0
    vehicle_length_m: float = 6.0
    requires_loader: bool = False
    fuel_consumption_per_100km: float = 12.0
    driver_hourly_rate: float = 0  # For cost calculation
    max_driving_hours: float = 8.0
    required_break_after_hours: float = 4.0


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

    # FMCG-specific fields
    visit_purpose: VisitPurpose = VisitPurpose.REGULAR
    stock_days_remaining: Optional[int] = None  # Client's stock level
    outstanding_debt: float = 0  # For collection routing
    expected_order_value: float = 0  # ML prediction
    order_probability: float = 0.5  # ML prediction
    is_new_client: bool = False  # Needs more attention
    has_active_promo: bool = False
    churn_risk_score: float = 0  # 0-1, from ML model

    def calculate_priority_score(self, is_payday: bool = False) -> float:
        """
        Calculate visit priority score based on FMCG factors.

        Returns: float 0-100 (higher = more urgent)
        """
        score = float(self.priority * 10)  # Base priority

        # Stock levels (critical = high priority)
        if self.stock_days_remaining is not None:
            if self.stock_days_remaining < 3:
                score += 30  # Critical stock
            elif self.stock_days_remaining < 7:
                score += 15  # Low stock

        # Debt collection (prioritize on payday)
        if self.outstanding_debt > 0:
            if is_payday:
                score += 25
            else:
                score += 10

        # Active promotions
        if self.has_active_promo:
            score += 15

        # New clients need attention
        if self.is_new_client:
            score += 20

        # Churn risk
        if self.churn_risk_score > 0.7:
            score += 25
        elif self.churn_risk_score > 0.5:
            score += 10

        # Expected value (prioritize high-value visits)
        if self.expected_order_value > 0:
            score += min(self.expected_order_value / 100, 20)

        return min(score, 100)


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

    # FMCG KPIs
    total_expected_value: float = 0  # Sum of expected order values
    workload_balance_score: float = 0  # 0-1, how balanced across vehicles
    travel_to_service_ratio: float = 0  # Target: 30/70

    def calculate_kpis(self) -> dict:
        """Calculate FMCG-specific KPIs."""
        if not self.routes:
            return {}

        visits_per_route = [len([s for s in r.steps if s.step_type == "job"]) for r in self.routes]

        total_visits = sum(visits_per_route)
        avg_visits = total_visits / len(self.routes) if self.routes else 0

        # Workload balance (coefficient of variation)
        if avg_visits > 0 and len(visits_per_route) > 1:
            import statistics

            std_dev = statistics.stdev(visits_per_route)
            cv = std_dev / avg_visits
            self.workload_balance_score = max(0, 1 - cv)
        else:
            self.workload_balance_score = 1.0

        # Travel to service ratio
        total_travel = sum(r.total_duration_s for r in self.routes)
        # Estimate service time (15 min per visit)
        total_service = total_visits * 15 * 60
        total_time = total_travel + total_service
        if total_time > 0:
            self.travel_to_service_ratio = total_travel / total_time

        return {
            "total_visits": total_visits,
            "avg_visits_per_route": avg_visits,
            "visits_per_route": visits_per_route,
            "workload_balance_score": self.workload_balance_score,
            "travel_to_service_ratio": self.travel_to_service_ratio,
            "total_distance_km": self.total_distance_m / 1000,
            "total_duration_hours": self.total_duration_s / 3600,
            "km_per_visit": (self.total_distance_m / 1000 / total_visits) if total_visits > 0 else 0,
            "vehicles_used": len(self.routes),
            "unassigned_count": len(self.unassigned_jobs),
            "assignment_rate": (
                total_visits / (total_visits + len(self.unassigned_jobs))
                if (total_visits + len(self.unassigned_jobs)) > 0
                else 0
            ),
        }


@dataclass
class RoutingProblem:
    """Complete routing problem definition."""

    jobs: list[Job]
    vehicles: list[VehicleConfig]
    depot_location: Optional[Location] = None
    distance_matrix: Optional[list[list[int]]] = None
    duration_matrix: Optional[list[list[int]]] = None

    # Transport configuration
    transport_mode: TransportMode = TransportMode.CAR

    # Problem characteristics (for solver selection)
    has_time_windows: bool = False
    has_pickup_delivery: bool = False
    has_multi_depot: bool = False
    max_computation_time_s: int = 300

    # FMCG-specific configuration
    regional_constraints: Optional[RegionalConstraints] = None
    planning_date: Optional[date] = None
    optimization_objective: str = "minimize_distance"  # or "maximize_value", "balance_workload"
    respect_lunch_break: bool = True
    respect_friday_prayer: bool = False
    is_payday_period: bool = False

    # Load balancing
    max_visits_per_vehicle: int = 30
    target_visits_per_vehicle: int = 12
    workload_balance_tolerance: float = 0.1  # ±10%

    def get_regional_constraints(self) -> RegionalConstraints:
        """Get regional constraints, defaulting to Uzbekistan."""
        if self.regional_constraints:
            return self.regional_constraints
        return RegionalConstraints.for_uzbekistan()

    def is_within_lunch_break(self, check_time: time) -> bool:
        """Check if time falls within lunch break."""
        if not self.respect_lunch_break:
            return False
        constraints = self.get_regional_constraints()
        return constraints.lunch_break_start <= check_time <= constraints.lunch_break_end

    def is_within_friday_prayer(self, check_time: time, weekday: int) -> bool:
        """Check if time falls within Friday prayer (weekday 4 = Friday)."""
        if not self.respect_friday_prayer or weekday != 4:
            return False
        constraints = self.get_regional_constraints()
        if constraints.friday_prayer_start and constraints.friday_prayer_end:
            return constraints.friday_prayer_start <= check_time <= constraints.friday_prayer_end
        return False

    def check_payday_period(self) -> bool:
        """Check if planning date is within payday period (±3 days)."""
        if self.planning_date is None:
            return self.is_payday_period
        constraints = self.get_regional_constraints()
        day = self.planning_date.day
        for payday in constraints.payday_dates:
            if abs(day - payday) <= 3:
                return True
        return False


class RouteSolver(ABC):
    """
    Abstract base class for route solvers.

    Implement this interface to add new solver backends.
    """

    @property
    @abstractmethod
    def solver_type(self) -> SolverType:
        """Return the solver type identifier."""

    @abstractmethod
    async def solve(self, problem: RoutingProblem) -> SolutionResult:
        """
        Solve the routing problem.

        Args:
            problem: Complete problem definition

        Returns:
            SolutionResult with optimized routes
        """

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

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if solver is available and working."""

    def estimate_quality(self, result: SolutionResult) -> float:
        """
        Estimate solution quality (0-1).

        Default implementation based on unassigned jobs ratio.
        """
        if not result.routes and not result.unassigned_jobs:
            return 0.0

        total_jobs = sum(len([s for s in r.steps if s.step_type == "job"]) for r in result.routes) + len(
            result.unassigned_jobs
        )

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
        if problem.has_pickup_delivery or problem.has_multi_depot or len(problem.jobs) > 500:
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
