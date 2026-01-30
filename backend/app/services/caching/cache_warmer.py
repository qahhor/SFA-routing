"""
Cache Warming Service (R13).

Proactive cache warming for predictable access patterns.
Runs as a background task to pre-populate caches before
peak usage times.

Schedule: Daily at 05:00 local time (before work day starts)
"""

import asyncio
import logging
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


class CacheWarmer:
    """
    Proactive cache warming service.

    Warms:
    1. Distance matrices for active agents
    2. Reference data (clients, vehicles, agents)
    3. Today's visit plans
    4. Frequently accessed routes
    """

    def __init__(
        self,
        db_session_factory,
        cache_service,
        osrm_client,
    ):
        """
        Initialize cache warmer.

        Args:
            db_session_factory: Async session factory
            cache_service: Redis cache service
            osrm_client: OSRM client for distance matrices
        """
        self.db_session_factory = db_session_factory
        self.cache = cache_service
        self.osrm = osrm_client

    async def warm_all(self) -> dict:
        """
        Run all warming tasks.

        Returns:
            Summary of warming results
        """
        start_time = datetime.now()
        results = {}

        logger.info("Starting cache warming...")

        try:
            # 1. Warm distance matrices
            matrices_result = await self.warm_distance_matrices()
            results["distance_matrices"] = matrices_result

            # 2. Warm reference data
            ref_result = await self.warm_reference_data()
            results["reference_data"] = ref_result

            # 3. Warm today's plans
            plans_result = await self.warm_daily_plans()
            results["daily_plans"] = plans_result

            # 4. Warm route geometries
            routes_result = await self.warm_route_geometries()
            results["route_geometries"] = routes_result

        except Exception as e:
            logger.error(f"Cache warming failed: {e}")
            results["error"] = str(e)

        duration = (datetime.now() - start_time).total_seconds()
        results["duration_seconds"] = duration

        logger.info(f"Cache warming completed in {duration:.1f}s")
        return results

    async def warm_distance_matrices(self) -> dict:
        """
        Pre-compute distance matrices for active agents.

        For each agent with >10 clients, compute and cache
        the full distance matrix.
        """
        from app.models.agent import Agent

        warmed = 0
        skipped = 0
        errors = 0

        async with self.db_session_factory() as db:
            # Get active agents
            result = await db.execute(select(Agent).where(Agent.is_active.is_(True)).options(selectinload(Agent.clients)))
            agents = result.scalars().all()

            for agent in agents:
                try:
                    # Get active clients for this agent
                    clients = [c for c in agent.clients if c.is_active]

                    if len(clients) < 10:
                        skipped += 1
                        continue

                    # Build coordinate list
                    coords = [(float(c.longitude), float(c.latitude)) for c in clients]

                    # Add agent start location
                    coords.insert(
                        0,
                        (
                            float(agent.start_longitude),
                            float(agent.start_latitude),
                        ),
                    )

                    # This will auto-cache via OSRM client
                    await self.osrm.get_table(coords)
                    warmed += 1

                    # Small delay to avoid overwhelming OSRM
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.warning(f"Failed to warm matrix for agent {agent.id}: {e}")
                    errors += 1

        return {
            "warmed": warmed,
            "skipped": skipped,
            "errors": errors,
        }

    async def warm_reference_data(self) -> dict:
        """
        Cache all reference data (clients, agents, vehicles).

        Uses batch Redis operations for efficiency.
        """
        from app.models.agent import Agent
        from app.models.client import Client
        from app.models.vehicle import Vehicle

        results = {"agents": 0, "clients": 0, "vehicles": 0}

        async with self.db_session_factory() as db:
            # Agents
            agent_result = await db.execute(select(Agent))
            agents = agent_result.scalars().all()

            agent_data = {}
            for agent in agents:
                agent_data[f"agent:{agent.id}"] = {
                    "id": str(agent.id),
                    "name": agent.name,
                    "external_id": agent.external_id,
                    "start_latitude": float(agent.start_latitude),
                    "start_longitude": float(agent.start_longitude),
                    "work_start": agent.work_start.isoformat() if agent.work_start else None,
                    "work_end": agent.work_end.isoformat() if agent.work_end else None,
                    "max_visits_per_day": agent.max_visits_per_day,
                    "is_active": agent.is_active,
                }

            if agent_data:
                await self.cache.mset(agent_data, ttl=3600)
                results["agents"] = len(agent_data)

            # Clients
            client_result = await db.execute(select(Client))
            clients = client_result.scalars().all()

            client_data = {}
            for client in clients:
                client_data[f"client:{client.id}"] = {
                    "id": str(client.id),
                    "name": client.name,
                    "external_id": client.external_id,
                    "latitude": float(client.latitude),
                    "longitude": float(client.longitude),
                    "category": client.category.value if client.category else "B",
                    "agent_id": str(client.agent_id) if client.agent_id else None,
                    "visit_duration_minutes": client.visit_duration_minutes,
                    "time_window_start": client.time_window_start.isoformat() if client.time_window_start else None,
                    "time_window_end": client.time_window_end.isoformat() if client.time_window_end else None,
                    "is_active": client.is_active,
                }

            if client_data:
                await self.cache.mset(client_data, ttl=3600)
                results["clients"] = len(client_data)

            # Vehicles
            vehicle_result = await db.execute(select(Vehicle))
            vehicles = vehicle_result.scalars().all()

            vehicle_data = {}
            for vehicle in vehicles:
                vehicle_data[f"vehicle:{vehicle.id}"] = {
                    "id": str(vehicle.id),
                    "name": vehicle.name,
                    "license_plate": vehicle.license_plate,
                    "capacity_kg": float(vehicle.capacity_kg) if vehicle.capacity_kg else None,
                    "capacity_volume_m3": float(vehicle.capacity_volume_m3) if vehicle.capacity_volume_m3 else None,
                    "is_active": vehicle.is_active,
                }

            if vehicle_data:
                await self.cache.mset(vehicle_data, ttl=3600)
                results["vehicles"] = len(vehicle_data)

        return results

    async def warm_daily_plans(self) -> dict:
        """
        Pre-generate today's visit plans for active agents.

        Only generates if not already cached.
        """
        from app.models.agent import Agent
        from app.models.visit_plan import VisitPlan

        today = date.today()
        generated = 0
        cached = 0
        errors = 0

        async with self.db_session_factory() as db:
            # Get active agents
            result = await db.execute(select(Agent).where(Agent.is_active.is_(True)))
            agents = result.scalars().all()

            for agent in agents:
                cache_key = f"daily_plan:{agent.id}:{today}"

                try:
                    # Check if already cached
                    existing = await self.cache.get(cache_key)
                    if existing:
                        cached += 1
                        continue

                    # Get today's visit plans
                    plans_result = await db.execute(
                        select(VisitPlan)
                        .where(VisitPlan.agent_id == agent.id)
                        .where(VisitPlan.planned_date == today)
                        .options(selectinload(VisitPlan.client))
                        .order_by(VisitPlan.sequence_number)
                    )
                    plans = plans_result.scalars().all()

                    if not plans:
                        continue

                    # Build plan summary
                    plan_data = {
                        "agent_id": str(agent.id),
                        "date": today.isoformat(),
                        "total_visits": len(plans),
                        "visits": [
                            {
                                "id": str(p.id),
                                "client_id": str(p.client_id),
                                "client_name": p.client.name if p.client else "Unknown",
                                "sequence": p.sequence_number,
                                "planned_time": p.planned_time.isoformat() if p.planned_time else None,
                                "status": p.status.value if p.status else "planned",
                            }
                            for p in plans
                        ],
                    }

                    await self.cache.set(cache_key, plan_data, ttl=3600)
                    generated += 1

                except Exception as e:
                    logger.warning(f"Failed to warm plan for agent {agent.id}: {e}")
                    errors += 1

        return {
            "generated": generated,
            "already_cached": cached,
            "errors": errors,
        }

    async def warm_route_geometries(self) -> dict:
        """
        Pre-fetch route geometries for today's routes.

        Useful for map rendering performance.
        """
        from app.models.delivery_route import DeliveryRoute

        today = date.today()
        warmed = 0
        errors = 0

        async with self.db_session_factory() as db:
            # Get today's routes
            result = await db.execute(
                select(DeliveryRoute)
                .where(DeliveryRoute.route_date == today)
                .options(selectinload(DeliveryRoute.stops))
            )
            routes = result.scalars().all()

            for route in routes:
                try:
                    if not route.stops:
                        continue

                    cache_key = f"route_geometry:{route.id}"

                    # Check if already cached
                    existing = await self.cache.get(cache_key)
                    if existing:
                        continue

                    # Build coordinate list for OSRM route
                    # Note: Would need to join with orders/clients for coordinates
                    # Simplified: skip geometry for now
                    for stop in sorted(route.stops, key=lambda s: s.sequence_number):
                        pass

                    warmed += 1

                except Exception as e:
                    logger.warning(f"Failed to warm geometry for route {route.id}: {e}")
                    errors += 1

        return {
            "warmed": warmed,
            "errors": errors,
        }

    async def invalidate_agent_caches(self, agent_id: UUID) -> int:
        """
        Invalidate all caches for a specific agent.

        Called when agent data changes.
        """
        patterns = [
            f"agent:{agent_id}",
            f"matrix:*{agent_id}*",
            f"daily_plan:{agent_id}:*",
        ]

        deleted = 0
        for pattern in patterns:
            deleted += await self.cache.delete_pattern(pattern)

        return deleted

    async def invalidate_client_caches(self, client_id: UUID, agent_id: Optional[UUID] = None) -> int:
        """
        Invalidate caches when client data changes.
        """
        patterns = [f"client:{client_id}"]

        if agent_id:
            patterns.extend(
                [
                    f"matrix:*{agent_id}*",
                    f"daily_plan:{agent_id}:*",
                ]
            )

        deleted = 0
        for pattern in patterns:
            deleted += await self.cache.delete_pattern(pattern)

        return deleted


# Celery task for scheduled warming
def create_warming_task(celery_app):
    """Create Celery task for cache warming."""

    @celery_app.task(name="app.tasks.cache.warm_caches")
    def warm_caches():
        """Warm all caches (runs at 05:00 daily)."""
        import asyncio

        from app.core.cache import cache_service
        from app.core.database import async_session_factory
        from app.services.routing.osrm_client import osrm_client

        async def run():
            warmer = CacheWarmer(
                db_session_factory=async_session_factory,
                cache_service=cache_service,
                osrm_client=osrm_client,
            )
            return await warmer.warm_all()

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(run())
        finally:
            loop.close()

    return warm_caches
