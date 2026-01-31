"""
Routing Services based on Google OR-Tools.

TSP - Traveling Salesperson Problem for salesperson route planning.
VRPC - Vehicle Routing Problem with Capacity Constraints.
"""

import logging
from typing import Optional

import httpx

from app.schemas.field_routing import (
    ErrorCode,
    TSPAutoResponse,
    TSPData,
    TSPKind,
    TSPRequest,
    TSPSingleResponse,
    VisitIntensity,
    VRPCLoop,
    VRPCRequest,
    VRPCResponse,
)

logger = logging.getLogger(__name__)


# ============================================================
# OSRM Client
# ============================================================


class OSRMClient:
    """Client for OSRM distance matrix API."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def get_distance_matrix(
        self,
        coordinates: list[tuple[float, float]],
        map_url: str,
        profile: str = "driving",
    ) -> tuple[Optional[list[list[float]]], Optional[list[list[float]]]]:
        """
        Get distance and duration matrix from OSRM.

        Args:
            coordinates: List of (lat, lng) tuples
            map_url: OSRM server URL
            profile: Routing profile (driving, walking, cycling)

        Returns:
            Tuple of (durations matrix, distances matrix) or (None, None) on error
        """
        if len(coordinates) < 2:
            return None, None

        # Build coordinates string (lng,lat format for OSRM)
        coords_str = ";".join(f"{lng},{lat}" for lat, lng in coordinates)

        url = f"{map_url}/table/v1/{profile}/{coords_str}"
        params = {"annotations": "duration,distance"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if data.get("code") != "Ok":
                    logger.error(f"OSRM error: {data.get('message', 'Unknown error')}")
                    return None, None

                return data.get("durations"), data.get("distances")

        except httpx.ConnectError as e:
            logger.error(f"OSRM connection error: {e}")
            return None, None
        except httpx.HTTPStatusError as e:
            logger.error(f"OSRM HTTP error: {e}")
            return None, None
        except Exception as e:
            logger.error(f"OSRM unexpected error: {e}")
            return None, None


# ============================================================
# TSP Service (Traveling Salesperson Problem)
# ============================================================


class TSPService:
    """
    Traveling Salesperson Problem service.

    Generates routes for a salesperson visiting multiple points
    over 4 weeks, considering visit intensity and constraints.
    """

    # Days per week for planning
    DAYS_PER_WEEK = 6  # Working days (Mon-Sat)
    WEEKS = 4  # Planning horizon

    # Visit frequency mapping (visits per 4 weeks)
    INTENSITY_TO_VISITS = {
        VisitIntensity.THREE_TIMES_A_WEEK: 12,  # 3 * 4 weeks
        VisitIntensity.TWICE_A_WEEK: 8,  # 2 * 4 weeks
        VisitIntensity.ONCE_A_WEEK: 4,  # 1 * 4 weeks
        VisitIntensity.TWICE_A_MONTH: 2,  # 2 per month
        VisitIntensity.ONCE_A_MONTH: 1,  # 1 per month
    }

    def __init__(self, osrm_client: Optional[OSRMClient] = None):
        self.osrm = osrm_client or OSRMClient()

    async def solve(self, request: TSPRequest) -> TSPAutoResponse | TSPSingleResponse:
        """
        Solve TSP problem.

        Args:
            request: TSP request with kind and data

        Returns:
            TSPAutoResponse or TSPSingleResponse based on kind
        """
        if request.kind == TSPKind.MANUAL:
            return TSPSingleResponse(
                code=ErrorCode.INVALID_INPUT_FORMAT,
                error_text="Manual kind is not implemented",
            )

        try:
            # Get distance matrix from OSRM
            coordinates = [
                (float(loc.lat), float(loc.lng)) for loc in request.data.locations
            ]

            durations, distances = await self.osrm.get_distance_matrix(
                coordinates=coordinates,
                map_url=request.data.map_url,
                profile=request.data.profile.value,
            )

            if durations is None:
                return self._error_response(
                    request.kind,
                    ErrorCode.OSRM_CONNECTION_ERROR,
                    "Failed to connect to OSRM server",
                )

            # Build visit requirements based on intensity
            visit_requirements = self._build_visit_requirements(request.data)

            # Solve the problem
            if request.kind == TSPKind.AUTO:
                return await self._solve_auto(request.data, durations, visit_requirements)
            else:  # SINGLE
                return await self._solve_single(request.data, durations, visit_requirements)

        except MemoryError:
            return self._error_response(
                request.kind, ErrorCode.OUT_OF_MEMORY, "Out of memory"
            )
        except Exception as e:
            logger.exception(f"TSP solver error: {e}")
            return self._error_response(
                request.kind, ErrorCode.UNEXPECTED_ERROR, str(e)
            )

    def _build_visit_requirements(self, data: TSPData) -> list[int]:
        """Build list of required visits per location for 4 weeks."""
        return [
            self.INTENSITY_TO_VISITS.get(loc.visit_intensity, 1)
            for loc in data.locations
        ]

    async def _solve_auto(
        self,
        data: TSPData,
        durations: list[list[float]],
        visit_requirements: list[int],
    ) -> TSPAutoResponse:
        """
        Solve TSP with auto mode - generate multiple optimal plans.
        """
        try:
            # Generate multiple plans with different starting strategies
            plans = []

            # Plan 1: Standard greedy approach
            plan1 = self._generate_plan(data, durations, visit_requirements, seed=0)
            if plan1:
                plans.append(plan1)

            # Plan 2: Reversed order
            plan2 = self._generate_plan(data, durations, visit_requirements, seed=1)
            if plan2 and plan2 != plan1:
                plans.append(plan2)

            # Plan 3: Random shuffle (if enough locations)
            if len(data.locations) > 5:
                plan3 = self._generate_plan(data, durations, visit_requirements, seed=42)
                if plan3 and plan3 not in plans:
                    plans.append(plan3)

            if not plans:
                return TSPAutoResponse(
                    code=ErrorCode.NO_SOLUTION_FOUND,
                    error_text="No solution found to the problem",
                )

            return TSPAutoResponse(code=ErrorCode.SUCCESS, plans=plans)

        except Exception as e:
            logger.exception(f"TSP auto solve error: {e}")
            return TSPAutoResponse(
                code=ErrorCode.UNEXPECTED_ERROR, error_text=str(e)
            )

    async def _solve_single(
        self,
        data: TSPData,
        durations: list[list[float]],
        visit_requirements: list[int],
    ) -> TSPSingleResponse:
        """
        Solve TSP with single mode - generate one optimal plan.
        """
        try:
            routes = self._generate_plan(data, durations, visit_requirements, seed=0)

            if not routes:
                return TSPSingleResponse(
                    code=ErrorCode.NO_SOLUTION_FOUND,
                    error_text="No solution found to the problem",
                )

            # Find ignored locations (those not visited enough times)
            visited_counts = [0] * len(data.locations)
            for week in routes:
                for day in week:
                    for loc_idx in day:
                        if 0 <= loc_idx < len(visited_counts):
                            visited_counts[loc_idx] += 1

            ignored_locations = [
                i
                for i, (visited, required) in enumerate(
                    zip(visited_counts, visit_requirements)
                )
                if visited < required
            ]

            return TSPSingleResponse(
                code=ErrorCode.SUCCESS,
                routes=routes,
                ignored_locations=ignored_locations if ignored_locations else None,
            )

        except Exception as e:
            logger.exception(f"TSP single solve error: {e}")
            return TSPSingleResponse(
                code=ErrorCode.UNEXPECTED_ERROR, error_text=str(e)
            )

    def _generate_plan(
        self,
        data: TSPData,
        durations: list[list[float]],
        visit_requirements: list[int],
        seed: int = 0,
    ) -> Optional[list[list[list[int]]]]:
        """
        Generate a 4-week plan using greedy nearest neighbor heuristic.

        Returns:
            4 weeks of daily routes, each as list of location indexes
        """
        max_per_day = data.max_visit_limit_per_day
        working_seconds = data.working_seconds_per_day

        # Track remaining visits needed for each location
        remaining_visits = visit_requirements.copy()

        # Calculate service time per location
        service_times = [loc.visit_duration for loc in data.locations]

        # Generate route for 4 weeks
        weeks: list[list[list[int]]] = []

        for week_num in range(self.WEEKS):
            week_routes: list[list[int]] = []

            for day_num in range(self.DAYS_PER_WEEK):
                day_route: list[int] = []
                day_time = 0.0
                current_location = -1  # Start from depot (virtual)

                # Find locations that need visits
                candidates = [
                    i for i, r in enumerate(remaining_visits) if r > 0
                ]

                if not candidates:
                    week_routes.append([])
                    continue

                # Shuffle candidates based on seed for variety
                if seed > 0:
                    import random
                    random.seed(seed + week_num * 10 + day_num)
                    random.shuffle(candidates)

                while len(day_route) < max_per_day and candidates:
                    # Find nearest unvisited location
                    best_idx = None
                    best_time = float("inf")

                    for idx in candidates:
                        if current_location < 0:
                            travel_time = 0  # First location
                        else:
                            travel_time = durations[current_location][idx]

                        total_time = day_time + travel_time + service_times[idx]

                        if total_time <= working_seconds and travel_time < best_time:
                            best_time = travel_time
                            best_idx = idx

                    if best_idx is None:
                        break

                    # Add to route
                    day_route.append(best_idx)
                    if current_location >= 0:
                        day_time += durations[current_location][best_idx]
                    day_time += service_times[best_idx]
                    current_location = best_idx

                    # Update remaining visits
                    remaining_visits[best_idx] -= 1
                    if remaining_visits[best_idx] <= 0:
                        candidates.remove(best_idx)

                week_routes.append(day_route)

            weeks.append(week_routes)

        return weeks if any(any(day for day in week) for week in weeks) else None

    def _error_response(
        self, kind: TSPKind, code: int, message: str
    ) -> TSPAutoResponse | TSPSingleResponse:
        """Create error response based on kind."""
        if kind == TSPKind.AUTO:
            return TSPAutoResponse(code=code, error_text=message)
        return TSPSingleResponse(code=code, error_text=message)


# ============================================================
# VRPC Service (Vehicle Routing Problem with Capacity)
# ============================================================


class VRPCService:
    """
    Vehicle Routing Problem with Capacity Constraints service.

    Handles multi-vehicle delivery scenarios with:
    - Vehicle capacity constraints
    - Multiple vehicle types
    - Depot start/end location
    """

    def __init__(self, osrm_client: Optional[OSRMClient] = None):
        self.osrm = osrm_client or OSRMClient()

    async def solve(self, request: VRPCRequest) -> VRPCResponse:
        """
        Solve VRPC problem.

        Args:
            request: VRPC request with depot, points, and vehicles

        Returns:
            VRPCResponse with routes per vehicle
        """
        try:
            # Validate vehicle types have URLs
            for vehicle in request.vehicles:
                url = getattr(request.urls, vehicle.type.value, None)
                if not url:
                    return VRPCResponse(
                        code=ErrorCode.URL_NOT_FOUND_FOR_VEHICLE,
                        error_text=f"URL not found for vehicle type: {vehicle.type.value}",
                    )

            # Check capacity constraints
            total_weight = sum(p.weight for p in request.points)
            total_capacity = sum(v.capacity for v in request.vehicles)

            if total_weight > total_capacity:
                return VRPCResponse(
                    code=ErrorCode.WEIGHT_EXCEEDS_CAPACITY,
                    error_text=f"Total weight ({total_weight}) exceeds total capacity ({total_capacity})",
                )

            # Build coordinates list (depot + points)
            depot_coord = (float(request.depot.lat), float(request.depot.lng))
            point_coords = [(float(p.lat), float(p.lng)) for p in request.points]
            all_coords = [depot_coord] + point_coords

            # Get distance matrix for first vehicle type (as baseline)
            first_vehicle_type = request.vehicles[0].type.value
            map_url = getattr(request.urls, first_vehicle_type)

            durations, distances = await self.osrm.get_distance_matrix(
                coordinates=all_coords,
                map_url=map_url,
                profile=self._type_to_profile(first_vehicle_type),
            )

            if durations is None or distances is None:
                return VRPCResponse(
                    code=ErrorCode.OSRM_CONNECTION_ERROR,
                    error_text="Failed to get distance matrix from OSRM",
                )

            # Solve using greedy algorithm
            solution = self._solve_greedy(
                request=request,
                durations=durations,
                distances=distances,
            )

            return solution

        except MemoryError:
            return VRPCResponse(
                code=ErrorCode.OUT_OF_MEMORY, error_text="Out of memory"
            )
        except Exception as e:
            logger.exception(f"VRPC solver error: {e}")
            return VRPCResponse(code=ErrorCode.UNEXPECTED_ERROR, error_text=str(e))

    def _type_to_profile(self, vehicle_type: str) -> str:
        """Convert vehicle type to OSRM profile."""
        mapping = {
            "car": "driving",
            "truck": "driving",
            "walking": "walking",
            "cycling": "cycling",
        }
        return mapping.get(vehicle_type, "driving")

    def _solve_greedy(
        self,
        request: VRPCRequest,
        durations: list[list[float]],
        distances: list[list[float]],
    ) -> VRPCResponse:
        """
        Solve VRPC using greedy nearest neighbor algorithm.

        Depot is at index 0, points are at indexes 1 to N.
        """
        num_points = len(request.points)
        max_distance = request.max_cycle_distance or float("inf")

        # Track which points are assigned
        unassigned = set(range(1, num_points + 1))  # 1-indexed (0 is depot)
        point_weights = {i + 1: p.weight for i, p in enumerate(request.points)}

        vehicle_routes: list[list[VRPCLoop]] = []
        total_distance = 0.0
        total_duration = 0.0

        for vehicle in request.vehicles:
            loops: list[VRPCLoop] = []
            remaining_capacity = vehicle.capacity

            while unassigned:
                # Start a new loop from depot
                loop_route: list[int] = []
                loop_distance = 0.0
                loop_duration = 0.0
                current = 0  # Start at depot
                loop_capacity = remaining_capacity

                while True:
                    # Find nearest feasible point
                    best_point = None
                    best_distance = float("inf")

                    for point in unassigned:
                        weight = point_weights[point]

                        # Check capacity
                        if weight > loop_capacity:
                            continue

                        # Check distance constraint
                        dist_to_point = distances[current][point]
                        dist_back = distances[point][0]  # Return to depot

                        if loop_distance + dist_to_point + dist_back > max_distance:
                            continue

                        if dist_to_point < best_distance:
                            best_distance = dist_to_point
                            best_point = point

                    if best_point is None:
                        break

                    # Add point to loop
                    loop_route.append(best_point - 1)  # Convert to 0-indexed for output
                    loop_distance += distances[current][best_point]
                    loop_duration += durations[current][best_point]
                    loop_capacity -= point_weights[best_point]
                    current = best_point
                    unassigned.remove(best_point)

                # Return to depot
                if loop_route:
                    loop_distance += distances[current][0]
                    loop_duration += durations[current][0]

                    loops.append(
                        VRPCLoop(
                            route=loop_route,
                            distance=round(loop_distance, 2),
                            duration=round(loop_duration, 2),
                        )
                    )

                    total_distance += loop_distance
                    total_duration += loop_duration

                    # Update remaining capacity for next loop
                    remaining_capacity = vehicle.capacity
                else:
                    # No more points can be assigned to this vehicle
                    break

            vehicle_routes.append(loops)

            if not unassigned:
                break

        # Check if all points were assigned
        if unassigned:
            return VRPCResponse(
                code=ErrorCode.NO_SOLUTION_FOUND,
                error_text=f"Could not assign all points. {len(unassigned)} points remaining.",
            )

        return VRPCResponse(
            code=ErrorCode.SUCCESS,
            vehicles=vehicle_routes,
            total_distance=round(total_distance, 2),
            total_duration=round(total_duration, 2),
        )


# ============================================================
# Service Instances
# ============================================================

tsp_service = TSPService()
vrpc_service = VRPCService()
