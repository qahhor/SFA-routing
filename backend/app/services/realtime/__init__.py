"""
Realtime sub-package.

Contains real-time processing services:
- Event pipeline for async event processing
- WebSocket manager for live updates
- Spatial index for geo-queries
"""

from app.services.realtime.event_pipeline import (
    EventHandler,
    EventPipeline,
    EventPriority,
    EventType,
    GPSDeviationHandler,
    GPSEvent,
    OrderChangeHandler,
    OrderEvent,
    RoutingEvent,
    TrafficEvent,
    TrafficHandler,
)
from app.services.realtime.spatial_index import (
    FallbackSpatialIndex,
    H3SpatialIndex,
    SpatialEntity,
    create_spatial_index,
)
from app.services.realtime.websocket_manager import WebSocketManager, manager

__all__ = [
    # Event pipeline
    "EventPipeline",
    "EventType",
    "EventPriority",
    "RoutingEvent",
    "GPSEvent",
    "TrafficEvent",
    "OrderEvent",
    "EventHandler",
    "GPSDeviationHandler",
    "TrafficHandler",
    "OrderChangeHandler",
    # WebSocket
    "WebSocketManager",
    "manager",
    # Spatial
    "SpatialEntity",
    "H3SpatialIndex",
    "FallbackSpatialIndex",
    "create_spatial_index",
]
