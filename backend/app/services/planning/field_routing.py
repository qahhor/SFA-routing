"""
Routing Services based on Google OR-Tools.

TSP - Traveling Salesperson Problem (Salesperson Plan)
VRPC - Vehicle Routing Problem with Capacity Constraints
"""

import logging
import math
from typing import Optional

import httpx

from app.schemas.field_routing import (
    DayRoute,
    ErrorCode,
    Intensity,
    TSPAutoResponse,
    TSPKind,
    TSPLocation,
    TSPRequest,
    TSPSingleResponse,
    VRPCLoop,
    VRPCRequest,
    VRPCResponse,
    WeekPlan,
)

logger = logging.getLogger(__name__)


# ============================================================
# Constants
# ============================================================

# Intensity coefficients (visits per week)
INTENSITY_COEFFICIENT = {
    Intensity.THREE_TIMES_A_WEEK: 3.0,
    Intensity.TWO_TIMES_A_WEEK: 2.0,
    Intensity.ONCE_A_WEEK: 1.0,
    Intensity.ONCE_IN_TWO_WEEKS: 0.5,
    Intensity.ONCE_A_MONTH: 0.25,
}

# Days pattern for each intensity
INTENSITY_DAYS = {
    Intensity.THREE_TIMES_A_WEEK: [1, 3, 5],  # Mon, Wed, Fri
    Intensity.TWO_TIMES_A_WEEK: [1, 4],  # Mon, Thu
    Intensity.ONCE_A_WEEK: [1],  # Mon
    Intensity.ONCE_IN_TWO_WEEKS: [1],  # Mon (every 2 weeks)
    Intensity.ONCE_A_MONTH: [1],  # Mon (every 4 weeks)
}

# Planning constants
WEEKS = 4
DAYS_PER_WEEK = 6
WORKING_MINUTES_PER_DAY = 480  # 8 hours


# ============================================================
# Haversine Distance Calculation
# ============================================================


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate distance between two points using Haversine formula.

    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    sin_dlat = math.sin(delta_lat / 2) ** 2
    sin_dlon = math.sin(delta_lon / 2) ** 2
    a = sin_dlat + math.cos(lat1_rad) * math.cos(lat2_rad) * sin_dlon
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# ============================================================
# OSRM Client
# ============================================================


class OSRMClient:
    """Client for OSRM distance matrix API."""

    def __init__(self, base_url: str = "", timeout: float = 30.0):
        self.base_url = base_url
        self.timeout = timeout

    async def get_distance_matrix(
        self,
        coordinates: list[tuple[float, float]],
        profile: str = "driving",
    ) -> tuple[Optional[list[list[float]]], Optional[list[list[float]]]]:
        """
        Get distance and duration matrix from OSRM.

        Args:
            coordinates: List of (lat, lng) tuples
            profile: Routing profile

        Returns:
            Tuple of (durations in seconds, distances in meters)
        """
        if not self.base_url or len(coordinates) < 2:
            return None, None

        # Build coordinates string (lng,lat format for OSRM)
        coords_str = ";".join(f"{lng},{lat}" for lat, lng in coordinates)
        url = f"{self.base_url}/table/v1/{profile}/{coords_str}"
        params = {"annotations": "duration,distance"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if data.get("code") != "Ok":
                    return None, None

                return data.get("durations"), data.get("distances")

        except Exception as e:
            logger.error(f"OSRM error: {e}")
            return None, None


# ============================================================
# TSP Service - Single Plan Solver
# ============================================================


class SinglePlanSolver:
    """
    Single plan solver for TSP.

    Generates a 4-week route plan for a salesperson.
    """

    def __init__(self, osrm_client: Optional[OSRMClient] = None):
        self.osrm = osrm_client

    async def solve(self, request: TSPRequest) -> TSPSingleResponse:
        """Solve TSP and return a single 4-week plan."""
        try:
            locations = request.locations
            start_loc = request.startLocation

            if not locations:
                return TSPSingleResponse(
                    code=ErrorCode.INVALID_INPUT_FORMAT,
                    error_text="No locations provided",
                )

            # Build distance matrix using Haversine (OSRM fallback)
            distance_matrix = self._build_distance_matrix(locations, start_loc)

            # Calculate required visits per location for 4 weeks
            visit_requirements = self._calculate_visit_requirements(locations)

            # Generate 4-week plan
            weeks = self._generate_plan(
                locations, distance_matrix, visit_requirements, start_loc
            )

            return TSPSingleResponse(code=ErrorCode.SUCCESS, weeks=weeks)

        except MemoryError:
            return TSPSingleResponse(
                code=ErrorCode.OUT_OF_MEMORY, error_text="Out of memory"
            )
        except Exception as e:
            logger.exception(f"SinglePlanSolver error: {e}")
            return TSPSingleResponse(
                code=ErrorCode.UNEXPECTED_ERROR, error_text=str(e)
            )

    def _build_distance_matrix(
        self,
        locations: list[TSPLocation],
        start_loc: Optional[object],
    ) -> list[list[float]]:
        """Build distance matrix using Haversine formula."""
        # Include start location if provided
        all_coords = []
        if start_loc:
            all_coords.append((start_loc.latitude, start_loc.longitude))
        for loc in locations:
            all_coords.append((loc.latitude, loc.longitude))

        n = len(all_coords)
        matrix = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i][j] = haversine_distance(
                        all_coords[i][0],
                        all_coords[i][1],
                        all_coords[j][0],
                        all_coords[j][1],
                    )

        return matrix

    def _calculate_visit_requirements(
        self, locations: list[TSPLocation]
    ) -> dict[str, int]:
        """Calculate required visits per location for 4 weeks."""
        requirements = {}
        for loc in locations:
            coefficient = INTENSITY_COEFFICIENT.get(loc.intensity, 1.0)
            total_visits = int(coefficient * WEEKS)
            requirements[loc.id] = max(1, total_visits)
        return requirements

    def _generate_plan(
        self,
        locations: list[TSPLocation],
        distance_matrix: list[list[float]],
        visit_requirements: dict[str, int],
        start_loc: Optional[object],
    ) -> list[WeekPlan]:
        """Generate 4-week plan using greedy algorithm."""
        # Create location lookup
        loc_by_id = {loc.id: loc for loc in locations}
        loc_ids = [loc.id for loc in locations]

        # Track remaining visits needed
        remaining_visits = visit_requirements.copy()

        # Track which locations were visited on which days
        weeks: list[WeekPlan] = []

        # Index offset for distance matrix (if start_loc is included)
        offset = 1 if start_loc else 0

        for week_num in range(1, WEEKS + 1):
            days: list[DayRoute] = []

            for day_num in range(1, DAYS_PER_WEEK + 1):
                day_route: list[str] = []
                day_duration = 0
                day_distance = 0.0

                # Find locations that need visits and can be visited today
                candidates = []
                for loc_id, remaining in remaining_visits.items():
                    if remaining <= 0:
                        continue

                    loc = loc_by_id[loc_id]

                    # Check if this day is in location's working days
                    if day_num not in loc.workingDays:
                        continue

                    # Check intensity pattern
                    intensity_days = INTENSITY_DAYS.get(loc.intensity, [1])
                    if loc.intensity in [
                        Intensity.THREE_TIMES_A_WEEK,
                        Intensity.TWO_TIMES_A_WEEK,
                        Intensity.ONCE_A_WEEK,
                    ]:
                        if day_num not in intensity_days:
                            continue
                    elif loc.intensity == Intensity.ONCE_IN_TWO_WEEKS:
                        if week_num % 2 != 1 or day_num != 1:
                            continue
                    elif loc.intensity == Intensity.ONCE_A_MONTH:
                        if week_num != 1 or day_num != 1:
                            continue

                    candidates.append(loc_id)

                # Greedy nearest neighbor
                current_idx = 0  # Start from depot/first location
                available_time = WORKING_MINUTES_PER_DAY

                while candidates and available_time > 0:
                    # Find nearest candidate
                    best_loc_id = None
                    best_distance = float("inf")
                    best_idx = -1

                    for loc_id in candidates:
                        loc_idx = loc_ids.index(loc_id) + offset
                        dist = distance_matrix[current_idx][loc_idx]

                        if dist < best_distance:
                            best_distance = dist
                            best_loc_id = loc_id
                            best_idx = loc_idx

                    if best_loc_id is None:
                        break

                    loc = loc_by_id[best_loc_id]

                    # Check time constraint
                    travel_time = int(best_distance / 0.5)  # ~30 km/h average
                    total_time = travel_time + loc.visitDuration

                    if total_time > available_time:
                        # Skip this location - not enough time
                        candidates.remove(best_loc_id)
                        continue

                    # Add to route
                    day_route.append(best_loc_id)
                    day_duration += total_time
                    day_distance += best_distance
                    available_time -= total_time

                    remaining_visits[best_loc_id] -= 1
                    candidates.remove(best_loc_id)
                    current_idx = best_idx

                if day_route:
                    days.append(
                        DayRoute(
                            dayNumber=day_num,
                            route=day_route,
                            totalDuration=day_duration,
                            totalDistance=round(day_distance, 2),
                        )
                    )

            weeks.append(WeekPlan(weekNumber=week_num, days=days))

        return weeks


# ============================================================
# TSP Service - Auto Plan Solver (Clustering)
# ============================================================


class AutoPlanSolver:
    """
    Auto plan solver with clustering.

    Clusters locations geographically and generates
    separate plans for each cluster.
    """

    def __init__(self, osrm_client: Optional[OSRMClient] = None):
        self.osrm = osrm_client
        self.single_solver = SinglePlanSolver(osrm_client)

    async def solve(self, request: TSPRequest) -> TSPAutoResponse:
        """Solve TSP with automatic clustering."""
        try:
            locations = request.locations

            if not locations:
                return TSPAutoResponse(
                    code=ErrorCode.INVALID_INPUT_FORMAT,
                    error_text="No locations provided",
                )

            # Cluster locations
            clusters = self._cluster_locations(locations)

            if not clusters:
                return TSPAutoResponse(
                    code=ErrorCode.NO_SOLUTION_FOUND,
                    error_text="Could not create clusters",
                )

            # Solve each cluster
            plans: list[list[WeekPlan]] = []

            for cluster_locations in clusters:
                cluster_request = TSPRequest(
                    kind=TSPKind.SINGLE,
                    locations=cluster_locations,
                    startLocation=request.startLocation,
                )

                result = await self.single_solver.solve(cluster_request)

                if result.code == ErrorCode.SUCCESS and result.weeks:
                    plans.append(result.weeks)

            if not plans:
                return TSPAutoResponse(
                    code=ErrorCode.NO_SOLUTION_FOUND,
                    error_text="No solution found for any cluster",
                )

            return TSPAutoResponse(code=ErrorCode.SUCCESS, plans=plans)

        except MemoryError:
            return TSPAutoResponse(
                code=ErrorCode.OUT_OF_MEMORY, error_text="Out of memory"
            )
        except Exception as e:
            logger.exception(f"AutoPlanSolver error: {e}")
            return TSPAutoResponse(
                code=ErrorCode.UNEXPECTED_ERROR, error_text=str(e)
            )

    def _cluster_locations(
        self,
        locations: list[TSPLocation],
        max_cluster_size: int = 50,
    ) -> list[list[TSPLocation]]:
        """
        Cluster locations using geographic proximity.

        Algorithm:
        1. Find the leftmost (min longitude) location
        2. Iteratively add nearest locations until cluster is full
        3. Repeat for remaining locations
        """
        if len(locations) <= max_cluster_size:
            return [locations]

        remaining = list(locations)
        clusters: list[list[TSPLocation]] = []

        while remaining:
            # Find leftmost location (min longitude)
            leftmost = min(remaining, key=lambda loc: loc.longitude)
            cluster = [leftmost]
            remaining.remove(leftmost)

            # Add nearest locations until cluster is full
            while remaining and len(cluster) < max_cluster_size:
                last = cluster[-1]

                # Find nearest to last added
                def dist_to_last(loc):
                    return haversine_distance(
                        last.latitude, last.longitude,
                        loc.latitude, loc.longitude
                    )
                nearest = min(remaining, key=dist_to_last)

                cluster.append(nearest)
                remaining.remove(nearest)

            clusters.append(cluster)

        return clusters


# ============================================================
# TSP Service (Main Entry Point)
# ============================================================


class TSPService:
    """Main TSP service that routes to appropriate solver."""

    def __init__(self, osrm_client: Optional[OSRMClient] = None):
        self.single_solver = SinglePlanSolver(osrm_client)
        self.auto_solver = AutoPlanSolver(osrm_client)

    async def solve(
        self, request: TSPRequest
    ) -> TSPSingleResponse | TSPAutoResponse:
        """Solve TSP based on request kind."""
        if request.kind == TSPKind.SINGLE:
            return await self.single_solver.solve(request)
        elif request.kind == TSPKind.AUTO:
            return await self.auto_solver.solve(request)
        else:
            return TSPSingleResponse(
                code=ErrorCode.INVALID_INPUT_FORMAT,
                error_text=f"Unknown kind: {request.kind}",
            )


# ============================================================
# VRPC Service (Vehicle Routing Problem with Capacity)
# ============================================================


class VRPCService:
    """Vehicle Routing Problem with Capacity Constraints."""

    def __init__(self, osrm_client: Optional[OSRMClient] = None):
        self.osrm = osrm_client or OSRMClient()

    async def solve(self, request: VRPCRequest) -> VRPCResponse:
        """Solve VRPC problem."""
        try:
            # Validate vehicle URLs
            for vehicle in request.vehicles:
                url = getattr(request.urls, vehicle.type.value, None)
                if not url:
                    vtype = vehicle.type.value
                    return VRPCResponse(
                        code=ErrorCode.URL_NOT_FOUND_FOR_VEHICLE,
                        error_text=f"URL not found for vehicle type: {vtype}",
                    )

            # Check capacity
            total_weight = sum(p.weight for p in request.points)
            total_capacity = sum(v.capacity for v in request.vehicles)

            if total_weight > total_capacity:
                msg = f"Weight ({total_weight}) > capacity ({total_capacity})"
                return VRPCResponse(
                    code=ErrorCode.WEIGHT_EXCEEDS_CAPACITY,
                    error_text=msg,
                )

            # Build distance matrix using Haversine
            depot = (float(request.depot.lat), float(request.depot.lng))
            points = [(float(p.lat), float(p.lng)) for p in request.points]
            all_coords = [depot] + points

            n = len(all_coords)
            distances = [[0.0] * n for _ in range(n)]
            durations = [[0.0] * n for _ in range(n)]

            for i in range(n):
                for j in range(n):
                    if i != j:
                        dist = haversine_distance(
                            all_coords[i][0],
                            all_coords[i][1],
                            all_coords[j][0],
                            all_coords[j][1],
                        )
                        distances[i][j] = dist * 1000  # km to m
                        durations[i][j] = dist / 30 * 3600  # 30 km/h

            # Solve using greedy
            return self._solve_greedy(request, durations, distances)

        except MemoryError:
            return VRPCResponse(
                code=ErrorCode.OUT_OF_MEMORY, error_text="Out of memory"
            )
        except Exception as e:
            logger.exception(f"VRPC error: {e}")
            return VRPCResponse(
                code=ErrorCode.UNEXPECTED_ERROR, error_text=str(e)
            )

    def _solve_greedy(
        self,
        request: VRPCRequest,
        durations: list[list[float]],
        distances: list[list[float]],
    ) -> VRPCResponse:
        """Solve VRPC using greedy algorithm."""
        num_points = len(request.points)
        max_distance = request.max_cycle_distance or float("inf")

        unassigned = set(range(1, num_points + 1))
        point_weights = {i + 1: p.weight for i, p in enumerate(request.points)}

        vehicle_routes: list[list[VRPCLoop]] = []
        total_distance = 0.0
        total_duration = 0.0

        for vehicle in request.vehicles:
            loops: list[VRPCLoop] = []
            remaining_capacity = vehicle.capacity

            while unassigned:
                loop_route: list[int] = []
                loop_distance = 0.0
                loop_duration = 0.0
                current = 0
                loop_capacity = remaining_capacity

                while True:
                    best_point = None
                    best_dist = float("inf")

                    for point in unassigned:
                        weight = point_weights[point]
                        if weight > loop_capacity:
                            continue

                        dist_to = distances[current][point]
                        dist_back = distances[point][0]

                        if loop_distance + dist_to + dist_back > max_distance:
                            continue

                        if dist_to < best_dist:
                            best_dist = dist_to
                            best_point = point

                    if best_point is None:
                        break

                    loop_route.append(best_point - 1)
                    loop_distance += distances[current][best_point]
                    loop_duration += durations[current][best_point]
                    loop_capacity -= point_weights[best_point]
                    current = best_point
                    unassigned.remove(best_point)

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
                    remaining_capacity = vehicle.capacity
                else:
                    break

            vehicle_routes.append(loops)

            if not unassigned:
                break

        if unassigned:
            return VRPCResponse(
                code=ErrorCode.NO_SOLUTION_FOUND,
                error_text=f"Could not assign {len(unassigned)} points",
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
