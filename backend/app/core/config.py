"""
Application configuration settings.
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Route Optimization Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, staging, production

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Database (R8: Optimized connection pool)
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/routes"
    DATABASE_POOL_SIZE: int = 20  # Increased from 10
    DATABASE_MAX_OVERFLOW: int = 40  # Increased from 20
    DATABASE_POOL_RECYCLE: int = 1800  # 30 min (reduced from 1 hour for freshness)
    DATABASE_POOL_TIMEOUT: int = 30  # Wait max 30s for a connection
    DATABASE_POOL_PRE_PING: bool = True  # Verify connections before use
    DATABASE_STATEMENT_TIMEOUT: int = 30000  # Statement timeout in ms (30s)

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Cache TTL Strategy (R15: Tiered TTL)
    CACHE_TTL_DISTANCE_MATRIX: int = 604800  # 7 days - road networks rarely change
    CACHE_TTL_ROAD_NETWORK: int = 2592000  # 30 days
    CACHE_TTL_CLIENT_LIST: int = 3600  # 1 hour - reference data
    CACHE_TTL_AGENT_SCHEDULE: int = 1800  # 30 min - semi-static
    CACHE_TTL_AGENT_LOCATION: int = 60  # 1 min - dynamic
    CACHE_TTL_ACTIVE_ROUTES: int = 300  # 5 min - frequently updated
    CACHE_TTL_GPS_POSITION: int = 10  # 10 sec - real-time
    CACHE_TTL_WEEKLY_PLAN: int = 3600  # 1 hour

    # External Services
    OSRM_URL: str = "http://localhost:5000"
    VROOM_URL: str = "http://localhost:3000"

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7 days
    ALGORITHM: str = "HS256"

    # API Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 10  # For unauthenticated requests
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # API Client defaults
    API_CLIENT_DEFAULT_TIER: str = "free"
    API_CLIENT_FREE_RATE_LIMIT: int = 10
    API_CLIENT_FREE_MAX_POINTS: int = 50
    API_CLIENT_FREE_MONTHLY_QUOTA: int = 1000

    # Planning defaults
    DEFAULT_WORK_START: str = "09:00"
    DEFAULT_WORK_END: str = "18:00"
    DEFAULT_VISIT_DURATION_MINUTES: int = 15
    DEFAULT_MAX_VISITS_PER_DAY: int = 30

    # Client categories visit frequency (times per week)
    CATEGORY_A_VISITS_PER_WEEK: int = 2
    CATEGORY_B_VISITS_PER_WEEK: int = 1
    CATEGORY_C_VISITS_PER_WEEK: float = 0.5  # Once every 2 weeks

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Observability
    SENTRY_DSN: Optional[str] = None  # Set to enable Sentry error tracking
    METRICS_ENABLED: bool = True
    METRICS_PATH: str = "/metrics"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

