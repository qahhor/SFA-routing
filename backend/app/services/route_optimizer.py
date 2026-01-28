"""
Route optimizer service for delivery routes.
"""
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from app.models.delivery_order import DeliveryOrder, OrderStatus
from app.models.delivery_route import DeliveryRoute, DeliveryRouteStop, RouteStatus
from app.models.vehicle import Vehicle
from app.models.client import Client
from app.services.vroom_solver import VROOMSolver, VROOMSolution, vroom_solver
from app.services.osrm_client import OSRMClient, osrm_client


@dataclass
class OptimizationResult:
    """Result of delivery route optimization."""
    routes: list["OptimizedRoute"]
    unassigned_orders: list[uuid.UUID]
    total_distance_km: float
    total_duration_minutes: int
    total_vehicles_used: int
    summary: dict


@dataclass
class OptimizedRoute:
    """Single optimized route for a vehicle."""
    vehicle_id: uuid.UUID
    vehicle_name: str
    stops: list["OptimizedStop"]
    total_distance_km: float
    total_duration_minutes: int
    total_weight_kg: float
    planned_start: datetime
    planned_end: datetime
    geometry: Optional[str] = None


@dataclass
class OptimizedStop:
    """Single stop in an optimized route."""
    order_id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    sequence_number: int
    planned_arrival: datetime
    planned_departure: datetime
    distance_from_previous_km: float
    duration_from_previous_minutes: int
    weight_kg: float
    latitude: float
    longitude: float


class RouteOptimizer:
    """
    Delivery route optimizer using VROOM.

    Optimizes routes considering:
    - Vehicle capacities (weight, volume)
    - Time windows for deliveries
    - Service times at each stop
    - Order priorities
    """

    def __init__(
        self,
        vroom: Optional[VROOMSolver] = None,
        osrm: Optional[OSRMClient] = None,
    ):
        self.vroom = vroom or vroom_solver
        self.osrm = osrm or osrm_client

    async def optimize(
        self,
        orders: list[DeliveryOrder],
        vehicles: list[Vehicle],
        clients_map: dict[uuid.UUID, Client],
        route_date: date,
    ) -> OptimizationResult:
        """
        Optimize delivery routes for given orders and vehicles.

        Args:
            orders: List of pending delivery orders
            vehicles: List of available vehicles
            clients_map: Map of client IDs to Client objects
            route_date: Date for the routes

        Returns:
            OptimizationResult with optimized routes
        """
        if not orders or not vehicles:
            return OptimizationResult(
                routes=[],
                unassigned_orders=[o.id for o in orders],
                total_distance_km=0,
                total_duration_minutes=0,
                total_vehicles_used=0,
                summary={},
            )

        # Create order and vehicle index maps
        order_index = {idx: order for idx, order in enumerate(orders)}
        vehicle_index = {idx: vehicle for idx, vehicle in enumerate(vehicles)}

        # Solve using VROOM
        solution = await self.vroom.solve(
            orders=orders,
            vehicles=vehicles,
            clients_map=clients_map,
            route_date=route_date,
        )

        # Parse solution into routes
        return self._parse_solution(
            solution=solution,
            orders=orders,
            vehicles=vehicles,
            order_index=order_index,
            vehicle_index=vehicle_index,
            clients_map=clients_map,
            route_date=route_date,
        )

    def _parse_solution(
        self,
        solution: VROOMSolution,
        orders: list[DeliveryOrder],
        vehicles: list[Vehicle],
        order_index: dict[int, DeliveryOrder],
        vehicle_index: dict[int, Vehicle],
        clients_map: dict[uuid.UUID, Client],
        route_date: date,
    ) -> OptimizationResult:
        """Parse VROOM solution into OptimizationResult."""
        optimized_routes = []
        total_distance = 0
        total_duration = 0

        for vroom_route in solution.routes:
            vehicle = vehicle_index[vroom_route.vehicle_id]
            stops = []
            sequence = 0
            route_weight = Decimal("0")

            for step in vroom_route.steps:
                if step.type == "job" and step.job_id is not None:
                    order = order_index[step.job_id]
                    client = clients_map.get(order.client_id)

                    if client:
                        sequence += 1
                        route_weight += order.weight_kg

                        arrival_dt = datetime.fromtimestamp(step.arrival)
                        departure_dt = arrival_dt + timedelta(
                            minutes=order.service_time_minutes
                        )

                        stops.append(OptimizedStop(
                            order_id=order.id,
                            client_id=client.id,
                            client_name=client.name,
                            sequence_number=sequence,
                            planned_arrival=arrival_dt,
                            planned_departure=departure_dt,
                            distance_from_previous_km=step.distance / 1000,
                            duration_from_previous_minutes=step.duration // 60,
                            weight_kg=float(order.weight_kg),
                            latitude=float(client.latitude),
                            longitude=float(client.longitude),
                        ))

            if stops:
                route_distance = vroom_route.distance / 1000
                route_duration = vroom_route.duration // 60
                total_distance += route_distance
                total_duration += route_duration

                optimized_routes.append(OptimizedRoute(
                    vehicle_id=vehicle.id,
                    vehicle_name=vehicle.name,
                    stops=stops,
                    total_distance_km=route_distance,
                    total_duration_minutes=route_duration,
                    total_weight_kg=float(route_weight),
                    planned_start=stops[0].planned_arrival - timedelta(
                        minutes=stops[0].duration_from_previous_minutes
                    ),
                    planned_end=stops[-1].planned_departure,
                    geometry=vroom_route.geometry,
                ))

        # Get unassigned orders
        unassigned_ids = [
            orders[u["id"]].id
            for u in solution.unassigned
            if u["id"] < len(orders)
        ]

        return OptimizationResult(
            routes=optimized_routes,
            unassigned_orders=unassigned_ids,
            total_distance_km=total_distance,
            total_duration_minutes=total_duration,
            total_vehicles_used=len(optimized_routes),
            summary=solution.summary,
        )

    async def create_delivery_routes(
        self,
        optimization_result: OptimizationResult,
        route_date: date,
    ) -> list[DeliveryRoute]:
        """
        Create DeliveryRoute models from optimization result.

        Args:
            optimization_result: Result from optimize()
            route_date: Date for the routes

        Returns:
            List of DeliveryRoute models (not yet persisted)
        """
        routes = []

        for opt_route in optimization_result.routes:
            route = DeliveryRoute(
                vehicle_id=opt_route.vehicle_id,
                route_date=route_date,
                total_distance_km=Decimal(str(opt_route.total_distance_km)),
                total_duration_minutes=opt_route.total_duration_minutes,
                total_weight_kg=Decimal(str(opt_route.total_weight_kg)),
                total_stops=len(opt_route.stops),
                status=RouteStatus.PLANNED,
                planned_start=opt_route.planned_start,
                planned_end=opt_route.planned_end,
            )

            # Create stops
            for stop in opt_route.stops:
                route_stop = DeliveryRouteStop(
                    route_id=route.id,
                    order_id=stop.order_id,
                    sequence_number=stop.sequence_number,
                    distance_from_previous_km=Decimal(
                        str(stop.distance_from_previous_km)
                    ),
                    duration_from_previous_minutes=stop.duration_from_previous_minutes,
                    planned_arrival=stop.planned_arrival,
                    planned_departure=stop.planned_departure,
                )
                route.stops.append(route_stop)

            routes.append(route)

        return routes


# Singleton instance
route_optimizer = RouteOptimizer()
