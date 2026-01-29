"""
Event-Driven Rerouting Pipeline (R16).

Stream processing for real-time route adaptation.
Handles GPS updates, traffic incidents, and dynamic order changes.

Events flow:
1. Event received (GPS, traffic, order)
2. Impact analysis
3. Decision (ignore, alert, reroute)
4. Action execution
5. Notification broadcast
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of routing events."""

    # GPS events
    GPS_UPDATE = "gps_update"
    GPS_DEVIATION = "gps_deviation"
    GPS_LOST = "gps_lost"

    # Traffic events
    TRAFFIC_INCIDENT = "traffic_incident"
    TRAFFIC_CLEARED = "traffic_cleared"
    ROAD_CLOSURE = "road_closure"

    # Order events
    ORDER_CANCELLED = "order_cancelled"
    ORDER_URGENT = "order_urgent"
    ORDER_ADDED = "order_added"
    ORDER_TIME_CHANGED = "order_time_changed"

    # Agent events
    AGENT_BREAK = "agent_break"
    AGENT_OFFLINE = "agent_offline"
    AGENT_AVAILABLE = "agent_available"

    # System events
    ROUTE_OPTIMIZED = "route_optimized"
    FEASIBILITY_CHECK = "feasibility_check"
    ALERT_GENERATED = "alert_generated"


class EventPriority(int, Enum):
    """Event processing priority."""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class RoutingEvent:
    """Base routing event."""

    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: UUID = field(default_factory=uuid4)
    priority: EventPriority = EventPriority.NORMAL
    data: dict = field(default_factory=dict)

    # Context
    agent_id: Optional[UUID] = None
    route_id: Optional[UUID] = None
    order_id: Optional[UUID] = None

    # Processing metadata
    processed: bool = False
    processing_time_ms: float = 0
    action_taken: Optional[str] = None


@dataclass
class GPSEvent(RoutingEvent):
    """GPS position update event."""

    latitude: float = 0.0
    longitude: float = 0.0
    accuracy_meters: float = 0.0
    speed_kmh: float = 0.0
    heading: float = 0.0

    def __post_init__(self):
        self.event_type = EventType.GPS_UPDATE
        self.data = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy": self.accuracy_meters,
            "speed": self.speed_kmh,
            "heading": self.heading,
        }


@dataclass
class TrafficEvent(RoutingEvent):
    """Traffic incident event."""

    incident_type: str = ""  # accident, construction, congestion
    road_segment_id: Optional[str] = None
    delay_minutes: int = 0
    affected_area_km: float = 0.0
    expected_clear_time: Optional[datetime] = None

    def __post_init__(self):
        self.event_type = EventType.TRAFFIC_INCIDENT
        self.priority = EventPriority.HIGH
        self.data = {
            "incident_type": self.incident_type,
            "road_segment": self.road_segment_id,
            "delay_minutes": self.delay_minutes,
            "affected_area_km": self.affected_area_km,
        }


@dataclass
class OrderEvent(RoutingEvent):
    """Order change event."""

    client_id: Optional[UUID] = None
    change_type: str = ""  # cancelled, urgent, time_changed
    new_time_window: Optional[tuple[datetime, datetime]] = None

    def __post_init__(self):
        if self.change_type == "cancelled":
            self.event_type = EventType.ORDER_CANCELLED
        elif self.change_type == "urgent":
            self.event_type = EventType.ORDER_URGENT
            self.priority = EventPriority.HIGH
        else:
            self.event_type = EventType.ORDER_TIME_CHANGED


class EventHandler(ABC):
    """Abstract event handler."""

    @abstractmethod
    async def can_handle(self, event: RoutingEvent) -> bool:
        """Check if handler can process this event."""
        pass

    @abstractmethod
    async def handle(self, event: RoutingEvent) -> Optional[RoutingEvent]:
        """
        Process event.

        Returns:
            Optional follow-up event to process
        """
        pass


class GPSDeviationHandler(EventHandler):
    """Handle GPS deviation from planned route."""

    DEVIATION_THRESHOLD_METERS = 500  # Trigger reroute above this

    def __init__(self, rerouting_service, websocket_manager):
        self.rerouting = rerouting_service
        self.websocket = websocket_manager

    async def can_handle(self, event: RoutingEvent) -> bool:
        return event.event_type == EventType.GPS_UPDATE

    async def handle(self, event: RoutingEvent) -> Optional[RoutingEvent]:
        if not event.agent_id:
            return None

        # Calculate deviation from planned route
        deviation = await self._calculate_deviation(
            event.agent_id,
            event.data.get("latitude"),
            event.data.get("longitude"),
        )

        if deviation > self.DEVIATION_THRESHOLD_METERS:
            logger.info(
                f"GPS deviation detected for agent {event.agent_id}: "
                f"{deviation:.0f}m (threshold: {self.DEVIATION_THRESHOLD_METERS}m)"
            )

            # Trigger rerouting
            result = await self.rerouting.reroute_agent_visits(
                agent_id=event.agent_id,
                current_lat=event.data.get("latitude"),
                current_lon=event.data.get("longitude"),
                reason="gps_deviation",
            )

            # Broadcast update
            await self.websocket.broadcast(
                {
                    "type": "route_updated",
                    "agent_id": str(event.agent_id),
                    "reason": "gps_deviation",
                    "deviation_meters": deviation,
                },
                topic=f"agent:{event.agent_id}",
            )

            event.action_taken = "rerouted"

            # Return follow-up event
            return RoutingEvent(
                event_type=EventType.ROUTE_OPTIMIZED,
                agent_id=event.agent_id,
                data={"reason": "gps_deviation", "result": str(result)},
            )

        return None

    async def _calculate_deviation(
        self,
        agent_id: UUID,
        lat: float,
        lon: float,
    ) -> float:
        """Calculate deviation from planned route."""
        # Simplified: would compare against actual route geometry
        # For now, return 0 (no deviation)
        return 0


class TrafficHandler(EventHandler):
    """Handle traffic incidents."""

    def __init__(self, rerouting_service, spatial_index, websocket_manager):
        self.rerouting = rerouting_service
        self.spatial_index = spatial_index
        self.websocket = websocket_manager

    async def can_handle(self, event: RoutingEvent) -> bool:
        return event.event_type in (
            EventType.TRAFFIC_INCIDENT,
            EventType.ROAD_CLOSURE,
        )

    async def handle(self, event: RoutingEvent) -> Optional[RoutingEvent]:
        # Find affected agents
        affected_agents = await self._find_affected_agents(event)

        if not affected_agents:
            return None

        logger.info(
            f"Traffic incident affects {len(affected_agents)} agents"
        )

        # Reroute affected agents
        for agent_id in affected_agents:
            await self.rerouting.reroute_agent_visits(
                agent_id=agent_id,
                reason="traffic_incident",
                avoid_segments=[event.data.get("road_segment")],
            )

            # Notify agent
            await self.websocket.broadcast(
                {
                    "type": "traffic_alert",
                    "incident": event.data,
                    "action": "rerouting",
                },
                topic=f"agent:{agent_id}",
            )

        event.action_taken = f"rerouted_{len(affected_agents)}_agents"

        return RoutingEvent(
            event_type=EventType.ALERT_GENERATED,
            data={
                "alert_type": "traffic_reroute",
                "affected_agents": len(affected_agents),
            },
        )

    async def _find_affected_agents(
        self,
        event: RoutingEvent,
    ) -> list[UUID]:
        """Find agents whose routes pass through affected area."""
        # Simplified: would use spatial index to find nearby agents
        return []


class OrderChangeHandler(EventHandler):
    """Handle order changes (cancellation, urgency, time changes)."""

    def __init__(self, rerouting_service, websocket_manager):
        self.rerouting = rerouting_service
        self.websocket = websocket_manager

    async def can_handle(self, event: RoutingEvent) -> bool:
        return event.event_type in (
            EventType.ORDER_CANCELLED,
            EventType.ORDER_URGENT,
            EventType.ORDER_ADDED,
            EventType.ORDER_TIME_CHANGED,
        )

    async def handle(self, event: RoutingEvent) -> Optional[RoutingEvent]:
        if not event.agent_id:
            return None

        if event.event_type == EventType.ORDER_CANCELLED:
            # Remove from route and optimize remaining
            result = await self.rerouting.remove_and_reoptimize(
                agent_id=event.agent_id,
                order_id=event.order_id,
            )
            event.action_taken = "removed_and_reoptimized"

        elif event.event_type == EventType.ORDER_URGENT:
            # Bump priority and reorder
            result = await self.rerouting.prioritize_order(
                agent_id=event.agent_id,
                order_id=event.order_id,
                priority=100,
            )
            event.action_taken = "prioritized"

        elif event.event_type == EventType.ORDER_ADDED:
            # Insert into optimal position
            result = await self.rerouting.insert_order(
                agent_id=event.agent_id,
                order_id=event.order_id,
            )
            event.action_taken = "inserted"

        # Notify agent and dispatcher
        await self.websocket.broadcast(
            {
                "type": "route_updated",
                "agent_id": str(event.agent_id),
                "reason": event.event_type.value,
                "order_id": str(event.order_id) if event.order_id else None,
            },
            topic=f"agent:{event.agent_id}",
        )

        return None


class EventPipeline:
    """
    Event processing pipeline.

    Features:
    - Priority queue for event processing
    - Multiple handlers per event type
    - Async processing with backpressure
    - Event persistence for replay
    """

    def __init__(
        self,
        max_queue_size: int = 1000,
        max_concurrent: int = 10,
    ):
        self.handlers: list[EventHandler] = []
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=max_queue_size
        )
        self.max_concurrent = max_concurrent
        self._running = False
        self._workers: list[asyncio.Task] = []

        # Metrics
        self.events_processed = 0
        self.events_dropped = 0
        self.avg_processing_time_ms = 0

    def register_handler(self, handler: EventHandler) -> None:
        """Register event handler."""
        self.handlers.append(handler)
        logger.info(f"Registered handler: {handler.__class__.__name__}")

    async def submit(self, event: RoutingEvent) -> bool:
        """
        Submit event for processing.

        Returns:
            True if event was queued, False if queue full
        """
        try:
            # Priority queue: lower number = higher priority
            priority = -event.priority.value
            self.queue.put_nowait((priority, event.timestamp, event))
            return True
        except asyncio.QueueFull:
            self.events_dropped += 1
            logger.warning(f"Event queue full, dropped: {event.event_type}")
            return False

    async def start(self) -> None:
        """Start event processing workers."""
        if self._running:
            return

        self._running = True
        logger.info(f"Starting event pipeline with {self.max_concurrent} workers")

        for i in range(self.max_concurrent):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

    async def stop(self) -> None:
        """Stop event processing."""
        self._running = False

        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        logger.info("Event pipeline stopped")

    async def _worker(self, worker_id: int) -> None:
        """Event processing worker."""
        while self._running:
            try:
                # Wait for event with timeout
                priority, timestamp, event = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=1.0,
                )

                await self._process_event(event)
                self.queue.task_done()

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")

    async def _process_event(self, event: RoutingEvent) -> None:
        """Process single event through handlers."""
        import time
        start = time.time()

        try:
            for handler in self.handlers:
                if await handler.can_handle(event):
                    follow_up = await handler.handle(event)

                    if follow_up:
                        await self.submit(follow_up)

            event.processed = True

        except Exception as e:
            logger.error(f"Event processing error: {e}", exc_info=True)

        finally:
            processing_time = (time.time() - start) * 1000
            event.processing_time_ms = processing_time

            # Update metrics
            self.events_processed += 1
            self.avg_processing_time_ms = (
                self.avg_processing_time_ms * 0.9 +
                processing_time * 0.1
            )

    def get_metrics(self) -> dict:
        """Get pipeline metrics."""
        return {
            "events_processed": self.events_processed,
            "events_dropped": self.events_dropped,
            "queue_size": self.queue.qsize(),
            "avg_processing_time_ms": round(self.avg_processing_time_ms, 2),
            "handlers_count": len(self.handlers),
            "workers_count": len(self._workers),
            "running": self._running,
        }


# Factory function
def create_event_pipeline(
    rerouting_service,
    websocket_manager,
    spatial_index=None,
) -> EventPipeline:
    """
    Create configured event pipeline.

    Args:
        rerouting_service: Rerouting service instance
        websocket_manager: WebSocket manager for notifications
        spatial_index: Optional spatial index for traffic queries

    Returns:
        Configured EventPipeline
    """
    pipeline = EventPipeline()

    # Register handlers
    pipeline.register_handler(
        GPSDeviationHandler(rerouting_service, websocket_manager)
    )
    pipeline.register_handler(
        TrafficHandler(rerouting_service, spatial_index, websocket_manager)
    )
    pipeline.register_handler(
        OrderChangeHandler(rerouting_service, websocket_manager)
    )

    return pipeline
