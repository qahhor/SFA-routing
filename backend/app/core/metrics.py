"""
Prometheus metrics for observability.

Exposes metrics for:
- HTTP request latency and counts
- Solver performance
- Database connections
- Cache hit rates
- External service health
"""

import time
from functools import wraps
from typing import Callable

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

# ============================================================
# HTTP Metrics
# ============================================================

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "status_code"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

HTTP_REQUEST_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently in progress",
    ["method", "endpoint"],
)


# ============================================================
# Solver Metrics
# ============================================================

SOLVER_DURATION = Histogram(
    "solver_duration_seconds",
    "Route solver execution time",
    ["solver_type", "problem_size"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

SOLVER_JOBS_TOTAL = Counter(
    "solver_jobs_total",
    "Total solver jobs processed",
    ["solver_type", "status"],
)

SOLVER_QUALITY = Histogram(
    "solver_quality_score",
    "Solution quality score (0-1)",
    ["solver_type"],
    buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0],
)

SOLVER_UNASSIGNED = Histogram(
    "solver_unassigned_jobs",
    "Number of unassigned jobs per solution",
    ["solver_type"],
    buckets=[0, 1, 2, 5, 10, 20, 50, 100],
)


# ============================================================
# Database Metrics
# ============================================================

DB_CONNECTIONS_ACTIVE = Gauge(
    "db_connections_active",
    "Active database connections",
)

DB_CONNECTIONS_IDLE = Gauge(
    "db_connections_idle",
    "Idle database connections",
)

DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Database query duration",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)


# ============================================================
# Cache Metrics
# ============================================================

CACHE_HITS = Counter(
    "cache_hits_total",
    "Cache hits",
    ["cache_type"],
)

CACHE_MISSES = Counter(
    "cache_misses_total",
    "Cache misses",
    ["cache_type"],
)

CACHE_SIZE = Gauge(
    "cache_size_bytes",
    "Cache size in bytes",
    ["cache_type"],
)


# ============================================================
# External Service Metrics
# ============================================================

EXTERNAL_REQUEST_DURATION = Histogram(
    "external_request_duration_seconds",
    "External service request duration",
    ["service", "operation"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

EXTERNAL_REQUEST_TOTAL = Counter(
    "external_requests_total",
    "Total external service requests",
    ["service", "operation", "status"],
)

SERVICE_HEALTH = Gauge(
    "service_health",
    "External service health (1=healthy, 0=unhealthy)",
    ["service"],
)


# ============================================================
# Business Metrics
# ============================================================

ROUTES_GENERATED = Counter(
    "routes_generated_total",
    "Total routes generated",
    ["route_type"],
)

ROUTES_DISTANCE_KM = Histogram(
    "routes_distance_km",
    "Route distance in kilometers",
    buckets=[5, 10, 25, 50, 100, 200, 500],
)

VISITS_PLANNED = Counter(
    "visits_planned_total",
    "Total visits planned",
    ["category"],
)


# ============================================================
# Application Info
# ============================================================

APP_INFO = Info(
    "app",
    "Application information",
)
APP_INFO.info(
    {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }
)


# ============================================================
# Middleware
# ============================================================


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect HTTP request metrics.

    Tracks:
    - Request duration
    - Request count by endpoint and status
    - In-progress requests
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        # Normalize endpoint (replace IDs with placeholders)
        endpoint = self._normalize_path(request.url.path)

        # Track in-progress
        HTTP_REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception:
            status_code = "500"
            raise
        finally:
            duration = time.perf_counter() - start_time

            HTTP_REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
            ).observe(duration)

            HTTP_REQUEST_TOTAL.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
            ).inc()

            HTTP_REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()

        return response

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path by replacing dynamic segments with placeholders.

        /api/v1/agents/123 -> /api/v1/agents/{id}
        """
        parts = path.split("/")
        normalized = []

        for part in parts:
            if not part:
                continue
            # Check if part looks like an ID (UUID or numeric)
            if self._is_id(part):
                normalized.append("{id}")
            else:
                normalized.append(part)

        return "/" + "/".join(normalized) if normalized else "/"

    def _is_id(self, part: str) -> bool:
        """Check if path part is likely an ID."""
        # UUID pattern
        if len(part) == 36 and part.count("-") == 4:
            return True
        # Numeric ID
        if part.isdigit():
            return True
        # Short UUID
        if len(part) >= 20 and all(c.isalnum() or c == "-" for c in part):
            return True
        return False


# ============================================================
# Helper Functions
# ============================================================


def track_solver_execution(
    solver_type: str,
    problem_size: int,
):
    """
    Decorator/context manager to track solver execution.

    Usage:
        with track_solver_execution("vroom", 100) as tracker:
            result = await solver.solve(problem)
            tracker.set_result(result)
    """

    class SolverTracker:
        def __init__(self):
            self.start_time = None
            self.result = None

        def __enter__(self):
            self.start_time = time.perf_counter()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            duration = time.perf_counter() - self.start_time
            size_bucket = self._size_bucket(problem_size)

            SOLVER_DURATION.labels(
                solver_type=solver_type,
                problem_size=size_bucket,
            ).observe(duration)

            if exc_type:
                SOLVER_JOBS_TOTAL.labels(
                    solver_type=solver_type,
                    status="error",
                ).inc()
            else:
                SOLVER_JOBS_TOTAL.labels(
                    solver_type=solver_type,
                    status="success",
                ).inc()

                if self.result:
                    SOLVER_QUALITY.labels(solver_type=solver_type).observe(self.result.quality_score)
                    SOLVER_UNASSIGNED.labels(solver_type=solver_type).observe(len(self.result.unassigned_jobs))

        def set_result(self, result):
            self.result = result

        def _size_bucket(self, size: int) -> str:
            if size <= 10:
                return "1-10"
            elif size <= 50:
                return "11-50"
            elif size <= 100:
                return "51-100"
            elif size <= 500:
                return "101-500"
            else:
                return "500+"

    return SolverTracker()


def track_external_request(service: str, operation: str):
    """
    Decorator to track external service requests.

    Usage:
        @track_external_request("osrm", "table")
        async def get_distance_matrix(...):
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                EXTERNAL_REQUEST_TOTAL.labels(
                    service=service,
                    operation=operation,
                    status="success",
                ).inc()
                return result
            except Exception:
                EXTERNAL_REQUEST_TOTAL.labels(
                    service=service,
                    operation=operation,
                    status="error",
                ).inc()
                raise
            finally:
                duration = time.perf_counter() - start_time
                EXTERNAL_REQUEST_DURATION.labels(
                    service=service,
                    operation=operation,
                ).observe(duration)

        return wrapper

    return decorator


def track_cache(cache_type: str, hit: bool):
    """Record cache hit or miss."""
    if hit:
        CACHE_HITS.labels(cache_type=cache_type).inc()
    else:
        CACHE_MISSES.labels(cache_type=cache_type).inc()


def update_service_health(service: str, healthy: bool):
    """Update external service health status."""
    SERVICE_HEALTH.labels(service=service).set(1 if healthy else 0)


def update_db_pool_metrics(active: int, idle: int):
    """Update database connection pool metrics."""
    DB_CONNECTIONS_ACTIVE.set(active)
    DB_CONNECTIONS_IDLE.set(idle)


# ============================================================
# Metrics Endpoint
# ============================================================


async def metrics_endpoint(request: Request) -> Response:
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format.
    """
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )
