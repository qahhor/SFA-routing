"""
Service layer tests.
"""
import pytest
from datetime import date, time
from decimal import Decimal
from uuid import uuid4

from app.models.agent import Agent
from app.models.client import Client, ClientCategory
from app.services.planning.weekly_planner import WeeklyPlanner


class TestWeeklyPlanner:
    """Tests for WeeklyPlanner service."""

    def test_calculate_required_visits_category_a(self):
        """Test visit calculation for category A clients."""
        planner = WeeklyPlanner()

        client = Client(
            id=uuid4(),
            external_id="test-001",
            name="Test Client",
            address="Test Address",
            latitude=Decimal("41.311081"),
            longitude=Decimal("69.279737"),
            category=ClientCategory.A,
        )

        visits = planner.calculate_required_visits([client], week_number=1)
        assert visits[client.id] == 2

    def test_calculate_required_visits_category_b(self):
        """Test visit calculation for category B clients."""
        planner = WeeklyPlanner()

        client = Client(
            id=uuid4(),
            external_id="test-001",
            name="Test Client",
            address="Test Address",
            latitude=Decimal("41.311081"),
            longitude=Decimal("69.279737"),
            category=ClientCategory.B,
        )

        visits = planner.calculate_required_visits([client], week_number=1)
        assert visits[client.id] == 1

    def test_calculate_required_visits_category_c(self):
        """Test visit calculation for category C clients."""
        planner = WeeklyPlanner()

        client = Client(
            id=uuid4(),
            external_id="test-001",
            name="Test Client",
            address="Test Address",
            latitude=Decimal("41.311081"),
            longitude=Decimal("69.279737"),
            category=ClientCategory.C,
        )

        # Week 1: should have visit
        visits_week1 = planner.calculate_required_visits([client], week_number=1)
        assert visits_week1[client.id] == 1

        # Week 2: should not have visit
        visits_week2 = planner.calculate_required_visits([client], week_number=2)
        assert visits_week2[client.id] == 0

    def test_cluster_by_geography(self):
        """Test geographic clustering."""
        planner = WeeklyPlanner()

        # Create clients in different locations
        clients = [
            Client(
                id=uuid4(),
                external_id=f"test-{i}",
                name=f"Client {i}",
                address="Test Address",
                latitude=Decimal(str(41.30 + i * 0.01)),
                longitude=Decimal(str(69.27 + i * 0.01)),
                category=ClientCategory.B,
            )
            for i in range(10)
        ]

        clusters = planner.cluster_by_geography(clients, n_clusters=3)
        assert len(clusters) == 3
        assert sum(len(c) for c in clusters.values()) == 10

    def test_assign_to_days(self):
        """Test day assignment."""
        planner = WeeklyPlanner()

        clients = [
            Client(
                id=uuid4(),
                external_id=f"test-{i}",
                name=f"Client {i}",
                address="Test Address",
                latitude=Decimal(str(41.30 + i * 0.01)),
                longitude=Decimal(str(69.27 + i * 0.01)),
                category=ClientCategory.B,
            )
            for i in range(25)
        ]

        visits_needed = {c.id: 1 for c in clients}
        assignments = planner.assign_to_days(
            clients, visits_needed, n_days=5, max_per_day=10
        )

        # Should have 5 days
        assert len(assignments) == 5

        # Each day should have <= 10 visits
        for day, day_clients in assignments.items():
            assert len(day_clients) <= 10

    def test_time_conversions(self):
        """Test time conversion methods."""
        planner = WeeklyPlanner()

        # Test time to seconds
        t = time(9, 30, 0)
        seconds = planner._time_to_seconds(t)
        assert seconds == 9 * 3600 + 30 * 60

        # Test seconds to time
        result = planner._seconds_to_time(seconds)
        assert result == t

    def test_add_minutes(self):
        """Test minute addition."""
        planner = WeeklyPlanner()

        t = time(9, 30, 0)
        result = planner._add_minutes(t, 45)
        assert result == time(10, 15, 0)

        # Test overflow to next hour
        t2 = time(23, 30, 0)
        result2 = planner._add_minutes(t2, 60)
        assert result2 == time(0, 30, 0)


class TestClientVisitsPerWeek:
    """Tests for client visit frequency property."""

    def test_category_a_visits_per_week(self):
        """Category A should have 2 visits per week."""
        client = Client(
            id=uuid4(),
            external_id="test-001",
            name="Test Client",
            address="Test Address",
            latitude=Decimal("41.311081"),
            longitude=Decimal("69.279737"),
            category=ClientCategory.A,
        )
        assert client.visits_per_week == 2.0

    def test_category_b_visits_per_week(self):
        """Category B should have 1 visit per week."""
        client = Client(
            id=uuid4(),
            external_id="test-001",
            name="Test Client",
            address="Test Address",
            latitude=Decimal("41.311081"),
            longitude=Decimal("69.279737"),
            category=ClientCategory.B,
        )
        assert client.visits_per_week == 1.0

    def test_category_c_visits_per_week(self):
        """Category C should have 0.5 visits per week."""
        client = Client(
            id=uuid4(),
            external_id="test-001",
            name="Test Client",
            address="Test Address",
            latitude=Decimal("41.311081"),
            longitude=Decimal("69.279737"),
            category=ClientCategory.C,
        )
        assert client.visits_per_week == 0.5
