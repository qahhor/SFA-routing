"""
Background optimization tasks using Celery.
"""
import asyncio
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.celery_app import celery_app
from app.models.agent import Agent
from app.models.client import Client
from app.models.delivery_order import DeliveryOrder, OrderStatus
from app.models.delivery_route import DeliveryRoute, DeliveryRouteStop, RouteStatus
from app.models.vehicle import Vehicle
from app.models.visit_plan import VisitPlan, VisitStatus
from app.services import WeeklyPlanner, RouteOptimizer


def get_async_session() -> async_sessionmaker[AsyncSession]:
    """Create async session for background tasks."""
    engine = create_async_engine(settings.DATABASE_URL)
    return async_sessionmaker(engine, expire_on_commit=False)


def run_async(coro):
    """Run async coroutine in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="app.tasks.optimization.generate_weekly_plan")
def generate_weekly_plan_task(
    self,
    agent_id: str,
    week_start_date: str,
    week_number: int = 1,
) -> dict[str, Any]:
    """
    Background task for generating weekly plan.

    Args:
        agent_id: UUID of the agent
        week_start_date: Start date of the week (ISO format)
        week_number: Week number in cycle (1 or 2)

    Returns:
        Dictionary with plan summary
    """
    return run_async(_generate_weekly_plan(
        UUID(agent_id),
        date.fromisoformat(week_start_date),
        week_number,
        self.request.id,
    ))


async def _generate_weekly_plan(
    agent_id: UUID,
    week_start: date,
    week_number: int,
    task_id: str,
) -> dict[str, Any]:
    """Async implementation of weekly plan generation."""
    AsyncSessionLocal = get_async_session()

    async with AsyncSessionLocal() as db:
        # Get agent
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()

        if not agent:
            return {"status": "error", "message": "Agent not found"}

        # Get agent's clients
        clients_result = await db.execute(
            select(Client).where(
                (Client.agent_id == agent_id)
                & (Client.is_active.is_(True))
            )
        )
        clients = list(clients_result.scalars().all())

        if not clients:
            return {"status": "error", "message": "No clients found for agent"}

        # Generate plan
        planner = WeeklyPlanner()
        plan = await planner.generate_weekly_plan(
            agent=agent,
            clients=clients,
            week_start=week_start,
            week_number=week_number,
        )

        # Save visit plans
        for daily_plan in plan.daily_plans:
            for visit in daily_plan.visits:
                visit_plan = VisitPlan(
                    agent_id=agent.id,
                    client_id=visit.client_id,
                    planned_date=daily_plan.date,
                    planned_time=visit.planned_time,
                    sequence_number=visit.sequence_number,
                    estimated_arrival_time=visit.estimated_arrival,
                    estimated_departure_time=visit.estimated_departure,
                    distance_from_previous_km=visit.distance_from_previous_km,
                    duration_from_previous_minutes=visit.duration_from_previous_minutes,
                    status=VisitStatus.PLANNED,
                )
                db.add(visit_plan)

        await db.commit()

        return {
            "status": "success",
            "task_id": task_id,
            "agent_id": str(agent_id),
            "week_start": week_start.isoformat(),
            "total_visits": plan.total_visits,
            "total_distance_km": plan.total_distance_km,
            "total_duration_minutes": plan.total_duration_minutes,
        }


@celery_app.task(bind=True, name="app.tasks.optimization.optimize_delivery_routes")
def optimize_delivery_routes_task(
    self,
    order_ids: list[str],
    vehicle_ids: list[str],
    route_date: str,
) -> dict[str, Any]:
    """
    Background task for optimizing delivery routes.

    Args:
        order_ids: List of order UUIDs
        vehicle_ids: List of vehicle UUIDs
        route_date: Date for routes (ISO format)

    Returns:
        Dictionary with optimization results
    """
    return run_async(_optimize_delivery_routes(
        [UUID(oid) for oid in order_ids],
        [UUID(vid) for vid in vehicle_ids],
        date.fromisoformat(route_date),
        self.request.id,
    ))


async def _optimize_delivery_routes(
    order_ids: list[UUID],
    vehicle_ids: list[UUID],
    route_date: date,
    task_id: str,
) -> dict[str, Any]:
    """Async implementation of delivery route optimization."""
    AsyncSessionLocal = get_async_session()

    async with AsyncSessionLocal() as db:
        # Get orders
        orders_result = await db.execute(
            select(DeliveryOrder)
            .options(selectinload(DeliveryOrder.client))
            .where(DeliveryOrder.id.in_(order_ids))
        )
        orders = list(orders_result.scalars().all())

        if not orders:
            return {"status": "error", "message": "No orders found"}

        # Get vehicles
        vehicles_result = await db.execute(
            select(Vehicle).where(Vehicle.id.in_(vehicle_ids))
        )
        vehicles = list(vehicles_result.scalars().all())

        if not vehicles:
            return {"status": "error", "message": "No vehicles found"}

        # Create clients map
        clients_map = {o.client_id: o.client for o in orders if o.client}

        # Optimize
        optimizer = RouteOptimizer()
        result = await optimizer.optimize(
            orders=orders,
            vehicles=vehicles,
            clients_map=clients_map,
            route_date=route_date,
        )

        # Save routes
        vehicle_map = {v.id: v for v in vehicles}
        route_ids = []

        for opt_route in result.routes:
            vehicle = vehicle_map.get(opt_route.vehicle_id)
            if not vehicle:
                continue

            route = DeliveryRoute(
                vehicle_id=vehicle.id,
                route_date=route_date,
                total_distance_km=Decimal(str(opt_route.total_distance_km)),
                total_duration_minutes=opt_route.total_duration_minutes,
                total_weight_kg=Decimal(str(opt_route.total_weight_kg)),
                total_stops=len(opt_route.stops),
                status=RouteStatus.PLANNED,
                planned_start=opt_route.planned_start,
                planned_end=opt_route.planned_end,
            )
            db.add(route)
            await db.flush()
            route_ids.append(str(route.id))

            for stop in opt_route.stops:
                route_stop = DeliveryRouteStop(
                    route_id=route.id,
                    order_id=stop.order_id,
                    sequence_number=stop.sequence_number,
                    distance_from_previous_km=Decimal(str(stop.distance_from_previous_km)),
                    duration_from_previous_minutes=stop.duration_from_previous_minutes,
                    planned_arrival=stop.planned_arrival,
                    planned_departure=stop.planned_departure,
                )
                db.add(route_stop)

        # Update order statuses
        for order in orders:
            if order.id not in result.unassigned_orders:
                order.status = OrderStatus.ASSIGNED

        await db.commit()

        return {
            "status": "success",
            "task_id": task_id,
            "route_date": route_date.isoformat(),
            "routes_created": len(route_ids),
            "route_ids": route_ids,
            "unassigned_orders": [str(oid) for oid in result.unassigned_orders],
            "total_distance_km": result.total_distance_km,
            "total_duration_minutes": result.total_duration_minutes,
            "total_vehicles_used": result.total_vehicles_used,
        }


@celery_app.task(name="app.tasks.optimization.health_check")
def health_check_task() -> dict[str, str]:
    """Simple health check task."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }
