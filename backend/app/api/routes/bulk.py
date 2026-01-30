"""
Bulk Data Import API.

Endpoints:
- POST /api/v1/bulk/orders: Import delivery orders from JSON/CSV
"""
import csv
import io
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, time, datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.delivery_order import DeliveryOrder, OrderStatus
from app.models.client import Client

router = APIRouter(prefix="/bulk", tags=["Bulk Import"])


class BulkOrderSchema(BaseModel):
    """Schema for single order in bulk request."""
    external_id: str
    client_external_id: str # Match by external ID, not UUID
    weight_kg: float
    volume_m3: Optional[float] = 0.0
    order_value: float = 0.0
    delivery_date: date
    time_window_start: Optional[time] = None
    time_window_end: Optional[time] = None
    priority: int = 1
    items: Optional[list] = []


class BulkImportResponse(BaseModel):
    """Response for bulk import."""
    total_processed: int
    success_count: int
    error_count: int
    errors: list[dict] # {index: 1, error: "Client not found"}


@router.post("/orders", response_model=BulkImportResponse)
async def import_orders(
    orders: List[BulkOrderSchema],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Import multiple orders JSON.
    """
    # 1. Prefetch clients to minimize DB calls
    # optimization: fetch all needed clients in one query
    # For now, simple loop with cache check or batch query
    
    # Collect all client_external_ids
    client_ext_ids = {o.client_external_id for o in orders}

    # Fetch clients in single query (efficient for bulk operations)
    from sqlalchemy import select
    query = select(Client).where(Client.external_id.in_(client_ext_ids))
    result = await db.execute(query)
    clients = result.scalars().all()
    client_map = {c.external_id: c for c in clients}

    processed = 0
    success = 0
    errors = []

    for idx, order_data in enumerate(orders):
        processed += 1
        
        try:
            client = client_map.get(order_data.client_external_id)
            if not client:
                errors.append({"index": idx, "error": f"Client {order_data.client_external_id} not found"})
                continue

            # Check for duplicates? external_id on Order? 
            # DeliveryOrder doesn't strictly enforce unique external_id but it should have one.
            # Assuming 'order_number' is external_id in DeliveryOrder model
            
            new_order = DeliveryOrder(
                client_id=client.id,
                external_id=order_data.external_id,
                delivery_date=order_data.delivery_date,
                weight_kg=order_data.weight_kg,
                volume_m3=order_data.volume_m3,
                order_value=order_data.order_value,
                priority=order_data.priority,
                time_window_start=order_data.time_window_start,
                time_window_end=order_data.time_window_end,
                status=OrderStatus.PENDING,
                items=order_data.items
            )
            db.add(new_order)
            success += 1
            
        except Exception as e:
            errors.append({"index": idx, "error": str(e)})

    if success > 0:
        await db.commit()

    return {
        "total_processed": processed,
        "success_count": success,
        "error_count": len(errors),
        "errors": errors
    }
