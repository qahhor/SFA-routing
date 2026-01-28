"""
Real-time routes for WebSocket communication.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, status, Body
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from uuid import UUID

from app.core.database import get_db
from app.core.security import decode_token, get_admin_user
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.agent import Agent
from app.services.websocket_manager import manager
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.agent import Agent
from app.services.websocket_manager import manager

router = APIRouter(tags=["Realtime"])


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
    except Exception:
        return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint for real-time updates.
    
    Query params:
    - token: JWT access token
    """
    user = await get_current_user_ws(websocket, token, db)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, user.id)
    
    # Subscribe to relevant topics based on role
    if user.is_dispatcher or user.is_admin:
        await manager.subscribe(websocket, "dispatchers")
        
    # Subscribe to own updates
    await manager.subscribe(websocket, f"user:{user.id}")

    try:
        while True:
            data = await websocket.receive_json()
            
            # Handle message types
            msg_type = data.get("type")
            
            if msg_type == "gps_update":
                await handle_gps_update(data, user, db)
            
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
        # Handle disconnect (mark offline?)
    except Exception as e:
        print(f"WebSocket error: {e}") # TODO: proper logging
        manager.disconnect(websocket, user.id)


async def handle_gps_update(data: dict, user: User, db: AsyncSession):
    """
    Handle GPS update from agent.
    
    Expected format:
    {
        "type": "gps_update",
        "latitude": 41.123,
        "longitude": 69.123,
        "speed": 60,
        "timestamp": 1234567890
    }
    """
    # Only agents/drivers send GPS updates
    if not user.agent_id:
        return

    lat = data.get("latitude")
    lon = data.get("longitude")
    
    if lat is None or lon is None:
        return

    # Persist to Agent
    try:
        ts = datetime.fromtimestamp(data.get("timestamp")) if data.get("timestamp") else datetime.utcnow()
        
        await db.execute(
            update(Agent)
            .where(Agent.id == user.agent_id)
            .values(
                current_latitude=lat,
                current_longitude=lon,
                last_gps_update=ts
            )
        )
        await db.commit()
    except Exception as e:
        print(f"Failed to update Agent location: {e}")
    
    # Broadcast to dispatchers
    await manager.broadcast(
        {
            "type": "agent_location",
            "agent_id": str(user.agent_id),
            "user_id": str(user.id),
            "latitude": lat,
            "longitude": lon,
            "speed": data.get("speed"),
            "timestamp": data.get("timestamp"),
        },
        topic="dispatchers"
    )


@router.post("/notify", status_code=status.HTTP_202_ACCEPTED)
async def send_notification(
    user_id: UUID = Body(...),
    message: dict = Body(...),
    admin: User = Depends(get_admin_user),
):
    """
    Send real-time notification to a user (Admin only).
    """
    await manager.send_personal_message(message, user_id)
    return {"status": "sent"}
