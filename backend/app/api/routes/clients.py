"""
Client API routes.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.client import Client, ClientCategory
from app.models.agent import Agent
from app.schemas.client import (
    ClientCreate,
    ClientUpdate,
    ClientResponse,
    ClientListResponse,
)

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=ClientListResponse)
async def list_clients(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    agent_id: Optional[UUID] = Query(None, description="Filter by agent"),
    category: Optional[ClientCategory] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Search by name or address"),
    db: AsyncSession = Depends(get_db),
) -> ClientListResponse:
    """Get list of clients with pagination."""
    query = select(Client).options(selectinload(Client.agent))

    if agent_id:
        query = query.where(Client.agent_id == agent_id)

    if category:
        query = query.where(Client.category == category)

    if is_active is not None:
        query = query.where(Client.is_active == is_active)

    if search:
        query = query.where(
            (Client.name.ilike(f"%{search}%")) |
            (Client.address.ilike(f"%{search}%")) |
            (Client.external_id.ilike(f"%{search}%"))
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Get page
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    clients = result.scalars().all()

    items = []
    for client in clients:
        client_dict = {
            **{k: v for k, v in client.__dict__.items() if not k.startswith('_')},
            "agent_name": client.agent.name if client.agent else None,
        }
        items.append(ClientResponse.model_validate(client_dict))

    return ClientListResponse(
        items=items,
        total=total or 0,
        page=page,
        size=size,
    )


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """Get client by ID."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.agent))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return ClientResponse.model_validate({
        **{k: v for k, v in client.__dict__.items() if not k.startswith('_')},
        "agent_name": client.agent.name if client.agent else None,
    })


@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    data: ClientCreate,
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """Create a new client."""
    # Check for duplicate external_id
    existing = await db.execute(
        select(Client).where(Client.external_id == data.external_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Client with external_id '{data.external_id}' already exists"
        )

    # Verify agent exists if specified
    agent_name = None
    if data.agent_id:
        agent_result = await db.execute(
            select(Agent).where(Agent.id == data.agent_id)
        )
        agent = agent_result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=400, detail="Agent not found")
        agent_name = agent.name

    client = Client(**data.model_dump())
    db.add(client)
    await db.commit()
    await db.refresh(client)

    return ClientResponse.model_validate({
        **{k: v for k, v in client.__dict__.items() if not k.startswith('_')},
        "agent_name": agent_name,
    })


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    data: ClientUpdate,
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """Update a client."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.agent))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Verify agent exists if changing
    update_data = data.model_dump(exclude_unset=True)
    if "agent_id" in update_data and update_data["agent_id"]:
        agent_result = await db.execute(
            select(Agent).where(Agent.id == update_data["agent_id"])
        )
        if not agent_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Agent not found")

    for field, value in update_data.items():
        setattr(client, field, value)

    await db.commit()
    await db.refresh(client)

    # Reload with agent
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.agent))
        .where(Client.id == client_id)
    )
    client = result.scalar_one()

    return ClientResponse.model_validate({
        **{k: v for k, v in client.__dict__.items() if not k.startswith('_')},
        "agent_name": client.agent.name if client.agent else None,
    })


@router.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a client."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    await db.delete(client)
    await db.commit()


@router.post("/{client_id}/assign/{agent_id}", response_model=ClientResponse)
async def assign_client_to_agent(
    client_id: UUID,
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """Assign a client to an agent."""
    # Verify client exists
    client_result = await db.execute(select(Client).where(Client.id == client_id))
    client = client_result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Verify agent exists
    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    client.agent_id = agent_id
    await db.commit()
    await db.refresh(client)

    return ClientResponse.model_validate({
        **{k: v for k, v in client.__dict__.items() if not k.startswith('_')},
        "agent_name": agent.name,
    })
