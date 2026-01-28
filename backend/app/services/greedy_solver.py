"""
Greedy fallback solver.

Simple nearest-neighbor heuristic for when other solvers fail.
Guarantees a solution but with lower quality.
"""
import math
from datetime import datetime, timedelta
from typing import Optional

from app.services.solver_interface import (
    RouteSolver,
    SolverFactory,
    SolverType,
    RoutingProblem,
    SolutionResult,
    Route,
    RouteStep,
    Location,
    VehicleConfig,
    Job,
)


@SolverFactory.register(SolverType.GREEDY)
class GreedySolver(RouteSolver):
    """
    Greedy nearest-neighbor solver.

    Simple but guaranteed to produce a solution.
    Used as fallback when other solvers fail.

    Algorithm:
    1. For each vehicle, repeatedly pick the nearest unvisited job
    2. Stop when capacity is reached or no jobs remain
    3. Return to depot
    """

    @property
    def solver_type(self) -> SolverType:
        return SolverType.GREEDY

    async def health_check(self) -> bool:
        """Greedy solver is always available."""
        return True

    async def solve(self, problem: RoutingProblem) -> SolutionResult:
        """
        Solve using nearest-neighbor heuristic.

        Assigns jobs to vehicles greedily by nearest distance.
        """
        if not problem.jobs:
            return SolutionResult(routes=[], unassigned_jobs=[])

        routes = []
        assigned_jobs: set[int] = set()  # Track by index
        total_distance = 0

        # Get depot location
        depot = self._get_depot(problem)

        for vehicle in problem.vehicles:
            route, route_distance, route_assigned = self._build_route_for_vehicle(
                vehicle=vehicle,
                jobs=problem.jobs,
                assigned_indices=assigned_jobs,
                depot=depot,
            )

            if route.steps and len(route.steps) > 2:  # Has actual jobs
                routes.append(route)
                total_distance += route_distance
                assigned_jobs.update(route_assigned)

        # Find unassigned
        unassigned = [
            problem.jobs[i].id
            for i in range(len(problem.jobs))
            if i not in assigned_jobs
        ]

        return SolutionResult(
            routes=routes,
            unassigned_jobs=unassigned,
            total_distance_m=total_distance,
            total_duration_s=int(total_distance / 8.33),  # ~30 km/h
            summary={
                "algorithm": "nearest_neighbor",
                "vehicles_used": len(routes),
            },
        )

    def _get_depot(self, problem: RoutingProblem) -> Location:
        """Get depot location from problem."""
        if problem.depot_location:
            return problem.depot_location
        if problem.vehicles and problem.vehicles[0].start_location:
            return problem.vehicles[0].start_location
        # Fallback: use first job location
        return problem.jobs[0].location

    def _build_route_for_vehicle(
        self,
        vehicle: VehicleConfig,
        jobs: list[Job],
        assigned_indices: set[int],
        depot: Location,
    ) -> tuple[Route, int, set[int]]:
        """
        Build route for a single vehicle using nearest neighbor.

        Returns:
            (route, total_distance, assigned_job_indices)
        """
        steps = []
        current_location = vehicle.start_location or depot
        current_load = 0.0
        total_distance = 0
        route_assigned: set[int] = set()

        now = datetime.now().replace(
            hour=vehicle.work_start.hour,
            minute=vehicle.work_start.minute,
        )

        # Add start step
        steps.append(RouteStep(
            job_id=None,
            location=current_location,
            arrival_time=now,
            departure_time=now,
            step_type="start",
        ))

        # Greedily assign nearest unvisited job
        while True:
            nearest_idx = self._find_nearest_feasible_job(
                current_location=current_location,
                jobs=jobs,
                assigned_indices=assigned_indices | route_assigned,
                current_load=current_load,
                vehicle_capacity=vehicle.capacity_kg,
            )

            if nearest_idx is None:
                break

            job = jobs[nearest_idx]
            distance = self._calculate_distance(current_location, job.location)
            travel_time = int(distance / 8.33)  # seconds at ~30 km/h

            # Update state
            total_distance += distance
            current_load += job.demand_kg
            route_assigned.add(nearest_idx)

            arrival = now + timedelta(seconds=travel_time)
            departure = arrival + timedelta(minutes=job.location.service_time_minutes)

            steps.append(RouteStep(
                job_id=job.id,
                location=job.location,
                arrival_time=arrival,
                departure_time=departure,
                distance_from_previous_m=int(distance),
                duration_from_previous_s=travel_time,
                load_after=current_load,
                step_type="job",
            ))

            current_location = job.location
            now = departure

        # Return to depot
        if len(steps) > 1:
            return_distance = self._calculate_distance(current_location, depot)
            total_distance += int(return_distance)

            steps.append(RouteStep(
                job_id=None,
                location=depot,
                arrival_time=now + timedelta(seconds=int(return_distance / 8.33)),
                departure_time=now + timedelta(seconds=int(return_distance / 8.33)),
                distance_from_previous_m=int(return_distance),
                step_type="end",
            ))

        route = Route(
            vehicle_id=vehicle.id,
            vehicle_name=vehicle.name,
            steps=steps,
            total_distance_m=int(total_distance),
            total_duration_s=int(total_distance / 8.33),
            total_load=current_load,
        )

        return route, int(total_distance), route_assigned

    def _find_nearest_feasible_job(
        self,
        current_location: Location,
        jobs: list[Job],
        assigned_indices: set[int],
        current_load: float,
        vehicle_capacity: float,
    ) -> Optional[int]:
        """Find nearest unassigned job that fits in vehicle."""
        nearest_idx = None
        nearest_distance = float('inf')

        for idx, job in enumerate(jobs):
            if idx in assigned_indices:
                continue

            # Check capacity
            if current_load + job.demand_kg > vehicle_capacity:
                continue

            distance = self._calculate_distance(current_location, job.location)
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_idx = idx

        return nearest_idx

    def _calculate_distance(self, loc1: Location, loc2: Location) -> float:
        """Calculate Haversine distance between two locations in meters."""
        lat1, lon1 = math.radians(loc1.latitude), math.radians(loc1.longitude)
        lat2, lon2 = math.radians(loc2.latitude), math.radians(loc2.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371000  # Earth radius in meters

        return c * r

    async def solve_tsp(
        self,
        locations: list[Location],
        start_index: int = 0,
        return_to_start: bool = True,
    ) -> list[int]:
        """
        Solve TSP using nearest neighbor heuristic.

        Simple greedy approach - always visit nearest unvisited city.
        """
        if len(locations) <= 2:
            return list(range(len(locations)))

        visited = [False] * len(locations)
        route = [start_index]
        visited[start_index] = True
        current = start_index

        for _ in range(len(locations) - 1):
            nearest = None
            nearest_dist = float('inf')

            for i, loc in enumerate(locations):
                if visited[i]:
                    continue
                dist = self._calculate_distance(locations[current], loc)
                if dist < nearest_dist:
                    nearest = i
                    nearest_dist = dist

            if nearest is not None:
                route.append(nearest)
                visited[nearest] = True
                current = nearest

        if return_to_start:
            route.append(start_index)

        return route
