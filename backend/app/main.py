"""
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.redis import redis_client
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.logging import setup_logging, RequestLoggingMiddleware
from app.core.middleware.idempotency import IdempotencyMiddleware
from app.api.routes import api_router

# Setup logging
setup_logging(
    level="DEBUG" if settings.DEBUG else "INFO",
    json_format=not settings.DEBUG,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting application...")
    await init_db()
    logger.info("Application started successfully")
    yield
    # Shutdown
    logger.info("Shutting down application...")
    await close_db()
    await redis_client.close()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Route Optimization Service for SFA and Delivery",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        lifespan=lifespan,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Request logging middleware (must be added first to wrap all requests)
    app.add_middleware(RequestLoggingMiddleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Idempotency middleware
    app.add_middleware(IdempotencyMiddleware)

    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    logger.info(f"Application configured: {settings.APP_NAME} v{settings.APP_VERSION}")

    return app


app = create_app()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": f"{settings.API_V1_PREFIX}/docs",
    }
