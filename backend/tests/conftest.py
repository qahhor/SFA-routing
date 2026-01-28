"""
Pytest configuration and fixtures.
"""
import asyncio
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base, get_db
from app.main import app


# Test database URL (use SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async engine for tests."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for tests."""
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with overridden dependencies."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# Sample data fixtures
@pytest.fixture
def sample_agent_data():
    """Sample agent data for tests."""
    return {
        "external_id": f"agent-{uuid4().hex[:8]}",
        "name": "Test Agent",
        "phone": "+998901234567",
        "email": "test@example.com",
        "start_latitude": 41.311081,
        "start_longitude": 69.279737,
        "work_start": "09:00:00",
        "work_end": "18:00:00",
        "max_visits_per_day": 30,
        "is_active": True,
    }


@pytest.fixture
def sample_client_data():
    """Sample client data for tests."""
    return {
        "external_id": f"client-{uuid4().hex[:8]}",
        "name": "Test Client",
        "address": "Test Address, Tashkent",
        "phone": "+998901234567",
        "latitude": 41.321081,
        "longitude": 69.289737,
        "category": "B",
        "visit_duration_minutes": 15,
        "time_window_start": "09:00:00",
        "time_window_end": "18:00:00",
        "priority": 1,
        "is_active": True,
    }


@pytest.fixture
def sample_vehicle_data():
    """Sample vehicle data for tests."""
    return {
        "name": "Test Vehicle",
        "license_plate": f"01A{uuid4().hex[:3].upper()}AA",
        "capacity_kg": 1000,
        "capacity_volume_m3": 10,
        "start_latitude": 41.311081,
        "start_longitude": 69.279737,
        "work_start": "08:00:00",
        "work_end": "20:00:00",
        "is_active": True,
    }
