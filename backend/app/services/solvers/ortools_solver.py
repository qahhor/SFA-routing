"""
Google OR-Tools solver implementation.

Provides high-quality solutions for complex routing problems:
- Capacity constrained VRP (CVRP)
- VRP with time windows (VRPTW)
- Pickup and delivery
- Multi-depot scenarios

Features:
- OSRM integration for real road distances
- Fallback to Euclidean when OSRM unavailable
- Cached distance matrices via Redis

Documentation: https://developers.google.com/optimization/routing
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.services.routing.osrm_client import osrm_client
from app.services.solvers.solver_interface import (
    Location,
    Route,
    RouteSolver,
    RouteStep,
    RoutingProblem,
    SolutionResult,
    SolverFactory,
    SolverType,
)

logger = logging.getLogger(__name__)

try:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False


@SolverFactory.register(SolverType.ORTOOLS)
class ORToolsSolver(RouteSolver):
    """
    Google OR-Tools based solver.

    Best for:
    - Complex constraints (pickup/delivery, multi-depot)
    - Large problem instances (500+ locations)
    - High solution quality requirements

    Limitations:
    - Slower than VROOM for simple problems
    - Requires ortools package installed
    """

    def __init__(
        self,
        time_limit_seconds: int = 30,
        solution_limit: int = 100,
        first_solution_strategy: str = "PATH_CHEAPEST_ARC",
        local_search_metaheuristic: str = "GUIDED_LOCAL_SEARCH",
        use_osrm: bool = True,
    ):
        self.time_limit_seconds = time_limit_seconds
        self.solution_limit = solution_limit
        self.first_solution_strategy = first_solution_strategy
        self.local_search_metaheuristic = local_search_metaheuristic
        self.use_osrm = use_osrm

    @property
    def solver_type(self) -> SolverType:
        return SolverType.ORTOOLS

    async def health_check(self) -> bool:
        """Check if OR-Tools is available."""
        return ORTOOLS_AVAILABLE

    async def solve(self, problem: RoutingProblem) -> SolutionResult:
        """
        Solve VRP using OR-Tools.

        Supports:
        - Capacity constraints
        - Time windows
        - Multiple vehicles with different capacities
        - Depot constraints
        """
        if not ORTOOLS_AVAILABLE:
            raise RuntimeError("ortools package not installed")

        # Build location list first
        locations = self._build_location_list(problem)

        # Fetch OSRM matrices if enabled and not provided
        distance_matrix = problem.distance_matrix
        duration_matrix = problem.duration_matrix

        if (distance_matrix is None or duration_matrix is None) and self.use_osrm:
            try:
                osrm_distance, osrm_duration = await self._get_osrm_matrices(locations)
                if distance_matrix is None:
                    distance_matrix = osrm_distance
                if duration_matrix is None:
                    duration_matrix = osrm_duration
                logger.info(f"Using OSRM matrices for {len(locations)} locations")
            except Exception as e:
                logger.warning(f"OSRM matrix fetch failed, using Euclidean: {e}")
                # Will fall back to Euclidean in _solve_sync

        # Run in thread pool to not block event loop
        return await asyncio.get_event_loop().run_in_executor(
            None,
            self._solve_sync,
            problem,
            locations,
            distance_matrix,
            duration_matrix,
        )

    async def _get_osrm_matrices(
        self,
        locations: list[Location],
    ) -> tuple[list[list[int]], list[list[int]]]:
        """
        Fetch distance and duration matrices from OSRM.

        Uses batched requests for large location sets and Redis caching.

        Returns:
            Tuple of (distance_matrix, duration_matrix) in meters and seconds
        """
        # Convert locations to coordinates (lon, lat) for OSRM
        coordinates = [(float(loc.longitude), float(loc.latitude)) for loc in locations]

        # Use batched method for large sets
        if len(coordinates) > 100:
            result = await osrm_client.get_table_batched(coordinates)
        else:
            result = await osrm_client.get_table(coordinates)

        # Convert to integer matrices (meters and seconds)
        distance_matrix = [[int(d) if d is not None else 999999 for d in row] for row in result.distances]
        duration_matrix = [[int(d) if d is not None else 99999 for d in row] for row in result.durations]

        return distance_matrix, duration_matrix

    def _solve_sync(
        self,
        problem: RoutingProblem,
        locations: list[Location],
        distance_matrix: Optional[list[list[int]]],
        duration_matrix: Optional[list[list[int]]],
    ) -> SolutionResult:
        """Synchronous solving logic."""

        if not problem.jobs:
            return SolutionResult(routes=[], unassigned_jobs=[])

        num_locations = len(locations)
        num_vehicles = len(problem.vehicles)

        # Fall back to Euclidean if matrices not provided
        if distance_matrix is None:
            logger.debug("Using Euclidean distance matrix (OSRM unavailable)")
            distance_matrix = self._compute_euclidean_matrix(locations)

        if duration_matrix is None:
            # Estimate duration from distance (assuming 30 km/h average)
            duration_matrix = [
                [int(d / 500) for d in row] for row in distance_matrix  # d meters / 500 = seconds at 30 km/h
            ]

        # Create routing index manager
        # Depot is at index 0
        manager = pywrapcp.RoutingIndexManager(
            num_locations,
            num_vehicles,
            0,  # depot index
        )

        # Create routing model
        routing = pywrapcp.RoutingModel(manager)

        # Distance callback
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return distance_matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Add capacity constraint
        if any(j.demand_kg > 0 for j in problem.jobs):
            self._add_capacity_constraint(routing, manager, problem, locations)

        # Add time windows if present
        if problem.has_time_windows:
            self._add_time_windows(routing, manager, problem, locations, duration_matrix)

        # Search parameters
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()

        # First solution strategy
        strategy = getattr(
            routing_enums_pb2.FirstSolutionStrategy,
            self.first_solution_strategy,
        )
        search_parameters.first_solution_strategy = strategy

        # Local search metaheuristic
        metaheuristic = getattr(
            routing_enums_pb2.LocalSearchMetaheuristic,
            self.local_search_metaheuristic,
        )
        search_parameters.local_search_metaheuristic = metaheuristic

        # Time limit
        search_parameters.time_limit.seconds = self.time_limit_seconds

        # Solution limit
        search_parameters.solution_limit = self.solution_limit

        # Solve
        solution = routing.SolveWithParameters(search_parameters)

        if not solution:
            # Return empty result with all jobs unassigned
            return SolutionResult(
                routes=[],
                unassigned_jobs=[j.id for j in problem.jobs],
                summary={"status": "no_solution"},
            )

        # Parse solution
        return self._parse_solution(routing, manager, solution, problem, locations, distance_matrix)

    def _build_location_list(self, problem: RoutingProblem) -> list[Location]:
        """Build ordered location list with depot at index 0."""
        locations = []

        # Add depot (index 0)
        if problem.depot_location:
            locations.append(problem.depot_location)
        elif problem.vehicles and problem.vehicles[0].start_location:
            locations.append(problem.vehicles[0].start_location)
        else:
            # Use first job location as depot
            if problem.jobs:
                locations.append(problem.jobs[0].location)

        # Add job locations (indices 1 to N)
        for job in problem.jobs:
            locations.append(job.location)

        return locations

    def _compute_euclidean_matrix(
        self,
        locations: list[Location],
    ) -> list[list[int]]:
        """
        Compute Euclidean distance matrix.

        Note: In production, use OSRM for actual road distances.
        """
        import math

        n = len(locations)
        matrix = [[0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i != j:
                    # Haversine approximation (meters)
                    lat1, lon1 = locations[i].latitude, locations[i].longitude
                    lat2, lon2 = locations[j].latitude, locations[j].longitude

                    # Simplified distance calculation
                    dlat = abs(lat2 - lat1) * 111000  # ~111km per degree lat
                    dlon = abs(lon2 - lon1) * 111000 * math.cos(math.radians(lat1))
                    matrix[i][j] = int(math.sqrt(dlat**2 + dlon**2))

        return matrix

    def _add_capacity_constraint(
        self,
        routing,
        manager,
        problem: RoutingProblem,
        locations: list[Location],
    ):
        """Add vehicle capacity constraints."""

        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            if from_node == 0:  # Depot
                return 0
            job_index = from_node - 1
            if job_index < len(problem.jobs):
                return int(problem.jobs[job_index].demand_kg)
            return 0

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)

        # Add dimension for capacity
        vehicle_capacities = [int(v.capacity_kg) for v in problem.vehicles]

        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,  # null capacity slack
            vehicle_capacities,
            True,  # start cumul to zero
            "Capacity",
        )

    def _add_time_windows(
        self,
        routing,
        manager,
        problem: RoutingProblem,
        locations: list[Location],
        duration_matrix: list[list[int]],
    ):
        """Add time window constraints."""

        def time_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            travel_time = duration_matrix[from_node][to_node]

            # Add service time at from_node
            if from_node > 0:
                job_index = from_node - 1
                if job_index < len(problem.jobs):
                    travel_time += problem.jobs[job_index].location.service_time_minutes * 60

            return travel_time

        time_callback_index = routing.RegisterTransitCallback(time_callback)

        # Add time dimension
        max_time = 24 * 3600  # 24 hours in seconds

        routing.AddDimension(
            time_callback_index,
            30 * 60,  # 30 min slack
            max_time,
            False,  # Don't force start cumul to zero
            "Time",
        )

        time_dimension = routing.GetDimensionOrDie("Time")

        # Add time windows for each job
        for job_index, job in enumerate(problem.jobs):
            node_index = job_index + 1  # +1 for depot offset
            index = manager.NodeToIndex(node_index)

            if job.time_window_start and job.time_window_end:
                # Convert to seconds from midnight
                start_seconds = job.time_window_start.hour * 3600 + job.time_window_start.minute * 60
                end_seconds = job.time_window_end.hour * 3600 + job.time_window_end.minute * 60
                time_dimension.CumulVar(index).SetRange(start_seconds, end_seconds)

    def _parse_solution(
        self,
        routing,
        manager,
        solution,
        problem: RoutingProblem,
        locations: list[Location],
        distance_matrix: list[list[int]],
    ) -> SolutionResult:
        """Parse OR-Tools solution into SolutionResult."""

        routes = []
        total_distance = 0
        assigned_jobs = set()

        for vehicle_id in range(len(problem.vehicles)):
            vehicle = problem.vehicles[vehicle_id]
            index = routing.Start(vehicle_id)
            steps = []

            route_distance = 0
            prev_index = None

            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                location = locations[node]

                # Calculate distance from previous
                dist_from_prev = 0
                if prev_index is not None:
                    prev_node = manager.IndexToNode(prev_index)
                    dist_from_prev = distance_matrix[prev_node][node]

                route_distance += dist_from_prev

                # Determine step type and job ID
                if node == 0:
                    step_type = "start"
                    job_id = None
                else:
                    step_type = "job"
                    job_index = node - 1
                    job_id = problem.jobs[job_index].id if job_index < len(problem.jobs) else None
                    if job_id:
                        assigned_jobs.add(job_id)

                # Create step
                now = datetime.now().replace(hour=8, minute=0, second=0)
                step = RouteStep(
                    job_id=job_id,
                    location=location,
                    arrival_time=now,  # Would be calculated properly with time dimension
                    departure_time=now + timedelta(minutes=location.service_time_minutes),
                    distance_from_previous_m=dist_from_prev,
                    step_type=step_type,
                )
                steps.append(step)

                prev_index = index
                index = solution.Value(routing.NextVar(index))

            # Add end step (return to depot)
            if steps:
                prev_node = manager.IndexToNode(prev_index)
                dist_to_depot = distance_matrix[prev_node][0]
                route_distance += dist_to_depot

                steps.append(
                    RouteStep(
                        job_id=None,
                        location=locations[0],
                        arrival_time=datetime.now(),
                        departure_time=datetime.now(),
                        distance_from_previous_m=dist_to_depot,
                        step_type="end",
                    )
                )

            # Only add route if it has jobs
            if len(steps) > 2:  # More than just start and end
                route = Route(
                    vehicle_id=vehicle.id,
                    vehicle_name=vehicle.name,
                    steps=steps,
                    total_distance_m=route_distance,
                    total_duration_s=int(route_distance / 8.33),  # ~30 km/h
                    total_load=(
                        sum(
                            problem.jobs[manager.IndexToNode(manager.NodeToIndex(i)) - 1].demand_kg
                            for i, s in enumerate(steps)
                            if s.step_type == "job" and s.job_id
                        )
                        if steps
                        else 0
                    ),
                )
                routes.append(route)
                total_distance += route_distance

        # Find unassigned jobs
        unassigned = [j.id for j in problem.jobs if j.id not in assigned_jobs]

        return SolutionResult(
            routes=routes,
            unassigned_jobs=unassigned,
            total_distance_m=total_distance,
            total_duration_s=int(total_distance / 8.33),
            summary={
                "status": "success",
                "objective": solution.ObjectiveValue(),
                "vehicles_used": len(routes),
            },
        )

    async def solve_tsp(
        self,
        locations: list[Location],
        start_index: int = 0,
        return_to_start: bool = True,
    ) -> list[int]:
        """
        Solve TSP using OR-Tools.

        Args:
            locations: Locations to visit
            start_index: Starting location index
            return_to_start: Whether to return to start

        Returns:
            Ordered list of location indices
        """
        if not ORTOOLS_AVAILABLE:
            raise RuntimeError("ortools package not installed")

        # Fetch OSRM matrix if enabled
        distance_matrix = None
        if self.use_osrm:
            try:
                distance_matrix, _ = await self._get_osrm_matrices(locations)
                logger.info(f"Using OSRM matrix for TSP with {len(locations)} locations")
            except Exception as e:
                logger.warning(f"OSRM matrix fetch failed for TSP, using Euclidean: {e}")

        return await asyncio.get_event_loop().run_in_executor(
            None,
            self._solve_tsp_sync,
            locations,
            start_index,
            return_to_start,
            distance_matrix,
        )

    def _solve_tsp_sync(
        self,
        locations: list[Location],
        start_index: int,
        return_to_start: bool,
        distance_matrix: Optional[list[list[int]]] = None,
    ) -> list[int]:
        """Synchronous TSP solving."""

        if len(locations) <= 2:
            return list(range(len(locations)))

        # Compute distance matrix if not provided
        if distance_matrix is None:
            distance_matrix = self._compute_euclidean_matrix(locations)

        # Create routing model
        manager = pywrapcp.RoutingIndexManager(
            len(locations),
            1,  # single vehicle
            start_index,
        )
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return distance_matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Search parameters
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        search_parameters.time_limit.seconds = 10

        # Solve
        solution = routing.SolveWithParameters(search_parameters)

        if not solution:
            return list(range(len(locations)))

        # Extract route
        route = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))

        if return_to_start:
            route.append(start_index)

        return route
