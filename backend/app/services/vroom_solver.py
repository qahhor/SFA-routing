"""
VROOM (Vehicle Routing Open-source Optimization Machine) solver.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from typing import Optional, Any

import httpx

from app.core.config import settings
from app.models.delivery_order import DeliveryOrder
from app.models.vehicle import Vehicle
from app.models.client import Client


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


class VROOMSolver:
    """
    Solver for Vehicle Routing Problem using VROOM.

    VROOM solves VRP with:
    - Multiple vehicles with capacities
    - Time windows for pickups/deliveries
    - Service times at stops
    - Priority-based optimization
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.VROOM_URL).rstrip("/")
        self.timeout = httpx.Timeout(300.0, connect=30.0)

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
            job["time_windows"] = [[
                self._datetime_to_timestamp(order.time_window_start),
                self._datetime_to_timestamp(order.time_window_end),
            ]]

            vroom_jobs.append(job)

        return vroom_jobs

    async def solve(
        self,
        orders: list[DeliveryOrder],
        vehicles: list[Vehicle],
        clients_map: dict[uuid.UUID, Client],
        route_date: date,
        explore: int = 5,
    ) -> VROOMSolution:
        """
        Solve VRP for given orders and vehicles.

        Args:
            orders: List of orders to deliver
            vehicles: List of available vehicles
            clients_map: Map of client IDs to Client objects
            route_date: Date for the routes
            explore: Exploration level (higher = better quality, slower)

        Returns:
            VROOMSolution with optimized routes
        """
        request_data = {
            "vehicles": self.prepare_vehicles(vehicles, route_date),
            "jobs": self.prepare_jobs(orders, clients_map, route_date),
            "options": {
                "g": True,  # return geometry
                "explore": explore,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.base_url,
                json=request_data,
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_solution(data, orders, vehicles)

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

    async def solve_raw(self, request_data: dict) -> dict:
        """
        Send raw VROOM request.

        Args:
            request_data: VROOM-formatted request

        Returns:
            Raw VROOM response
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.base_url,
                json=request_data,
            )
            response.raise_for_status()
            return response.json()

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
            result = await self.solve_raw(request_data)
            return result.get("code") == 0
        except Exception:
            return False


# Singleton instance
vroom_solver = VROOMSolver()
