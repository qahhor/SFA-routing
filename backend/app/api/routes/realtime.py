"""
Real-time routes for WebSocket communication and dynamic re-routing.

Features:
- GPS tracking and updates
- Real-time route re-optimization
- Push notifications to agents/dispatchers
- Live order status updates
"""

import logging
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Body,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token, get_dispatcher_user
from app.models.agent import Agent
from app.models.user import User
from app.services import rerouting_service
from app.services import ws_manager as manager
from app.services.planning.rerouting import RerouteResult

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Realtime"])


# ============================================================
# Schemas
# ============================================================


class GPSUpdate(BaseModel):
    """GPS update from agent/driver."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    speed: Optional[float] = Field(None, ge=0, description="Speed in km/h")
    heading: Optional[float] = Field(None, ge=0, le=360, description="Heading in degrees")
    accuracy: Optional[float] = Field(None, ge=0, description="Accuracy in meters")
    timestamp: Optional[int] = Field(None, description="Unix timestamp")


class RerouteRequestSchema(BaseModel):
    """Request to re-optimize a route."""

    agent_id: Optional[UUID] = None
    route_id: Optional[UUID] = None
    current_latitude: Optional[float] = Field(None, ge=-90, le=90)
    current_longitude: Optional[float] = Field(None, ge=-180, le=180)
    reason: str = Field("manual", description="Reason for re-routing")


class AddStopRequest(BaseModel):
    """Request to add urgent stop to route."""

    route_id: UUID
    order_id: UUID
    insert_position: str = Field("optimal", pattern="^(optimal|next|last)$")


class RerouteResponse(BaseModel):
    """Response from re-routing operation."""

    success: bool
    message: str
    stops_reordered: int = 0
    distance_saved_m: int = 0
    time_saved_s: int = 0
    new_route_order: list[str] = []


# ============================================================
# WebSocket Authentication
# ============================================================


async def get_current_user_ws(
    websocket: WebSocket,
    token: str,
    db: AsyncSession,
) -> Optional[User]:
    """Authenticate WebSocket user."""
    try:
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            return None

        return user
    except Exception as e:
        logger.warning(f"WebSocket auth failed: {e}")
        return None


# ============================================================
# WebSocket Endpoint
# ============================================================


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint for real-time updates.

    Message types (client -> server):
    - gps_update: Agent location update
    - ping: Keep-alive
    - subscribe: Subscribe to topic
    - request_reroute: Request route re-optimization

    Message types (server -> client):
    - pong: Response to ping
    - agent_location: Agent position broadcast
    - route_updated: Route was re-optimized
    - your_route_updated: Your route changed
    - notification: General notification
    """
    user = await get_current_user_ws(websocket, token, db)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, user.id)
    logger.info(f"WebSocket connected: user {user.id}")

    # Auto-subscribe based on role
    if user.is_dispatcher or user.is_admin:
        await manager.subscribe(websocket, "dispatchers")

    if user.agent_id:
        await manager.subscribe(websocket, f"agent:{user.agent_id}")

    await manager.subscribe(websocket, f"user:{user.id}")

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "gps_update":
                await handle_gps_update(data, user, db)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong", "ts": datetime.utcnow().isoformat()})

            elif msg_type == "subscribe":
                topic = data.get("topic")
                if topic and _can_subscribe(user, topic):
                    await manager.subscribe(websocket, topic)
                    await websocket.send_json({"type": "subscribed", "topic": topic})

            elif msg_type == "request_reroute":
                if user.is_dispatcher or user.is_admin:
                    result = await handle_reroute_request(data, db)
                    await websocket.send_json(
                        {
                            "type": "reroute_result",
                            "success": result.success,
                            "message": result.message,
                        }
                    )

            else:
                logger.debug(f"Unknown message type: {msg_type}")

    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
        logger.info(f"WebSocket disconnected: user {user.id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user.id}: {e}")
        manager.disconnect(websocket, user.id)


def _can_subscribe(user: User, topic: str) -> bool:
    """Check if user can subscribe to topic."""
    if user.is_dispatcher or user.is_admin:
        return True

    if topic.startswith("agent:") and user.agent_id:
        return topic == f"agent:{user.agent_id}"

    if topic.startswith("user:"):
        return topic == f"user:{user.id}"

    return False


# ============================================================
# GPS Update Handler
# ============================================================


async def handle_gps_update(data: dict, user: User, db: AsyncSession):
    """
    Handle GPS update from agent.

    - Updates agent position in database
    - Broadcasts to dispatchers
    - Checks for route deviation and triggers re-routing if needed
    """
    if not user.agent_id:
        return

    lat = data.get("latitude")
    lon = data.get("longitude")

    if lat is None or lon is None:
        return

    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return

    ts = datetime.utcnow()
    if data.get("timestamp"):
        try:
            ts = datetime.fromtimestamp(data["timestamp"])
        except (ValueError, OSError):
            pass

    try:
        await db.execute(
            update(Agent)
            .where(Agent.id == user.agent_id)
            .values(current_latitude=lat, current_longitude=lon, last_gps_update=ts)
        )
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to update agent {user.agent_id} location: {e}")
        return

    await manager.broadcast(
        {
            "type": "agent_location",
            "agent_id": str(user.agent_id),
            "user_id": str(user.id),
            "latitude": lat,
            "longitude": lon,
            "speed": data.get("speed"),
            "heading": data.get("heading"),
            "accuracy": data.get("accuracy"),
            "timestamp": ts.isoformat(),
        },
        topic="dispatchers",
    )

    # Auto-reroute check
    try:
        result = await rerouting_service.check_and_reroute_agent(
            db=db,
            agent_id=user.agent_id,
            current_lat=lat,
            current_lon=lon,
        )
        if result and result.success:
            logger.info(f"Auto-rerouted agent {user.agent_id}: saved {result.distance_saved_m}m")
    except Exception as e:
        logger.error(f"Auto-reroute check failed: {e}")


async def handle_reroute_request(data: dict, db: AsyncSession) -> RerouteResult:
    """Handle re-route request from dispatcher."""
    agent_id = data.get("agent_id")
    route_id = data.get("route_id")
    current_lat = data.get("current_latitude")
    current_lon = data.get("current_longitude")

    if agent_id:
        return await rerouting_service.reroute_agent_visits(
            db=db,
            agent_id=UUID(agent_id),
            current_lat=current_lat or 0,
            current_lon=current_lon or 0,
            reason="manual",
        )
    elif route_id:
        return await rerouting_service.reroute_delivery_route(
            db=db,
            route_id=UUID(route_id),
            current_lat=current_lat,
            current_lon=current_lon,
            reason="manual",
        )
    else:
        return RerouteResult(success=False, message="No agent_id or route_id provided")


# ============================================================
# REST Endpoints for Re-routing
# ============================================================


@router.post("/reroute/agent/{agent_id}", response_model=RerouteResponse)
async def reroute_agent(
    agent_id: UUID,
    request: RerouteRequestSchema,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_dispatcher_user),
):
    """
    Manually trigger re-routing for an agent's visits.

    Requires dispatcher or admin role.
    """
    result = await rerouting_service.reroute_agent_visits(
        db=db,
        agent_id=agent_id,
        current_lat=request.current_latitude or 0,
        current_lon=request.current_longitude or 0,
        reason=request.reason,
    )

    return RerouteResponse(
        success=result.success,
        message=result.message,
        stops_reordered=result.stops_reordered,
        distance_saved_m=result.distance_saved_m,
        time_saved_s=result.time_saved_s,
        new_route_order=[str(uid) for uid in result.new_route_order],
    )


@router.post("/reroute/delivery/{route_id}", response_model=RerouteResponse)
async def reroute_delivery(
    route_id: UUID,
    request: RerouteRequestSchema,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_dispatcher_user),
):
    """
    Manually trigger re-routing for a delivery route.

    Requires dispatcher or admin role.
    """
    result = await rerouting_service.reroute_delivery_route(
        db=db,
        route_id=route_id,
        current_lat=request.current_latitude,
        current_lon=request.current_longitude,
        reason=request.reason,
    )

    return RerouteResponse(
        success=result.success,
        message=result.message,
        stops_reordered=result.stops_reordered,
        distance_saved_m=result.distance_saved_m,
        time_saved_s=result.time_saved_s,
        new_route_order=[str(uid) for uid in result.new_route_order],
    )


@router.post("/reroute/add-stop", response_model=RerouteResponse)
async def add_urgent_stop(
    request: AddStopRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_dispatcher_user),
):
    """
    Add an urgent order to an existing delivery route.

    Finds optimal position to insert the stop with minimal distance increase.
    """
    result = await rerouting_service.add_urgent_stop(
        db=db,
        route_id=request.route_id,
        order_id=request.order_id,
        insert_position=request.insert_position,
    )

    return RerouteResponse(
        success=result.success,
        message=result.message,
        stops_reordered=result.stops_reordered,
        new_route_order=[str(uid) for uid in result.new_route_order],
    )


@router.post("/notify", status_code=status.HTTP_202_ACCEPTED)
async def send_notification(
    user_id: UUID = Body(..., embed=True),
    message: dict = Body(..., embed=True),
    admin: User = Depends(get_dispatcher_user),
):
    """Send real-time notification to a user."""
    await manager.send_personal_message(message, user_id)
    return {"status": "sent", "recipient": str(user_id)}


@router.post("/broadcast", status_code=status.HTTP_202_ACCEPTED)
async def broadcast_message(
    topic: str = Body(..., embed=True),
    message: dict = Body(..., embed=True),
    admin: User = Depends(get_dispatcher_user),
):
    """Broadcast message to a topic."""
    await manager.broadcast(message, topic=topic)
    return {"status": "broadcast", "topic": topic}


@router.get("/connections")
async def get_active_connections(
    admin: User = Depends(get_dispatcher_user),
):
    """Get list of active WebSocket connections."""
    return {
        "active_users": len(manager.active_connections),
        "user_ids": [str(uid) for uid in manager.active_connections.keys()],
        "topics": list(manager.subscriptions.keys()),
    }
