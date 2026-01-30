"""
Realtime sub-package.

Contains real-time processing services:
- Event pipeline for async event processing
- WebSocket manager for live updates
- Spatial index for geo-queries
"""
from app.services.realtime.event_pipeline import (
    EventPipeline,
    EventType,
    EventPriority,
    BaseEvent,
    GPSEvent,
    TrafficEvent,
    OrderEvent,
    VisitEvent,
    EventHandler,
    GPSUpdateHandler,
    TrafficAlertHandler,
    OrderCancelHandler,
    VisitCompleteHandler,
)
from app.services.realtime.websocket_manager import WebSocketManager, ws_manager
from app.services.realtime.spatial_index import (
    SpatialEntity,
    H3SpatialIndex,
    FallbackSpatialIndex,
    create_spatial_index,
)

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
