"""
Database connection and session management.

Features:
- Connection pooling with configurable size
- Automatic connection recycling
- Pre-ping for connection health checking
- Statement timeout for long-running queries
- Pool monitoring endpoints
"""

import logging
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import Pool

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


# Create engine with optimized pool settings
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
    echo=settings.DEBUG,
    # Additional options for asyncpg
    connect_args={
        "server_settings": {
            "statement_timeout": str(settings.DATABASE_STATEMENT_TIMEOUT),
        },
    },
)


# Connection pool event listeners for monitoring
@event.listens_for(Pool, "checkout")
def on_checkout(dbapi_conn, connection_rec, connection_proxy):
    """Called when a connection is checked out from the pool."""
    logger.debug(f"Connection checked out: {id(dbapi_conn)}")


@event.listens_for(Pool, "checkin")
def on_checkin(dbapi_conn, connection_rec):
    """Called when a connection is returned to the pool."""
    logger.debug(f"Connection checked in: {id(dbapi_conn)}")


@event.listens_for(Pool, "connect")
def on_connect(dbapi_conn, connection_rec):
    """Called when a new connection is created."""
    logger.info(f"New database connection created: {id(dbapi_conn)}")


@event.listens_for(Pool, "invalidate")
def on_invalidate(dbapi_conn, connection_rec, exception):
    """Called when a connection is invalidated."""
    logger.warning(f"Connection invalidated: {id(dbapi_conn)}, reason: {exception}")


AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
    logger.info("Database connections closed")


async def get_pool_status() -> dict:
    """
    Get connection pool status for monitoring.

    Returns:
        Dictionary with pool statistics
    """
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
        "pool_recycle_seconds": settings.DATABASE_POOL_RECYCLE,
    }


async def check_db_connection() -> bool:
    """
    Check if database connection is healthy.

    Returns:
        True if connection is healthy, False otherwise
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
