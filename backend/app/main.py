"""
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.redis import redis_client
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.logging import setup_logging, RequestLoggingMiddleware
from app.core.middleware.idempotency import IdempotencyMiddleware
from app.core.sentry import init_sentry
from app.core.metrics import PrometheusMiddleware, metrics_endpoint, update_service_health
from app.core.exceptions import register_exception_handlers
from app.api.routes import api_router

# Setup logging
setup_logging(
    level="DEBUG" if settings.DEBUG else "INFO",
    json_format=not settings.DEBUG,
)

logger = logging.getLogger(__name__)

# Initialize Sentry (if configured)
init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting application...")
    await init_db()

    # Initial health check of external services
    await _check_external_services()

    logger.info("Application started successfully")
    yield
    # Shutdown
    logger.info("Shutting down application...")
    await close_db()
    await redis_client.close()
    logger.info("Application shutdown complete")


async def _check_external_services():
    """Check and report health of external services on startup."""
    from app.services.osrm_client import osrm_client
    from app.services.vroom_solver import vroom_solver

    # Check OSRM
    try:
        osrm_healthy = await osrm_client.health_check()
        update_service_health("osrm", osrm_healthy)
        if osrm_healthy:
            logger.info("OSRM service: healthy")
        else:
            logger.warning("OSRM service: unhealthy")
    except Exception as e:
        update_service_health("osrm", False)
        logger.warning(f"OSRM service check failed: {e}")

    # Check VROOM
    try:
        vroom_healthy = await vroom_solver.health_check()
        update_service_health("vroom", vroom_healthy)
        if vroom_healthy:
            logger.info("VROOM service: healthy")
        else:
            logger.warning("VROOM service: unhealthy")
    except Exception as e:
        update_service_health("vroom", False)
        logger.warning(f"VROOM service check failed: {e}")

    # Check Redis
    try:
        await redis_client.ping()
        update_service_health("redis", True)
        logger.info("Redis service: healthy")
    except Exception as e:
        update_service_health("redis", False)
        logger.warning(f"Redis service check failed: {e}")


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

    # Standardized exception handlers (must be registered first)
    register_exception_handlers(app)

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Prometheus metrics middleware
    if settings.METRICS_ENABLED:
        app.add_middleware(PrometheusMiddleware)

    # Request logging middleware
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

    # Metrics endpoint (outside API prefix)
    if settings.METRICS_ENABLED:
        app.add_api_route(
            settings.METRICS_PATH,
            metrics_endpoint,
            methods=["GET"],
            include_in_schema=False,
        )

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
        "metrics": settings.METRICS_PATH if settings.METRICS_ENABLED else None,
    }
