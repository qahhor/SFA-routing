"""
WebSocket Manager for real-time updates.

Handles:
- Active connections management
- Broadcasting events (GPS updates, order status)
- Targeted notifications
"""

import logging
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections for real-time features.
    """

    def __init__(self):
        # active_connections: dict[user_id, list[WebSocket]]
        # A user can have multiple connections (multiple tabs/devices)
        self.active_connections: Dict[UUID, List[WebSocket]] = {}

        # Topic subscriptions (e.g., "dispatchers", "agent:{id}")
        # subscriptions: dict[topic, list[WebSocket]]
        self.subscriptions: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: UUID):
        """Accept connection and register user."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: UUID):
        """Remove connection."""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

        # Remove from subscriptions
        for topic in self.subscriptions:
            if websocket in self.subscriptions[topic]:
                self.subscriptions[topic].remove(websocket)

    async def subscribe(self, websocket: WebSocket, topic: str):
        """Subscribe websocket to a topic."""
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        if websocket not in self.subscriptions[topic]:
            self.subscriptions[topic].append(websocket)

    async def broadcast(self, message: dict, topic: Optional[str] = None):
        """
        Broadcast message to all connected users or subscribers of a topic.
        """
        if topic:
            if topic in self.subscriptions:
                for connection in self.subscriptions[topic]:
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        logger.debug(f"WebSocket send failed (topic={topic}): {e}")
        else:
            # Broadcast to all
            for user_conns in self.active_connections.values():
                for connection in user_conns:
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        logger.debug(f"WebSocket broadcast failed: {e}")

    async def send_personal_message(self, message: dict, user_id: UUID):
        """Send message to specific user."""
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.debug(f"WebSocket personal message failed (user={user_id}): {e}")


# Global instance
manager = WebSocketManager()
