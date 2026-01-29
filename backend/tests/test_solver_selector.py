"""
Tests for Smart Solver Selection module.

Tests cover:
- ProblemComplexity enum
- ProblemFeatures dataclass
- SolverProfile dataclass
- Feature extraction from problems
- Complexity classification
- Solver filtering by capabilities
- Solver scoring
- Full selection logic
"""
import pytest
from datetime import datetime, time, timedelta
from uuid import uuid4

from app.services.solver_selector import (
    ProblemComplexity,
    ProblemFeatures,
    SolverProfile,
    SmartSolverSelector,
    SOLVER_PROFILES,
    solver_selector,
)
from app.services.solver_interface import (
    RoutingProblem,
    Job,
    Vehicle,
    Location,
    SolverType,
)


class TestProblemComplexity:
    """Tests for ProblemComplexity enum."""

    def test_enum_values(self):
        """Test enum has expected values."""
        assert ProblemComplexity.SIMPLE == "simple"
        assert ProblemComplexity.MEDIUM == "medium"
        assert ProblemComplexity.COMPLEX == "complex"
        assert ProblemComplexity.VERY_COMPLEX == "very_complex"


class TestProblemFeatures:
    """Tests for ProblemFeatures dataclass."""

    def test_creation(self):
        """Test feature creation."""
        features = ProblemFeatures(
            n_jobs=100,
            n_vehicles=5,
            has_time_windows=True,
            time_window_tightness=0.7,
            has_capacity=True,
            capacity_utilization=0.85,
            geographic_dispersion=0.5,
            cluster_coefficient=0.6,
            has_pickup_delivery=False,
            has_multi_depot=False,
            has_breaks=False,
            has_skills=False,
            constraint_complexity=5,
            estimated_solve_time_factor=2.0,
        )

        assert features.n_jobs == 100
        assert features.n_vehicles == 5
        assert features.has_time_windows is True
        assert features.time_window_tightness == 0.7


class TestSolverProfile:
    """Tests for SolverProfile dataclass."""

    def test_creation(self):
        """Test profile creation."""
        profile = SolverProfile(
            solver_type=SolverType.VROOM,
            max_jobs_efficient=150,
            max_jobs_feasible=500,
            supports_pickup_delivery=False,
            supports_multi_depot=True,
            supports_breaks=True,
            speed_factor=1.0,
            quality_factor=0.97,
        )

        assert profile.solver_type == SolverType.VROOM
        assert profile.max_jobs_efficient == 150
        assert profile.quality_factor == 0.97


class TestSolverProfiles:
    """Tests for predefined solver profiles."""

    def test_vroom_profile(self):
        """Test VROOM profile exists and has correct values."""
        profile = SOLVER_PROFILES[SolverType.VROOM]

        assert profile.solver_type == SolverType.VROOM
        assert profile.max_jobs_efficient == 150
        assert profile.supports_pickup_delivery is False
        assert profile.speed_factor == 1.0

    def test_ortools_profile(self):
        """Test OR-Tools profile exists and has correct values."""
        profile = SOLVER_PROFILES[SolverType.ORTOOLS]

        assert profile.solver_type == SolverType.ORTOOLS
        assert profile.max_jobs_efficient == 300
        assert profile.supports_pickup_delivery is True
        assert profile.speed_factor == 3.0

    def test_genetic_profile(self):
        """Test Genetic profile exists and has correct values."""
        profile = SOLVER_PROFILES[SolverType.GENETIC]

        assert profile.solver_type == SolverType.GENETIC
        assert profile.max_jobs_efficient == 1000
        assert profile.supports_breaks is False

    def test_greedy_profile(self):
        """Test Greedy profile exists and has correct values."""
        profile = SOLVER_PROFILES[SolverType.GREEDY]

        assert profile.solver_type == SolverType.GREEDY
        assert profile.max_jobs_efficient == float("inf")
        assert profile.quality_factor == 0.85


class TestSmartSolverSelector:
    """Tests for SmartSolverSelector class."""

    @pytest.fixture
    def selector(self):
        """Create selector instance."""
        return SmartSolverSelector()

    @pytest.fixture
    def simple_job(self):
        """Create a simple job without time windows."""
        return Job(
            id=uuid4(),
            location=Location(latitude=41.311, longitude=69.279, address="Test"),
            priority=1,
            demand_kg=10.0,
        )

    @pytest.fixture
    def time_windowed_job(self):
        """Create a job with time window."""
        start = datetime.now().replace(hour=9, minute=0)
        end = datetime.now().replace(hour=10, minute=0)
        return Job(
            id=uuid4(),
            location=Location(latitude=41.311, longitude=69.279, address="Test"),
            priority=1,
            demand_kg=10.0,
            time_window_start=start,
            time_window_end=end,
        )

    @pytest.fixture
    def simple_vehicle(self):
        """Create a simple vehicle."""
        return Vehicle(
            id=uuid4(),
            capacity_kg=100.0,
            work_start=time(8, 0),
            work_end=time(18, 0),
        )

    def test_extract_features_empty_problem(self, selector):
        """Test feature extraction with no jobs."""
        problem = RoutingProblem(
            jobs=[],
            vehicles=[],
            planning_date=datetime.now().date(),
        )

        features = selector.extract_features(problem)

        assert features.n_jobs == 0
        assert features.n_vehicles == 1  # Default to 1
        assert features.has_time_windows is False
        assert features.constraint_complexity == 0

    def test_extract_features_simple_problem(self, selector, simple_job, simple_vehicle):
        """Test feature extraction with simple problem."""
        jobs = [simple_job for _ in range(10)]

        problem = RoutingProblem(
            jobs=jobs,
            vehicles=[simple_vehicle],
            planning_date=datetime.now().date(),
        )

        features = selector.extract_features(problem)

        assert features.n_jobs == 10
        assert features.n_vehicles == 1
        assert features.has_capacity is True
        assert features.capacity_utilization == 1.0  # 100kg demand / 100kg capacity

    def test_extract_features_time_windows(self, selector, time_windowed_job, simple_vehicle):
        """Test feature extraction with time windows."""
        jobs = [time_windowed_job for _ in range(5)]

        problem = RoutingProblem(
            jobs=jobs,
            vehicles=[simple_vehicle],
            planning_date=datetime.now().date(),
        )

        features = selector.extract_features(problem)

        assert features.has_time_windows is True
        assert features.time_window_tightness > 0  # 1-hour windows are tight

    def test_extract_features_geographic_dispersion(self, selector, simple_vehicle):
        """Test geographic dispersion calculation."""
        # Create jobs in a line
        jobs = [
            Job(
                id=uuid4(),
                location=Location(
                    latitude=41.0 + i * 0.1,
                    longitude=69.0 + i * 0.1,
                    address=f"Point {i}",
                ),
                priority=1,
            )
            for i in range(10)
        ]

        problem = RoutingProblem(
            jobs=jobs,
            vehicles=[simple_vehicle],
            planning_date=datetime.now().date(),
        )

        features = selector.extract_features(problem)

        assert features.geographic_dispersion > 0

    def test_classify_complexity_simple(self, selector):
        """Test simple complexity classification."""
        features = ProblemFeatures(
            n_jobs=30,
            n_vehicles=2,
            has_time_windows=False,
            time_window_tightness=0.0,
            has_capacity=False,
            capacity_utilization=0.0,
            geographic_dispersion=0.1,
            cluster_coefficient=0.8,
            has_pickup_delivery=False,
            has_multi_depot=False,
            has_breaks=False,
            has_skills=False,
            constraint_complexity=0,
            estimated_solve_time_factor=0.3,
        )

        complexity = selector.classify_complexity(features)
        assert complexity == ProblemComplexity.SIMPLE

    def test_classify_complexity_medium(self, selector):
        """Test medium complexity classification."""
        features = ProblemFeatures(
            n_jobs=100,
            n_vehicles=5,
            has_time_windows=True,
            time_window_tightness=0.3,
            has_capacity=True,
            capacity_utilization=0.5,
            geographic_dispersion=0.3,
            cluster_coefficient=0.5,
            has_pickup_delivery=False,
            has_multi_depot=False,
            has_breaks=False,
            has_skills=False,
            constraint_complexity=3,
            estimated_solve_time_factor=1.5,
        )

        complexity = selector.classify_complexity(features)
        assert complexity == ProblemComplexity.MEDIUM

    def test_classify_complexity_complex(self, selector):
        """Test complex complexity classification."""
        features = ProblemFeatures(
            n_jobs=300,
            n_vehicles=10,
            has_time_windows=True,
            time_window_tightness=0.7,
            has_capacity=True,
            capacity_utilization=0.8,
            geographic_dispersion=0.5,
            cluster_coefficient=0.3,
            has_pickup_delivery=False,
            has_multi_depot=False,
            has_breaks=False,
            has_skills=False,
            constraint_complexity=6,
            estimated_solve_time_factor=5.0,
        )

        complexity = selector.classify_complexity(features)
        assert complexity == ProblemComplexity.COMPLEX

    def test_classify_complexity_very_complex(self, selector):
        """Test very complex classification."""
        features = ProblemFeatures(
            n_jobs=600,
            n_vehicles=20,
            has_time_windows=True,
            time_window_tightness=0.9,
            has_capacity=True,
            capacity_utilization=0.95,
            geographic_dispersion=1.0,
            cluster_coefficient=0.1,
            has_pickup_delivery=True,
            has_multi_depot=True,
            has_breaks=True,
            has_skills=True,
            constraint_complexity=10,
            estimated_solve_time_factor=20.0,
        )

        complexity = selector.classify_complexity(features)
        assert complexity == ProblemComplexity.VERY_COMPLEX

    def test_filter_by_capabilities_all_solvers(self, selector):
        """Test filtering with no constraints (all solvers valid)."""
        features = ProblemFeatures(
            n_jobs=50,
            n_vehicles=2,
            has_time_windows=False,
            time_window_tightness=0.0,
            has_capacity=False,
            capacity_utilization=0.0,
            geographic_dispersion=0.1,
            cluster_coefficient=0.5,
            has_pickup_delivery=False,
            has_multi_depot=False,
            has_breaks=False,
            has_skills=False,
            constraint_complexity=0,
            estimated_solve_time_factor=0.5,
        )

        candidates = selector._filter_by_capabilities(features)

        assert SolverType.VROOM in candidates
        assert SolverType.ORTOOLS in candidates
        assert SolverType.GENETIC in candidates
        assert SolverType.GREEDY in candidates

    def test_filter_by_capabilities_pickup_delivery(self, selector):
        """Test filtering with pickup-delivery constraint."""
        features = ProblemFeatures(
            n_jobs=50,
            n_vehicles=2,
            has_time_windows=False,
            time_window_tightness=0.0,
            has_capacity=False,
            capacity_utilization=0.0,
            geographic_dispersion=0.1,
            cluster_coefficient=0.5,
            has_pickup_delivery=True,  # VROOM doesn't support this
            has_multi_depot=False,
            has_breaks=False,
            has_skills=False,
            constraint_complexity=2,
            estimated_solve_time_factor=0.5,
        )

        candidates = selector._filter_by_capabilities(features)

        assert SolverType.VROOM not in candidates
        assert SolverType.ORTOOLS in candidates
        assert SolverType.GENETIC in candidates
        assert SolverType.GREEDY in candidates

    def test_filter_by_capabilities_breaks(self, selector):
        """Test filtering with breaks constraint."""
        features = ProblemFeatures(
            n_jobs=50,
            n_vehicles=2,
            has_time_windows=False,
            time_window_tightness=0.0,
            has_capacity=False,
            capacity_utilization=0.0,
            geographic_dispersion=0.1,
            cluster_coefficient=0.5,
            has_pickup_delivery=False,
            has_multi_depot=False,
            has_breaks=True,  # GENETIC doesn't support this
            has_skills=False,
            constraint_complexity=1,
            estimated_solve_time_factor=0.5,
        )

        candidates = selector._filter_by_capabilities(features)

        assert SolverType.VROOM in candidates
        assert SolverType.ORTOOLS in candidates
        assert SolverType.GENETIC not in candidates
        assert SolverType.GREEDY not in candidates

    def test_filter_by_capabilities_job_limit(self, selector):
        """Test filtering by max jobs feasible."""
        features = ProblemFeatures(
            n_jobs=10000,  # Very large problem
            n_vehicles=50,
            has_time_windows=False,
            time_window_tightness=0.0,
            has_capacity=False,
            capacity_utilization=0.0,
            geographic_dispersion=0.5,
            cluster_coefficient=0.5,
            has_pickup_delivery=False,
            has_multi_depot=False,
            has_breaks=False,
            has_skills=False,
            constraint_complexity=4,
            estimated_solve_time_factor=100.0,
        )

        candidates = selector._filter_by_capabilities(features)

        # Only GREEDY can handle infinite jobs
        assert SolverType.VROOM not in candidates  # max 500
        assert SolverType.ORTOOLS not in candidates  # max 2000
        assert SolverType.GENETIC not in candidates  # max 5000
        assert SolverType.GREEDY in candidates

    def test_score_solver_speed_preference(self, selector):
        """Test scoring with speed preference."""
        features = ProblemFeatures(
            n_jobs=50,
            n_vehicles=2,
            has_time_windows=False,
            time_window_tightness=0.0,
            has_capacity=False,
            capacity_utilization=0.0,
            geographic_dispersion=0.1,
            cluster_coefficient=0.5,
            has_pickup_delivery=False,
            has_multi_depot=False,
            has_breaks=False,
            has_skills=False,
            constraint_complexity=0,
            estimated_solve_time_factor=0.5,
        )

        score_normal = selector._score_solver(SolverType.GREEDY, features, False, False)
        score_speed = selector._score_solver(SolverType.GREEDY, features, True, False)

        # GREEDY should score higher with speed preference (speed_factor=0.1)
        assert score_speed > score_normal

    def test_score_solver_quality_preference(self, selector):
        """Test scoring with quality preference."""
        features = ProblemFeatures(
            n_jobs=50,
            n_vehicles=2,
            has_time_windows=False,
            time_window_tightness=0.0,
            has_capacity=False,
            capacity_utilization=0.0,
            geographic_dispersion=0.1,
            cluster_coefficient=0.5,
            has_pickup_delivery=False,
            has_multi_depot=False,
            has_breaks=False,
            has_skills=False,
            constraint_complexity=0,
            estimated_solve_time_factor=0.5,
        )

        score_normal = selector._score_solver(SolverType.ORTOOLS, features, False, False)
        score_quality = selector._score_solver(SolverType.ORTOOLS, features, False, True)

        # OR-Tools should score higher with quality preference
        assert score_quality > score_normal

    def test_select_small_simple_problem(self, selector, simple_job, simple_vehicle):
        """Test selection for small simple problem prefers VROOM."""
        jobs = [simple_job for _ in range(30)]

        problem = RoutingProblem(
            jobs=jobs,
            vehicles=[simple_vehicle],
            planning_date=datetime.now().date(),
        )

        result = selector.select(problem)

        # For small simple problems, VROOM is typically best
        assert result in [SolverType.VROOM, SolverType.ORTOOLS]

    def test_select_large_problem(self, selector, simple_vehicle):
        """Test selection for large problem."""
        jobs = [
            Job(
                id=uuid4(),
                location=Location(
                    latitude=41.0 + i * 0.001,
                    longitude=69.0 + i * 0.001,
                    address=f"P{i}",
                ),
                priority=1,
                demand_kg=1.0,
            )
            for i in range(400)
        ]

        problem = RoutingProblem(
            jobs=jobs,
            vehicles=[simple_vehicle] * 10,
            planning_date=datetime.now().date(),
        )

        result = selector.select(problem)

        # For large problems, GENETIC or ORTOOLS expected
        assert result in [SolverType.GENETIC, SolverType.ORTOOLS]

    def test_select_with_speed_preference(self, selector, simple_job, simple_vehicle):
        """Test selection with speed preference."""
        jobs = [simple_job for _ in range(50)]

        problem = RoutingProblem(
            jobs=jobs,
            vehicles=[simple_vehicle],
            planning_date=datetime.now().date(),
        )

        result = selector.select(problem, prefer_speed=True)

        # With speed preference, faster solvers should be preferred
        assert result is not None

    def test_select_with_quality_preference(self, selector, simple_job, simple_vehicle):
        """Test selection with quality preference."""
        jobs = [simple_job for _ in range(50)]

        problem = RoutingProblem(
            jobs=jobs,
            vehicles=[simple_vehicle],
            planning_date=datetime.now().date(),
        )

        result = selector.select(problem, prefer_quality=True)

        assert result is not None

    def test_get_recommendation_reason_vroom(self, selector):
        """Test recommendation reason for VROOM."""
        features = ProblemFeatures(
            n_jobs=50,
            n_vehicles=2,
            has_time_windows=False,
            time_window_tightness=0.0,
            has_capacity=False,
            capacity_utilization=0.0,
            geographic_dispersion=0.1,
            cluster_coefficient=0.5,
            has_pickup_delivery=False,
            has_multi_depot=False,
            has_breaks=False,
            has_skills=False,
            constraint_complexity=0,
            estimated_solve_time_factor=0.5,
        )

        reason = selector.get_recommendation_reason(SolverType.VROOM, features)

        assert "Fast" in reason or "97%" in reason

    def test_get_recommendation_reason_ortools(self, selector):
        """Test recommendation reason for OR-Tools."""
        features = ProblemFeatures(
            n_jobs=100,
            n_vehicles=5,
            has_time_windows=True,
            time_window_tightness=0.7,
            has_capacity=True,
            capacity_utilization=0.8,
            geographic_dispersion=0.3,
            cluster_coefficient=0.5,
            has_pickup_delivery=False,
            has_multi_depot=False,
            has_breaks=False,
            has_skills=False,
            constraint_complexity=5,
            estimated_solve_time_factor=2.0,
        )

        reason = selector.get_recommendation_reason(SolverType.ORTOOLS, features)

        assert "time window" in reason.lower() or "complex" in reason.lower()

    def test_get_recommendation_reason_greedy(self, selector):
        """Test recommendation reason for GREEDY."""
        features = ProblemFeatures(
            n_jobs=50,
            n_vehicles=2,
            has_time_windows=False,
            time_window_tightness=0.0,
            has_capacity=False,
            capacity_utilization=0.0,
            geographic_dispersion=0.1,
            cluster_coefficient=0.5,
            has_pickup_delivery=False,
            has_multi_depot=False,
            has_breaks=False,
            has_skills=False,
            constraint_complexity=0,
            estimated_solve_time_factor=0.5,
        )

        reason = selector.get_recommendation_reason(SolverType.GREEDY, features)

        assert "fast" in reason.lower() or "fallback" in reason.lower()


class TestSolverSelectorSingleton:
    """Tests for singleton instance."""

    def test_singleton_exists(self):
        """Test singleton instance exists."""
        assert solver_selector is not None
        assert isinstance(solver_selector, SmartSolverSelector)

    def test_singleton_has_profiles(self):
        """Test singleton has solver profiles."""
        assert solver_selector.profiles is not None
        assert len(solver_selector.profiles) == 4
