"""
Weekly planning service for Sales Force Automation (SFA).
"""
import uuid
from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Optional

import numpy as np
from sklearn.cluster import KMeans

from app.core.config import settings
from app.models.agent import Agent
from app.models.client import Client, ClientCategory
from app.models.visit_plan import VisitPlan, VisitStatus
from app.services.osrm_client import OSRMClient, osrm_client
from app.services.vroom_solver import VROOMSolver, vroom_solver


@dataclass
class DailyPlan:
    """Plan for a single day."""
    date: date
    visits: list["PlannedVisit"]
    total_distance_km: float
    total_duration_minutes: int
    geometry: Optional[dict] = None


@dataclass
class PlannedVisit:
    """Planned visit to a client."""
    client_id: uuid.UUID
    client_name: str
    sequence_number: int
    planned_time: time
    estimated_arrival: time
    estimated_departure: time
    distance_from_previous_km: float
    duration_from_previous_minutes: int
    latitude: float
    longitude: float


@dataclass
class WeeklyPlan:
    """Complete weekly plan for an agent."""
    agent_id: uuid.UUID
    week_start: date
    daily_plans: list[DailyPlan]
    total_visits: int
    total_distance_km: float
    total_duration_minutes: int


class WeeklyPlanner:
    """
    Weekly planning algorithm for sales representatives.

    Logic:
    1. Get all clients for the agent
    2. Distribute across week days considering:
       - Client category (A=2/week, B=1/week, C=0.5/week)
       - Geographic clustering
       - Client time windows
    3. Optimize daily route order (TSP via VROOM)
    """

    def __init__(
        self,
        osrm: Optional[OSRMClient] = None,
        vroom: Optional[VROOMSolver] = None,
    ):
        self.osrm = osrm or osrm_client
        self.vroom = vroom or vroom_solver

    def calculate_required_visits(
        self,
        clients: list[Client],
        week_number: int = 1,
    ) -> dict[uuid.UUID, int]:
        """
        Calculate required visits for each client this week.

        Args:
            clients: List of clients
            week_number: Week number in the planning cycle (1 or 2)

        Returns:
            Dict mapping client_id to number of visits needed
        """
        visits_needed = {}

        for client in clients:
            if client.category == ClientCategory.A:
                visits_needed[client.id] = 2
            elif client.category == ClientCategory.B:
                visits_needed[client.id] = 1
            elif client.category == ClientCategory.C:
                # C-class: visit every other week
                visits_needed[client.id] = 1 if week_number % 2 == 1 else 0

        return visits_needed

    def cluster_by_geography(
        self,
        clients: list[Client],
        n_clusters: int = 5,
    ) -> dict[int, list[Client]]:
        """
        Cluster clients by geographic proximity.

        Args:
            clients: List of clients
            n_clusters: Number of clusters (days)

        Returns:
            Dict mapping cluster_id to list of clients
        """
        if len(clients) < n_clusters:
            return {0: clients}

        # Prepare coordinates
        coords = np.array([
            [float(c.latitude), float(c.longitude)]
            for c in clients
        ])

        # K-means clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(coords)

        # Group clients by cluster
        clusters: dict[int, list[Client]] = {}
        for client, label in zip(clients, labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(client)

        return clusters

    def assign_to_days(
        self,
        clients: list[Client],
        visits_needed: dict[uuid.UUID, int],
        n_days: int = 5,
        max_per_day: int = 30,
    ) -> dict[int, list[Client]]:
        """
        Assign clients to specific days of the week.

        Strategy:
        1. Cluster clients geographically
        2. Assign clusters to days
        3. Handle A-class clients (2 visits) by splitting across days
        4. Balance load across days

        Args:
            clients: List of clients
            visits_needed: Dict of client_id -> visits count
            n_days: Number of working days
            max_per_day: Maximum visits per day

        Returns:
            Dict mapping day_index (0-4) to list of clients
        """
        # First, cluster geographically
        clusters = self.cluster_by_geography(clients, n_clusters=n_days)

        # Initialize daily assignments
        daily_assignments: dict[int, list[Client]] = {
            day: [] for day in range(n_days)
        }

        # Track A-class clients for second visit
        a_class_clients = [c for c in clients if c.category == ClientCategory.A]

        # Assign clusters to days
        for cluster_id, cluster_clients in clusters.items():
            day = cluster_id % n_days

            for client in cluster_clients:
                if len(daily_assignments[day]) < max_per_day:
                    daily_assignments[day].append(client)
                else:
                    # Find day with least visits
                    min_day = min(
                        range(n_days),
                        key=lambda d: len(daily_assignments[d])
                    )
                    daily_assignments[min_day].append(client)

        # Add second visits for A-class clients on different days
        for client in a_class_clients:
            # Find the day where first visit was assigned
            first_visit_day = None
            for day, clients_list in daily_assignments.items():
                if client in clients_list:
                    first_visit_day = day
                    break

            if first_visit_day is not None:
                # Find a different day with capacity
                second_day_candidates = [
                    d for d in range(n_days)
                    if d != first_visit_day
                    and len(daily_assignments[d]) < max_per_day
                    and abs(d - first_visit_day) >= 2  # At least 2 days apart
                ]

                if second_day_candidates:
                    second_day = min(
                        second_day_candidates,
                        key=lambda d: len(daily_assignments[d])
                    )
                    daily_assignments[second_day].append(client)

        return daily_assignments

    async def optimize_day_route(
        self,
        agent: Agent,
        clients: list[Client],
        route_date: date,
    ) -> DailyPlan:
        """
        Optimize route for a single day using VROOM.

        Args:
            agent: Agent for the route
            clients: Clients to visit
            route_date: Date of the route

        Returns:
            Optimized DailyPlan
        """
        if not clients:
            return DailyPlan(
                date=route_date,
                visits=[],
                total_distance_km=0,
                total_duration_minutes=0,
            )

        # Prepare VROOM request
        request_data = {
            "vehicles": [{
                "id": 0,
                "start": [float(agent.start_longitude), float(agent.start_latitude)],
                "end": [float(agent.end_longitude or agent.start_longitude),
                        float(agent.end_latitude or agent.start_latitude)],
                "time_window": [
                    self._time_to_seconds(agent.work_start),
                    self._time_to_seconds(agent.work_end),
                ],
            }],
            "jobs": [
                {
                    "id": idx,
                    "location": [float(client.longitude), float(client.latitude)],
                    "service": client.visit_duration_minutes * 60,
                    "time_windows": [[
                        self._time_to_seconds(client.time_window_start),
                        self._time_to_seconds(client.time_window_end),
                    ]],
                }
                for idx, client in enumerate(clients)
            ],
            "options": {"g": True},
        }

        try:
            result = await self.vroom.solve_raw(request_data)
        except Exception as e:
            # Fallback: return clients in original order
            return self._create_fallback_plan(agent, clients, route_date)

        # Parse result
        visits = []
        total_distance_km = 0
        total_duration_minutes = 0

        if result.get("routes"):
            route = result["routes"][0]
            total_distance_km = route.get("distance", 0) / 1000
            total_duration_minutes = route.get("duration", 0) // 60

            current_time = agent.work_start
            sequence = 0

            for step in route.get("steps", []):
                if step["type"] == "job":
                    job_idx = step["job"]
                    client = clients[job_idx]
                    sequence += 1

                    arrival_seconds = step.get("arrival", 0)
                    duration_from_prev = step.get("duration", 0)
                    distance_from_prev = step.get("distance", 0)

                    arrival_time = self._seconds_to_time(arrival_seconds)
                    departure_time = self._seconds_to_time(
                        arrival_seconds + client.visit_duration_minutes * 60
                    )

                    visits.append(PlannedVisit(
                        client_id=client.id,
                        client_name=client.name,
                        sequence_number=sequence,
                        planned_time=arrival_time,
                        estimated_arrival=arrival_time,
                        estimated_departure=departure_time,
                        distance_from_previous_km=distance_from_prev / 1000,
                        duration_from_previous_minutes=duration_from_prev // 60,
                        latitude=float(client.latitude),
                        longitude=float(client.longitude),
                    ))

        return DailyPlan(
            date=route_date,
            visits=visits,
            total_distance_km=total_distance_km,
            total_duration_minutes=total_duration_minutes,
            geometry=result.get("routes", [{}])[0].get("geometry"),
        )

    def _time_to_seconds(self, t: time) -> int:
        """Convert time to seconds since midnight."""
        return t.hour * 3600 + t.minute * 60 + t.second

    def _seconds_to_time(self, seconds: int) -> time:
        """Convert seconds since midnight to time."""
        seconds = seconds % 86400  # Handle overflow
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return time(hour=hours, minute=minutes, second=secs)

    def _create_fallback_plan(
        self,
        agent: Agent,
        clients: list[Client],
        route_date: date,
    ) -> DailyPlan:
        """Create fallback plan when optimization fails."""
        visits = []
        current_time = agent.work_start

        for idx, client in enumerate(clients):
            visits.append(PlannedVisit(
                client_id=client.id,
                client_name=client.name,
                sequence_number=idx + 1,
                planned_time=current_time,
                estimated_arrival=current_time,
                estimated_departure=self._add_minutes(
                    current_time, client.visit_duration_minutes
                ),
                distance_from_previous_km=0,
                duration_from_previous_minutes=0,
                latitude=float(client.latitude),
                longitude=float(client.longitude),
            ))
            current_time = self._add_minutes(
                current_time, client.visit_duration_minutes + 15
            )

        return DailyPlan(
            date=route_date,
            visits=visits,
            total_distance_km=0,
            total_duration_minutes=0,
        )

    def _add_minutes(self, t: time, minutes: int) -> time:
        """Add minutes to a time object."""
        total_minutes = t.hour * 60 + t.minute + minutes
        hours = (total_minutes // 60) % 24
        mins = total_minutes % 60
        return time(hour=hours, minute=mins)

    async def generate_weekly_plan(
        self,
        agent: Agent,
        clients: list[Client],
        week_start: date,
        week_number: int = 1,
    ) -> WeeklyPlan:
        """
        Generate complete weekly plan for an agent.

        Args:
            agent: Agent to plan for
            clients: Agent's assigned clients
            week_start: Monday of the planning week
            week_number: Week number in cycle (for C-class scheduling)

        Returns:
            Complete WeeklyPlan
        """
        # Calculate required visits
        visits_needed = self.calculate_required_visits(clients, week_number)

        # Filter to clients that need visits this week
        clients_to_visit = [c for c in clients if visits_needed.get(c.id, 0) > 0]

        # Assign to days
        daily_assignments = self.assign_to_days(
            clients_to_visit,
            visits_needed,
            n_days=5,
            max_per_day=agent.max_visits_per_day,
        )

        # Optimize each day
        daily_plans = []
        for day_offset in range(5):
            route_date = week_start + timedelta(days=day_offset)
            day_clients = daily_assignments.get(day_offset, [])

            daily_plan = await self.optimize_day_route(
                agent, day_clients, route_date
            )
            daily_plans.append(daily_plan)

        # Calculate totals
        total_visits = sum(len(dp.visits) for dp in daily_plans)
        total_distance = sum(dp.total_distance_km for dp in daily_plans)
        total_duration = sum(dp.total_duration_minutes for dp in daily_plans)

        return WeeklyPlan(
            agent_id=agent.id,
            week_start=week_start,
            daily_plans=daily_plans,
            total_visits=total_visits,
            total_distance_km=total_distance,
            total_duration_minutes=total_duration,
        )


# Singleton instance
weekly_planner = WeeklyPlanner()
