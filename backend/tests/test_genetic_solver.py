"""
Tests for Genetic Algorithm VRP Solver.

Tests cover:
- GAConfig defaults and custom values
- Individual creation and manipulation
- Population initialization
- Order Crossover (OX) algorithm
- Mutation operators (swap, insert, 2-opt)
- Tournament selection
- Fitness evaluation
- solve_tsp() method
"""
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, time
from uuid import uuid4

from app.services.genetic_solver import (
    GAConfig,
    Individual,
    GeneticSolver,
)
from app.services.solver_interface import (
    RoutingProblem,
    Job,
    Vehicle,
    Location,
    SolverType,
)


class TestGAConfig:
    """Tests for GAConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = GAConfig()

        assert config.population_size == 100
        assert config.generations == 500
        assert config.mutation_rate == 0.15
        assert config.crossover_rate == 0.85
        assert config.elite_size == 10
        assert config.tournament_size == 5
        assert config.early_stop_generations == 50

    def test_custom_values(self):
        """Test custom configuration values."""
        config = GAConfig(
            population_size=50,
            generations=100,
            mutation_rate=0.2,
            crossover_rate=0.9,
            elite_size=5,
            tournament_size=3,
        )

        assert config.population_size == 50
        assert config.generations == 100
        assert config.mutation_rate == 0.2
        assert config.crossover_rate == 0.9
        assert config.elite_size == 5
        assert config.tournament_size == 3

    def test_penalty_weights(self):
        """Test penalty weight defaults."""
        config = GAConfig()

        assert config.capacity_penalty == 10000
        assert config.time_window_penalty == 5000
        assert config.overtime_penalty == 2000


class TestIndividual:
    """Tests for Individual dataclass."""

    def test_creation(self):
        """Test basic individual creation."""
        ind = Individual(chromosome=[0, 1, 2, 3, 4])

        assert ind.chromosome == [0, 1, 2, 3, 4]
        assert ind.fitness == 0.0
        assert ind.violations == 0
        assert ind.total_distance == 0.0
        assert ind.routes == []

    def test_with_fitness(self):
        """Test individual with fitness values."""
        ind = Individual(
            chromosome=[0, 1, 2],
            fitness=-1000.0,
            violations=2,
            total_distance=5000.0,
            routes=[[0, 1], [2]],
        )

        assert ind.fitness == -1000.0
        assert ind.violations == 2
        assert ind.total_distance == 5000.0
        assert ind.routes == [[0, 1], [2]]


class TestGeneticSolver:
    """Tests for GeneticSolver class."""

    @pytest.fixture
    def solver(self):
        """Create solver instance with fast config."""
        config = GAConfig(
            population_size=20,
            generations=10,
            elite_size=2,
            tournament_size=3,
        )
        return GeneticSolver(config=config)

    @pytest.fixture
    def sample_locations(self):
        """Create sample locations for testing."""
        return [
            Location(latitude=41.311, longitude=69.279, address="Point 1"),
            Location(latitude=41.321, longitude=69.289, address="Point 2"),
            Location(latitude=41.331, longitude=69.299, address="Point 3"),
            Location(latitude=41.341, longitude=69.309, address="Point 4"),
            Location(latitude=41.351, longitude=69.319, address="Point 5"),
        ]

    @pytest.fixture
    def sample_jobs(self, sample_locations):
        """Create sample jobs for testing."""
        return [
            Job(
                id=uuid4(),
                location=loc,
                priority=1,
                demand_kg=10.0,
            )
            for loc in sample_locations
        ]

    @pytest.fixture
    def sample_vehicles(self):
        """Create sample vehicles for testing."""
        return [
            Vehicle(
                id=uuid4(),
                capacity_kg=100.0,
                work_start=time(8, 0),
                work_end=time(18, 0),
            ),
            Vehicle(
                id=uuid4(),
                capacity_kg=80.0,
                work_start=time(8, 0),
                work_end=time(18, 0),
            ),
        ]

    def test_solver_type(self, solver):
        """Test solver type property."""
        assert solver.solver_type == SolverType.GENETIC

    @pytest.mark.asyncio
    async def test_health_check(self, solver):
        """Test health check always returns True."""
        result = await solver.health_check()
        assert result is True

    def test_initialize_population(self, solver):
        """Test population initialization."""
        n_jobs = 10
        population = solver._initialize_population(n_jobs)

        assert len(population) == solver.config.population_size
        for individual in population:
            assert len(individual.chromosome) == n_jobs
            assert set(individual.chromosome) == set(range(n_jobs))

    def test_initialize_population_randomness(self, solver):
        """Test that population has randomness."""
        n_jobs = 10
        pop1 = solver._initialize_population(n_jobs)
        pop2 = solver._initialize_population(n_jobs)

        # Not all individuals should be the same
        different_count = sum(
            1 for i1, i2 in zip(pop1, pop2)
            if i1.chromosome != i2.chromosome
        )
        assert different_count > 0

    def test_order_crossover_small(self, solver):
        """Test OX crossover with small chromosomes."""
        parent1 = [0, 1]
        parent2 = [1, 0]

        child1, child2 = solver._order_crossover(parent1, parent2)

        # Small chromosomes returned as-is
        assert child1 == [0, 1]
        assert child2 == [1, 0]

    def test_order_crossover_preserves_genes(self, solver):
        """Test OX crossover preserves all genes."""
        parent1 = [0, 1, 2, 3, 4, 5, 6, 7]
        parent2 = [7, 6, 5, 4, 3, 2, 1, 0]

        for _ in range(10):
            child1, child2 = solver._order_crossover(parent1, parent2)

            assert set(child1) == set(parent1)
            assert set(child2) == set(parent2)
            assert len(child1) == len(parent1)
            assert len(child2) == len(parent2)

    def test_swap_mutation(self, solver):
        """Test swap mutation operator."""
        individual = Individual(chromosome=[0, 1, 2, 3, 4])
        original = individual.chromosome.copy()

        solver._swap_mutation(individual)

        # Should still contain same elements
        assert set(individual.chromosome) == set(original)
        assert len(individual.chromosome) == len(original)

    def test_swap_mutation_small(self, solver):
        """Test swap mutation with 1 element."""
        individual = Individual(chromosome=[0])
        solver._swap_mutation(individual)
        assert individual.chromosome == [0]

    def test_insert_mutation(self, solver):
        """Test insert mutation operator."""
        individual = Individual(chromosome=[0, 1, 2, 3, 4])
        original = individual.chromosome.copy()

        solver._insert_mutation(individual)

        # Should still contain same elements
        assert set(individual.chromosome) == set(original)
        assert len(individual.chromosome) == len(original)

    def test_insert_mutation_small(self, solver):
        """Test insert mutation with 1 element."""
        individual = Individual(chromosome=[0])
        solver._insert_mutation(individual)
        assert individual.chromosome == [0]

    def test_2opt_mutation(self, solver):
        """Test 2-opt mutation operator."""
        individual = Individual(chromosome=[0, 1, 2, 3, 4])
        original = individual.chromosome.copy()

        solver._2opt_mutation(individual)

        # Should still contain same elements
        assert set(individual.chromosome) == set(original)
        assert len(individual.chromosome) == len(original)

    def test_2opt_mutation_small(self, solver):
        """Test 2-opt mutation with small chromosome."""
        individual = Individual(chromosome=[0, 1])
        solver._2opt_mutation(individual)
        assert set(individual.chromosome) == {0, 1}

    def test_tournament_selection(self, solver):
        """Test tournament selection."""
        population = [
            Individual(chromosome=[i], fitness=-i * 100)
            for i in range(20)
        ]

        selected = solver._tournament_selection(population)

        assert len(selected) == len(population)
        for ind in selected:
            assert len(ind.chromosome) == 1

    def test_calculate_route_distance(self, solver):
        """Test route distance calculation."""
        solver._distance_matrix = np.array([
            [0, 100, 200],
            [100, 0, 150],
            [200, 150, 0],
        ])

        route = [0, 1, 2]
        distance = solver._calculate_route_distance(route)

        assert distance == 250  # 0->1 (100) + 1->2 (150)

    def test_calculate_route_distance_empty(self, solver):
        """Test route distance with empty route."""
        solver._distance_matrix = None
        distance = solver._calculate_route_distance([])
        assert distance == 0.0

    def test_euclidean_matrix(self, solver, sample_jobs):
        """Test Euclidean distance matrix fallback."""
        problem = RoutingProblem(
            jobs=sample_jobs,
            vehicles=[],
            planning_date=datetime.now().date(),
        )

        matrix = solver._euclidean_matrix(problem)

        assert matrix.shape == (len(sample_jobs), len(sample_jobs))
        assert np.all(np.diag(matrix) == 0)  # Diagonal is zero
        assert np.allclose(matrix, matrix.T, rtol=1e-5)  # Symmetric

    def test_split_into_routes_single_vehicle(self, solver, sample_jobs):
        """Test route splitting with single vehicle."""
        problem = RoutingProblem(
            jobs=sample_jobs,
            vehicles=[],
            planning_date=datetime.now().date(),
        )

        chromosome = list(range(len(sample_jobs)))
        routes = solver._split_into_routes(chromosome, problem)

        assert len(routes) == 1
        assert routes[0] == chromosome

    def test_split_into_routes_multiple_vehicles(self, solver, sample_jobs, sample_vehicles):
        """Test route splitting with multiple vehicles."""
        problem = RoutingProblem(
            jobs=sample_jobs,
            vehicles=sample_vehicles,
            planning_date=datetime.now().date(),
        )

        chromosome = list(range(len(sample_jobs)))
        routes = solver._split_into_routes(chromosome, problem)

        assert len(routes) == len(sample_vehicles)
        # All jobs should be assigned
        all_assigned = [j for route in routes for j in route]
        assert set(all_assigned) == set(chromosome)

    @pytest.mark.asyncio
    async def test_solve_empty_jobs(self, solver):
        """Test solving with no jobs."""
        problem = RoutingProblem(
            jobs=[],
            vehicles=[],
            planning_date=datetime.now().date(),
        )

        result = await solver.solve(problem)

        assert result.routes == []
        assert result.unassigned_jobs == []
        assert result.total_distance_m == 0
        assert result.summary["algorithm"] == "genetic"
        assert result.summary["reason"] == "no_jobs"

    @pytest.mark.asyncio
    async def test_solve_tsp_small(self, solver, sample_locations):
        """Test TSP solving with small input."""
        locations = sample_locations[:2]
        result = await solver.solve_tsp(locations)

        assert len(result) == 2
        assert set(result) == {0, 1}

    @pytest.mark.asyncio
    async def test_solve_tsp_returns_valid_tour(self, solver, sample_locations):
        """Test TSP returns valid tour."""
        result = await solver.solve_tsp(
            sample_locations,
            start_index=0,
            return_to_start=True,
        )

        # Should start with start_index
        assert result[0] == 0
        # Should end with start_index (return to start)
        assert result[-1] == 0
        # Should visit all locations
        assert set(result[:-1]) == set(range(len(sample_locations)))

    @pytest.mark.asyncio
    async def test_solve_tsp_no_return(self, solver, sample_locations):
        """Test TSP without returning to start."""
        result = await solver.solve_tsp(
            sample_locations,
            start_index=0,
            return_to_start=False,
        )

        assert result[0] == 0
        assert len(result) == len(sample_locations)
        assert set(result) == set(range(len(sample_locations)))

    @pytest.mark.asyncio
    async def test_solve_with_jobs(self, solver, sample_jobs, sample_vehicles):
        """Test solving with actual jobs and vehicles."""
        problem = RoutingProblem(
            jobs=sample_jobs,
            vehicles=sample_vehicles,
            planning_date=datetime.now().date(),
        )

        with patch.object(
            solver,
            '_build_distance_matrix',
            new_callable=AsyncMock,
        ) as mock_matrix:
            # Return simple distance matrix
            n = len(sample_jobs)
            mock_matrix.return_value = np.random.rand(n, n) * 1000

            result = await solver.solve(problem)

            assert result.summary["algorithm"] == "genetic"
            assert "final_fitness" in result.summary

    def test_evaluate_fitness(self, solver, sample_jobs, sample_vehicles):
        """Test fitness evaluation."""
        problem = RoutingProblem(
            jobs=sample_jobs,
            vehicles=sample_vehicles,
            planning_date=datetime.now().date(),
        )

        solver._problem = problem
        solver._distance_matrix = np.random.rand(len(sample_jobs), len(sample_jobs)) * 1000

        individual = Individual(chromosome=list(range(len(sample_jobs))))
        solver._evaluate_fitness(individual, problem)

        assert individual.fitness < 0  # Cost is positive, fitness is negative
        assert individual.total_distance >= 0
        assert isinstance(individual.routes, list)

    def test_crossover_rate_applied(self, solver):
        """Test that crossover rate is respected."""
        solver.config.crossover_rate = 0.0  # No crossover

        parents = [
            Individual(chromosome=[0, 1, 2]),
            Individual(chromosome=[2, 1, 0]),
        ]

        offspring = solver._crossover(parents)

        # With 0% crossover, children should be copies
        assert offspring[0].chromosome == [0, 1, 2]
        assert offspring[1].chromosome == [2, 1, 0]

    def test_mutate_rate_applied(self, solver):
        """Test mutation with 0% rate."""
        solver.config.mutation_rate = 0.0

        original = [0, 1, 2, 3, 4]
        population = [Individual(chromosome=original.copy())]

        mutated = solver._mutate(population)

        # With 0% mutation, chromosome should be unchanged
        assert mutated[0].chromosome == original

    def test_check_capacity_violation_no_vehicles(self, solver, sample_jobs):
        """Test capacity check with no vehicles."""
        problem = RoutingProblem(
            jobs=sample_jobs,
            vehicles=[],
            planning_date=datetime.now().date(),
        )

        violation = solver._check_capacity_violation([0, 1, 2], problem)
        assert violation == 0

    def test_check_capacity_violation_within_limit(self, solver, sample_jobs, sample_vehicles):
        """Test capacity check within vehicle limit."""
        problem = RoutingProblem(
            jobs=sample_jobs,
            vehicles=sample_vehicles,
            planning_date=datetime.now().date(),
        )

        # Each job has 10kg demand, vehicle has 100kg capacity
        violation = solver._check_capacity_violation([0, 1, 2], problem)
        assert violation == 0

    def test_check_capacity_violation_exceeds_limit(self, solver, sample_jobs, sample_vehicles):
        """Test capacity check exceeding vehicle limit."""
        # Modify vehicle to have small capacity
        sample_vehicles[0].capacity_kg = 20.0

        problem = RoutingProblem(
            jobs=sample_jobs,
            vehicles=sample_vehicles,
            planning_date=datetime.now().date(),
        )

        # 5 jobs with 10kg each = 50kg, vehicle has 20kg
        violation = solver._check_capacity_violation(list(range(5)), problem)
        assert violation == 30  # 50 - 20 = 30kg over


class TestGeneticSolverIntegration:
    """Integration tests for GeneticSolver."""

    @pytest.fixture
    def fast_solver(self):
        """Create solver with minimal iterations for fast tests."""
        return GeneticSolver(config=GAConfig(
            population_size=10,
            generations=5,
            elite_size=2,
            tournament_size=3,
            early_stop_generations=3,
        ))

    @pytest.mark.asyncio
    async def test_full_evolution_cycle(self, fast_solver):
        """Test complete evolution cycle."""
        locations = [
            Location(latitude=41.311 + i * 0.01, longitude=69.279 + i * 0.01, address=f"P{i}")
            for i in range(10)
        ]
        jobs = [
            Job(id=uuid4(), location=loc, priority=1, demand_kg=5.0)
            for loc in locations
        ]

        problem = RoutingProblem(
            jobs=jobs,
            vehicles=[],
            planning_date=datetime.now().date(),
        )

        result = await fast_solver.solve(problem)

        assert result.summary["algorithm"] == "genetic"
        assert result.total_distance_m >= 0
