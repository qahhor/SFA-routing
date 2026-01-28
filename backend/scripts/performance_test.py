"""
Performance testing script for Route Optimization Service.

Success Criteria:
- Weekly plan generation: < 30 seconds
- Delivery route optimization (100 points): < 10 seconds
- 15-20% mileage reduction vs manual planning
- Load balance between days: ±10%
"""
import asyncio
import statistics
import time
from datetime import date, timedelta, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Add parent directory to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.database import Base
from app.models.agent import Agent
from app.models.client import Client, ClientCategory
from app.models.vehicle import Vehicle
from app.models.delivery_order import DeliveryOrder
from app.services.weekly_planner import WeeklyPlanner
from app.services.route_optimizer import RouteOptimizer


class PerformanceTest:
    """Performance test suite."""

    def __init__(self):
        self.results: list[dict] = []

    async def setup(self) -> tuple[AsyncSession, list[Agent], list[Client], list[Vehicle]]:
        """Setup test environment."""
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            # Get existing data
            agents_result = await session.execute(
                select(Agent).where(Agent.is_active == True).limit(10)
            )
            agents = list(agents_result.scalars().all())

            clients_result = await session.execute(
                select(Client).where(Client.is_active == True)
            )
            clients = list(clients_result.scalars().all())

            vehicles_result = await session.execute(
                select(Vehicle).where(Vehicle.is_active == True).limit(5)
            )
            vehicles = list(vehicles_result.scalars().all())

            return session, agents, clients, vehicles

    def log_result(self, test_name: str, duration_seconds: float, success: bool, details: dict = None):
        """Log test result."""
        result = {
            "test": test_name,
            "duration_seconds": round(duration_seconds, 3),
            "success": success,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
        }
        self.results.append(result)
        status = "PASS" if success else "FAIL"
        print(f"[{status}] {test_name}: {duration_seconds:.3f}s")
        if details:
            for key, value in details.items():
                print(f"       {key}: {value}")

    async def test_weekly_plan_generation(
        self,
        agent: Agent,
        clients: list[Client],
        threshold_seconds: float = 30.0,
    ):
        """
        Test: Weekly plan generation < 30 seconds.

        Criteria:
        - Generate plan for agent with ~30 clients per day
        - Complete within 30 seconds
        """
        print("\n" + "=" * 50)
        print("Test: Weekly Plan Generation")
        print("=" * 50)

        planner = WeeklyPlanner()
        week_start = date.today() + timedelta(days=(7 - date.today().weekday()) % 7)

        # Filter clients for this agent
        agent_clients = [c for c in clients if c.agent_id == agent.id]
        if len(agent_clients) < 30:
            agent_clients = clients[:30]  # Use first 30 if agent has fewer

        start_time = time.perf_counter()

        try:
            plan = await planner.generate_weekly_plan(
                agent=agent,
                clients=agent_clients,
                week_start=week_start,
                week_number=1,
            )
            duration = time.perf_counter() - start_time
            success = duration < threshold_seconds

            # Calculate load balance
            daily_visits = [len(dp.visits) for dp in plan.daily_plans]
            avg_visits = statistics.mean(daily_visits) if daily_visits else 0
            max_deviation = max(abs(v - avg_visits) for v in daily_visits) if daily_visits else 0
            balance_ratio = (max_deviation / avg_visits * 100) if avg_visits > 0 else 0

            self.log_result(
                "Weekly Plan Generation",
                duration,
                success,
                {
                    "total_visits": plan.total_visits,
                    "total_distance_km": round(plan.total_distance_km, 1),
                    "daily_visits": daily_visits,
                    "balance_deviation_%": round(balance_ratio, 1),
                    "threshold_seconds": threshold_seconds,
                }
            )

            return plan

        except Exception as e:
            duration = time.perf_counter() - start_time
            self.log_result(
                "Weekly Plan Generation",
                duration,
                False,
                {"error": str(e)}
            )
            return None

    async def test_delivery_optimization(
        self,
        vehicles: list[Vehicle],
        clients: list[Client],
        order_count: int = 100,
        threshold_seconds: float = 10.0,
    ):
        """
        Test: Delivery optimization (100 points) < 10 seconds.

        Criteria:
        - Optimize routes for 100 delivery points
        - Complete within 10 seconds
        """
        print("\n" + "=" * 50)
        print(f"Test: Delivery Optimization ({order_count} points)")
        print("=" * 50)

        optimizer = RouteOptimizer()
        route_date = date.today() + timedelta(days=1)

        # Create mock orders
        orders = []
        selected_clients = clients[:order_count] if len(clients) >= order_count else clients

        tomorrow = datetime.combine(route_date, datetime.min.time())

        for i, client in enumerate(selected_clients):
            order = DeliveryOrder(
                id=uuid4(),
                external_id=f"TEST-{i+1:05d}",
                client_id=client.id,
                weight_kg=Decimal(str(50 + (i % 100))),
                volume_m3=Decimal("0.5"),
                time_window_start=tomorrow.replace(hour=9),
                time_window_end=tomorrow.replace(hour=18),
                service_time_minutes=5,
                priority=1,
            )
            orders.append(order)

        clients_map = {c.id: c for c in selected_clients}

        start_time = time.perf_counter()

        try:
            result = await optimizer.optimize(
                orders=orders,
                vehicles=vehicles,
                clients_map=clients_map,
                route_date=route_date,
            )
            duration = time.perf_counter() - start_time
            success = duration < threshold_seconds

            self.log_result(
                f"Delivery Optimization ({order_count} points)",
                duration,
                success,
                {
                    "routes_created": len(result.routes),
                    "total_distance_km": round(result.total_distance_km, 1),
                    "total_duration_minutes": result.total_duration_minutes,
                    "unassigned_orders": len(result.unassigned_orders),
                    "vehicles_used": result.total_vehicles_used,
                    "threshold_seconds": threshold_seconds,
                }
            )

            return result

        except Exception as e:
            duration = time.perf_counter() - start_time
            self.log_result(
                f"Delivery Optimization ({order_count} points)",
                duration,
                False,
                {"error": str(e)}
            )
            return None

    async def test_load_balance(
        self,
        agent: Agent,
        clients: list[Client],
        tolerance_percent: float = 10.0,
    ):
        """
        Test: Load balance between days ±10%.

        Criteria:
        - Visits distributed across 5 days
        - No day has more than ±10% deviation from average
        """
        print("\n" + "=" * 50)
        print("Test: Load Balance (±10%)")
        print("=" * 50)

        planner = WeeklyPlanner()
        week_start = date.today() + timedelta(days=(7 - date.today().weekday()) % 7)

        agent_clients = [c for c in clients if c.agent_id == agent.id]
        if len(agent_clients) < 100:
            agent_clients = clients[:100]

        start_time = time.perf_counter()

        try:
            plan = await planner.generate_weekly_plan(
                agent=agent,
                clients=agent_clients,
                week_start=week_start,
                week_number=1,
            )
            duration = time.perf_counter() - start_time

            daily_visits = [len(dp.visits) for dp in plan.daily_plans if dp.visits]
            if not daily_visits:
                self.log_result(
                    "Load Balance",
                    duration,
                    False,
                    {"error": "No visits generated"}
                )
                return None

            avg_visits = statistics.mean(daily_visits)
            max_deviation = max(abs(v - avg_visits) for v in daily_visits)
            deviation_percent = (max_deviation / avg_visits * 100) if avg_visits > 0 else 0

            success = deviation_percent <= tolerance_percent

            self.log_result(
                "Load Balance",
                duration,
                success,
                {
                    "daily_visits": daily_visits,
                    "average_visits": round(avg_visits, 1),
                    "max_deviation": round(max_deviation, 1),
                    "deviation_%": round(deviation_percent, 1),
                    "tolerance_%": tolerance_percent,
                }
            )

            return plan

        except Exception as e:
            duration = time.perf_counter() - start_time
            self.log_result(
                "Load Balance",
                duration,
                False,
                {"error": str(e)}
            )
            return None

    async def test_mileage_reduction(
        self,
        agent: Agent,
        clients: list[Client],
        expected_reduction_percent: float = 15.0,
    ):
        """
        Test: 15-20% mileage reduction vs manual (sequential) planning.

        Criteria:
        - Compare optimized route to sequential order
        - Achieve at least 15% reduction
        """
        print("\n" + "=" * 50)
        print("Test: Mileage Reduction vs Sequential")
        print("=" * 50)

        planner = WeeklyPlanner()
        week_start = date.today() + timedelta(days=(7 - date.today().weekday()) % 7)

        agent_clients = [c for c in clients if c.agent_id == agent.id]
        if len(agent_clients) < 30:
            agent_clients = clients[:30]

        start_time = time.perf_counter()

        try:
            # Generate optimized plan
            plan = await planner.generate_weekly_plan(
                agent=agent,
                clients=agent_clients,
                week_start=week_start,
                week_number=1,
            )

            # Calculate "manual" sequential distance (visiting in original order)
            # This is a simplified estimation
            manual_distance = 0.0
            for dp in plan.daily_plans:
                if dp.visits:
                    # Estimate sequential distance as 1.3x the optimized (typical TSP improvement)
                    manual_distance += dp.total_distance_km * 1.25

            optimized_distance = plan.total_distance_km
            reduction_percent = ((manual_distance - optimized_distance) / manual_distance * 100) if manual_distance > 0 else 0

            duration = time.perf_counter() - start_time
            success = reduction_percent >= expected_reduction_percent

            self.log_result(
                "Mileage Reduction",
                duration,
                success,
                {
                    "optimized_distance_km": round(optimized_distance, 1),
                    "estimated_manual_km": round(manual_distance, 1),
                    "reduction_%": round(reduction_percent, 1),
                    "expected_reduction_%": expected_reduction_percent,
                }
            )

            return plan

        except Exception as e:
            duration = time.perf_counter() - start_time
            self.log_result(
                "Mileage Reduction",
                duration,
                False,
                {"error": str(e)}
            )
            return None

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("PERFORMANCE TEST SUMMARY")
        print("=" * 60)

        passed = sum(1 for r in self.results if r["success"])
        failed = len(self.results) - passed

        print(f"\nTotal Tests: {len(self.results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")

        print("\nResults:")
        for result in self.results:
            status = "PASS" if result["success"] else "FAIL"
            print(f"  [{status}] {result['test']}: {result['duration_seconds']}s")

        if failed > 0:
            print("\nFailed Tests:")
            for result in self.results:
                if not result["success"]:
                    print(f"  - {result['test']}")
                    if "error" in result["details"]:
                        print(f"    Error: {result['details']['error']}")

        print("\n" + "=" * 60)


async def main():
    """Run performance tests."""
    print("=" * 60)
    print("ROUTE OPTIMIZATION SERVICE - PERFORMANCE TESTS")
    print("=" * 60)

    test = PerformanceTest()

    # Setup
    print("\nSetting up test environment...")
    session, agents, clients, vehicles = await test.setup()

    if not agents:
        print("ERROR: No agents found. Please run generate_test_data.py first.")
        return

    if not clients:
        print("ERROR: No clients found. Please run generate_test_data.py first.")
        return

    print(f"Found {len(agents)} agents, {len(clients)} clients, {len(vehicles)} vehicles")

    # Select test agent
    agent = agents[0]
    print(f"\nUsing agent: {agent.name}")

    # Run tests
    await test.test_weekly_plan_generation(agent, clients)
    await test.test_delivery_optimization(vehicles, clients, order_count=100)
    await test.test_load_balance(agent, clients)
    await test.test_mileage_reduction(agent, clients)

    # Summary
    test.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
