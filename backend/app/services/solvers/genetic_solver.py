"""
Genetic Algorithm VRP Solver (R1).

Advanced evolutionary algorithm for complex vehicle routing problems.

Best for:
- Multi-objective optimization (distance + time + priority)
- Non-linear constraints
- Very large problems (>500 points)

Reference: Holland, J.H. (1975). Adaptation in Natural and Artificial Systems.
"""
import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

import numpy as np

from app.services.solvers.solver_interface import (
    RouteSolver,
    SolverFactory,
    SolverType,
    RoutingProblem,
    SolutionResult,
    Route,
    RouteStep,
    Location,
)

logger = logging.getLogger(__name__)


@dataclass
class GAConfig:
    """Genetic Algorithm configuration."""

    population_size: int = 100
    generations: int = 500
    mutation_rate: float = 0.15
    crossover_rate: float = 0.85
    elite_size: int = 10
    tournament_size: int = 5
    early_stop_generations: int = 50

    # Penalty weights for constraint violations
    capacity_penalty: float = 10000
    time_window_penalty: float = 5000
    overtime_penalty: float = 2000


@dataclass
class Individual:
    """
    Represents a solution in the population.

    Chromosome: List of job indices representing visit order.
    Fitness: Negative cost (higher = better).
    """

    chromosome: list[int]
    fitness: float = 0.0
    violations: int = 0
    total_distance: float = 0.0
    routes: list[list[int]] = field(default_factory=list)


@SolverFactory.register(SolverType.GENETIC)
class GeneticSolver(RouteSolver):
    """
    Genetic Algorithm solver for complex VRP.

    Implements:
    - Tournament selection
    - Order crossover (OX) for permutations
    - Multiple mutation operators (swap, insert, 2-opt)
    - Elitism to preserve best solutions
    - Early stopping on convergence

    Chromosome representation: permutation of job indices
    """

    def __init__(self, config: Optional[GAConfig] = None):
        self.config = config or GAConfig()
        self._distance_matrix: Optional[np.ndarray] = None
        self._problem: Optional[RoutingProblem] = None

    @property
    def solver_type(self) -> SolverType:
        return SolverType.GENETIC

    async def health_check(self) -> bool:
        """GA solver is always available (no external dependencies)."""
        return True

    async def solve(self, problem: RoutingProblem) -> SolutionResult:
        """
        Solve VRP using Genetic Algorithm.

        Args:
            problem: Routing problem to solve

        Returns:
            SolutionResult with optimized routes
        """
        self._problem = problem
        n_jobs = len(problem.jobs)

        if n_jobs == 0:
            return SolutionResult(
                routes=[],
                unassigned_jobs=[],
                total_distance_m=0,
                total_duration_s=0,
                summary={"algorithm": "genetic", "reason": "no_jobs"},
            )

        logger.info(f"Starting GA solver: {n_jobs} jobs, {len(problem.vehicles or [])} vehicles")

        # Build distance matrix
        self._distance_matrix = await self._build_distance_matrix(problem)

        # Initialize population
        population = self._initialize_population(n_jobs)

        # Evolution loop
        best_fitness = float("-inf")
        generations_without_improvement = 0
        best_individual: Optional[Individual] = None

        for gen in range(self.config.generations):
            # Evaluate fitness for all individuals
            for individual in population:
                self._evaluate_fitness(individual, problem)

            # Sort by fitness (descending)
            population.sort(key=lambda x: x.fitness, reverse=True)

            # Track best
            if population[0].fitness > best_fitness:
                best_fitness = population[0].fitness
                best_individual = population[0]
                generations_without_improvement = 0
            else:
                generations_without_improvement += 1

            # Log progress
            if gen % 50 == 0:
                logger.debug(
                    f"Generation {gen}: best_fitness={best_fitness:.0f}, "
                    f"best_distance={population[0].total_distance:.0f}m"
                )

            # Early stopping
            if generations_without_improvement >= self.config.early_stop_generations:
                logger.info(f"GA converged at generation {gen}")
                break

            # Selection
            parents = self._tournament_selection(population)

            # Crossover
            offspring = self._crossover(parents)

            # Mutation
            offspring = self._mutate(offspring)

            # Create next generation with elitism
            elite = population[: self.config.elite_size]
            population = elite + offspring[: len(population) - self.config.elite_size]

        # Return best solution
        if best_individual:
            return self._decode_solution(best_individual, problem)

        # Fallback
        return SolutionResult(
            routes=[],
            unassigned_jobs=[job.id for job in problem.jobs],
            total_distance_m=0,
            total_duration_s=0,
            summary={"algorithm": "genetic", "error": "no_solution_found"},
        )

    def _initialize_population(self, n_jobs: int) -> list[Individual]:
        """Create initial random population."""
        population = []

        for _ in range(self.config.population_size):
            # Random permutation of job indices
            chromosome = list(range(n_jobs))
            random.shuffle(chromosome)
            population.append(Individual(chromosome=chromosome))

        return population

    def _evaluate_fitness(
        self,
        individual: Individual,
        problem: RoutingProblem,
    ) -> None:
        """
        Evaluate fitness of an individual.

        Fitness = -cost where cost = distance + penalties
        Higher fitness is better.
        """
        # Split chromosome into routes per vehicle
        routes = self._split_into_routes(individual.chromosome, problem)
        individual.routes = routes

        total_distance = 0.0
        total_violations = 0

        for route in routes:
            if not route:
                continue

            # Calculate route distance
            route_distance = self._calculate_route_distance(route)
            total_distance += route_distance

            # Check capacity violations
            capacity_violation = self._check_capacity_violation(route, problem)
            total_violations += capacity_violation

            # Check time window violations
            tw_violation = self._check_time_window_violations(route, problem)
            total_violations += tw_violation

        individual.total_distance = total_distance
        individual.violations = total_violations

        # Cost = distance + penalties
        penalty = total_violations * self.config.capacity_penalty
        cost = total_distance + penalty

        # Fitness is negative cost (maximize fitness = minimize cost)
        individual.fitness = -cost

    def _split_into_routes(
        self,
        chromosome: list[int],
        problem: RoutingProblem,
    ) -> list[list[int]]:
        """
        Split chromosome into routes for each vehicle.

        Simple split based on capacity constraints.
        """
        if not problem.vehicles:
            # Single vehicle scenario
            return [chromosome.copy()]

        routes: list[list[int]] = [[] for _ in problem.vehicles]
        vehicle_loads = [0.0] * len(problem.vehicles)
        vehicle_capacities = [
            v.capacity_kg or float("inf") for v in problem.vehicles
        ]

        # Assign jobs to vehicles (bin packing style)
        for job_idx in chromosome:
            job = problem.jobs[job_idx]
            job_demand = job.demand_kg or 0

            # Find vehicle with capacity
            assigned = False
            for v_idx in range(len(problem.vehicles)):
                if vehicle_loads[v_idx] + job_demand <= vehicle_capacities[v_idx]:
                    routes[v_idx].append(job_idx)
                    vehicle_loads[v_idx] += job_demand
                    assigned = True
                    break

            if not assigned:
                # Assign to least loaded vehicle (will incur penalty)
                min_load_idx = vehicle_loads.index(min(vehicle_loads))
                routes[min_load_idx].append(job_idx)
                vehicle_loads[min_load_idx] += job_demand

        return routes

    def _calculate_route_distance(self, route: list[int]) -> float:
        """Calculate total distance for a route."""
        if not route or self._distance_matrix is None:
            return 0.0

        total = 0.0

        # Add distances between consecutive jobs
        for i in range(len(route) - 1):
            total += self._distance_matrix[route[i], route[i + 1]]

        return total

    def _check_capacity_violation(
        self,
        route: list[int],
        problem: RoutingProblem,
    ) -> int:
        """Count capacity violations in route."""
        if not problem.vehicles:
            return 0

        total_demand = sum(
            problem.jobs[job_idx].demand_kg or 0
            for job_idx in route
        )

        # Assume first vehicle capacity as limit
        capacity = problem.vehicles[0].capacity_kg or float("inf")

        if total_demand > capacity:
            return int(total_demand - capacity)

        return 0

    def _check_time_window_violations(
        self,
        route: list[int],
        problem: RoutingProblem,
    ) -> int:
        """Count time window violations in route."""
        violations = 0

        for job_idx in route:
            job = problem.jobs[job_idx]
            # Simplified check - would need arrival time simulation for accuracy
            if job.time_window_start and job.time_window_end:
                # Mark as potential violation if tight window
                window_hours = (
                    job.time_window_end - job.time_window_start
                ).total_seconds() / 3600
                if window_hours < 1:
                    violations += 1

        return violations

    def _tournament_selection(
        self,
        population: list[Individual],
    ) -> list[Individual]:
        """
        Tournament selection for parents.

        Select tournament_size random individuals, pick best.
        """
        selected = []

        for _ in range(len(population)):
            # Random tournament
            tournament = random.sample(population, self.config.tournament_size)
            winner = max(tournament, key=lambda x: x.fitness)
            selected.append(Individual(chromosome=winner.chromosome.copy()))

        return selected

    def _crossover(self, parents: list[Individual]) -> list[Individual]:
        """
        Apply Order Crossover (OX) to create offspring.

        OX preserves relative order of elements, suitable for TSP/VRP.
        """
        offspring = []

        for i in range(0, len(parents) - 1, 2):
            if random.random() < self.config.crossover_rate:
                c1, c2 = self._order_crossover(
                    parents[i].chromosome,
                    parents[i + 1].chromosome,
                )
                offspring.append(Individual(chromosome=c1))
                offspring.append(Individual(chromosome=c2))
            else:
                offspring.append(Individual(chromosome=parents[i].chromosome.copy()))
                offspring.append(Individual(chromosome=parents[i + 1].chromosome.copy()))

        return offspring

    def _order_crossover(
        self,
        parent1: list[int],
        parent2: list[int],
    ) -> tuple[list[int], list[int]]:
        """
        Order Crossover (OX) implementation.

        1. Select random segment from parent1
        2. Copy segment to child1
        3. Fill remaining positions from parent2 (preserving order)
        """
        size = len(parent1)
        if size < 3:
            return parent1.copy(), parent2.copy()

        # Random segment
        start, end = sorted(random.sample(range(size), 2))

        # Child 1: segment from parent1
        child1 = [-1] * size
        child1[start:end] = parent1[start:end]

        # Fill from parent2
        segment1 = set(parent1[start:end])
        fill_values = [x for x in parent2 if x not in segment1]
        fill_idx = 0

        for i in list(range(end, size)) + list(range(0, start)):
            if fill_idx < len(fill_values):
                child1[i] = fill_values[fill_idx]
                fill_idx += 1

        # Child 2: segment from parent2
        child2 = [-1] * size
        child2[start:end] = parent2[start:end]

        segment2 = set(parent2[start:end])
        fill_values = [x for x in parent1 if x not in segment2]
        fill_idx = 0

        for i in list(range(end, size)) + list(range(0, start)):
            if fill_idx < len(fill_values):
                child2[i] = fill_values[fill_idx]
                fill_idx += 1

        return child1, child2

    def _mutate(self, population: list[Individual]) -> list[Individual]:
        """
        Apply mutation operators.

        Operators:
        - Swap: Exchange two random positions
        - Insert: Remove and insert at different position
        - 2-opt: Reverse a segment
        """
        for individual in population:
            if random.random() < self.config.mutation_rate:
                mutation_type = random.choice(["swap", "insert", "2opt"])

                if mutation_type == "swap":
                    self._swap_mutation(individual)
                elif mutation_type == "insert":
                    self._insert_mutation(individual)
                else:
                    self._2opt_mutation(individual)

        return population

    def _swap_mutation(self, individual: Individual) -> None:
        """Swap two random positions."""
        if len(individual.chromosome) < 2:
            return

        i, j = random.sample(range(len(individual.chromosome)), 2)
        individual.chromosome[i], individual.chromosome[j] = (
            individual.chromosome[j],
            individual.chromosome[i],
        )

    def _insert_mutation(self, individual: Individual) -> None:
        """Remove and insert at random position."""
        if len(individual.chromosome) < 2:
            return

        i = random.randint(0, len(individual.chromosome) - 1)
        j = random.randint(0, len(individual.chromosome) - 1)

        gene = individual.chromosome.pop(i)
        individual.chromosome.insert(j, gene)

    def _2opt_mutation(self, individual: Individual) -> None:
        """Reverse a random segment."""
        if len(individual.chromosome) < 3:
            return

        i, j = sorted(random.sample(range(len(individual.chromosome)), 2))
        individual.chromosome[i : j + 1] = reversed(individual.chromosome[i : j + 1])

    async def _build_distance_matrix(
        self,
        problem: RoutingProblem,
    ) -> np.ndarray:
        """Build distance matrix for the problem."""
        n = len(problem.jobs)

        try:
            from app.services.routing.osrm_client import osrm_client
            from app.services.caching.parallel_matrix import ParallelMatrixComputer

            coords = [
                (job.location.longitude, job.location.latitude)
                for job in problem.jobs
            ]

            # Use parallel computation for large problems
            if n > 100:
                computer = ParallelMatrixComputer(osrm_client)
                durations, _ = await computer.compute(coords)
                return durations
            else:
                result = await osrm_client.get_table(coords)
                return np.array(result.durations) if result.durations else self._euclidean_matrix(problem)

        except Exception as e:
            logger.warning(f"OSRM failed, using Euclidean: {e}")
            return self._euclidean_matrix(problem)

    def _euclidean_matrix(self, problem: RoutingProblem) -> np.ndarray:
        """Fallback Euclidean distance matrix."""
        from math import atan2, cos, radians, sin, sqrt

        n = len(problem.jobs)
        matrix = np.zeros((n, n))

        def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            R = 6371000  # Earth radius in meters
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            return R * 2 * atan2(sqrt(a), sqrt(1 - a))

        for i, job_i in enumerate(problem.jobs):
            for j, job_j in enumerate(problem.jobs):
                if i != j:
                    matrix[i, j] = haversine(
                        job_i.location.latitude,
                        job_i.location.longitude,
                        job_j.location.latitude,
                        job_j.location.longitude,
                    )

        return matrix

    def _decode_solution(
        self,
        individual: Individual,
        problem: RoutingProblem,
    ) -> SolutionResult:
        """Convert best individual to SolutionResult."""
        from datetime import datetime, timedelta

        routes = []
        unassigned = []

        for v_idx, route_indices in enumerate(individual.routes):
            if not route_indices:
                continue

            vehicle = problem.vehicles[v_idx] if problem.vehicles and v_idx < len(problem.vehicles) else None
            vehicle_id = vehicle.id if vehicle else None

            steps = []
            current_time = datetime.combine(
                problem.planning_date or datetime.now().date(),
                vehicle.work_start if vehicle else datetime.min.time(),
            )

            for seq, job_idx in enumerate(route_indices):
                job = problem.jobs[job_idx]
                service_time = job.location.service_time_minutes or 15

                arrival = current_time
                departure = arrival + timedelta(minutes=service_time)

                steps.append(
                    RouteStep(
                        step_type="job",
                        job_id=job.id,
                        location=job.location,
                        arrival_time=arrival,
                        departure_time=departure,
                        distance_from_previous_m=0,
                        duration_from_previous_s=0,
                        load_after=0,
                    )
                )

                current_time = departure + timedelta(minutes=15)  # Travel estimate

            if steps:
                routes.append(
                    Route(
                        vehicle_id=vehicle_id,
                        steps=steps,
                        total_distance_m=individual.total_distance,
                        total_duration_s=int(individual.total_distance / 8.33),  # ~30km/h
                        total_load=sum(
                            problem.jobs[i].demand_kg or 0
                            for i in route_indices
                        ),
                        geometry=None,
                    )
                )

        return SolutionResult(
            routes=routes,
            unassigned_jobs=unassigned,
            total_distance_m=individual.total_distance,
            total_duration_s=int(individual.total_distance / 8.33),
            summary={
                "algorithm": "genetic",
                "generations": self.config.generations,
                "population_size": self.config.population_size,
                "final_fitness": individual.fitness,
                "violations": individual.violations,
            },
        )

    async def solve_tsp(
        self,
        locations: list[Location],
        start_index: int = 0,
        return_to_start: bool = True,
    ) -> list[int]:
        """
        Solve TSP using Genetic Algorithm.

        Args:
            locations: List of locations
            start_index: Starting location index
            return_to_start: Whether to return to start

        Returns:
            Optimized visit order as list of indices
        """
        n = len(locations)

        if n <= 2:
            return list(range(n))

        # Build distance matrix
        from math import atan2, cos, radians, sin, sqrt

        def haversine(loc1: Location, loc2: Location) -> float:
            R = 6371000
            lat1, lon1 = radians(loc1.latitude), radians(loc1.longitude)
            lat2, lon2 = radians(loc2.latitude), radians(loc2.longitude)
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            return R * 2 * atan2(sqrt(a), sqrt(1 - a))

        self._distance_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i != j:
                    self._distance_matrix[i, j] = haversine(locations[i], locations[j])

        # Run GA
        population = self._initialize_population(n)

        best_route = list(range(n))
        best_distance = float("inf")

        for gen in range(min(self.config.generations, 200)):
            for individual in population:
                dist = self._calculate_route_distance(individual.chromosome)
                individual.fitness = -dist
                individual.total_distance = dist

            population.sort(key=lambda x: x.fitness, reverse=True)

            if population[0].total_distance < best_distance:
                best_distance = population[0].total_distance
                best_route = population[0].chromosome.copy()

            # Selection and evolution
            parents = self._tournament_selection(population)
            offspring = self._crossover(parents)
            offspring = self._mutate(offspring)
            elite = population[: self.config.elite_size]
            population = elite + offspring[: len(population) - self.config.elite_size]

        # Ensure start_index is first
        if start_index in best_route:
            idx = best_route.index(start_index)
            best_route = best_route[idx:] + best_route[:idx]

        if return_to_start:
            best_route.append(best_route[0])

        return best_route
