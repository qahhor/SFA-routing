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
    APP_VERSION: str = "1.2.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, staging, production
    LOG_LEVEL: str = "INFO"

    # API
    API_V1_PREFIX: str = "/api/v1"

    # PostgreSQL container settings (used by docker-compose)
    POSTGRES_USER: str = "routeuser"
    POSTGRES_PASSWORD: str = "routepass"
    POSTGRES_DB: str = "routes"

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
    SECRET_KEY: str = ""  # REQUIRED: Must be set in environment
    WEBHOOK_SECRET_KEY: str = ""  # For HMAC webhook signatures
    GEO_ENCRYPTION_KEY: str = ""  # For encrypting geolocation data (GDPR)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7 days
    ALGORITHM: str = "HS256"

    def validate_production_settings(self) -> None:
        """Validate critical settings for production environment."""
        import logging
        import warnings

        logger = logging.getLogger(__name__)

        if self.ENVIRONMENT == "production":
            # Critical security checks
            if not self.SECRET_KEY or self.SECRET_KEY == "":
                raise ValueError("SECRET_KEY must be set in production")
            if len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters")
            if not self.WEBHOOK_SECRET_KEY:
                raise ValueError("WEBHOOK_SECRET_KEY must be set in production")
            if not self.GEO_ENCRYPTION_KEY:
                raise ValueError("GEO_ENCRYPTION_KEY must be set in production")
            if len(self.GEO_ENCRYPTION_KEY) < 32:
                raise ValueError("GEO_ENCRYPTION_KEY must be at least 32 characters")

            # Debug mode check
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production")

            # CORS security check
            insecure_origins = [o for o in self.CORS_ORIGINS if "localhost" in o or "127.0.0.1" in o]
            if insecure_origins:
                warnings.warn(
                    f"CORS_ORIGINS contains localhost entries: {insecure_origins}. "
                    "Consider removing for production.",
                    UserWarning,
                )

            # Monitoring recommendations
            if not self.SENTRY_DSN:
                logger.warning("SENTRY_DSN not configured. Error tracking disabled.")

    # API Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 10  # For unauthenticated requests
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # API Client defaults
    API_CLIENT_DEFAULT_TIER: str = "free"
    API_CLIENT_FREE_RATE_LIMIT: int = 10
    API_CLIENT_FREE_MAX_POINTS: int = 50
    API_CLIENT_FREE_MONTHLY_QUOTA: int = 1000
    API_CLIENT_STANDARD_RATE_LIMIT: int = 60
    API_CLIENT_STANDARD_MAX_POINTS: int = 200
    API_CLIENT_STANDARD_MONTHLY_QUOTA: int = 10000
    API_CLIENT_PREMIUM_RATE_LIMIT: int = 300
    API_CLIENT_PREMIUM_MAX_POINTS: int = 1000
    API_CLIENT_PREMIUM_MONTHLY_QUOTA: int = 100000

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_TASK_ALWAYS_EAGER: bool = False  # Set True for testing

    # Solver settings
    SOLVER_DEFAULT: str = "auto"  # auto, vroom, ortools, genetic, greedy

    # Genetic Algorithm settings
    GA_POPULATION_SIZE: int = 100
    GA_GENERATIONS: int = 500
    GA_MUTATION_RATE: float = 0.15
    GA_ELITE_SIZE: int = 5

    # Geo Security
    GEO_ANONYMIZATION_LEVEL: str = "none"  # none, low, medium, high

    # WebSocket settings
    WS_HEARTBEAT_INTERVAL: int = 30  # seconds
    WS_MAX_CONNECTIONS_PER_AGENT: int = 5

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
