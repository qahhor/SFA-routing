"""
Realtime sub-package.

Contains real-time processing services:
- Event pipeline for async event processing
- WebSocket manager for live updates
- Spatial index for geo-queries
"""

from app.services.realtime.event_pipeline import (
    BaseEvent,
    EventHandler,
    EventPipeline,
    EventPriority,
    EventType,
    GPSEvent,
    GPSUpdateHandler,
    OrderCancelHandler,
    OrderEvent,
    TrafficAlertHandler,
    TrafficEvent,
    VisitCompleteHandler,
    VisitEvent,
)
from app.services.realtime.spatial_index import (
    FallbackSpatialIndex,
    H3SpatialIndex,
    SpatialEntity,
    create_spatial_index,
)
from app.services.realtime.websocket_manager import WebSocketManager, ws_manager

__all__ = [
    # Event pipeline
    "EventPipeline",
    "EventType",
    "EventPriority",
    "BaseEvent",
    "GPSEvent",
    "TrafficEvent",
    "OrderEvent",
    "VisitEvent",
    "EventHandler",
    "GPSUpdateHandler",
    "TrafficAlertHandler",
    "OrderCancelHandler",
    "VisitCompleteHandler",
    # WebSocket
    "WebSocketManager",
    "ws_manager",
    # Spatial
    "SpatialEntity",
    "H3SpatialIndex",
    "FallbackSpatialIndex",
    "create_spatial_index",
]
