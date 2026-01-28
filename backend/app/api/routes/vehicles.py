"""
Vehicle API routes.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.vehicle import Vehicle
from app.schemas.vehicle import (
    VehicleCreate,
    VehicleUpdate,
    VehicleResponse,
    VehicleListResponse,
)

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("", response_model=VehicleListResponse)
async def list_vehicles(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Search by name or license plate"),
    db: AsyncSession = Depends(get_db),
) -> VehicleListResponse:
    """Get list of vehicles with pagination."""
    query = select(Vehicle)

    if is_active is not None:
        query = query.where(Vehicle.is_active == is_active)

    if search:
        query = query.where(
            (Vehicle.name.ilike(f"%{search}%")) |
            (Vehicle.license_plate.ilike(f"%{search}%"))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Get page
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    vehicles = result.scalars().all()

    items = [VehicleResponse.model_validate(v) for v in vehicles]

    return VehicleListResponse(
        items=items,
        total=total or 0,
        page=page,
        size=size,
    )


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(
    vehicle_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> VehicleResponse:
    """Get vehicle by ID."""
    result = await db.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
    vehicle = result.scalar_one_or_none()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return VehicleResponse.model_validate(vehicle)


@router.post("", response_model=VehicleResponse, status_code=201)
async def create_vehicle(
    data: VehicleCreate,
    db: AsyncSession = Depends(get_db),
) -> VehicleResponse:
    """Create a new vehicle."""
    # Check for duplicate license plate
    existing = await db.execute(
        select(Vehicle).where(Vehicle.license_plate == data.license_plate)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Vehicle with license plate '{data.license_plate}' already exists"
        )

    vehicle = Vehicle(**data.model_dump())
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)

    return VehicleResponse.model_validate(vehicle)


@router.put("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: UUID,
    data: VehicleUpdate,
    db: AsyncSession = Depends(get_db),
) -> VehicleResponse:
    """Update a vehicle."""
    result = await db.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
    vehicle = result.scalar_one_or_none()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    update_data = data.model_dump(exclude_unset=True)

    # Check license plate uniqueness if changing
    if "license_plate" in update_data:
        existing = await db.execute(
            select(Vehicle).where(
                (Vehicle.license_plate == update_data["license_plate"]) &
                (Vehicle.id != vehicle_id)
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Vehicle with license plate '{update_data['license_plate']}' already exists"
            )

    for field, value in update_data.items():
        setattr(vehicle, field, value)

    await db.commit()
    await db.refresh(vehicle)

    return VehicleResponse.model_validate(vehicle)


@router.delete("/{vehicle_id}", status_code=204)
async def delete_vehicle(
    vehicle_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a vehicle."""
    result = await db.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
    vehicle = result.scalar_one_or_none()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    await db.delete(vehicle)
    await db.commit()
