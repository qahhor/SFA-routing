"""
Planning API routes for SFA weekly planning.
"""
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.agent import Agent
from app.models.client import Client
from app.models.visit_plan import VisitPlan, VisitStatus
from app.schemas.planning import (
    WeeklyPlanRequest,
    WeeklyPlanResponse,
    DailyPlanResponse,
    PlannedVisitResponse,
    VisitPlanResponse,
    VisitPlanUpdate,
    VisitPlanListResponse,
)
from app.services.weekly_planner import weekly_planner

router = APIRouter(prefix="/planning", tags=["planning"])


def get_monday(d: date) -> date:
    """Get Monday of the week containing the given date."""
    return d - timedelta(days=d.weekday())


def get_day_name(d: date) -> str:
    """Get day name in English."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[d.weekday()]


@router.post("/weekly", response_model=WeeklyPlanResponse)
async def generate_weekly_plan(
    request: WeeklyPlanRequest,
    db: AsyncSession = Depends(get_db),
) -> WeeklyPlanResponse:
    """
    Generate weekly plan for an agent.

    This endpoint generates an optimized weekly visiting plan considering:
    - Client categories (A=2/week, B=1/week, C=1/2weeks)
    - Geographic clustering for efficient routes
    - Time windows and visit durations
    """
    # Get agent
    agent_result = await db.execute(
        select(Agent).where(Agent.id == request.agent_id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get agent's clients
    clients_result = await db.execute(
        select(Client).where(
            (Client.agent_id == request.agent_id) &
            (Client.is_active == True)
        )
    )
    clients = list(clients_result.scalars().all())

    if not clients:
        raise HTTPException(
            status_code=400,
            detail="Agent has no assigned clients"
        )

    # Ensure week_start is a Monday
    week_start = get_monday(request.week_start_date)
    week_end = week_start + timedelta(days=4)  # Friday

    # Generate plan
    plan = await weekly_planner.generate_weekly_plan(
        agent=agent,
        clients=clients,
        week_start=week_start,
        week_number=request.week_number,
    )

    # Create client lookup for addresses
    client_map = {c.id: c for c in clients}

    # Convert to response format
    daily_plans = []
    for daily_plan in plan.daily_plans:
        visits = []
        for visit in daily_plan.visits:
            client = client_map.get(visit.client_id)
            visits.append(PlannedVisitResponse(
                client_id=visit.client_id,
                client_name=visit.client_name,
                client_address=client.address if client else None,
                sequence_number=visit.sequence_number,
                planned_time=visit.planned_time,
                estimated_arrival=visit.estimated_arrival,
                estimated_departure=visit.estimated_departure,
                distance_from_previous_km=visit.distance_from_previous_km,
                duration_from_previous_minutes=visit.duration_from_previous_minutes,
                latitude=visit.latitude,
                longitude=visit.longitude,
            ))

        daily_plans.append(DailyPlanResponse(
            date=daily_plan.date,
            day_of_week=get_day_name(daily_plan.date),
            visits=visits,
            total_visits=len(visits),
            total_distance_km=daily_plan.total_distance_km,
            total_duration_minutes=daily_plan.total_duration_minutes,
            geometry=daily_plan.geometry,
        ))

    # Save visit plans to database
    for daily_plan in plan.daily_plans:
        for visit in daily_plan.visits:
            visit_plan = VisitPlan(
                agent_id=agent.id,
                client_id=visit.client_id,
                planned_date=daily_plan.date,
                planned_time=visit.planned_time,
                sequence_number=visit.sequence_number,
                estimated_arrival_time=visit.estimated_arrival,
                estimated_departure_time=visit.estimated_departure,
                distance_from_previous_km=visit.distance_from_previous_km,
                duration_from_previous_minutes=visit.duration_from_previous_minutes,
                status=VisitStatus.PLANNED,
            )
            db.add(visit_plan)

    await db.commit()

    return WeeklyPlanResponse(
        agent_id=agent.id,
        agent_name=agent.name,
        week_start=week_start,
        week_end=week_end,
        daily_plans=daily_plans,
        total_visits=plan.total_visits,
        total_distance_km=plan.total_distance_km,
        total_duration_minutes=plan.total_duration_minutes,
        generated_at=datetime.utcnow(),
    )


@router.get("/agent/{agent_id}/week/{week_date}", response_model=WeeklyPlanResponse)
async def get_weekly_plan(
    agent_id: UUID,
    week_date: date,
    db: AsyncSession = Depends(get_db),
) -> WeeklyPlanResponse:
    """Get existing weekly plan for an agent."""
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
        raise HTTPException(
            status_code=404,
            detail="No plan found for this week"
        )

    # Group by date
    plans_by_date: dict[date, list[VisitPlan]] = {}
    for vp in visit_plans:
        if vp.planned_date not in plans_by_date:
            plans_by_date[vp.planned_date] = []
        plans_by_date[vp.planned_date].append(vp)

    # Build response
    daily_plans = []
    total_visits = 0
    total_distance = 0.0
    total_duration = 0

    for day_offset in range(5):
        plan_date = week_start + timedelta(days=day_offset)
        day_visits = plans_by_date.get(plan_date, [])

        visits = []
        day_distance = 0.0
        day_duration = 0

        for vp in day_visits:
            visits.append(PlannedVisitResponse(
                client_id=vp.client_id,
                client_name=vp.client.name,
                client_address=vp.client.address,
                sequence_number=vp.sequence_number,
                planned_time=vp.planned_time,
                estimated_arrival=vp.estimated_arrival_time or vp.planned_time,
                estimated_departure=vp.estimated_departure_time or vp.planned_time,
                distance_from_previous_km=vp.distance_from_previous_km or 0,
                duration_from_previous_minutes=vp.duration_from_previous_minutes or 0,
                latitude=float(vp.client.latitude),
                longitude=float(vp.client.longitude),
            ))
            day_distance += vp.distance_from_previous_km or 0
            day_duration += vp.duration_from_previous_minutes or 0

        daily_plans.append(DailyPlanResponse(
            date=plan_date,
            day_of_week=get_day_name(plan_date),
            visits=visits,
            total_visits=len(visits),
            total_distance_km=day_distance,
            total_duration_minutes=day_duration,
            geometry=None,
        ))

        total_visits += len(visits)
        total_distance += day_distance
        total_duration += day_duration

    return WeeklyPlanResponse(
        agent_id=agent.id,
        agent_name=agent.name,
        week_start=week_start,
        week_end=week_end,
        daily_plans=daily_plans,
        total_visits=total_visits,
        total_distance_km=total_distance,
        total_duration_minutes=total_duration,
        generated_at=visit_plans[0].created_at if visit_plans else datetime.utcnow(),
    )


@router.get("/agent/{agent_id}/day/{plan_date}", response_model=VisitPlanListResponse)
async def get_daily_visits(
    agent_id: UUID,
    plan_date: date,
    db: AsyncSession = Depends(get_db),
) -> VisitPlanListResponse:
    """Get visit plan for a specific day."""
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

    items = []
    for vp in visit_plans:
        items.append(VisitPlanResponse(
            id=vp.id,
            agent_id=vp.agent_id,
            client_id=vp.client_id,
            client_name=vp.client.name,
            client_address=vp.client.address,
            planned_date=vp.planned_date,
            planned_time=vp.planned_time,
            sequence_number=vp.sequence_number,
            status=vp.status,
            distance_from_previous_km=vp.distance_from_previous_km,
            duration_from_previous_minutes=vp.duration_from_previous_minutes,
            actual_arrival_time=vp.actual_arrival_time,
            actual_departure_time=vp.actual_departure_time,
            notes=vp.notes,
            skip_reason=vp.skip_reason,
            created_at=vp.created_at,
            updated_at=vp.updated_at,
        ))

    return VisitPlanListResponse(
        items=items,
        total=len(items),
        date=plan_date,
    )


@router.put("/visit/{visit_id}", response_model=VisitPlanResponse)
async def update_visit(
    visit_id: UUID,
    data: VisitPlanUpdate,
    db: AsyncSession = Depends(get_db),
) -> VisitPlanResponse:
    """Update a visit plan (status, actual times, notes)."""
    result = await db.execute(
        select(VisitPlan)
        .options(selectinload(VisitPlan.client))
        .where(VisitPlan.id == visit_id)
    )
    visit_plan = result.scalar_one_or_none()

    if not visit_plan:
        raise HTTPException(status_code=404, detail="Visit plan not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(visit_plan, field, value)

    await db.commit()
    await db.refresh(visit_plan)

    return VisitPlanResponse(
        id=visit_plan.id,
        agent_id=visit_plan.agent_id,
        client_id=visit_plan.client_id,
        client_name=visit_plan.client.name,
        client_address=visit_plan.client.address,
        planned_date=visit_plan.planned_date,
        planned_time=visit_plan.planned_time,
        sequence_number=visit_plan.sequence_number,
        status=visit_plan.status,
        distance_from_previous_km=visit_plan.distance_from_previous_km,
        duration_from_previous_minutes=visit_plan.duration_from_previous_minutes,
        actual_arrival_time=visit_plan.actual_arrival_time,
        actual_departure_time=visit_plan.actual_departure_time,
        notes=visit_plan.notes,
        skip_reason=visit_plan.skip_reason,
        created_at=visit_plan.created_at,
        updated_at=visit_plan.updated_at,
    )
