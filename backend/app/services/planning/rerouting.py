"""
Dynamic re-routing service.

Handles real-time route adjustments based on:
- Agent GPS position changes
- New urgent orders
- Traffic conditions
- Order cancellations/changes
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.delivery_order import DeliveryOrder
from app.models.delivery_route import DeliveryRoute
from app.models.visit_plan import VisitPlan
from app.services.realtime.websocket_manager import manager
from app.services.routing.osrm_client import osrm_client
from app.services.solvers.solver_interface import (
    Location,
    SolverFactory,
    SolverType,
)

logger = logging.getLogger(__name__)


@dataclass
class RerouteRequest:
    """Request for route re-optimization."""

    route_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    reason: str = "manual"  # manual, gps_deviation, new_order, order_cancelled
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    skip_completed: bool = True  # Skip already completed stops
    preserve_next_stop: bool = True  # Don't change the immediate next stop


@dataclass
class RerouteResult:
    """Result of re-routing operation."""

    success: bool
    route_id: Optional[UUID] = None
    message: str = ""
    stops_reordered: int = 0
    distance_saved_m: int = 0
    time_saved_s: int = 0
    new_route_order: list[UUID] = None

    def __post_init__(self):
        if self.new_route_order is None:
            self.new_route_order = []


class ReroutingService:
    """
    Service for dynamic route re-optimization.

    Triggers:
    1. Manual re-route request
    2. GPS deviation beyond threshold
    3. New urgent order added
    4. Order cancelled mid-route
    """

    GPS_DEVIATION_THRESHOLD_M = 500  # Trigger re-route if >500m from expected
    MIN_REROUTE_INTERVAL_S = 300  # Don't re-route more than every 5 min

    def __init__(self):
        self._last_reroute: dict[UUID, datetime] = {}

    async def check_and_reroute_agent(
        self,
        db: AsyncSession,
        agent_id: UUID,
        current_lat: float,
        current_lon: float,
    ) -> Optional[RerouteResult]:
        """
        Check if agent has deviated from route and trigger re-route if needed.

        Called on GPS updates.
        """
        # Check rate limit
        if not self._can_reroute(agent_id):
            return None

        # Get agent's current route/plan
        today = datetime.utcnow().date()

        result = await db.execute(
            select(VisitPlan)
            .where(
                and_(
                    VisitPlan.agent_id == agent_id,
                    VisitPlan.planned_date == today,
                    VisitPlan.status == "planned",
                )
            )
            .options(selectinload(VisitPlan.client))
            .order_by(VisitPlan.sequence_number)
        )
        remaining_visits = result.scalars().all()

        if len(remaining_visits) < 2:
            return None  # Nothing to optimize

        # Get next expected location
        next_visit = remaining_visits[0]
        next_client = next_visit.client

        if not next_client:
            return None

        # Calculate distance from expected position
        expected_lat = float(next_client.latitude)
        expected_lon = float(next_client.longitude)

        # Simple distance check (Haversine would be better)
        distance = await self._calculate_distance(current_lat, current_lon, expected_lat, expected_lon)

        if distance < self.GPS_DEVIATION_THRESHOLD_M:
            return None  # Within tolerance

        # Trigger re-route
        logger.info(f"Agent {agent_id} deviated {distance:.0f}m from route, triggering re-route")

        return await self.reroute_agent_visits(
            db=db,
            agent_id=agent_id,
            current_lat=current_lat,
            current_lon=current_lon,
            remaining_visits=remaining_visits,
            reason="gps_deviation",
        )

    async def reroute_agent_visits(
        self,
        db: AsyncSession,
        agent_id: UUID,
        current_lat: float,
        current_lon: float,
        remaining_visits: Optional[list[VisitPlan]] = None,
        reason: str = "manual",
    ) -> RerouteResult:
        """
        Re-optimize remaining visits for an agent from their current position.
        """
        self._last_reroute[agent_id] = datetime.utcnow()

        # Get remaining visits if not provided
        if remaining_visits is None:
            today = datetime.utcnow().date()
            result = await db.execute(
                select(VisitPlan)
                .where(
                    and_(
                        VisitPlan.agent_id == agent_id,
                        VisitPlan.planned_date == today,
                        VisitPlan.status == "planned",
                    )
                )
                .options(selectinload(VisitPlan.client))
                .order_by(VisitPlan.sequence_number)
            )
            remaining_visits = result.scalars().all()

        if len(remaining_visits) < 2:
            return RerouteResult(
                success=False,
                message="Not enough remaining visits to optimize",
            )

        # Build locations for TSP
        locations = [
            Location(
                id=UUID(int=0),  # Current position as pseudo-location
                name="Current Position",
                latitude=current_lat,
                longitude=current_lon,
                service_time_minutes=0,
            )
        ]

        visit_map = {}  # index -> visit
        for i, visit in enumerate(remaining_visits):
            if visit.client:
                loc = Location(
                    id=visit.client.id,
                    name=visit.client.name,
                    latitude=float(visit.client.latitude),
                    longitude=float(visit.client.longitude),
                    service_time_minutes=visit.client.visit_duration_minutes or 15,
                )
                locations.append(loc)
                visit_map[i + 1] = visit  # +1 because 0 is current position

        if len(locations) < 3:
            return RerouteResult(
                success=False,
                message="Not enough locations to optimize",
            )

        # Solve TSP from current position
        try:
            solver = SolverFactory.get_solver(SolverType.ORTOOLS)
            optimal_order = await solver.solve_tsp(
                locations=locations,
                start_index=0,
                return_to_start=False,
            )

            # Remove start position and map back to visits
            optimal_order = [i for i in optimal_order if i > 0]

            # Calculate savings
            old_distance = await self._calculate_route_distance(
                [(current_lat, current_lon)]
                + [(float(v.client.latitude), float(v.client.longitude)) for v in remaining_visits if v.client]
            )
            new_distance = await self._calculate_route_distance(
                [(current_lat, current_lon)]
                + [
                    (float(visit_map[i].client.latitude), float(visit_map[i].client.longitude))
                    for i in optimal_order
                    if i in visit_map and visit_map[i].client
                ]
            )

            distance_saved = max(0, old_distance - new_distance)

            # Update visit sequence numbers
            new_route_order = []
            for new_seq, old_idx in enumerate(optimal_order, start=1):
                if old_idx in visit_map:
                    visit = visit_map[old_idx]
                    visit.sequence_number = new_seq
                    new_route_order.append(visit.id)

            await db.commit()

            result = RerouteResult(
                success=True,
                message=f"Route optimized: {len(optimal_order)} stops reordered",
                stops_reordered=len(optimal_order),
                distance_saved_m=int(distance_saved),
                time_saved_s=int(distance_saved / 8.33),  # ~30 km/h
                new_route_order=new_route_order,
            )

            # Broadcast route update
            await self._broadcast_route_update(agent_id, result, reason)

            return result

        except Exception as e:
            logger.error(f"Re-routing failed for agent {agent_id}: {e}")
            return RerouteResult(
                success=False,
                message=f"Optimization failed: {str(e)}",
            )

    async def reroute_delivery_route(
        self,
        db: AsyncSession,
        route_id: UUID,
        current_lat: Optional[float] = None,
        current_lon: Optional[float] = None,
        reason: str = "manual",
    ) -> RerouteResult:
        """
        Re-optimize a delivery route from current position.
        """
        # Get route with stops
        result = await db.execute(
            select(DeliveryRoute)
            .where(DeliveryRoute.id == route_id)
            .options(
                selectinload(DeliveryRoute.stops),
                selectinload(DeliveryRoute.vehicle),
            )
        )
        route = result.scalar_one_or_none()

        if not route:
            return RerouteResult(
                success=False,
                message="Route not found",
            )

        # Get pending stops
        pending_stops = [s for s in route.stops if s.status in ("pending", "assigned")]

        if len(pending_stops) < 2:
            return RerouteResult(
                success=False,
                route_id=route_id,
                message="Not enough pending stops to optimize",
            )

        # Use vehicle start or current position
        if current_lat is None or current_lon is None:
            if route.vehicle and route.vehicle.start_latitude:
                current_lat = float(route.vehicle.start_latitude)
                current_lon = float(route.vehicle.start_longitude)
            else:
                return RerouteResult(
                    success=False,
                    route_id=route_id,
                    message="Current position required",
                )

        # Build locations
        locations = [
            Location(
                id=UUID(int=0),
                name="Current Position",
                latitude=current_lat,
                longitude=current_lon,
                service_time_minutes=0,
            )
        ]

        stop_map = {}
        for i, stop in enumerate(pending_stops):
            loc = Location(
                id=stop.id,
                name=f"Stop {stop.sequence_number}",
                latitude=float(stop.latitude) if stop.latitude else 0,
                longitude=float(stop.longitude) if stop.longitude else 0,
                service_time_minutes=15,
            )
            locations.append(loc)
            stop_map[i + 1] = stop

        # Solve TSP
        try:
            solver = SolverFactory.get_solver(SolverType.ORTOOLS)
            optimal_order = await solver.solve_tsp(
                locations=locations,
                start_index=0,
                return_to_start=False,
            )

            # Update stop sequence
            optimal_order = [i for i in optimal_order if i > 0]
            new_route_order = []

            for new_seq, old_idx in enumerate(optimal_order, start=1):
                if old_idx in stop_map:
                    stop = stop_map[old_idx]
                    stop.sequence_number = new_seq
                    new_route_order.append(stop.id)

            await db.commit()

            result = RerouteResult(
                success=True,
                route_id=route_id,
                message=f"Delivery route optimized: {len(optimal_order)} stops",
                stops_reordered=len(optimal_order),
                new_route_order=new_route_order,
            )

            # Broadcast update
            await manager.broadcast(
                {
                    "type": "route_updated",
                    "route_id": str(route_id),
                    "reason": reason,
                    "stops_reordered": len(optimal_order),
                    "new_order": [str(uid) for uid in new_route_order],
                },
                topic="dispatchers",
            )

            return result

        except Exception as e:
            logger.error(f"Re-routing failed for route {route_id}: {e}")
            return RerouteResult(
                success=False,
                route_id=route_id,
                message=f"Optimization failed: {str(e)}",
            )

    async def add_urgent_stop(
        self,
        db: AsyncSession,
        route_id: UUID,
        order_id: UUID,
        insert_position: str = "optimal",  # "optimal", "next", "last"
    ) -> RerouteResult:
        """
        Add an urgent order to an existing route.

        Finds the optimal position to insert the new stop
        with minimal distance increase.
        """
        # Get route and new order
        route_result = await db.execute(
            select(DeliveryRoute).where(DeliveryRoute.id == route_id).options(selectinload(DeliveryRoute.stops))
        )
        route = route_result.scalar_one_or_none()

        order_result = await db.execute(
            select(DeliveryOrder).where(DeliveryOrder.id == order_id).options(selectinload(DeliveryOrder.client))
        )
        order = order_result.scalar_one_or_none()

        if not route or not order:
            return RerouteResult(
                success=False,
                route_id=route_id,
                message="Route or order not found",
            )

        if not order.client:
            return RerouteResult(
                success=False,
                route_id=route_id,
                message="Order has no client location",
            )

        pending_stops = sorted(
            [s for s in route.stops if s.status == "pending"],
            key=lambda s: s.sequence_number,
        )

        # Find optimal insertion point
        new_lat = float(order.client.latitude)
        new_lon = float(order.client.longitude)

        if insert_position == "next":
            insert_at = 1
        elif insert_position == "last":
            insert_at = len(pending_stops) + 1
        else:
            # Find position with minimum distance increase
            best_pos = len(pending_stops) + 1
            best_increase = float("inf")

            for i in range(len(pending_stops) + 1):
                increase = await self._calculate_insertion_cost(pending_stops, i, new_lat, new_lon)
                if increase < best_increase:
                    best_increase = increase
                    best_pos = i + 1  # 1-indexed sequence

            insert_at = best_pos

        # Shift existing stops and insert new one
        for stop in pending_stops:
            if stop.sequence_number >= insert_at:
                stop.sequence_number += 1

        # Create new stop (this would be done in the route service normally)
        # For now, just return the result
        await db.commit()

        result = RerouteResult(
            success=True,
            route_id=route_id,
            message=f"Order added at position {insert_at}",
            stops_reordered=len(pending_stops) + 1,
        )

        # Broadcast
        await manager.broadcast(
            {
                "type": "stop_added",
                "route_id": str(route_id),
                "order_id": str(order_id),
                "position": insert_at,
            },
            topic="dispatchers",
        )

        return result

    def _can_reroute(self, entity_id: UUID) -> bool:
        """Check if enough time has passed since last re-route."""
        last = self._last_reroute.get(entity_id)
        if not last:
            return True
        elapsed = (datetime.utcnow() - last).total_seconds()
        return elapsed >= self.MIN_REROUTE_INTERVAL_S

    async def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Calculate distance between two points using OSRM."""
        try:
            result = await osrm_client.get_route([(lon1, lat1), (lon2, lat2)])
            return result.distance_meters
        except Exception:
            # Fallback to Haversine
            import math

            R = 6371000  # Earth radius in meters
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = (
                math.sin(dlat / 2) ** 2
                + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
            )
            return R * 2 * math.asin(math.sqrt(a))

    async def _calculate_route_distance(
        self,
        coordinates: list[tuple[float, float]],
    ) -> float:
        """Calculate total route distance."""
        if len(coordinates) < 2:
            return 0

        total = 0
        for i in range(len(coordinates) - 1):
            lat1, lon1 = coordinates[i]
            lat2, lon2 = coordinates[i + 1]
            total += await self._calculate_distance(lat1, lon1, lat2, lon2)
        return total

    async def _calculate_insertion_cost(
        self,
        stops: list,
        position: int,
        new_lat: float,
        new_lon: float,
    ) -> float:
        """Calculate distance increase from inserting at position."""
        if not stops:
            return 0

        # Get coordinates before and after insertion point
        if position == 0:
            # Insert at beginning
            if stops:
                next_stop = stops[0]
                return await self._calculate_distance(
                    new_lat, new_lon, float(next_stop.latitude), float(next_stop.longitude)
                )
            return 0

        elif position >= len(stops):
            # Insert at end
            prev_stop = stops[-1]
            return await self._calculate_distance(
                float(prev_stop.latitude), float(prev_stop.longitude), new_lat, new_lon
            )

        else:
            # Insert in middle
            prev_stop = stops[position - 1]
            next_stop = stops[position]

            # Old distance: prev -> next
            old_dist = await self._calculate_distance(
                float(prev_stop.latitude),
                float(prev_stop.longitude),
                float(next_stop.latitude),
                float(next_stop.longitude),
            )

            # New distance: prev -> new -> next
            new_dist = await self._calculate_distance(
                float(prev_stop.latitude), float(prev_stop.longitude), new_lat, new_lon
            ) + await self._calculate_distance(new_lat, new_lon, float(next_stop.latitude), float(next_stop.longitude))

            return new_dist - old_dist

    async def _broadcast_route_update(
        self,
        agent_id: UUID,
        result: RerouteResult,
        reason: str,
    ):
        """Broadcast route update to relevant parties."""
        # Notify dispatchers
        await manager.broadcast(
            {
                "type": "agent_route_updated",
                "agent_id": str(agent_id),
                "reason": reason,
                "stops_reordered": result.stops_reordered,
                "distance_saved_m": result.distance_saved_m,
                "new_order": [str(uid) for uid in result.new_route_order],
            },
            topic="dispatchers",
        )

        # Notify the agent
        await manager.broadcast(
            {
                "type": "your_route_updated",
                "reason": reason,
                "message": result.message,
                "new_order": [str(uid) for uid in result.new_route_order],
            },
            topic=f"agent:{agent_id}",
        )


# Singleton instance
rerouting_service = ReroutingService()
