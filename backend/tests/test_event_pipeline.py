"""
Tests for Event-Driven Rerouting Pipeline module.

Tests cover:
- EventType enum
- EventPriority enum
- RoutingEvent and subclasses (GPSEvent, TrafficEvent, OrderEvent)
- EventHandler ABC
- GPSDeviationHandler, TrafficHandler, OrderChangeHandler
- EventPipeline operations (submit, start, stop, process)
- create_event_pipeline factory
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.event_pipeline import (
    EventType,
    EventPriority,
    RoutingEvent,
    GPSEvent,
    TrafficEvent,
    OrderEvent,
    EventHandler,
    GPSDeviationHandler,
    TrafficHandler,
    OrderChangeHandler,
    EventPipeline,
    create_event_pipeline,
)


class TestEventType:
    """Tests for EventType enum."""

    def test_gps_events(self):
        """Test GPS event types exist."""
        assert EventType.GPS_UPDATE == "gps_update"
        assert EventType.GPS_DEVIATION == "gps_deviation"
        assert EventType.GPS_LOST == "gps_lost"

    def test_traffic_events(self):
        """Test traffic event types exist."""
        assert EventType.TRAFFIC_INCIDENT == "traffic_incident"
        assert EventType.TRAFFIC_CLEARED == "traffic_cleared"
        assert EventType.ROAD_CLOSURE == "road_closure"

    def test_order_events(self):
        """Test order event types exist."""
        assert EventType.ORDER_CANCELLED == "order_cancelled"
        assert EventType.ORDER_URGENT == "order_urgent"
        assert EventType.ORDER_ADDED == "order_added"
        assert EventType.ORDER_TIME_CHANGED == "order_time_changed"

    def test_agent_events(self):
        """Test agent event types exist."""
        assert EventType.AGENT_BREAK == "agent_break"
        assert EventType.AGENT_OFFLINE == "agent_offline"
        assert EventType.AGENT_AVAILABLE == "agent_available"

    def test_system_events(self):
        """Test system event types exist."""
        assert EventType.ROUTE_OPTIMIZED == "route_optimized"
        assert EventType.FEASIBILITY_CHECK == "feasibility_check"
        assert EventType.ALERT_GENERATED == "alert_generated"


class TestEventPriority:
    """Tests for EventPriority enum."""

    def test_priority_values(self):
        """Test priority values and ordering."""
        assert EventPriority.LOW.value == 1
        assert EventPriority.NORMAL.value == 5
        assert EventPriority.HIGH.value == 10
        assert EventPriority.CRITICAL.value == 20

    def test_priority_comparison(self):
        """Test priority comparison."""
        assert EventPriority.CRITICAL.value > EventPriority.HIGH.value
        assert EventPriority.HIGH.value > EventPriority.NORMAL.value
        assert EventPriority.NORMAL.value > EventPriority.LOW.value


class TestRoutingEvent:
    """Tests for RoutingEvent dataclass."""

    def test_creation_minimal(self):
        """Test minimal event creation."""
        event = RoutingEvent(event_type=EventType.GPS_UPDATE)

        assert event.event_type == EventType.GPS_UPDATE
        assert event.priority == EventPriority.NORMAL
        assert event.event_id is not None
        assert event.timestamp is not None
        assert event.data == {}
        assert event.processed is False

    def test_creation_full(self):
        """Test full event creation."""
        agent_id = uuid4()
        route_id = uuid4()
        order_id = uuid4()

        event = RoutingEvent(
            event_type=EventType.ORDER_CANCELLED,
            priority=EventPriority.HIGH,
            data={"reason": "customer request"},
            agent_id=agent_id,
            route_id=route_id,
            order_id=order_id,
        )

        assert event.event_type == EventType.ORDER_CANCELLED
        assert event.priority == EventPriority.HIGH
        assert event.agent_id == agent_id
        assert event.route_id == route_id
        assert event.order_id == order_id

    def test_processing_metadata(self):
        """Test processing metadata updates."""
        event = RoutingEvent(event_type=EventType.GPS_UPDATE)

        assert event.processed is False
        assert event.processing_time_ms == 0
        assert event.action_taken is None

        event.processed = True
        event.processing_time_ms = 15.5
        event.action_taken = "rerouted"

        assert event.processed is True
        assert event.processing_time_ms == 15.5
        assert event.action_taken == "rerouted"


class TestGPSEvent:
    """Tests for GPSEvent dataclass."""

    def test_creation(self):
        """Test GPS event creation."""
        agent_id = uuid4()

        event = GPSEvent(
            event_type=EventType.GPS_UPDATE,
            agent_id=agent_id,
            latitude=41.311,
            longitude=69.279,
            accuracy_meters=5.0,
            speed_kmh=30.0,
            heading=90.0,
        )

        assert event.event_type == EventType.GPS_UPDATE
        assert event.latitude == 41.311
        assert event.longitude == 69.279
        assert event.accuracy_meters == 5.0
        assert event.speed_kmh == 30.0
        assert event.heading == 90.0

    def test_data_populated(self):
        """Test GPS event data is populated."""
        event = GPSEvent(
            event_type=EventType.GPS_UPDATE,
            latitude=41.311,
            longitude=69.279,
            accuracy_meters=5.0,
            speed_kmh=30.0,
            heading=90.0,
        )

        assert event.data["latitude"] == 41.311
        assert event.data["longitude"] == 69.279
        assert event.data["accuracy"] == 5.0
        assert event.data["speed"] == 30.0
        assert event.data["heading"] == 90.0


class TestTrafficEvent:
    """Tests for TrafficEvent dataclass."""

    def test_creation(self):
        """Test traffic event creation."""
        event = TrafficEvent(
            event_type=EventType.TRAFFIC_INCIDENT,
            incident_type="accident",
            road_segment_id="seg_123",
            delay_minutes=30,
            affected_area_km=2.5,
        )

        assert event.event_type == EventType.TRAFFIC_INCIDENT
        assert event.priority == EventPriority.HIGH  # Auto-set
        assert event.incident_type == "accident"
        assert event.delay_minutes == 30

    def test_data_populated(self):
        """Test traffic event data is populated."""
        event = TrafficEvent(
            event_type=EventType.TRAFFIC_INCIDENT,
            incident_type="construction",
            road_segment_id="seg_456",
            delay_minutes=15,
            affected_area_km=1.0,
        )

        assert event.data["incident_type"] == "construction"
        assert event.data["road_segment"] == "seg_456"
        assert event.data["delay_minutes"] == 15
        assert event.data["affected_area_km"] == 1.0


class TestOrderEvent:
    """Tests for OrderEvent dataclass."""

    def test_cancelled_event(self):
        """Test cancelled order event."""
        event = OrderEvent(
            event_type=EventType.ORDER_CANCELLED,
            order_id=uuid4(),
            change_type="cancelled",
        )

        assert event.event_type == EventType.ORDER_CANCELLED

    def test_urgent_event_high_priority(self):
        """Test urgent order gets high priority."""
        event = OrderEvent(
            event_type=EventType.ORDER_URGENT,
            order_id=uuid4(),
            change_type="urgent",
        )

        assert event.event_type == EventType.ORDER_URGENT
        assert event.priority == EventPriority.HIGH


class TestGPSDeviationHandler:
    """Tests for GPSDeviationHandler class."""

    @pytest.fixture
    def mock_rerouting(self):
        """Create mock rerouting service."""
        service = MagicMock()
        service.reroute_agent_visits = AsyncMock()
        return service

    @pytest.fixture
    def mock_websocket(self):
        """Create mock websocket manager."""
        manager = MagicMock()
        manager.broadcast = AsyncMock()
        return manager

    @pytest.fixture
    def handler(self, mock_rerouting, mock_websocket):
        """Create handler instance."""
        return GPSDeviationHandler(mock_rerouting, mock_websocket)

    @pytest.mark.asyncio
    async def test_can_handle_gps_update(self, handler):
        """Test handler accepts GPS_UPDATE events."""
        event = RoutingEvent(event_type=EventType.GPS_UPDATE)
        assert await handler.can_handle(event) is True

    @pytest.mark.asyncio
    async def test_cannot_handle_other_events(self, handler):
        """Test handler rejects non-GPS events."""
        event = RoutingEvent(event_type=EventType.ORDER_CANCELLED)
        assert await handler.can_handle(event) is False

    @pytest.mark.asyncio
    async def test_handle_no_agent(self, handler):
        """Test handling event without agent_id."""
        event = GPSEvent(
            event_type=EventType.GPS_UPDATE,
            latitude=41.311,
            longitude=69.279,
        )

        result = await handler.handle(event)

        assert result is None

    @pytest.mark.asyncio
    async def test_handle_no_deviation(self, handler):
        """Test handling event with no deviation."""
        event = GPSEvent(
            event_type=EventType.GPS_UPDATE,
            agent_id=uuid4(),
            latitude=41.311,
            longitude=69.279,
        )

        result = await handler.handle(event)

        # No deviation detected (simplified implementation returns 0)
        assert result is None


class TestTrafficHandler:
    """Tests for TrafficHandler class."""

    @pytest.fixture
    def mock_rerouting(self):
        """Create mock rerouting service."""
        service = MagicMock()
        service.reroute_agent_visits = AsyncMock()
        return service

    @pytest.fixture
    def mock_spatial_index(self):
        """Create mock spatial index."""
        return MagicMock()

    @pytest.fixture
    def mock_websocket(self):
        """Create mock websocket manager."""
        manager = MagicMock()
        manager.broadcast = AsyncMock()
        return manager

    @pytest.fixture
    def handler(self, mock_rerouting, mock_spatial_index, mock_websocket):
        """Create handler instance."""
        return TrafficHandler(mock_rerouting, mock_spatial_index, mock_websocket)

    @pytest.mark.asyncio
    async def test_can_handle_traffic_incident(self, handler):
        """Test handler accepts TRAFFIC_INCIDENT events."""
        event = RoutingEvent(event_type=EventType.TRAFFIC_INCIDENT)
        assert await handler.can_handle(event) is True

    @pytest.mark.asyncio
    async def test_can_handle_road_closure(self, handler):
        """Test handler accepts ROAD_CLOSURE events."""
        event = RoutingEvent(event_type=EventType.ROAD_CLOSURE)
        assert await handler.can_handle(event) is True

    @pytest.mark.asyncio
    async def test_cannot_handle_other_events(self, handler):
        """Test handler rejects non-traffic events."""
        event = RoutingEvent(event_type=EventType.GPS_UPDATE)
        assert await handler.can_handle(event) is False

    @pytest.mark.asyncio
    async def test_handle_no_affected_agents(self, handler):
        """Test handling with no affected agents."""
        event = TrafficEvent(
            event_type=EventType.TRAFFIC_INCIDENT,
            incident_type="accident",
            delay_minutes=30,
        )

        result = await handler.handle(event)

        # No affected agents found (simplified implementation)
        assert result is None


class TestOrderChangeHandler:
    """Tests for OrderChangeHandler class."""

    @pytest.fixture
    def mock_rerouting(self):
        """Create mock rerouting service."""
        service = MagicMock()
        service.remove_and_reoptimize = AsyncMock()
        service.prioritize_order = AsyncMock()
        service.insert_order = AsyncMock()
        return service

    @pytest.fixture
    def mock_websocket(self):
        """Create mock websocket manager."""
        manager = MagicMock()
        manager.broadcast = AsyncMock()
        return manager

    @pytest.fixture
    def handler(self, mock_rerouting, mock_websocket):
        """Create handler instance."""
        return OrderChangeHandler(mock_rerouting, mock_websocket)

    @pytest.mark.asyncio
    async def test_can_handle_order_events(self, handler):
        """Test handler accepts order events."""
        for event_type in [
            EventType.ORDER_CANCELLED,
            EventType.ORDER_URGENT,
            EventType.ORDER_ADDED,
            EventType.ORDER_TIME_CHANGED,
        ]:
            event = RoutingEvent(event_type=event_type)
            assert await handler.can_handle(event) is True

    @pytest.mark.asyncio
    async def test_cannot_handle_other_events(self, handler):
        """Test handler rejects non-order events."""
        event = RoutingEvent(event_type=EventType.GPS_UPDATE)
        assert await handler.can_handle(event) is False

    @pytest.mark.asyncio
    async def test_handle_no_agent(self, handler):
        """Test handling event without agent_id."""
        event = RoutingEvent(
            event_type=EventType.ORDER_CANCELLED,
            order_id=uuid4(),
        )

        result = await handler.handle(event)

        assert result is None

    @pytest.mark.asyncio
    async def test_handle_order_cancelled(self, handler, mock_rerouting, mock_websocket):
        """Test handling cancelled order."""
        event = RoutingEvent(
            event_type=EventType.ORDER_CANCELLED,
            agent_id=uuid4(),
            order_id=uuid4(),
        )

        await handler.handle(event)

        mock_rerouting.remove_and_reoptimize.assert_called_once()
        mock_websocket.broadcast.assert_called()
        assert event.action_taken == "removed_and_reoptimized"

    @pytest.mark.asyncio
    async def test_handle_order_urgent(self, handler, mock_rerouting, mock_websocket):
        """Test handling urgent order."""
        event = RoutingEvent(
            event_type=EventType.ORDER_URGENT,
            agent_id=uuid4(),
            order_id=uuid4(),
        )

        await handler.handle(event)

        mock_rerouting.prioritize_order.assert_called_once()
        assert event.action_taken == "prioritized"

    @pytest.mark.asyncio
    async def test_handle_order_added(self, handler, mock_rerouting, mock_websocket):
        """Test handling added order."""
        event = RoutingEvent(
            event_type=EventType.ORDER_ADDED,
            agent_id=uuid4(),
            order_id=uuid4(),
        )

        await handler.handle(event)

        mock_rerouting.insert_order.assert_called_once()
        assert event.action_taken == "inserted"


class TestEventPipeline:
    """Tests for EventPipeline class."""

    @pytest.fixture
    def pipeline(self):
        """Create pipeline instance."""
        return EventPipeline(max_queue_size=100, max_concurrent=2)

    def test_initialization(self, pipeline):
        """Test pipeline initialization."""
        assert len(pipeline.handlers) == 0
        assert pipeline.max_concurrent == 2
        assert pipeline._running is False
        assert pipeline.events_processed == 0
        assert pipeline.events_dropped == 0

    def test_register_handler(self, pipeline):
        """Test handler registration."""
        mock_handler = MagicMock(spec=EventHandler)

        pipeline.register_handler(mock_handler)

        assert len(pipeline.handlers) == 1
        assert pipeline.handlers[0] == mock_handler

    @pytest.mark.asyncio
    async def test_submit_event(self, pipeline):
        """Test event submission."""
        event = RoutingEvent(event_type=EventType.GPS_UPDATE)

        result = await pipeline.submit(event)

        assert result is True
        assert pipeline.queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_submit_event_queue_full(self, pipeline):
        """Test event submission when queue is full."""
        small_pipeline = EventPipeline(max_queue_size=2)

        # Fill queue
        for _ in range(2):
            event = RoutingEvent(event_type=EventType.GPS_UPDATE)
            await small_pipeline.submit(event)

        # Next should fail
        event = RoutingEvent(event_type=EventType.GPS_UPDATE)
        result = await small_pipeline.submit(event)

        assert result is False
        assert small_pipeline.events_dropped == 1

    @pytest.mark.asyncio
    async def test_submit_priority_ordering(self, pipeline):
        """Test events are ordered by priority."""
        low_event = RoutingEvent(
            event_type=EventType.GPS_UPDATE,
            priority=EventPriority.LOW,
        )
        high_event = RoutingEvent(
            event_type=EventType.ORDER_URGENT,
            priority=EventPriority.HIGH,
        )

        await pipeline.submit(low_event)
        await pipeline.submit(high_event)

        # Higher priority should come out first
        priority1, _, event1 = await pipeline.queue.get()
        priority2, _, event2 = await pipeline.queue.get()

        assert event1.priority == EventPriority.HIGH
        assert event2.priority == EventPriority.LOW

    @pytest.mark.asyncio
    async def test_start_stop(self, pipeline):
        """Test starting and stopping pipeline."""
        await pipeline.start()

        assert pipeline._running is True
        assert len(pipeline._workers) == pipeline.max_concurrent

        await pipeline.stop()

        assert pipeline._running is False
        assert len(pipeline._workers) == 0

    @pytest.mark.asyncio
    async def test_process_event_with_handler(self, pipeline):
        """Test event processing through handler."""
        mock_handler = MagicMock(spec=EventHandler)
        mock_handler.can_handle = AsyncMock(return_value=True)
        mock_handler.handle = AsyncMock(return_value=None)

        pipeline.register_handler(mock_handler)

        event = RoutingEvent(event_type=EventType.GPS_UPDATE)
        await pipeline._process_event(event)

        mock_handler.can_handle.assert_called_once_with(event)
        mock_handler.handle.assert_called_once_with(event)
        assert event.processed is True

    @pytest.mark.asyncio
    async def test_process_event_follow_up(self, pipeline):
        """Test follow-up event submission."""
        follow_up = RoutingEvent(event_type=EventType.ROUTE_OPTIMIZED)

        mock_handler = MagicMock(spec=EventHandler)
        mock_handler.can_handle = AsyncMock(return_value=True)
        mock_handler.handle = AsyncMock(return_value=follow_up)

        pipeline.register_handler(mock_handler)

        event = RoutingEvent(event_type=EventType.GPS_UPDATE)
        await pipeline._process_event(event)

        # Follow-up should be in queue
        assert pipeline.queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_process_event_updates_metrics(self, pipeline):
        """Test metrics are updated after processing."""
        mock_handler = MagicMock(spec=EventHandler)
        mock_handler.can_handle = AsyncMock(return_value=True)
        mock_handler.handle = AsyncMock(return_value=None)

        pipeline.register_handler(mock_handler)

        event = RoutingEvent(event_type=EventType.GPS_UPDATE)
        await pipeline._process_event(event)

        assert pipeline.events_processed == 1
        assert event.processing_time_ms > 0

    def test_get_metrics(self, pipeline):
        """Test metrics retrieval."""
        metrics = pipeline.get_metrics()

        assert "events_processed" in metrics
        assert "events_dropped" in metrics
        assert "queue_size" in metrics
        assert "avg_processing_time_ms" in metrics
        assert "handlers_count" in metrics
        assert "workers_count" in metrics
        assert "running" in metrics


class TestCreateEventPipeline:
    """Tests for create_event_pipeline factory function."""

    def test_creates_pipeline_with_handlers(self):
        """Test factory creates pipeline with all handlers."""
        mock_rerouting = MagicMock()
        mock_websocket = MagicMock()
        mock_spatial_index = MagicMock()

        pipeline = create_event_pipeline(
            rerouting_service=mock_rerouting,
            websocket_manager=mock_websocket,
            spatial_index=mock_spatial_index,
        )

        assert isinstance(pipeline, EventPipeline)
        assert len(pipeline.handlers) == 3

    def test_creates_pipeline_without_spatial_index(self):
        """Test factory works without spatial index."""
        mock_rerouting = MagicMock()
        mock_websocket = MagicMock()

        pipeline = create_event_pipeline(
            rerouting_service=mock_rerouting,
            websocket_manager=mock_websocket,
        )

        assert isinstance(pipeline, EventPipeline)
        assert len(pipeline.handlers) == 3


class TestEventPipelineIntegration:
    """Integration tests for event pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_cycle(self):
        """Test complete event processing cycle."""
        pipeline = EventPipeline(max_queue_size=10, max_concurrent=2)

        # Track processed events
        processed_events = []

        class TestHandler(EventHandler):
            async def can_handle(self, event):
                return True

            async def handle(self, event):
                processed_events.append(event)
                return None

        pipeline.register_handler(TestHandler())

        # Start pipeline
        await pipeline.start()

        # Submit events
        events = [
            RoutingEvent(event_type=EventType.GPS_UPDATE)
            for _ in range(5)
        ]
        for event in events:
            await pipeline.submit(event)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Stop pipeline
        await pipeline.stop()

        assert len(processed_events) == 5
        assert pipeline.events_processed == 5
