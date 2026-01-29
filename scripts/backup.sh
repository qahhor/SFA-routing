#!/bin/bash
# ==============================================
# SFA-Routing: Database Backup Script
# ==============================================
# Creates full PostgreSQL backups
# Usage: ./scripts/backup.sh [--daily] [--compress]
#
# Recommended: Add to crontab for daily backups
# 0 2 * * * /opt/sfa-routing/scripts/backup.sh --daily --compress

set -e

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$PROJECT_ROOT/backups"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
RETENTION_DAYS=30
MAX_BACKUPS=50

# Database credentials (read from .env if exists)
if [[ -f "$PROJECT_ROOT/backend/.env" ]]; then
    source "$PROJECT_ROOT/backend/.env" 2>/dev/null || true
fi
DB_USER="${POSTGRES_USER:-routeuser}"
DB_NAME="${POSTGRES_DB:-routes}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    local level=$1
    shift
    case $level in
        INFO)  echo -e "${GREEN}[INFO]${NC} $*" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} $*" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $*" ;;
    esac
}

# Parse arguments
DAILY_MODE=false
COMPRESS=false

for arg in "$@"; do
    case $arg in
        --daily)    DAILY_MODE=true ;;
        --compress) COMPRESS=true ;;
        --help|-h)
            echo "Usage: $0 [--daily] [--compress]"
            echo ""
            echo "Options:"
            echo "  --daily     Run in daily backup mode (with cleanup)"
            echo "  --compress  Compress backup with gzip"
            exit 0
            ;;
    esac
done

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

cd "$PROJECT_ROOT"

# Check if database container is running
if ! docker compose $COMPOSE_FILES ps db --status running &> /dev/null; then
    log ERROR "Database container is not running"
    exit 1
fi

# Generate backup filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
if $DAILY_MODE; then
    BACKUP_FILE="$BACKUP_DIR/daily_${TIMESTAMP}.sql"
else
    BACKUP_FILE="$BACKUP_DIR/manual_${TIMESTAMP}.sql"
fi

log INFO "Starting database backup..."

# Create backup
if docker compose $COMPOSE_FILES exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists > "$BACKUP_FILE" 2>/dev/null; then
    log INFO "Backup created: $BACKUP_FILE"

    # Compress if requested
    if $COMPRESS && [[ -f "$BACKUP_FILE" ]]; then
        gzip "$BACKUP_FILE"
        BACKUP_FILE="$BACKUP_FILE.gz"
        log INFO "Compressed backup: $BACKUP_FILE"
    fi

    # Show backup size
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log INFO "Backup size: $BACKUP_SIZE"
else
    log ERROR "Backup failed"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Cleanup old backups (only in daily mode)
if $DAILY_MODE; then
    log INFO "Cleaning up old backups (keeping $RETENTION_DAYS days)..."

    # Remove backups older than retention period
    find "$BACKUP_DIR" -name "daily_*.sql*" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

    # Keep maximum number of backups
    BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/daily_*.sql* 2>/dev/null | wc -l)
    if [[ $BACKUP_COUNT -gt $MAX_BACKUPS ]]; then
        log INFO "Removing excess backups (keeping latest $MAX_BACKUPS)..."
        ls -1t "$BACKUP_DIR"/daily_*.sql* | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -f 2>/dev/null || true
    fi
fi

# List recent backups
log INFO "Recent backups:"
ls -lh "$BACKUP_DIR"/*.sql* 2>/dev/null | tail -5 || echo "No backups found"

log INFO "Backup completed successfully!"
