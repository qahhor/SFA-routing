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
from app.models.delivery_order import DeliveryOrder, OrderStatus
from app.models.delivery_route import DeliveryRoute, DeliveryRouteStop, RouteStatus
from app.models.vehicle import Vehicle
from app.models.client import Client
from app.services.solver_interface import (
    SolverFactory,
    SolverType,
    RoutingProblem,
    Job,
    VehicleConfig,
    Location,
    TransportMode,
    SolutionResult,
)
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

    """

    def __init__(
        self,
        osrm: Optional[OSRMClient] = None,
    ):
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
        
        # Build RoutingProblem
        problem = self._build_problem(orders, vehicles, clients_map, route_date)

        # Solve using SolverFactory with fallback
        try:
            solution = await SolverFactory.solve_with_fallback(
                problem,
                preferred=SolverType.VROOM
            )
        except Exception as e:
            # Fallback failed completely
            return OptimizationResult(
                routes=[],
                unassigned_orders=[o.id for o in orders],
                total_distance_km=0,
                total_duration_minutes=0,
                total_vehicles_used=0,
                summary={"error": str(e)},
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

    def _build_problem(
        self,
        orders: list[DeliveryOrder],
        vehicles: list[Vehicle],
        clients_map: dict[uuid.UUID, Client],
        route_date: date,
    ) -> RoutingProblem:
        """Build RoutingProblem from domain models."""
        
        # Convert vehicles
        vehicle_configs = []
        for v in vehicles:
            start_loc = Location(
                id=uuid.uuid4(),
                name=f"Start {v.name}",
                latitude=float(v.start_latitude),
                longitude=float(v.start_longitude),
            )
            
            end_loc = None
            if v.end_latitude and v.end_longitude:
                end_loc = Location(
                    id=uuid.uuid4(),
                    name=f"End {v.name}",
                    latitude=float(v.end_latitude),
                    longitude=float(v.end_longitude),
                )
            
            vehicle_configs.append(VehicleConfig(
                id=v.id,
                name=v.name,
                capacity_kg=float(v.capacity_kg),
                start_location=start_loc,
                end_location=end_loc,
                work_start=v.work_start,
                work_end=v.work_end,
            ))
            
        # Convert orders to jobs
        jobs = []
        for order in orders:
            client = clients_map.get(order.client_id)
            if not client:
                continue
                
            loc = Location(
                id=uuid.uuid4(),
                name=client.name,
                latitude=float(client.latitude),
                longitude=float(client.longitude),
                service_time_minutes=order.service_time_minutes,
            )
            
            jobs.append(Job(
                id=uuid.uuid4(), # Use internal ID to map back? Or order ID directly? 
                # Job expects UUID. Let's map strict index logic or reuse order ID if it's UUID.
                # Only Job.id is UUID. DeliveryOrder.id is UUID. Perfect
                location=loc,
                demand_kg=float(order.weight_kg),
                priority=order.priority,
                time_window_start=order.time_window_start,
                time_window_end=order.time_window_end,
                
                # FMCG Advanced Features
                stock_days_remaining=client.stock_days_remaining,
                outstanding_debt=float(client.outstanding_debt or 0),
                is_new_client=client.is_new_client,
                has_active_promo=client.has_active_promo,
                churn_risk_score=float(client.churn_risk_score or 0),
            ))
            
            # Recalculate priority based on FMCG factors
            # Check if today is payday (simplified check, real logic needs business calendar)
            is_payday = route_date.day in [5, 20]
            jobs[-1].priority = int(jobs[-1].calculate_priority_score(is_payday=is_payday))
            
        return RoutingProblem(
            jobs=jobs,
            vehicles=vehicle_configs,
            planning_date=route_date,
            transport_mode=TransportMode.CAR, # Delivery implies car usually
            has_time_windows=True,
        )

    def _parse_solution(
        self,
        solution: Any,
        orders: list[DeliveryOrder],
        vehicles: list[Vehicle],
        order_index: dict[int, DeliveryOrder],
        vehicle_index: dict[int, Vehicle],
        clients_map: dict[uuid.UUID, Client],
        route_date: date,
    ) -> OptimizationResult:
        """Parse solution into OptimizationResult."""
        # Handle new SolutionResult
        if isinstance(solution, SolutionResult):
             return self._parse_solution_result(
                solution, orders, vehicles, order_index, vehicle_index, clients_map, route_date
             )

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

    def _parse_solution_result(
        self,
        solution: SolutionResult,
        orders: list[DeliveryOrder],
        vehicles: list[Vehicle],
        order_index: dict[int, DeliveryOrder],
        vehicle_index: dict[int, Vehicle],
        clients_map: dict[uuid.UUID, Client],
        route_date: date,
    ) -> OptimizationResult:
        """Parse standard SolutionResult."""
        opt_routes = []
        
        # Map UUID back to objects
        orders_map = {o.id: o for o in orders}
        vehicles_map = {v.id: v for v in vehicles}
        
        for route in solution.routes:
            vehicle = vehicles_map.get(route.vehicle_id)
            if not vehicle:
                continue

            stops = []
            
            for step in route.steps:
                if step.step_type == "job" and step.job_id:
                    order = orders_map.get(step.job_id)
                    if not order:
                        continue
                    
                    client = clients_map.get(order.client_id)
                    client_name = client.name if client else "Unknown"
                    client_lat = float(client.latitude) if client else 0.0
                    client_lon = float(client.longitude) if client else 0.0
                    
                    stops.append(OptimizedStop(
                        order_id=order.id,
                        client_id=order.client_id,
                        client_name=client_name,
                        sequence_number=len(stops) + 1,
                        planned_arrival=step.arrival_time,
                        planned_departure=step.departure_time,
                        distance_from_previous_km=float(step.distance_from_previous_m) / 1000,
                        duration_from_previous_minutes=int(step.duration_from_previous_s / 60) if getattr(step, 'duration_from_previous_s', None) else 0,
                        weight_kg=float(order.weight_kg),
                        latitude=client_lat,
                        longitude=client_lon,
                    ))
            
            if stops:
                opt_routes.append(OptimizedRoute(
                    vehicle_id=vehicle.id,
                    vehicle_name=vehicle.name,
                    stops=stops,
                    total_distance_km=float(route.total_distance_m) / 1000,
                    total_duration_minutes=int(route.total_duration_s / 60),
                    total_weight_kg=float(route.total_load),
                    planned_start=route.steps[0].departure_time if route.steps else datetime.combine(route_date, datetime.min.time()),
                    planned_end=route.steps[-1].arrival_time if route.steps else datetime.combine(route_date, datetime.max.time()),
                    geometry=route.geometry,
                ))
                
        return OptimizationResult(
            routes=opt_routes,
            unassigned_orders=solution.unassigned_jobs,
            total_distance_km=float(solution.total_distance_m) / 1000,
            total_duration_minutes=int(solution.total_duration_s / 60),
            total_vehicles_used=len(opt_routes),
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
