"""
Weekly planning service for Sales Force Automation (SFA).

Central Asia specific features:
- Lunch break avoidance (13:00-14:00)
- Friday prayer consideration (Uzbekistan)
- Payday prioritization (5th, 20th)
- Summer early start (07:00)
- Visit prioritization based on FMCG factors
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

import numpy as np
from sklearn.cluster import KMeans

from app.models.agent import Agent
from app.models.client import Client, ClientCategory
from app.services.routing.osrm_client import OSRMClient, osrm_client
from app.services.solvers.solver_interface import (
    Break,
    Job,
    Location,
    RegionalConfig,
    RegionalConstraints,
    RoutingProblem,
    SolverFactory,
    SolverType,
    TransportMode,
    VehicleConfig,
)
from app.services.solvers.vroom_solver import VROOMSolver, vroom_solver


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
    # FMCG extensions
    priority_score: float = 0
    expected_order_value: float = 0
    is_during_lunch: bool = False
    client_category: str = "B"


@dataclass
class WeeklyPlan:
    """Complete weekly plan for an agent."""

    agent_id: uuid.UUID
    week_start: date
    daily_plans: list[DailyPlan]
    total_visits: int
    total_distance_km: float
    total_duration_minutes: int
    # KPIs
    workload_balance_score: float = 0  # 0-1, how balanced across days
    avg_visits_per_day: float = 0
    total_expected_value: float = 0
    coverage_rate: float = 0  # % of required visits scheduled

    def calculate_kpis(self) -> dict:
        """Calculate FMCG-specific KPIs."""
        visits_per_day = [len(dp.visits) for dp in self.daily_plans]
        active_days = [v for v in visits_per_day if v > 0]

        if not active_days:
            return {}

        self.avg_visits_per_day = sum(active_days) / len(active_days)

        # Workload balance (coefficient of variation)
        if len(active_days) > 1 and self.avg_visits_per_day > 0:
            import statistics

            std_dev = statistics.stdev(active_days)
            cv = std_dev / self.avg_visits_per_day
            self.workload_balance_score = max(0, 1 - cv)
        else:
            self.workload_balance_score = 1.0

        # Travel vs service ratio (target: 30/70)
        total_service_minutes = sum(sum(15 for _ in dp.visits) for dp in self.daily_plans)  # Assuming 15 min per visit
        total_time = self.total_duration_minutes
        if total_time > 0:
            travel_ratio = (total_time - total_service_minutes) / total_time
        else:
            travel_ratio = 0

        return {
            "total_visits": self.total_visits,
            "avg_visits_per_day": round(self.avg_visits_per_day, 1),
            "visits_per_day": visits_per_day,
            "workload_balance_score": round(self.workload_balance_score, 2),
            "total_distance_km": round(self.total_distance_km, 1),
            "total_duration_hours": round(self.total_duration_minutes / 60, 1),
            "km_per_visit": round(self.total_distance_km / self.total_visits, 2) if self.total_visits > 0 else 0,
            "travel_ratio": round(travel_ratio, 2),
            "active_days": len(active_days),
        }


class WeeklyPlanner:
    """
    Weekly planning algorithm for sales representatives.

    Logic:
    1. Get all clients for the agent
    2. Distribute across week days considering:
       - Client category (A=2/week, B=1/week, C=0.5/week)
       - Geographic clustering
       - Client time windows
       - Visit priority (stock levels, debt, promotions)
    3. Optimize daily route order (TSP via VROOM)

    Central Asia specifics:
    - Avoid lunch break (13:00-14:00)
    - Consider Friday prayer in Uzbekistan
    - Prioritize debt collection on payday (5th, 20th)
    - Summer early start at 07:00
    """

    def __init__(
        self,
        osrm: Optional[OSRMClient] = None,
        vroom: Optional[VROOMSolver] = None,
        region: RegionalConfig = RegionalConfig.UZBEKISTAN,
    ):
        self.osrm = osrm or osrm_client
        self.vroom = vroom or vroom_solver
        self.region = region
        self.constraints = self._get_regional_constraints()

    def _get_regional_constraints(self) -> RegionalConstraints:
        """Get constraints for the configured region."""
        if self.region == RegionalConfig.UZBEKISTAN:
            return RegionalConstraints.for_uzbekistan()
        elif self.region == RegionalConfig.KAZAKHSTAN:
            return RegionalConstraints.for_kazakhstan()
        return RegionalConstraints()

    def is_payday_period(self, check_date: date) -> bool:
        """Check if date is within payday period (±3 days)."""
        day = check_date.day
        for payday in self.constraints.payday_dates:
            if abs(day - payday) <= 3:
                return True
        return False

    def is_summer_period(self, check_date: date) -> bool:
        """Check if date is in summer (June-August)."""
        return check_date.month in [6, 7, 8]

    def get_adjusted_work_start(self, agent: Agent, route_date: date) -> time:
        """Get adjusted work start time based on season."""
        if self.is_summer_period(route_date) and self.constraints.summer_early_start:
            return time(7, 0)  # Early start in summer
        return agent.work_start

    def calculate_client_priority(
        self,
        client: Client,
        route_date: date,
        stock_levels: Optional[dict[uuid.UUID, int]] = None,
        debts: Optional[dict[uuid.UUID, float]] = None,
        active_promos: Optional[set[uuid.UUID]] = None,
    ) -> float:
        """
        Calculate visit priority score for a client.

        Args:
            client: Client to score
            route_date: Date of planned visit
            stock_levels: Dict of client_id -> days of stock remaining
            debts: Dict of client_id -> outstanding debt amount
            active_promos: Set of client IDs with active promotions

        Returns:
            Priority score 0-100 (higher = more urgent)
        """
        score = 0.0

        # Base priority by category
        if client.category == ClientCategory.A:
            score += 20
        elif client.category == ClientCategory.B:
            score += 10

        # Stock levels (critical = high priority)
        if stock_levels and client.id in stock_levels:
            days_remaining = stock_levels[client.id]
            if days_remaining < 3:
                score += 30  # Critical
            elif days_remaining < 7:
                score += 15  # Low

        # Debt collection on payday
        if debts and client.id in debts:
            debt_amount = debts[client.id]
            if debt_amount > 0:
                if self.is_payday_period(route_date):
                    score += 25  # High priority on payday
                else:
                    score += 10

        # Active promotions
        if active_promos and client.id in active_promos:
            score += 15

        return min(score, 100)

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

    async def cluster_by_geography(
        self,
        clients: list[Client],
        n_clusters: int = 5,
        use_osrm: bool = True,
    ) -> dict[int, list[Client]]:
        """
        Cluster clients by geographic proximity.

        Uses OSRM road distances for accurate clustering
        that considers actual road network, not just Euclidean distance.

        Args:
            clients: List of clients
            n_clusters: Number of clusters (days)
            use_osrm: Whether to use OSRM distances (slower but more accurate)

        Returns:
            Dict mapping cluster_id to list of clients
        """
        if len(clients) < n_clusters:
            return {0: clients}

        # Try OSRM-based hierarchical clustering
        if use_osrm:
            try:
                from app.services.clustering import clustering_service

                result = await clustering_service.cluster_hierarchical_osrm(
                    clients,
                    n_clusters=n_clusters,
                    use_cache=True,
                )

                # Map indices back to clients
                clusters: dict[int, list[Client]] = {}
                for cluster_id, indices in result.clusters.items():
                    clusters[cluster_id] = [clients[i] for i in indices]

                return clusters

            except Exception as e:
                # Log error and fallback to K-means
                print(f"OSRM clustering failed, falling back to K-means: {e}")

        # Fallback: K-means with Euclidean distance
        coords = np.array([[float(c.latitude), float(c.longitude)] for c in clients])

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(coords)

        # Group clients by cluster
        clusters: dict[int, list[Client]] = {}
        for client, label in zip(clients, labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(client)

        return clusters

    async def assign_to_days(
        self,
        clients: list[Client],
        visits_needed: dict[uuid.UUID, int],
        n_days: int = 5,
        max_per_day: int = 30,
    ) -> dict[int, list[Client]]:
        """
        Assign clients to specific days of the week.

        Strategy:
        1. Cluster clients geographically using OSRM distances
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
        # First, cluster geographically using OSRM
        clusters = await self.cluster_by_geography(clients, n_clusters=n_days)

        # Initialize daily assignments
        daily_assignments: dict[int, list[Client]] = {day: [] for day in range(n_days)}

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
                    min_day = min(range(n_days), key=lambda d: len(daily_assignments[d]))
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
                    d
                    for d in range(n_days)
                    if d != first_visit_day
                    and len(daily_assignments[d]) < max_per_day
                    and abs(d - first_visit_day) >= 2  # At least 2 days apart
                ]

                if second_day_candidates:
                    second_day = min(second_day_candidates, key=lambda d: len(daily_assignments[d]))
                    daily_assignments[second_day].append(client)

        return daily_assignments

    async def optimize_day_route(
        self,
        agent: Agent,
        clients: list[Client],
        route_date: date,
        client_priorities: Optional[dict[uuid.UUID, float]] = None,
    ) -> DailyPlan:
        """
        Optimize route for a single day using SolverFactory (defaulting to VROOM).

        Args:
            agent: Agent for the route
            clients: Clients to visit
            route_date: Date of the route
            client_priorities: Optional priority scores for clients

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

        # Get adjusted work hours
        work_start = self.get_adjusted_work_start(agent, route_date)
        is_friday = route_date.weekday() == 4

        # Define breaks
        breaks = []

        # Lunch break
        lunch_start_time = self.constraints.lunch_break_start
        lunch_end_time = self.constraints.lunch_break_end
        breaks.append(
            Break(
                id=1,
                start=lunch_start_time,
                end=lunch_end_time,
                description="Lunch Break",
                duration_minutes=60,  # Approximation if dates needed
            )
        )

        # Friday prayer (Uzbekistan)
        if is_friday and self.region == RegionalConfig.UZBEKISTAN:
            if self.constraints.friday_prayer_start:
                breaks.append(
                    Break(
                        id=2,
                        start=self.constraints.friday_prayer_start,
                        end=self.constraints.friday_prayer_end,
                        description="Friday Prayer",
                        duration_minutes=90,
                    )
                )

        # Build VehicleConfig
        start_loc = Location(
            id=uuid.uuid4(),
            name="Depot",
            latitude=float(agent.start_latitude),
            longitude=float(agent.start_longitude),
        )
        end_loc = None
        if agent.end_latitude and agent.end_longitude:
            end_loc = Location(
                id=uuid.uuid4(), name="End", latitude=float(agent.end_latitude), longitude=float(agent.end_longitude)
            )

        vehicle = VehicleConfig(
            id=agent.id,
            name=agent.name,
            capacity_kg=1000,  # Dummy capacity for sales agent
            start_location=start_loc,
            end_location=end_loc,
            work_start=work_start,
            work_end=agent.work_end,
            breaks=breaks,
        )

        # Build Jobs
        jobs = []
        clients_map = {c.id: c for c in clients}

        for idx, client in enumerate(clients):
            priority = 50
            if client_priorities:
                priority = int(client_priorities.get(client.id, 50))

            # Use client time window if available, else work hours
            # Note: We rely on Breaks to handle lunch exclusions
            tw_start = datetime.combine(route_date, client.time_window_start or work_start)
            tw_end = datetime.combine(route_date, client.time_window_end or agent.work_end)

            jobs.append(
                Job(
                    id=client.id,  # Use Client UUID as Job ID
                    location=Location(
                        id=uuid.uuid4(),
                        name=client.name,
                        latitude=float(client.latitude),
                        longitude=float(client.longitude),
                        service_time_minutes=client.visit_duration_minutes,
                    ),
                    priority=priority,
                    time_window_start=tw_start,
                    time_window_end=tw_end,
                )
            )

        # Create Problem
        problem = RoutingProblem(
            jobs=jobs,
            vehicles=[vehicle],
            planning_date=route_date,
            transport_mode=TransportMode.CAR,  # Agents drive
            regional_constraints=self.constraints,
        )

        # Solve
        try:
            solution = await SolverFactory.solve_with_fallback(problem, preferred=SolverType.VROOM)
        except Exception:
            # Fallback
            return self._create_fallback_plan(agent, clients, route_date)

        # Parse result
        visits = []
        if solution.routes:
            route = solution.routes[0]

            sequence = 0
            for step in route.steps:
                if step.step_type == "job" and step.job_id:  # job_id is client.id (UUID)
                    client = clients_map.get(step.job_id)
                    if not client:
                        continue

                    sequence += 1

                    # Check lunch overlap
                    arrival_time = step.arrival_time.time()
                    is_during_lunch = lunch_start_time <= arrival_time <= lunch_end_time

                    visits.append(
                        PlannedVisit(
                            client_id=client.id,
                            client_name=client.name,
                            sequence_number=sequence,
                            planned_time=arrival_time,
                            estimated_arrival=step.arrival_time.time(),
                            estimated_departure=step.departure_time.time(),
                            distance_from_previous_km=step.distance_from_previous_m / 1000,
                            duration_from_previous_minutes=int(step.duration_from_previous_s / 60),
                            latitude=float(client.latitude),
                            longitude=float(client.longitude),
                            priority_score=client_priorities.get(client.id, 0) if client_priorities else 0,
                            is_during_lunch=is_during_lunch,
                            client_category=(
                                client.category if isinstance(client.category, str) else client.category.value
                            ),
                        )
                    )

            return DailyPlan(
                date=route_date,
                visits=visits,
                total_distance_km=solution.total_distance_m / 1000,
                total_duration_minutes=int(solution.total_duration_s / 60),
                geometry={"encoded": route.geometry} if route.geometry else None,
            )

        return DailyPlan(
            date=route_date,
            visits=[],
            total_distance_km=0,
            total_duration_minutes=0,
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
            visits.append(
                PlannedVisit(
                    client_id=client.id,
                    client_name=client.name,
                    sequence_number=idx + 1,
                    planned_time=current_time,
                    estimated_arrival=current_time,
                    estimated_departure=self._add_minutes(current_time, client.visit_duration_minutes),
                    distance_from_previous_km=0,
                    duration_from_previous_minutes=0,
                    latitude=float(client.latitude),
                    longitude=float(client.longitude),
                )
            )
            current_time = self._add_minutes(current_time, client.visit_duration_minutes + 15)

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
        stock_levels: Optional[dict[uuid.UUID, int]] = None,
        debts: Optional[dict[uuid.UUID, float]] = None,
        active_promos: Optional[set[uuid.UUID]] = None,
    ) -> WeeklyPlan:
        """
        Generate complete weekly plan for an agent.

        Args:
            agent: Agent to plan for
            clients: Agent's assigned clients
            week_start: Monday of the planning week
            week_number: Week number in cycle (for C-class scheduling)
            stock_levels: Optional dict of client_id -> days of stock remaining
            debts: Optional dict of client_id -> outstanding debt amount
            active_promos: Optional set of client IDs with active promotions

        Returns:
            Complete WeeklyPlan with KPIs
        """
        # Calculate required visits
        visits_needed = self.calculate_required_visits(clients, week_number)

        # Filter to clients that need visits this week
        clients_to_visit = [c for c in clients if visits_needed.get(c.id, 0) > 0]

        # Calculate priority scores for all clients
        client_priorities: dict[uuid.UUID, float] = {}
        for client in clients_to_visit:
            # Use first day of week for priority calculation
            priority = self.calculate_client_priority(
                client,
                week_start,
                stock_levels,
                debts,
                active_promos,
            )
            client_priorities[client.id] = priority

        # Assign to days (prioritized clients first) using OSRM-based clustering
        daily_assignments = await self.assign_to_days(
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

            # Recalculate priorities for specific day (payday might differ)
            day_priorities = {
                c.id: self.calculate_client_priority(c, route_date, stock_levels, debts, active_promos)
                for c in day_clients
            }

            daily_plan = await self.optimize_day_route(agent, day_clients, route_date, day_priorities)
            daily_plans.append(daily_plan)

        # Calculate totals
        total_visits = sum(len(dp.visits) for dp in daily_plans)
        total_distance = sum(dp.total_distance_km for dp in daily_plans)
        total_duration = sum(dp.total_duration_minutes for dp in daily_plans)

        # Calculate coverage rate
        total_required = sum(visits_needed.values())
        coverage_rate = total_visits / total_required if total_required > 0 else 1.0

        plan = WeeklyPlan(
            agent_id=agent.id,
            week_start=week_start,
            daily_plans=daily_plans,
            total_visits=total_visits,
            total_distance_km=total_distance,
            total_duration_minutes=total_duration,
            coverage_rate=coverage_rate,
        )

        # Calculate KPIs
        plan.calculate_kpis()

        return plan


# Singleton instances for different regions
weekly_planner = WeeklyPlanner(region=RegionalConfig.UZBEKISTAN)
weekly_planner_uz = WeeklyPlanner(region=RegionalConfig.UZBEKISTAN)
weekly_planner_kz = WeeklyPlanner(region=RegionalConfig.KAZAKHSTAN)
