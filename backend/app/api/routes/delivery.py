"""
Delivery optimization API routes.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.delivery_order import DeliveryOrder, OrderStatus
from app.models.delivery_route import DeliveryRoute, DeliveryRouteStop, RouteStatus
from app.models.vehicle import Vehicle
from app.models.client import Client
from app.schemas.delivery import (
    DeliveryOrderCreate,
    DeliveryOrderResponse,
    DeliveryOptimizeRequest,
    DeliveryOptimizeResponse,
    DeliveryRouteResponse,
    DeliveryRouteStopResponse,
    DeliveryRouteListResponse,
)
from app.services.route_optimizer import route_optimizer

router = APIRouter(prefix="/delivery", tags=["delivery"])


@router.post("/orders", response_model=DeliveryOrderResponse, status_code=201)
async def create_order(
    data: DeliveryOrderCreate,
    db: AsyncSession = Depends(get_db),
) -> DeliveryOrderResponse:
    """Create a new delivery order."""
    # Check for duplicate external_id
    existing = await db.execute(
        select(DeliveryOrder).where(DeliveryOrder.external_id == data.external_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Order with external_id '{data.external_id}' already exists"
        )

    # Verify client exists
    client_result = await db.execute(
        select(Client).where(Client.id == data.client_id)
    )
    client = client_result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=400, detail="Client not found")

    order = DeliveryOrder(**data.model_dump())
    db.add(order)
    await db.commit()
    await db.refresh(order)

    return DeliveryOrderResponse(
        **{k: v for k, v in order.__dict__.items() if not k.startswith('_')},
        client_name=client.name,
        client_address=client.address,
    )


@router.get("/orders", response_model=list[DeliveryOrderResponse])
async def list_orders(
    status: Optional[OrderStatus] = Query(None),
    client_id: Optional[UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[DeliveryOrderResponse]:
    """List delivery orders with filters."""
    query = select(DeliveryOrder).options(selectinload(DeliveryOrder.client))

    if status:
        query = query.where(DeliveryOrder.status == status)

    if client_id:
        query = query.where(DeliveryOrder.client_id == client_id)

    if date_from:
        query = query.where(DeliveryOrder.time_window_start >= datetime.combine(
            date_from, datetime.min.time()
        ))

    if date_to:
        query = query.where(DeliveryOrder.time_window_end <= datetime.combine(
            date_to, datetime.max.time()
        ))

    query = query.limit(limit)
    result = await db.execute(query)
    orders = result.scalars().all()

    return [
        DeliveryOrderResponse(
            **{k: v for k, v in o.__dict__.items() if not k.startswith('_')},
            client_name=o.client.name if o.client else None,
            client_address=o.client.address if o.client else None,
        )
        for o in orders
    ]


@router.post("/optimize", response_model=DeliveryOptimizeResponse)
async def optimize_delivery_routes(
    request: DeliveryOptimizeRequest,
    db: AsyncSession = Depends(get_db),
) -> DeliveryOptimizeResponse:
    """
    Optimize delivery routes for given orders and vehicles.

    This endpoint uses VROOM to find optimal routes considering:
    - Vehicle capacities
    - Time windows for deliveries
    - Service times
    - Order priorities
    """
    # Get orders
    orders_result = await db.execute(
        select(DeliveryOrder)
        .options(selectinload(DeliveryOrder.client))
        .where(DeliveryOrder.id.in_(request.order_ids))
    )
    orders = list(orders_result.scalars().all())

    if len(orders) != len(request.order_ids):
        found_ids = {o.id for o in orders}
        missing = [oid for oid in request.order_ids if oid not in found_ids]
        raise HTTPException(
            status_code=400,
            detail=f"Orders not found: {missing}"
        )

    # Get vehicles
    vehicles_result = await db.execute(
        select(Vehicle).where(Vehicle.id.in_(request.vehicle_ids))
    )
    vehicles = list(vehicles_result.scalars().all())

    if len(vehicles) != len(request.vehicle_ids):
        found_ids = {v.id for v in vehicles}
        missing = [vid for vid in request.vehicle_ids if vid not in found_ids]
        raise HTTPException(
            status_code=400,
            detail=f"Vehicles not found: {missing}"
        )

    # Create clients map
    clients_map = {o.client_id: o.client for o in orders if o.client}

    # Optimize
    result = await route_optimizer.optimize(
        orders=orders,
        vehicles=vehicles,
        clients_map=clients_map,
        route_date=request.route_date,
    )

    # Save routes to database
    vehicle_map = {v.id: v for v in vehicles}
    order_map = {o.id: o for o in orders}
    routes_response = []

    for opt_route in result.routes:
        vehicle = vehicle_map.get(opt_route.vehicle_id)
        if not vehicle:
            continue

        # Create route
        route = DeliveryRoute(
            vehicle_id=vehicle.id,
            route_date=request.route_date,
            total_distance_km=Decimal(str(opt_route.total_distance_km)),
            total_duration_minutes=opt_route.total_duration_minutes,
            total_weight_kg=Decimal(str(opt_route.total_weight_kg)),
            total_stops=len(opt_route.stops),
            status=RouteStatus.PLANNED,
            planned_start=opt_route.planned_start,
            planned_end=opt_route.planned_end,
        )
        db.add(route)
        await db.flush()

        stops_response = []
        for stop in opt_route.stops:
            order = order_map.get(stop.order_id)
            client = clients_map.get(stop.client_id)

            # Create stop
            route_stop = DeliveryRouteStop(
                route_id=route.id,
                order_id=stop.order_id,
                sequence_number=stop.sequence_number,
                distance_from_previous_km=Decimal(str(stop.distance_from_previous_km)),
                duration_from_previous_minutes=stop.duration_from_previous_minutes,
                planned_arrival=stop.planned_arrival,
                planned_departure=stop.planned_departure,
            )
            db.add(route_stop)

            # Update order status
            if order:
                order.status = OrderStatus.ASSIGNED

            stops_response.append(DeliveryRouteStopResponse(
                id=route_stop.id,
                order_id=stop.order_id,
                order_external_id=order.external_id if order else None,
                client_id=stop.client_id,
                client_name=stop.client_name,
                client_address=client.address if client else "",
                sequence_number=stop.sequence_number,
                distance_from_previous_km=stop.distance_from_previous_km,
                duration_from_previous_minutes=stop.duration_from_previous_minutes,
                planned_arrival=stop.planned_arrival,
                planned_departure=stop.planned_departure,
                actual_arrival=None,
                actual_departure=None,
                latitude=stop.latitude,
                longitude=stop.longitude,
                weight_kg=stop.weight_kg,
            ))

        routes_response.append(DeliveryRouteResponse(
            id=route.id,
            vehicle_id=vehicle.id,
            vehicle_name=vehicle.name,
            vehicle_license_plate=vehicle.license_plate,
            route_date=request.route_date,
            total_distance_km=float(route.total_distance_km),
            total_duration_minutes=route.total_duration_minutes,
            total_weight_kg=float(route.total_weight_kg),
            total_stops=route.total_stops,
            status=route.status,
            planned_start=route.planned_start,
            planned_end=route.planned_end,
            actual_start=None,
            actual_end=None,
            stops=stops_response,
            geometry=None,
            notes=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ))

    await db.commit()

    return DeliveryOptimizeResponse(
        routes=routes_response,
        unassigned_orders=result.unassigned_orders,
        total_distance_km=result.total_distance_km,
        total_duration_minutes=result.total_duration_minutes,
        total_vehicles_used=result.total_vehicles_used,
        summary=result.summary,
        optimized_at=datetime.utcnow(),
    )


@router.get("/routes", response_model=DeliveryRouteListResponse)
async def list_routes(
    route_date: date,
    vehicle_id: Optional[UUID] = Query(None),
    status: Optional[RouteStatus] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> DeliveryRouteListResponse:
    """List delivery routes for a date."""
    query = (
        select(DeliveryRoute)
        .options(
            selectinload(DeliveryRoute.vehicle),
            selectinload(DeliveryRoute.stops).selectinload(DeliveryRouteStop.order),
        )
        .where(DeliveryRoute.route_date == route_date)
    )

    if vehicle_id:
        query = query.where(DeliveryRoute.vehicle_id == vehicle_id)

    if status:
        query = query.where(DeliveryRoute.status == status)

    result = await db.execute(query)
    routes = result.scalars().all()

    items = []
    for route in routes:
        stops = []
        for stop in route.stops:
            client_result = await db.execute(
                select(Client).where(Client.id == stop.order.client_id)
            )
            client = client_result.scalar_one_or_none()

            stops.append(DeliveryRouteStopResponse(
                id=stop.id,
                order_id=stop.order_id,
                order_external_id=stop.order.external_id,
                client_id=stop.order.client_id,
                client_name=client.name if client else "",
                client_address=client.address if client else "",
                sequence_number=stop.sequence_number,
                distance_from_previous_km=float(stop.distance_from_previous_km),
                duration_from_previous_minutes=stop.duration_from_previous_minutes,
                planned_arrival=stop.planned_arrival,
                planned_departure=stop.planned_departure,
                actual_arrival=stop.actual_arrival,
                actual_departure=stop.actual_departure,
                latitude=float(client.latitude) if client else 0,
                longitude=float(client.longitude) if client else 0,
                weight_kg=float(stop.order.weight_kg),
            ))

        items.append(DeliveryRouteResponse(
            id=route.id,
            vehicle_id=route.vehicle_id,
            vehicle_name=route.vehicle.name,
            vehicle_license_plate=route.vehicle.license_plate,
            route_date=route.route_date,
            total_distance_km=float(route.total_distance_km),
            total_duration_minutes=route.total_duration_minutes,
            total_weight_kg=float(route.total_weight_kg),
            total_stops=route.total_stops,
            status=route.status,
            planned_start=route.planned_start,
            planned_end=route.planned_end,
            actual_start=route.actual_start,
            actual_end=route.actual_end,
            stops=stops,
            geometry=route.geometry,
            notes=route.notes,
            created_at=route.created_at,
            updated_at=route.updated_at,
        ))

    return DeliveryRouteListResponse(
        items=items,
        total=len(items),
        date=route_date,
    )


@router.get("/route/{route_id}", response_model=DeliveryRouteResponse)
async def get_route(
    route_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DeliveryRouteResponse:
    """Get delivery route with geometry for map display."""
    result = await db.execute(
        select(DeliveryRoute)
        .options(
            selectinload(DeliveryRoute.vehicle),
            selectinload(DeliveryRoute.stops).selectinload(DeliveryRouteStop.order),
        )
        .where(DeliveryRoute.id == route_id)
    )
    route = result.scalar_one_or_none()

    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    stops = []
    for stop in route.stops:
        client_result = await db.execute(
            select(Client).where(Client.id == stop.order.client_id)
        )
        client = client_result.scalar_one_or_none()

        stops.append(DeliveryRouteStopResponse(
            id=stop.id,
            order_id=stop.order_id,
            order_external_id=stop.order.external_id,
            client_id=stop.order.client_id,
            client_name=client.name if client else "",
            client_address=client.address if client else "",
            sequence_number=stop.sequence_number,
            distance_from_previous_km=float(stop.distance_from_previous_km),
            duration_from_previous_minutes=stop.duration_from_previous_minutes,
            planned_arrival=stop.planned_arrival,
            planned_departure=stop.planned_departure,
            actual_arrival=stop.actual_arrival,
            actual_departure=stop.actual_departure,
            latitude=float(client.latitude) if client else 0,
            longitude=float(client.longitude) if client else 0,
            weight_kg=float(stop.order.weight_kg),
        ))

    return DeliveryRouteResponse(
        id=route.id,
        vehicle_id=route.vehicle_id,
        vehicle_name=route.vehicle.name,
        vehicle_license_plate=route.vehicle.license_plate,
        route_date=route.route_date,
        total_distance_km=float(route.total_distance_km),
        total_duration_minutes=route.total_duration_minutes,
        total_weight_kg=float(route.total_weight_kg),
        total_stops=route.total_stops,
        status=route.status,
        planned_start=route.planned_start,
        planned_end=route.planned_end,
        actual_start=route.actual_start,
        actual_end=route.actual_end,
        stops=stops,
        geometry=route.geometry,
        notes=route.notes,
        created_at=route.created_at,
        updated_at=route.updated_at,
    )
