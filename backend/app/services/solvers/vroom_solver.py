"""
VROOM (Vehicle Routing Open-source Optimization Machine) solver.

Features:
- Exponential backoff retry logic
- Structured error handling
- Configurable timeouts
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.models.client import Client
from app.models.delivery_order import DeliveryOrder
from app.models.vehicle import Vehicle
from app.services.solvers.solver_interface import (
    Job,
    Location,
    Route,
    RouteSolver,
    RouteStep,
    RoutingProblem,
    SolutionResult,
    SolverFactory,
    SolverType,
    TransportMode,
    VehicleConfig,
)

logger = logging.getLogger(__name__)


class VROOMError(Exception):
    """VROOM service error."""

    def __init__(self, message: str, code: Optional[int] = None, details: Optional[dict] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


@dataclass
class VROOMJob:
    """Job (delivery stop) for VROOM."""

    id: int
    location: list[float]  # [longitude, latitude]
    service: int = 300  # service time in seconds
    amount: list[int] = field(default_factory=lambda: [0])
    time_windows: list[list[int]] = field(default_factory=list)
    priority: int = 0
    description: str = ""


@dataclass
class VROOMVehicle:
    """Vehicle for VROOM."""

    id: int
    start: list[float]  # [longitude, latitude]
    end: Optional[list[float]] = None
    capacity: list[int] = field(default_factory=lambda: [1000])
    time_window: Optional[list[int]] = None
    description: str = ""


@dataclass
class VROOMStep:
    """Step in a VROOM solution route."""

    type: str  # "start", "job", "end"
    location: list[float]
    arrival: int  # timestamp
    duration: int  # seconds
    distance: int  # meters
    service: int = 0
    job_id: Optional[int] = None
    load: list[int] = field(default_factory=list)


@dataclass
class VROOMRoute:
    """Route in a VROOM solution."""

    vehicle_id: int
    steps: list[VROOMStep]
    cost: int
    duration: int  # seconds
    distance: int  # meters
    service: int  # total service time
    waiting_time: int
    delivery: list[int]
    geometry: Optional[str] = None  # encoded polyline


@dataclass
class VROOMSolution:
    """VROOM optimization solution."""

    code: int
    summary: dict
    routes: list[VROOMRoute]
    unassigned: list[dict]


@SolverFactory.register(SolverType.VROOM)
class VROOMSolver(RouteSolver):
    """
    Solver for Vehicle Routing Problem using VROOM.

    VROOM solves VRP with:
    - Multiple vehicles with capacities
    - Time windows for pickups/deliveries
    - Service times at stops
    - Priority-based optimization

    Features:
    - Exponential backoff retry (3 attempts)
    - Configurable timeouts
    - Structured error handling
    """

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2.0  # seconds

    def __init__(self, base_url: Optional[str] = None, timeout_seconds: float = 300.0):
        self.base_url = (base_url or settings.VROOM_URL).rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds, connect=30.0)

    async def _request_with_retry(
        self,
        request_data: dict,
        operation: str = "solve",
    ) -> dict:
        """
        Make VROOM request with exponential backoff retry.

        Args:
            request_data: VROOM request payload
            operation: Operation name for logging

        Returns:
            VROOM response data

        Raises:
            VROOMError: If all retries fail
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.base_url,
                        json=request_data,
                    )
                    response.raise_for_status()
                    data = response.json()

                # Check VROOM-specific error codes
                if data.get("code") != 0:
                    error_msg = data.get("error", "Unknown VROOM error")
                    raise VROOMError(
                        f"VROOM returned error: {error_msg}",
                        code=data.get("code"),
                        details=data,
                    )

                return data

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"VROOM {operation} HTTP error (attempt {attempt + 1}/{self.MAX_RETRIES}): "
                    f"{e.response.status_code}"
                )
            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"VROOM {operation} network error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
            except VROOMError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(f"VROOM {operation} error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")

            if attempt < self.MAX_RETRIES - 1:
                delay = self.RETRY_BASE_DELAY * (2**attempt)
                logger.info(f"Retrying VROOM {operation} in {delay}s...")
                await asyncio.sleep(delay)

        raise VROOMError(f"VROOM {operation} failed after {self.MAX_RETRIES} attempts: {last_error}")

    @property
    def solver_type(self) -> SolverType:
        return SolverType.VROOM

    def _time_to_timestamp(self, t: time, base_date: date) -> int:
        """Convert time to Unix timestamp."""
        dt = datetime.combine(base_date, t)
        return int(dt.timestamp())

    def _datetime_to_timestamp(self, dt: datetime) -> int:
        """Convert datetime to Unix timestamp."""
        return int(dt.timestamp())

    def prepare_vehicles(
        self,
        vehicles: list[Vehicle],
        route_date: date,
    ) -> list[dict]:
        """
        Prepare vehicle data for VROOM request.

        Args:
            vehicles: List of Vehicle models
            route_date: Date for the route

        Returns:
            List of VROOM vehicle dictionaries
        """
        vroom_vehicles = []

        for idx, vehicle in enumerate(vehicles):
            v = {
                "id": idx,
                "start": [float(vehicle.start_longitude), float(vehicle.start_latitude)],
                "capacity": [int(vehicle.capacity_kg)],
                "description": vehicle.name,
            }

            # Add end location if different from start
            if vehicle.end_latitude and vehicle.end_longitude:
                v["end"] = [float(vehicle.end_longitude), float(vehicle.end_latitude)]
            else:
                v["end"] = v["start"]

            # Add time window
            v["time_window"] = [
                self._time_to_timestamp(vehicle.work_start, route_date),
                self._time_to_timestamp(vehicle.work_end, route_date),
            ]

            vroom_vehicles.append(v)

        return vroom_vehicles

    def prepare_jobs(
        self,
        orders: list[DeliveryOrder],
        clients_map: dict[uuid.UUID, Client],
        route_date: date,
    ) -> list[dict]:
        """
        Prepare job data for VROOM request.

        Args:
            orders: List of DeliveryOrder models
            clients_map: Dictionary mapping client_id to Client
            route_date: Date for the route

        Returns:
            List of VROOM job dictionaries
        """
        vroom_jobs = []

        for idx, order in enumerate(orders):
            client = clients_map.get(order.client_id)
            if not client:
                continue

            job = {
                "id": idx,
                "location": [float(client.longitude), float(client.latitude)],
                "service": order.service_time_minutes * 60,  # convert to seconds
                "amount": [int(order.weight_kg)],
                "priority": order.priority,
                "description": f"Order {order.external_id}",
            }

            # Add time window
            job["time_windows"] = [
                [
                    self._datetime_to_timestamp(order.time_window_start),
                    self._datetime_to_timestamp(order.time_window_end),
                ]
            ]

            vroom_jobs.append(job)

        return vroom_jobs

    async def solve(
        self,
        problem: Any,  # Typed as Any to support both RoutingProblem and legacy args
        *args,
        **kwargs,
    ) -> Any:
        # Check if called with RoutingProblem (new interface)
        if isinstance(problem, RoutingProblem):
            return await self._solve_problem(problem)

        # Legacy call support
        return await self._solve_legacy(problem, *args, **kwargs)

    async def _solve_problem(self, problem: RoutingProblem) -> SolutionResult:
        """Solve using RoutingProblem definition."""

        # Determine profile
        profile = "car"  # Default VROOM profile
        if problem.transport_mode == TransportMode.PEDESTRIAN:
            profile = "foot"  # Assuming VROOM configured with 'foot' profile
        elif problem.transport_mode == TransportMode.BICYCLE:
            profile = "bicycle"

        # Prepare request
        vehicles_data = self._prepare_vehicles_from_config(problem.vehicles, profile)
        jobs_data = self._prepare_jobs_from_routing_jobs(problem.jobs)

        request_data = {
            "vehicles": vehicles_data,
            "jobs": jobs_data,
            "options": {
                "g": True,
            },
        }

        # Call VROOM
        result = await self.solve_raw(request_data)

        # Parse result into SolutionResult (adapter logic)
        return self._parse_vroom_to_solution_result(result, problem)

    async def _solve_legacy(
        self,
        orders: list[DeliveryOrder],
        vehicles: list[Vehicle],
        clients_map: dict[uuid.UUID, Client],
        route_date: date,
        explore: int = 5,
    ) -> VROOMSolution:
        """
        Solve VRP for given orders and vehicles (legacy interface).

        Args:
            orders: List of orders to deliver
            vehicles: List of available vehicles
            clients_map: Map of client IDs to Client objects
            route_date: Date for the routes
            explore: Exploration level (higher = better quality, slower)

        Returns:
            VROOMSolution with optimized routes

        Raises:
            VROOMError: If solving fails after retries
        """
        request_data = {
            "vehicles": self.prepare_vehicles(vehicles, route_date),
            "jobs": self.prepare_jobs(orders, clients_map, route_date),
            "options": {
                "g": True,  # return geometry
                "explore": explore,
            },
        }

        logger.info(f"Solving VRP with VROOM: {len(orders)} orders, {len(vehicles)} vehicles")

        data = await self._request_with_retry(request_data, "solve")

        logger.info(
            f"VROOM solution: {len(data.get('routes', []))} routes, " f"{len(data.get('unassigned', []))} unassigned"
        )

        return self._parse_solution(data, orders, vehicles)

    def _prepare_vehicles_from_config(self, vehicles: list[VehicleConfig], profile: str) -> list[dict]:
        vroom_vehicles = []
        for idx, v_conf in enumerate(vehicles):
            v = {
                "id": idx,
                "profile": profile,
                "start": (
                    [v_conf.start_location.longitude, v_conf.start_location.latitude]
                    if v_conf.start_location
                    else [0, 0]
                ),
                "capacity": [int(v_conf.capacity_kg)],
                "description": v_conf.name,
                # Time window (seconds from midnight)
                "time_window": [
                    v_conf.work_start.hour * 3600 + v_conf.work_start.minute * 60,
                    v_conf.work_end.hour * 3600 + v_conf.work_end.minute * 60,
                ],
            }
            if v_conf.end_location:
                v["end"] = [v_conf.end_location.longitude, v_conf.end_location.latitude]

            # Map breaks
            if v_conf.breaks:
                v["breaks"] = []
                for b in v_conf.breaks:
                    v_break = {
                        "id": b.id,
                        "description": b.description,
                        "service": b.duration_minutes * 60,
                    }
                    if b.start and b.end:
                        # Provide time window for break: assumes break happens within this window
                        # For fixed lunch break 13:00-14:00, window is [13:00, 14:00] and service matches duration
                        v_break["time_windows"] = [
                            [
                                b.start.hour * 3600 + b.start.minute * 60,
                                b.end.hour * 3600 + b.end.minute * 60,
                            ]
                        ]
                    v["breaks"].append(v_break)

            vroom_vehicles.append(v)
        return vroom_vehicles

    def _prepare_jobs_from_routing_jobs(self, jobs: list[Job]) -> list[dict]:
        vroom_jobs = []
        for idx, job in enumerate(jobs):
            j = {
                "id": idx,
                "location": [job.location.longitude, job.location.latitude],
                "service": job.location.service_time_minutes * 60,
                "amount": [int(job.demand_kg)],
                "priority": job.priority,
                "description": str(job.id),
            }
            if job.time_window_start and job.time_window_end:
                # Timestamps? VROOM usually expects [start_sec, end_sec] relative to 0 if no date provided
                # Or unix timestamps. Let's use relative for now if dates match, or just unix.
                # Given RoutingProblem usually has dates, let's stick to Unix timestamp consistency if VROOM expects it.
                # Actually VROOM is agnostic, but consistency matters.
                # _time_to_timestamp uses Unix.
                # Let's use Unix timestamps for jobs.
                j["time_windows"] = [[int(job.time_window_start.timestamp()), int(job.time_window_end.timestamp())]]
            vroom_jobs.append(j)
        return vroom_jobs

    def _parse_vroom_to_solution_result(self, data: dict, problem: RoutingProblem) -> SolutionResult:
        """Parse raw VROOM response to SolutionResult."""
        routes = []
        unassigned_ids = []

        # Parse unassigned
        for u in data.get("unassigned", []):
            job_idx = u["id"]
            if job_idx < len(problem.jobs):
                unassigned_ids.append(problem.jobs[job_idx].id)

        # Parse routes
        total_dist = 0
        total_dur = 0

        for r in data.get("routes", []):
            v_idx = r["vehicle"]
            if v_idx >= len(problem.vehicles):
                continue

            vehicle = problem.vehicles[v_idx]
            steps = []

            for s in r.get("steps", []):
                s_type = s["type"]
                loc_coords = s.get("location", [0, 0])
                location = Location(
                    id=uuid.uuid4(), name=s_type, latitude=loc_coords[1], longitude=loc_coords[0]  # Dummy
                )

                job_id = None
                if s_type == "job":
                    job_idx = s["job"]
                    if job_idx < len(problem.jobs):
                        job_id = problem.jobs[job_idx].id
                        location = problem.jobs[job_idx].location

                steps.append(
                    RouteStep(
                        job_id=job_id,
                        location=location,
                        arrival_time=datetime.fromtimestamp(s.get("arrival", 0)),
                        departure_time=datetime.fromtimestamp(s.get("arrival", 0) + s.get("service", 0)),
                        distance_from_previous_m=s.get("distance", 0),
                        duration_from_previous_s=s.get("duration", 0),
                        step_type=s_type,
                    )
                )

            route_dist = r.get("distance", 0)
            route_dur = r.get("duration", 0)
            total_dist += route_dist
            total_dur += route_dur

            # Parse load from delivery array (sum of all dimensions)
            delivery = r.get("delivery", [])
            total_load = sum(delivery) if delivery else 0

            routes.append(
                Route(
                    vehicle_id=vehicle.id,
                    vehicle_name=vehicle.name,
                    steps=steps,
                    total_distance_m=route_dist,
                    total_duration_s=route_dur,
                    total_load=total_load,
                    geometry=r.get("geometry"),
                )
            )

        return SolutionResult(
            routes=routes,
            unassigned_jobs=unassigned_ids,
            total_distance_m=total_dist,
            total_duration_s=total_dur,
            solver_used=SolverType.VROOM,
        )

    def _parse_solution(
        self,
        data: dict,
        orders: list[DeliveryOrder],
        vehicles: list[Vehicle],
    ) -> VROOMSolution:
        """Parse VROOM response into VROOMSolution."""
        routes = []

        for route_data in data.get("routes", []):
            steps = []
            for step_data in route_data.get("steps", []):
                step = VROOMStep(
                    type=step_data["type"],
                    location=step_data.get("location", [0, 0]),
                    arrival=step_data.get("arrival", 0),
                    duration=step_data.get("duration", 0),
                    distance=step_data.get("distance", 0),
                    service=step_data.get("service", 0),
                    job_id=step_data.get("job"),
                    load=step_data.get("load", []),
                )
                steps.append(step)

            route = VROOMRoute(
                vehicle_id=route_data["vehicle"],
                steps=steps,
                cost=route_data.get("cost", 0),
                duration=route_data.get("duration", 0),
                distance=route_data.get("distance", 0),
                service=route_data.get("service", 0),
                waiting_time=route_data.get("waiting_time", 0),
                delivery=route_data.get("delivery", []),
                geometry=route_data.get("geometry"),
            )
            routes.append(route)

        return VROOMSolution(
            code=data.get("code", 0),
            summary=data.get("summary", {}),
            routes=routes,
            unassigned=data.get("unassigned", []),
        )

    async def solve_tsp(
        self,
        locations: list[Location],
        start_index: int = 0,
        return_to_start: bool = True,
    ) -> list[int]:
        """
        Solve TSP using VROOM.

        Args:
            locations: List of locations to visit
            start_index: Index of starting location
            return_to_start: Whether to return to start location

        Returns:
            List of location indices in optimal order
        """
        if len(locations) <= 2:
            return list(range(len(locations)))

        # Build VROOM request for TSP
        start_loc = locations[start_index]
        start_coords = [float(start_loc.longitude), float(start_loc.latitude)]

        # Create single vehicle starting (and optionally ending) at start location
        vehicle = {
            "id": 0,
            "start": start_coords,
            "profile": "car",
        }
        if return_to_start:
            vehicle["end"] = start_coords

        # Create jobs for all locations except start
        jobs = []
        index_mapping = {}  # VROOM job_id -> original location index

        job_id = 0
        for i, loc in enumerate(locations):
            if i == start_index:
                continue
            jobs.append(
                {
                    "id": job_id,
                    "location": [float(loc.longitude), float(loc.latitude)],
                    "service": 0,  # No service time for pure TSP
                }
            )
            index_mapping[job_id] = i
            job_id += 1

        request_data = {
            "vehicles": [vehicle],
            "jobs": jobs,
            "options": {
                "g": True,  # Return geometry
            },
        }

        try:
            response = await self._request_with_retry(request_data, "tsp")

            if response.get("code") != 0:
                logger.warning(f"VROOM TSP failed: {response}")
                return list(range(len(locations)))

            # Extract tour order from solution
            routes = response.get("routes", [])
            if not routes:
                return list(range(len(locations)))

            # Build ordered list of indices
            tour = [start_index]  # Start with starting location

            for step in routes[0].get("steps", []):
                if step.get("type") == "job":
                    vroom_job_id = step.get("job")
                    if vroom_job_id is not None and vroom_job_id in index_mapping:
                        tour.append(index_mapping[vroom_job_id])

            # If return_to_start and tour doesn't end at start, add it
            if return_to_start and tour[-1] != start_index:
                tour.append(start_index)

            return tour

        except Exception as e:
            logger.error(f"TSP solve failed: {e}, falling back to trivial order")
            return list(range(len(locations)))

    async def solve_raw(self, request_data: dict) -> dict:
        """
        Send raw VROOM request with retry logic.

        Args:
            request_data: VROOM-formatted request

        Returns:
            Raw VROOM response

        Raises:
            VROOMError: If request fails after retries
        """
        return await self._request_with_retry(request_data, "raw_solve")

    async def health_check(self) -> bool:
        """Check if VROOM service is available."""
        try:
            # Send minimal valid request
            request_data = {
                "vehicles": [
                    {
                        "id": 0,
                        "start": [69.279737, 41.311081],
                        "end": [69.279737, 41.311081],
                    }
                ],
                "jobs": [
                    {
                        "id": 0,
                        "location": [69.289737, 41.321081],
                    }
                ],
            }
            # Use direct request without retry for health check
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                response = await client.post(
                    self.base_url,
                    json=request_data,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("code") == 0
        except Exception as e:
            logger.debug(f"VROOM health check failed: {e}")
            return False


# Singleton instance
vroom_solver = VROOMSolver()
