#!/bin/bash
# ==============================================
# SFA-Routing: Production Deployment Script
# ==============================================
# This script automates the deployment process
# Usage: ./scripts/deploy.sh [--build] [--migrate] [--restart]
#
# Options:
#   --build     Rebuild Docker images
#   --migrate   Run database migrations
#   --restart   Restart all services
#   --full      Full deployment (build + migrate + restart)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
LOG_FILE="$PROJECT_ROOT/logs/deploy_$(date +%Y%m%d_%H%M%S).log"

# Ensure logs directory exists
mkdir -p "$PROJECT_ROOT/logs"

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    case $level in
        INFO)  echo -e "${BLUE}[INFO]${NC} $message" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} $message" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" ;;
        OK)    echo -e "${GREEN}[OK]${NC} $message" ;;
    esac

    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

# Check prerequisites
check_prerequisites() {
    log INFO "Checking prerequisites..."

    # Docker
    if ! command -v docker &> /dev/null; then
        log ERROR "Docker is not installed"
        exit 1
    fi

    # Docker Compose
    if ! docker compose version &> /dev/null; then
        log ERROR "Docker Compose v2 is not installed"
        exit 1
    fi

    # .env file
    if [[ ! -f "$PROJECT_ROOT/backend/.env" ]]; then
        log ERROR "backend/.env file not found. Copy from .env.example and configure."
        exit 1
    fi

    log OK "All prerequisites met"
}

# Backup database before deployment
backup_database() {
    log INFO "Creating database backup..."

    local backup_dir="$PROJECT_ROOT/backups"
    local backup_file="$backup_dir/pre_deploy_$(date +%Y%m%d_%H%M%S).sql"
    mkdir -p "$backup_dir"

    if docker compose $COMPOSE_FILES ps db --status running &> /dev/null; then
        docker compose $COMPOSE_FILES exec -T db pg_dumpall -c -U routeuser > "$backup_file" 2>/dev/null || true
        if [[ -s "$backup_file" ]]; then
            log OK "Backup created: $backup_file"
        else
            log WARN "Database backup may be empty or failed"
        fi
    else
        log WARN "Database container not running, skipping backup"
    fi
}

# Build Docker images
build_images() {
    log INFO "Building Docker images..."

    cd "$PROJECT_ROOT"
    docker compose $COMPOSE_FILES build --no-cache

    log OK "Docker images built successfully"
}

# Run database migrations
run_migrations() {
    log INFO "Running database migrations..."

    cd "$PROJECT_ROOT"

    # Wait for database to be ready
    log INFO "Waiting for database to be ready..."
    local max_attempts=30
    local attempt=0

    while ! docker compose $COMPOSE_FILES exec -T db pg_isready -U routeuser &> /dev/null; do
        attempt=$((attempt + 1))
        if [[ $attempt -ge $max_attempts ]]; then
            log ERROR "Database not ready after $max_attempts attempts"
            exit 1
        fi
        sleep 2
    done

    # Run alembic migrations
    docker compose $COMPOSE_FILES exec -T api alembic upgrade head

    log OK "Database migrations completed"
}

# Restart services
restart_services() {
    log INFO "Restarting services..."

    cd "$PROJECT_ROOT"
    docker compose $COMPOSE_FILES down
    docker compose $COMPOSE_FILES up -d

    log OK "Services restarted"
}

# Health check
health_check() {
    log INFO "Running health checks..."

    local max_attempts=30
    local attempt=0

    while true; do
        attempt=$((attempt + 1))

        if curl -sf http://localhost/api/v1/health > /dev/null 2>&1; then
            log OK "API is healthy"
            break
        fi

        if [[ $attempt -ge $max_attempts ]]; then
            log ERROR "Health check failed after $max_attempts attempts"
            log INFO "Check logs with: docker compose $COMPOSE_FILES logs api"
            exit 1
        fi

        log INFO "Waiting for API to be ready... ($attempt/$max_attempts)"
        sleep 5
    done
}

# Show status
show_status() {
    log INFO "Current service status:"
    echo ""
    cd "$PROJECT_ROOT"
    docker compose $COMPOSE_FILES ps
    echo ""

    log INFO "Resource usage:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || true
}

# Parse arguments
DO_BUILD=false
DO_MIGRATE=false
DO_RESTART=false

for arg in "$@"; do
    case $arg in
        --build)   DO_BUILD=true ;;
        --migrate) DO_MIGRATE=true ;;
        --restart) DO_RESTART=true ;;
        --full)    DO_BUILD=true; DO_MIGRATE=true; DO_RESTART=true ;;
        --help|-h)
            echo "Usage: $0 [--build] [--migrate] [--restart] [--full]"
            echo ""
            echo "Options:"
            echo "  --build     Rebuild Docker images"
            echo "  --migrate   Run database migrations"
            echo "  --restart   Restart all services"
            echo "  --full      Full deployment (build + migrate + restart)"
            exit 0
            ;;
        *)
            log ERROR "Unknown option: $arg"
            exit 1
            ;;
    esac
done

# If no options specified, show help
if [[ "$DO_BUILD" == "false" && "$DO_MIGRATE" == "false" && "$DO_RESTART" == "false" ]]; then
    echo "No action specified. Use --help for usage information."
    exit 0
fi

# Main deployment flow
echo "=============================================="
echo "  SFA-Routing Production Deployment"
echo "=============================================="
echo ""

cd "$PROJECT_ROOT"

check_prerequisites

if [[ "$DO_BUILD" == "true" || "$DO_RESTART" == "true" ]]; then
    backup_database
fi

if [[ "$DO_BUILD" == "true" ]]; then
    build_images
fi

if [[ "$DO_RESTART" == "true" ]]; then
    restart_services
fi

if [[ "$DO_MIGRATE" == "true" ]]; then
    run_migrations
fi

health_check
show_status

echo ""
log OK "Deployment completed successfully!"
echo "Log file: $LOG_FILE"
