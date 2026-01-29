"""
Smart Solver Selection (R3).

Intelligent solver selection based on problem characteristics.
Uses feature extraction and rule-based heuristics to choose
the optimal solver for each problem.

Can be upgraded to ML-based selection in the future.
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from app.services.solver_interface import RoutingProblem, SolverType

logger = logging.getLogger(__name__)


class ProblemComplexity(str, Enum):
    """Problem complexity classification."""

    SIMPLE = "simple"  # <50 jobs, no complex constraints
    MEDIUM = "medium"  # 50-200 jobs, basic constraints
    COMPLEX = "complex"  # 200-500 jobs, multiple constraints
    VERY_COMPLEX = "very_complex"  # >500 jobs or advanced constraints


@dataclass
class ProblemFeatures:
    """
    Features extracted from routing problem.

    Used for solver selection decision.
    """

    # Size metrics
    n_jobs: int
    n_vehicles: int

    # Constraint complexity
    has_time_windows: bool
    time_window_tightness: float  # 0-1 (1 = very tight)
    has_capacity: bool
    capacity_utilization: float  # 0-1

    # Geographic features
    geographic_dispersion: float  # std of coordinates
    cluster_coefficient: float  # 0-1 (1 = highly clustered)

    # Advanced constraints
    has_pickup_delivery: bool
    has_multi_depot: bool
    has_breaks: bool
    has_skills: bool

    # Derived
    constraint_complexity: int  # 0-10 score
    estimated_solve_time_factor: float


@dataclass
class SolverProfile:
    """Performance profile for a solver."""

    solver_type: SolverType
    max_jobs_efficient: int
    max_jobs_feasible: int
    supports_pickup_delivery: bool
    supports_multi_depot: bool
    supports_breaks: bool
    speed_factor: float  # 1.0 = baseline
    quality_factor: float  # 0-1, typical solution quality vs optimal


# Solver profiles based on benchmarks
SOLVER_PROFILES = {
    SolverType.VROOM: SolverProfile(
        solver_type=SolverType.VROOM,
        max_jobs_efficient=150,
        max_jobs_feasible=500,
        supports_pickup_delivery=False,
        supports_multi_depot=True,
        supports_breaks=True,
        speed_factor=1.0,
        quality_factor=0.97,
    ),
    SolverType.ORTOOLS: SolverProfile(
        solver_type=SolverType.ORTOOLS,
        max_jobs_efficient=300,
        max_jobs_feasible=2000,
        supports_pickup_delivery=True,
        supports_multi_depot=True,
        supports_breaks=True,
        speed_factor=3.0,
        quality_factor=0.98,
    ),
    SolverType.GENETIC: SolverProfile(
        solver_type=SolverType.GENETIC,
        max_jobs_efficient=1000,
        max_jobs_feasible=5000,
        supports_pickup_delivery=True,
        supports_multi_depot=True,
        supports_breaks=False,
        speed_factor=5.0,
        quality_factor=0.92,
    ),
    SolverType.GREEDY: SolverProfile(
        solver_type=SolverType.GREEDY,
        max_jobs_efficient=float("inf"),
        max_jobs_feasible=float("inf"),
        supports_pickup_delivery=True,
        supports_multi_depot=True,
        supports_breaks=False,
        speed_factor=0.1,
        quality_factor=0.85,
    ),
}


class SmartSolverSelector:
    """
    Intelligent solver selection based on problem characteristics.

    Selection Strategy:
    1. Extract features from problem
    2. Filter solvers by hard constraints (capabilities)
    3. Score remaining solvers by expected performance
    4. Return best solver for the problem
    """

    def __init__(self):
        self.profiles = SOLVER_PROFILES

    def select(
        self,
        problem: RoutingProblem,
        prefer_speed: bool = False,
        prefer_quality: bool = False,
    ) -> SolverType:
        """
        Select best solver for the problem.

        Args:
            problem: Routing problem to solve
            prefer_speed: Prioritize faster solvers
            prefer_quality: Prioritize higher quality solvers

        Returns:
            Selected SolverType
        """
        features = self.extract_features(problem)
        complexity = self.classify_complexity(features)

        logger.debug(
            f"Problem features: {features.n_jobs} jobs, "
            f"complexity={complexity.value}, "
            f"tw_tightness={features.time_window_tightness:.2f}"
        )

        # Filter by hard constraints
        candidates = self._filter_by_capabilities(features)

        if not candidates:
            logger.warning("No suitable solver found, defaulting to GREEDY")
            return SolverType.GREEDY

        # Score candidates
        scores = {}
        for solver_type in candidates:
            scores[solver_type] = self._score_solver(
                solver_type, features, prefer_speed, prefer_quality
            )

        # Select best
        best_solver = max(scores, key=scores.get)

        logger.info(
            f"Selected solver: {best_solver.value} "
            f"(score={scores[best_solver]:.2f}, "
            f"complexity={complexity.value})"
        )

        return best_solver

    def extract_features(self, problem: RoutingProblem) -> ProblemFeatures:
        """Extract features from routing problem."""
        n_jobs = len(problem.jobs)
        n_vehicles = len(problem.vehicles) if problem.vehicles else 1

        # Time window analysis
        tw_tightness = 0.0
        if problem.has_time_windows:
            window_widths = []
            for job in problem.jobs:
                if job.time_window_start and job.time_window_end:
                    width = (
                        job.time_window_end - job.time_window_start
                    ).total_seconds() / 3600
                    window_widths.append(width)

            if window_widths:
                avg_width = np.mean(window_widths)
                # Normalize: 1 hour = very tight (1.0), 8 hours = loose (0.0)
                tw_tightness = max(0, min(1, 1 - (avg_width - 1) / 7))

        # Capacity analysis
        has_capacity = any(
            v.capacity_kg and v.capacity_kg > 0
            for v in (problem.vehicles or [])
        )
        capacity_utilization = 0.0
        if has_capacity and problem.vehicles:
            total_demand = sum(j.demand_kg or 0 for j in problem.jobs)
            total_capacity = sum(v.capacity_kg or 0 for v in problem.vehicles)
            if total_capacity > 0:
                capacity_utilization = min(1.0, total_demand / total_capacity)

        # Geographic analysis
        geographic_dispersion = 0.0
        cluster_coefficient = 0.5
        if problem.jobs:
            lats = [j.location.latitude for j in problem.jobs]
            lons = [j.location.longitude for j in problem.jobs]
            geographic_dispersion = np.std(lats) + np.std(lons)

            # Simple cluster coefficient based on dispersion
            # Low dispersion = high clustering
            cluster_coefficient = max(0, min(1, 1 - geographic_dispersion / 2))

        # Constraint complexity score
        constraint_complexity = 0
        if problem.has_time_windows:
            constraint_complexity += 2
        if has_capacity:
            constraint_complexity += 1
        if tw_tightness > 0.5:
            constraint_complexity += 2
        if n_vehicles > 5:
            constraint_complexity += 1
        if n_jobs > 200:
            constraint_complexity += 2
        if n_jobs > 500:
            constraint_complexity += 2

        # Check advanced constraints
        has_pickup_delivery = any(
            hasattr(j, "pickup_location") and j.pickup_location
            for j in problem.jobs
        )
        has_multi_depot = (
            problem.vehicles
            and len(set(
                (v.start_location.latitude, v.start_location.longitude)
                for v in problem.vehicles
                if v.start_location
            )) > 1
        )
        has_breaks = any(
            v.breaks for v in (problem.vehicles or [])
        )
        has_skills = any(
            hasattr(j, "required_skills") and j.required_skills
            for j in problem.jobs
        )

        # Estimated solve time factor
        solve_time_factor = (
            n_jobs / 100 *
            (1 + constraint_complexity / 5) *
            (1 + tw_tightness)
        )

        return ProblemFeatures(
            n_jobs=n_jobs,
            n_vehicles=n_vehicles,
            has_time_windows=problem.has_time_windows,
            time_window_tightness=tw_tightness,
            has_capacity=has_capacity,
            capacity_utilization=capacity_utilization,
            geographic_dispersion=geographic_dispersion,
            cluster_coefficient=cluster_coefficient,
            has_pickup_delivery=has_pickup_delivery,
            has_multi_depot=has_multi_depot,
            has_breaks=has_breaks,
            has_skills=has_skills,
            constraint_complexity=constraint_complexity,
            estimated_solve_time_factor=solve_time_factor,
        )

    def classify_complexity(self, features: ProblemFeatures) -> ProblemComplexity:
        """Classify problem complexity."""
        if features.n_jobs > 500 or features.constraint_complexity >= 8:
            return ProblemComplexity.VERY_COMPLEX
        elif features.n_jobs > 200 or features.constraint_complexity >= 5:
            return ProblemComplexity.COMPLEX
        elif features.n_jobs > 50 or features.constraint_complexity >= 3:
            return ProblemComplexity.MEDIUM
        else:
            return ProblemComplexity.SIMPLE

    def _filter_by_capabilities(
        self,
        features: ProblemFeatures,
    ) -> list[SolverType]:
        """Filter solvers by required capabilities."""
        candidates = []

        for solver_type, profile in self.profiles.items():
            # Check hard constraints
            if features.has_pickup_delivery and not profile.supports_pickup_delivery:
                continue

            if features.has_multi_depot and not profile.supports_multi_depot:
                continue

            if features.has_breaks and not profile.supports_breaks:
                continue

            # Check size limits
            if features.n_jobs > profile.max_jobs_feasible:
                continue

            candidates.append(solver_type)

        return candidates

    def _score_solver(
        self,
        solver_type: SolverType,
        features: ProblemFeatures,
        prefer_speed: bool,
        prefer_quality: bool,
    ) -> float:
        """
        Score a solver for the given problem.

        Higher score = better match.
        """
        profile = self.profiles[solver_type]
        score = 0.0

        # Size efficiency (0-30 points)
        if features.n_jobs <= profile.max_jobs_efficient:
            score += 30
        elif features.n_jobs <= profile.max_jobs_feasible:
            efficiency_ratio = profile.max_jobs_efficient / features.n_jobs
            score += 30 * efficiency_ratio
        else:
            score -= 50  # Penalty for exceeding limits

        # Quality factor (0-30 points)
        quality_weight = 1.5 if prefer_quality else 1.0
        score += profile.quality_factor * 30 * quality_weight

        # Speed factor (0-30 points)
        speed_weight = 1.5 if prefer_speed else 1.0
        # Inverse of speed_factor (lower = faster = better)
        speed_score = 30 / profile.speed_factor
        score += speed_score * speed_weight

        # Constraint handling bonus (0-10 points)
        if features.has_time_windows and features.time_window_tightness > 0.5:
            # OR-Tools handles tight windows better
            if solver_type == SolverType.ORTOOLS:
                score += 10
            elif solver_type == SolverType.VROOM:
                score += 5

        # Large problem bonus for GA
        if features.n_jobs > 300 and solver_type == SolverType.GENETIC:
            score += 15

        # VROOM bonus for simple problems
        if features.constraint_complexity < 3 and solver_type == SolverType.VROOM:
            score += 10

        return score

    def get_recommendation_reason(
        self,
        solver_type: SolverType,
        features: ProblemFeatures,
    ) -> str:
        """Get human-readable reason for solver recommendation."""
        profile = self.profiles[solver_type]

        reasons = []

        if solver_type == SolverType.VROOM:
            if features.n_jobs < 100:
                reasons.append("Fast for small-medium problems")
            reasons.append(f"Quality: {profile.quality_factor*100:.0f}% optimal")

        elif solver_type == SolverType.ORTOOLS:
            if features.has_time_windows:
                reasons.append("Excellent time window handling")
            if features.constraint_complexity > 3:
                reasons.append("Handles complex constraints")
            reasons.append(f"Quality: {profile.quality_factor*100:.0f}% optimal")

        elif solver_type == SolverType.GENETIC:
            if features.n_jobs > 300:
                reasons.append("Efficient for large problems")
            reasons.append("Good for multi-objective optimization")

        elif solver_type == SolverType.GREEDY:
            reasons.append("Guaranteed fast solution")
            reasons.append("Fallback when others fail")

        return "; ".join(reasons)


# Singleton instance
solver_selector = SmartSolverSelector()
