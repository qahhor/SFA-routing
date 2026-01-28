"""
Export API routes for PDF and data export.
"""
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.agent import Agent
from app.models.client import Client
from app.models.visit_plan import VisitPlan
from app.models.delivery_route import DeliveryRoute
from app.services.pdf_export import pdf_exporter

router = APIRouter(prefix="/export", tags=["export"])


def get_monday(d: date) -> date:
    """Get Monday of the week."""
    return d - timedelta(days=d.weekday())


@router.get("/daily-plan/{agent_id}/{plan_date}")
async def export_daily_plan_pdf(
    agent_id: UUID,
    plan_date: date,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Export daily visit plan as PDF.

    Returns a downloadable PDF file with the day's visit schedule.
    """
    # Get agent
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get visit plans for the day
    result = await db.execute(
        select(VisitPlan)
        .options(selectinload(VisitPlan.client))
        .where(
            (VisitPlan.agent_id == agent_id) &
            (VisitPlan.planned_date == plan_date)
        )
        .order_by(VisitPlan.sequence_number)
    )
    visit_plans = list(result.scalars().all())

    if not visit_plans:
        raise HTTPException(status_code=404, detail="No visits found for this date")

    # Prepare visit data
    visits = []
    total_distance = 0.0
    total_duration = 0

    for vp in visit_plans:
        visits.append({
            "sequence_number": vp.sequence_number,
            "planned_time": vp.planned_time.strftime("%H:%M"),
            "client_name": vp.client.name,
            "client_address": vp.client.address,
            "distance_from_previous_km": vp.distance_from_previous_km or 0,
            "duration_from_previous_minutes": vp.duration_from_previous_minutes or 0,
        })
        total_distance += vp.distance_from_previous_km or 0
        total_duration += vp.duration_from_previous_minutes or 0

    # Generate PDF
    pdf_content = pdf_exporter.export_daily_plan(
        agent_name=agent.name,
        plan_date=plan_date,
        visits=visits,
        total_distance_km=total_distance,
        total_duration_minutes=total_duration,
    )

    filename = f"daily_plan_{agent.name.replace(' ', '_')}_{plan_date.isoformat()}.pdf"

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/weekly-plan/{agent_id}/{week_date}")
async def export_weekly_plan_pdf(
    agent_id: UUID,
    week_date: date,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Export weekly visit plan as PDF.

    Returns a downloadable PDF file with the week's visit schedule.
    """
    # Get agent
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get Monday of the week
    week_start = get_monday(week_date)
    week_end = week_start + timedelta(days=4)

    # Get visit plans for the week
    result = await db.execute(
        select(VisitPlan)
        .options(selectinload(VisitPlan.client))
        .where(
            (VisitPlan.agent_id == agent_id) &
            (VisitPlan.planned_date >= week_start) &
            (VisitPlan.planned_date <= week_end)
        )
        .order_by(VisitPlan.planned_date, VisitPlan.sequence_number)
    )
    visit_plans = list(result.scalars().all())

    if not visit_plans:
        raise HTTPException(status_code=404, detail="No visits found for this week")

    # Group by date
    plans_by_date: dict[date, list[VisitPlan]] = {}
    for vp in visit_plans:
        if vp.planned_date not in plans_by_date:
            plans_by_date[vp.planned_date] = []
        plans_by_date[vp.planned_date].append(vp)

    # Build daily plans
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    daily_plans = []
    total_visits = 0
    total_distance = 0.0

    for day_offset in range(5):
        plan_date = week_start + timedelta(days=day_offset)
        day_visits = plans_by_date.get(plan_date, [])

        visits = []
        day_distance = 0.0
        day_duration = 0

        for vp in day_visits:
            visits.append({
                "sequence_number": vp.sequence_number,
                "planned_time": vp.planned_time.strftime("%H:%M"),
                "client_name": vp.client.name,
                "client_address": vp.client.address,
            })
            day_distance += vp.distance_from_previous_km or 0
            day_duration += vp.duration_from_previous_minutes or 0

        daily_plans.append({
            "day_of_week": days[day_offset],
            "date": plan_date.strftime("%d.%m.%Y"),
            "visits": visits,
            "total_distance_km": day_distance,
            "total_duration_minutes": day_duration,
        })

        total_visits += len(visits)
        total_distance += day_distance

    # Generate PDF
    pdf_content = pdf_exporter.export_weekly_plan(
        agent_name=agent.name,
        week_start=week_start,
        daily_plans=daily_plans,
        total_visits=total_visits,
        total_distance_km=total_distance,
    )

    filename = f"weekly_plan_{agent.name.replace(' ', '_')}_{week_start.isoformat()}.pdf"

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/delivery-route/{route_id}")
async def export_delivery_route_pdf(
    route_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Export delivery route as PDF.

    Returns a downloadable PDF file with the delivery route sheet.
    """
    # Get route with vehicle and stops
    result = await db.execute(
        select(DeliveryRoute)
        .options(
            selectinload(DeliveryRoute.vehicle),
            selectinload(DeliveryRoute.stops),
        )
        .where(DeliveryRoute.id == route_id)
    )
    route = result.scalar_one_or_none()

    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Get client data for stops
    stops = []
    for stop in sorted(route.stops, key=lambda s: s.sequence_number):
        # Get client
        order_result = await db.execute(
            select(Client).where(Client.id == stop.order.client_id)
        )
        client = order_result.scalar_one_or_none()

        stops.append({
            "sequence_number": stop.sequence_number,
            "planned_arrival": stop.planned_arrival.isoformat() if stop.planned_arrival else "",
            "client_name": client.name if client else "Unknown",
            "client_address": client.address if client else "",
            "weight_kg": float(stop.order.weight_kg),
        })

    # Generate PDF
    pdf_content = pdf_exporter.export_delivery_route(
        vehicle_name=route.vehicle.name,
        license_plate=route.vehicle.license_plate,
        route_date=route.route_date,
        stops=stops,
        total_distance_km=float(route.total_distance_km),
        total_weight_kg=float(route.total_weight_kg),
    )

    filename = f"delivery_route_{route.vehicle.license_plate}_{route.route_date.isoformat()}.pdf"

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
