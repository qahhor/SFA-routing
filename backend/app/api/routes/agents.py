"""
Agent (Sales Representative) API routes.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, get_dispatcher_user
from app.models.agent import Agent
from app.models.client import Client
from app.models.user import User
from app.schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=AgentListResponse)
async def list_agents(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Search by name or external_id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentListResponse:
    """Get list of agents with pagination."""
    query = select(Agent)

    if is_active is not None:
        query = query.where(Agent.is_active == is_active)

    if search:
        query = query.where(
            (Agent.name.ilike(f"%{search}%")) |
            (Agent.external_id.ilike(f"%{search}%"))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Get page
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    agents = result.scalars().all()

    # Get client counts
    items = []
    for agent in agents:
        client_count_query = select(func.count()).where(Client.agent_id == agent.id)
        clients_count = await db.scalar(client_count_query)

        agent_dict = {
            **agent.__dict__,
            "clients_count": clients_count,
        }
        items.append(AgentResponse.model_validate(agent_dict))

    return AgentListResponse(
        items=items,
        total=total or 0,
        page=page,
        size=size,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """Get agent by ID."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get client count
    client_count_query = select(func.count()).where(Client.agent_id == agent.id)
    clients_count = await db.scalar(client_count_query)

    return AgentResponse.model_validate({
        **agent.__dict__,
        "clients_count": clients_count,
    })


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    data: AgentCreate,
    current_user: User = Depends(get_dispatcher_user),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """Create a new agent."""
    # Check for duplicate external_id
    existing = await db.execute(
        select(Agent).where(Agent.external_id == data.external_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Agent with external_id '{data.external_id}' already exists"
        )

    agent = Agent(**data.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return AgentResponse.model_validate({**agent.__dict__, "clients_count": 0})


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    data: AgentUpdate,
    current_user: User = Depends(get_dispatcher_user),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """Update an agent."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)

    await db.commit()
    await db.refresh(agent)

    # Get client count
    client_count_query = select(func.count()).where(Client.agent_id == agent.id)
    clients_count = await db.scalar(client_count_query)

    return AgentResponse.model_validate({
        **agent.__dict__,
        "clients_count": clients_count,
    })


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: UUID,
    current_user: User = Depends(get_dispatcher_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an agent."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await db.delete(agent)
    await db.commit()
